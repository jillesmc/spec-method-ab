---
schema_version: "compozy.tasks/v2"
workflow: kvstore
graph:
  nodes:
    - id: task_01
      file: task_01.md
    - id: task_02
      file: task_02.md
    - id: task_03
      file: task_03.md
  edges:
    - from: task_01
      to: task_02
    - from: task_02
      to: task_03
---

# Task Graph: kvstore

Spec: [`_spec.md`](_spec.md) · Surface: [`_dx.md`](_dx.md) · Behavior: [`_user_stories.md`](_user_stories.md)
· Tests: [`_tests.md`](_tests.md)

| Task      | Title                                          | Type    | Complexity | Depends on | Ships                                                                              |
| --------- | ---------------------------------------------- | ------- | ---------- | ---------- | ---------------------------------------------------------------------------------- |
| `task_01` | Durable store and CLI                          | feature | high       | —          | The four verbs, durable on ack, surviving a kill. **Solves the Motivating Problem** |
| `task_02` | Concurrent access and large values             | feature | high       | `task_01`  | Safe concurrent invocations, stdin values, byte-exact large values                  |
| `task_03` | Bounded growth over time                       | feature | medium     | `task_02`  | Space reclaimed after deletes, journal bounded, reads that do not scan              |

## Why this order

`task_01` is the MVP slice: after it merges, the service can write state and trust the ack, which is the
whole reason the spec exists. `task_02` and `task_03` harden the same frozen surface — neither adds a verb,
an option, or an exception type beyond what `_dx.md` already lists.

The chain is linear rather than fanned out on purpose: all three tasks edit `kvstore/store.py`, so they are
sequenced by ownership of that file. `task_03` follows `task_02` because the reclaim path runs inside the
same write transaction that `task_02` makes contention-safe.

## Test ownership

Every ID in `_tests.md` is assigned exactly once.

| Task      | Unit           | Integration     | E2E               |
| --------- | -------------- | --------------- | ----------------- |
| `task_01` | UT-001–UT-025  | IT-001–IT-005   | E2E-001–E2E-009   |
| `task_02` | UT-026–UT-029  | IT-006–IT-008   | —                 |
| `task_03` | UT-030–UT-032  | IT-009          | —                 |

`tests/test_fumaca.py` keeps its existing package-import coverage and is owned by no task.
