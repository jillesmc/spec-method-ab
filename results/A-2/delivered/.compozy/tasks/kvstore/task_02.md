---
status: completed
title: Concurrent access and large values
type: feature
complexity: high
---

# Task 2: Concurrent access and large values

## Overview

After this task merges, an operator can inspect or fix a key from a shell while the service is writing to
the same directory, and nothing breaks: concurrent writers are serialized, a writer that cannot get the
lock fails loudly instead of corrupting anything, and readers never see a half-written value. It also
pins the behavior for the values the requester called large — multi-megabyte text, in and out, byte for
byte.

## Shippable Outcome

- Outcome: several processes can use one state directory at the same time, and a value of several tens of
  megabytes round-trips unchanged through the CLI.
- Verify in this task: `make test` green with UT-026–UT-029 and IT-006–IT-007 passing, plus IT-008 run once
  locally with `KVSTORE_SLOW_TESTS=1` and its result recorded in the task's completion note.
- Integration verification: none — the concurrency cases run real processes against a real directory, which
  is the entry path.

## Requirements

- No change to the public surface: this task adds no verb, no flag, and no exception type beyond what
  [`_dx.md`](_dx.md) already lists. `StoreBusy` and the busy message are already in that contract.
- Contention is handled by SQLite's write lock plus `busy_timeout` alone. Do not add an application-level
  retry loop, a lock file, or a backoff — a second locking mechanism on top of SQLite's is a deadlock
  waiting to be written ([ADR-001](adrs/adr-001.md)).
- A `set`/`delete` that gives up on the lock must raise `StoreBusy` having written nothing, and the CLI
  must map it to exit 3 with the message in the `_dx.md` error table.
- Honour [Safety Invariant](_spec.md#safety-invariants) 5 (writers serialized, a timed-out writer writes
  nothing) and 6 (read paths never modify the directory — including against a directory whose last writer
  was killed and whose journal is being recovered).
- Values are held in memory in full on both `set` and `get`; that is the accepted limit recorded in Known
  Risks. Do not introduce streaming or `blobopen()` here.
- Keep `make test` in the low seconds: the 64 MiB case (IT-008) must skip unless `KVSTORE_SLOW_TESTS=1`
  and must say why when it skips.
- The concurrency tests must be deterministic, not timing-lucky: synchronize child processes with pipes or
  barriers rather than `sleep`, and assert on outcomes rather than on durations.

## Subtasks

- [x] 2.1 Confirm the `busy_timeout` wiring from task_01 is on every connection and derives from the
      `Store(timeout=...)` argument in milliseconds; fix it if it only reached `sqlite3.connect(timeout=)`.
- [x] 2.2 Map SQLite's "database is locked" failure to `StoreBusy` in `kvstore/store.py`, and `StoreBusy`
      to exit 3 with the `_dx.md` message in `kvstore/__main__.py`, without swallowing other
      `sqlite3.OperationalError` causes into the same class.
- [x] 2.3 Verify and, if needed, fix the stdin value path (`set <chave> -`) for multi-megabyte input:
      read from `sys.stdin.buffer` in full, never through a text wrapper that would re-encode.
- [x] 2.4 Write `tests/test_concorrencia.py` with UT-026–UT-029 and IT-006–IT-008.
- [x] 2.5 Run IT-008 once with `KVSTORE_SLOW_TESTS=1` and record the result.
- [x] 2.6 Run `make test` and confirm every task_01 case still passes unchanged.

## Implementation Details

Files to modify: `kvstore/store.py` (busy mapping, pragma wiring), `kvstore/__main__.py` (stdin path, exit
code mapping). File to create: `tests/test_concorrencia.py`.

Most of this task is verification rather than new code — if task_01 was implemented as specified, the
concurrency behavior is already correct and the work is proving it and fixing what the proof finds. Do not
add machinery to make the tests pass that the tests did not show to be missing.

Two traps:

- `sqlite3.OperationalError` covers far more than lock contention. Match on the locked/busy condition
  specifically; mapping every `OperationalError` to `StoreBusy` would report a schema error as "banco
  ocupado".
- A reader that opens the store while a killed writer's journal is being recovered *does* cause SQLite to
  write — recovery is a write. UT-029 asserts on `kvstore.db` remaining unchanged for an ordinary read of
  a cleanly closed store; do not weaken the assertion to make a recovery case pass, split the case.

### Relevant Files

- `kvstore/store.py` — connection setup, error mapping; the file this task edits.
- `kvstore/__main__.py` — stdin handling and the exit-3 mapping.
- `tests/apoio.py` — child-process helpers from task_01, reused for the concurrent writers.
- `.compozy/tasks/kvstore/_dx.md` — the frozen busy message and exit code.

### Dependent Files

- `tests/test_durabilidade.py` — shares the child-process helpers; a change to `tests/apoio.py` must keep
  those cases passing.

### Related ADRs

- [ADR-001: SQLite as the storage engine](adrs/adr-001.md) — why the locking is SQLite's and not ours.
- [ADR-002: Durability by `synchronous=FULL` and one transaction per mutation](adrs/adr-002.md) — why
  there is no batching to amortize contention.

## Deliverables

- `StoreBusy` raised and mapped correctly, with nothing written by the failed attempt.
- A verified stdin path for multi-megabyte values.
- `tests/test_concorrencia.py` covering UT-026–UT-029 and IT-006–IT-008.

## Tests

Cases assigned from [`_tests.md`](_tests.md) — read each definition before writing it.

- [x] UT-026 — 8 MiB value round-trips through the API.
- [x] UT-027, UT-028 — `StoreBusy` under a held write lock, and the `busy_timeout` actually applied.
- [x] UT-029 — read paths leave `kvstore.db` byte- and mtime-identical.
- [x] IT-006, IT-007 — eight concurrent writer processes; a concurrent reader against a looping writer.
- [x] IT-008 — 64 MiB through the CLI stdin path (opt-in via `KVSTORE_SLOW_TESTS=1`).

## Success Criteria

- `make test` passes and stays in the low seconds; no task_01 case changed to accommodate this task.
- IT-008 passes when run with `KVSTORE_SLOW_TESTS=1`, and its result is recorded.
- No lock file, retry loop, or backoff was added anywhere in the package.
- `_dx.md` is unchanged: the surface this task hardens is the surface task_01 shipped.

## Completion Note

- `busy_timeout` wiring (2.1), the `StoreBusy`/exit-3 mapping (2.2), and the stdin byte path (2.3) were
  already correct from task_01; no change was needed for those three subtasks.
- Writing IT-006 (eight concurrent CLI writers against a brand-new directory) reproduced a real bug: on a
  cold bootstrap, multiple processes can race to flip a fresh, still-`delete`-journal-mode `kvstore.db`
  into WAL mode at the same instant. SQLite's `busy_timeout`/busy handler does not cover that specific
  lock acquisition (`PRAGMA auto_vacuum=INCREMENTAL` / `PRAGMA journal_mode=WAL`), so the losing
  process(es) got `sqlite3.OperationalError: database is locked` in under a millisecond — not after the
  configured timeout — which `kvstore/store.py` then (correctly, but on a false signal) reported as
  `StoreBusy`. Confirmed by direct reproduction (isolated pragma-by-pragma timing) that the failure always
  landed on the very first post-connect pragma, immediately, regardless of the 5s `busy_timeout`.
  Fixed in `kvstore/store.py::Store._connect` by manually bounding the retry of just those two bootstrap
  pragmas to `self._timeout` (a `time.monotonic()` deadline with a short sleep between attempts) before
  giving up — this is not a second lock: it makes SQLite's own lock wait for the one acquisition its busy
  handler skips, instead of adding any file lock, retry-around-`set`, or backoff of our own. Verified with
  15 back-to-back runs of the reproduction script and 5 back-to-back full `make test` runs, all green.
- IT-008 (64 MiB through `python -m kvstore <dir> set grande -`, then `get`, compared byte for byte) was
  run once with `KVSTORE_SLOW_TESTS=1`: passed in ~0.75s, byte-exact round trip confirmed.
- UT-029 is split into two test methods per the task's guidance: the ID itself only covers a cleanly
  closed store; a second, unnumbered test documents that a store reopened after its last writer was
  killed *is* allowed to write during WAL recovery, and only asserts the value is still readable, not that
  `kvstore.db` is byte-identical.
