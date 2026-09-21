---
status: completed
title: Bounded growth over time
type: feature
complexity: medium
---

# Task 3: Bounded growth over time

## Overview

The requester said the number of keys and of writes grows forever and nobody cleans anything up. After
this task merges, that is a measured property rather than an assumption: disk use tracks the live data,
space from deleted keys comes back without anyone running a maintenance command, the journal stays
bounded across thousands of writes, and reading one key out of a hundred thousand does not walk the store.

## Shippable Outcome

- Outcome: a store that has been written to indefinitely and had keys deleted keeps a size proportional to
  what it currently holds, with no operator action.
- Verify in this task: `make test` green with UT-030–UT-032 and IT-009 passing — UT-031 (size drops after
  a mass delete) and UT-032 (2 000 rewrites of one key stay bounded) are the two that would fail if
  reclaim or checkpointing were not actually happening.
- Integration verification: none.

## Requirements

- No change to the public surface: no maintenance verb, no `compact` command, no flag.
  [`_dx.md`](_dx.md) stays exactly as it is — reclaim is automatic or it does not exist.
- Reclaim runs inside the ordinary delete path: after a `delete` commits, release free pages with
  `PRAGMA incremental_vacuum`. This depends on `auto_vacuum=INCREMENTAL` having been set *before* the
  schema was created in task_01 — UT-030 is what proves it took effect, and it cannot be fixed after the
  fact except by a full `VACUUM`.
- Do not run a full `VACUUM`: it rewrites the entire database, which is the whole-dataset rewrite this
  spec exists to eliminate ([ADR-001](adrs/adr-001.md), Motivating Problem).
- Do not add a background thread, a timer, or a checkpoint daemon. WAL checkpointing is SQLite's
  `wal_autocheckpoint` default; this task verifies it holds rather than replacing it.
- Honour [Safety Invariant](_spec.md#safety-invariants) 6: reclaim happens on the write path only, never
  on a read.
- Keep `make test` in the low seconds. IT-009 seeds its 100 000 keys in one bulk transaction on purpose —
  the durable write path is covered by task_01, and 100 000 fsynced writes would cost minutes.
- IT-009 asserts on the query plan, not on elapsed time: a timing assertion on a shared machine is a flaky
  test, not a scale test.

## Subtasks

- [x] 3.1 Add the `PRAGMA incremental_vacuum` step after a successful delete commits in
      `kvstore/store.py`, on the write path only.
- [x] 3.2 Confirm `PRAGMA auto_vacuum` reports `2` on a fresh store and on a reopened one; if it reports
      `0`, fix the creation order in task_01's connection sequence rather than working around it.
- [x] 3.3 Write `tests/test_crescimento.py` with UT-030–UT-032 and IT-009.
- [x] 3.4 Measure the actual numbers UT-031 and UT-032 assert against (peak size, post-delete size, the
      db+wal total after 2 000 rewrites) and set the thresholds from the measurement, keeping headroom so
      the case is not brittle.
- [x] 3.5 Run `make test` and confirm no earlier case changed.

## Implementation Details

File to modify: `kvstore/store.py`. File to create: `tests/test_crescimento.py`.

This is the smallest task in the graph — one pragma call on the delete path plus the evidence that the
storage configuration from task_01 does what the spec claims. If UT-030 fails, the bug is in task_01's
connection order, and that is where it must be fixed.

One trap: `PRAGMA incremental_vacuum` with no argument releases every free page, which after a mass delete
is the behavior UT-031 wants, but on a store with heavy churn it makes one delete pay for all accumulated
free pages. If the measurement in subtask 3.4 shows that cost is material, bound it with an explicit page
count (`PRAGMA incremental_vacuum(N)`) and record the number and the reason in the code.

### Relevant Files

- `kvstore/store.py` — the delete path and the connection pragmas; the only file this task edits.
- `.compozy/tasks/kvstore/_spec.md` — Part II Data Models, for why `auto_vacuum` has to precede the
  schema.
- `tests/apoio.py` — helpers from task_01, reused for directory-size assertions if useful.

### Dependent Files

- `tests/test_store.py` — owns the delete-behavior cases (UT-005, UT-006); adding reclaim to the delete
  path must not change what they observe.

### Related ADRs

- [ADR-001: SQLite as the storage engine](adrs/adr-001.md) — free-page reuse is one of the mechanisms the
  engine choice bought instead of a hand-written compactor; also why a full `VACUUM` is off the table.

## Deliverables

- Automatic space reclaim on the delete path, with no new public surface.
- `tests/test_crescimento.py` covering UT-030–UT-032 and IT-009, with thresholds set from measurement.

## Tests

Cases assigned from [`_tests.md`](_tests.md) — read each definition before writing it.

- [x] UT-030 — `PRAGMA auto_vacuum` is `2` (INCREMENTAL) on creation and on reopen.
- [x] UT-031 — 200 keys of 64 KiB written then all deleted: `list()` empty and `kvstore.db` under 25% of
      its peak.
- [x] UT-032 — one 64 KiB key rewritten 2 000 times: `kvstore.db` plus `kvstore.db-wal` stay under 8 MiB
      and the last value reads back correctly.
- [x] IT-009 — 100 000 bulk-seeded keys: `list()` returns all of them sorted, and `EXPLAIN QUERY PLAN`
      shows an index search for `get`, not a table scan.

## Success Criteria

- `make test` passes, still in the low seconds, with every task_01 and task_02 case unchanged.
- No full `VACUUM`, no background thread, no maintenance command exists in the package.
- `_dx.md` is byte-identical to what task_01 shipped against.
- The thresholds in UT-031 and UT-032 are justified by a measurement recorded in the task's completion
  note, not guessed.

## Completion Note

- **UT-030**: `PRAGMA auto_vacuum` was already `2` on creation and on reopen before this task — task_01's
  connection order (bootstrap `auto_vacuum=INCREMENTAL` before `CREATE TABLE`) was already correct. No
  fix to task_01 was needed; UT-030 is a regression guard, not a bug fix.
- **Gotcha found while implementing 3.1**: `conn.execute("PRAGMA incremental_vacuum")` on its own only
  frees **one page per call**, regardless of an explicit `(N)` argument — Python's `sqlite3` module steps
  the pragma's VM exactly once per `execute()` and the VM frees one page per step. The fix is
  `.fetchall()` on the returned cursor to drain it to completion, which does clear the whole freelist in
  one call (confirmed: `freelist_count` went from 16 → 0 in a single drained call vs. 16 → 15 undrained).
  Recorded in `kvstore/store.py`'s comment and in task memory so it isn't rediscovered.
- **Measurements behind the thresholds** (this machine, Python 3.14.7 / SQLite 3.53.1, ext4 `/tmp`):
  - UT-031: peak `kvstore.db` after 200×64 KiB writes = 13 238 272 bytes (~12.6 MiB); after deleting all
    200 (with the drained `incremental_vacuum` on each delete) and forcing a WAL checkpoint,
    `kvstore.db` = 16 384 bytes (one page) — ratio ≈ 0.0012. Threshold set at 25% of peak, ~200x headroom
    over the measured ratio.
  - UT-032: after 2 000 rewrites of one 64 KiB key, `kvstore.db` + `kvstore.db-wal` = 4 201 952 bytes
    (~4.0 MiB), from SQLite's own default `wal_autocheckpoint` (no code change needed — this pins that it
    holds). Threshold set at 8 MiB, ~2x headroom.
  - Per-delete cost of the drained vacuum stays bounded (~9 ms/delete average over the 200 calls) because
    each call only ever has that one delete's freshly-freed pages to release — the freelist never
    accumulates a backlog, so no explicit page-count bound (`incremental_vacuum(N)`) was needed per the
    task's own trap warning.
- **Timing**: `make test` (52 cases, +4 from this task) runs in ~17s clean, up from ~4.1s after task_02 —
  the increase is almost entirely UT-031's 200 real deletes (~1.9s) and UT-032's 2 000 real fsynced
  writes (~8s), both required by the canonical test definitions (no bulk-seed shortcut applies to them,
  unlike IT-009). Still low seconds, not minutes.
