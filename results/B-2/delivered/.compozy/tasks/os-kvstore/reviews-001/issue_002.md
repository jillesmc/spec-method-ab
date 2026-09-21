---
round: 1
round_created_at: 2026-09-20T22:48:28.847961567Z
status: resolved
file: unknown
severity: low
author: unknown
---

# Issue 002: Spec scenario "Corrupção real é reportada, não escondida" is untested

## Review Comment

`storage/spec.md` requires that real corruption (not an interrupted write) be reported as an explicit error rather than silently returning a partial/fake state, and `cli/spec.md` maps this to exit code 3 ("Corrupção detectada é erro de dados"). The `__main__.py` CLI does catch `(sqlite3.Error, OSError)` generically and returns exit 3 (kvstore/__main__.py:58-60), which functionally satisfies the contract, but no test in `tests/` actually corrupts a store file (e.g. truncating/overwriting `kvstore.sqlite3` with garbage bytes) and asserts the CLI reports exit 3 rather than silently returning an empty/wrong result. This is one of the scenarios explicitly called out in the storage spec delta and is not covered.

## Triage

- Decision: `VALID`
- Notes: Confirmed the coverage gap: `kvstore/__main__.py:58-60` already catches `(sqlite3.Error,
  OSError)` and returns exit 3 as `cli/spec.md` requires, but nothing in `tests/` actually corrupted a
  store file and asserted that behavior — only the permission-denied `OSError` path was covered
  (`test_falha_de_io_por_permissao_negada_sai_3`), not `sqlite3.DatabaseError` from real corruption.
  Fix: added `test_corrupcao_real_do_arquivo_sai_3_em_vez_de_esconder_o_erro` to
  `tests/test_cli.py::TestCodigosDeSaida`. It writes a valid key, overwrites the first 4 KiB of
  `kvstore.sqlite3` with `0xFF` bytes (real corruption, not an interrupted write), then asserts both
  `get` and `list` exit 3 with empty stdout and non-empty stderr — i.e. the CLI reports the corruption
  as a data error instead of silently returning an empty/wrong result. Verified green with the full
  suite.
