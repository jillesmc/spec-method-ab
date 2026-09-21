# Specification: fidx

Indice de busca incremental para uma pasta grande de arquivos de texto.

---

# Part I — Product

## Overview

- **Motivating Problem**: achar um termo na pasta de notas/relatorios/dumps hoje significa `grep -r`
  e esperar, porque toda busca relê a pasta inteira. O usuario quer pagar a leitura uma vez (num
  `index` agendado por cron) e depois buscar em tempo interativo.
  **Comportamento minimo observavel de ponta a ponta**: depois de `python -m fidx ./notas index`,
  o comando `python -m fidx ./notas search orcamento` imprime os caminhos dos arquivos em que o
  termo aparece, sem varrer a pasta. Slice 1 (task_01) entrega exatamente isso.
- **Para quem**: o operador da pasta — uma pessoa so, na propria maquina, sem servidor, sem daemon.
- **Por que vale**: transforma uma espera de varredura completa em uma consulta por chave; e faz a
  reindexacao periodica custar proporcional ao que mudou, nao ao tamanho da pasta.

## Goals

- O operador consegue perguntar "em quais arquivos aparece X" e receber a lista de caminhos sem
  esperar uma varredura da pasta.
- O `index` roda por cron quantas vezes for preciso e **so reprocessa o que mudou de conteudo**.
- A deteccao de mudanca **nao depende de data de modificacao**: arquivo que volta do rsync com data
  antiga e conteudo novo e reindexado; arquivo com data nova e conteudo igual nao e.
- Arquivo apagado da pasta some do resultado da busca na rodada seguinte.
- Uma rodada interrompida no meio nao deixa o indice corrompido nem meio-atualizado: a busca
  continua respondendo com o estado da ultima rodada completa.
- Nada de dependencia externa: so biblioteca padrao do Python, e `make test` passa.

## User Stories

- **US-001** — busca por termo (o valor principal).
- **US-002** — primeira indexacao de uma pasta.
- **US-003–US-005** — reindexacao incremental: o que mudou, o que mentiu a data, o que sumiu.
- **US-006** — superficie de erro acionavel (pasta invalida, indice ausente, termo sem token).
- **US-007** — operacao por cron: interrupcao, concorrencia, leitura durante a escrita.

[Full user stories](_user_stories.md)

## Core Features

- **`index`** — varre o diretorio, calcula o hash de conteudo de cada arquivo, reprocessa somente os
  arquivos cujo hash mudou (ou que sao novos), remove do indice os que sumiram do disco, e imprime
  uma linha de resumo com total/reindexados/removidos. Roda inteiro dentro de uma transacao.
- **`search <termo>`** — consulta o indice pelo token e imprime os caminhos, um por linha, ordenados.
  Nao toca no conteudo dos arquivos.
- **Interacao entre os dois**: `search` so le o que o ultimo `index` completo gravou. O resultado da
  busca e uma foto da ultima rodada, nao do disco agora (US-001.EC-4).

## Business Rules

1. **O conteudo e a unica autoridade sobre mudanca.** O sinal de mudanca de um arquivo e o SHA-256
   do seu conteudo. `mtime`, `ctime` e tamanho **nao** participam da decisao — nem como atalho
   ("se a data e igual, pula"), porque ja se observou data antiga com conteudo novo e data nova com
   conteudo igual (ADR-001).
2. Um arquivo esta no indice sob exatamente um caminho, relativo a raiz indexada, com separador `/`.
3. Um `path` tem exatamente um hash registrado; reindexar um caminho substitui **todas** as suas
   entradas antigas antes de gravar as novas (sem resto de rodada anterior).
4. Termo e token: o texto e normalizado para minusculas e quebrado em tokens `\w+` (Unicode, logo
   `orcamento` e `orçamento` sao tokens inteiros, e `a,b` sao dois tokens). A busca casa **token
   inteiro**, nao substring — diferenca deliberada em relacao ao `grep` (Assumptions).
5. Busca com varios tokens retorna os arquivos que contem **todos** eles (E logico), em qualquer
   posicao do arquivo. Nao existe busca por frase/adjacencia.
6. Sao ignorados na varredura: qualquer entrada cujo nome comece com `.` (o que cobre `.git/`,
   `.fidx.sqlite3` e seus `-wal`/`-shm`) e qualquer symlink, de arquivo ou de diretorio.
7. Arquivo ilegivel (permissao, sumiu durante a varredura) nao derruba a rodada: e pulado, avisado
   em `stderr`, e o `index` termina com exit 0.
8. Bytes que nao decodificam em UTF-8 sao descartados na decodificacao (`errors="ignore"`); o
   arquivo e indexado com o texto que sobrou. Arquivo vazio e valido: fica registrado, sem tokens.
9. O indice mora **dentro** da pasta indexada, em `<dir>/.fidx.sqlite3`. Perder esse arquivo nunca e
   erro: a rodada seguinte reconstroi tudo.
10. Exit codes sao contrato: `0` ok, `1` busca sem resultado, `2` erro de uso (diretorio invalido,
    indice ausente, termo sem token), `3` indice ocupado por outra rodada.

## User Experience

- **Persona**: operador da propria maquina, terminal aberto, pasta local; e o **cron**, que so le
  exit code e a linha de resumo no log.
- **Fluxo primario**: `python -m fidx ./notas index` uma vez na mao para semear; entrada no crontab
  para manter; `python -m fidx ./notas search <termo>` quando precisar achar algo.
- **Descoberta**: sem argumentos, ou com subcomando desconhecido, o modulo imprime a linha de uso e
  sai com 2. A mensagem de indice ausente **contem o comando exato** que resolve.
- **Acessibilidade**: saida e texto puro em `stdout`, uma ocorrencia por linha, sem cor e sem
  barra de progresso — funciona em pipe, em `xargs` e no log do cron.

Sem superficie grafica: `_uiux.md` nao se aplica (feature de CLI).

## High-Level Technical Constraints

- **So biblioteca padrao do Python** (3.11+), incluindo `sqlite3` e `hashlib`. Nenhuma dependencia
  nova, nenhum servico.
- `make test` (`python3 -m unittest discover -s tests -t .`) tem de passar.
- Desempenho pela otica do usuario: `search` responde em tempo interativo (« 1 s) porque e uma
  consulta indexada; o custo de `index` numa rodada sem mudanca e dominado pela leitura+hash dos
  arquivos, nao por reprocessamento.
- Privacidade: o indice guarda tokens e caminhos da propria pasta do operador, no disco dele; nada
  sai da maquina.
- Operabilidade: tudo que um agente ou script precisa esta no exit code e na linha de resumo; nao
  existe estado escondido fora de `<dir>/.fidx.sqlite3`.
- Sem ecossistema de extensao: o programa e um modulo Python de duas partes.

## Non-Goals (Out of Scope)

- **Ranking/relevancia** (TF-IDF, BM25, ordenacao por score): a pergunta e "em quais arquivos", a
  saida e ordenada por caminho.
- **Numero de linha e trecho de contexto** (o `-n` e o match do grep): o enunciado pede arquivos.
- **Busca por substring, prefixo, regex ou frase**: casamento e por token inteiro (ADR-002).
- **Watcher/daemon/inotify**: quem dispara a reindexacao e o cron.
- **Reuso de postings quando um arquivo so muda de lugar** (mesmo hash, caminho novo): re-tokeniza.
  Adicionar quando medicao mostrar que movimentacao de arquivo domina o custo da rodada.
- **Paralelismo na indexacao** (threads/processos para hash): rodada single-thread.
- **Configuracao** (arquivo de config, env var para a localizacao do indice, lista de exclusao):
  as regras 6 e 9 sao fixas.

## Open Questions

1. Token inteiro em vez de substring muda o resultado em relacao ao `grep` que o usuario usa hoje:
   `search log` **nao** acha `logs` nem `catalogo`. Assumido como aceitavel (Assumptions) — confirmar
   com o operador; se nao for, vira um follow-up de prefixo (`LIKE 'termo%'` sobre a tabela de
   termos), nao uma mudanca de armazenamento.
2. Nao ha limite de tamanho por arquivo: um dump de varios GB e lido inteiro em memoria para
   tokenizar. Assumido que os arquivos cabem; se aparecer dump gigante, o ajuste e tokenizar em
   blocos com sobreposicao de fronteira.

---

# Part II — Technical

## Executive Summary

Dois arquivos novos: `fidx/core.py` (varredura, hash, tokenizacao, armazenamento, as duas operacoes)
e `fidx/__main__.py` (parse de argv, mensagens, exit codes). O armazenamento e um SQLite
(`<dir>/.fidx.sqlite3`) com tres tabelas: `meta`, `files` (caminho → sha256) e `postings`
(termo → caminho). `index` roda em **uma** transacao: para cada arquivo do disco calcula o SHA-256,
compara com o `files` guardado, e so quando difere (ou o caminho e novo) apaga os postings antigos
daquele caminho e grava os novos; caminhos que estavam em `files` e nao apareceram no disco sao
removidos. `search` e um `SELECT ... WHERE term = ?` (intersecao quando o termo tem mais de um
token).

O trade-off honesto e o do ADR-001: como a data nao e confiavel, **toda rodada le todos os bytes**
para hashear. O que o incremental economiza e a tokenizacao e a escrita no indice — que e a parte
cara — nao a leitura. Uma rodada sem mudanca faz zero `INSERT` em `postings`.

## MVP Boundary

MVP = task_01 + task_02. **task_01** entrega o Motivating Problem inteiro (indexar e buscar,
reescrevendo o indice a cada rodada). **task_02** entrega o requisito do cron (so o que mudou de
conteudo e reprocessado, o que sumiu e removido). **task_03** endurece a operacao por cron
(atomicidade, concorrencia, bytes indecifraveis, superficie de erro) — necessario para o uso
descrito, e por isso dentro do escopo, mas depois do valor ja estar de pe. Fora de escopo: tudo em
Non-Goals.

## Developer Experience

- [Developer experience contract](_dx.md) — CLI `python -m fidx <dir> index`, CLI
  `python -m fidx <dir> search <termo>`, formato do resumo, tabela de exit codes e mensagens de erro.
- Sem `_uiux.md`: a feature nao tem superficie visual.

## System Architecture

- **`fidx/__main__.py`** — unica porta de entrada. Le `sys.argv`, valida a forma do comando, chama
  `core`, formata saida e traduz resultado/excecao em exit code. Nenhuma regra de dominio aqui.
- **`fidx/core.py`** — quatro responsabilidades coesas, pequenas demais para justificar modulos
  separados: varredura (`iter_files`), conteudo (`file_digest`, `tokenize`), armazenamento
  (`open_index`, esquema, consultas) e as duas operacoes (`index_dir`, `search`).
- **Fluxo de `index`**: `iter_files` → para cada caminho `file_digest` → compara com o mapa
  `known_files()` → se mudou: `tokenize` → `replace_file` → ao fim `remove_missing` → `COMMIT` →
  devolve `(total, reindexados, removidos)`.
- **Fluxo de `search`**: abre o indice existente → `tokenize(termo)` → intersecao dos postings →
  lista ordenada.
- **Sistema externo**: apenas o filesystem e o arquivo SQLite. Sem rede.

## Architectural Boundaries

- `fidx/__main__.py` importa `fidx.core`. `fidx/core.py` **nao** importa `__main__`, nao le
  `sys.argv`, nao chama `sys.exit` e nao imprime: devolve dados ou levanta excecao. Essa e a razao
  de os testes de unidade e de integracao nao precisarem de subprocesso.
- `fidx/core.py` importa apenas stdlib (`hashlib`, `os`, `re`, `sqlite3`, `pathlib`, `typing`).
- `fidx/__init__.py` continua vazio (o `test_fumaca.py` existente so exige que o pacote importe).
- `tests/` importa `fidx.core` direto; so os casos E2E usam `subprocess` com `python3 -m fidx`.

## Implementation Design

### Core Interfaces

```python
# fidx/core.py
SCHEMA_VERSION = 1
INDEX_NAME = ".fidx.sqlite3"
BUSY_TIMEOUT_S = 30.0

class FidxError(Exception): ...        # base; __main__ traduz em mensagem + exit code
class NotADirectory(FidxError): ...    # exit 2
class IndexMissing(FidxError): ...     # exit 2
class EmptyTerm(FidxError): ...        # exit 2
class IndexBusy(FidxError): ...        # exit 3

def tokenize(text: str) -> list[str]:
    """minusculas + re.findall(r"\\w+"): 'Orcamento, 2026' -> ['orcamento', '2026']"""

def iter_files(root: str) -> Iterator[str]:
    """caminhos relativos posix, ordem estavel; pula entradas com '.' inicial e symlinks."""

def file_digest(path: str) -> str:
    """sha256 hex, lido em blocos de 1 MiB."""

def index_dir(root: str) -> tuple[int, int, int]:
    """(total_no_indice, reindexados, removidos); uma transacao; ilegivel -> pulado + aviso."""

def search(root: str, term: str) -> list[str]:
    """caminhos relativos posix, ordenados, sem repeticao; [] quando nao ha ocorrencia."""
```

### Data Models

`<dir>/.fidx.sqlite3`, `PRAGMA journal_mode=WAL`, `sqlite3.connect(..., timeout=BUSY_TIMEOUT_S)`.

```sql
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
-- meta('schema_version') = '1'

CREATE TABLE files (
  path   TEXT PRIMARY KEY,   -- relativo a raiz, separador '/'
  sha256 TEXT NOT NULL       -- unico sinal de mudanca (ADR-001)
);

CREATE TABLE postings (
  term TEXT NOT NULL,        -- token normalizado
  path TEXT NOT NULL,        -- FK logica para files.path
  PRIMARY KEY (term, path)
) WITHOUT ROWID;             -- PK cobre o lookup por termo; sem rowid duplicado

CREATE INDEX postings_path ON postings(path);  -- apaga postings de um caminho em O(log n)
```

- `files.sha256` e coluna propria, nao JSON: e o campo pelo qual a rodada decide trabalho.
- `postings` e tabela de relacao, nao lista JSON por arquivo: a consulta de busca precisa ser por
  termo, nao por arquivo.
- Sem contagem de ocorrencias por termo: ranking e Non-Goal; a coluna so existiria para ele.
- `meta.schema_version` divergente de `SCHEMA_VERSION` → `index` derruba e recria as tabelas e
  reindexa tudo; `search` levanta `IndexMissing` com a instrucao de rodar `index`.

### API Endpoints

Nao se aplica: a superficie publica e a CLI descrita em `_dx.md`. Sem HTTP, sem UDS.

## Integration Points

Nao se aplica: nenhum sistema externo ao filesystem local.

## Impact Analysis

| Component              | Impact Type | Description and Risk                                                                       | Required Action                                     |
| ---------------------- | ----------- | ------------------------------------------------------------------------------------------ | --------------------------------------------------- |
| `fidx/__init__.py`     | modified    | Continua vazio; so precisa seguir importavel (risco nulo)                                   | Nao mexer alem do necessario                         |
| `fidx/core.py`         | new         | Toda a logica; risco concentrado na deteccao de mudanca e na transacao unica                | task_01 cria, task_02/03 estendem                    |
| `fidx/__main__.py`     | new         | Contrato de exit code e mensagem; risco de divergir de `_dx.md`                             | E2E compara transcricao literal de `_dx.md`          |
| `<dir>/.fidx.sqlite3`  | new         | Estado novo no disco do usuario, dentro da pasta indexada; pode ser apagado pelo rsync      | Perda do arquivo = reconstrucao total, nunca erro    |
| `tests/test_fumaca.py` | modified    | Nenhuma alteracao: segue como guarda de importabilidade do pacote                           | Manter passando                                      |
| `Makefile`             | modified    | Nenhuma: `unittest discover` ja pega os arquivos novos em `tests/`                          | Nao mexer                                            |
| `README.md`            | modified    | Comandos, exit codes e a regra de token inteiro precisam ficar escritos                     | task_03 atualiza                                     |

**Delete targets**: nenhum. Nao ha codigo, storage, comando ou artefato anterior para remover — o
pacote e um esqueleto vazio. Compatibilidade de estado do usuario: o unico estado e o indice, e ele e
**derivado** — versao de esquema diferente da corrente e reconstruida na proxima rodada, sem migracao
e sem shim. Nenhuma superficie publica antiga existe para manter uma release atras.

## Extensibility Integration Plan

Nao se aplica. Verificado: o projeto nao tem manifesto de extensao, hook, skill, registry, bridge SDK
nem sidecar MCP — e um pacote Python de stdlib com `Makefile` e `tests/`. Nada a adicionar ou alterar.

## Agent Manageability Plan

O que um agente ou script precisa para operar a feature sem UI:

- `python3 -m fidx <dir> index` → exit 0/2/3 e uma linha de resumo estavel em `stdout`
  (`fidx: <total> arquivos, <n> reindexados, <n> removidos`), parseavel e boa para log de cron.
- `python3 -m fidx <dir> search <termo>` → exit 0 com um caminho por linha; exit 1 sem ocorrencia
  (mesma convencao do `grep`, logo encadeavel em `&&`/`||`); exit 2 com erro acionavel em `stderr`.
- Descoberta de estado: o indice e um arquivo SQLite inspecionavel com `sqlite3` na mao; nao existe
  estado em outro lugar. Ausencia do arquivo e um estado valido e auto-corrigivel.
- Erros sao deterministicos e distinguiveis por exit code (2 = uso/estado, 3 = concorrencia), nao
  por texto.

## Config Lifecycle

Nao se aplica: a feature nao le `config.toml`, nem env var, nem arquivo de configuracao (Non-Goals).
Superficies conferidas: nao ha config no repositorio alem do `Makefile`.

## Testing Approach

- **Framework**: `unittest` da stdlib, descoberto por `make test` (`-s tests -t .`). Sem framework
  novo, sem fixture externa.
- **Fixtures**: `tempfile.TemporaryDirectory` montando arvores de arquivos reais. Filesystem e
  SQLite sao **reais** em todos os niveis — sao o objeto do teste, nao um I/O a ser fingido.
- **Unidade**: funcoes de `core` isoladas (tokenizador, digest, varredura, operacoes de
  armazenamento, contabilidade da rodada). O unico "fake" permitido e um espiao sobre `tokenize`
  para provar que arquivo inalterado **nao** e reprocessado.
- **Integracao**: `index_dir` + `search` sobre uma arvore temporaria, exercitando o ciclo
  indexa → muda/apaga → reindexa → busca, incluindo `mtime` mentiroso via `os.utime`.
- **E2E**: `subprocess.run([sys.executable, "-m", "fidx", ...])` com as invocacoes **literais** de
  `_dx.md`, conferindo `stdout`, `stderr` e `returncode`.
- **Dependencias de ambiente**: nenhuma alem do Python 3.11+. Os casos de concorrencia usam uma
  segunda conexao SQLite segurando a escrita, nao um segundo processo com relogio.

Casos concretos: [Test specification](_tests.md).

## Development Sequencing

### Build Order

1. **Contrato de armazenamento + ponta a ponta (task_01)**: esquema, varredura, tokenizacao, CLI,
   busca. Portao de verificacao: UT de `core` + E2E das invocacoes de `_dx.md`. Tudo que vem depois
   consome esse esquema; por isso ele e resolvido antes de qualquer consumidor.
2. **Incremental por hash (task_02)**: `known_files`, comparacao de digest, remocao dos sumidos,
   contadores do resumo. Portao: IT com `os.utime` mentindo nas duas direcoes + UT com espiao.
   So depende do esquema de task_01, nao da superficie de erro de task_03.
3. **Operacao por cron (task_03)**: transacao unica/atomicidade, WAL, `timeout`/exit 3, bytes
   indecifraveis, arquivo ilegivel, versao de esquema, README. Portao: IT de interrupcao e de
   concorrencia. Vem por ultimo porque endurece um caminho que ja tem que existir.

Fase de limpeza: nenhuma — nao ha codigo anterior para remover.

### Technical Dependencies

Nenhuma bloqueante: Python 3.11+ com `sqlite3` (presente em qualquer build padrao de CPython) e o
`Makefile` que ja existe. Nenhum servico, nenhuma infraestrutura, nenhum componente compartilhado.

## Monitoring and Observability

Proporcional ao que a coisa e (um script de cron numa maquina):

- A linha de resumo de `index` em `stdout` e o registro da rodada: `total`, `reindexados`,
  `removidos`. `reindexados` alto em rodada seguida e o sintoma de deteccao de mudanca quebrada.
- Avisos de arquivo pulado (ilegivel/sumiu no meio da varredura) vao para `stderr` com o caminho,
  uma linha por arquivo — o cron os entrega por e-mail/log sem poluir o `stdout`.
- Exit code e o alerta: 3 repetido significa rodadas se atropelando (intervalo do cron menor que a
  rodada); 2 significa indice/pasta em estado invalido.
- Sem metrica, sem tracing, sem log estruturado: seriam infra nova para um processo de um usuario.

## Technical Considerations

### Key Decisions

- **Hash de conteudo como unico sinal de mudanca** — ADR-001.
- **SQLite com indice invertido proprio** (sem FTS5, sem JSON/pickle) — ADR-002.
- **Indice dentro da pasta indexada** (`<dir>/.fidx.sqlite3`), e nao em `~/.cache/fidx/<hash>`:
  estado visivel e colado no que ele descreve, apagavel com `rm`, sem mapa de caminho→cache para
  manter. Trade-off: um `rsync --delete` pode remove-lo; a regra 9 transforma isso em reconstrucao
  automatica em vez de erro.
- **Symlinks ignorados por completo** em vez de resolvidos com controle de ciclo: evita recursao
  infinita e indexar o mesmo conteudo em dois caminhos, ao custo de ignorar arvores montadas por
  link — o que o enunciado (rsync + checkout) nao descreve.
- **Rodada single-thread**: o gargalo e I/O de leitura; paralelizar traria pool, ordem instavel e
  contencao de escrita no SQLite antes de haver medicao que justifique.
- **`__main__` sem `argparse`**: a forma `<dir> <comando> [termo]` poe o posicional antes do
  subcomando, o que em `argparse` exige subparser torto; o parse manual sao ~10 linhas e uma linha
  de uso literal.

### Known Risks

- **Toda rodada le todos os bytes** (consequencia do ADR-001, likelihood: certo). Mitigacao: o que se
  economiza e tokenizacao e escrita; o resumo mostra `reindexados` para provar. Se a leitura sozinha
  ficar cara demais, a saida e um daemon com inotify (Non-Goal) e nao voltar a confiar no `mtime`.
- **Arquivo enorme lido inteiro em memoria** (likelihood: baixa, depende do dump). Mitigacao: o hash
  ja e em blocos; se estourar, tokenizar em blocos com sobreposicao — Open Question 2.
- **Token inteiro surpreende quem espera `grep`** (likelihood: media). Mitigacao: escrito no README e
  na mensagem de "sem resultado"; Open Question 1 tem o caminho de prefixo se incomodar.
- **Rodadas de cron se atropelando** numa pasta em que a rodada demora mais que o intervalo
  (likelihood: media). Mitigacao: exit 3 deterministico em vez de duas rodadas escrevendo junto.

## Safety Invariants

1. Uma rodada de `index` grava tudo ou nada: todas as alteracoes acontecem em uma unica transacao,
   com `COMMIT` apos o ultimo arquivo processado.
2. Interrupcao (excecao, `SIGKILL`, queda de energia) deixa o indice no estado da ultima rodada
   completa — nunca num estado parcial em que parte dos arquivos foi atualizada.
3. Uma busca concorrente a uma rodada le a foto anterior, integralmente consistente (WAL), e nunca
   um indice meio-escrito.
4. No maximo uma rodada de `index` escreve no mesmo indice por vez; a segunda espera ate
   `BUSY_TIMEOUT_S` e entao falha com `IndexBusy` (exit 3) sem gravar nada.
5. Reindexar um caminho apaga **todos** os postings antigos daquele caminho antes de inserir os
   novos; nenhum posting sobrevive ao conteudo que o gerou.
6. Nenhum caminho fica em `postings` sem a linha correspondente em `files`, e a remocao de um
   caminho apaga os dois lados na mesma transacao.

## File References

### Repo Files

- `fidx/__init__.py` — pacote vazio existente; estabelece o nome do modulo que a CLI expoe e o que
  o teste de fumaca importa. Fica vazio: a logica entra em `core.py`.
- `tests/test_fumaca.py:1-14` — o unico teste existente e o estilo a seguir (`unittest.TestCase`,
  sem framework, sem fixture); nao pode quebrar.
- `Makefile:1-4` — define o comando de verificacao (`python3 -m unittest discover -s tests -t .`) e
  por que os testes novos precisam estar em `tests/test_*.py` e importaveis a partir da raiz.
- `README.md:1-8` — ja publica as tres invocacoes (`make test`, `index`, `search`); `_dx.md` tem de
  bater com elas, e task_03 atualiza o arquivo com exit codes e a regra de token.
- `.gitignore:1-2` — ignora `__pycache__/`; o indice `.fidx.sqlite3` nasce dentro da pasta indexada
  do usuario, nao no repositorio, entao nao precisa de entrada nova.

### External References

Nao se aplica: nenhuma fonte externa vendorizada no repositorio.

### Design and Analysis Sources

- `adrs/adr-001.md` — por que a data de modificacao nao participa da decisao de reprocessar.
- `adrs/adr-002.md` — por que SQLite com indice invertido proprio, e nao FTS5 nem arquivo serializado.

## Assumptions and Defaults

| Assuncao / default                        | Valor                                                              |
| ----------------------------------------- | ------------------------------------------------------------------ |
| Versao de Python                          | 3.11+ (`python3` do sistema), so stdlib                             |
| Nome/lugar do indice                      | `<dir>/.fidx.sqlite3` (+ `-wal`/`-shm`)                             |
| Algoritmo de hash                         | SHA-256, leitura em blocos de 1 MiB                                 |
| Tokenizacao                               | `re.findall(r"\w+", texto.lower())` — Unicode, acento preservado    |
| Casamento                                 | token inteiro, case-insensitive; varios tokens = E logico           |
| Decodificacao                             | UTF-8 com `errors="ignore"`                                         |
| Exclusoes da varredura                    | nomes iniciados por `.` e todos os symlinks                         |
| Ordem da saida de busca                   | crescente por caminho, sem repeticao                                |
| Caminho impresso                          | o diretorio como o usuario digitou + caminho relativo               |
| Timeout de lock do SQLite                 | 30 s, depois exit 3                                                 |
| `journal_mode`                            | WAL (permite buscar durante a rodada)                               |
| Arquivo ilegivel                          | pulado, aviso em `stderr`, rodada continua com exit 0               |
| Indice ausente ou de esquema antigo       | `index` reconstroi do zero; `search` erra com instrucao, exit 2     |
| Idioma das mensagens                      | portugues sem acento, como o `README.md` atual                      |

## Architecture Decision Records

- [ADR-001: Hash de conteudo, nunca data de modificacao](adrs/adr-001.md) — o sinal de mudanca e o
  SHA-256 do conteudo; `mtime`/tamanho nao entram nem como atalho.
- [ADR-002: SQLite com indice invertido proprio](adrs/adr-002.md) — tres tabelas e `SELECT` por
  termo, em vez de FTS5 (dependente de flag de compilacao) ou de um arquivo serializado.
