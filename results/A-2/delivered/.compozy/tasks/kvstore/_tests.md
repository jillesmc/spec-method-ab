# Test Specification: kvstore

Canonical test contract for kvstore. Companion to `_spec.md`.
Derived from `_user_stories.md` (behavior), `_spec.md` Part II (components), and `_dx.md` (CLI journeys).
There is no UI surface, so there are no browser journeys.

## Strategy

- Framework and harness: `unittest` from the standard library, discovered by the existing
  `make test` → `python3 -m unittest discover -s tests -t .`. No third-party test dependency, at any level.
- Fixtures: one `tempfile.TemporaryDirectory` per test case; no state directory is ever shared between
  cases and the repository working tree is never used as one. Child processes are spawned with
  `subprocess` / `os.fork` against those temp directories.
- Fakes: none. The filesystem and SQLite *are* the subject — faking either would fake the property under
  test. The only shortcut taken anywhere is bulk-seeding a large store in one transaction (IT-009), where
  the case is about read behavior, not about the durable write path.
- Conventions: files under `tests/` named `test_*.py`; helpers live in `tests/apoio.py`, which discovery
  ignores. Test names state the behavior, and each case asserts one observable thing.
- Runtime budget: `make test` stays in the low seconds. The only case that would break that (a 64 MiB
  round trip, IT-008) is skipped unless `KVSTORE_SLOW_TESTS=1` is set, and says so when it skips.

### What this suite does not prove

Power-loss and kernel-panic durability cannot be tested here. It is inherited from SQLite's WAL guarantee,
and what the suite verifies is (a) the configuration that guarantee depends on — `journal_mode=wal` and
`synchronous=FULL` asserted on live connections in UT-018 and UT-019 — and (b) directly, by SIGKILL, the
failure mode the incident actually had: process death. No case in this file should be read as evidence
about power loss.

## Coverage Matrix

| Source        | Behavior                                    | Unit                        | Integration     | E2E               |
| ------------- | ------------------------------------------- | --------------------------- | --------------- | ----------------- |
| US-001        | Durable write                               | UT-001, UT-002, UT-015      | IT-001          | E2E-001           |
| US-001.EC-1   | Empty key rejected                          | UT-010                      | —               | E2E-005           |
| US-001.EC-2   | Key with newline/NUL rejected               | UT-011                      | —               | E2E-005           |
| US-001.EC-3   | Value with newline/NUL/non-ASCII            | UT-013                      | —               | —                 |
| US-001.EC-4   | Empty value                                 | UT-012                      | —               | —                 |
| US-001.EC-5   | Large value from stdin                      | —                           | —               | E2E-006           |
| US-001.EC-6   | Path is a regular file                      | UT-016                      | —               | —                 |
| US-001.EC-7   | Directory not writable                      | UT-017                      | —               | —                 |
| US-001.EC-8   | Repeated identical set is a no-op           | UT-003                      | —               | —                 |
| US-002        | Byte-exact read                             | UT-001, UT-013              | —               | E2E-001, E2E-007  |
| US-002.EC-1   | Missing key                                 | UT-004                      | —               | E2E-002           |
| US-002.EC-2   | Deleted key                                 | UT-005                      | —               | —                 |
| US-002.EC-3   | Read of a non-existent directory            | UT-009                      | —               | E2E-008           |
| US-003        | Delete reports existence, durably           | UT-005                      | IT-002          | E2E-001           |
| US-003.EC-1   | Delete of an absent key                     | UT-006                      | —               | E2E-003           |
| US-003.EC-2   | Delete twice                                | UT-006                      | —               | —                 |
| US-004        | Sorted key listing                          | UT-007, UT-005              | —               | E2E-001           |
| US-004.EC-1   | Empty store lists nothing                   | UT-008                      | —               | E2E-008           |
| US-004.EC-2   | Keys with spaces and non-ASCII              | —                           | —               | E2E-009           |
| US-004.EC-3   | 100 000 keys listed                         | —                           | IT-009          | —                 |
| US-005        | Acked writes survive a kill                 | UT-014                      | IT-001, IT-002  | —                 |
| US-005.EC-1   | Kill mid-write of a large value             | —                           | IT-003          | —                 |
| US-005.EC-2   | Repeated kill/reopen cycles                 | —                           | IT-004          | —                 |
| US-005.EC-3   | Kill between two writes                     | —                           | IT-003          | —                 |
| US-006        | Opens after a crash with no repair step     | UT-018, UT-019              | IT-002          | —                 |
| US-006.EC-1   | Newer on-disk format refused                | UT-020                      | —               | —                 |
| US-006.EC-2   | Unrelated file untouched                    | UT-022                      | —               | —                 |
| US-006.EC-3   | Corrupt database reported, not hidden       | UT-021                      | —               | —                 |
| US-007        | Concurrent writers and readers              | —                           | IT-006, IT-007  | —                 |
| US-007.EC-1   | Write lock held past the timeout            | UT-027, UT-028              | —               | —                 |
| US-007.EC-2   | Two writers on one key                      | —                           | IT-007          | —                 |
| US-007.EC-3   | Readers never modify the directory          | UT-029                      | —               | —                 |
| US-008        | Large values, growth tracks live data       | UT-026, UT-032              | IT-008          | —                 |
| US-008.EC-1   | Space reclaimed after mass delete           | UT-030, UT-031              | —               | —                 |
| US-008.EC-2   | Journal stays bounded                       | UT-032                      | —               | —                 |
| US-008.EC-3   | Single read does not scan the store         | —                           | IT-009          | —                 |
| US-009        | Python API with the same guarantee          | UT-023, UT-025              | —               | —                 |
| US-009.EC-1   | Exception inside the `with` block           | UT-023                      | —               | —                 |
| US-009.EC-2   | Never closed, then killed                   | —                           | IT-005          | —                 |
| US-009.EC-3   | Two Store objects, one directory            | UT-024                      | —               | —                 |
| `Store`       | Storage behavior and durability config      | UT-001–UT-032               | IT-001–IT-009   | —                 |
| `__main__`    | Argument parsing, exit codes, byte-exact IO | —                           | —               | E2E-001–E2E-009   |
| Package import| `import kvstore` keeps working              | existing `tests/test_fumaca.py::TestPacote::test_pacote_importa` | — | — |
| Usage surface | Bare invocation and unknown command         | —                           | —               | E2E-004           |

## Unit Tests

### `Store` — basic operations (Spec: Part II Implementation Design)

- **UT-001** (happy): `Store.set("modo", "rapido")` on a fresh directory, then `Store.get("modo")` returns
  `"rapido"`.
- **UT-002** (state): `set("modo", "rapido")` then `set("modo", "lento")` — `get("modo")` returns
  `"lento"` and `list()` returns `["modo"]` (one row, not two).
- **UT-003** (idempotency): `set("k", "v")` twice — `get("k")` is `"v"` and `list()` has exactly one entry.
- **UT-004** (error): `get("ausente")` on a store holding other keys raises `KeyNotFound`.
- **UT-005** (state): `set("k", "v")`, `delete("k")` returns `True`; then `get("k")` raises `KeyNotFound`
  and `list()` does not contain `"k"`.
- **UT-006** (idempotency): `delete("nunca")` on an empty store returns `False`; after `set("k","v")`,
  `delete("k")` returns `True` and a second `delete("k")` returns `False`, with `list() == []` both times.
- **UT-007** (happy): writing `"b"`, `"a"`, `"c"` in that order — `list()` returns `["a", "b", "c"]`.
- **UT-008** (boundary): `Store(<path that does not exist>).list()` returns `[]` and
  `os.path.exists(path)` is still `False` afterwards.
- **UT-009** (error): `Store(<path that does not exist>).get("k")` raises `KeyNotFound` and creates
  nothing on disk.
- **UT-010** (error): `set("", "v")` raises `InvalidKey`; the directory is not created and no row exists.
- **UT-011** (error): `set("a\nb", "v")` and `set("a\x00b", "v")` each raise `InvalidKey`; `list()` is
  still `[]`.
- **UT-012** (boundary): `set("vazio", "")` succeeds; `get("vazio")` returns `""` and `list()` contains
  `"vazio"`.
- **UT-013** (boundary): `set("t", "com\nquebras\x00e acentuação 日本語")` then `get("t")` returns that
  exact string, character for character.
- **UT-014** (state): `set("a","1")`, `set("b","2")`, `delete("a")`, `set("c","3")`, `close()`; a new
  `Store` on the same directory returns `list() == ["b","c"]` and `get("c") == "3"`.
- **UT-015** (happy): first `set` on a missing directory creates it and leaves `kvstore.db`,
  `kvstore.db-wal` and `kvstore.db-shm` in it and nothing else.
- **UT-016** (error): `Store(<path of a regular file>).set("k","v")` raises `KVStoreError` whose message
  contains the path; the file's content is unchanged.
- **UT-017** (error): a directory with mode `0o500` — `set("k","v")` raises `KVStoreError` carrying the
  operating-system reason. Skipped when the test runs as root, with the skip reason stated.

### `Store` — durability configuration (Spec: Safety Invariants 1–2; ADR-002)

- **UT-018** (state): on a live `Store`, `PRAGMA journal_mode` reports `wal` — both on the connection that
  created the database and on a connection that reopened it.
- **UT-019** (state): on both of those connections, `PRAGMA synchronous` reports `2` (`FULL`). This is the
  regression guard for the one setting the durability promise depends on.
- **UT-020** (boundary): `PRAGMA user_version` equals `FORMAT_VERSION` (1) after creation; when it is set
  to `2` behind the store's back, opening raises `IncompatibleStore`, the message names version 2, and the
  database file's size and mtime are unchanged afterwards.
- **UT-021** (error): after overwriting the first 100 bytes of `kvstore.db` with zeros, opening raises
  `KVStoreError` mentioning corruption — never an empty store and never a silent success.
- **UT-022** (state): with `anotacao.txt` present in the state directory, a full `set`/`get`/`delete`/
  `list` round leaves that file's bytes and mtime untouched.

### `Store` — Python API surface (Spec: Part II Core Interfaces; US-009)

- **UT-023** (happy): `with Store(d) as s: s.set("k","v")` — after the block, a new `Store` reads `"v"`;
  and when the block body raises `RuntimeError`, the exception propagates, the store is closed, and a
  write made before the raise is still readable.
- **UT-024** (state): two `Store` objects open on the same directory in one process — a `set` through the
  first is returned by a `get` through the second.
- **UT-025** (error): `KeyNotFound` is a subclass of both `KVStoreError` and `KeyError`; `InvalidKey` is a
  subclass of both `KVStoreError` and `ValueError`; `from kvstore import Store, KVStoreError, KeyNotFound,
  InvalidKey, StoreBusy, IncompatibleStore, FORMAT_VERSION` all resolve.

### `Store` — concurrency and large values (Spec: Safety Invariants 5–6)

- **UT-026** (boundary): an 8 MiB value written and read back through the API is identical, and
  `len(get(k))` equals what was written.
- **UT-027** (concurrency): with a separate connection holding `BEGIN IMMEDIATE` on the same database,
  `Store(d, timeout=0.1).set("k","v")` raises `StoreBusy`; after the other transaction rolls back, the
  same call succeeds and `"k"` was not written by the failed attempt.
- **UT-028** (boundary): `PRAGMA busy_timeout` on a live `Store(d, timeout=2.5)` connection reports
  `2500`.
- **UT-029** (state): record `kvstore.db` size and mtime, run `get` and `list` (including on a store whose
  last writer was killed), and find both unchanged — a read path never truncates, vacuums, or writes.

### `Store` — growth over time (Spec: Part II Data Models; US-008)

- **UT-030** (boundary): `PRAGMA auto_vacuum` reports `2` (`INCREMENTAL`) on a freshly created store and
  on a reopened one — it is only settable before the schema exists, so this pins the creation order.
- **UT-031** (state): write 200 keys holding 64 KiB each, record `kvstore.db` size, delete all 200, then
  find `list() == []` and `kvstore.db` reduced to under 25% of the recorded peak.
- **UT-032** (boundary): rewrite one 64 KiB key 2 000 times; afterwards `kvstore.db` and `kvstore.db-wal`
  together stay under 8 MiB — growth tracks the live value, not the 2 000 writes — and `get` returns the
  last value written.

## Integration Tests

### Crash and restart (US-005, US-006)

- **IT-001**: a child process opens the store, calls `set("posicao","1042")`, writes a byte to a pipe to
  signal the ack, and is then sent `SIGKILL` by the parent; a fresh `Store` in the parent returns
  `"1042"`.
- **IT-002**: a child writes 50 keys with distinct values, acking each, and is `SIGKILL`ed; the parent
  reopens the directory — all 50 keys are present with exactly their values, no repair call is made, and a
  second `list()` returns the same set as the first.
- **IT-003**: a child writes `ancora=ok`, then starts writing a 32 MiB value for `grande`, and is
  `SIGKILL`ed while that write is in flight; reopening succeeds, `get("ancora")` returns `"ok"`, and
  `"grande"` is either absent or holds a complete previous value — never a truncated one.
- **IT-004**: ten consecutive cycles of (spawn child → write key `n` → ack → `SIGKILL` → reopen); after
  each cycle `list()` equals exactly the keys acked so far.
- **IT-005**: a child creates a `Store`, writes two keys, and is `SIGKILL`ed without ever calling
  `close()`; both keys are readable afterwards.

### Concurrent processes (US-007)

- **IT-006**: eight `python -m kvstore <dir> set chave-<i> valor-<i>` processes started together — all
  eight exit 0, and a subsequent `list` returns all eight keys with their exact values.
- **IT-007**: one process rewrites `alvo` between `"A"*1024` and `"B"*1024` in a loop for one second while
  another process reads `alvo` in a loop — every read returns one of those two exact strings and no read
  fails; the final value is one of the two.
- **IT-008**: a 64 MiB value piped into `python -m kvstore <dir> set grande -`, then read back through
  `get` and compared byte for byte. Skipped unless `KVSTORE_SLOW_TESTS=1`, with the reason printed.

### Scale (US-004.EC-3, US-008.EC-3)

- **IT-009**: seed 100 000 keys in a single bulk transaction (fixture shortcut: the durable write path is
  covered elsewhere, this case is about reads) — `list()` returns 100 000 keys in sorted order, and
  `EXPLAIN QUERY PLAN` for the `get` statement shows an index search on the primary key, not a table scan.

## End-to-End Tests

Every case below runs `python -m kvstore` as a subprocess and asserts stdout bytes, stderr, and the exit
code. The invocations are the `_dx.md` transcripts verbatim.

### Golden path (US-001, US-002, US-003, US-004)

- **E2E-001**: `set posicao 1042` → exit 0, empty stdout; `set modo rapido` → exit 0; `list` → stdout
  exactly `b"modo\nposicao\n"`; `get posicao` → stdout exactly `b"1042"` (no trailing newline);
  `del modo` → exit 0; `list` → stdout exactly `b"posicao\n"`.

### Failure surface (US-002.EC-1, US-003.EC-1, US-001.EC-1, US-001.EC-2)

- **E2E-002**: `get ausente` → exit 1, stdout empty, stderr exactly
  `kvstore: chave nao encontrada: ausente\n`.
- **E2E-003**: `del ausente` → exit 1, stdout empty, stderr exactly
  `kvstore: chave nao encontrada: ausente\n`.
- **E2E-004**: `python -m kvstore` with no arguments → exit 2 with the usage block naming all four
  commands on stdout; `python -m kvstore <dir> dump` → exit 2 with
  `kvstore: comando desconhecido: dump\n` on stderr.
- **E2E-005**: `set "" valor` → exit 2, stderr `kvstore: chave vazia\n`; `set $'a\nb' valor` → exit 2,
  stderr `kvstore: chave nao pode conter quebra de linha ou NUL\n`; the directory holds no keys after
  either.

### Value fidelity (US-001.EC-5, US-002.AC-2)

- **E2E-006**: a 2 MiB value piped into `set relatorio -`, then `get relatorio` — stdout equals the input
  bytes exactly, with nothing added.
- **E2E-007**: `printf 'com\nquebras\n'` piped into `set texto -`, then `get texto` — stdout is exactly
  `b"com\nquebras\n"`: one trailing newline, the one that was stored.

### Empty and unusual stores (US-004.EC-1, US-004.EC-2, US-002.EC-3)

- **E2E-008**: `list` and `get k` against a directory that does not exist → `list` exits 0 with empty
  stdout, `get` exits 1, and the directory still does not exist afterwards.
- **E2E-009**: keys `com espaco`, `acentuação` and `日本語` written, then `list` → stdout is those three
  keys, sorted, one per line, decoded as UTF-8 without escaping.

## Coverage Decisions

- The package-import invariant is already owned by `tests/test_fumaca.py::TestPacote::test_pacote_importa`
  and gets no new ID; the file is not modified.
- `make test` itself is the gate, not a test case: every task's acceptance includes running it.
- The durability promise is owned at two layers on purpose — UT-018/UT-019 own the *configuration* that
  makes it true, IT-001–IT-005 own the *observable* survival of process death. Neither substitutes for the
  other: a pragma regression would pass the kill tests on a machine with a fast page cache.
- Multi-key atomicity has no case because it is an explicit Non-Goal; IT-003's "first present, second
  absent" assertion pins the behavior that replaces it.
- Power loss has no case, by the limit stated under Strategy.
- Every error class in the `_dx.md` error table has an owner: exit 1 (E2E-002, E2E-003), exit 2 (E2E-004,
  E2E-005), exit 3 in its four flavors (UT-016 not-a-directory, UT-017 unwritable, UT-027 busy, UT-020
  incompatible, UT-021 corrupt). The exit-3 CLI mapping is exercised through the `Store` exceptions the
  CLI translates, since the translation itself is a one-line table.
