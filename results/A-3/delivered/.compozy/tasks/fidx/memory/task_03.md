# Task memory: task_03 (Operacao por cron: atomicidade, concorrencia e superficie de erro)

- Status: completed. `make test` green, 52 tests (was 41 before this task; +4 UT, +4 IT, +3 E2E).
- Atomicity (Invariants 1/2) was **already correct** before this task: `index_dir` already ran the
  whole scan/write loop inside `with conn:` (sqlite3's context manager rolls back on exception,
  commits on success). Only change needed: wrap it in `try/finally: conn.close()` so the connection
  is always closed even when the with-block re-raises — no behavior change, just cleanup hygiene.
- `BUSY_TIMEOUT_S` was already "injectable" without adding a parameter: it's a bare module global
  referenced at call time inside `open_index`/functions, so `mock.patch.object(core, "BUSY_TIMEOUT_S", 0.2)`
  works from tests as-is. No signature change there.
- New in `core.py`: `IndexCreateError(FidxError)` (path, reason) — for "pasta sem permissao de
  escrita". `open_index(create=True)` now wraps `connect + PRAGMA + _ensure_schema + commit` in
  `try/except sqlite3.OperationalError`: message containing "locked" -> `IndexBusy(path)` (translates
  the busy-timeout lock error, exit 3 in `__main__`); anything else -> `IndexCreateError(path, str(exc))`
  (exit 2). The lock is actually acquired by the `INSERT OR IGNORE INTO meta` write inside
  `_ensure_schema` when a competing connection holds `BEGIN IMMEDIATE` — CREATE TABLE IF NOT EXISTS
  on already-existing tables does not itself contend for the write lock.
- `index_dir` gained one new optional parameter (not in `_spec.md`'s original frozen sketch, but
  explicitly called for by this task's Implementation Details: "o aviso nasce em core como dado
  (lista de pulados ou callback)"): `on_pulado: Callable[[str, str], None] | None = None`, called as
  `on_pulado(rel, motivo)` for every file skipped due to `OSError` (permission denied, vanished
  mid-scan). `core.py` still never prints; `__main__._avisa_pulado` is the callback that prints
  `fidx: aviso: pulado <path>: <motivo>` to stderr. Skipped files are **not** added to `vistos`, so
  a previously-indexed-then-unreadable file gets swept up by `remove_missing` like any other missing
  path — total/removidos accounting falls out of the existing incremental logic with no special case.
- Used `exc.strerror` (not `str(exc)`) for the skip reason so the message matches `_dx.md`'s
  literal example (`Permission denied`, not `[Errno 13] Permission denied: '/path'`).
- Decoding-tolerance (`errors="ignore"` in `read_text`) and empty-file handling (UT-030/UT-031) were
  **already correct** from task_01 — only needed tests, no production change.
- WAL guarantee (Invariant 3) was **already correct**: `open_index(create=True)` always re-runs
  `PRAGMA journal_mode=WAL` regardless of prior state, and `search` already opened `mode=ro`. No
  production change; IT-008 just proves it with a real second connection holding `BEGIN IMMEDIATE`.
- Concurrency tests (IT-007/IT-008) use a second real `sqlite3.connect(path, isolation_level=None)`
  executing `BEGIN IMMEDIATE` — `isolation_level=None` is required so Python's sqlite3 module doesn't
  fight the manual `BEGIN`/`ROLLBACK` transaction control.
- Rollback tests (IT-006/IT-009) reuse the task_02-established pattern: `mock.patch.object(core,
  "iter_files", side_effect=fake_generator)` where `fake_generator` wraps the real `iter_files` and
  raises after yielding N items — no framework mock needed, matches the repo's existing test style.
- New file `tests/test_operacao.py` (own local `arvore`/`despejo` helpers, matching repo convention:
  no shared test-util module). E2E-007/008/009 added as new methods in `TestE2E` in `tests/test_cli.py`.
- `README.md` extended (not rewritten) with: index location + "apagar e seguro", summary line format,
  whole-token search rule vs `grep`, and the exit-code table (0/1/2/3) from `_dx.md` § Errors.
- Verified `grep -rn "mtime\|st_mtime\|getmtime\|st_size" fidx/` still returns nothing (ADR-001 respected).
- This was the last task in the `fidx` sequence (task_03, no dependents).
