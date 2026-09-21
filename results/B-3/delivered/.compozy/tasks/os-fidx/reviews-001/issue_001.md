---
round: 1
round_created_at: 2026-09-20T19:40:36.127219339Z
status: resolved
file: fidx/__init__.py
line: 80
severity: blocking
author: unknown
---

# Issue 001: Text file that becomes undecodable leaves permanently stale, phantom search results

## Review Comment

In fidx/__init__.py:74-81, index() compares the freshly computed sha256 digest against existentes.get(caminho) to decide staleness, then on UnicodeDecodeError does `continue` before updating `files.hash` or deleting the old `postings` rows for that path. If a file was previously indexed with valid UTF-8 content and is later overwritten with non-UTF-8 bytes (the exact rsync/checkout scenario the proposal.md motivates this feature with), the stored hash never gets updated, so every future index() run treats the file as changed, fails to decode it again, and drops it from all three Resumo counters (reprocessados/inalterados/removidos) — while its old postings from the prior text content remain in the index forever. search() will keep returning that file for terms that no longer exist in it, with no way to self-correct short of deleting .fidx entirely. Reproduced directly: after the transition, `fidx.search(tmp, 'termo_valioso')` still returns ['a.txt'] across 3 subsequent index() rounds, even though the file has contained only binary bytes since round 2. This violates the spec's 'Reprocessamento decidido pelo conteúdo' requirement (search must reflect current content) and the 'Resumo verificável' requirement (counts must reflect work actually done). No test in tests/test_indice_core.py covers this transition — TestIncrementalidade's binary-file test (2.6) only covers a file that was binary from the first round, never the case where a previously-indexed text file goes stale. Fix should delete the file's existing files/postings rows (or otherwise stop reporting it as indexed) when a previously-known path fails to decode, rather than silently leaving the stale entry in place.

## Triage

- Decision: `VALID`
- Notes: Confirmed by direct code read of `fidx/__init__.py:78-81` (pre-fix): on `UnicodeDecodeError`
  the loop did `continue` before touching `files`/`postings`, and the path was already added to `vistos`
  at the top of the loop body, so the post-loop `sumidos = existentes.keys() - vistos` purge never caught
  it either — the stale hash and stale postings were permanent once a previously-indexed text file turned
  undecodable.

  Fix (root cause, `fidx/__init__.py:80-85,100`): when decode fails for a `caminho` that is present in
  `existentes` (i.e. it was successfully indexed before), delete its `postings` and `files` rows
  immediately, same as the removed-file path does, and fold that count into the round's `removidos` via a
  new `ilegiveis` counter (`Resumo(reprocessados, inalterados, len(sumidos) + ilegiveis)`). A brand-new
  file that was binary from round one is still silently skipped and uncounted, preserving the existing
  "Arquivo binário não derruba a rodada" behavior/test.

  Regression test added: `tests/test_indice_core.py::TestIncrementalidade::test_arquivo_texto_vira_binario_sai_do_indice`.
  It indexes a text file, confirms it's searchable, overwrites it with invalid UTF-8 bytes, and asserts:
  the transition round reports `(0, 0, 1)` and `search` returns `[]`; the `files` row for that path is
  gone from the sqlite index; and two further rounds report `(0, 0, 0)` with `search` still returning
  `[]` (matching the uncounted-binary-file convention once the stale entry has been purged).

  Verification: `python3 -m unittest discover` — 25/25 tests pass (24 pre-existing + 1 new).
