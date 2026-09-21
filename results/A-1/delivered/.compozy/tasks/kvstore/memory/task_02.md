# task_02 memory: Linha de comando `python -m kvstore`

## Status

Completed. `kvstore/__main__.py` implements the four verbs (`set`/`get`/`del`/`list`) against the
frozen `_dx.md` § CLI/Errors surface; `tests/test_cli.py` (E2E-001..E2E-027) all pass. `make test`
green (58/58), stable across 2 repeated runs.

## Implementation decisions

- **Never import `sqlite3`, not even in a comment.** The task's Success Criteria says a plain-text
  `grep` for `sqlite3` (and `SELECT`/`INSERT`) must return nothing from `kvstore/__main__.py` — this
  is literal, not "no `import sqlite3` statement". A first draft had the word `sqlite3.Error` inside
  an explanatory comment and that would have failed the check. Since the file can't name the exception
  type, storage-layer failures are caught with a plain `except Exception` (after `ValueError`/
  `TypeError` are caught first for usage errors) — safe here because `Store` only ever raises
  `ValueError`, `TypeError`, `OSError`, or a `sqlite3.Error` subtype, never anything else.
- **Arity validation happens before opening `Store`.** `_validar_resto()` checks argument count (and
  the `set k - extra` special case) purely from `argv`, before `_abrir_store()` runs. This avoids
  creating the target directory as a side effect of a usage error (e.g. `set posicao` with a missing
  value would otherwise silently `mkdir` the directory before printing the usage line and exiting 2).
- **Two exception-catching layers**: one around `Store(diretorio)` construction (`_abrir_store`,
  mapping any failure — `OSError` from `os.makedirs`, or a storage-engine error opening/creating the
  db file in a read-only directory — to the single "nao foi possivel abrir" message, code 3), and one
  around the actual verb execution (`_executar`, mapping `ValueError`/`TypeError` to code 2 and
  everything else to code 3, with a `"locked"` substring check on the message to special-case the
  busy-timeout message from `_dx.md`).
- **`_motivo(erro)`**: for `OSError` with both `errno` and `strerror` set, formats as
  `[Errno N] strerror`, deliberately *not* `str(erro)` — Python's default `str(OSError)` appends
  `: '<path>'`, but `_dx.md`'s example (`kvstore: nao foi possivel abrir /proc/impossivel: [Errno 13]
  Permission denied`) does not repeat the path a second time. For non-`OSError` (storage-engine
  errors), falls back to plain `str(erro)`.
- **`get`/`list` write raw bytes via `sys.stdout.buffer`**, never `print`, so no newline is ever added
  to `get`'s output and `list` can write incrementally per key. `BrokenPipeError` around these writes
  is handled with the standard CPython recipe (dup2 stdout's fd to `/dev/null` after catching it) so
  interpreter shutdown doesn't try to flush a closed pipe and print a second traceback.
- **`stdin` for `set k -` is read as raw bytes and decoded once** (`sys.stdin.buffer.read().decode
  ("utf-8")`), not via a reconfigured text-mode `sys.stdin` — this keeps decode-error byte-offset
  reporting exact (`UnicodeDecodeError.start`) and is locale-independent regardless of the reconfigure
  calls at the bottom of the file (those only matter for the `stderr` text writes).

## Test-writing techniques worth reusing in later tasks

- **Never put a multi-MB value in argv for a CLI subprocess test** — confirmed again here (task_01
  memory already flagged this for the SDK layer): `subprocess.run([..., "set", "grande", <5MB string>]
  )` fails with `OSError: [Errno 7] Argument list too long` on this machine, independent of Python's
  own `MAX_ARG_STRLEN`. Route any value over a few KB through `-`/`stdin` (`input=...` to
  `subprocess.run`) instead — this is what E2E-011 and E2E-024 do.
- **Seeding many keys for the broken-pipe test (E2E-023) must bypass `Store`.** `Store.set()` is one
  fsynced transaction per call (`synchronous=FULL`, `isolation_level=None`), so a loop of ~100k calls
  to reliably overflow the OS pipe buffer (64 KiB on Linux) would take far too long. The test opens
  its own `sqlite3.Connection` directly (test code only — `kvstore/__main__.py` itself still can't
  import `sqlite3`) and does a single `executemany` + one `commit()` to seed 100k rows fast, then
  launches the real CLI subprocess against that pre-seeded directory.
- **E2E-023's mechanism**: `subprocess.Popen` (not `run`), read exactly one line, close
  `proc.stdout`, then `communicate()` and assert `stderr` has no `BrokenPipeError`/`Traceback`
  substring. A `run()` call can't do this because it doesn't let you close the pipe mid-read.
- **Permission tests (E2E-021, E2E-025) skip under root** via
  `unittest.skipIf(os.geteuid() == 0, ...)` — root ignores directory permission bits, so the setup
  wouldn't actually reproduce the failure condition and would need a different mechanism entirely.
  This environment runs as `uid=1000`, so these tests actually exercise the real permission-denied
  path here.

## Follow-ups for later tasks (not this task's scope)

- task_03 owns `IT-023` (busy-timeout contention) and `IT-031` (`list` at scale) — both drive this
  task's `__main__.py` as a real subprocess; the busy message (`armazenamento ocupado por outro
  processo (5s)`) and `list`'s incremental-write behavior implemented here are what those cases
  assert against, but neither was exercised by an actual concurrent-writer scenario in this task.
- README (task_04) already shows the exact invocation implemented here
  (`python -m kvstore ./dados set foo bar`) — verified it still matches, no change needed in this
  task per the Relevant Files note.

## Verification evidence

- `python3 -m unittest tests.test_cli -v` → 27/27 ok.
- `make test` (`python3 -m unittest discover -s tests -t . -v`) → 58/58 ok, run twice with no flakes
  (~36s each, dominated by task_01's durability tests that fork/kill subprocesses).
- `grep -in "sqlite3\|SELECT\|INSERT" kvstore/__main__.py` → no output (clean).
- Manual spot checks of the Golden Path and every row of the Errors table via direct `python3 -m
  kvstore` invocations, cross-checked byte-for-byte against `_dx.md` before writing the automated
  tests.
- `git status --short` after implementation: `kvstore/__main__.py` and `tests/test_cli.py` are new;
  no stray `kvstore.sqlite3*` or temp directories left in the repo tree (all test fixtures use
  `tempfile.TemporaryDirectory`).
