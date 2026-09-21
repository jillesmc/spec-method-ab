# Task memory: task_04 (fidx/__main__.py — contrato de erro)

Status: completed.

## What was built

- `fidx/__main__.py`: `main()` now validates `raiz.is_dir()` before dispatching to either subcommand,
  translates `IndiceEmUso` and `(OSError, sqlite3.Error)` around the `indexar()` call, translates
  `FileNotFoundError` around the `buscar()` call, and returns exit code 1 when `buscar()` comes back empty.
  `indexar()`/`buscar()` themselves are unchanged — no new exception handling inside them, per task_03's
  note that translation belongs only in `main()`.
- `tests/test_cli.py`: added E2E-002–E2E-005 (four new `TestCLI` methods).
- `tests/test_index.py`: added IT-013, IT-014, IT-015, IT-017 (four new `TestIndexar` methods), plus the
  new imports they need (`sqlite3`, `fidx.scan`, `fidx.store`, `IndiceEmUso`).

## Decisions

- **Error messages are fixed literals from `_dx.md`, not derived from `str(exc)`.** The permission-denied
  case is the one that matters: writing to a `0o555` directory actually raises
  `sqlite3.OperationalError('unable to open database file')`, not a message containing "Permission
  denied" — confirmed empirically. `_dx.md`'s table says the stderr text must be exactly
  `... : Permission denied` regardless, so `main()` hardcodes that suffix instead of interpolating the
  caught exception. Don't "fix" this later by switching to `str(exc)` — that would break the contract.
- **All error messages interpolate `args.diretorio` (the raw CLI string), not `str(raiz)`.** `Path("./x")`
  normalizes to `"x"` when stringified (`str(Path("./notas")) == "notas"`, confirmed empirically) which
  would silently drop the `./` prefix `_dx.md`'s examples show. Using the untouched argparse string keeps
  the message byte-for-byte reproducible regardless of how the caller spelled the path.
- **Directory validation runs once in `main()`, before branching on `comando`**, covering both `index` and
  `search` with one check (E2E-004 requires both). Placed before any call into `indexar`/`buscar`, so
  nothing touches disk when the path doesn't exist.
- **`search` does not catch `IndiceEmUso`.** `buscar()` calls `Indice.abrir(raiz, criar=False)` with no
  `with` block, so it never issues `BEGIN IMMEDIATE` and can't contend for the write lock — Safety
  Invariant 5 guarantees this structurally (task_01's design), so there's nothing for `main()`'s search
  branch to translate there.
- **No new code needed for atomicity (Safety Invariants 1–3).** `indexar()`'s existing
  `with Indice.abrir(raiz, criar=True) as idx:` (task_03/task_01) already rolls back on any exception via
  `Indice.__exit__`. task_04's job here was proving it (IT-013), not changing it.
- **IT-013's interruption test can't rely on file processing order** — `scan.percorrer`'s docstring says
  "em qualquer ordem". Used a call-counter wrapper around the real `scan.ler` (raises `RuntimeError` on the
  2nd call, delegates to the original otherwise) instead of a fixed two-item `side_effect` list keyed to a
  specific file.
- **IT-014/IT-015 concurrency setup copies `test_store.py`'s existing pattern** (a second
  `sqlite3.connect(..., timeout=1)` holding `BEGIN IMMEDIATE`, released in a `finally: ROLLBACK; close()`)
  rather than subprocesses+`sleep`, per this task's own Implementation Details note that the latter is
  flaky.
- **IT-015 proves "sem esperar o timeout" via a wall-clock assertion**: `buscar()` during a held write
  transaction must complete in under `store.TIMEOUT_CONEXAO` (2.0s) — there's no other observable signal
  that it didn't block.
- **IT-017 is skipped as root** (`unittest.skipIf(os.geteuid() == 0, ...)`), per this task's own
  Implementation Details note — `chmod 0o555` doesn't stop root from writing, so the test would pass for
  the wrong reason.

## Verification run

- `python3 -m unittest discover -s tests -t . -v` → 55/55 ok (8 new: 4 in `test_cli.py` + 4 in
  `test_index.py`).
- `make test` → same, green.
- Manual subprocess check of all four E2E error paths (E2E-002–005) confirms: `stdout == ""` and no
  `"Traceback"` substring in `stderr` for every failing invocation; exit codes 1/2/2/2 match `_dx.md`.
