# Design

## Context

See `proposal.md` — Why. The binding constraints for this design:

- Standard library only, Python 3.11+ (`README.md`), `make test` runs `python3 -m unittest discover`.
- `index` runs from cron, frequently, over a large folder where almost nothing changes between runs.
- mtime carries no information (rsync and repo checkouts rewrite it both ways), so the only trustworthy
  change signal is the bytes themselves.
- Today the repository holds only a skeleton: an empty `fidx/__init__.py` and a smoke test.

The consequence that shapes everything below: **every run must read every file**, because deciding a
file is unchanged requires looking at its content. The incremental win therefore has to come from the
work *after* the read — decoding, tokenising, and rewriting index rows — which is where the
per-file cost actually is.

## Goals / Non-Goals

**Goals:**

- Refresh cost proportional to *bytes read* (unavoidable) plus *work on changed files only*.
- A search that never touches the corpus, so query time is independent of folder size.
- Crash-safe refresh with no half-written index and no separate recovery step.
- No configuration, no daemon, no state outside the indexed folder.

**Non-Goals (design level, beyond the proposal's scope exclusions):**

- Parallel or multi-process indexing. A single sequential pass keeps the transaction model trivial.
- Any in-memory cache or server process shared between invocations.
- Guarding against two `index` runs racing on the same folder beyond a clear error (see Risks).

## Decisions

### 1. Staleness signal: SHA-256 of the file bytes, stored per path

Alternatives considered:

- *mtime + size* — the classic incremental trick, and the one the requirements forbid: this corpus
  produces both false "unchanged" (new content, old mtime) and false "changed" (same content, new
  mtime). Rejected outright.
- *size only as a pre-filter* — a differing size proves change, but an equal size proves nothing, so
  every file still has to be read. It saves no I/O and adds a branch. Rejected.
- *BLAKE2b* — faster than SHA-256 on machines without SHA instructions, equally stdlib. Either works;
  SHA-256 is chosen for familiarity, and the digest is an internal detail that a future run can
  change by bumping the schema version and rebuilding.

Digests are computed with `hashlib.file_digest(fh, "sha256")` (3.11+), which streams the file in
chunks and never holds a large file in memory. The digest is stored hex-encoded next to the path.

A changed file is read twice: once streamed for the digest, once for decoding. That is accepted —
it only happens for files that actually changed, which is the rare case by premise. Reading the whole
file into memory to do both from one read would make the common (unchanged) case pay the memory cost.

### 2. Storage: one SQLite database under `<directory>/.fidx/index.sqlite3`

Alternatives considered:

- *A JSON file* — simple, but every refresh rewrites the entire index even when one file changed, and
  every search loads the whole index into memory. That defeats the purpose of the change at the folder
  size described. Rejected.
- *SQLite FTS5* — gives tokenisation and matching for free, but FTS5 is a compile-time-optional
  module, so availability is not guaranteed on an arbitrary Python build; and it solves problems
  (phrase, prefix, ranking) that are explicit non-goals. Rejected.
- *Plain SQLite tables* — chosen. Partial updates touch only the affected rows, lookup by term is an
  index seek, and the transaction gives the atomicity requirement for free rather than through a
  hand-rolled write-temp-and-rename dance.

Schema:

```sql
CREATE TABLE files    (path TEXT PRIMARY KEY, digest TEXT NOT NULL);
CREATE TABLE postings (term TEXT NOT NULL, path TEXT NOT NULL,
                       PRIMARY KEY (term, path)) WITHOUT ROWID;
CREATE INDEX postings_path ON postings(path);
PRAGMA user_version = 1;
```

- `postings` is keyed `(term, path)`, so a search is a range scan on the primary key — no separate
  term index needed, and `WITHOUT ROWID` drops the duplicate row-id copy of what is already the key.
- `postings_path` exists for the delete side: reprocessing a file starts with
  `DELETE FROM postings WHERE path = ?`, which without that index would scan the whole table for each
  changed file.
- `PRAGMA user_version` identifies the schema. A future version mismatch is handled by discarding the
  database and rebuilding from scratch — correct, and cheaper to maintain than migration code for a
  derived artefact that can always be regenerated.
- The folder holds the index, so a copied folder carries its index with it, and there is no global
  state directory to reason about.

### 3. Refresh algorithm: one pass, one transaction

```
open db (creating schema if absent)
seen = {}
for each file in walk(directory):          # skips entries whose name starts with "."
    digest = sha256(file)                  # streamed; unreadable -> warn, keep old row, continue
    seen[path] = digest
    if digest == stored_digest(path): continue          # unchanged: no decode, no writes
    delete postings for path; insert new postings; upsert files row
delete every indexed path not in seen      # removals and moves
commit
```

- A move shows up as one removal plus one addition; with the content already hashed, the addition is
  the normal changed-file path. Detecting the move as such would save a re-tokenise, at the cost of
  digest-keyed bookkeeping for a case that is not in the requirements. Not done.
- The whole pass is one transaction: an interrupted run is rolled back by SQLite's journal, which is
  exactly the "atomic with respect to interruption" requirement, with no code of our own.
- `index_directory()` returns a small stats record (`seen`, `reprocessed`, `removed`, `unreadable`);
  the CLI prints it and tests assert on it. This makes "was this file reprocessed?" an observable
  fact rather than something a test has to infer.

### 4. Tokenisation: `re.findall(r"\w+", text.casefold())`, unique per file

`\w` is Unicode-aware in Python 3, so `orçamento` is one token; `casefold()` handles case-insensitive
matching (and folds more correctly than `lower()`). No stop-word removal, no stemming, no minimum
length: a term the user can `grep` for should be findable, and any filtering would silently lose
matches. The same function normalises the query, which is what keeps index and search consistent —
one function, two callers, so they cannot drift apart.

Decoding uses `errors="replace"`, so a non-UTF-8 dump degrades to partially garbled tokens instead of
failing the run.

### 5. Corpus boundary: skip entries whose name starts with `.`

The index lives in `.fidx/` inside the folder, so it must be excluded anyway; the same rule also keeps
`.git` checkout metadata out of the index, which matters here since the folder is fed by repository
checkouts. One rule, no special cases.

### 6. CLI: `argparse` with the directory as the first positional

`python -m fidx <directory> <command> [...]` puts the directory before the sub-command, which
`argparse` supports directly (positional, then sub-parsers). Exit codes: `0` success (and, for
`search`, at least one match), `1` search with no match — the `grep` convention, so shell callers can
branch — and `2` for usage errors and operational failures such as a missing directory or a missing
index, which is also `argparse`'s own usage-error code.

## Risks / Trade-offs

- **Every run reads every byte; `index` stays I/O-bound.** → Unavoidable given the untrusted mtime;
  it is the floor, not a regression, and it is paid once per cron run instead of once per query. If
  the folder later grows past what the schedule tolerates, the escape hatch is an opt-in
  `--trust-mtime` fast path for subtrees known to be well-behaved — deliberately not built now,
  because it re-introduces exactly the bug this change exists to avoid.
- **Index size can approach corpus size** (one row per unique term/file pair). → `WITHOUT ROWID`
  keeps the posting rows compact; freed pages are reused by SQLite. If disk pressure appears, an
  occasional `VACUUM` is a one-line addition.
- **Two overlapping `index` runs** (cron fires again before the previous finished) → the second
  blocks on the connection timeout and then fails with a clear locked-database error and a non-zero
  exit; the index stays consistent because the loser's transaction is rolled back. A lock file with
  "another run in progress, skipping" is the upgrade if cron overlap becomes routine.
- **Binary files bloat the index with junk tokens.** → Accepted: the stated corpus is text, and the
  `errors="replace"` path keeps the run alive. If dumps turn out to be binary, the cheap fix is the
  classic `grep` heuristic — skip a file whose first block contains a NUL byte.
- **Unreadable file keeps its previous entry** rather than being dropped. → Deliberate: a transient
  permission error should not silently empty the index for that path. The path is reported on stderr
  on every run, so a permanent failure stays visible instead of being swallowed.

## Migration Plan

Greenfield: there is no existing index and no data to migrate. First deployment is the first cron run
of `python -m fidx <dir> index`, which builds the full index; subsequent runs are incremental.
Rollback is `rm -rf <dir>/.fidx` (plus reverting the code) — the index is a derived artefact and
carries nothing that cannot be rebuilt from the folder.

## Open Questions

- Should `search` report a count or a match preview alongside the paths? The requirement is only "in
  which files the term appears", and adding either later changes no stored data — deferrable.
- Is an occasional `VACUUM` (or a `--compact` flag) worth adding once real index sizes are known?
  Answerable after the first weeks of cron runs, and it changes no interface.
