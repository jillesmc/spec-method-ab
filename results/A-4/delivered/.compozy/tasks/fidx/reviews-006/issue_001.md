---
round: 6
round_created_at: 2026-09-21T02:48:37.078652316Z
status: pending
file: tests/test_store.py
line: 142
severity: medium
author: unknown
---

# Issue 001: Test suite leaks sqlite3.Connection objects, causing misattributed ResourceWarning noise in `make test`

## Review Comment

Reproduced directly: `make test` (the exact command `_spec.md`'s constraints require to pass) currently prints 5 `ResourceWarning: unclosed database` lines during a normal run, all attached to `tests.test_store.TestAbrir.test_falha_ao_criar_indice_fecha_a_conexao_antes_de_repropagar` — a test that exists specifically to prove `_criar()` doesn't leak a connection on failure. Using `python3 -W error::ResourceWarning -m unittest tests.test_store -v`, the real source is `TestTransacao.test_context_manager_desfaz_ao_sair_com_excecao` (and its sibling `test_context_manager_commita_ao_sair_sem_excecao`), whose `idx`/`idx2` `Indice` objects (tests/test_store.py:216,219,225,234) are never closed; the ResourceWarnings only fire later when Python's GC happens to collect them, landing on whatever test is running at that moment. The same pattern also exists in `tests/test_store.py:142` (`TestGravarRemoverBuscar.setUp`, shared by 9 test methods), `tests/test_store.py:244/250`, and `tests/test_index.py:160,186,204,223`. This is exactly the class of bug reviews-002/issue_002 and reviews-004/issue_001 fixed in production code — but the test suite itself reintroduces it. Fix: close every `Indice` obtained via `Indice.abrir(...)` in tests.

## Triage

- Decision: `UNREVIEWED`
- Notes:
