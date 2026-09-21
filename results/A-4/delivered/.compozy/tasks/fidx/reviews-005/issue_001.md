---
round: 5
round_created_at: 2026-09-21T02:41:27.91077606Z
status: resolved
file: fidx/__main__.py
line: 92
severity: medium
author: unknown
---

# Issue 001: index's permission-denied stderr message never matches _dx.md's documented literal

## Review Comment

_dx.md's Errors table requires exactly `fidx: nao foi possivel gravar o indice em ./notas: Permission denied` (exit 2) for 'Pasta sem permissão de escrita (no index)'. Reproduced directly on this machine: chmod 0o555 a directory with no existing .fidx.sqlite3, then run `python -m fidx <dir> index` → stderr is `fidx: nao foi possivel gravar o indice em <dir>: unable to open database file`, returncode 2. The real failure surfaces as sqlite3.OperationalError('unable to open database file'), not Python's PermissionError, so it falls into fidx/__main__.py's `except sqlite3.Error as exc: print(f'...: {exc}')` clause (lines 92-97) instead of the `except OSError` clause (lines 85-91) that hardcodes the 'Permission denied' literal — that OSError/PermissionError branch is effectively unreachable for this exact documented scenario. Failure scenario: operator or cron runs `python -m fidx <dir> index` against a directory whose write permission was revoked before any .fidx.sqlite3 exists; instead of the contractual 'Permission denied' text, the raw sqlite message leaks, breaking any downstream tooling that pattern-matches on the documented literal. This is a known, previously-traded-off gap: reviews-001/issue_001.md's own triage notes state 'the fix cannot rely on catching PermissionError alone to cover the documented permission case' — round 1 deliberately gave up exact _dx.md text compliance here to stop mislabeling corrupted/disk-full errors as 'Permission denied', but that trade-off was never filed as its own issue or reflected in _dx.md as an accepted deviation. Compounding this, .compozy/tasks/fidx/memory/task_04.md still documents the opposite design ('main() hardcodes that suffix... regardless, so don't switch to str(exc)'), which is now stale and contradicts the shipped code. No test catches the gap: IT-017 (tests/test_index.py) only asserts indexar() raises (sqlite3.OperationalError, PermissionError), never exercising main()'s CLI-level message translation, and it's skipped under root anyway.

## Triage

- Decision: `VALID`
- Notes:
  - Reproduced exactly as described: `chmod 0o555` on a directory with no existing
    `.fidx.sqlite3`, then `python -m fidx <dir> index` raised `sqlite3.OperationalError:
    unable to open database file`, not `PermissionError`. Before the fix this landed in
    `main()`'s `except sqlite3.Error` clause (added in reviews-001/issue_001's fix) and printed
    the raw sqlite message instead of `_dx.md`'s contractual `Permission denied` literal —
    confirmed the `except OSError` branch's `isinstance(exc, PermissionError)` special-case was
    unreachable for this exact scenario.
  - Root cause: the CLI tried to infer "was this a permissions problem?" from the *type* of the
    exception sqlite raised, but sqlite wraps a permission-denied `open()` failure in the same
    `sqlite3.OperationalError` type (and can share overlapping message text) as other conditions
    round 1 deliberately routed to `str(exc)` (corrupted db, disk full). No exception-type or
    message-substring split can separate "directory not writable" from those other cases without
    re-introducing round 1's mislabeling bug — string/type matching on sqlite's opaque error is
    inherently the wrong signal here.
  - Fix: check the real, authoritative signal directly — `os.access(raiz, os.W_OK)` — before
    attempting to create/write the index, and short-circuit with the documented `Permission
    denied` message and exit 2 when the directory isn't writable. This is orthogonal to the
    round-1 fix: it never inspects `str(exc)` or exception subtypes, so corrupted-db and
    disk-full failures still fall through unchanged to `except sqlite3.Error` and report the
    real message. The pre-existing `except OSError` branch's `PermissionError` special case is
    left in place as a fallback for platforms/filesystems where `os.access` doesn't reflect the
    actual write outcome.
  - Scope note: `_dx.md`'s row is specifically "Pasta sem permissão de escrita" (the *folder*
    lacks write permission), which is exactly what `os.access(raiz, os.W_OK)` tests — not an
    existing-but-read-only `.fidx.sqlite3` file inside a writable folder, which is a different,
    undocumented condition and out of scope for this fix.
  - `.compozy/tasks/fidx/memory/task_04.md`'s claim that "main() hardcodes that suffix... don't
    switch to str(exc)" is now stale for the sqlite3.Error branch (superseded by reviews-001's
    fix) and this change doesn't touch that branch further; flagged here for the record per the
    issue's own note, left unedited as it's outside this batch's code scope (`fidx/__main__.py`
    only).
  - Regression coverage: added
    `tests/test_cli.py::TestCLI::test_pasta_sem_permissao_de_escrita_reporta_permission_denied`,
    which reproduces the exact issue scenario (chmod 0o555, no pre-existing index, real
    subprocess invocation) and asserts the literal stderr text and exit code 2 from `_dx.md`.
    Skipped under root, matching `IT-017`'s existing precedent (`chmod` doesn't restrict root).
    Existing `IT-017` continues to pass unchanged (it only asserts on exception type at the
    `indexar()` level, not the CLI's message).
