# task_01 — Durable store and CLI

## Decisions and learnings future tasks (task_02, task_03) need

- **SQLite auto-deletes `-wal`/`-shm` on the last connection's orderly close.** Verified
  empirically on this machine (Python 3.14.7, SQLite 3.53.1): closing the last open
  connection to a WAL-mode database runs a full checkpoint and removes the `-wal`/`-shm`
  files, leaving only the main `.db` file. This contradicts `_dx.md`'s golden path, which
  shows all three files present after several sequential CLI commands.
  - Fix: `kvstore/__main__.py`'s `if __name__ == "__main__":` block never calls
    `store.close()`, and exits via `os._exit(code)` (after flushing stdout/stderr)
    instead of `sys.exit(code)`. A normal Python interpreter shutdown still finalizes
    (and thus closes) the `Connection` via refcounting before the process truly exits —
    confirmed empirically that plain `sys.exit()` still triggers the same WAL/SHM
    cleanup. Only `os._exit()` bypasses it.
  - This only matters for the CLI's own process exit. `Store.close()` / the context
    manager still do a normal close for library (`Store` API) callers — that's correct
    and expected; only the CLI's golden-path transcript depends on the files surviving.
  - If task_02/task_03 add any codepath that explicitly closes a `Store` at the end of
    a CLI command, re-verify the `ls` transcript in `_dx.md` still matches.
- **`KeyNotFound(KVStoreError, KeyError)` needs its own `__str__`.** `KeyError.__str__`
  reprs its argument (a long-standing Python wart), so `str(KeyNotFound("chave nao
  encontrada: x"))` would render as `"'chave nao encontrada: x'"` (with quotes) instead
  of the plain message. Overrode `__str__` in `store.py` to return `self.args[0]`
  directly. Any other exception added on top of `KeyError`/`LookupError` needs the same
  treatment.
- **Corruption vs. busy vs. permission errors all surface as `sqlite3.DatabaseError`
  subclasses** (`OperationalError` is a subclass of `DatabaseError`, not a sibling).
  `_connect()` in `store.py` distinguishes them by message substring (`"locked"`/`"busy"`
  → `StoreBusy`, else → `KVStoreError` "banco corrompido"). Permission failures on the
  write path are caught *before* ever calling `sqlite3.connect()`, via an explicit
  `os.open(db_path, O_RDWR | O_CREAT)` pre-check — this is what lets the error message
  carry the exact OS `strerror` text (`"Permission denied"`) that `_dx.md` requires,
  since SQLite's own "unable to open database file" message doesn't include it.
- **Connection order is create-time-conditional, not just a fixed sequence.**
  `auto_vacuum=INCREMENTAL` and `PRAGMA user_version=<FORMAT_VERSION>` are only executed
  when `_connect(create=True)` (a brand-new db file); `journal_mode`, `synchronous`, and
  `busy_timeout` are re-applied on every connect, matching the "per-connection settings
  must be reapplied on reopen" requirement (UT-018/UT-019).
- **IT-003 (kill mid-large-write) is inherently a best-effort race.** The child acks via
  a background thread fired concurrently with the start of the large `set()`, so the
  parent's `SIGKILL` *usually* lands during the write, but there's no hard guarantee.
  The assertion doesn't require it to land mid-write either way: since `"grande"` never
  had a prior value, "absent or a complete previous value" reduces to "absent, or the
  one complete value" — both outcomes pass. If this test becomes flaky under CI load,
  the fix is tightening the race, not changing the assertion.
- **`tests/apoio.py` child-process pattern**: pass the pipe write-fd as the *last*
  positional CLI argument (its actual integer value, via `pass_fds`) rather than
  hardcoding fd 3 — `os.pipe()` does not guarantee fd 3. Test child processes need
  `sys.path.insert(0, sys.argv[1])` with the repo root (`apoio.raiz_repositorio()`)
  since they run as detached `python -c` invocations with no inherited package context.
- Key/value validation (`InvalidKey`) is applied uniformly across `set`/`get`/`delete`
  in `Store`, not just `set` — `_dx.md` only shows CLI examples for `set`, but an
  invalid key can never exist in the store regardless of verb, so this seemed like the
  correct generalization. Worth flagging if a future task's test contradicts it.

## Status

Completed. `make test` green (40/40), Golden Path hand-run confirmed byte-for-byte
against `_dx.md`, including the auto-created-directory and not-a-directory failure
cases.
