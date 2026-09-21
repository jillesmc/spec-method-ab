---
status: completed
title: Durable store and CLI
type: feature
complexity: high
---

# Task 1: Durable store and CLI

## Overview

After this task merges, the service can run `python -m kvstore ./dados set posicao 1042`, get exit code 0,
be killed with `SIGKILL` one instant later, and read `1042` back from a new process. That is the Motivating
Problem of the spec, end to end: the ack stops being a hope. The task delivers the `kvstore.Store` API, the
`python -m kvstore` CLI with all four verbs, and the durability configuration that makes the ack mean
something.

## Shippable Outcome

- Outcome: all four verbs work through their real entry path (`python -m kvstore <dir> <verb>`), and every
  acknowledged write survives an abrupt kill of the writing process.
- Verify in this task: `make test` green, with UT-001–UT-025, IT-001–IT-005 and E2E-001–E2E-009 passing —
  in particular IT-001 (kill right after the ack) and UT-018/UT-019 (the pragma configuration the ack
  depends on). Also run the `_dx.md` Golden Path by hand once and confirm the transcript matches.
- Integration verification: none — this task owns its own entry-path proof.

## Requirements

- Implement the surface exactly as frozen in [`_dx.md`](_dx.md): verb shapes, exit codes (0/1/2/3), the
  error message table, and the byte-exact stdout rule for `get`. Do not add a verb, a flag, or an
  exception type that is not in that document.
- Honour [Safety Invariants](_spec.md#safety-invariants) 1, 2, 3, 4, 6, 7 and 8. Invariant 5 (writer
  contention) is configured here via `busy_timeout` but is verified in `task_02`.
- Connection setup must follow the exact order in [`_spec.md` Core Interfaces](_spec.md#core-interfaces):
  `auto_vacuum=INCREMENTAL` → `journal_mode=WAL` → `synchronous=FULL` → `busy_timeout` → `CREATE TABLE`.
  `auto_vacuum` is only settable before the schema exists; `synchronous` is per-connection and must be
  re-applied on every open, including reopens. Getting this order wrong fails silently — that is what
  UT-018, UT-019 and UT-030 exist for.
- Open the connection with `isolation_level=None`, so each statement is its own committed transaction. Do
  not wrap operations in an explicit transaction and do not batch.
- `kvstore/__main__.py` must not `import sqlite3` and must not touch the state directory directly; it
  parses, calls `Store`, and maps exceptions to exit codes.
- `kvstore/store.py` must not print, read `sys.argv`, or call `sys.exit`; it raises.
- Standard library only — including in the tests.
- `set <key> -` reads the value from stdin as bytes; any other `-` is the literal value `-`.
- Read paths create nothing: `get`/`list` against a missing directory behave as an empty store and leave
  the filesystem untouched.

## Subtasks

- [x] 1.1 Implement `kvstore/store.py`: the error hierarchy, `FORMAT_VERSION`, connection/pragma setup,
      schema creation with `PRAGMA user_version`, and the version check on open.
- [x] 1.2 Implement `Store.set`, `Store.get`, `Store.delete`, `Store.list`, `close`, and the context
      manager, including key validation (non-empty, no newline, no NUL) and UTF-8 encode/decode at the
      BLOB boundary.
- [x] 1.3 Make directory creation lazy: created on the first mutation, never on a read.
- [x] 1.4 Re-export `Store`, the error types and `FORMAT_VERSION` from `kvstore/__init__.py`.
- [x] 1.5 Implement `kvstore/__main__.py`: argument parsing, the stdin value path, byte-exact stdout for
      `get`, the usage block, and the exception → exit-code mapping.
- [x] 1.6 Write `tests/test_store.py` (UT-001–UT-017, UT-022–UT-025) and `tests/apoio.py` with the
      child-process helpers the crash tests need.
- [x] 1.7 Write `tests/test_durabilidade.py` (UT-018–UT-021, IT-001–IT-005).
- [x] 1.8 Write `tests/test_cli.py` (E2E-001–E2E-009), asserting stdout/stderr as bytes.
- [x] 1.9 Update `README.md` from the `_dx.md` Golden Path: the four verbs, the stdin form, the exit-code
      table, and one sentence on what exit 0 from `set` guarantees.
- [x] 1.10 Run `make test` and the Golden Path transcript by hand.

## Implementation Details

Files to create: `kvstore/store.py`, `kvstore/__main__.py`, `tests/apoio.py`, `tests/test_store.py`,
`tests/test_durabilidade.py`, `tests/test_cli.py`. Files to modify: `kvstore/__init__.py`, `README.md`.

Code patterns and the exact connection sequence are in
[`_spec.md` Part II → Implementation Design](_spec.md#implementation-design); the public shapes are in
[`_dx.md`](_dx.md). Do not re-derive either.

Two traps worth naming, because both fail silently:

- A `SIGKILL` test that kills the child before the child has actually acked proves nothing. Have the child
  signal the parent through a pipe *after* `set` returns, and have the parent kill on that signal.
- `PRAGMA synchronous` returns to its default on a connection that forgets to set it, and nothing about
  the store's behavior looks different afterwards — on a machine with a warm page cache, even the kill
  tests would still pass. UT-019 asserts it on a reopened connection for exactly that reason.

### Relevant Files

- `kvstore/__init__.py` — empty today; becomes the public import surface.
- `tests/test_fumaca.py` — the `unittest` style to follow; must keep passing untouched.
- `Makefile` — the discovery command new test files have to satisfy (`test_*.py` under `tests/`).
- `README.md` — states the Python 3.11+ floor and the standard-library-only rule; updated here.

### Dependent Files

- `tests/test_fumaca.py` — imports `kvstore`; a broken `__init__.py` breaks it first.

### Related ADRs

- [ADR-001: SQLite as the storage engine](adrs/adr-001.md) — why there is no hand-written log, CRC,
  lock file or compactor to implement here.
- [ADR-002: Durability by `synchronous=FULL` and one transaction per mutation](adrs/adr-002.md) — the
  rule behind subtask 1.1 and UT-018/UT-019.

## Deliverables

- `kvstore.Store` with the four operations, durable on return.
- `python -m kvstore` with the four verbs, the exit-code contract and the error messages from `_dx.md`.
- Test files covering UT-001–UT-025, IT-001–IT-005, E2E-001–E2E-009.
- A `README.md` that shows the whole surface.

## Tests

Cases assigned from [`_tests.md`](_tests.md) — read each definition before writing it.

- [x] UT-001–UT-017 — basic operations, key/value validation, directory handling, error paths.
- [x] UT-018–UT-021 — the durability configuration and the on-disk format guard.
- [x] UT-022–UT-025 — foreign files left alone, context manager, two stores on one directory, exported
      error surface.
- [x] IT-001–IT-005 — process kill after the ack, 50-key survival, kill mid-large-write, repeated
      kill/reopen cycles, a never-closed store.
- [x] E2E-001–E2E-009 — the `_dx.md` transcripts: golden path, failure surface, value fidelity, empty and
      unusual stores.

## Success Criteria

- `make test` passes, including the pre-existing `tests/test_fumaca.py`.
- The `_dx.md` Golden Path, typed by hand, produces exactly the transcript in that document — including
  `get` emitting no trailing newline and `set` emitting nothing at all.
- `python -m kvstore` contains no `import sqlite3`, and `kvstore/store.py` contains no `print` and no
  `sys.exit`.
- No file in the repository declares a dependency outside the standard library.
