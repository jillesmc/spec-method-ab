# Task 02 memory — concurrent access and large values

## Decisions

- No production-surface change needed for subtasks 2.1–2.3: task_01's `busy_timeout` wiring, `StoreBusy`
  mapping, and stdin byte-path were already correct. The real work was in 2.4 (writing the tests) and what
  they found.
- `tests/test_concorrencia.py` was added with its own local `_PREAMBULO`/`_run_cli` helpers rather than
  importing the private constants from `tests/test_durabilidade.py` or `tests/test_cli.py` — those are
  module-local by convention, not shared surface.
- UT-029 is split into two methods, per the task's own trap warning: the numbered one only covers a
  cleanly closed store (`kvstore.db` byte/mtime-identical across a read); a second, unnumbered method
  documents that a store whose last writer was killed may legitimately write during WAL recovery on
  reopen, and only asserts the read result, not file identity.

## Bug found and fixed

Writing IT-006 (8 concurrent `python -m kvstore <dir> set ...` CLI processes racing against a **brand-new**
directory) was flaky (~1/3 runs failed) with `StoreBusy`, even though the default `busy_timeout` is 5s.

Root cause (confirmed by isolated repro, not guessed): when several processes race to bootstrap the same
zero-byte `kvstore.db` for the first time, more than one of them attempts the real
`delete → wal` journal-mode transition (and `auto_vacuum=INCREMENTAL`) concurrently. That specific
lock acquisition in SQLite does **not** go through the registered busy handler — losers get
`sqlite3.OperationalError: database is locked` in under 1ms, not after the configured timeout. Confirmed
via `time.perf_counter()` around each pragma in a forked-multiprocess repro: failures always landed on the
very first post-connect pragma, instantly.

Fix, in `kvstore/store.py::Store._connect`: wrap only `PRAGMA auto_vacuum=INCREMENTAL` and
`PRAGMA journal_mode=WAL` in a manual bounded retry (`time.monotonic()` deadline = `self._timeout`, short
`time.sleep(0.005)` between attempts) that only retries on the same busy/locked message
`_is_busy_message` already recognizes. Ordinary statements (`synchronous`, `busy_timeout` pragma,
`CREATE TABLE`, and all of `_execute_mutation`) are untouched — those already honor SQLite's busy handler
correctly (proved by UT-027 waiting out a real 0.1s timeout).

This is *not* a second locking mechanism (the thing ADR-001/the task explicitly forbid): it doesn't add a
lock file, doesn't retry `set`/`delete` themselves, and doesn't add backoff to the write path. It only
makes one specific SQLite lock acquisition — one SQLite's own busy handler happens to skip — wait the same
`self._timeout` window every other lock already gets. If revisiting this: reproduce first with per-pragma
timing (see the repro pattern below) before assuming any locking change is safe; the failure signature is
elapsed time in the microseconds-to-single-digit-milliseconds range despite a multi-second configured
timeout, which is what distinguishes it from a genuine busy_timeout expiry (that one takes close to the
full configured window, as UT-027 shows).

Repro pattern that isolates this (kept out of the test suite as noise, but useful if this regresses):
spawn N forked processes with a `multiprocessing.Barrier`, each opening a fresh `Store` against the same
never-before-used directory, and print `time.perf_counter()` deltas and the exact pragma that failed.

## Verification done

- `tests/test_concorrencia.py`: UT-026, UT-027, UT-028, UT-029 (+ split recovery case), IT-006, IT-007,
  IT-008 (skipped by default, run once explicitly).
- `KVSTORE_SLOW_TESTS=1 python3 -m unittest tests.test_concorrencia.TestProcessosConcorrentes.test_it008_64mib_via_stdin_do_cli`
  → passed, ~0.75s.
- `make test` (48 cases, includes all of task_01's) run 3× clean, ~4.1s each.
- `tests/test_concorrencia.py` alone run 5× clean after the fix (was flaky before, on IT-006, ~1/3 runs).
- Standalone reproduction script (8 concurrent CLI `set` invocations against a fresh dir) run 15× clean
  after the fix.
