import sqlite3
from collections.abc import Iterable
from pathlib import Path

NOME_ARQUIVO_INDICE = ".fidx.sqlite3"
SCHEMA_VERSION = "1"
TIMEOUT_CONEXAO = 2.0


class IndiceEmUso(Exception):
    """Outra execução já mantém o índice em escrita (BEGIN IMMEDIATE bloqueado)."""


class Indice:
    def __init__(self, conexao: sqlite3.Connection) -> None:
        self._conexao = conexao

    @classmethod
    def abrir(cls, raiz: Path, *, criar: bool) -> "Indice":
        caminho = raiz / NOME_ARQUIVO_INDICE
        if not caminho.exists():
            if not criar:
                raise FileNotFoundError(str(caminho))
            return cls._criar(caminho)
        conexao = sqlite3.connect(caminho, isolation_level=None, timeout=TIMEOUT_CONEXAO)
        try:
            versao = cls._ler_schema_version(conexao)
        except Exception:
            conexao.close()
            raise
        if versao != SCHEMA_VERSION:
            conexao.close()
            if not criar:
                raise FileNotFoundError(str(caminho))
            caminho.unlink()
            return cls._criar(caminho)
        return cls(conexao)

    @classmethod
    def _criar(cls, caminho: Path) -> "Indice":
        conexao = sqlite3.connect(caminho, isolation_level=None, timeout=TIMEOUT_CONEXAO)
        try:
            conexao.execute("PRAGMA journal_mode=WAL")
            conexao.execute("CREATE TABLE meta (chave TEXT PRIMARY KEY, valor TEXT)")
            conexao.execute(
                "CREATE TABLE arquivos (caminho TEXT PRIMARY KEY, digest TEXT NOT NULL)"
            )
            conexao.execute(
                "CREATE TABLE termos (termo TEXT NOT NULL, caminho TEXT NOT NULL, "
                "PRIMARY KEY (termo, caminho))"
            )
            conexao.execute("CREATE INDEX termos_caminho ON termos(caminho)")
            conexao.execute(
                "INSERT INTO meta (chave, valor) VALUES ('schema_version', ?)", (SCHEMA_VERSION,)
            )
        except Exception:
            conexao.close()
            raise
        return cls(conexao)

    @staticmethod
    def _ler_schema_version(conexao: sqlite3.Connection) -> str | None:
        try:
            linha = conexao.execute(
                "SELECT valor FROM meta WHERE chave = 'schema_version'"
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        return linha[0] if linha else None

    def digests(self) -> dict[str, str]:
        linhas = self._conexao.execute("SELECT caminho, digest FROM arquivos").fetchall()
        return {caminho: digest for caminho, digest in linhas}

    def gravar(self, caminho: str, digest: str, termos: set[str]) -> None:
        self._conexao.execute(
            "INSERT INTO arquivos (caminho, digest) VALUES (?, ?) "
            "ON CONFLICT(caminho) DO UPDATE SET digest = excluded.digest",
            (caminho, digest),
        )
        self._conexao.execute("DELETE FROM termos WHERE caminho = ?", (caminho,))
        self._conexao.executemany(
            "INSERT INTO termos (termo, caminho) VALUES (?, ?)",
            [(termo, caminho) for termo in termos],
        )

    def remover(self, caminhos: Iterable[str]) -> None:
        linhas = [(caminho,) for caminho in caminhos]
        self._conexao.executemany("DELETE FROM arquivos WHERE caminho = ?", linhas)
        self._conexao.executemany("DELETE FROM termos WHERE caminho = ?", linhas)

    def buscar(self, termos: set[str]) -> list[str]:
        if not termos:
            return []
        marcadores = ",".join("?" for _ in termos)
        linhas = self._conexao.execute(
            f"SELECT caminho FROM termos WHERE termo IN ({marcadores}) "
            "GROUP BY caminho HAVING COUNT(DISTINCT termo) = ? ORDER BY caminho",
            (*termos, len(termos)),
        ).fetchall()
        return [caminho for (caminho,) in linhas]

    def close(self) -> None:
        self._conexao.close()

    def __enter__(self) -> "Indice":
        try:
            self._conexao.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc):
                raise IndiceEmUso(str(exc)) from exc
            raise
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        if exc_type is None:
            self._conexao.execute("COMMIT")
        else:
            self._conexao.execute("ROLLBACK")
