# Part I — Product

Part I frames WHAT and WHY. Implementation choices belong to Part II, except the ones the requester
fixed as constraints (Python standard library only, `python -m kvstore` command shape, `make test`).

## Overview

- **Motivating Problem**: a long-running service keeps its state (configuration, counters, processing
  position) in a single JSON file that is rewritten in full on every change. The service restarts several
  times a day — deploys and OOM kills — and at least once it came back with an emptied file and lost all
  of its state. The simplest end-to-end behavior that solves it: `python -m kvstore <dir> set <k> <v>`
  exits 0 only after that write is on disk, and a process started after an immediate `kill -9` reads the
  same value back. Slice 1 (task_01) delivers exactly that.
- **Who it is for**: the service that owns the state directory, and the engineer who inspects or repairs
  that state from a shell.
- **Why it is valuable**: "gravei" becomes a promise instead of a hope. A restart at any instant loses at
  most the writes that were never acknowledged, and never the ones that were.

## Goals

- After a `set` returns success, the value is readable by any later process, including one started right
  after an abrupt kill of the writer.
- A crash during a write can no longer destroy data written before it — no operation rewrites the whole
  dataset in place, which is the mechanism that emptied the JSON file.
- Keys and values are read and written one at a time; a large value does not cost a full-dataset rewrite.
- Several concurrent invocations against the same directory either succeed or fail loudly; they never
  leave the directory in a state a later process cannot read.
- Disk usage tracks the live data, not the number of writes ever performed, without anyone running a
  cleanup job.
- The four verbs are usable both from a shell and from the service's own Python process, with the same
  durability contract.

## User Stories

- `US-001`–`US-004`: the four verbs (`set`, `get`, `del`, `list`) and their observable results.
- `US-005`–`US-006`: durability across restart and crash recovery.
- `US-007`: concurrent invocations against one directory.
- `US-008`: large values and unbounded growth over time.
- [Full user stories](_user_stories.md)

## Core Features

- **Durable write (`set`)**: stores a text value under a key, replacing any previous value, and reports
  success only once the write is durable. Interacts with every other feature: it is the only producer of
  state.
- **Point read (`get`)**: returns the current value for a key verbatim, or reports that the key is absent.
  Never sees a partially written value.
- **Delete (`del`)**: removes a key. Reports whether the key existed. The space it occupied returns to the
  store instead of accumulating.
- **Key listing (`list`)**: prints every live key in sorted order, one per line. Reflects every acked
  `set`/`del` that preceded it.
- **Python API**: the same four operations as a `Store` object, so the service can call them in-process
  instead of spawning a subprocess per write. The CLI is a thin wrapper over it, so both carry the same
  guarantee.

## Business Rules

- A `set` is acknowledged (exit code 0 / `Store.set` returning) only after its transaction is committed
  and flushed to disk. There is no write buffering, batching, or background flush inside kvstore.
- After any crash, the store contains exactly the acknowledged writes: every acked write is present, and a
  write interrupted before its ack is absent. No intermediate or torn state is ever visible.
- A key is a non-empty UTF-8 string containing no newline and no NUL character — `list` is line-oriented,
  so a key with a newline could not be listed unambiguously. A key that breaks these rules is rejected as
  a usage error and nothing is written.
- A value is a UTF-8 text string, possibly empty, possibly containing newlines or NUL. `get` returns the
  bytes that `set` received, byte for byte.
- `set` on an existing key replaces the value; there is no versioning and no history to read back.
- Reads never block on other reads; a writer excludes other writers for the duration of its transaction
  only.
- Operations are single-key. There is no multi-key atomicity: two `set` calls are two independent writes.
- Repeating a `set` with the same key and value is a no-op from an observer's point of view. `del` on an
  absent key changes nothing and reports "not found".
- The state directory is created on first write if missing. A read against a missing or empty directory is
  an empty store, and creates nothing.
- The directory belongs to kvstore alone; a file inside it that kvstore did not create is not read,
  written, or deleted by kvstore.
- The on-disk format carries a format version. A directory written by a newer format version is refused
  with a clear error rather than read with the wrong rules.

## User Experience

- **Personas**: the *service* (an unattended process that writes state and must trust the ack); the
  *operator* (a person inspecting or fixing state from a shell after an incident).
- **Primary flow — service**: on start, `list`/`get` to restore its state; during work, `set` per change,
  treating the return as the durability point; `del` when a key becomes irrelevant.
- **Primary flow — operator**: `python -m kvstore ./dados list` to see what exists, `get` to inspect one
  key, `set` to correct it, `del` to drop it. Output is line-oriented so it composes with shell tooling.
- **Accessibility**: the CLI is text-only. Success is silent, failures print a one-line reason to stderr
  and use a distinct exit code per class, so both a human and a script can act on the result.
- **Onboarding and discoverability**: `python -m kvstore` with no arguments prints the usage block listing
  all four verbs; the README shows the golden path.

## High-Level Technical Constraints

- **Python standard library only** — no third-party dependency, at any layer, including tests.
- Target runtime: CPython on Linux (the service's platform); `make test` must pass on it.
- Performance from the user's point of view: one `set` costs one flush to disk, and no work proportional
  to the total number of keys or to the total number of writes ever performed.
- Operability: everything the operator needs is reachable from the four CLI verbs plus ordinary filesystem
  inspection of the directory. No daemon, no server, no admin surface.
- Data privacy: values are stored as-is, unencrypted; the directory's filesystem permissions are the only
  access control, matching how the JSON file was protected.

## Non-Goals (Out of Scope)

- **Migrating the service's existing JSON state file** — the requester specified the package and its four
  verbs, not an importer. A one-off import is a few lines over the public `set` API. Recorded as an open
  question rather than a capability of this spec.
- **Multi-key transactions**, range or prefix queries, iteration over values, TTL/expiry, and any query
  language: never requested; the callers are config, counters, and a processing position.
- **Network access, a server, or multi-host replication**: the state is local to the service's host.
- **Windows support**: the service runs on Linux; the design uses POSIX filesystem semantics.
- **Encryption at rest and per-key access control**: not part of the problem being solved.
- **Streaming values larger than memory**: values are held in memory in full on both `set` and `get`.
  Named in Known Risks with its upgrade path.

## Open Questions

1. Does the existing JSON state file need to be imported into the new store as part of the cutover, or
   will the service repopulate the keys itself on first run? Scoped out above; a decision to import turns
   into a follow-up task, not a redesign.
2. Will the service call the Python API in-process, or spawn `python -m kvstore` per write? Both are
   supported and carry the same durability contract, so this does not block implementation — but a
   per-write subprocess costs process startup per ack, which the service owner may want to measure.
3. Is there an upper bound on a single value's size in practice? The design is verified to 64 MiB per
   value; beyond that, memory use is the limit (see Known Risks).

---

# Part II — Technical

## Executive Summary

The store is a single SQLite database inside the state directory, opened in WAL mode with
`synchronous=FULL`, one autocommitted transaction per mutation. SQLite's write-ahead log already provides
exactly the properties the incident demanded — a commit is durable when it returns, a crash rolls back to
the last commit, recovery is automatic on the next open, and multi-process access is serialized — and it
ships in the Python standard library, which is the requester's hard constraint. The alternative of
hand-writing an append-only log with CRCs, tail truncation, a lock file, and a compactor was rejected
(ADR-001): it reimplements four mechanisms SQLite has already debugged, and each one is a place where the
next data-loss incident can come from.

The primary trade-off is latency: `synchronous=FULL` costs one fsync per write (ADR-002). That is the
price of the promise the service makes to its callers, and it is the requirement, not an optimization
target.

The second trade-off is that the whole-file rewrite disappears, which is the point: SQLite writes pages,
so no operation ever puts the entire dataset in a position to be lost at once.

## MVP Boundary

The MVP is **task_01**, and it ships first: the `Store` API plus the `python -m kvstore` CLI with all four
verbs, durable-on-ack, verified by a kill-the-writer-and-reopen test. That alone solves the Motivating
Problem. **task_02** (concurrent invocations, large values, byte-exact values) and **task_03** (space
reclaim and behavior at scale over time) harden the same surface without changing it; they are in scope
for this spec and post-MVP in sequence. Out of scope entirely: everything under Non-Goals.

## Developer Experience

- [Developer experience contract](_dx.md) — CLI (the four verbs, stdin values, exit codes, error
  messages), the `kvstore.Store` Python API, and the on-disk directory contents.
- No UI surface: this is a CLI and a library, so there is no `_uiux.md`.

## System Architecture

- **`kvstore/store.py` — `Store`**: owns the connection, the pragma set, the schema, the format-version
  check, and the four operations. The only component that knows SQLite exists.
- **`kvstore/__init__.py`**: re-exports `Store` and the error types; the package's public import surface.
- **`kvstore/__main__.py`**: argument parsing, stdin handling, byte-exact stdout, error-to-exit-code
  mapping. Holds no storage logic and no SQLite call.
- Data flow: `__main__` parses argv → constructs `Store(dir)` → calls one method → maps the result or the
  raised error to stdout/stderr and an exit code → process exits (which releases the connection).
- External interactions: the filesystem only.

## Architectural Boundaries

- `kvstore/__main__.py` imports from `kvstore` (the public surface) and the standard library. It must not
  `import sqlite3`, and must not read or write files in the state directory directly.
- `kvstore/store.py` imports the standard library only. It does not read `sys.argv`, print, or call
  `sys.exit`; it raises.
- `tests/` imports the public surface for behavior, and may inspect the directory's files directly when a
  case is about the on-disk state (pragma values, WAL size, file names).

## Implementation Design

### Core Interfaces

```python
# kvstore/store.py

class KVStoreError(Exception):
    """Base for every error kvstore raises."""

class KeyNotFound(KVStoreError, KeyError):
    """Requested key is absent from the store."""

class InvalidKey(KVStoreError, ValueError):
    """Key is empty or not a string."""

class StoreBusy(KVStoreError):
    """Another process held the write lock past the timeout."""

class IncompatibleStore(KVStoreError):
    """Directory was written by a newer on-disk format version."""

FORMAT_VERSION = 1

class Store:
    def __init__(self, directory: str | os.PathLike, *, timeout: float = 5.0) -> None:
        """Open (creating if needed) the store in `directory`.

        Creating the directory and the database is deferred to the first mutation;
        opening a missing directory read-only yields an empty store and creates nothing.
        """

    def set(self, key: str, value: str) -> None:
        """Store `value` under `key`. Returns only after the write is committed and flushed."""

    def get(self, key: str) -> str:
        """Return the current value for `key`. Raises KeyNotFound if absent."""

    def delete(self, key: str) -> bool:
        """Remove `key`. Returns True if it existed, False otherwise. Durable on return."""

    def list(self) -> list[str]:
        """Return every live key, sorted."""

    def close(self) -> None: ...
    def __enter__(self) -> "Store": ...
    def __exit__(self, *exc: object) -> None: ...
```

Connection setup, in this exact order on a fresh database — `auto_vacuum` is only settable before the
first table exists, and `synchronous` is per-connection so it must be re-applied on every open:

```python
conn = sqlite3.connect(db_path, isolation_level=None, timeout=timeout)
conn.execute("PRAGMA auto_vacuum=INCREMENTAL")   # persistent; must precede schema creation
conn.execute("PRAGMA journal_mode=WAL")          # persistent
conn.execute("PRAGMA synchronous=FULL")          # per connection, every time
conn.execute("PRAGMA busy_timeout=<timeout_ms>")
conn.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY NOT NULL, v BLOB NOT NULL)")
```

`isolation_level=None` (not the 3.12+ `autocommit=` keyword) keeps the package working on the Python 3.11+
range the README promises, and makes each statement its own committed transaction — the ack point.

### Data Models

One table, one row per key:

| Column | Type   | Purpose                                                                          |
| ------ | ------ | -------------------------------------------------------------------------------- |
| `k`    | TEXT   | The key, UTF-8, non-empty, primary key (unique index; lookup and `list` ordering) |
| `v`    | BLOB   | The value, UTF-8-encoded bytes, never NULL                                        |

- A plain rowid table, deliberately **not** `WITHOUT ROWID`: values can be large, and SQLite's guidance is
  that `WITHOUT ROWID` degrades once rows exceed a small fraction of a page, which is the normal case here.
- `v` is BLOB rather than TEXT: the value is encoded to UTF-8 at the boundary and decoded on the way out,
  so a value containing NUL or unusual code points round-trips byte for byte with no dependence on text
  affinity or on how any tool handles embedded NUL.
- `PRAGMA user_version` holds `FORMAT_VERSION`; it is set when the schema is created and checked on every
  open. A larger value raises `IncompatibleStore`.
- No side tables, no JSON columns: the value is opaque to kvstore by definition.

### API Endpoints

Not applicable — the feature ships no HTTP or UDS surface. Its public surfaces are the CLI and the Python
API, both frozen in `_dx.md`.

## Integration Points

None. kvstore talks to the filesystem and to nothing else.

## Impact Analysis

| Component                 | Impact Type | Description and Risk                                                                                                | Required Action                                        |
| ------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| `kvstore/store.py`        | new         | All storage behavior and the durability contract. Highest-risk file in the change.                                    | Implement in task_01; pragma assertions are tests.      |
| `kvstore/__main__.py`     | new         | CLI entry point, exit codes, byte-exact stdout. Risk: swallowing a store error into exit 0 would fake an ack.         | Implement in task_01; one exit-code case per class.     |
| `kvstore/__init__.py`     | modified    | Currently empty; becomes the public import surface (`Store` and the error types).                                     | Re-export only; no logic.                               |
| `tests/test_fumaca.py`    | unaffected  | Package-import smoke test stays valid and keeps passing.                                                              | Do not modify.                                          |
| `Makefile`                | unaffected  | `python3 -m unittest discover -s tests -t .` already finds new `tests/test_*.py` files.                               | Verified by running `make test`; no edit expected.      |
| `README.md`               | modified    | Documents only the golden path today; must show all four verbs and the durability rule.                               | Update in task_01 from the `_dx.md` transcript.         |
| Service's JSON state file | out of scope| Lives in the service repository, not here. It is not read, migrated, or deleted by this change.                        | Covered by Open Question 1.                             |

No breaking changes and no delete targets: the package has no released surface and no existing user state.
The on-disk format is new, so the compatibility obligation is forward-looking only, and it is discharged by
`PRAGMA user_version`: a future format bump either reads version 1 directories or refuses them by name. No
fallback path, no compatibility shim, and no placeholder store implementation is to be added for a format
that does not exist yet.

## Extensibility Integration Plan

Not applicable. This is a standalone Python package: no extension manifests, hooks, skills, tools,
registries, bridges, or MCP sidecars are added or changed. Surfaces checked: the repository contains only
`kvstore/`, `tests/`, `Makefile`, and `README.md`.

## Agent Manageability Plan

The CLI is the whole management surface, and it is complete for an unattended caller: every verb has a
deterministic exit code (0 success, 1 key not found, 2 usage error, 3 store error), failures print one
line to stderr and nothing to stdout, and `list` emits one key per line so it parses without a format
flag. `get` writes the value to stdout with no added bytes, so a script can capture it exactly. State is
discoverable with `list` plus ordinary `ls` on the directory. There is no UI-only capability.

## Config Lifecycle

Not applicable: no `config.toml`, no configuration file, and no environment variables. The only tunable is
the `timeout` argument of `Store`, defaulting to 5 seconds; the CLI does not expose it. Surfaces checked:
the repository has no configuration layer at all.

## Testing Approach

- Framework: `unittest` from the standard library, run by `make test`
  (`python3 -m unittest discover -s tests -t .`). Files under `tests/` named `test_*.py`.
- Fixtures: `tempfile.TemporaryDirectory` per case — every test gets its own state directory and nothing
  is shared between cases. No fakes for the filesystem or for SQLite: faking the storage layer would fake
  the property under test.
- Unit level: the `Store` API against a real temporary directory, including the on-disk assertions (pragma
  values, `user_version`, files present).
- Integration level: crash and concurrency behavior, driven with `subprocess` and `os.kill(SIGKILL)`
  against child processes that use the real package.
- E2E level: `python -m kvstore` invoked exactly as `_dx.md` transcribes it, asserting stdout bytes,
  stderr, and exit codes.
- Environment: a POSIX filesystem and the ability to spawn subprocesses. No network, no services.
- Honest limit: power-loss durability cannot be tested in this suite. It is inherited from SQLite's WAL
  guarantee and verified indirectly by asserting that every connection runs with `synchronous=FULL` and
  `journal_mode=wal` (UT-018, UT-019) — the configuration the guarantee depends on. What *is* tested
  directly is process death, which is the failure mode the incident actually had.
- Every concrete case lives in [`_tests.md`](_tests.md).

## Development Sequencing

### Build Order

1. `Store` and the CLI land together (task_01): the CLI is the contract's entry path, and a `Store`
   without it proves nothing observable. Gate: the durability and verb suites pass, `make test` green.
2. Concurrency and value handling (task_02) build on the frozen `Store` surface: they add a busy timeout
   path, stdin input, and byte-exactness, changing behavior only under contention and at the edges. Gate:
   the concurrency integration cases pass with the task_01 suite still green.
3. Space reclaim and scale (task_03) tune `auto_vacuum`/WAL behavior after the semantics are fixed. Gate:
   the growth cases pass, no behavioral case from earlier tasks changes.

Linear order is deliberate: all three tasks edit `kvstore/store.py`, so they are sequenced by ownership of
that file rather than parallelized on paper.

### Technical Dependencies

CPython 3.11+ with the `sqlite3` module (present in every standard CPython build). Verified on this
machine: Python 3.14.7, SQLite library 3.53.1, `auto_vacuum=INCREMENTAL` and `journal_mode=WAL` both
persist, `synchronous=FULL` applies, and a BLOB containing NUL round-trips. No other dependency.

## Monitoring and Observability

No metrics or log pipeline: the package is a library and a short-lived CLI, and adding a logging layer
would be an unrequested surface. The observable signals are the exit code, the one-line stderr message,
and the directory's file sizes. If the service wants a metric, it times its own `set` calls.

## Technical Considerations

### Key Decisions

- **SQLite over a hand-written append-only log** — see [ADR-001](adrs/adr-001.md).
- **`synchronous=FULL` with one transaction per mutation** — see [ADR-002](adrs/adr-002.md).
- **Plain rowid table, not `WITHOUT ROWID`**: values are large by requirement, and `WITHOUT ROWID` is
  recommended against for large rows. Trade-off: one extra index lookup per read, which is irrelevant at
  this scale. Alternative rejected: `WITHOUT ROWID` for slightly denser small-value storage.
- **`v BLOB` with UTF-8 encoding at the boundary, not `TEXT`**: guarantees a byte-exact round-trip
  regardless of embedded NUL or text affinity. Trade-off: the API must encode and decode explicitly.
  Alternative rejected: `TEXT`, which pushes the round-trip guarantee onto SQLite's text handling.
- **`isolation_level=None` rather than the 3.12+ `autocommit=True` keyword**: keeps the 3.11 floor the
  README states. Trade-off: uses an older, verbose spelling of the same behavior.
- **Silence on success for `set`/`del`**: exit 0 *is* the ack, so a script checks one thing. Alternative
  rejected: printing "ok", which adds output a caller must ignore.
- **`get` writes the value with no trailing newline**: a store that adds a byte to what it was given is
  not a store. Trade-off: shell output runs into the prompt; the operator adds `; echo` when it bothers
  them. Alternative rejected: `print(value)`, which makes `set k "$(get k)"` lossy for values ending in a
  newline.
- **`del` on an absent key exits 1 rather than 0**: the caller can distinguish "was there, now gone" from
  "never existed" without a preceding `get`. The on-disk effect is idempotent either way.
- **Directory created on first write, never on a read**: `get` against a typo'd path reports an empty
  store instead of silently creating one.

### Known Risks

- **Values are materialized in memory** on both `set` and `get`, so a value near the process's memory
  headroom fails at the Python level. Likelihood: low for config/counters/positions; rises if the service
  starts storing payloads. Mitigation: verified to 8 MiB in the default suite (UT-026) and to 64 MiB in
  the opt-in case (IT-008); upgrade path is
  `sqlite3.Connection.blobopen()` for incremental BLOB I/O, available since 3.11, if it is ever needed.
- **A long-lived reader connection can defer WAL checkpoints**, letting `kvstore.db-wal` grow. Likelihood:
  low, because the CLI is short-lived and the service's own connection commits constantly. Mitigation:
  default `wal_autocheckpoint` plus the growth case in task_03 (UT-032).
- **Sustained write contention** from many concurrent processes surfaces as `StoreBusy` after the timeout
  rather than as a queue. Likelihood: low (one service owns the directory). Mitigation: the error is
  explicit and retryable by the caller; exit code 3 distinguishes it from a missing key.
- **The service's cutover from the JSON file** is unspecified (Open Question 1). Risk: the service starts
  reading an empty store and treats it as "no state". Mitigation: decide the cutover before deploying.

## Safety Invariants

1. A mutation is acknowledged only after its transaction has committed on a connection running
   `journal_mode=wal` and `synchronous=FULL`.
2. Every mutation is exactly one transaction; kvstore never leaves a transaction open across a return to
   its caller, and never buffers a write for a later flush.
3. After any process death, the visible content of the store is exactly the set of acknowledged writes —
   no acknowledged write is absent, and no unacknowledged write is present.
4. No operation rewrites the full dataset in place; the largest unit any single write can endanger is the
   pages of that write.
5. Concurrent writers are serialized by SQLite's write lock; a writer that cannot acquire it within the
   timeout fails with `StoreBusy` and writes nothing.
6. Readers never mutate the directory: no truncation, no vacuum, no file creation on any read path.
7. kvstore touches only the database files it created in the directory; any other file is left untouched.
8. A directory whose `user_version` exceeds `FORMAT_VERSION` is refused, never read under version-1 rules.

## File References

### Repo Files

- `kvstore/__init__.py` — currently empty; becomes the public import surface the CLI and tests use.
- `tests/test_fumaca.py` — the existing smoke test; shows the `unittest` style and the import the suite
  already depends on, which must keep passing.
- `Makefile` — defines the only verification command (`make test`) and the discovery flags that new test
  files must satisfy.
- `README.md` — states the Python 3.11+ floor and the standard-library-only constraint this design is
  bound by, and is the doc updated from `_dx.md`.
- `.gitignore` — ignores `__pycache__/`; state directories created by tests live in temp dirs, so nothing
  else needs ignoring.

### External References

None: no vendored source or reference implementation is used.

### Design and Analysis Sources

- [ADR-001](adrs/adr-001.md) — storage engine choice; feeds System Architecture and Implementation Design.
- [ADR-002](adrs/adr-002.md) — durability level and transaction granularity; feeds Safety Invariants.
- SQLite documentation on WAL mode, `PRAGMA synchronous`, `PRAGMA auto_vacuum`, and `WITHOUT ROWID` —
  cited by concept; no path in this repo.

## Assumptions and Defaults

- Keys and values are UTF-8 text. Non-UTF-8 input is a caller error, not a supported case.
- The state directory is owned exclusively by kvstore, as the requester stated; no other program writes
  files into it.
- The database file is named `kvstore.db` inside the given directory; SQLite adds `kvstore.db-wal` and
  `kvstore.db-shm` alongside it.
- `FORMAT_VERSION = 1`, stored in `PRAGMA user_version`.
- Default write-lock timeout: 5 seconds, overridable via `Store(timeout=...)` and not exposed on the CLI.
- Exit codes: 0 success, 1 key not found, 2 usage error, 3 store error.
- `set <key> -` reads the value from stdin, because `ARG_MAX` (~2 MB) would otherwise cap "large values"
  well below what the requester described. Any other literal `-` is the value `-`.
- `list` orders keys by SQLite's default `TEXT` comparison (byte order of the UTF-8 encoding).
- Error messages are Portuguese, matching the repository's existing language, prefixed `kvstore: `.
- The service may use either the CLI or the Python API; both carry the identical durability contract.
- Tests create their directories under `tempfile.TemporaryDirectory`; the repository working tree is never
  used as a state directory.

## Architecture Decision Records

- [ADR-001: SQLite as the storage engine](adrs/adr-001.md) — use the standard library's `sqlite3` instead
  of hand-writing an append-only log with CRCs, recovery, locking, and compaction.
- [ADR-002: Durability by `synchronous=FULL` and one transaction per mutation](adrs/adr-002.md) — pay one
  fsync per write so that the ack means what the service promises its callers.
