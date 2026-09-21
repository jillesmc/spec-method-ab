# task_02 — Os testes que sustentam a promessa de incrementalidade

## Implemented

- Added `TestIncrementalidade` to the existing `tests/test_indice_core.py` (no new test file —
  keeps the "one file, tests import `fidx` directly" pattern from task_01). Six tests, one per
  item 2.1-2.6:
  - `test_conteudo_mudou_com_data_antiga_reprocessa`: writes new content then rewinds `mtime` 30
    days into the past with `os.utime`; asserts `(1, 0, 0)`, new term found, old term gone.
  - `test_data_nova_sem_mudanca_de_conteudo_nao_reprocessa`: advances `mtime` 30 days forward with
    no content change; asserts `(0, 1, 0)`.
  - `test_pasta_inalterada_devolve_zero_reprocessados_e_busca_identica`: two rounds, no changes;
    asserts second `Resumo == (0, N, 0)` and search results identical before/after.
  - `test_arquivo_removido_sai_do_indice`: deletes one of two indexed files; asserts
    `(0, 1, 1)` and that a search for the deleted file's exclusive term returns `[]`.
  - `test_indice_nao_indexa_a_si_mesmo`: indexes twice, then queries `.fidx/index.sqlite3`
    directly (`SELECT path FROM files`) to assert the only row is the real file — no `.fidx/...`
    path ever entered `files`. Also asserts second round's `reprocessados == 0`.
  - `test_arquivo_binario_nao_interrompe_a_rodada`: one file with undecodable bytes plus one real
    text file; asserts `index()` doesn't raise, resumo is `(1, 0, 0)` (the binary file is counted
    in neither reprocessados nor inalterados — see below), and the text file is searchable.

## Non-obvious behavior verified, not changed

- A file that never decodes as UTF-8 (2.6 case) is **not counted anywhere** in `Resumo`: it's
  added to `vistos` (so it's never flagged "removido") but the `UnicodeDecodeError` `continue`
  happens before `reprocessados`/`inalterados` increment, and since it was never inserted into
  `files`, every future round re-hashes it and hits the same decode failure again. This matches
  design D5/D8's "aceito conscientemente" — didn't touch `fidx/__init__.py` to change this, since
  it's existing task_01 behavior and the spec only requires the round not to raise and other files
  to stay indexed, which it doesn't.
- Did not touch `fidx/__init__.py` at all — this task is test-only per its scope (tasks.md
  section 2 is entirely test items). File was already modified (uncommitted) by task_01 before
  this task started.

## Verification run

- `make test` (`python3 -m unittest discover -s tests -t . -v`) → 13 passed (7 pre-existing +
  6 new), exit 0.
- `openspec validate fidx --strict` → still **could not run**, `openspec` binary not present
  (`which openspec` → not found). Same blocker as recorded in shared memory from task_01; not a
  regression introduced here.
