---
round: 1
round_created_at: 2026-09-21T02:13:40.860290826Z
status: resolved
file: tests/test_store.py
line: 10
severity: low
author: unknown
---

# Issue 002: test_store.py does not follow the stated test-naming convention

## Review Comment

`_tests.md`'s Strategy section requires: 'nome do método descrevendo o comportamento, não o número do caso; o ID do caso no docstring'. `tests/test_scan.py` and `tests/test_index.py` both comply (behavior-named methods, case ID in a `"""UT-00x"""` docstring). `tests/test_store.py` does the opposite for all 12 of its cases: method names embed the case number directly (`test_ut020_cria_indice_vazio`, `test_ut031_indice_em_uso_dentro_do_timeout`, etc.) and none of them have a docstring with the case ID.

## Triage

- Decision: `VALID`
- Notes: Confirmed against `.compozy/tasks/fidx/_tests.md` Strategy section and against the sibling
  files `tests/test_scan.py` / `tests/test_index.py`, which both name methods by behavior and carry the
  case ID (`UT-00x`/`IT-00x`) as a docstring. `tests/test_store.py` had 13 methods named
  `test_ut0NN_...` with no case-ID docstring (`test_ut020_...`, `test_ut021_...`, `test_ut028_...`,
  `test_ut022_...`, `test_ut023_...`, `test_ut024_...`, `test_ut025_...`, `test_ut026_...`,
  `test_ut027_...`, `test_ut029_...`, `test_ut030_...`, `test_ut032_...`, `test_ut031_...`). Renamed all
  of them to behavior-describing names and moved the corresponding `UT-0NN` ID from `_tests.md`'s Unit
  Tests section for `fidx/store.py` into a one-line docstring, matching the convention already used by
  `test_scan.py`/`test_index.py`. The two `TestTransacao` context-manager tests
  (`test_context_manager_commita_ao_sair_sem_excecao`,
  `test_context_manager_desfaz_ao_sair_com_excecao`) were already behavior-named and are not assigned a
  case ID in `_tests.md`, so they were left untouched — out of scope for this finding.
