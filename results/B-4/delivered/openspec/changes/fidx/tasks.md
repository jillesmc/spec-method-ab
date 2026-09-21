# Tasks

Layout: the library lives in `fidx/__init__.py` (tokenising, storage, refresh, search) and the CLI in
`fidx/__main__.py`; tests go under `tests/`. Every task below is verified by `make test` unless it
names something else.

## 1. Storage and tokenising

- [ ] 1.1 Implement `tokens(text)` — `re.findall(r"\w+", text.casefold())` returned as a set — and
      verify with a test covering case folding, an accented word (`Orçamento` → `orçamento`), digits,
      and punctuation as a separator
- [ ] 1.2 Implement opening the index at `<directory>/.fidx/index.sqlite3`: create the directory and
      the `files` / `postings` schema plus the `postings_path` index when absent, set
      `PRAGMA user_version = 1`, and connect with a busy timeout; verify a test that opens a fresh
      directory twice and finds the second open reusing the same database with the schema intact
- [ ] 1.3 Make a `user_version` mismatch discard and rebuild the database instead of failing; verify
      with a test that writes a database stamped with a different version and then indexes
      successfully

## 2. Content-addressed refresh

- [ ] 2.1 Implement the directory walk that skips every entry whose name starts with `.`; verify with
      a test that a file under `.git/` and the `.fidx/` storage itself are never indexed
- [ ] 2.2 Implement `index_directory(directory)`: stream a SHA-256 per file with
      `hashlib.file_digest`, skip files whose digest matches the stored one, and re-tokenise and
      rewrite postings for the rest, all inside a single transaction; return stats
      (`seen`, `reprocessed`, `removed`, `unreadable`). Verify a first run indexes every file and
      reports `reprocessed == seen`
- [ ] 2.3 Delete from the index every path not seen in the walk; verify with a test that a deleted
      file is reported as removed and that a term unique to it then matches nothing
- [ ] 2.4 Report unreadable files on stderr, count them, keep their previous entry, and continue;
      verify with a test that chmods one file to unreadable and asserts the run exits `0`, indexes
      the others, and leaves the old entry in place (skip the test when running as root, where the
      chmod has no effect)
- [ ] 2.5 **Timestamp trap A**: verify with a test that a file whose content is replaced and whose
      mtime is then set to the past (`os.utime`) is reprocessed, that a term from the new content
      matches it, and that a term from the old content no longer does
- [ ] 2.6 **Timestamp trap B**: verify with a test that touching a file's mtime to now without
      changing its bytes yields `reprocessed == 0` on the next run
- [ ] 2.7 Verify with a test that a file moved to a new path with identical content is reported only
      at its new path after a refresh

## 3. Search

- [ ] 3.1 Implement `search(directory, term)` returning matching paths relative to the directory,
      sorted, each path once, using the same `tokens()` normalisation on the query and requiring all
      query terms when it yields more than one; verify with tests for the two-of-three-files case,
      the repeated-term-in-one-file case, a case-mismatched query, and a two-word query
- [ ] 3.2 Make search read only the index: it opens the database read-only, never walks the folder,
      and never writes; verify with a test that makes the indexed files unreadable, still gets the
      matches, and finds the following `index` run reporting `reprocessed == 0`
- [ ] 3.3 Make search on a directory with no index raise a distinct error naming the `index` command;
      verify with a test asserting the message and the error path

## 4. CLI

- [ ] 4.1 Implement `fidx/__main__.py` with `argparse`: positional `directory`, then `index` and
      `search <term>` sub-commands; verify with a test that runs `python -m fidx <dir> index` and
      `python -m fidx <dir> search <term>` through `subprocess` and asserts the matching paths on
      stdout, one per line
- [ ] 4.2 Print the refresh report (files seen, reprocessed, removed) on stdout from `index`; verify
      with a subprocess test asserting the counts for a run with exactly one changed file
- [ ] 4.3 Wire the exit codes — `0` on success or at least one match, `1` for a search with no match
      and empty stdout, `2` for a missing directory, a missing index, or a query that normalises to
      no term — and verify each with a subprocess test asserting the status and the stream the
      message goes to

## 5. Wrap-up

- [ ] 5.1 Update `README.md` with the two commands, the index location, and the exit codes; verify by
      running the commands exactly as documented against a scratch directory
- [ ] 5.2 Run `make test` and confirm the whole suite passes, including the pre-existing
      `tests/test_fumaca.py`
