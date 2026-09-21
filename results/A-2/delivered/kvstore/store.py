"""Durable key-value store backed by SQLite (WAL, synchronous=FULL)."""

from __future__ import annotations

import os
import sqlite3
import time

FORMAT_VERSION = 1

_DB_FILENAME = "kvstore.db"


class KVStoreError(Exception):
    """Base for every error kvstore raises."""


class KeyNotFound(KVStoreError, KeyError):
    """Requested key is absent from the store."""

    def __str__(self) -> str:
        # KeyError.__str__ reprs its argument; a plain message reads better.
        return self.args[0] if self.args else ""


class InvalidKey(KVStoreError, ValueError):
    """Key is empty, or contains a newline or NUL."""


class StoreBusy(KVStoreError):
    """Another process held the write lock past the timeout."""


class IncompatibleStore(KVStoreError):
    """Directory was written by a newer on-disk format version."""


def _validate_key(key: str) -> None:
    if not key:
        raise InvalidKey("chave vazia")
    if "\n" in key or "\x00" in key:
        raise InvalidKey("chave nao pode conter quebra de linha ou NUL")


def _is_busy_message(message: str) -> bool:
    lowered = message.lower()
    return "locked" in lowered or "busy" in lowered


class Store:
    def __init__(self, directory: "str | os.PathLike[str]", *, timeout: float = 5.0) -> None:
        self._directory = os.fspath(directory)
        self._timeout = timeout
        self._conn: "sqlite3.Connection | None" = None

    def _db_path(self) -> str:
        return os.path.join(self._directory, _DB_FILENAME)

    def _open_existing(self) -> "sqlite3.Connection | None":
        """Open a connection to an existing store, or None if there is nothing to open."""
        if self._conn is not None:
            return self._conn
        db_path = self._db_path()
        if not os.path.isdir(self._directory) or not os.path.exists(db_path):
            return None
        self._conn = self._connect(create=False)
        return self._conn

    def _open_for_write(self) -> sqlite3.Connection:
        """Open (creating the directory and schema if needed) a connection for mutation."""
        if self._conn is not None:
            return self._conn
        if os.path.exists(self._directory) and not os.path.isdir(self._directory):
            raise KVStoreError(f"{self._directory} nao e um diretorio")
        try:
            os.makedirs(self._directory, exist_ok=True)
        except OSError as exc:
            raise KVStoreError(f"erro ao abrir {self._directory}: {exc.strerror}") from exc
        db_path = self._db_path()
        fresh = not os.path.exists(db_path)
        try:
            fd = os.open(db_path, os.O_RDWR | os.O_CREAT, 0o644)
            os.close(fd)
        except OSError as exc:
            raise KVStoreError(f"erro ao abrir {self._directory}: {exc.strerror}") from exc
        self._conn = self._connect(create=fresh)
        return self._conn

    def _connect(self, *, create: bool) -> sqlite3.Connection:
        db_path = self._db_path()
        try:
            conn = sqlite3.connect(db_path, isolation_level=None, timeout=self._timeout)
        except sqlite3.OperationalError as exc:
            raise KVStoreError(f"erro ao abrir {self._directory}: {exc}") from exc

        def _pragma_bootstrap(sql: str, deadline: float) -> None:
            # auto_vacuum and journal_mode transitions take an exclusive lock
            # to rewrite the file header, and SQLite does not run the
            # busy_timeout handler for that particular lock: two processes
            # racing to bootstrap the same brand-new database file can get
            # "database is locked" instantly instead of after busy_timeout.
            # Retry it ourselves, bounded by the same timeout, so this one
            # lock acquisition waits like every other one does.
            while True:
                try:
                    conn.execute(sql)
                    return
                except sqlite3.OperationalError as exc:
                    if not _is_busy_message(str(exc)) or time.monotonic() >= deadline:
                        raise
                    time.sleep(0.005)

        try:
            deadline = time.monotonic() + self._timeout
            if create:
                _pragma_bootstrap("PRAGMA auto_vacuum=INCREMENTAL", deadline)
            _pragma_bootstrap("PRAGMA journal_mode=WAL", deadline)
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute(f"PRAGMA busy_timeout={int(self._timeout * 1000)}")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY NOT NULL, v BLOB NOT NULL)"
            )
            if create:
                conn.execute(f"PRAGMA user_version={FORMAT_VERSION}")
            self._check_version(conn)
        except IncompatibleStore:
            conn.close()
            raise
        except sqlite3.DatabaseError as exc:
            conn.close()
            message = str(exc)
            if _is_busy_message(message):
                raise StoreBusy(
                    f"banco ocupado por outro processo (timeout {self._timeout}s)"
                ) from exc
            raise KVStoreError(f"banco corrompido em {db_path}: {exc}") from exc
        return conn

    def _check_version(self, conn: sqlite3.Connection) -> None:
        (version,) = conn.execute("PRAGMA user_version").fetchone()
        if version > FORMAT_VERSION:
            raise IncompatibleStore(
                f"formato do diretorio e versao {version}, esta versao le ate {FORMAT_VERSION}"
            )

    def _execute_mutation(self, conn: sqlite3.Connection, sql: str, params: tuple) -> sqlite3.Cursor:
        try:
            return conn.execute(sql, params)
        except sqlite3.OperationalError as exc:
            if _is_busy_message(str(exc)):
                raise StoreBusy(
                    f"banco ocupado por outro processo (timeout {self._timeout}s)"
                ) from exc
            raise

    def set(self, key: str, value: str) -> None:
        _validate_key(key)
        conn = self._open_for_write()
        self._execute_mutation(
            conn,
            "INSERT INTO kv (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v",
            (key, value.encode("utf-8")),
        )

    def get(self, key: str) -> str:
        _validate_key(key)
        conn = self._open_existing()
        if conn is None:
            raise KeyNotFound(f"chave nao encontrada: {key}")
        row = conn.execute("SELECT v FROM kv WHERE k = ?", (key,)).fetchone()
        if row is None:
            raise KeyNotFound(f"chave nao encontrada: {key}")
        return row[0].decode("utf-8")

    def delete(self, key: str) -> bool:
        _validate_key(key)
        conn = self._open_existing()
        if conn is None:
            return False
        cur = self._execute_mutation(conn, "DELETE FROM kv WHERE k = ?", (key,))
        deleted = cur.rowcount > 0
        if deleted:
            # Runs after the DELETE has committed (autocommit mode), and only when a row
            # was actually removed, so each call has at most one row's worth of freshly
            # freed pages to release, never a backlog. auto_vacuum=INCREMENTAL only
            # marks pages free; without this, kvstore.db never shrinks (Safety Invariant
            # 6 keeps this off the read path).
            # fetchall() is required: sqlite3 steps the pragma's VM once per call and it
            # frees one page per step, so an un-drained cursor only ever releases one page
            # no matter the (omitted, here) page-count argument.
            self._execute_mutation(conn, "PRAGMA incremental_vacuum", ()).fetchall()
        return deleted

    def list(self) -> list[str]:
        conn = self._open_existing()
        if conn is None:
            return []
        rows = conn.execute("SELECT k FROM kv ORDER BY k").fetchall()
        return [row[0] for row in rows]

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
