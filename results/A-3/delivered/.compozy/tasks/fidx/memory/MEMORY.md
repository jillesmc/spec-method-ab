# Workflow memory: fidx

- Schema, exceptions and core function signatures are frozen by task_01 exactly as in
  `_spec.md` Implementation Design — task_02/task_03 extend `core.py`, they don't change the
  schema or the public signatures.
- `search()` opens the index with `sqlite3.connect("file:<path>?mode=ro", uri=True)` so it can
  never create the file; missing/incompatible index -> `IndexMissing`. `index_dir()` opens with
  `create=True`, which runs `PRAGMA journal_mode=WAL` + schema creation + a `conn.commit()`
  before the single indexing transaction starts.
- `open_index(create=True)` and `_ensure_schema` are already schema-version aware only to the
  extent of writing `meta.schema_version`; the "recreate on mismatch" behavior (IT-005) is
  task_02 scope per `_tasks.md` coverage table — not implemented yet.
- task_02 done: incremental reindex lands as a single `if conhecidos.get(rel) != digest` inside
  `index_dir`'s existing loop, `known_files(conn)` as the one query that feeds it, and a
  version-mismatch branch inside `_ensure_schema` (drop `files`/`postings` + the meta row, then
  recreate) — no new functions beyond `known_files`, no schema/signature changes. `remove_missing`
  turned out to already exist from task_01 and needed no changes. See `task_02.md` for detail.
- task_03 done (final task in the sequence): most Safety Invariants (1/2 atomicity, 3 WAL) were
  already correct from task_01/02 and only needed tests. Real production additions: `IndexCreateError`
  exception (read-only dir -> exit 2), lock-detection in `open_index` (`"locked" in str(exc)` ->
  `IndexBusy` -> exit 3, timeout via the pre-existing `BUSY_TIMEOUT_S` module global, no signature
  change needed since it's read at call time), and one new optional `index_dir(root, on_pulado=...)`
  callback param so `core.py` can report skipped files as data without printing (the one deliberate
  exception to "task_01/02 froze the public signatures" — this task's own spec explicitly calls for
  a callback/list here). See `task_03.md` for full detail.
