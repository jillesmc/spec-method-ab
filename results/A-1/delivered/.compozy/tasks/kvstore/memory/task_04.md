# task_04 memory: README e verificação final

## Decisions

- README rewritten from scratch (previously 4 lines) into: intro, CLI usage (golden path + get-missing
  + stdin `-` + usage error), in-process SDK usage, durability guarantee (with the `fsync`-lying-hardware
  caveat verbatim from `_spec.md` § Business Rules / `adr-002.md`), the three known limitations
  (file doesn't shrink after deleting a large key, `list` ambiguous for newline-containing keys, single
  writer at a time), on-disk files section, and `make test`.
- Every command shown in the README was actually executed in a scratch directory outside the repo
  (`/tmp/kvstore-readme-check*`, PYTHONPATH pointed at the repo) and its output compared byte-for-byte
  against what the README claims, including the no-trailing-newline behavior of `get` (visible as
  `1042config` running together when piped straight into the next command).
- `ls -a ./dados` in a fresh scratch dir only ever showed `kvstore.sqlite3` (no `-wal`/`-shm`) because
  each CLI invocation is a fresh process that closes its only connection, which checkpoints WAL away.
  Documented as "pode aparecer e sumir entre execuções" rather than claiming they're always present —
  matches `_dx.md` wording, no contradiction.
- Added one closing sentence in the limitations section ("nenhuma dessas exige rotina periódica de
  manutenção") specifically to satisfy the `US-008.AC-3` review criterion (no periodic maintenance
  routine implied anywhere in the README) — this is the only test for this task and it's a review
  check, not automated.
- No code changed. No new test IDs (task_04 owns zero per `_tasks.md` § Propriedade dos casos de teste).

## Verification performed

- Enumerated `def test_..._` names across `tests/test_store.py`, `test_durabilidade.py`, `test_cli.py`
  and confirmed all 64 assigned IDs are present (24 UT, 6 IT-01x/040, 27 E2E, 7 IT-02x/03x) with no
  `IT-022b`.
- `make test` → 65/65 passed (64 assigned + 1 smoke test in `test_fumaca.py`), ~52s.
- Manually re-ran every console/Python snippet quoted in the README against the real package and diffed
  outputs.

## Follow-up (not in scope here)

None identified — task_04 is the last task in the graph.
