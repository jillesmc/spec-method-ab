# Memória: task_01 — Abertura do store e pragmas de durabilidade

## Status

Implementada e verificada. `status: completed` em `task_01.md`.

## O que foi feito

- `kvstore/__init__.py`: função interna `_connect(directory)` que cria o diretório sob
  demanda, abre/cria `kvstore.sqlite3`, aplica `PRAGMA auto_vacuum=INCREMENTAL` antes do
  `CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL)`, e os
  pragmas de durabilidade `journal_mode=WAL`, `synchronous=FULL`, `busy_timeout=5000`,
  `journal_size_limit=64MiB` (64*1024*1024 bytes).
- `tests/test_abertura.py` (3 testes, todos verdes com `make test`):
  - diretório novo é criado sob demanda e o store reporta `PRAGMA auto_vacuum == 2`;
  - `PRAGMA synchronous == 2` (FULL) e `PRAGMA journal_mode == "wal"` efetivos em tempo de
    execução, lidos da própria conexão aberta (não só o valor escrito no código);
  - abrir duas vezes seguidas (a segunda depois de já ter uma linha gravada) não recria a
    tabela nem altera os dados — a segunda abertura ainda lê a linha inserida pela primeira.

## Decisões locais

- `_connect` é privada (prefixo `_`) porque `task_02` é quem define a API pública
  (`set`/`get`/`delete`/`list_keys`); ela deve chamar `_connect` internamente a cada
  operação, não expor conexão sqlite crua para fora do módulo.
- `busy_timeout=5000` ms e `journal_size_limit=64MiB`: valores não especificados
  explicitamente em design.md ("alguns segundos" / "impede WAL grande"); escolhidos como
  default razoável. Se `task_05` (concorrência) achar 5s insuficiente sob N processos
  concorrentes, ajustar aqui, não duplicar a constante em outro lugar.

## Verificação executada

- `make test` → `python3 -m unittest discover -s tests -t . -v`: 4 testes, todos OK
  (3 novos de `test_abertura.py` + o smoke test pré-existente `test_fumaca.py`).
- `openspec validate kvstore --strict`: **não executável neste ambiente** — CLI `openspec`
  ausente (ver `MEMORY.md` da workflow, seção "Bloqueio ambiental"). Comando que seria
  rodado: `openspec validate kvstore --strict`.

## Sem pendências de escopo

Seções 2–6 do change (operações, CLI, testes de crash, concorrência, fechamento) ficam para
`task_02`–`task_06`, na ordem definida em `_tasks.md`. Nenhum código delas foi antecipado
aqui além do necessário para `_connect` ser reusável.
