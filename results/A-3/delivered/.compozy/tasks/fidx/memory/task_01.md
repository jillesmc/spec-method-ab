# task_01 — Indexar e buscar de ponta a ponta

## Done

- `fidx/core.py`: `tokenize`, `file_digest`, `read_text`, `iter_files`, schema/`open_index`,
  `replace_file`, `remove_missing`, `index_dir`, `search`, and the `FidxError` hierarchy
  (`NotADirectory`, `IndexMissing`, `EmptyTerm`, `IndexBusy` — the last is declared now but only
  used starting task_03).
- `fidx/__main__.py`: manual `<dir> <comando> [termo...]` parsing, summary line, path printing
  (`os.path.join(directory, rel)`), exception → exit-code translation.
- `tests/test_core.py` (UT-001..019, IT-001) and `tests/test_cli.py` (E2E-001..005).

## Decisions / notes for future tasks

- `iter_files` relies on `os.walk(..., followlinks=False)` to stop recursion into symlinked
  directories (sufficient per the task's own hint), and explicitly checks `os.path.islink` only
  for filenames — directory symlink filtering wasn't needed beyond what `followlinks=False`
  already gives.
- `index_dir` follows the task's literal skeleton: every visited file goes through
  `replace_file` unconditionally (no digest comparison yet) — `reindexados == total` every round
  in this task. task_02 changes the `if` inside the loop, nothing else in the skeleton shape.
- Tokens are deduplicated with `set(tokens)` before the postings insert to avoid redundant
  `INSERT OR IGNORE` calls on files with many repeated terms.
- `read_text` decodes UTF-8 with `errors="ignore"` unconditionally; unreadable-file skip/warning
  (Business Rule 7, UT-032/UT-033) is out of scope here per `_tasks.md` coverage (task_03).

## Verification run

- `make test` → 26/26 green (incl. pre-existing `tests/test_fumaca.py`).
- Manual transcript of every case in `_dx.md` (golden path, idempotent 2nd index, empty dir,
  invalid dir, missing index, empty term, no-args usage) matches the doc byte for byte.
- `grep -rn "mtime\|st_mtime\|getmtime" fidx/` → empty.
- Verified `search` never opens indexed files: `chmod 000` on the only matching file, `search`
  still returns the match (reads only `.fidx.sqlite3`).
- No non-stdlib imports (checked via `ast` walk over `fidx/*.py`).

Status: completed.
