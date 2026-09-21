# Task memory: task_01 (fidx/store.py)

Status: completed.

## Decisions

- **Where `BEGIN IMMEDIATE` actually happens.** The Core Interfaces block shows `__enter__` as the
  `BEGIN IMMEDIATE` point, and `task_03.md` confirms the intended call shape is
  `with Indice.abrir(raiz, criar=True) as idx:`. So `abrir()` only opens/creates/validates the schema
  (never takes a write lock by itself); `__enter__` is what escalates to a write transaction. This keeps
  `search` (`Indice.abrir(raiz, criar=False)` + `.buscar()`, no `with`) lock-free per Safety Invariant 5.
  UT-031's wording ("`Indice.abrir(...)` levanta `IndiceEmUso`") is loose — the actual trigger is entering
  the `with` block right after `abrir()`, since that's the only realistic call shape for the write path.
- **Schema-version mismatch is unconditional**, not gated on `criar`. The requirement text ("schema_version
  divergente ou ausente → apagar e recriar vazio") doesn't mention `criar`, and only `abrir()`'s
  file-not-found branch is gated on `criar`. If this surfaces a problem in task_03/04 (e.g. `search`
  silently discarding a corrupt index), that's a design question for those tasks, not a reason to change
  `store.py` — flag it there instead of preemptively guessing.
- `buscar()` interseção done in SQL (`GROUP BY caminho HAVING COUNT(DISTINCT termo) = ?`), per the task's
  stated preference (avoids loading big term sets into Python).
- `gravar()` upsert uses `INSERT ... ON CONFLICT(caminho) DO UPDATE` (sqlite supports this since well before
  3.11) rather than DELETE+INSERT on `arquivos`, so the row's rowid/associated state is preserved across
  reindexing — an incidental correctness choice, not requested behavior.
- Timeout is 2s (`store.TIMEOUT_CONEXAO`) uniformly on every connection sqlite3.connect() call, including
  the read path — harmless for reads and simpler than branching.

## Touched surfaces

- Created `fidx/store.py` (new file): `IndiceEmUso`, `NOME_ARQUIVO_INDICE`, `SCHEMA_VERSION`, `Indice`.
- Created `tests/test_store.py` (new file): UT-020–UT-032 plus two extra context-manager tests (commit path,
  rollback-on-exception path) that weren't individually numbered in `_tests.md` but are needed to prove
  Safety Invariants 1–3 from the requirements, which UT-020..032 alone don't fully cover.

## Verification run

- `python3 -m unittest tests.test_store -v` → 15/15 ok.
- `make test` → 16/16 ok (includes `tests/test_fumaca.py`).
- `grep -n "print(\|sys\.exit\|import.*scan" fidx/store.py` → no matches (Requirements: no print, no
  sys.exit, no `fidx.scan` import).
- External inspectability: `sqlite3` CLI binary is **not installed** on this machine (`FileNotFoundError`
  when subprocess tries to exec it). Verified equivalently with a fresh, independent
  `sqlite3.connect(path)` + `SELECT count(*) FROM arquivos` in Python instead — confirms the file is a
  valid, externally-readable sqlite3 database. Worth flagging to the operator if a real `sqlite3` CLI check
  is required later; the tool just isn't on PATH here.

## For task_03/task_04

- Use `with Indice.abrir(raiz, criar=True) as idx:` for the whole `index` command body (matches
  `task_03.md`'s own text) — don't call `gravar`/`remover` outside a `with` block for the real CLI path,
  even though `store.py`'s own unit tests do (autocommit mode still makes those visible immediately, which
  is why the unit tests don't need `with`, but the CLI needs the one-transaction-per-run guarantee).
- `search` must call `Indice.abrir(raiz, criar=False)` and use the returned `Indice` directly (no `with`),
  or it will contend for the write lock against a concurrent `index` and violate Safety Invariant 5.
- `IndiceEmUso` is raised from `__enter__`, not from `abrir()` — task_04's error-handling code needs to wrap
  the `with` statement, not just the `abrir()` call, to catch it.
