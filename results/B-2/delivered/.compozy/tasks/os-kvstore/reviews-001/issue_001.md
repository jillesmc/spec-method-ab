---
round: 1
round_created_at: 2026-09-20T22:48:28.847961567Z
status: resolved
file: unknown
severity: medium
author: unknown
---

# Issue 001: Spec scenario "Interrupção durante manutenção preserva o estado" has no dedicated test

## Review Comment

`openspec/changes/kvstore/specs/kvstore/storage/spec.md` (Requirement "Nenhuma operação normal destrói o estado acumulado") explicitly requires: "WHEN o processo é morto em qualquer instante durante a reorganização interna do arquivo (compactação) THEN um processo novo lê exatamente o mesmo conjunto de chaves e valores confirmados que existia antes da interrupção." `kvstore.delete()` (kvstore/__init__.py:122-143) is the only operation that performs this reorganization, via `PRAGMA wal_checkpoint(TRUNCATE)` + `PRAGMA incremental_vacuum` after the row DELETE. `tests/test_falha_abrupta.py` only kills subprocesses during `set`, or after a `delete` has fully returned (i.e. after checkpoint+vacuum already completed) — no test kills the process while `delete()` is inside the checkpoint/vacuum window. I manually stress-tested this path (30 trials, SIGKILL at increasing delays inside a `delete` targeting a store with 50 other keys) and did not reproduce corruption, so the implementation appears sound — but the explicit spec scenario for the compaction-interruption case is currently unverified by the repository's own test suite.

## Triage

- Decision: `VALID`
- Notes: Confirmed the coverage gap. `kvstore.delete()` (kvstore/__init__.py:122-143) is the only
  operation that runs the compaction (`wal_checkpoint(TRUNCATE)` + `incremental_vacuum`) that
  storage/spec.md's "Interrupção durante manutenção preserva o estado" scenario targets, and
  `tests/test_falha_abrupta.py` had no test that lands a `SIGKILL` inside that specific window — the
  existing kill-during-write tests (4.4/4.5) only exercise `set`, and the confirmed-then-kill test for
  `del` (4.3) kills only after `delete()` fully returns, i.e. after the compaction already finished.
  Root cause: no synchronization point existed for "compaction has started" — a fixed-delay kill (like
  4.4's) can't reliably land inside a fast checkpoint/vacuum window.
  Fix: instrumented `tests/_sigkill_worker.py` (test-only) to emit a `compactando` line the instant
  `delete()`'s `wal_checkpoint` pragma starts running, by swapping `sqlite3.connect` for a version using
  a `_ConexaoInstrumentada` factory (opt-in via `KVSTORE_TEST_SINALIZAR_INICIO_DA_COMPACTACAO=1`, so the
  existing 4.1/4.3 tests are unaffected). Added
  `TestInterrupcaoDuranteCompactacaoPreservaEstado.test_kill_durante_compactacao_do_delete_preserva_as_demais_chaves`
  in `tests/test_falha_abrupta.py`, which builds a 20-key store with large values (so the vacuum has
  real work and a real time window), deletes one key while sweeping SIGKILL delays from the moment
  compaction starts, and asserts via a fresh connection/CLI subprocess that the deleted key stays
  absent and every other key/value survives intact. Verified stable across repeated runs (no flakes in
  4 consecutive full runs) and green together with the full suite (42/42 via `make test`, up from
  40/40 before this batch — the other new test is issue 002's).
