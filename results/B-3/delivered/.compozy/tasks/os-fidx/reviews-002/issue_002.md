---
round: 2
round_created_at: 2026-09-20T19:46:20.557870761Z
status: resolved
file: tests/test_indice_core.py
severity: minor
author: reviewer
---

# Issue 002: No test covers spec.md's 'Uma mudança entre rodadas' scenario with N>1 files

## Review Comment

spec.md requires that when exactly one of N indexed files changes between rounds, the summary reports 1 reprocessado and N-1 inalterados, but every content-change test in TestIncrementalidade (tests/test_indice_core.py) uses a single-file directory, so this multi-file interaction is never asserted by the suite. Manually verified the current implementation is correct (3 files indexed, one changed → 'reprocessados=1 inalterados=2 removidos=0'), but a future regression in the per-file counting logic when multiple files coexist in one round would not be caught by any existing test.

## Triage

- Decision: `VALID`
- Notes: Confirmed the gap — every content-change case in `TestIncrementalidade` used a single-file
  directory, so per-file counting across a multi-file round was untested. Added
  `test_uma_mudanca_entre_tres_arquivos_reprocessa_so_um` (3 files indexed, one changed) asserting
  `(1, 2, 0)`, matching the reviewer's manual verification. Test passes against the current
  implementation (`fidx/__init__.py:index`), confirming no regression.
