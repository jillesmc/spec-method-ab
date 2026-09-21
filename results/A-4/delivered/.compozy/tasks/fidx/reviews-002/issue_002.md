---
round: 2
round_created_at: 2026-09-21T02:21:13.318130226Z
status: resolved
file: fidx/store.py
line: 99
severity: medium
author: unknown
---

# Issue 002: `Indice`'s sqlite3 connections are never explicitly closed

## Review Comment

`fidx/store.py`'s `Indice` class has no `close()` method, and its `__exit__` (lines 99-103) only issues `COMMIT`/`ROLLBACK` — it never closes `self._conexao`. Neither call site closes the connection either: `indexar()` (`fidx/__main__.py:13`) uses `with Indice.abrir(...) as idx:` which relies on `__exit__` alone, and `buscar()` (`fidx/__main__.py:41`) calls `Indice.abrir(raiz, criar=False)` and never closes the returned object at all.

This is observable, not theoretical: running `make test` currently prints `ResourceWarning: unclosed database in <sqlite3.Connection object at 0x...>` during `IT-013` (`tests/test_index.py::test_indexacao_interrompida_nao_deixa_indice_pela_metade`), because the exception frame captured by `assertRaises` keeps the connection object alive past its scope, so CPython's refcounting doesn't reclaim the file descriptor promptly.

There's also a structural leak on the error path in `Indice.abrir` (`fidx/store.py:19-30`): the raw `conexao` opened at line 25 is only closed at line 27 *if* `_ler_schema_version` returns a value other than `SCHEMA_VERSION`. If `_ler_schema_version` raises (e.g. `sqlite3.DatabaseError` for a corrupted file, as in the finding above), the exception propagates from inside the `if` condition before `conexao.close()` on line 27 is ever reached, leaking that connection unconditionally.

For a per-invocation CLI subprocess this is low real-world impact (the OS reclaims descriptors at process exit), but it is a genuine resource-management gap that would bite any caller that imports `fidx` as a library and calls `indexar()`/`buscar()` repeatedly in a long-lived process, and it already produces observable warnings in the test suite today. Fix: give `Indice` a `close()`, call it from `__exit__` after commit/rollback, wrap the exception path in `abrir()` (e.g. `try/except` around the schema-version check that closes `conexao` before re-raising), and have `buscar()` close the connection after querying.

## Triage

- Decision: VALID
- Root cause: `Indice` never exposed a way to release its `sqlite3.Connection`. `__exit__`
  only ran `COMMIT`/`ROLLBACK` for the `BEGIN IMMEDIATE` transaction it opened in
  `__enter__`; it never owned the connection's lifetime. Separately, `Indice.abrir()`'s
  existing-file branch only closed the just-opened `conexao` when `_ler_schema_version`
  returned a mismatched (non-raising) version string — if that call raised instead (e.g.
  `sqlite3.DatabaseError` for a corrupted file, which `_ler_schema_version` does not catch
  since it only catches `sqlite3.OperationalError`), the exception propagated straight out
  of `abrir()` before `conexao.close()` on the old line 27 was ever reached.
- Fix implemented in `fidx/store.py`:
  - Added `Indice.close()`, which closes `self._conexao`.
  - Wrapped the `_ler_schema_version(conexao)` call in `abrir()` in `try/except Exception:
    conexao.close(); raise`, so any exception from reading the schema version closes the
    connection before propagating instead of leaking it.
  - Left `__enter__`/`__exit__` unchanged (transaction BEGIN/COMMIT/ROLLBACK only). Making
    `__exit__` also call `close()`, as the review comment's suggested fix literally proposes,
    would break the tested contract that a single `Indice` can be re-entered as a context
    manager across multiple transactions — see
    `tests/test_store.py::TestTransacao::test_context_manager_desfaz_ao_sair_com_excecao` and
    `test_indice_em_uso_por_segunda_conexao_levanta_indiceemuso_dentro_do_timeout`, both of
    which call `with idx:` twice on the same `Indice` instance and would start hitting
    `sqlite3.ProgrammingError: Cannot operate on a closed database.` on the second entry.
    Coupling connection lifetime to transaction lifetime is the wrong fix; `close()` as a
    separate, explicit lifecycle primitive is the correct one.
- Out-of-scope-file change (documented per workflow rule — batch scope names only
  `fidx/store.py`, but `store.py` alone cannot make any caller invoke `close()`):
  touched `fidx/__main__.py` minimally so the two call sites that actually own an `Indice`'s
  full lifetime release it:
  - `indexar()`: now does `idx = Indice.abrir(...)` then `try: with idx: ... finally:
    idx.close()`, so the connection closes deterministically whether or not the body raises
    (this is exactly the IT-013 `ResourceWarning: unclosed database` path from the review
    comment — the exception now propagates through a `finally` that closes the connection
    instead of relying on refcounting/GC).
  - `buscar()`: now does `idx = Indice.abrir(...)` then `try: return idx.buscar(...) finally:
    idx.close()`.
- Regression coverage added (coverage gap; no existing test exercised either behavior):
  - `tests/test_store.py::TestAbrir::test_falha_ao_ler_schema_version_fecha_a_conexao_antes_de_repropagar`
    — writes an invalid sqlite file so `_ler_schema_version` raises `sqlite3.DatabaseError`,
    asserts it still propagates, then asserts `gc.collect()` produces no "unclosed database"
    `ResourceWarning`.
  - `tests/test_store.py::TestClose::test_close_fecha_a_conexao_subjacente` — calls
    `close()` then asserts further queries raise `sqlite3.ProgrammingError`.
  - `tests/test_index.py::TestIndexar::test_indexar_e_buscar_fecham_a_conexao_mesmo_quando_indexar_e_interrompido`
    — reproduces the exact IT-013-style interrupted-indexing scenario plus a `buscar()` call,
    then asserts `gc.collect()` produces no "unclosed database" `ResourceWarning`, directly
    validating the symptom the review comment reported from `make test` output.
