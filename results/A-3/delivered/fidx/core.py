"""Nucleo do fidx: varredura, conteudo, armazenamento e as operacoes index/search.

Este modulo nao imprime, nao le sys.argv e nao chama sys.exit: devolve dados ou
levanta excecao. fidx/__main__.py traduz isso em saida e exit code.
"""

import hashlib
import os
import re
import sqlite3
from pathlib import PurePath
from typing import Callable, Iterator

SCHEMA_VERSION = 1
INDEX_NAME = ".fidx.sqlite3"
BUSY_TIMEOUT_S = 30.0

_BLOCK_SIZE = 1024 * 1024
_TOKEN_RE = re.compile(r"\w+")


class FidxError(Exception):
    """Base de todo erro de dominio do fidx."""


class NotADirectory(FidxError):
    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(path)


class IndexMissing(FidxError):
    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(path)


class EmptyTerm(FidxError):
    def __init__(self, term: str) -> None:
        self.term = term
        super().__init__(term)


class IndexBusy(FidxError):
    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(path)


class IndexCreateError(FidxError):
    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"{path}: {reason}")


def tokenize(text: str) -> list[str]:
    """minusculas + re.findall(r"\\w+"): 'Orcamento, 2026' -> ['orcamento', '2026']"""
    return _TOKEN_RE.findall(text.lower())


def iter_files(root: str) -> Iterator[str]:
    """Caminhos relativos posix, ordem estavel; pula entradas com '.' inicial e symlinks."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                continue
            rel = os.path.relpath(full, root)
            yield PurePath(rel).as_posix()


def file_digest(path: str) -> str:
    """sha256 hex, lido em blocos de 1 MiB."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(_BLOCK_SIZE), b""):
            digest.update(block)
    return digest.hexdigest()


def read_text(path: str) -> str:
    with open(path, "rb") as f:
        data = f.read()
    return data.decode("utf-8", errors="ignore")


def _index_path(root: str) -> str:
    return os.path.join(root, INDEX_NAME)


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    if row is not None and row[0] != str(SCHEMA_VERSION):
        conn.executescript("DROP TABLE IF EXISTS files; DROP TABLE IF EXISTS postings;")
        conn.execute("DELETE FROM meta WHERE key = 'schema_version'")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS files (
          path   TEXT PRIMARY KEY,
          sha256 TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS postings (
          term TEXT NOT NULL,
          path TEXT NOT NULL,
          PRIMARY KEY (term, path)
        ) WITHOUT ROWID;
        CREATE INDEX IF NOT EXISTS postings_path ON postings(path);
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )


def open_index(root: str, create: bool) -> sqlite3.Connection:
    path = _index_path(root)
    if create:
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(path, timeout=BUSY_TIMEOUT_S)
            conn.execute("PRAGMA journal_mode=WAL")
            _ensure_schema(conn)
            conn.commit()
        except sqlite3.OperationalError as exc:
            if conn is not None:
                conn.close()
            if "locked" in str(exc).lower():
                raise IndexBusy(path) from exc
            raise IndexCreateError(path, str(exc)) from exc
        return conn
    if not os.path.exists(path):
        raise IndexMissing(path)
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=BUSY_TIMEOUT_S)
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    except sqlite3.OperationalError as exc:
        conn.close()
        raise IndexMissing(path) from exc
    if row is None or row[0] != str(SCHEMA_VERSION):
        conn.close()
        raise IndexMissing(path)
    return conn


def known_files(conn: sqlite3.Connection) -> dict[str, str]:
    """Mapa {path: sha256} gravado no indice, em uma consulta."""
    return {row[0]: row[1] for row in conn.execute("SELECT path, sha256 FROM files")}


def replace_file(conn: sqlite3.Connection, rel: str, digest: str, tokens: list[str]) -> None:
    conn.execute("DELETE FROM postings WHERE path = ?", (rel,))
    conn.execute(
        "INSERT INTO files (path, sha256) VALUES (?, ?) "
        "ON CONFLICT(path) DO UPDATE SET sha256 = excluded.sha256",
        (rel, digest),
    )
    if tokens:
        conn.executemany(
            "INSERT OR IGNORE INTO postings (term, path) VALUES (?, ?)",
            ((term, rel) for term in set(tokens)),
        )


def remove_missing(conn: sqlite3.Connection, vistos: set[str]) -> int:
    known = {row[0] for row in conn.execute("SELECT path FROM files")}
    missing = known - vistos
    if not missing:
        return 0
    conn.executemany("DELETE FROM files WHERE path = ?", ((p,) for p in missing))
    conn.executemany("DELETE FROM postings WHERE path = ?", ((p,) for p in missing))
    return len(missing)


def index_dir(
    root: str, on_pulado: Callable[[str, str], None] | None = None
) -> tuple[int, int, int]:
    """(total_no_indice, reindexados, removidos); uma transacao; ilegivel -> pulado + aviso."""
    if not os.path.isdir(root):
        raise NotADirectory(root)
    conn = open_index(root, create=True)
    try:
        with conn:
            conhecidos = known_files(conn)
            vistos: set[str] = set()
            reindexados = 0
            for rel in iter_files(root):
                full = os.path.join(root, rel)
                try:
                    digest = file_digest(full)
                    mudou = conhecidos.get(rel) != digest  # unico criterio (ADR-001)
                    texto = read_text(full) if mudou else None
                except OSError as exc:
                    if rel in conhecidos:
                        # ja estava no indice: leitura falhou, mas o arquivo
                        # continua no disco e nao deve ser tratado como removido
                        vistos.add(rel)
                    if on_pulado is not None:
                        on_pulado(rel, exc.strerror or str(exc))
                    continue
                if mudou:
                    replace_file(conn, rel, digest, tokenize(texto))
                    reindexados += 1
                vistos.add(rel)
            removidos = remove_missing(conn, vistos)
    finally:
        conn.close()
    return len(vistos), reindexados, removidos


def search(root: str, term: str) -> list[str]:
    """Caminhos relativos posix, ordenados, sem repeticao; [] quando nao ha ocorrencia."""
    if not os.path.isdir(root):
        raise NotADirectory(root)
    tokens = tokenize(term)
    if not tokens:
        raise EmptyTerm(term)
    conn = open_index(root, create=False)
    try:
        matches: set[str] | None = None
        for token in tokens:
            rows = {row[0] for row in conn.execute("SELECT path FROM postings WHERE term = ?", (token,))}
            matches = rows if matches is None else (matches & rows)
            if not matches:
                return []
        return sorted(matches) if matches else []
    finally:
        conn.close()
