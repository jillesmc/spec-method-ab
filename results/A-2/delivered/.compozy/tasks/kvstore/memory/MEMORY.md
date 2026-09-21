# kvstore — shared workflow memory

- [task_01](task_01.md) — Store/CLI foundation: connection lifecycle, the WAL/SHM-on-close
  gotcha, exception `__str__` gotcha, `os._exit` in the CLI. Read before touching
  `kvstore/store.py` or `kvstore/__main__.py` in task_02/task_03.
- [task_02](task_02.md) — concurrent bootstrap gotcha: SQLite's busy handler does not cover the
  `journal_mode`/`auto_vacuum` transition lock, so N processes racing to create the same brand-new
  `kvstore.db` can get an instant (not timed-out) `StoreBusy`. `Store._connect` now retries just those
  two bootstrap pragmas against `self._timeout` manually. Read before changing `_connect` again.
- [task_03](task_03.md) — `PRAGMA incremental_vacuum` (any pragma implemented as a stepping VM, really)
  only does 1 page/step's worth of work per `sqlite3` `execute()` call unless you `.fetchall()` the
  cursor to drain it. `Store.delete()` now drains it after every delete that removed a row. Read before
  touching the delete path or adding any other multi-step PRAGMA.
