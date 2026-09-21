# spec-method-ab

Pre-registered A/B experiments comparing two spec-driven development methods on the same tasks,
with the same executor, measured by a hidden acceptance suite that was calibrated before any
round ran.

**Result: all three experiments tied.** The final one scored 43/44 against 42/44 on the primary
metric, a difference of one test.

Discussion with the full write-up: <!-- DISCUSSION_URL -->

---

## The comparison

| | arm A | arm B |
|---|---|---|
| planning | `cy-create-spec` + `cy-create-tasks` (CompozyOS `spec-cycle`, bundled) | `openspec-propose` ([OpenSpec](https://openspec.dev)) + a converter |
| execution | identical | identical |
| review | identical | identical |

Only the planning layer differs. Everything after it is the same pair of CompozyOS Loops
(`implement-tasks`, `review-and-fix`) with the same runtime.

Model per phase, which is the usage pattern being tested:

```
plan     claude-opus-5   (premium seat, identical in all rounds)
execute  sonnet          (seat rotated, paired between arms)
```

## Why there are three experiments

The first two tied **at ceiling**: every round scored 100% on the primary metric, so there was
nothing to compare. The diagnosis was that the tasks had no *trap* — any reasonable decomposition
worked, and a strong planner does not produce unreasonable decompositions.

The third experiment adds a trap to each task: a natural approach that passes the entire happy
path and fails an invariant.

| domain | natural approach | what the requirement actually needs |
|---|---|---|
| `store` | rewrite the whole JSON file on every write | writes that survive the process dying mid-write |
| `indexador` | cache by `mtime` | decide what changed by content |

**The prompts state the requirement in plain business language and never name a technique.** The
store prompt says the service restarts several times a day and that a confirmed write must survive
a restart. The indexer prompt says files arrive over rsync and checkout, so modification times are
not trustworthy. Translating a requirement into a technique is the work planning is supposed to do.

## The suites were calibrated before any round ran

Four reference implementations, written by hand, measured with the same command the runner uses:

| domain | reference | base | robustness | **primary** |
|---|---|---|---|---|
| store | careful (append log + CRC + atomic rename) | 8/8 | 12/12 | **10/10** |
| store | naive (whole-file rewrite) | 8/8 | 12/12 | **3/10** |
| indexador | careful (content hash) | 8/8 | 10/10 | **12/12** |
| indexador | naive (mtime cache) | 8/8 | 10/10 | **8/12** |

The naive implementation passes everything except the layer that matters. Without this step,
"the suite discriminates" would be an opinion. Reproduce it with:

```
harness/calibrar.sh store ingenua
harness/calibrar.sh store cuidadosa
harness/calibrar.sh indexador ingenua
harness/calibrar.sh indexador cuidadosa
```

## Result

| | store (2 rounds) | indexador (2 rounds) | **pooled** |
|---|---|---|---|
| arm A (`spec-cycle`) | 19/20 | 24/24 | **43/44 · 98%** |
| arm B (OpenSpec) | 18/20 | 24/24 | **42/44 · 95%** |

Decision rule, fixed before running: a tie if the pooled percentages differ by less than 10
points. They differ by 3.

Per-round scores, seat audit and Loop states are in [`results/RESULTADO.md`](results/RESULTADO.md).

## What this does and does not show

**Shows.** The choice of spec tool did not change delivered quality on these tasks. Both arms
avoided both traps in 8 out of 8 rounds, on suites where a naive implementation scores 3/10 and
8/12.

**Does not show.** *Why* the quality was there. The obvious candidate is the planner model, and
that control round was never run: every round in every experiment planned with the same model.
Nothing here separates the planner from the method.

**Also does not show.** Anything about programming in general. Two tasks, n=2 per domain, one
planner model, one executor model, one runtime version.

## The suites are now burned

Publishing the hidden suites is what makes a negative result checkable — "my private suite says
they tied" is unfalsifiable. The price is that **these two tasks can no longer measure anything**.
Anyone repeating this needs new tasks.

## Layout

```
fixtures/<domain>/
  ENUNCIADO.md              the prompt handed to both arms (Portuguese)
  repo-base/                the starting repository, identical for both arms
  aceite/test_aceite.py     the hidden acceptance suite, three layers
  referencia/{ingenua,cuidadosa}/   the calibration references
harness/
  rodar.sh                  one round: prepare, plan, implement, review, measure
  executar.sh               the driver: rehearsal gate, queue in passes, report
  calibrar.sh               runs a suite against a reference implementation
preregistration/
  PRE-REGISTRO-V4.md        frozen before the first round (Portuguese)
  CONGELADO-V4.md5          checksums of every frozen artifact
results/
  RESULTADO.md              the generated verdict
  INTERVENCOES.md           every change made after freezing, with reason and time
  SEQUENCIA.log             the driver's log
  <ARM>-<n>/
    RESUMO.txt              the round's measurements
    aceite-*.txt            raw suite output per layer
    prompt-plano.txt        the exact planning prompt
    delivered/              the repository the agents produced, plans included
```

The prompts, the pre-registration and the deviation log are in Portuguese; they are the primary
record and were not rewritten after the fact.

## Environment

| | |
|---|---|
| runtime | CompozyOS `0.3.0-beta.27` |
| ACP adapter | `@agentclientprotocol/claude-agent-acp@0.77.0`, pinned |
| planner | `claude-opus-5` |
| executor | `sonnet` |
| background roles | all six disabled, so no other consumer shares the seat |

## Honest notes

- **Every deviation after freezing is logged** in [`results/INTERVENCOES.md`](results/INTERVENCOES.md),
  including the ones that were mistakes of mine: a kill-timing test that turned out to be a coin
  flip, a 1 MB value that exceeded `MAX_ARG_STRLEN`, and an auth failure that was almost counted
  against a planning method.
- **Round A-4 is an anomaly.** Its review Loop ended `failed` after 55 minutes and it opened 19
  agent sessions against 6 for its pair. It still scored 12/12. It counts by the pre-registered
  rule, and it is worth a look.
- The `spec-cycle` arm runs a small sanitizer over the generated task frontmatter, for symmetry
  applied to both arms. It did not need to change anything in any of the 8 rounds.
