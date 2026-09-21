# Spec Delta

## Purpose

Keeps a persistent, incrementally refreshed index of the text files in a directory, deciding what is
stale from file content rather than from filesystem timestamps, so a frequent scheduled refresh only
reprocesses what actually changed and never misses a change that arrived with a misleading mtime.

## ADDED Requirements

### Requirement: Index command

The system SHALL provide the command `python -m fidx <directory> index`, which creates the index for
`<directory>` on first run and refreshes it on later runs. The command SHALL exit with status `0`
when the refresh completes, and with a non-zero status and a message on standard error when the
target directory does not exist or is not a directory.

#### Scenario: First run on a directory with no index

- **WHEN** `python -m fidx <directory> index` runs against a directory that has never been indexed
- **THEN** every regular text file under the directory (at any depth) is added to the index
- **AND** the command exits with status `0`

#### Scenario: Target directory does not exist

- **WHEN** `python -m fidx <directory> index` runs and `<directory>` does not exist
- **THEN** no index is created
- **AND** the command writes an error message naming the directory to standard error and exits
  non-zero

### Requirement: Staleness is decided by content, never by timestamps

The system SHALL decide whether a file needs reprocessing by comparing a cryptographic digest of the
file's current bytes against the digest recorded for that path in the index. Modification time, file
size, and any other filesystem metadata SHALL NOT be used to decide that a file is unchanged or
changed.

#### Scenario: Content changed but modification time is older than the previous run

- **WHEN** an indexed file's content is replaced with different content and its modification time is
  set to a time earlier than the previous index run
- **AND** `python -m fidx <directory> index` runs
- **THEN** that file is reprocessed and the index reflects its new content
- **AND** a term present only in the new content finds that file, while a term present only in the
  old content no longer finds it

#### Scenario: Modification time changed but content is identical

- **WHEN** an indexed file's modification time is updated to the current time while its bytes are
  left unchanged
- **AND** `python -m fidx <directory> index` runs
- **THEN** that file is not reprocessed
- **AND** the run's report counts it as unchanged

#### Scenario: Unchanged directory between two runs

- **WHEN** `python -m fidx <directory> index` runs twice with no file content changed in between
- **THEN** the second run reprocesses no file
- **AND** search results after the second run are identical to those after the first

### Requirement: New and removed files are reconciled on every refresh

Each refresh SHALL add files that appeared under the directory since the previous run and SHALL
remove from the index every path that no longer exists on disk, so that search never reports a file
that is gone.

#### Scenario: File added since the previous run

- **WHEN** a new file is created under an already-indexed directory and `index` runs
- **THEN** searching for a term contained in that new file reports it

#### Scenario: File deleted since the previous run

- **WHEN** an indexed file is deleted from disk and `index` runs
- **THEN** searching for a term that occurred only in that file reports no file
- **AND** the deleted path is absent from every search result

#### Scenario: File moved to a new path with unchanged content

- **WHEN** an indexed file is renamed or moved within the directory and `index` runs
- **THEN** searching for a term in that file reports the new path only

### Requirement: Index refresh is atomic with respect to interruption

An interrupted refresh SHALL NOT leave the index in a partially updated or unreadable state. If a
refresh does not complete, the index SHALL remain exactly as it was before that refresh, and the next
refresh SHALL bring it up to date.

#### Scenario: Refresh interrupted part-way

- **WHEN** an `index` run is interrupted before completion
- **THEN** a subsequent `search` still answers from the previous complete index without error
- **AND** a subsequent `index` run completes and reflects all current content

### Requirement: Index storage is self-contained and excluded from the corpus

The index SHALL be stored under the indexed directory itself, in a fixed location that requires no
configuration and no argument beyond `<directory>`, and SHALL persist between runs. The index's own
storage files SHALL NOT be indexed and SHALL NOT appear in search results, and neither SHALL any
entry whose name begins with `.`.

#### Scenario: Index storage is not part of the corpus

- **WHEN** `index` runs and then `search` is given a term that occurs inside the index's own storage
  files
- **THEN** no path belonging to the index storage is reported

#### Scenario: Hidden entries are not part of the corpus

- **WHEN** the directory contains entries whose name begins with `.` (for example a `.git` checkout
  directory) and `index` runs
- **THEN** no file under such an entry is indexed or reported by search

#### Scenario: Index survives between separate process invocations

- **WHEN** `index` runs in one process and `search` runs in a later, separate process
- **THEN** the search is answered from the index written by the earlier run, with no re-reading of
  the corpus required

### Requirement: Refresh reports what it did

An `index` run SHALL report, on standard output, how many files were seen, how many were reprocessed
because their content changed or they were new, and how many were removed from the index.

#### Scenario: Report after a refresh with one changed file

- **WHEN** exactly one file's content changed since the previous run and `index` runs
- **THEN** the report states that one file was reprocessed and that the remaining files were
  unchanged

### Requirement: An unreadable file does not abort the refresh

A file that cannot be read SHALL NOT abort the run. The system SHALL report the affected path on
standard error and continue with the remaining files. Files whose bytes are not valid UTF-8 SHALL be
indexed on a best-effort basis rather than rejected.

#### Scenario: One file cannot be read

- **WHEN** one file under the directory cannot be opened for reading and `index` runs
- **THEN** the run reports that path on standard error, indexes every other file, and exits `0`
- **AND** the previously recorded entry for that path is left untouched rather than deleted
