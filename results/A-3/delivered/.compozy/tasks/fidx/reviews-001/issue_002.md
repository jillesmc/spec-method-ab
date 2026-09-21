---
round: 1
round_created_at: 2026-09-20T20:27:41.835375372Z
status: resolved
file: fidx/core.py
line: 137
severity: medium
author: unknown
---

# Issue 002: search() does not enforce the documented schema_version contract

## Review Comment

`_spec.md` § Data Models states explicitly: "meta.schema_version divergente de SCHEMA_VERSION → index derruba e recria as tabelas e reindexa tudo; search levanta IndexMissing com a instrucao de rodar index." The `index_dir` path implements this (via `_ensure_schema`), but `open_index(root, create=False)` — the path `search()` uses (fidx/core.py lines 137-145) — never inspects `schema_version` at all. It only checks that the `meta` table query doesn't throw (i.e., that the file exists and has *some* schema), then proceeds to read from `files`/`postings` regardless of version.

Reproduced live: after indexing a folder normally, then directly setting `meta.schema_version = '0'` via a separate sqlite3 connection (simulating an index left behind by an older/incompatible fidx version) and calling `core.search(tmp, "orcamento")` directly, it returns `['a.md']` with no exception — instead of raising `IndexMissing` as the spec requires.

Currently low-impact because `SCHEMA_VERSION` has only ever been `1` in this codebase, so there's no real incompatible schema in the wild yet — but it is an explicit, testable contract in the technical spec that the implementation silently doesn't honor, and no test in `_tests.md`/`tests/test_incremental.py` exercises `search` against a schema-mismatched index (IT-005 only exercises `index_dir`, not `search`). This should either be implemented (schema check in the read-only open path) or the spec's Data Models section corrected to reflect that only `index` reacts to schema drift.

## Triage

- Decision: `valid`
- Notes: Confirmed `open_index(root, create=False)` (the path `search()` uses) only
  probed that the `meta` query didn't throw, never comparing `schema_version`
  against `SCHEMA_VERSION`. Reproduced the spec violation live: index normally,
  set `meta.schema_version = '0'` via a raw sqlite3 connection, then `search()`
  returned matches instead of raising `IndexMissing`.

  Fix (fidx/core.py, `open_index`): in the `create=False` branch, fetch the
  `schema_version` row and raise `IndexMissing(path)` when it is missing or does
  not equal `str(SCHEMA_VERSION)`, mirroring the write path's contract
  ("`meta.schema_version` divergente ... search levanta IndexMissing").

  Regression test added:
  `tests/test_incremental.py::TestIntegracaoIncremental::test_search_esquema_divergente_levanta_indexmissing`
  — indexes a folder, rewrites `schema_version` to `'0'` directly in the sqlite
  file, and asserts `core.search` now raises `IndexMissing`. Full suite
  (`make test`, 54 tests) passes, including `test_it005_esquema_antigo_recria`
  which exercises the same drift on the `index_dir` path.
