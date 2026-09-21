# Proposal

## Why

Finding a term in a large folder of text files today means `grep -r`, which rescans and re-reads
every byte on every query and is slow at that folder's size. A persistent index makes queries cheap,
but only pays off if the periodic (cron) refresh does not redo the whole folder each run — almost
nothing changes between runs. The complication is that these files arrive by rsync and by repository
checkout, so **modification time is not a usable change signal**: files come back with old timestamps
after their content changed, and with fresh timestamps without any change. Change detection therefore
has to be decided by content.

## What Changes

- New `fidx` package with a `python -m fidx <directory> <command>` CLI, standard library only.
- `index` command: walks the directory, and updates a persistent index stored alongside the data.
  Refresh is incremental and **content-addressed**: each file's bytes are hashed (SHA-256) and
  compared with the hash recorded in the index. Only files whose hash differs (and files not yet in
  the index) are re-tokenized and have their index entries rewritten. File mtime and size are never
  consulted as change signals.
- `index` also reconciles removals: paths in the index that no longer exist on disk are dropped, so
  searches never report files that are gone.
- `search` command: reports the files in which the term occurs, one path per line.
- Index refresh is transactional: a run interrupted part-way (cron kill, machine reboot) leaves the
  previous consistent index in place rather than a half-written one.
- Test suite under `tests/` covering the timestamp traps explicitly (changed content with an older
  mtime must be reindexed; touched mtime with identical content must not be reprocessed), run by the
  existing `make test`.

### Assumption worth stating

Because mtime cannot be trusted, an `index` run must **read** every file to hash it; there is no
correct way to skip a file unseen. "Only what changed is reprocessed" is therefore scoped to the
expensive half of the work — decoding, tokenizing and rewriting index entries — which happens only
for files whose content hash actually moved. Hashing is a sequential byte read with no per-token
allocation, i.e. roughly the cost of the `grep -r` this replaces, but paid once per cron run instead
of once per query.

## Capabilities

### New Capabilities

- `content-index`: building and incrementally refreshing a persistent index of a directory of text
  files, where staleness is decided by file content rather than by filesystem metadata, including
  reconciliation of deleted files and crash-safe refresh.
- `content-search`: querying that index for a term and reporting the files that contain it, with a
  scriptable command-line contract (output shape and exit codes).

### Modified Capabilities

None — this is the project's first capability set.

## Impact

- **Code**: the `fidx/` package gains the indexing, storage and search logic plus a `__main__.py` CLI
  entry point; `fidx/__init__.py` is currently an empty placeholder. New tests under `tests/`; the
  existing `tests/test_fumaca.py` smoke test stays valid.
- **Dependencies**: none added. Python standard library only — `sqlite3` for index storage,
  `hashlib` for content hashing, `argparse`, `os`, `re`, `unittest`.
- **On-disk artifacts**: the `index` command writes an index directory inside the indexed folder
  (`<directory>/.fidx/`). This is new state in the user's data folder and is excluded from indexing
  and from search results.
- **Operations**: the cron entry stays `python -m fidx <dir> index`; no configuration file, no daemon.
- **Out of scope**: phrase/prefix/regex/fuzzy search, ranking or relevance ordering, line numbers or
  match snippets, concurrent index runs against the same directory, and non-text (binary) corpora.
