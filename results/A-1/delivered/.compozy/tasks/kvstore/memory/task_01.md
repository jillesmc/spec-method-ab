# task_01 memory: Camada de armazenamento durável (`Store`)

## Status

Completed. `kvstore/__init__.py` implements `Store` per the frozen contracts; `make test` passes
31/31 (24 UT + 6 IT + 1 smoke), stable across repeated runs.

## Implementation decisions

- `_validar_chave` checks `isinstance(str)` before the empty-string check, so `set(1, ...)`,
  `get(1)`, `delete(1)` all raise `TypeError` (UT-010) and empty-string only raises `ValueError`
  once the type check has passed (UT-009).
- Directory creation is bare `os.makedirs(diretorio, exist_ok=True)`. When `diretorio` is an
  existing regular file, this itself raises `FileExistsError` (an `OSError`) naming the path —
  satisfies UT-016 without extra handling.
- `keys()` and `get()`/`delete()` all go through the single `_conectar`-opened connection stored
  as `self._con` — tests read `s._con.execute("PRAGMA ...")` directly (UT-020/021/022), matching
  the private-attribute access shown in `_spec.md`/`_tests.md` verbatim.

## Test-writing techniques worth reusing in later tasks

- **Mid-write kill without `sleep`**: for IT-012 and IT-013 (kill *during* a write), the child
  script registers `sqlite3.Connection.set_progress_handler(callback, 1)` and the callback writes
  a one-byte-per-line message to a pipe fd on its *first* invocation. The parent blocks reading
  that pipe (real synchronization, not a race) and sends `SIGKILL` the instant it gets the
  message — this reliably interrupts execution mid-statement, before the implicit commit/fsync,
  without ever guessing a delay.
- **Passing large values to a subprocess**: never put multi-MB values in argv — Linux caps a
  single exec argument at `MAX_ARG_STRLEN` (128 KiB), so a 5–8 MB value passed via `sys.argv`
  fails with `E2BIG`. Send it over `stdin` (`subprocess.Popen(..., stdin=subprocess.PIPE)` /
  `subprocess.run(..., input=...)`) and have the child do `sys.stdin.read()` before opening the
  `Store`.
- **`pass_fds`** is required for a child to inherit pipe fds across `exec` — pipes created with
  `os.pipe()` are close-on-exec by default in a `subprocess.Popen` child unless listed there.
- IT-012 loops 3 times (fresh temp dir each time) since the exact byte the kill lands on is not
  controlled — the assertion (`old value or new value, never a mix, sentinel untouched`) holds
  regardless, so this isn't a race-prone assertion, just a "run it a few times" per `_tests.md`'s
  own text.
- IT-040 (`RLIMIT_FSIZE`) makes the child crash with an uncaught `sqlite3.OperationalError: disk
  I/O error` traceback printed to stderr — that's expected/correct: the process exits non-zero
  either way, and `kvstore/__init__.py` deliberately doesn't catch this (it's a storage failure,
  meant to bubble as `sqlite3.Error`).

## Follow-ups for later tasks (not this task's scope)

- task_02 (`__main__.py`) is the sole consumer of `Store` and must not import `sqlite3` — this is
  an enforced architectural boundary, not just a style preference (ADR-002 risk).
- task_03 owns `IT-020`–`IT-023` (concurrency) and `IT-030`–`IT-032` (growth); none of that was
  touched here.

## Verification evidence

- `python3 -m unittest tests.test_store -v` → 24/24 ok.
- `python3 -m unittest tests.test_durabilidade -v` → 6/6 ok.
- `make test` (`python3 -m unittest discover -s tests -t . -v`) → 31/31 ok, run 4 times total
  (including the `make test` invocation) with no flakes.
- `git status --short` after implementation: only `kvstore/__init__.py` modified and the two new
  test files added — no stray `kvstore.sqlite3*` files left in the repo tree.
