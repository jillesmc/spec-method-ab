---
round: 1
round_created_at: 2026-09-21T02:13:40.860290826Z
status: resolved
file: fidx/__main__.py
line: 78
severity: medium
author: unknown
---

# Issue 001: index's generic error handler masks real failure causes with a hardcoded message

## Review Comment

fidx/__main__.py's `main()` catches `(OSError, sqlite3.Error)` for the `index` command and unconditionally prints `fidx: nao foi possivel gravar o indice em {dir}: Permission denied`, regardless of the actual exception. `_dx.md`'s error table maps that exact string only to the 'pasta sem permissao de escrita' condition (verified correct via IT-017/E2E via PermissionError). But any other `sqlite3.Error` — e.g. a truncated/corrupted `.fidx.sqlite3` raising `sqlite3.DatabaseError: file is not a database` (not caught by `_ler_schema_version`'s narrower `except sqlite3.OperationalError`), or `sqlite3.OperationalError: database or disk is full` — reaches this same clause and gets reported as 'Permission denied'. A cron operator reading the log would misdiagnose a disk-full or corrupted-index failure as a permissions problem.

## Triage

- Decision: `VALID`
- Notes:
  - Reproduced: writing garbage bytes to `.fidx.sqlite3` and running `index` raised
    `sqlite3.DatabaseError: file is not a database` (confirmed via manual `sqlite3.connect`/`execute`
    against a corrupted file — this is a `DatabaseError`, a sibling of `OperationalError`, so
    `Indice._ler_schema_version`'s `except sqlite3.OperationalError` does not catch it and it propagates
    to `main()`). Before the fix, `main()`'s `except (OSError, sqlite3.Error)` clause unconditionally
    printed `Permission denied` for this case, misdiagnosing a corrupted index as a permissions problem.
  - Root cause: the handler hardcoded the "Permission denied" detail text for every `OSError`/
    `sqlite3.Error`, instead of reporting the exception that actually occurred.
  - Also verified empirically that a real permission-denied directory (`chmod 0o555`, matching IT-017)
    raises `sqlite3.OperationalError: unable to open database file`, not `PermissionError` — so the fix
    cannot rely on catching `PermissionError` alone to cover the documented permission case; it must
    surface the real exception text for every case *except* genuine `PermissionError`, where `_dx.md`'s
    literal "Permission denied" wording is preserved.
  - Fix: split the except clause into `except OSError` (prints `Permission denied` only when the
    exception actually is a `PermissionError`, else the real `str(exc)`) and `except sqlite3.Error`
    (always prints the real `str(exc)`), in `fidx/__main__.py`'s `main()`.
  - Regression coverage: added
    `tests/test_cli.py::TestCLI::test_indice_corrompido_reporta_erro_real_em_vez_de_permission_denied`,
    which writes a corrupted `.fidx.sqlite3` and asserts stderr contains the real sqlite message and
    does not contain "Permission denied". Existing `IT-017`
    (`tests/test_index.py::test_pasta_sem_permissao_de_escrita_levanta_erro_de_gravacao`) continues to
    cover the permission-denied path at the `indexar()` level and is unaffected since it does not
    exercise `main()`'s CLI-level message formatting.
