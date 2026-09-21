# Spec: fidx

Índice de busca para uma pasta grande de arquivos de texto. Parte I descreve o comportamento pedido;
Parte II desenha a implementação que serve `_dx.md`.

---

# Part I — Product

## Overview

- **Motivating Problem**: o operador tem uma pasta grande de notas, relatórios exportados e dumps. Para
  achar qualquer coisa ele roda `grep -r` e espera — numa pasta desse tamanho, demora. O comportamento
  observável que resolve isso: depois de um `python -m fidx <dir> index`, o comando
  `python -m fidx <dir> search <termo>` imprime a lista de arquivos que contêm o termo **sem varrer a
  pasta**, respondendo pelo índice. O `index` roda por cron e reprocessa apenas o que mudou.
- **Para quem**: o operador da pasta, na linha de comando, e o cron que mantém o índice em dia.
- **Por que vale**: troca uma varredura de conteúdo por consulta a um índice, e troca a reindexação total
  periódica por reprocessamento apenas do que mudou.

## Goals

- O operador passa a descobrir em quais arquivos um termo aparece consultando um índice, e não relendo a
  pasta.
- O sistema garante que a decisão de reprocessar um arquivo depende **do conteúdo dele**, nunca da data de
  modificação — que neste ambiente não é confiável.
- O sistema garante que um arquivo apagado da pasta deixa de aparecer nos resultados na rodada seguinte.
- Uma reindexação em que nada mudou deixa de custar uma reindexação: nenhuma entrada do índice é reescrita.
- O cron passa a distinguir, pelo código de saída, "não achei nada" de "não consegui rodar".

## User Stories

- Indexação (US-001, US-003): construir o índice e mantê-lo em dia por cron sem reprocessar o que não mudou.
- Busca (US-002): descobrir em quais arquivos um termo aparece.
- Confiabilidade (US-004, US-005): conteúdo manda sobre `mtime`; arquivo removido sai do índice.
- Operação (US-006): mensagens em stderr e códigos de saída distintos.

[Full user stories](_user_stories.md)

## Core Features

- **`index`** — varre o diretório recursivamente, calcula o digest de conteúdo de cada arquivo de texto,
  reprocessa apenas os que entraram ou mudaram, apaga do índice os que sumiram, e imprime um resumo com as
  cinco contagens (novos, alterados, removidos, inalterados, ignorados). É o comando do cron.
- **`search`** — recebe um termo, consulta o índice e imprime os caminhos dos arquivos que o contêm, um por
  linha, relativos ao diretório, em ordem alfabética. Não lê os arquivos da pasta.
- **Interação entre os dois**: o `search` só enxerga o que o último `index` gravou. Nada no `search`
  dispara indexação, e nada no `index` depende de uma busca anterior. Um `search` durante um `index` em
  andamento responde pelo estado da rodada anterior.

## Business Rules

1. **Conteúdo manda.** Um arquivo é considerado alterado se, e somente se, o digest do seu conteúdo difere
   do digest gravado. `mtime` não participa de nenhuma decisão ([ADR-001](adrs/adr-001.md)).
2. **O índice é um espelho da última varredura.** Ao fim de um `index` bem-sucedido, o conjunto de caminhos
   no índice é exatamente o conjunto de arquivos indexáveis encontrados naquela varredura.
3. **Reprocessar substitui, não acumula.** Ao reprocessar um arquivo, todas as entradas antigas dele são
   apagadas antes das novas; um termo que só existia na versão antiga deixa de apontar para ele.
4. **Elegibilidade.** É indexável o arquivo regular cujo nome e cujos diretórios-pai (relativos ao diretório
   indexado) não começam com `.`, e cujo conteúdo decodifica como UTF-8. O que não decodifica ou não pode
   ser lido é **ignorado**: contado no resumo e ausente do índice.
5. **Unidade de busca é a palavra.** Tanto a indexação quanto a consulta quebram o texto pela mesma regra:
   sequências de caracteres de palavra Unicode (`\w+`), em minúsculas. `orca` não encontra `orcamento`.
   Acentuação é preservada: `orçamento` e `Orçamento` são o mesmo termo; `orcamento` é outro.
6. **Consulta com mais de uma palavra é conjunção.** O resultado é a interseção: arquivos que contêm todas
   as palavras do termo, em qualquer posição. Termo sem nenhuma palavra (vazio, só pontuação) não tem
   resultado.
7. **Atomicidade.** Uma execução de `index` é tudo ou nada: interrompida no meio, o índice permanece no
   estado da última execução bem-sucedida.
8. **Exclusividade de escrita.** Duas execuções de `index` no mesmo diretório não se sobrepõem: a segunda
   falha rápido, com mensagem, em vez de esperar ou corromper.
9. **Códigos de saída.** `0` sucesso; `1` busca sem resultado; `2` não foi possível executar. Erro sempre em
   stderr, com stdout vazio.

## User Experience

**Personas**: o operador (interativo, na shell) e o cron (não interativo).

Fluxo do operador:

1. Roda `python -m fidx ~/notas index` uma vez e vê o resumo da construção.
2. Passa a usar `python -m fidx ~/notas search <termo>` no lugar do `grep -r`.
3. Quando o resultado parecer velho, roda `index` de novo — é barato.

Fluxo do cron: uma linha de crontab chamando `index`. Saída curta numa linha para o log; código de saída 2
quando algo impediu a execução.

Acessibilidade e descoberta: `python -m fidx --help` e `python -m fidx <dir> index --help` descrevem os dois
verbos; o `README.md` do repositório já mostra as duas invocações. Saída é texto puro, sem cor, sem
caractere de controle — legível em leitor de tela, em log e em pipe.

## High-Level Technical Constraints

- **Só a biblioteca padrão do Python.** Nenhuma dependência de terceiros, em runtime ou em teste.
- **`make test` tem de passar** — o alvo existente roda `python3 -m unittest discover -s tests -t . -v`.
- **A data de modificação dos arquivos não é confiável** (rsync e checkout de repositório): conteúdo novo
  com data antiga e data nova sem mudança de conteúdo já foram observados.
- **Desempenho, do ponto de vista do operador**: a busca responde sem varrer a pasta; a reindexação de uma
  pasta em que nada mudou não reescreve nenhuma entrada do índice. Ver o limite honesto em *Known Risks*.
- **Privacidade**: o índice guarda caminhos e termos de arquivos do próprio operador, dentro da própria
  pasta; nada sai da máquina e nada é enviado para lugar nenhum.
- **Manejo por agente/operador**: a CLI é a superfície completa — resumo em stdout, erro em stderr, código
  de saída distinto por classe. O índice é um arquivo sqlite3 inspecionável e apagável com `rm`.
- **Extensões**: não se aplica. O fidx é um pacote Python autocontido, sem pontos de extensão.

## Non-Goals (Out of Scope)

- **Buscar por substring, prefixo, regex ou frase.** O pedido é "em quais arquivos o termo aparece"; a busca
  é por palavra inteira. Um `--prefixo` é um acréscimo futuro, não uma omissão desta entrega.
- **Mostrar a linha ou o número da linha do acerto.** O resultado especificado é a lista de arquivos.
- **Ranking de relevância.** Os resultados saem em ordem alfabética, não por pontuação.
- **Observar a pasta em tempo real** (inotify, daemon). A atualização é o `index` do cron.
- **Indexar formatos binários** (PDF, docx, zip). São ignorados e contados.
- **Interface gráfica ou serviço HTTP.** A superfície é a CLI.

## Open Questions

1. A pasta indexada é sempre gravável? O desenho assume que sim e grava `.fidx.sqlite3` dentro dela
   ([ADR-002](adrs/adr-002.md), alternativa 3). Se aparecer uma pasta somente-leitura, a saída é um
   `--index <caminho>` — não decidido porque não foi pedido.
2. Existe algum arquivo individual grande o bastante para não caber confortavelmente em memória? O desenho
   lê cada arquivo de uma vez (ver *Assumptions and Defaults*). Um teto explícito só entra com um caso real.

---

# Part II — Technical

## Executive Summary

Um pacote `fidx` de três módulos sobre a stdlib: `store` (índice sqlite3), `scan` (varredura, digest,
tokenização) e `__main__` (CLI e os dois comandos). O índice é um sqlite3 em `<dir>/.fidx.sqlite3` com uma
tabela invertida escrita à mão — sem FTS5, para não depender de uma opção de compilação do sqlite
([ADR-002](adrs/adr-002.md)). O incremental é decidido por digest SHA-256 do conteúdo, nunca por `mtime`,
porque o ambiente do operador produz datas mentirosas nas duas direções ([ADR-001](adrs/adr-001.md)).

A troca principal: como o veredito é o conteúdo, **toda rodada lê todos os bytes da pasta**. A economia do
incremental está na tokenização e na escrita no índice — que é o custo dominante — e não na leitura.
Isso é consequência direta da restrição declarada, não um descuido; está registrado em *Known Risks* com o
caminho de melhoria.

## MVP Boundary

O MVP são as tasks **task_01 a task_04**, e todas as quatro entram nesta entrega.

- **Slice 1 (task_01 + task_02 + task_03)** resolve o Motivating Problem: `index` constrói e atualiza o
  índice reprocessando só o que mudou, e `search` responde pelo índice em vez de varrer a pasta. Ao fim
  dessa slice o operador já pode aposentar o `grep -r` no uso normal.
- **task_04** fecha o contrato de operação que o cron precisa: códigos de saída, mensagens em stderr,
  atomicidade e execução concorrente.
- **Pós-MVP**: nada previsto.
- **Fora de escopo**: os itens da seção *Non-Goals*.

## Developer Experience

- [Developer experience contract](_dx.md) — cobre a superfície inteira: os dois verbos da CLI
  (`index`, `search`), o formato do resumo, o formato do resultado da busca, as mensagens de erro e os
  códigos de saída.
- Sem `_uiux.md`: a feature não tem superfície visual.

## System Architecture

Três módulos, cada um com uma responsabilidade, mais o pacote já existente:

| Componente         | Responsabilidade                                                                             | Fronteira                                            |
| ------------------ | -------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `fidx/store.py`    | Abrir/criar o índice sqlite3, ler e gravar digests, substituir e apagar termos, consultar     | Conhece sqlite e caminhos relativos. Não toca no disco da pasta indexada nem em stdout. |
| `fidx/scan.py`     | Enumerar arquivos elegíveis, ler bytes, calcular digest, decodificar UTF-8, tokenizar         | Conhece o sistema de arquivos. Não conhece sqlite.   |
| `fidx/__main__.py` | `argparse`, o laço do `index`, o `search`, o resumo, as mensagens de erro e os códigos de saída | Único módulo que escreve em stdout/stderr e define exit code. |
| `fidx/__init__.py` | Pacote (já existe, vazio)                                                                      | —                                                    |

Fluxo do `index`: `__main__` valida o diretório → `store.abrir()` → `BEGIN IMMEDIATE` →
`store.digests()` devolve o mapa `{caminho: digest}` da rodada anterior → para cada item de
`scan.percorrer(dir)`: lê e hasheia; digest igual → conta inalterado e segue; diferente ou ausente →
`scan.tokenizar()` e `store.gravar(caminho, digest, termos)` → ao fim, `store.remover(caminhos_sumidos)` →
`COMMIT` → `__main__` imprime o resumo.

Fluxo do `search`: `__main__` valida o diretório e a existência do índice → `scan.tokenizar(termo)` →
`store.buscar(termos)` → imprime os caminhos ordenados, ou sai com 1.

## Architectural Boundaries

- `store.py` **não** importa `scan`; `scan.py` **não** importa `store`. Os dois são folhas, testáveis
  isoladamente, e só `__main__.py` importa ambos.
- Nenhum dos três importa nada fora da stdlib.
- `store.py` e `scan.py` não imprimem e não chamam `sys.exit`. Toda apresentação e todo código de saída
  ficam em `__main__.py` — é o que mantém `_dx.md` verificável num lugar só.

## Implementation Design

### Core Interfaces

```python
# fidx/scan.py
def percorrer(raiz: Path) -> Iterator[Path]:
    """Caminhos relativos a `raiz` dos arquivos regulares elegíveis (regra 4), em qualquer ordem."""

def ler(caminho: Path) -> tuple[str, str] | None:
    """(digest_sha256, texto) do arquivo; None quando não decodifica como UTF-8 ou não pode ser lido."""

def tokenizar(texto: str) -> set[str]:
    """Palavras Unicode (`\\w+`) em minúsculas. Mesma função para conteúdo e para consulta."""


# fidx/store.py
class Indice:
    @classmethod
    def abrir(cls, raiz: Path, *, criar: bool) -> "Indice":
        """Abre `<raiz>/.fidx.sqlite3`. criar=False e ausente -> FileNotFoundError.
        schema_version divergente -> descarta e recria vazio."""

    def digests(self) -> dict[str, str]:
        """{caminho_relativo: digest} da última indexação."""

    def gravar(self, caminho: str, digest: str, termos: set[str]) -> None:
        """Substitui digest e termos do caminho (apaga os antigos antes)."""

    def remover(self, caminhos: Iterable[str]) -> None: ...

    def buscar(self, termos: set[str]) -> list[str]:
        """Caminhos que contêm todos os termos, ordenados. Conjunto vazio -> []."""

    def __enter__(self) -> "Indice": ...   # BEGIN IMMEDIATE
    def __exit__(self, *exc) -> None:      # COMMIT sem exceção, ROLLBACK com exceção
        ...
```

`Indice.abrir` traduz `sqlite3.OperationalError: database is locked` em uma exceção própria
(`IndiceEmUso`), para que `__main__` produza a mensagem de `_dx.md` sem inspecionar texto de erro do sqlite.

### Data Models

Esquema completo em [ADR-002](adrs/adr-002.md). Campos:

| Tabela     | Coluna    | Tipo | Propósito                                                              |
| ---------- | --------- | ---- | ----------------------------------------------------------------------- |
| `meta`     | `chave`   | TEXT | Chave de metadado; única chave usada é `schema_version`                 |
| `meta`     | `valor`   | TEXT | Valor do metadado; `schema_version` é `"1"`                              |
| `arquivos` | `caminho` | TEXT | Caminho relativo à raiz, com `/` como separador (PK)                     |
| `arquivos` | `digest`  | TEXT | SHA-256 hex do conteúdo em bytes — o estado que decide reprocessar       |
| `termos`   | `termo`   | TEXT | Palavra normalizada (minúscula)                                          |
| `termos`   | `caminho` | TEXT | Caminho do arquivo que contém a palavra                                  |

`termos` é tabela própria (não JSON numa coluna de `arquivos`) porque é exatamente o estado consultado por
igualdade — é o que a busca casa. `meta` guarda só metadado opaco do formato.

Separador de caminho: sempre `/` no índice (`PurePath.as_posix()`), para que o índice não mude de conteúdo
por causa do sistema operacional.

### API Endpoints

Não se aplica: a feature não tem superfície HTTP/UDS. A superfície pública completa é a CLI de `_dx.md`.

## Integration Points

Não se aplica: o fidx não fala com nenhum sistema fora do próprio sistema de arquivos local.

## Impact Analysis

| Componente           | Tipo de impacto | Descrição e risco                                                                                | Ação necessária                          |
| -------------------- | --------------- | ------------------------------------------------------------------------------------------------ | ---------------------------------------- |
| `fidx/__init__.py`   | modificado      | Hoje vazio; continua vazio ou passa a reexportar nada. Risco baixo                                | Manter importável (teste de fumaça atual) |
| `fidx/store.py`      | novo            | Formato do índice em disco. Risco médio: um erro aqui corrompe resultados silenciosamente          | Cobertura de unidade própria (task_01)   |
| `fidx/scan.py`       | novo            | Regras de elegibilidade e tokenização. Risco médio: define o que é encontrável                     | Cobertura de unidade própria (task_02)   |
| `fidx/__main__.py`   | novo            | Contrato da CLI de `_dx.md`. Risco baixo, superfície pequena                                       | Cobertura E2E por subprocesso (task_04)  |
| `tests/test_fumaca.py` | inalterado    | Continua valendo como garantia de que o pacote importa                                             | Nenhuma                                  |
| `Makefile`           | inalterado      | `unittest discover -s tests -t .` já encontra os arquivos novos                                     | Nenhuma                                  |
| `.gitignore`         | modificado      | Acrescentar `.fidx.sqlite3` para não versionar índice gerado em teste manual                        | Uma linha (task_03)                      |
| Pasta do operador    | novo artefato   | Passa a conter `.fidx.sqlite3`. Risco baixo: oculto, ignorado pela própria varredura, apagável       | Documentar no `README.md` (task_03)      |

Sem mudanças incompatíveis: não há estado de usuário anterior, nem superfície pública anterior, nem alvo a
deletar. O `schema_version` do índice é o único formato versionado, e a regra na estreia já é a definitiva:
versão divergente → descarta e reconstrói, sem shim e sem migração.

## Extensibility Integration Plan

Não se aplica. Superfícies verificadas e inalteradas: não há manifesto de extensão, hook, skill, tool, MCP
sidecar ou registry neste repositório — ele contém apenas o pacote `fidx`, `tests/` e o `Makefile`.

## Agent Manageability Plan

A CLI é a superfície de operação completa, para pessoa e para agente:

- `python -m fidx <dir> index` — uma linha de resumo em stdout, com as cinco contagens estáveis e na mesma
  ordem, parseável.
- `python -m fidx <dir> search <termo>` — um caminho por linha, ordenado; nada mais em stdout.
- Códigos de saída distintos por classe (0 / 1 / 2) e toda mensagem de erro em stderr, como em `_dx.md`.
- Estado inspecionável sem o fidx: `sqlite3 <dir>/.fidx.sqlite3 "select count(*) from arquivos"`.
- Reparo: apagar `<dir>/.fidx.sqlite3` e rodar `index` reconstrói tudo.

Saída `--json` não entra: nada no pedido precisa dela e a saída de linhas já é parseável.

## Config Lifecycle

Não se aplica. Sem `config.toml`, sem variáveis de ambiente, sem arquivo de configuração próprio. Os únicos
parâmetros são os argumentos da CLI. Superfícies verificadas: o repositório não tem arquivo de configuração
de aplicação; `.compozy/workspace.toml` é do runtime, não do fidx.

## Testing Approach

- **Framework**: `unittest` da stdlib, executado por `make test`
  (`python3 -m unittest discover -s tests -t . -v`). Sem dependências novas, conforme a restrição.
- **Fixtures**: `tempfile.TemporaryDirectory` com a árvore de arquivos escrita pelo próprio teste; nada de
  fixture versionada. `os.utime()` é a ferramenta para forjar `mtime` mentiroso (US-004).
- **Fakes**: nenhum. sqlite em arquivo temporário e sistema de arquivos real são baratos; fake aqui
  esconderia justamente o que precisa ser provado.
- **Unidade**: `scan` (elegibilidade, digest, decodificação, tokenização) e `store` (esquema, substituição,
  remoção, consulta) isolados, sem passar pela CLI.
- **Integração**: o laço do `index` contra `store` e `scan` reais num diretório temporário — é onde vivem os
  casos de incremental, `mtime` mentiroso, remoção, atomicidade e concorrência.
- **E2E**: `subprocess.run([sys.executable, "-m", "fidx", ...])` num diretório temporário, conferindo stdout,
  stderr e `returncode` exatamente como `_dx.md` descreve.
- Todos os casos concretos estão em [`_tests.md`](_tests.md).

## Development Sequencing

### Build Order

1. **Contratos folha, em paralelo**: `store.py` (task_01) e `scan.py` (task_02). Cada um verifica sua
   fronteira pela própria suíte de unidade; nenhum depende do outro.
2. **Consumidor**: `__main__.py` com `index` e `search` (task_03) — só começa depois que as duas assinaturas
   acima existem, porque é ele quem as costura. Gate: os casos de integração passam.
3. **Contrato de operação** (task_04): códigos de saída, mensagens, atomicidade e concorrência pela
   superfície pública. Gate: os casos E2E passam e `make test` fica verde.

Nenhuma fase de limpeza: não há código anterior a remover.

### Technical Dependencies

Nenhuma bloqueante. Python 3.11+ com `sqlite3` da stdlib (presente na máquina: CPython 3.14, sqlite 3.53.1).
FTS5 não é requisito — ver [ADR-002](adrs/adr-002.md).

## Monitoring and Observability

Não há serviço a observar. A observabilidade é a linha de resumo do `index` (as cinco contagens, que o log
do cron guarda) e o código de saída. Um `index` cujo total de `alterados` vem alto todo dia numa pasta
estável é o sinal de que algo está reescrevendo arquivos — o resumo torna isso visível sem instrumentação
adicional.

## Technical Considerations

### Key Decisions

- **Digest de conteúdo em vez de `mtime`** — [ADR-001](adrs/adr-001.md).
- **sqlite3 com tabela invertida própria, sem FTS5** — [ADR-002](adrs/adr-002.md).
- **Índice dentro da pasta indexada**, em `.fidx.sqlite3`: cai sozinho na regra de ignorar entradas ocultas
  (a mesma que exclui `.git/`), acompanha a pasta se ela for movida e sai com um `rm`. Alternativa
  rejeitada: diretório de cache global, que deixa índice órfão. Reavaliar se surgir pasta somente-leitura.
- **Ignorar entradas ocultas (`.`) em vez de manter uma lista de exclusões** (`.git`, `.svn`, `node_modules`):
  uma regra em vez de uma lista que envelhece, e resolve o caso declarado (pasta que recebe checkout de
  repositório). Custo aceito: um arquivo de texto legítimo começando com `.` não é indexado.
- **Tokenização por `\w+` em minúsculas, acento preservado**: `str.lower()` e `re.findall(r"\w+", ...)`
  resolvem português sem dependência externa. Rejeitado remover acentos por `unicodedata`: faria
  `orcamento` casar com `orçamento`, o que muda a semântica sem ter sido pedido.
- **Termo com várias palavras é conjunção (AND)**, não frase: uma interseção de conjuntos, e é o
  comportamento que mais se aproxima de "em quais arquivos isso aparece".
- **Saída 1 para busca sem resultado**: convenção do `grep`, que é exatamente a ferramenta sendo
  substituída — o operador já tem o hábito, e o cron pode confiar nela.

### Known Risks

- **A leitura completa da pasta a cada rodada** (consequência da ADR-001) é o custo dominante do `index`
  numa pasta grande. Probabilidade: certa; impacto: proporcional ao tamanho da pasta. O que o incremental
  economiza é tokenização e escrita. Mitigação, quando houver medição que justifique: paralelizar a leitura
  e o digest com `ThreadPoolExecutor` — não muda o formato do índice nem o contrato da CLI.
- **Um arquivo individual muito grande** (um dump) é lido inteiro na memória. Probabilidade: baixa mas
  plausível no cenário descrito; impacto: `MemoryError` derrubaria a rodada. Sem teto arbitrário por ora
  (*Open Questions* 2); a atomicidade garante que a queda não deixa índice quebrado.
- **A busca por palavra inteira diverge do `grep`** que o operador usa hoje: `grep orca` acha `orcamento`,
  `fidx search orca` não. Probabilidade: alta de ser notado no primeiro uso; mitigação: está explícito em
  `_dx.md` e nos *Non-Goals*, e um `--prefixo` cabe depois sem mudar o formato do índice.

## Safety Invariants

O `index` é o único caminho sensível (escrita concorrente e interrupção):

1. Toda escrita de uma execução de `index` acontece dentro de uma única transação sqlite; não há `COMMIT`
   intermediário.
2. A transação abre com `BEGIN IMMEDIATE` antes do primeiro arquivo ser lido — o conflito de concorrência
   aparece no início, nunca depois de metade da varredura.
3. Se a transação não chega ao `COMMIT` (exceção, sinal, queda), o índice observável permanece exatamente
   como estava ao fim da execução bem-sucedida anterior.
4. Uma segunda execução de `index` na mesma pasta nunca espera indefinidamente: o `timeout` da conexão é
   curto e o estouro vira `IndiceEmUso` → saída 2.
5. `search` nunca escreve no índice, e nunca falha por haver um `index` em andamento: a conexão é
   somente-leitura sobre um índice em modo WAL.
6. Nenhum arquivo da pasta indexada é aberto para escrita em nenhum dos dois comandos; o único arquivo
   gravado é `<raiz>/.fidx.sqlite3`.

## File References

### Repo Files

- `fidx/__init__.py` — pacote alvo, hoje vazio; é onde `store.py`, `scan.py` e `__main__.py` entram.
- `tests/test_fumaca.py` — o único teste existente; mostra a convenção de `unittest` a seguir e continua
  valendo como garantia de que o pacote importa.
- `Makefile:2-4` — o comando exato que `make test` roda (`unittest discover -s tests -t .`); define onde os
  arquivos de teste precisam morar para serem descobertos.
- `README.md` — as duas invocações prometidas ao operador; `_dx.md` precisa continuar de acordo com ele.
- `.gitignore` — recebe `.fidx.sqlite3`.

### External References

Nenhuma fonte externa vendorizada neste repositório.

### Design and Analysis Sources

- [ADR-001](adrs/adr-001.md) — por que o digest de conteúdo, e o custo que ele impõe.
- [ADR-002](adrs/adr-002.md) — o formato do índice e o esquema sqlite completo.

## Assumptions and Defaults

- Índice em `<diretorio>/.fidx.sqlite3`; a pasta indexada é gravável (*Open Questions* 1).
- `schema_version = "1"`; divergência descarta e reconstrói.
- Digest: SHA-256 hex do conteúdo em bytes.
- Codificação de conteúdo: UTF-8 estrito. O que não decodifica é ignorado e contado — nada de
  `errors="ignore"`, que transformaria binário em termos-lixo dentro do índice.
- Tokenização: `re.findall(r"\w+", texto.lower())`, Unicode, acentos preservados.
- Varredura: `os.walk` sem seguir links simbólicos de diretório (padrão `followlinks=False`, que também
  elimina o risco de ciclo); arquivos que são link simbólico são lidos normalmente.
- Entradas cujo nome começa com `.` são puladas, arquivos e diretórios.
- Caminhos gravados e impressos são relativos à raiz, com `/`, ordenados por `sorted()` (ordem de ponto de
  código; sem `locale`, para que a saída não dependa do ambiente do cron).
- `timeout` da conexão de escrita: 2 segundos — curto o bastante para o cron falhar rápido, folgado o
  bastante para não acusar concorrência que não existe.
- Cada arquivo cabe em memória individualmente (*Open Questions* 2).
- Python 3.11+.

## Architecture Decision Records

- [ADR-001: Detecção de mudança por hash de conteúdo, não por mtime](adrs/adr-001.md) — o que decide
  reprocessar é o SHA-256 do conteúdo; `mtime` não é lido.
- [ADR-002: Índice em sqlite3 com tabela invertida própria](adrs/adr-002.md) — índice em
  `<dir>/.fidx.sqlite3`, esquema de três tabelas, sem FTS5.
