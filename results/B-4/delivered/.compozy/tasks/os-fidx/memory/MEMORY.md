# Shared workflow memory — os-fidx

Convertido de `openspec/changes/fidx/{proposal,design,tasks}.md`. Ler esses arquivos
(mais `specs/content-index/spec.md` e `specs/content-search/spec.md`) para contexto
completo — este arquivo so registra decisoes que atravessam tarefas.

## Decisoes de projeto (validas para todas as tarefas)

- Todo o pacote fica em `fidx/__init__.py` (storage, tokenising, refresh, search);
  CLI em `fidx/__main__.py` (ainda nao criado — task_04).
- Schema SQLite (design.md decisao 2):
  `files(path TEXT PRIMARY KEY, digest TEXT NOT NULL)`,
  `postings(term TEXT NOT NULL, path TEXT NOT NULL, PRIMARY KEY(term,path)) WITHOUT ROWID`,
  index `postings_path ON postings(path)`, `PRAGMA user_version = 1`.
- Index vive em `<directory>/.fidx/index.sqlite3`.
- `tokens(text)` = `set(re.findall(r"\w+", text.casefold()))`.
- `openspec` CLI nao esta instalado nesta maquina (`which openspec` falha) — o passo
  "`openspec validate fidx --strict` deve passar" de cada task nao pode ser executado
  localmente; reportar como bloqueio de ferramenta externa, nao pular a tarefa.
- `make test` = `python3 -m unittest discover -s tests -t . -v` (Makefile). Python 3.14.7
  instalado, satisfaz o minimo 3.11+ do proposal.

## Estado por tarefa

- task_01 (Storage and tokenising): ver `task_01.md` nesta pasta.
- task_02 (Content-addressed refresh): ver `task_02.md` nesta pasta. `index_directory()`
  existe; `search()` (secao 3) ainda nao — os testes de refresh leem `postings`
  diretamente por sqlite3 em vez de chamar uma API de busca inexistente.
- task_03 (Search): ver `task_03.md` nesta pasta. `search(directory, term)` existe,
  conexao read-only via `file:...?mode=ro`, levanta `fidx.IndexNotFoundError` (indice
  ausente) ou `ValueError` (query vazia apos `tokens()`) — task_04 (CLI) deve mapear os
  dois para o exit code de usage/operational failure (2) e "lista vazia sem excecao" para
  exit code 1 (sem match).
- task_04 (CLI): ver `task_04.md` nesta pasta. `fidx/__main__.py` existe:
  `python -m fidx <directory> index|search <term>`. Exit codes: 0 sucesso/match, 1 sem
  match (stdout vazio), 2 diretorio ausente / indice ausente / query vazia (mensagem em
  stderr). Relatorio de `index` em stdout: `seen=N reprocessed=N removed=N` (formato
  proprio, nao normativo). `main()` checa `os.path.isdir(directory)` antes de despachar
  porque `index_directory()` cria diretorios pais ausentes silenciosamente via
  `os.makedirs(exist_ok=True)`.
- task_05 (Wrap-up): ver `task_05.md` nesta pasta. `README.md` documentado (comandos,
  localizacao do indice, exit codes). Suite completa (30 testes) verde. Change `fidx`
  completo (task_01–task_05).
