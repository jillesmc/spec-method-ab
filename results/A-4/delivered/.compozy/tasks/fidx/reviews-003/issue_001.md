---
round: 3
round_created_at: 2026-09-21T02:30:44.32319255Z
status: resolved
file: fidx/store.py
line: 31
severity: high
author: unknown
---

# Issue 001: `Indice.abrir(criar=False)` (the `search` path) silently deletes and rebuilds the index on a schema_version mismatch, violating Safety Invariant 5

## Review Comment

`Indice.abrir()` (fidx/store.py:19-35) discards and recreates `.fidx.sqlite3` as an empty index whenever the stored `schema_version` differs from `SCHEMA_VERSION`, and it does this unconditionally — regardless of whether `criar=True` (the `index` path) or `criar=False` (the `search` path). Since `buscar()` in `fidx/__main__.py:43-49` calls `Indice.abrir(raiz, criar=False)`, a plain `search` invocation against a pre-existing, valid index written by a different fidx schema version will unlink that file and replace it with an empty one before running the query — a write performed by the one command the spec guarantees never writes.

Reproduced directly: build an index with `Indice.abrir(raiz, criar=True)`, write real content and a search term into it, then set `meta.schema_version` to a different value (simulating an index left by another fidx version, exactly the scenario `_spec.md`'s Known Risks / ADR-002 anticipates). Calling only `Indice.abrir(raiz, criar=False)` (the exact call `buscar()` makes for `search`) unlinks `.fidx.sqlite3` and returns a fresh empty index — `buscar({'orcamento'})` now returns `[]` and `digests()` returns `{}`, even though a valid populated index existed seconds before and no `index` command was ever run.

`_spec.md`'s Safety Invariants section states explicitly: '5. `search` nunca escreve no índice... 6. Nenhum arquivo... é aberto para escrita em nenhum dos dois comandos; o único arquivo gravado é `<raiz>/.fidx.sqlite3`' — 'nunca escreve' is violated here in the most destructive way possible (unlink + recreate), and the operator/cron sees only a silently empty result set with no error, no exit-code signal, and permanent loss of the previous index content.

No test exercises `Indice.abrir(raiz, criar=False)` with a mismatched schema_version (`tests/test_store.py::TestAbrir::test_schema_version_divergente_reconstroi_sem_excecao` only covers `criar=True`), so this gap passed both prior review rounds and the full `make test` suite (60/60 green) undetected.

Fix: `abrir()` should only discard-and-recreate on schema mismatch when `criar=True`; when `criar=False` (search), a mismatched schema should raise (e.g. treat it like the file being absent — `FileNotFoundError`, prompting the operator to run `index`) rather than destroying existing state.

## Triage

- Decision: `VALID`
- Notes: Confirmed by reading `fidx/store.py:19-35`: `Indice.abrir()` unlinked and rebuilt `.fidx.sqlite3`
  on any `schema_version` mismatch regardless of `criar`, so the `search` path (`criar=False`, called from
  `fidx/__main__.py:45`) destroyed a valid pre-existing index instead of raising, violating Safety
  Invariant 5/6 in `_spec.md`. Fixed in `fidx/store.py`: when `criar=False` and the schema version
  mismatches, the connection is closed and `FileNotFoundError(str(caminho))` is raised without touching
  the file, reusing the same "índice não encontrado; rode index" handling `__main__.buscar()` already has
  for the absent-file case. The `criar=True` (index) path is unchanged: it still discards and rebuilds on
  mismatch. Added regression test
  `tests/test_store.py::TestAbrir::test_schema_version_divergente_sem_criar_levanta_e_preserva_indice`,
  which builds a populated index, corrupts its `schema_version`, calls `Indice.abrir(raiz, criar=False)`,
  asserts it raises `FileNotFoundError`, and then verifies the on-disk file and its `arquivos` rows are
  untouched. Full suite verified via `make test` (61/61 passed, was 60).
