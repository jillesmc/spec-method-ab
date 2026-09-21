# Workflow Memory: kvstore

Shared, cross-task context for the `kvstore` delivery. Keep this file to durable facts the
next task genuinely needs; task-local detail lives in each `task_NN.md` memory file.

## Frozen contracts (do not re-derive, just depend on them)

- Public SDK surface is frozen in `_dx.md` § SDK and `_spec.md` § Core Interfaces:
  `Store(diretorio)`, `.set/.get/.delete/.keys/.close`, context manager protocol.
- Single connection-opening point lives in `kvstore/__init__.py` (`_conectar`). task_02's
  `__main__.py` must never import `sqlite3` directly — it only calls `Store`.
- Pragmas reasserted on every connection open: `journal_mode=WAL` (persists in file, reasserted
  anyway), `synchronous=FULL`, `busy_timeout=5000`. Table `kv(chave TEXT PRIMARY KEY, valor TEXT
  NOT NULL)` — with rowid, never `WITHOUT ROWID` (ADR-001, large values).
- Exceptions: no custom hierarchy. `ValueError` (empty key), `TypeError` (non-str key),
  `sqlite3.Error`/`OSError` (storage/filesystem failure) bubble up as-is. `kvstore/__init__.py`
  never writes to stdout/stderr and never calls `sys.exit` — task_02 owns CLI-facing translation.

## task_01 status

Completed — `Store` implemented, `tests/test_store.py` (UT-001..UT-024) and
`tests/test_durabilidade.py` (IT-010..IT-014, IT-040) all pass, `make test` green (31/31).
See `task_01.md` memory for implementation-level detail worth reusing.

## task_02 status

Completed — `kvstore/__main__.py` implements the four verbs against the frozen `_dx.md` § CLI/Errors
surface; `tests/test_cli.py` (E2E-001..E2E-027) all pass, `make test` green (58/58, stable across
repeated runs). See `task_02.md` memory for implementation-level detail worth reusing, especially the
constraint that `__main__.py` must catch storage errors via plain `except Exception` (not
`except sqlite3.Error`) since it's forbidden from importing `sqlite3` at all — not even in a comment,
since the grep check in this task's Success Criteria is literal.

## task_03 status

Completed — `tests/test_durabilidade.py` gained `TestConcorrencia` (IT-020..023) and
`TestCrescimento` (IT-030..032); `make test` green at 65/65, stable across 3 full runs and 10
standalone runs of the 7 new cases. **Found and fixed a real concurrency bug** in
`kvstore/__init__.py::_conectar`: `busy_timeout` was applied after `journal_mode=WAL`/`CREATE
TABLE`, and even after reordering it, the very first WAL bootstrap on a brand-new file could still
race between two processes opening the same fresh directory simultaneously (`database is locked`,
~15% of runs) — a documented SQLite quirk where `busy_timeout`'s handler doesn't cover that
specific moment. Fixed with a bounded manual retry (`_iniciar_com_retentativa`, same 5s budget) —
see `task_03.md` memory for the full repro and fix detail. Any future connection-setup change in
`_conectar` must keep `busy_timeout` first and keep this retry wrapped around the WAL/schema
bootstrap.

## task_04 status

Completed — the delivery graph is now fully implemented. `README.md` rewritten (was 4 lines) with the
four verbs, in-process SDK usage, the durability guarantee with the `fsync`-lying-hardware caveat, the
three known limitations, and the on-disk files note; every command shown was executed against the real
package and its output verified. No code changed. `make test` green at 65/65 (64 assigned test IDs +
1 smoke test), and all 64 IDs from `_tasks.md` § Propriedade dos casos de teste were confirmed present
by name in the three test files, with `IT-022b` confirmed absent. See `task_04.md` memory for detail.
