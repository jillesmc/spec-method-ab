---
round: 1
round_created_at: 2026-09-20T20:27:41.835375372Z
status: resolved
file: fidx/core.py
line: 195
severity: high
author: unknown
---

# Issue 001: Transient read failure on an already-indexed file silently deletes it from the search index

## Review Comment

index_dir() (fidx/core.py, the for-loop starting at line 189) treats any OSError raised while reading a file (permission denied, transient unreadability, race during access, etc.) as if the file no longer exists on disk: the `except OSError` handler at line 195-198 calls `continue` before `vistos.add(rel)` (line 202), so the file is excluded from `vistos` and gets swept up by `remove_missing()` — purged from `files`/`postings` and counted as `removido` — even though the file is still present on disk.

Reproduced live:
```
primeira rodada: (1, 1, 0)
search antes: ['segredo.md']
segunda rodada (arquivo perdeu permissao): (0, 0, 1)
avisos: [('segredo.md', 'Permission denied')]
search depois (arquivo ainda existe no disco!): []
```
After chmod 0 on an already-indexed file and a second `index_dir` round, the file is reported `removido` and disappears from `search`, even though it never left the folder. Restoring the file's permissions afterward does not restore its searchability — it silently stays gone until fully re-indexed.

This contradicts `_dx.md`'s own definition of the summary counters (`<removidos> — caminhos que estavam no indice e nao existem mais no disco`) and Business Rule 7 in `_spec.md` ("Arquivo ilegivel ... nao derruba a rodada: e pulado, avisado em stderr" — skipped, not deleted from the index). For the stated use case (unattended cron indexing of an operator's notes folder), this is a real, silent data-loss path: any transient permission glitch, lock, or read hiccup on a single file quietly erases it from search results while the round still reports exit 0 and only a warning line.

No existing test catches this: `tests/test_operacao.py` UT-032/UT-033 only cover files that are new in the same round (never previously indexed), not a previously-indexed file that becomes unreadable in a later round. `make test` is green because this exact scenario is untested.

Suggested fix direction: track "seen on disk during this walk" separately from "successfully processed"; a file that iter_files found but failed to read should count toward `vistos` (so it is not treated as removed) even though it isn't reindexed.

## Triage

- Decision: `valid`
- Notes: Reproduced exactly as described. `index_dir` (fidx/core.py) added `rel` to
  `vistos` only on the success path, so any `OSError` while hashing/reading an
  already-indexed file caused `remove_missing()` to purge it, even though the file
  was still on disk. Root-caused: the except handler never distinguished "seen on
  disk but unreadable this round" from "genuinely gone".

  Fix (fidx/core.py, `index_dir`): in the `except OSError` handler, add `rel` to
  `vistos` when `rel in conhecidos` (i.e. it was already in the index) so it
  survives `remove_missing()` and keeps its previous digest/postings until it can
  be read again. A brand-new, never-indexed file that fails to read is still
  correctly excluded from `vistos` (nothing to preserve, matches UT-032/UT-033
  semantics for `total_no_indice`).

  Regression test added: `tests/test_operacao.py::TestTolerancia::test_arquivo_ja_indexado_fica_ilegivel_nao_e_removido`
  — indexes a file, revokes read permission, re-indexes, and asserts the file is
  neither reported `removido` nor dropped from `search()`. Full suite (`make test`,
  54 tests) passes, including the pre-existing UT-032/UT-033 that exercise the
  never-indexed-and-unreadable case.
