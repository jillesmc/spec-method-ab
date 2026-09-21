# Task memory: task_02 (Reindexacao incremental por hash de conteudo)

- Status: completed. `make test` green, 41 tests (was 27 before this task).
- `index_dir` now diffs against `known_files(conn)` (new function, one `SELECT path, sha256
  FROM files`) and only calls `replace_file`/`tokenize` when the digest differs — the exact `if`
  from the task's Implementation Details pseudocode. `reindexados` only increments on real work.
- `remove_missing` was already implemented in task_01's `core.py` (ahead of its task_02 subtask
  listing) and already avoided the SQLite bound-variable trap — it diffs `known - vistos` in
  Python and deletes with `executemany`, not a `NOT IN (...)` with thousands of params. No change
  needed there; only wired it into the incremental loop, which it already was.
- `_ensure_schema` now reads `meta.schema_version` before creating `files`/`postings`: if a row
  exists and differs from `SCHEMA_VERSION`, it drops both tables and the meta row first, then
  recreates everything empty. This makes IT-005 (old schema) and a from-scratch index behave
  identically after the drop — full reindex falls out of the normal digest-mismatch path, no
  separate "wipe and reindex" branch was needed.
- Deliberately did not touch `remove_missing`, `replace_file`, `open_index`, `search`, or
  `__main__.py` — none needed a behavior change for this task; `__main__.py` already just
  destructures the same 3-tuple.
- New file `tests/test_incremental.py` covers UT-020..UT-029 and IT-002..IT-005 (each test file
  redefines its own local `arvore()` helper, matching the existing repo convention in
  `test_core.py`/`test_cli.py` — no shared test-util module exists or was added).
- E2E-006 added as a new method inside `TestE2E` in `tests/test_cli.py` (not a new file), per
  `_tests.md` Strategy → Arquivos.
- Verified `grep -rn "mtime\|st_mtime\|getmtime\|st_size" fidx/` returns nothing (Success
  Criteria requirement) — confirms ADR-001 is respected structurally, not just by test passing.
