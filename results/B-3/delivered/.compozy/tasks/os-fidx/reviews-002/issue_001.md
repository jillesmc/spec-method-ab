---
round: 2
round_created_at: 2026-09-20T19:46:20.557870761Z
status: resolved
file: fidx/__init__.py
line: 52
severity: minor
author: reviewer
---

# Issue 001: Unhandled PermissionError crashes index with raw traceback instead of clean stderr message

## Review Comment

When the target directory (or its .fidx subdir) is not writable, os.makedirs in _conectar (fidx/__init__.py:52) raises PermissionError, which propagates uncaught through fidx.index() and fidx/__main__.py:main() (whose except clause only covers ValueError, FileNotFoundError, sqlite3.OperationalError), producing a raw Python traceback instead of the clean stderr message design.md's Risks section explicitly promises ('falha com mensagem clara dizendo onde ele queria escrever'). Reproduced directly: `chmod 555 <dir>` then `python -m fidx <dir> index` prints a full traceback and exits with code 1 instead of a clear stderr message with exit code 2.

## Triage

- Decision: `VALID`
- Reproduced: `tmp=$(mktemp -d) && chmod 555 "$tmp" && python -m fidx "$tmp" index` printed a full
  `PermissionError` traceback from `os.makedirs` in `_conectar` (fidx/__init__.py:52) and exited 1,
  confirming the report. `design.md`'s Risks section explicitly promises "falha com mensagem clara
  dizendo onde ele queria escrever" for a read-only target folder.
- Root cause: `_conectar` let `os.makedirs`'s `PermissionError` propagate uncaught, and
  `fidx/__main__.py:main()`'s except clause only covered `ValueError`, `FileNotFoundError`, and
  `sqlite3.OperationalError` — `PermissionError` fell through to an unhandled traceback.
- Fix: `_conectar` now catches `PermissionError` around `os.makedirs` and re-raises it with a message
  naming the exact path it tried to create (`fidx/__init__.py:50-55`); `main()`'s except clause now
  also catches `PermissionError`, printing the clean message to stderr and exiting 2
  (`fidx/__main__.py:41`), consistent with the other clear-error paths (missing dir, locked db).
- Verification: manually reproduced before and after the fix (before: traceback + exit 1; after:
  `fidx: sem permissao para escrever em '<dir>/.fidx': ...` + exit 2, no traceback). Added
  `tests/test_cli.py::TestPastaSomenteLeitura::test_pasta_somente_leitura_sai_2_sem_stacktrace`
  covering the read-only-directory path, following the existing `TestBancoTravado` pattern. Full
  suite: `python -m unittest discover -s tests` — 26 tests, all pass.
