# Spec Delta

## Purpose

Answers "which files contain this term?" from the persistent index instead of re-reading the folder,
with a plain, scriptable command-line contract so it can replace `grep -r` in shell use and in
scripts.

## ADDED Requirements

### Requirement: Search command reports the matching files

The system SHALL provide the command `python -m fidx <directory> search <term>`, which reports the
files of `<directory>` in which `<term>` occurs. Each matching file SHALL be printed on its own line
on standard output, as a path relative to `<directory>`, with no other decoration. The order of the
reported paths SHALL be deterministic for a given index state.

#### Scenario: Term occurs in two of three files

- **WHEN** the directory holds three indexed files and the term occurs in two of them
- **AND** `python -m fidx <directory> search <term>` runs
- **THEN** exactly those two paths are printed, one per line, relative to `<directory>`

#### Scenario: Term occurs several times in the same file

- **WHEN** the term occurs more than once in a single file
- **THEN** that file is reported exactly once

### Requirement: Search answers from the index without rescanning the corpus

A search SHALL be answered from the stored index alone, without reading the indexed files, and SHALL
NOT modify the index.

#### Scenario: Corpus files are unreadable at search time

- **WHEN** the directory has been indexed and its files are subsequently made unreadable
- **AND** a search runs for a term present in them
- **THEN** the matching paths are still reported

#### Scenario: Search leaves the index untouched

- **WHEN** a search runs against an indexed directory
- **THEN** a subsequent `index` run reports no file as reprocessed

### Requirement: Matching is case-insensitive and consistent with indexing

Search SHALL apply to the query term the same normalisation that indexing applies to file content, so
that a term matches regardless of the letter case used in the file or in the query. A query that
normalises to more than one term SHALL report only the files that contain all of those terms.

#### Scenario: Query case differs from the file's case

- **WHEN** a file contains `Orçamento` and the query is `orçamento` (or the reverse)
- **THEN** that file is reported

#### Scenario: Query normalises to more than one term

- **WHEN** the query contains two words and only one file contains both of them
- **THEN** only that file is reported

### Requirement: Exit status distinguishes no-match from error

The search command SHALL exit `0` when at least one file matches, and non-zero with empty standard
output when no file matches, so callers can branch on the result. An invalid invocation SHALL exit
with a status distinct from the no-match status and SHALL explain the problem on standard error.

#### Scenario: No file contains the term

- **WHEN** a search runs for a term that occurs in no indexed file
- **THEN** nothing is printed on standard output and the command exits non-zero

#### Scenario: Search on a directory that was never indexed

- **WHEN** a search runs against a directory that has no index
- **THEN** the command explains on standard error that the directory must be indexed first, names the
  `index` command, and exits with a status distinct from the no-match status

#### Scenario: Empty search term

- **WHEN** a search runs with a term that normalises to no searchable term at all
- **THEN** the command reports the problem on standard error and exits with the invalid-invocation
  status
