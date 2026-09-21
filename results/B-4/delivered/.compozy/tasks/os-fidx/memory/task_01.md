# task_01 — Storage and tokenising

## Implementado

`fidx/__init__.py`:

- `tokens(text)` → `set(re.findall(r"\w+", text.casefold()))`.
- `index_path(directory)` → `<directory>/.fidx/index.sqlite3` (constantes
  `INDEX_DIRNAME`, `INDEX_FILENAME`).
- `open_index(directory)` → cria `.fidx/` se ausente, conecta com
  `sqlite3.connect(..., timeout=BUSY_TIMEOUT_SECONDS)` (busy timeout via o
  parametro nativo do driver, sem PRAGMA redundante), le `PRAGMA user_version`;
  se != `SCHEMA_VERSION` (1), dropa `files`/`postings` e recria do zero
  (`_SCHEMA`) — mesmo caminho de codigo serve tanto para "banco novo" (version
  0) quanto para "versao incompativel".

Schema exatamente como em `design.md` decisao 2: `files(path PK, digest)`,
`postings(term, path, PK(term,path)) WITHOUT ROWID`, indice `postings_path`.

## Testes

`tests/test_storage.py` (6 casos, todos verdes com `make test`):
- `TestTokens`: case folding, acentuacao (`Orçamento`→`orçamento`), digitos,
  pontuacao como separador.
- `TestOpenIndex.test_reopen_reuses_schema`: abre, insere linha, fecha, reabre,
  confirma schema e dado preservados.
- `TestSchemaVersionMismatch`: grava um sqlite com `user_version=99` e uma
  tabela `files` com lixo, chama `open_index`, confirma versao corrigida para 1
  e tabela vazia (rebuild), depois confirma que a tabela nova (`postings`) e
  usavel.

## Para as proximas tarefas (task_02+)

- `open_index()` retorna uma `sqlite3.Connection` normal (nao read-only) — quem
  chamar precisa fazer `commit()`/`close()`. `index_directory()` (task 2.2) deve
  reusar essa conexao dentro de uma unica transacao, conforme design.md decisao 3.
- Search (task 3.x) vai precisar abrir a conexao **read-only**
  (`sqlite3.connect("file:...?mode=ro", uri=True)`) e tratar "sem index" como
  erro distinto — `open_index()` atual sempre cria o arquivo se ausente, entao
  o modo read-only para search precisa de uma funcao separada (ou checagem de
  existencia do arquivo antes de chamar `open_index`).
- Nao criei `fidx/__main__.py` nem `index_directory`/`search` — fora do escopo
  desta tarefa (secoes 2-4 do `tasks.md`).

## Bloqueio conhecido (nao desta tarefa, mas repetido em todas)

`openspec` CLI nao esta instalado nesta maquina. `openspec validate fidx --strict`
nao pode ser executado; ver nota em `MEMORY.md`.
