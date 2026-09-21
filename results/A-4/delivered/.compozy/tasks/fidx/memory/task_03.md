# Task memory: task_03 (fidx/__main__.py)

Status: completed.

## What was built

- `fidx/__main__.py`: `indexar(raiz) -> dict[str, int]` (five counts: novos/alterados/removidos/
  inalterados/ignorados, callable without the CLI), `buscar(raiz, termo) -> list[str]`, `main(argv)` wiring
  `argparse` (`diretorio` positional + `index`/`search` subcommands) to both, and `_imprimir_resumo` for the
  `_dx.md` summary line.
- `tests/test_index.py`: IT-001–IT-012, IT-016 (one `unittest.TestCase`, one method per case, docstring
  carries the ID).
- `tests/test_cli.py`: E2E-001, E2E-006, E2E-007, E2E-008 via `subprocess.run([sys.executable, "-m",
  "fidx", ...])`.
- `.gitignore`: added `.fidx.sqlite3`. `README.md`: one line documenting the index file and that deleting
  it rebuilds from scratch.

## Decisions

- **Total count printed is derived, not stored**: `_dx.md`'s "`N` arquivos" is `novos + alterados +
  inalterados` (the final index size), computed only at print time in `_imprimir_resumo`. `indexar()` itself
  returns only the five contract counts, per the task's own wording ("devolve as cinco contagens") — don't
  add a sixth key to the returned dict later without checking task_04 doesn't rely on the current five-key
  shape.
- **Ignored files that were previously indexed count in both `ignorados` AND `removidos`** (IT-009): a file
  that becomes non-UTF-8 is never added to `vistos`, so the mirror rule (`espelho`, business rule 2) removes
  it from the index in the same pass it's counted as ignored. This isn't spelled out explicitly in the
  Requirements prose — it falls out of building `vistos` only from indexable files and diffing against
  `digests_antigos` at the end. Confirmed against IT-009's expected `removidos=1, ignorados=1`.
- **`digests_antigos` is a single snapshot taken once before the loop** (via `idx.digests()`), matching
  `_spec.md`'s System Architecture flow. New/changed comparisons all read from that frozen dict, never
  re-querying `idx` mid-loop — this is also what makes IT-002's "`gravar` not called at all on an
  unchanged second round" true without extra bookkeeping.
- **`buscar()` in `__main__.py` does not close the `Indice` connection** — `store.Indice` has no public
  `close()` method (by design, not an oversight; task_01 didn't add one) and reaching into `idx._conexao`
  would break encapsulation. This produces a `ResourceWarning: unclosed database` during test runs, same as
  the pre-existing one task_02 already flagged from `test_store.py` — not a regression, not fixed here
  (out of scope; would need a `store.py` API change).
- **No directory validation, no `sys.exit` with 1/2, no error translation** — deliberately deferred to
  task_04 per this task's own Requirements ("Nesta task basta o caminho feliz"). `main()` always returns 0
  today. Anyone touching `fidx/__main__.py` next (task_04) will replace the `return 0` branches with real
  exit-code logic and wrap `indexar`/`buscar` calls in exception translation — that's expected, not a bug
  to fix here.
- Called `scan.ler`/`scan.tokenizar` via the `scan` module object (`from fidx import scan`), not
  `from fidx.scan import ler`, so `unittest.mock.patch.object(scan, "ler", ...)` (task_04's IT-013
  interruption test) can intercept it.

## Verification run

- `python3 -m unittest discover -s tests -t . -v` → 47/47 ok (13 new in `test_index.py` + 4 new in
  `test_cli.py`, plus the 30 pre-existing from task_01/task_02).
- `make test` → same, green.
- `grep -n "mtime" fidx/__main__.py` → no matches (Success Criteria).
- Manually replayed the exact `_dx.md` Golden Path transcript in a scratch temp dir (via `subprocess`,
  cwd = repo root, `python -m fidx`): first `index` → `2 arquivos: 2 novos, 0 alterados, 0 removidos, 0
  inalterados, 0 ignorados`, `search orcamento` → both paths in order + exit 0, second `index` → `0 novos,
  0 alterados, 0 removidos, 2 inalterados` — matches format, order and counts exactly.

## For task_04

- `main()`'s two branches (`if args.comando == "index": ... return 0` / else search `return 0`) are the
  two places to inject exit codes 1 (empty search) and 2 (validation/translated exceptions). Directory
  validation and exception translation (`IndiceEmUso`, `FileNotFoundError` from `Indice.abrir(criar=False)`,
  permission errors) don't exist yet anywhere in `__main__.py` — add them there, not in `store`/`scan`.
- `indexar()`'s `with Indice.abrir(raiz, criar=True) as idx:` already gives one-transaction-per-run
  (Safety Invariants 1–3) for free from task_01's context manager; task_04 just needs to prove it (IT-013)
  and catch `IndiceEmUso` around the `with` (per task_01 memory: it's raised from `__enter__`, not `abrir()`).
