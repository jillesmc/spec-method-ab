# Workflow memory: fidx

Shared, durable context for the `fidx` task graph. Task-local decisions live in each `task_NN.md` memory
file; only promote something here if task_02/03/04 need to know it too.

- `fidx/store.py` (task_01) is done. Its `Indice` context-manager pattern (`with Indice.abrir(raiz,
  criar=True) as idx:` for writes; plain `Indice.abrir(raiz, criar=False)` + `.buscar()` for reads, no
  `with`) is the contract `fidx/__main__.py` (task_03) must follow — see `task_01.md` memory for why.
- `sqlite3` CLI binary is not installed on this machine. Verify `.fidx.sqlite3` externally via a fresh
  `sqlite3.connect(...)` in Python, not the shell `sqlite3` command, when a task's Success Criteria asks
  for external inspectability.
- No `AGENTS.md`/`CLAUDE.md` exists inside this repo (`<bench>/resultados/A-4/repo`); only the task files, `_spec.md`, `adrs/`, and `_tests.md` are the source of truth.
- `fidx/scan.py` (task_02) is done: `percorrer`, `ler`, `tokenizar` — leaf module, imports nothing from
  `fidx.store`, only stdlib. `tokenizar` is the **single** function task_03 must call for both indexing
  file content and tokenizing the search query — do not write a second one. See `task_02.md` memory for
  the cyclic-symlink and single-read implementation notes.
- `fidx/__main__.py` (task_03) is done: `indexar(raiz)` and `buscar(raiz, termo)` are the two functions
  that do the real work, callable without going through the CLI; `main(argv)` only wires `argparse` to
  them and prints. **Happy path only** — no directory validation, no exit codes 1/2, no exception
  translation; `main()` always returns 0 today. task_04 owns adding all of that directly in
  `fidx/__main__.py` (not in `store`/`scan`). See `task_03.md` memory for the exact seams (which branches
  of `main()` to touch) and the ignored-file-also-counts-as-removed subtlety (IT-009).
- **All four fidx tasks are done** (task_01–task_04). `fidx/__main__.py`'s `main()` now has the full error
  contract from `_dx.md`: directory validation, exit codes 0/1/2, and exception translation
  (`IndiceEmUso`, `FileNotFoundError`, permission errors) — all hardcoded message literals, not derived
  from `str(exc)` (see `task_04.md` memory for why the permission-denied text can't be `str(exc)`-based).
  `make test` is 55/55 green.
