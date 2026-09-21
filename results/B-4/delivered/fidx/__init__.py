"""fidx: content-addressed index and search for a folder of text files."""

import hashlib
import os
import re
import sqlite3
import sys
from urllib.parse import quote

SCHEMA_VERSION = 1
INDEX_DIRNAME = ".fidx"
INDEX_FILENAME = "index.sqlite3"
BUSY_TIMEOUT_SECONDS = 5.0

_SCHEMA = """
CREATE TABLE files (path TEXT PRIMARY KEY, digest TEXT NOT NULL);
CREATE TABLE postings (term TEXT NOT NULL, path TEXT NOT NULL,
                        PRIMARY KEY (term, path)) WITHOUT ROWID;
CREATE INDEX postings_path ON postings(path);
"""


def tokens(text):
    """Return the set of case-folded word tokens in text."""
    return set(re.findall(r"\w+", text.casefold()))


def index_path(directory):
    """Return the path to the index database for directory."""
    return os.path.join(directory, INDEX_DIRNAME, INDEX_FILENAME)


def open_index(directory):
    """Open the index database for directory, creating or rebuilding it as needed.

    A `user_version` that does not match SCHEMA_VERSION belongs to an
    incompatible schema; the derived database is discarded and rebuilt
    rather than migrated.
    """
    os.makedirs(os.path.join(directory, INDEX_DIRNAME), exist_ok=True)
    conn = sqlite3.connect(index_path(directory), timeout=BUSY_TIMEOUT_SECONDS)

    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version != SCHEMA_VERSION:
        conn.executescript(
            "DROP TABLE IF EXISTS files; DROP TABLE IF EXISTS postings;"
        )
        conn.executescript(_SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()

    return conn


def index_directory(directory):
    """Refresh the content-addressed index for directory.

    Walks directory (skipping entries whose name starts with ".", so the
    ".fidx" storage and things like ".git" are never indexed), hashes each
    file's bytes with SHA-256, and reprocesses only files whose digest
    differs from the one stored for that path. Paths no longer present in
    the walk are removed from the index. The whole refresh runs inside a
    single transaction, so an interrupted run leaves the previous index
    untouched.

    Returns a dict with `seen`, `reprocessed`, `removed`, and `unreadable`
    counts.
    """
    conn = open_index(directory)
    seen_paths = set()
    stats = {"seen": 0, "reprocessed": 0, "removed": 0, "unreadable": 0}

    for root, dirnames, filenames in os.walk(directory):
        dirnames[:] = [name for name in dirnames if not name.startswith(".")]
        for filename in filenames:
            if filename.startswith("."):
                continue
            full_path = os.path.join(root, filename)
            path = os.path.relpath(full_path, directory)
            stats["seen"] += 1

            try:
                with open(full_path, "rb") as fh:
                    digest = hashlib.file_digest(fh, "sha256").hexdigest()
            except OSError as exc:
                print(f"fidx: cannot read {path}: {exc}", file=sys.stderr)
                stats["unreadable"] += 1
                seen_paths.add(path)
                continue

            seen_paths.add(path)
            row = conn.execute(
                "SELECT digest FROM files WHERE path = ?", (path,)
            ).fetchone()
            if row is not None and row[0] == digest:
                continue

            with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            conn.execute("DELETE FROM postings WHERE path = ?", (path,))
            conn.executemany(
                "INSERT INTO postings (term, path) VALUES (?, ?)",
                [(term, path) for term in tokens(text)],
            )
            conn.execute(
                "INSERT OR REPLACE INTO files (path, digest) VALUES (?, ?)",
                (path, digest),
            )
            stats["reprocessed"] += 1

    stored_paths = {
        row[0] for row in conn.execute("SELECT path FROM files").fetchall()
    }
    removed_paths = stored_paths - seen_paths
    for path in removed_paths:
        conn.execute("DELETE FROM postings WHERE path = ?", (path,))
        conn.execute("DELETE FROM files WHERE path = ?", (path,))
    stats["removed"] = len(removed_paths)

    conn.commit()
    conn.close()
    return stats


class IndexNotFoundError(Exception):
    """Raised when search runs against a directory that has no index yet."""


def search(directory, term):
    """Return the sorted paths under directory whose indexed content matches term.

    Reads the persistent index only, opened read-only: this never walks directory
    and never writes to the index, so query time does not depend on folder size and
    a search never disturbs a later `index` run's incremental state. term is
    normalised with the same `tokens()` used at index time; when it normalises to
    more than one term, a path must contain all of them to match. A directory with
    no index raises IndexNotFoundError naming the `index` command that builds one;
    a term with no searchable token raises ValueError.
    """
    path = index_path(directory)
    if not os.path.isfile(path):
        raise IndexNotFoundError(
            f"{directory!r} has no index yet; "
            f"run `python -m fidx {directory} index` first"
        )

    query_terms = tokens(term)
    if not query_terms:
        raise ValueError(f"search term {term!r} contains no searchable token")

    uri = f"file:{quote(os.path.abspath(path))}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        matches = None
        for query_term in query_terms:
            rows = conn.execute(
                "SELECT path FROM postings WHERE term = ?", (query_term,)
            ).fetchall()
            term_paths = {row[0] for row in rows}
            matches = term_paths if matches is None else matches & term_paths
    finally:
        conn.close()

    return sorted(matches)
