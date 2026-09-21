# task_04 — Fechamento

## Implemented

- 4.1: `TestFumacaCliSubprocesso` added to the existing `tests/test_fumaca.py` (the file task_01
  already called "the pre-existing smoke test" — kept smoke tests together instead of a new file).
  Runs `[sys.executable, "-m", "fidx", tmp, "index"]` and then `search orcamento` as real
  subprocesses (no `cli.main()` call, no mocking), asserting exit codes and stdout — proves
  `python -m fidx` is actually executable per the README's own example commands.
- 4.2: README now documents (a) `.fidx/` lives inside the indexed folder and dotfiles/`.fidx`/`.git`
  are never indexed, (b) whole-word search semantics (`casefold` + `\w+`, no substring/prefix/regex,
  multi-word or empty-after-normalization term is a usage error not an empty result), (c) exit codes
  0/1/2 with what each means, matching design D8 exactly.
- 4.3: `make test` → 24/24 pass (23 prior + the new subprocess smoke test), stdlib-only, no
  external deps installed for the run.

## Verification run

- `make test` (`python3 -m unittest discover -s tests -t . -v`) → 24 passed, exit 0.
- Re-checked `openspec` CLI availability per shared memory's request: still not present (`which
  openspec`, `pip show openspec`, `npm ls -g openspec` all empty/not-found). `openspec validate fidx
  --strict` remains **unrunnable in this environment** — not a regression, same blocker task_01-03
  already recorded; repository's own verification gate (`make test`) is what actually ran and passed.

## Scope decisions

- Did not touch `fidx/__init__.py` or `fidx/__main__.py` — section 4 is test/docs/verification only.
- Closed the change: `_tasks.md` and this task file marked `completed`, all three item checkboxes
  checked.
