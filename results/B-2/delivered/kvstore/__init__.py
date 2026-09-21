"""Armazenamento chave-valor durável em disco, sobre um `sqlite3` local.

Cada operação pública abre uma conexão nova sobre o diretório do store (um processo
por operação, ver design.md), aplica os pragmas de durabilidade e a fecha. A conexão
faz o trabalho de atomicidade, recuperação e travamento entre processos; este módulo
define a política de abertura e as operações públicas (`set`/`get`/`delete`/
`list_keys`).
"""

import os
import sqlite3

_DB_FILENAME = "kvstore.sqlite3"
_BUSY_TIMEOUT_MS = 5000
_JOURNAL_SIZE_LIMIT_BYTES = 64 * 1024 * 1024


def _db_path(directory: str | os.PathLike[str]) -> str:
    return os.path.join(directory, _DB_FILENAME)


def _connect(directory: str | os.PathLike[str]) -> sqlite3.Connection:
    """Abre o store em `directory`, criando o diretório e o esquema sob demanda.

    Idempotente: reabrir um store já existente não recria a tabela nem toca nos
    dados. `auto_vacuum` só é aplicado quando o banco está vazio — é assim que o
    SQLite aceita esse pragma — por isso ele é definido antes da criação da tabela.
    O `PRAGMA auto_vacuum = INCREMENTAL` (forma de atribuição, não de consulta) só
    é emitido quando o valor efetivo ainda não é `2`: emiti-lo incondicionalmente
    em toda abertura, mesmo virando no-op num banco não-vazio, mediu contenção real
    entre conexões (uma escrita contínua via `set` e leituras concorrentes via
    `get`/`list_keys` no mesmo diretório chegaram a levar >2s por chamada e a
    `set` falhar com "database is locked" mesmo com `busy_timeout`) — a forma de
    consulta do pragma é barata e não contende.
    """
    os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(_db_path(directory))
    try:
        auto_vacuum_atual = conn.execute("PRAGMA auto_vacuum").fetchone()[0]
        if auto_vacuum_atual != 2:
            conn.execute("PRAGMA auto_vacuum = INCREMENTAL")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = FULL")
        conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
        conn.execute(f"PRAGMA journal_size_limit = {_JOURNAL_SIZE_LIMIT_BYTES}")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS kv ("
            "key TEXT PRIMARY KEY NOT NULL, "
            "value TEXT NOT NULL"
            ")"
        )
        conn.commit()
    except Exception:
        conn.close()
        raise
    return conn


class KvstoreError(Exception):
    """Erro de domínio do kvstore, nunca uma exceção crua do `sqlite3`."""


class InvalidKeyError(KvstoreError, ValueError):
    """Chave vazia, com quebra de linha ou com NUL, recusada na fronteira de entrada."""


class KeyNotFoundError(KvstoreError, LookupError):
    """Chave sem valor associado no store."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def _validate_key(key: str) -> None:
    if key == "":
        raise InvalidKeyError("chave vazia não é permitida")
    if "\n" in key:
        raise InvalidKeyError("chave não pode conter quebra de linha")
    if "\x00" in key:
        raise InvalidKeyError("chave não pode conter NUL")


def set(directory: str | os.PathLike[str], key: str, value: str) -> None:
    """Grava `key`→`value`, sobrescrevendo um valor anterior (upsert).

    Só retorna depois do `COMMIT`: a garantia de durabilidade vem dos pragmas de
    abertura (D2 em design.md), não de qualquer `fsync` manual aqui.
    """
    _validate_key(key)
    conn = _connect(directory)
    try:
        conn.execute(
            "INSERT INTO kv (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def get(directory: str | os.PathLike[str], key: str) -> str:
    """Devolve o valor de `key`, ou levanta `KeyNotFoundError` se ausente.

    Um diretório inexistente ou sem o arquivo do banco é tratado como store vazio,
    sem criar nada.
    """
    _validate_key(key)
    if not os.path.isfile(_db_path(directory)):
        raise KeyNotFoundError(key)
    conn = _connect(directory)
    try:
        row = conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise KeyNotFoundError(key)
    return row[0]


def delete(directory: str | os.PathLike[str], key: str) -> None:
    """Remove `key`, se existir; idempotente quando a chave já está ausente.

    Dispara `incremental_vacuum` depois da remoção para devolver páginas livres ao
    sistema de arquivos (D3). O `incremental_vacuum` só enxerga como livre uma
    página já refletida no arquivo principal, então a remoção precisa ser
    despejada do WAL para lá primeiro (`wal_checkpoint`) — sem isso, o `DELETE`
    fica preso no WAL e o `incremental_vacuum` não tem o que liberar.
    """
    _validate_key(key)
    conn = _connect(directory)
    try:
        conn.execute("DELETE FROM kv WHERE key = ?", (key,))
        conn.commit()
        # `fetchall()` é obrigatório aqui: sem consumir o cursor, o SQLite não
        # termina de executar o pragma (o checkpoint fica parcial e o vacuum não
        # libera página nenhuma) mesmo depois do `commit()` seguinte.
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
        conn.execute("PRAGMA incremental_vacuum").fetchall()
        conn.commit()
    finally:
        conn.close()


def list_keys(directory: str | os.PathLike[str]) -> list[str]:
    """Devolve as chaves vivas em ordem lexicográfica.

    Um diretório inexistente ou sem o arquivo do banco é tratado como store vazio,
    sem criar nada.
    """
    if not os.path.isfile(_db_path(directory)):
        return []
    conn = _connect(directory)
    try:
        rows = conn.execute("SELECT key FROM kv ORDER BY key").fetchall()
    finally:
        conn.close()
    return [row[0] for row in rows]
