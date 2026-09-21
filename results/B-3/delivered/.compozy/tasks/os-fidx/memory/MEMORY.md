# Shared memory: os-fidx

- `openspec` CLI is not installed in this environment (no binary, no npm/pip package under that
  name resolves to it). `openspec validate fidx --strict` from task Verificacao sections cannot be
  run here; `make test` is the only verification gate actually available. Re-checked at task_04
  (change closure) — still absent, confirmed final: this change was closed on `make test` alone.
- Repo verification gate is `make test` → `python3 -m unittest discover -s tests -t .`. No external
  deps allowed (stdlib only, Python 3.11+ per README, running 3.14 here).
- Design source of truth: `openspec/changes/fidx/design.md` decisions D1-D9. Read those before
  touching `fidx/__init__.py` or `fidx/__main__.py` again — they fix schema, tokenization, staleness
  rule (content hash only, never mtime), and the index/search split.
