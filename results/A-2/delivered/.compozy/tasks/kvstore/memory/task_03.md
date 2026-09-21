# Task 03 memory — bounded growth over time

## Decisions

- UT-030 needed no fix: task_01's connection order (bootstrap `auto_vacuum=INCREMENTAL` before
  `CREATE TABLE`) already reports `2` on creation and reopen. Subtask 3.2 was a confirmation, not a bug.
- `delete()` in `kvstore/store.py` now runs `PRAGMA incremental_vacuum` after every delete that actually
  removed a row (`rowcount > 0`), never on a no-op delete and never on any read path (Safety Invariant 6).
  Calling it after *every* delete — rather than batching — is what avoids the task's own trap ("one delete
  pays for all accumulated free pages"): each call only ever has that single delete's freshly-freed pages
  to release, so cost stays ~flat per call instead of growing with churn. No explicit `(N)` bound was
  needed as a result.

## Bug found and fixed (the one worth remembering)

`conn.execute("PRAGMA incremental_vacuum")` — with or without an explicit `(N)` argument — only frees
**one page per call** unless the returned cursor is drained. Python's `sqlite3` module calls
`sqlite3_step()` once per `execute()`, and SQLite's incremental_vacuum VM frees one page per step; without
draining, you silently get 1/Nth of the vacuum you asked for. Confirmed by isolated repro: undrained loop
of 20 calls needed all 20 to clear a 16-page freelist (1 page/call); `.fetchall()` on a single call cleared
the same 16-page freelist in one shot. Fix: `self._execute_mutation(conn, "PRAGMA incremental_vacuum", ()).fetchall()`.
This generalizes to any other multi-page-affecting PRAGMA invoked via the `sqlite3` module (e.g. `wal_checkpoint`
already happens to return one row so this wasn't hit there, but any pragma implemented as a stepping VM is
at risk) — drain the cursor, don't trust a bare `execute()`.

## Measurements (this machine, Python 3.14.7 / SQLite 3.53.1, ext4 `/tmp`)

- UT-031: peak `kvstore.db` = 13 238 272 B after 200×64 KiB writes; 16 384 B after deleting all 200
  (checkpointed). Threshold: peak × 0.25 (~200x headroom over the measured ratio of 0.0012).
- UT-032: `kvstore.db` + `kvstore.db-wal` = 4 201 952 B after 2 000 rewrites of one 64 KiB key, from
  SQLite's default `wal_autocheckpoint` alone — no code change needed for this half. Threshold: 8 MiB
  (~2x headroom).
- `make test` went from ~4.1s (end of task_02) to ~17s. Almost entirely UT-031's 200 real deletes (~1.9s,
  each doing a drained `incremental_vacuum`) and UT-032's 2 000 real fsynced writes (~8s) — both required
  by the canonical `_tests.md` definitions to exercise the real write path, unlike IT-009 which the spec
  explicitly permits to bulk-seed.

## Verification done

- `tests/test_crescimento.py`: UT-030, UT-031, UT-032, IT-009 — all pass, re-run 3x clean (once via
  `make test`, twice standalone) with stable margins (post-delete size ~0.12% of peak vs 25% threshold;
  UT-032 total ~4.0 MiB vs 8 MiB threshold).
- `make test`: 52/52 (51 pass + 1 expected skip for `KVSTORE_SLOW_TESTS`), ~17s, no task_01/task_02 case
  changed (`test_ut005`/`test_ut006` in `tests/test_store.py`, the delete-behavior dependents, still pass
  unchanged).
- `_dx.md` not touched; no new CLI verb, flag, or exception type added.

## Status

Completed. This was the last task in the `kvstore` graph (`task_01` → `task_02` → `task_03`).
