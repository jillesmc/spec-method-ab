# Task memory: task_03 (CLI)

- `fidx/__main__.py`: `argparse` with `diretorio` as the shared top-level positional, then
  `index`/`search` subparsers (search takes `termo`). Missing subcommand/argument or unknown
  subcommand already exit 2 with a stderr message via argparse's own `parser.error` — no custom
  handling needed for item 3.1.
- Directory existence is checked once (`os.path.isdir`) before dispatching to either subcommand,
  covering the "diretório inexistente" case for both `index` and `search`.
- `search` on a never-indexed directory relies entirely on `fidx.search()`'s own
  `FileNotFoundError` (checks for `.fidx/index.sqlite3` before touching the filesystem otherwise)
  — the CLI does not add a second check, so there is no risk of silently falling back to a scan.
- Exit codes: 0 success, 1 search-with-no-results (distinct from usage errors per spec), 2 for
  `ValueError`/`FileNotFoundError` (bad term, missing dir, missing index) and for
  `sqlite3.OperationalError` (locked db).
- Test for 3.5 (locked db) monkeypatches `fidx.sqlite3.connect` to force a 0.05s timeout instead of
  the hardcoded 30s in `fidx/__init__.py`, so the "banco travado" scenario doesn't cost 30 real
  seconds per test run. Production code is untouched — only the test's `sqlite3.connect` wrapper
  overrides the `timeout` kwarg. Lock is held by a second same-process `sqlite3.connect(...)` doing
  `BEGIN EXCLUSIVE`, no threading needed.
- Passing a literal `---`-like term through argparse needs a `--` separator
  (`["search", "--", "---"]`), otherwise argparse treats it as an unknown flag — this is an argparse
  quirk in the test, not a CLI bug.
- `openspec` CLI still not installed (re-confirmed: no binary, no pip package, not in `npm ls -g`).
  Matches [[MEMORY]]'s existing note — `openspec validate fidx --strict` remains unrunnable here;
  still deferred to task_04 per that note.
- Verification: `make test` → 23/23 pass. Manual smoke of `python -m fidx <dir> index|search`
  against a real temp directory confirmed exit codes 0/1/2 and output shape match
  `specs/file-index/spec.md` scenarios.
