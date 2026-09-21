---
round: 4
round_created_at: 2026-09-21T02:35:06.038558695Z
status: resolved
file: fidx/store.py
line: 40
severity: medium
author: unknown
---

# Issue 001: Indice._criar() leaks the sqlite3.Connection if any setup statement after connect() fails

## Review Comment

`_criar()` (fidx/store.py:39-53) calls `sqlite3.connect(caminho, ...)` and then five more `conexao.execute(...)` statements (PRAGMA journal_mode=WAL, three CREATE TABLE/INDEX statements, and the schema_version INSERT) before returning `cls(conexao)`. None of those five statements is wrapped in a try/except, so if any of them raises (e.g. `sqlite3.OperationalError: database or disk is full`, or the directory losing write permission in the brief window after the file was created), the exception propagates out of `_criar()` and the already-open `conexao` is never closed.

This is reachable from both call sites of `_criar()`: (1) `abrir(raiz, criar=True)` on a directory with no existing index (fidx/store.py:24), and (2) the schema-version-mismatch rebuild path (fidx/store.py:33-36), which is exactly the code path round 3 just hardened for the `criar=False`/search case. `indexar()` in fidx/__main__.py only closes `idx` in a `finally` after `Indice.abrir(...)` has already returned successfully, so a connection leaked inside `_criar()` is never reached by that cleanup.

Reproduced directly: wrapped `sqlite3.connect` so the second `execute()` call (the `CREATE TABLE meta` statement) raises `sqlite3.OperationalError('simulated disk full')`. `Indice.abrir(raiz, criar=True)` raised as expected, but the underlying connection's `close()` was never invoked. This is the same class of bug fixed in reviews-002/issue_002 (which added `Indice.close()` and wrapped the *existing-file* schema-read failure path in `abrir()` with `try/except Exception: conexao.close(); raise`) — but that fix did not cover the `_criar()` internal path.

Fix: wrap the body of `_criar()` in the same `try/except Exception: conexao.close(); raise` pattern already used in `abrir()`'s existing-file branch.

## Triage

- Decision: `VALID`
- Notes: Confirmed by inspection and reproduction. `_criar()` (fidx/store.py:40-58 before fix) opened
  the connection and then called five more `conexao.execute(...)` statements with no exception
  handling, unlike the sibling `abrir()` existing-file branch, which already wraps
  `_ler_schema_version` in `try/except Exception: conexao.close(); raise` (fixed under
  reviews-002/issue_002). Reproduced with a `sqlite3.Connection` subclass whose `execute()` raises
  `OperationalError` on the second call (mirroring the `CREATE TABLE meta` step): before the fix the
  connection stayed open after `Indice.abrir(raiz, criar=True)` propagated the exception; after the fix
  the connection is closed before re-raising.
  Root cause: the setup body in `_criar()` was written without the same close-then-raise guard used
  elsewhere in the module.
  Fix: wrapped the five `conexao.execute(...)` calls in `_criar()` in
  `try: ... except Exception: conexao.close(); raise`, matching the existing pattern in `abrir()`.
  Regression coverage: added `TestAbrir.test_falha_ao_criar_indice_fecha_a_conexao_antes_de_repropagar`
  in tests/test_store.py, which forces a failure on the second `execute()` call inside `_criar()` and
  asserts the connection was closed (via `sqlite3.ProgrammingError` on further use) instead of leaked.
  Verification: `make test` (62 tests) passes, including the new test and the full existing suite.
