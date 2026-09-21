# Task memory: task_02 (fidx/scan.py)

Status: completed.

## What was built

- `fidx/scan.py`: `percorrer(raiz)`, `ler(caminho)`, `tokenizar(texto)`. Stdlib only (`os`, `re`,
  `hashlib`, `pathlib`). No `mtime`/`st_mtime`/`getmtime`, no `print`, no `sys.exit`, no import of
  `fidx.store` — matches Success Criteria in `task_02.md` (verified with `grep`).
- `tests/test_scan.py`: UT-001–UT-014, one `unittest.TestCase` per group (`TestTokenizar`, `TestLer`,
  `TestPercorrer`), docstring on each test method carries the UT id per `_tests.md` convention.

## Decisions / gotchas for whoever reads scan.py next

- `percorrer` relies on `os.walk`'s **default** `followlinks=False` (not passed explicitly) — this alone
  breaks the cyclic-symlink case (UT-014) because os.walk never descends into a symlinked directory in the
  first place. No extra cycle-detection code needed.
- Hidden-entry pruning mutates `dirnames` in place (`dirnames[:] = [...]`) *before* the `for nome in
  filenames` loop, per the task's explicit instruction — filtering after the fact would still let os.walk
  descend into `.git/`.
- `ler()` does exactly one `open(path, "rb").read()`; the same `dados` bytes feed both
  `hashlib.sha256(...).hexdigest()` and `.decode("utf-8")` (strict, no `errors="ignore"`). Any `OSError` on
  open/read, or `UnicodeDecodeError` on decode, returns `None` — never raises. This is what ADR-001's
  "digest from content, not mtime" and "one read per file" implementation notes require.
- `tokenizar` is `set(re.findall(r"\w+", texto.lower()))` — no `unicodedata` normalization, so accents are
  preserved. This is the **same function** task_03 must call for both file content and the search query
  (do not write a second tokenizer there).

## Verification run

- `make test` → `python3 -m unittest discover -s tests -t . -v`: 30 tests, OK (14 new in `test_scan.py` +
  3 in `test_fumaca.py` + 13 pre-existing in `test_store.py` from task_01).
- `grep -n "mtime\|st_mtime\|getmtime" fidx/scan.py` → empty.
- `grep -n "print(\|sys\.exit\|import fidx\.store\|from fidx import store\|from fidx\.store" fidx/scan.py`
  → empty.
- A `ResourceWarning: unclosed database` appears during `make test` — it comes from task_01's
  `test_store.py`, not from anything touched in this task. Not a regression introduced here.

## Follow-up (not in scope here)

- None. This module is a leaf per the task's own constraint ("Não importar `fidx.store`"); task_03 is the
  integration point that wires `percorrer`/`ler`/`tokenizar` into the `index`/`search` loop.
