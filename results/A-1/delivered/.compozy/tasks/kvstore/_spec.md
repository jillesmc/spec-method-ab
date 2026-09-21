# Spec: kvstore

Especificação única do `kvstore`. Títulos de seção seguem o template em inglês porque documentos e
verificações a jusante se apoiam neles; o conteúdo acompanha a língua do repositório.

---

# Part I — Product

## Overview

- **Motivating Problem**: um serviço guarda configuração, contadores e posição de processamento num
  arquivo JSON reescrito por inteiro a cada mudança. O serviço reinicia sozinho várias vezes por dia,
  por deploy e por OOM, e **já voltou com o arquivo zerado, perdendo todo o estado** — a reescrita não é
  atômica, então morrer no meio dela trunca o arquivo. O comportamento observável de fora que resolve o
  problema: depois que uma gravação é confirmada, matar o processo a qualquer momento e reabrir o
  armazenamento devolve o valor gravado, sempre. A fatia 1 entrega exatamente isso.
- **Para quem**: o serviço (que escreve em processo e lê no boot) e o operador que o socorre num
  incidente pela linha de comando.
- **Por que vale**: hoje a resposta "gravei" é uma promessa que o armazenamento não cumpre. O prejuízo
  não é o arquivo corrompido, é a perda silenciosa de posição de processamento — o serviço volta e
  reprocessa ou pula trabalho sem ninguém perceber.

## Goals

- Depois que `set` confirma, o valor sobrevive a `SIGKILL`, OOM, deploy e queda da máquina.
- O armazenamento nunca volta vazio nem parcialmente escrito: em qualquer momento de morte, cada chave
  tem o valor antigo ou o novo.
- O operador inspeciona e corrige estado com quatro comandos, sem escrever código e sem derrubar o
  serviço.
- Chaves e gravações podem crescer indefinidamente **sem nenhuma rotina de manutenção** para agendar,
  lembrar ou esquecer.
- O custo de gravar uma chave deixa de ser proporcional ao total armazenado.

## User Stories

Catálogo canônico em [_user_stories.md](_user_stories.md) — as histórias não são repetidas aqui.

- **US-001, US-003, US-005** — Escrita: gravar, apagar, e gravar valor grande pela entrada padrão.
- **US-002, US-004** — Leitura: ler uma chave e listar as existentes.
- **US-006** — API: uso em processo pelo serviço, sem subprocesso por gravação.
- **US-007** — Durabilidade: o contrato de sobrevivência à morte abrupta.
- **US-008, US-009** — Operação: crescimento sem manutenção e primeira execução.
- **US-010** — Concorrência: operador e serviço no mesmo diretório ao mesmo tempo.

## Core Features

- **Armazenamento durável chave→texto**: um diretório guarda um mapa de chaves de texto para valores de
  texto. Gravação confirmada é gravação em disco. É a base de tudo o mais.
- **Linha de comando com quatro verbos** (`set`, `get`, `del`, `list`): a superfície que o enunciado
  pede, no formato `python -m kvstore <diretorio> <comando> [args]`. Camada fina sobre a API.
- **API Python em processo** (`Store`): o serviço grava um contador por evento; abrir um subprocesso a
  cada gravação seria inviável. A linha de comando e a API compartilham o mesmo código de
  armazenamento, então têm exatamente a mesma garantia de durabilidade.
- **Valor pela entrada padrão** (`set <chave> -`): o enunciado diz que os valores podem ser grandes, e
  o limite de tamanho de argumentos do sistema operacional (na ordem de 2 MiB no Linux, compartilhado
  com o ambiente) impede que argumentos sozinhos atendam a esse requisito.

Interação entre elas: a linha de comando abre um `Store`, executa uma operação e fecha. Tudo que vale
para a API vale para a linha de comando, incluindo a durabilidade e o comportamento sob concorrência.

## Business Rules

- **Confirmação implica durabilidade.** `set` e `delete` só retornam com sucesso depois que a mudança
  está sincronizada em disco. Vale para as duas superfícies. Ressalva única e explícita: hardware que
  mente sobre `fsync` está fora do alcance de qualquer software.
- **Atomicidade por operação.** Cada `set` e cada `delete` é atômico: após qualquer morte, a chave tem
  o valor antigo ou o novo, nunca um estado intermediário, e nenhuma outra chave é afetada.
- **Ausência não é erro no nível da API.** `get` de chave inexistente devolve `None`; `delete` de chave
  inexistente devolve `False`. Na linha de comando, `get` de chave ausente é código 1 e `del` de chave
  ausente é código 0 (idempotente — ver Assumptions).
- **Chaves**: texto não vazio; qualquer caractere é permitido, inclusive `/`, `..` e newline, porque a
  chave nunca vira nome de arquivo. Chave vazia é rejeitada. Chave que não é `str` levanta `TypeError`.
- **Valores**: texto, inclusive a string vazia, que é um valor legítimo e distinto de ausência. Sem
  limite imposto pelo pacote além do limite do próprio SQLite (1 GB por valor, na configuração padrão).
- **Sobrescrita, não versionamento.** `set` numa chave existente substitui o valor; o anterior não é
  recuperável.
- **Ordem de `list`**: crescente por código de caractere, determinística entre execuções.
- **Fidelidade de `get` na linha de comando**: o valor sai em stdout exatamente como entrou, sem
  newline acrescentado, para que redirecionar para arquivo reproduza o conteúdo.
- **Nenhuma operação de manutenção.** Não existe comando de compactação, e nenhuma rotina periódica é
  exigida para que o armazenamento continue correto ou rápido.
- **Codificação**: UTF-8 em toda fronteira de entrada e saída, independente do locale do sistema.

## User Experience

- **Personas e objetivos**: o **Serviço** quer gravar sem pensar e ler no boot; o **Operador** quer
  descobrir e corrigir estado durante um incidente; o **Integrador** quer embutir o pacote sem
  configurar nada.
- **Fluxo do integrador**: `from kvstore import Store` → `Store(diretorio)` → `set`/`get` no laço do
  serviço. Sem arquivo de configuração, sem parâmetros de ajuste, sem passo de inicialização do
  diretório.
- **Fluxo do operador em incidente**: `list` para descobrir o que existe → `get <chave>` para conferir
  → `set` ou `del` para corrigir. Funciona com o serviço no ar, sem derrubá-lo.
- **Primeiro contato**: apontar para um diretório que ainda não existe funciona; o diretório é criado
  na primeira operação. Não há passo de "inicializar o armazenamento".
- **Descobribilidade**: invocar sem argumentos ou com comando desconhecido imprime a linha de uso com
  os quatro verbos e termina com código 2. O README mostra o caminho completo em cinco linhas.
- **Acessibilidade**: superfície de terminal. Toda mensagem de erro vai para stderr com o prefixo
  `kvstore: `, stdout fica reservado para dados, e o código de saída distingue as classes de falha —
  o que torna o comportamento legível tanto por leitor de tela quanto por script.

## High-Level Technical Constraints

- **Só a biblioteca padrão do Python.** Nenhuma dependência externa, em tempo de execução ou de teste.
- **`make test` tem de passar** com o alvo existente (`python3 -m unittest discover -s tests -t .`).
- **Python 3.11+**, conforme o README do repositório (a máquina de desenvolvimento roda 3.14.7).
- **Durabilidade por confirmação** é requisito funcional, não meta de desempenho.
- **Desempenho da perspectiva do usuário**: o custo de uma gravação acompanha o tamanho do valor, não o
  total armazenado; leitura de uma chave não depende do número de chaves nem do histórico de gravações.
- **Manejabilidade por agente e operador**: toda a capacidade é operável pela linha de comando, com
  códigos de saída determinísticos e saída em stdout adequada a pipe — não há interface gráfica nem
  passo que exija um humano.
- **Privacidade e segurança**: o pacote não transmite nada pela rede e não escreve fora do diretório
  indicado. Chaves nunca são interpretadas como caminhos de arquivo, o que elimina travessia de
  diretório por chave hostil. O diretório é do serviço, conforme o enunciado; o pacote não tenta
  restringir permissões além do padrão do sistema.
- **Ecossistema de extensões**: não se aplica — pacote isolado, sem pontos de extensão em execução.

## Non-Goals (Out of Scope)

- **Servidor, rede ou protocolo.** É uma biblioteca com linha de comando; nada escuta em porta.
- **Expiração, TTL, namespaces, transações de múltiplas chaves, iteração por prefixo.** Nada disso foi
  pedido, e cada um deles é uma decisão de contrato que só se acerta com o uso real na mão.
- **Valores binários.** O enunciado diz que os valores são texto.
- **Comando de compactação ou `VACUUM`.** Decisão deliberada: exigiria o dobro do espaço em disco e
  seria a rotina periódica que o enunciado avisa que ninguém executa. Consequência aceita: o arquivo não
  encolhe depois que uma chave grande é apagada; o espaço é reaproveitado pelas gravações seguintes.
- **Backup, réplica ou exportação.** O arquivo é um banco SQLite comum e as ferramentas existentes
  servem.
- **Escrita concorrente de alta taxa entre processos.** Um escritor de cada vez é o desenho; o segundo
  espera até cinco segundos e depois falha com mensagem nomeada.
- **Importação do JSON legado** — não é exclusão, é decisão pendente: ver Open Questions.

## Open Questions

1. **O JSON que o serviço usa hoje precisa ser importado?** O enunciado descreve o formato atual como o
   problema, mas não diz o que fazer com o conteúdo que já está lá. As duas leituras plausíveis são
   "o serviço reconstrói o estado sozinho no boot" e "há estado insubstituível a migrar". A evidência
   disponível não decide, e o repositório é um pacote novo, sem o JSON à vista. Se a resposta for
   importar, o trabalho é pequeno com o desenho escolhido — um laço de `set` sobre o dicionário
   carregado — e cabe numa fatia própria sem alterar nenhum contrato definido aqui. **Nada nesta spec
   depende da resposta**; por isso ela não bloqueia a implementação.
2. **A espera de cinco segundos sob contenção é adequada à janela de reinício do serviço?** O valor foi
   escolhido por ser folgado para a carga descrita (configuração, contadores, posição). Se o serviço
   tiver um limite de inicialização mais apertado, o número muda em uma linha.

---

# Part II — Technical

## Executive Summary

O defeito é conhecido e tem causa identificada no próprio enunciado: reescrever o arquivo inteiro a
cada mudança não é atômico, então morrer no meio do `write` deixa um arquivo truncado — foi assim que o
serviço voltou com o estado zerado. A correção não é escrever com mais cuidado o mesmo formato; é parar
de reescrever o estado inteiro por gravação, porque o enunciado também garante que o estado só cresce e
que ninguém limpa nada.

A decisão central (ADR-001) é usar `sqlite3`, que já está na biblioteca padrão, em vez de escrever um
log append-only com compactação. As duas opções resolvem a durabilidade; a diferença é que uma delas
traz junto o código de recuperação e de compactação — a parte mais difícil de acertar, a menos exercida
em teste, e exatamente a que decide se o dado sobrevive. O nível de durabilidade (ADR-002) é
`journal_mode=WAL` com `synchronous=FULL`: WAL para que o `get` do operador não dispute trava com o
serviço, e `FULL` porque "aconteça o que acontecer" inclui a máquina cair, não só o processo morrer.

O trade-off aceito é um `fsync` por gravação confirmada e um arquivo que não é mais legível com `cat`.
O primeiro é irrelevante na carga descrita; o segundo é coberto por `list` e `get`.

Verificação feita nesta máquina em 2026-09-20 (Python 3.14.7, SQLite 3.53.1): com esses pragmas, um
valor de 5 MB gravado e o processo encerrado com `os._exit(0)` — sem `close()`, sem `atexit`, sem flush
— foi relido íntegro. É a reprodução do cenário de OOM que motiva a spec.

## MVP Boundary

O MVP são as tarefas 1 a 4, entregues em três fatias:

- **Fatia 1 (tarefas 1 e 2)** — resolve o Motivating Problem: `Store` com `set`/`get` duráveis e a
  linha de comando com `set` e `get`. Ao fim dela, gravar, matar com `SIGKILL` e reler devolve o valor.
- **Fatia 2 (tarefa 3)** — completa a superfície pedida: `del`, `list` e a entrada padrão para valores
  grandes.
- **Fatia 3 (tarefa 4)** — a prova: a suíte de durabilidade e concorrência que exerce as invariantes,
  mais o README.

Pós-MVP: nada planejado. Fora de escopo: a lista em Non-Goals. A importação do JSON legado (Open
Question 1) seria uma fatia adicional que não altera contrato nenhum.

## Developer Experience

Superfície pública congelada em [_dx.md](_dx.md) — não repetida aqui:

- **CLI** — `python -m kvstore <diretorio> {set|get|del|list}`, com a saída exata de cada verbo.
- **SDK** — a classe `Store` e sua assinatura completa.
- **Errors** — a tabela de código de saída × condição × mensagem exata em stderr.
- **Arquivos em disco** — o que o operador encontra no diretório durante um incidente.

Não se aplicam e foram removidas de `_dx.md`: YAML, HTTP/UDS, `config.toml`, native tools, bridges. O
pacote não tem daemon, rede, nem arquivo de configuração.

## System Architecture

Dois componentes, ambos novos, num pacote de dois arquivos:

- **`kvstore/__init__.py` — camada de armazenamento.** Exporta a classe `Store`. Dona da conexão, dos
  pragmas, do esquema e das quatro operações. Não sabe nada sobre argumentos, stdout, stderr ou código
  de saída. É onde mora toda a garantia de durabilidade.
- **`kvstore/__main__.py` — camada de linha de comando.** Traduz `sys.argv` em chamadas de `Store` e
  traduz retorno e exceção em stdout, stderr e código de saída. Não contém nenhuma instrução SQL nem
  abre conexão por conta própria.

Fluxo de dados: `sys.argv` → `__main__` valida a forma da invocação → abre `Store(diretorio)` →
uma chamada de método → o resultado vira bytes em stdout ou uma mensagem em stderr com código de saída
→ `Store` é fechado. O serviço, em processo, entra pela mesma classe `Store`, pulando a camada de cima.

Sistemas externos: apenas o sistema de arquivos, pelo módulo `sqlite3`.

## Architectural Boundaries

- `kvstore/__main__.py` **pode** importar `kvstore` (`Store`), `sys`, `os`.
- `kvstore/__main__.py` **não pode** importar `sqlite3` nem emitir SQL. Toda a interação com o motor
  fica atrás de `Store`, para que a garantia de durabilidade tenha um dono só. Um segundo caminho que
  abrisse conexão sem repetir `PRAGMA synchronous=FULL` perderia a garantia em silêncio — é o risco
  nomeado no ADR-002.
- `kvstore/__init__.py` **não pode** importar nada de `__main__`, nem escrever em stdout/stderr, nem
  chamar `sys.exit`. Ele levanta exceções; quem decide o que o usuário vê é a camada de cima.
- Nenhum dos dois pode importar pacote de fora da biblioteca padrão.
- `tests/` pode importar os dois, e usa `subprocess` para exercer a linha de comando de verdade.
- Não há raiz de composição neste repositório: é um pacote isolado, não um serviço com injeção de
  dependências.

## Implementation Design

### Core Interfaces

```python
# kvstore/__init__.py

class Store:
    """Mapa duravel de texto para texto, guardado num diretorio."""

    def __init__(self, diretorio: str | os.PathLike) -> None:
        """Cria o diretorio se preciso, abre a conexao e garante o esquema."""

    def set(self, chave: str, valor: str) -> None:
        """Grava. Retorna apenas depois que o dado esta sincronizado em disco."""

    def get(self, chave: str) -> str | None:
        """Devolve o valor, ou None se a chave nao existe."""

    def delete(self, chave: str) -> bool:
        """Apaga. Devolve True se a chave existia, False caso contrario."""

    def keys(self) -> list[str]:
        """Todas as chaves, em ordem crescente."""

    def close(self) -> None: ...
    def __enter__(self) -> "Store": ...
    def __exit__(self, *exc) -> None: ...
```

Abertura da conexão — o ponto único onde a durabilidade é estabelecida:

```python
NOME_ARQUIVO = "kvstore.sqlite3"
ESPERA_MS = 5000

def _conectar(caminho: str) -> sqlite3.Connection:
    # isolation_level=None: autocommit explicito; funciona de 3.11 em diante.
    # Connection.autocommit so existe a partir do 3.12 e nao pode ser usado aqui.
    con = sqlite3.connect(caminho, isolation_level=None)
    con.execute("PRAGMA journal_mode = WAL")    # persistente no arquivo
    con.execute(f"PRAGMA synchronous = FULL")   # POR CONEXAO: sem isto, cai para NORMAL
    con.execute(f"PRAGMA busy_timeout = {ESPERA_MS}")
    con.execute("CREATE TABLE IF NOT EXISTS kv (chave TEXT PRIMARY KEY, valor TEXT NOT NULL)")
    return con
```

Gravação — uma única instrução, logo uma única transação atômica:

```python
SQL_SET = "INSERT INTO kv VALUES (?, ?) ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor"
```

Sem hierarquia de exceções própria: `ValueError` para chave vazia, `TypeError` para chave que não é
`str`, e `sqlite3.Error` para falha de armazenamento. Uma classe de exceção nova envolvendo
`sqlite3.Error` não acrescentaria informação — só um nome a mais para o chamador aprender.

### Data Models

Uma tabela, duas colunas, nenhuma migração:

| Coluna  | Tipo   | Propósito                                                        |
| ------- | ------ | ---------------------------------------------------------------- |
| `chave` | `TEXT` | Chave, `PRIMARY KEY`. Não vazia (regra aplicada na camada Python) |
| `valor` | `TEXT` | Valor, `NOT NULL`. String vazia é permitida e distinta de ausente |

- **Tabela com rowid (o padrão), não `WITHOUT ROWID`.** `WITHOUT ROWID` guardaria a linha inteira
  dentro da árvore B do índice; com valores grandes isso incha o índice e degrada a busca. Com rowid, o
  valor fica na tabela com páginas de transbordo e o índice da chave continua pequeno. Decidido em
  ADR-001.
- **Dados em colunas, não em JSON.** `chave` é o critério de busca e `valor` é conteúdo opaco; ambos
  são primeira classe, nenhum é metadado acessório. Não há blob JSON neste desenho.
- **Ausência de `NOT NULL` em `chave`** é desnecessária: `PRIMARY KEY` em tabela com rowid já recusa
  `NULL` no SQLite quando a coluna é a chave primária declarada — mas a validação efetiva acontece na
  fronteira Python, que rejeita antes de chegar ao SQL.
- `keys()` ordena em SQL (`SELECT chave FROM kv ORDER BY chave`), não em Python.

### API Endpoints

Não se aplica: o pacote não expõe superfície HTTP. A superfície pública é a linha de comando e a classe
`Store`, ambas em `_dx.md`.

## Integration Points

Não se aplica: nenhum sistema fora do processo, além do sistema de arquivos local.

## Impact Analysis

| Component             | Impact Type | Description and Risk                                                                                       | Required Action                                             |
| --------------------- | ----------- | ---------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| `kvstore/__init__.py` | modified    | Hoje é um arquivo vazio; passa a conter toda a camada de armazenamento. Risco baixo: nada importa dele ainda | Implementar `Store` conforme Core Interfaces                |
| `kvstore/__main__.py` | new         | Novo ponto de entrada de `python -m kvstore`. Risco baixo: não existe hoje                                  | Implementar conforme `_dx.md`                               |
| `tests/test_fumaca.py`| modified    | Teste de fumaça que só confere que o pacote importa; continua válido mas deixa de ser a única cobertura      | Manter como está; a cobertura real entra em arquivos novos  |
| `tests/` (novos)      | new         | Suítes de unidade, integração e E2E. Risco: o teste de durabilidade usa subprocesso e sinal                 | Ver `_tests.md`; nenhum teste pode depender de rede ou relógio |
| `README.md`           | modified    | Precisa descrever os quatro verbos e a garantia de durabilidade                                             | Atualizar na tarefa 4                                        |
| `Makefile`            | unchanged   | `make test` já roda `unittest discover`; os arquivos novos são descobertos sozinhos                         | Nenhuma — confirmado lendo o alvo                            |

**Compatibilidade (SD-013).** Não há nada a preservar: `kvstore/__init__.py` está vazio, o pacote nunca
foi publicado nem importado, e não existe estado de usuário criado por ele. Portanto:

- **Estado de usuário**: nenhum produzido por este pacote — nada a migrar. O JSON legado do serviço é
  externo a este repositório e está registrado em Open Questions, não como migração assumida.
- **Superfícies públicas**: todas nascem nesta mudança; não há forma antiga para manter uma release
  atrás, nem shim de fronteira a instalar.
- **Código interno**: corte direto na mesma mudança.
- **Delete targets**: nenhum. Nenhum arquivo, API, comando ou artefato desaparece.

Sem fallback, sem shim de compatibilidade e sem placeholder: um segundo caminho de escrita que não
passe por `Store._conectar` perde a garantia de durabilidade em silêncio, que é precisamente o defeito
que esta spec existe para eliminar.

## Extensibility Integration Plan

Não se aplica. Superfícies conferidas e inalteradas: não há manifesto de extensão, hook, skill, tool,
registro, bridge SDK nem sidecar MCP neste repositório — ele contém apenas `kvstore/`, `tests/`,
`Makefile` e `README.md`. O pacote também não define ponto de extensão próprio (nem backend plugável,
nem serializador configurável), por decisão: nada no enunciado pede um segundo armazenamento, e uma
interface com uma só implementação seria abstração sem consumidor.

## Agent Manageability Plan

A capacidade inteira é operável por linha de comando, que é o que um agente ou script usa:

- **Verbos**: `set`, `get`, `del`, `list` — cobrem escrita, leitura, remoção e descoberta. Não existe
  operação disponível na API que falte na linha de comando.
- **Descoberta de estado**: `list` enumera tudo que existe; `get` confere um item. Não é preciso saber
  os nomes de antemão.
- **Saída estruturada**: `list` emite uma chave por linha e `get` emite o valor cru, ambos próprios
  para pipe. Não há `--json`: os dados são texto opaco, e uma camada de JSON obrigaria o consumidor a
  desembrulhar para chegar ao mesmo texto. Mensagens ficam em stderr e nunca contaminam stdout.
- **Erros determinísticos**: a tabela de `_dx.md` fixa código de saída por classe de falha — 1 para
  chave ausente, 2 para uso, 3 para armazenamento. Um script distingue "não existe" de "não consegui
  ler" sem interpretar texto de mensagem.
- **Sem estado de configuração a descobrir**: não há arquivo de config, variável de ambiente nem flag
  global; o diretório é o único parâmetro.

## Config Lifecycle

Não se aplica, e é decisão, não omissão: o pacote não lê `config.toml`, variável de ambiente nem flag
de ajuste. Os dois números do desenho — o nome do arquivo (`kvstore.sqlite3`) e a espera sob contenção
(5000 ms) — são constantes no módulo. Tornar configurável um valor que nunca muda é criar superfície
para manter sem nenhum consumidor pedindo. Se a Open Question 2 mudar a espera, muda a constante.

## Testing Approach

Estratégia; os casos concretos estão em [_tests.md](_tests.md).

- **Framework**: `unittest` da biblioteca padrão, descoberto pelo alvo `make test` que já existe
  (`python3 -m unittest discover -s tests -t .`). Nenhuma dependência de teste, coerente com a restrição
  do enunciado.
- **Fixtures**: `tempfile.TemporaryDirectory` por caso. Nenhum teste toca diretório fixo, nenhum
  depende de ordem de execução, nenhum deixa resíduo.
- **Fakes só na fronteira de E/S** — e aqui não há nenhuma: o sistema de arquivos real é a coisa sob
  teste. Um `sqlite3` falso provaria que o código chama o que achamos que chama, não que o dado
  sobrevive; para esta spec isso seria testar o contrário do que importa.
- **Unidade**: `Store` contra um diretório temporário — operações, regras de chave e valor, e os
  pragmas efetivos lidos da conexão aberta (a defesa contra o risco nomeado no ADR-002).
- **Integração**: durabilidade e concorrência, usando `subprocess` e `os.kill`. É o coração da suíte.
  Morte abrupta é simulada de duas formas complementares: `os._exit(0)` no filho (encerramento sem
  `close()`, sem `atexit`, sem flush) e `SIGKILL` do pai sobre o filho (morte de fora, inclusive
  **durante** uma gravação grande). Nenhuma das duas depende de `sleep` para sincronizar: o filho
  sinaliza prontidão por um pipe, e o pai reage ao sinal recebido.
- **E2E**: `python -m kvstore` executado por `subprocess` com as invocações verbatim de `_dx.md`,
  conferindo stdout, stderr e código de saída — incluindo a ausência de newline acrescentado em `get`.
- **Dependências de ambiente**: nenhuma. Sem rede, sem serviço externo, sem relógio de parede como
  condição de corrida. Os testes que dependem de `os.kill` e de semântica POSIX de sinal são marcados
  para pular fora de POSIX, e o alvo de desenvolvimento é Linux.
- **O que não é testável e como é coberto**: queda de energia da máquina não se reproduz em espaço de
  usuário. A invariante é coberta em duas frentes — morte do processo testada de verdade, e asserção
  sobre os pragmas efetivos, que são o que decide o comportamento sob queda de energia.

## Development Sequencing

### Build Order

1. **`Store` antes de tudo.** A linha de comando e todos os testes dependem dela. Portão de
   verificação: os casos de unidade de `_tests.md` passam, incluindo os dois de pragma.
2. **Linha de comando depois de `Store`.** Depende da assinatura congelada em Core Interfaces. Portão:
   os casos E2E dos verbos entregues passam com stdout, stderr e código de saída exatos.
3. **Suíte de durabilidade e concorrência por último**, porque precisa das duas superfícies existindo
   para matar processos que as usam. Portão: `make test` verde por inteiro.
4. **README junto do passo 3**, fase só de documentação, sem alterar comportamento — separada de
   propósito das fases que mexem em código.

A ordem de entrega por valor está em MVP Boundary; esta aqui é a ordem de dependência que alimenta as
arestas de `_tasks.md`.

### Technical Dependencies

- Python 3.11+ com o módulo `sqlite3` compilado (biblioteca padrão; a ausência seria uma build exótica
  e apareceria no primeiro `make test`).
- Sistema POSIX para os casos de integração que usam sinais.
- Nenhuma infraestrutura, serviço externo ou componente compartilhado.

## Monitoring and Observability

Não se aplica como sistema instrumentado: é uma biblioteca com linha de comando, sem processo de longa
duração próprio, sem métricas a exportar e sem destino de log. O pacote **não** emite log — quem tem
processo é o serviço que o embute, e uma biblioteca que escreve em log por conta própria polui a saída
do hospedeiro.

O que o pacote oferece para diagnóstico, e é suficiente:

- Código de saída por classe de falha, determinístico (tabela em `_dx.md`).
- Mensagens de erro em stderr que nomeiam o caminho, o motivo do sistema operacional e, sob contenção,
  a duração da espera.
- Exceções Python com o erro original do `sqlite3`, que aparecem no log do serviço hospedeiro pelo
  mecanismo dele.
- O arquivo em disco é um banco SQLite comum: durante um incidente, dá para inspecioná-lo com qualquer
  ferramenta SQLite sem parar o serviço.

## Technical Considerations

### Key Decisions

- **`sqlite3` em vez de log append-only próprio** — ADR-001. O log resolveria a durabilidade, mas traz
  junto recuperação de cauda parcial e compactação, que é a rotina periódica que o enunciado avisa que
  ninguém vai executar.
- **WAL com `synchronous=FULL`** — ADR-002. `NORMAL` já cobriria OOM e deploy (o dado está no cache do
  sistema operacional, que sobrevive ao processo), mas não cobre a máquina cair; o enunciado diz
  "aconteça o que acontecer".
- **Tabela com rowid, não `WITHOUT ROWID`.** Trade-off: `WITHOUT ROWID` economiza uma indireção em
  tabelas chave-valor com linhas pequenas, mas guarda a linha inteira no índice, e aqui os valores
  podem ser grandes. Rejeitado por isso.
- **`del` idempotente na linha de comando** (código 0 mesmo se a chave não existia). Trade-off: o
  operador perde a informação "não havia nada para apagar". Escolhido porque a pós-condição desejada já
  vale, e porque num serviço que reinicia várias vezes por dia a repetição de comando é a norma —
  devolver código diferente de zero faria um `set -e` derrubar o script no retry. Registrado em
  Assumptions como decisão reversível numa linha.
- **`get` sem newline acrescentado.** Trade-off: a saída fica visualmente colada no prompt. Escolhido
  para que `get dump > copia.json` reproduza o arquivo byte a byte; a captura por `$(...)` do shell
  remove newline final de qualquer jeito, então acrescentar um só prejudica o caso de redirecionamento.
- **`-` como valor lendo a entrada padrão.** É a única adição além dos quatro verbos literais do
  enunciado, e existe porque o enunciado diz que os valores podem ser grandes enquanto o limite de
  tamanho de argumentos do sistema operacional é da ordem de 2 MiB. Sem isso, "valores grandes" tem um
  teto que nenhuma escolha de armazenamento remove.
- **Sem classe de exceção própria.** Um `KVStoreError` envolvendo `sqlite3.Error` não acrescentaria
  informação nem permitiria tratamento diferente; acrescentaria um nome a aprender.
- **Sem `--json` na linha de comando.** Valores são texto opaco; embrulhar em JSON obriga o consumidor
  a desembrulhar para chegar ao mesmo texto, e a saída atual já é própria para pipe.

### Known Risks

- **Conexão aberta fora de `_conectar` perde `synchronous=FULL` em silêncio** (o pragma é por conexão).
  Probabilidade média ao longo do tempo, impacto alto: a garantia some sem sintoma. Mitigação: fronteira
  arquitetural proibindo `sqlite3` em `__main__.py`, ponto único de abertura, e os casos UT-020/UT-021
  que leem os pragmas efetivos de um `Store` aberto.
- **Teste de morte abrupta instável por corrida.** Probabilidade média se escrito com `sleep`. Mitigação:
  sincronização por pipe e por sinal, nunca por relógio; o caso que mata **durante** a gravação aceita
  os dois desfechos válidos (valor antigo ou novo) e falha apenas em valor parcial, ausência ou banco
  ilegível.
- **`sqlite3` ausente em build exótica do Python.** Probabilidade baixa, impacto total. Mitigação: falha
  na importação com mensagem clara; `make test` na máquina alvo detecta no primeiro minuto.
- **`fsync` mentiroso em hardware ou volume de container.** Probabilidade baixa, impacto alto, fora do
  alcance de software. Mitigação: registrado como ressalva explícita em Business Rules e no ADR-002, em
  vez de prometido a mais.
- **Arquivo não encolhe após apagar chave grande.** Probabilidade alta, impacto baixo. Mitigação:
  documentado em Non-Goals e em US-008.EC-1; o espaço é reaproveitado.

## Safety Invariants

O caminho de escrita é sensível a concorrência e a morte abrupta. As invariantes:

1. Toda mudança confirmada por `set` ou `delete` está sincronizada em disco antes de a chamada retornar.
2. Toda operação de escrita é atômica: após morte em qualquer instante, a chave afetada tem o valor
   anterior **ou** o novo, nunca um valor parcial, e nenhuma outra chave é alterada.
3. Nenhuma morte abrupta, em nenhum instante, pode deixar o armazenamento ilegível ou vazio quando
   havia dado confirmado antes dela.
4. A durabilidade não depende de encerramento limpo: nem de `close()`, nem de `__exit__`, nem de
   `atexit`, nem de flush de buffer do interpretador.
5. Toda conexão usada para escrever tem `synchronous=FULL` e `journal_mode=WAL` aplicados antes da
   primeira escrita. Não existe segundo caminho de abertura de conexão no pacote.
6. Dois processos no mesmo diretório nunca corrompem o armazenamento: escritas são serializadas pelo
   SQLite, leitores não bloqueiam o escritor e o escritor não bloqueia leitores.
7. Contenção de escrita resolve em espera limitada (5 s) seguida de erro nomeado, nunca em travamento
   indefinido nem em escrita perdida em silêncio.
8. Uma leitura nunca observa um estado intermediário de uma escrita concorrente.

## File References

### Repo Files

- `kvstore/__init__.py` — arquivo vazio hoje; é o alvo da camada de armazenamento e o ponto único de
  abertura de conexão de que dependem as invariantes 1, 4 e 5.
- `Makefile:2-3` — o alvo `test` é o contrato de verificação do enunciado
  (`python3 -m unittest discover -s tests -t .`); define que arquivos novos em `tests/` são descobertos
  sozinhos e que não há framework externo.
- `tests/test_fumaca.py` — o único teste existente; estabelece o estilo (`unittest.TestCase`, nomes em
  português) que as suítes novas seguem.
- `tests/__init__.py` — existe e torna `tests` um pacote; o `-t .` do alvo depende disso para que
  `import kvstore` funcione a partir da raiz.
- `README.md` — declara Python 3.11+, que fixa o limite de compatibilidade (por isso
  `isolation_level=None` e não `Connection.autocommit`); é atualizado na tarefa 4.
- `.gitignore` — ignora `__pycache__/` e `*.pyc`; note que **não** ignora `*.sqlite3`, e os testes usam
  diretório temporário, então nada de banco deve aparecer na árvore.

### External References

Não se aplica: nada foi trazido para dentro do repositório, e não há implementação de referência
vendorizada a espelhar.

### Design and Analysis Sources

- `adrs/adr-001.md` — escolha do motor de armazenamento e as quatro alternativas rejeitadas.
- `adrs/adr-002.md` — nível de durabilidade, com a tabela de modos e o risco do pragma por conexão.
- `_dx.md` — superfície pública congelada; a Part II é desenhada para servi-la.
- `_user_stories.md` — catálogo de comportamento; origem da matriz de cobertura de `_tests.md`.

## Assumptions and Defaults

- **Nome do arquivo**: `kvstore.sqlite3`, dentro do diretório indicado. Os auxiliares `-wal` e `-shm`
  são criados pelo SQLite ao lado dele.
- **Espera sob contenção**: 5000 ms (`busy_timeout`), depois erro com código 3. Ver Open Question 2.
- **`del` de chave ausente termina com código 0** (idempotente). Se o operador precisar distinguir,
  a mudança é uma linha na camada de linha de comando; registrado aqui de propósito para ser fácil de
  reverter.
- **`get` não acrescenta newline** à saída.
- **`list` ordena crescente** por código de caractere (ordem binária do SQLite para `TEXT`), não por
  regra de collation de locale — determinístico entre máquinas.
- **Diretório inexistente é criado** por qualquer comando, inclusive os de leitura.
- **String vazia é valor válido** e distinta de chave ausente.
- **Codificação UTF-8** em stdin, stdout e stderr, independente do locale.
- **Compatibilidade mínima Python 3.11**, conforme o README, mesmo a máquina de desenvolvimento rodando
  3.14.7. Consequência concreta: `isolation_level=None` em vez de `Connection.autocommit`.
- **O diretório é exclusivo do serviço**, conforme o enunciado; o pacote não defende contra terceiros
  apagando os arquivos auxiliares entre execuções.
- **Nenhum log emitido pela biblioteca**; diagnóstico sai por exceção e por código de saída.
- **Valores até o limite do SQLite** (1 GB por valor na configuração padrão); nenhum limite adicional é
  imposto pelo pacote.

## Architecture Decision Records

- [ADR-001: `sqlite3` da biblioteca padrão como motor de armazenamento](adrs/adr-001.md) — usar o
  `sqlite3` que já vem na biblioteca padrão em vez de escrever um log append-only com compactação, uma
  reescrita atômica do JSON inteiro, ou `dbm`.
- [ADR-002: WAL com `synchronous=FULL` como nível de durabilidade](adrs/adr-002.md) — pagar um `fsync`
  por gravação confirmada para cobrir queda da máquina, não só morte do processo, e usar WAL para que
  leitor e escritor não disputem trava.
