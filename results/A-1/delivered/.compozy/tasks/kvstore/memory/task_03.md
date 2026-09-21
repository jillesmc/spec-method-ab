# task_03 memory: Concorrência e crescimento

## Status

Completed. `tests/test_durabilidade.py` gained two new classes (`TestConcorrencia`: IT-020..023;
`TestCrescimento`: IT-030..032), all launching real subprocesses, IT-023 and IT-031 through the
actual `python -m kvstore` CLI. `make test` green at 65/65, run 3 times full plus the 7 new cases
run standalone 10 times consecutively — no flakes after the fix below.

## Bug found and fixed (not just tests written)

`kvstore/__init__.py`'s `_conectar` had a genuine Safety-Invariant-6/7 gap, caught by `IT-022`
(two concurrent writers on a **fresh** directory, no prior `Store` call): `PRAGMA busy_timeout`
was executed *after* `PRAGMA journal_mode = WAL` and the `CREATE TABLE IF NOT EXISTS`, so the very
first schema/journal bootstrap on a brand-new file could race between two processes and raise
`sqlite3.OperationalError: database is locked` immediately instead of retrying — reproduced ~1 in
10-20 runs.

Fixed in two layers:
1. Reordered `_conectar` so `busy_timeout` is set immediately after `sqlite3.connect()`, before
   any other pragma/DDL.
2. That alone was *not* sufficient — confirmed with a minimal raw-`sqlite3` repro (two bare
   processes, no `kvstore` code, `busy_timeout` set first, still ~1-in-7 `database is locked` on
   `PRAGMA journal_mode = WAL` against a fresh file). This is a known SQLite quirk: the very first
   WAL conversion on a zero-byte file can raise `SQLITE_BUSY` without going through the registered
   busy handler. Added `_iniciar_com_retentativa`: a manual retry loop around
   `journal_mode=WAL` + `CREATE TABLE`, catching `OperationalError` with "locked"/"busy" in the
   message, polling every 10ms, bounded by the same `ESPERA_MS` (5s) window as `busy_timeout` —
   preserves Safety Invariant 7 (bounded wait, never indefinite hang) for this specific race too.
   Confirmed via a standalone repro script before and after the fix (raw sqlite3, 20 concurrent
   pairs): failed ~15% of the time before, 0/20 after.

This means task_03, though typed `test`, ended up touching `kvstore/__init__.py` — justified
because the task's own overview says these two invariants "passam a ser resultado medido" and the
Operating Contract requires fixing root causes when tests catch them, not weakening the test.

## Test-writing techniques used (building on task_01's patterns)

- **IT-020** (reader during writer): reused the readiness-pipe pattern, but the *stopping*
  condition is `proc.poll() is not None` (child's own exit), not a clock — the reader loop polls
  `get()` in a tight loop until the writer subprocess (500 fixed-length writes) exits, with a
  `time.monotonic()`-based safety ceiling (30s) that only guards against a real hang, never
  decides pass/fail.
- **IT-021/022** (two independent writers): reused `SCRIPT_SET_E_MORRER` verbatim from task_01 (it
  already does "set one key, exit 0" — no death involved despite the name) instead of writing a
  third near-identical script. Just launched both via `Popen` without pipe sync — "simultaneous"
  here only needs best-effort overlap, not controlled interleaving, since the assertion is on the
  final state, not an intermediate one.
- **IT-023** (contention past busy_timeout): child does `s._con.execute("BEGIN IMMEDIATE")` then
  blocks on a pipe read (same shape as task_01's `SCRIPT_GRAVAR_E_BLOQUEAR`), holding the
  exclusive write lock without committing. Parent runs the *real* CLI (`python -m kvstore <dir>
  set k v`) via `subprocess.run(..., timeout=10)` — `TimeoutExpired` would itself fail the test
  loudly if the busy_timeout/CLI mapping ever regressed into a hang, satisfying "falha
  explicitamente se não retornar em ~10s" without a bespoke watchdog.
- **IT-030/031/032** (growth): all three write through a real subprocess using `with
  kvstore.Store(...) as s:` (not `os._exit`, unlike task_01's death tests) — a clean `close()` is
  what triggers SQLite's automatic WAL→main-file checkpoint, which is what makes
  `os.path.getsize` on `kvstore.sqlite3` alone a meaningful measurement. Using `os._exit` here (as
  task_01's helpers do) would leave data sitting in `-wal` and make the size assertions
  meaningless.
- **`_ler_com_timeout`**: a small `select.select`-based wrapper added around every readiness-pipe
  `os.read` in the new tests, enforcing the task's literal "nenhum subprocess sem timeout"
  requirement even for the blocking-read half of the synchronization (task_01's original pipe
  reads don't have this — left those untouched, out of this task's scope).
- **IT-031 goes through the real CLI for `list`/`get`**, but seeds the 2.000 keys with a single
  `python -c` subprocess calling `Store.set` in a loop — 2.000 individual CLI invocations would
  each pay process-startup cost on top of the fsync, making the case impractically slow.

## Timing (Subtask 3.6)

- New 7 cases alone: 16-18s across 10 consecutive runs (no flakes).
- Full `make test` (65 cases, was 58 before this task): ~51-52s across 3 runs (was ~36s at the
  task_02 baseline). Judged acceptable for daily use; did not reduce the 2.000 counts in
  `IT-030`/`IT-031`.

## Follow-ups for later tasks (not this task's scope)

- README (task_04) can now truthfully claim "no maintenance routine" per `US-008.AC-3` — `IT-030`
  and `IT-032` are the tests that back that claim, both green.
- The `_iniciar_com_retentativa` retry window (5s) is a second, independent contention path from
  the one `IT-023` exercises (mid-write `set`/`get`, already covered by `busy_timeout` alone). No
  test exercises the retry loop itself hitting its own 5s ceiling and re-raising (would need a
  child holding the *initial* WAL-bootstrap lock specifically, which is much harder to engineer
  deterministically than IT-023's `BEGIN IMMEDIATE` on an already-initialized file) — left as a
  documented gap, not asserted.

## Verification evidence

- `python3 -m unittest tests.test_durabilidade.TestConcorrencia tests.test_durabilidade.TestCrescimento
  -v` → 7/7 ok, run 10 times consecutively, all green (16-18s each).
- `make test` → 65/65 ok, run 3 times, ~51-52s each.
- `grep -n sleep tests/test_durabilidade.py` → no output (no `sleep` anywhere in the file,
  including the new classes).
- Every new `subprocess.run`/`Popen.wait()` call carries an explicit `timeout=`.
- `git status --short` after implementation: `kvstore/__init__.py` modified (the busy_timeout/WAL
  retry fix), `tests/test_durabilidade.py` modified (new classes); no stray `kvstore.sqlite3*`
  files left in the repo tree.
- Standalone raw-`sqlite3` repro (`/tmp/race_test`, not committed) confirming the WAL-bootstrap
  race exists independent of `kvstore` code, and confirming the fix closes it (0/20 failures after
  vs ~15% before).
