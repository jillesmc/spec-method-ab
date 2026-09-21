# task_01 — Núcleo do índice (`fidx/__init__.py`)

## Implemented

- `_varrer(dir)`: `os.walk`, prunes dotfile dirs/files in place, skips symlinks, returns sorted
  relative POSIX paths.
- `_tokenizar(texto)`: `re.findall(r"\w+", texto.casefold())` — single function used by both index
  and search (design D4).
- `_conectar(dir)`: opens/creates `<dir>/.fidx/index.sqlite3`, tables `files(path PK, hash)` and
  `postings(term, path, PK(term,path))`. Drops+recreates on `PRAGMA user_version` mismatch, else
  `CREATE TABLE IF NOT EXISTS` is idempotent (no duplicate-schema risk on repeat opens). Connect
  uses `timeout=30` for lock resilience (design mentions this for the future CLI OperationalError
  handling in task_03; set here since it's the connection point).
- `index(dir) -> Resumo`: one read per file, sha256 on raw bytes, skip UnicodeDecodeError files
  silently (not counted), per-file transaction (delete old postings, insert new, upsert hash) —
  matches D6 crash-consistency. Removed files (in `files` table but not seen in scan) deleted at
  the end. `Resumo` is a `NamedTuple(reprocessados, inalterados, removidos)`.
- `search(dir, termo) -> list[str]`: tokenizes the term, rejects anything that doesn't normalize to
  exactly one token (`ValueError`) — this validation lives in `search()`, not the future CLI, since
  it's part of the tokenization contract from D4. Raises `FileNotFoundError` if
  `.fidx/index.sqlite3` doesn't exist yet (never indexed) rather than silently creating an empty
  index and returning `[]` — needed so task_03's CLI layer (3.4) can catch it and print the
  "run index first" message without duplicating the check.

## Scope decisions

- Task_01 covers only tasks.md section 1 (items 1.1-1.5). Sections 2 (extra incrementality tests),
  3 (`fidx/__main__.py` CLI) and 4 (closing/README) are task_02/03/04 — did not touch
  `fidx/__main__.py` or README here, on purpose.
- Tests added in `tests/test_indice_core.py`, one class per item (varredura, tokenização, banco,
  index, search), matching the exact scenarios each item's description calls for. Private
  functions (`_varrer`, `_tokenizar`, `_conectar`, `_SCHEMA_VERSION`) are tested directly by name —
  acceptable for core-logic unit tests per design D9 ("a lógica testa direto, sem subprocesso").

## Verification run

- `python3 -m unittest discover -s tests -t . -v` → 7 passed (1 pre-existing smoke test + 6 new).
- `make test` → same, exit 0.
- `openspec validate fidx --strict` → **could not run**, `openspec` binary not present in this
  environment (checked PATH, npm registry, pip). See shared memory. Left for whoever closes the
  change (task_04) to verify once the CLI is available, or to confirm the harness runs it
  elsewhere.
