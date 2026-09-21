"""Mapa chave-valor duravel, guardado num diretorio, sobre sqlite3."""

import os
import sqlite3
import time

NOME_ARQUIVO = "kvstore.sqlite3"
ESPERA_MS = 5000

SQL_SET = "INSERT INTO kv VALUES (?, ?) ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor"


def _iniciar_com_retentativa(con):
    # A primeira troca para WAL e a criacao da tabela num arquivo novo competem por um lock
    # exclusivo momentaneo; quando dois processos abrem o mesmo diretorio pela primeira vez ao
    # mesmo tempo, essa contencao especifica pode devolver "database is locked" sem passar pelo
    # busy handler do busy_timeout (efeito de inicializacao do arquivo, confirmado sem nenhum
    # codigo deste pacote envolvido). Retentar manualmente pelo mesmo teto de ESPERA_MS fecha
    # essa lacuna e preserva a invariante de espera limitada seguida de erro, nunca travamento.
    prazo = time.monotonic() + ESPERA_MS / 1000
    while True:
        try:
            con.execute("PRAGMA journal_mode = WAL")  # persistente no arquivo
            con.execute(
                "CREATE TABLE IF NOT EXISTS kv (chave TEXT PRIMARY KEY, valor TEXT NOT NULL)"
            )
            return
        except sqlite3.OperationalError as erro:
            if "locked" not in str(erro).lower() and "busy" not in str(erro).lower():
                raise
            if time.monotonic() >= prazo:
                raise
            time.sleep(0.01)


def _conectar(caminho):
    # isolation_level=None: autocommit explicito; funciona de 3.11 em diante.
    # Connection.autocommit so existe a partir do 3.12 e nao pode ser usado aqui.
    con = sqlite3.connect(caminho, isolation_level=None)
    # busy_timeout primeiro: os demais comandos abaixo (setup de journal, criacao de tabela)
    # tambem podem contender com outro processo abrindo o mesmo diretorio agora, e sem o
    # timeout ja armado essa contencao vira "database is locked" imediato em vez de espera.
    con.execute(f"PRAGMA busy_timeout = {ESPERA_MS}")
    _iniciar_com_retentativa(con)
    con.execute("PRAGMA synchronous = FULL")  # POR CONEXAO: sem isto, cai para NORMAL
    return con


def _validar_chave(chave):
    if not isinstance(chave, str):
        raise TypeError(f"chave deve ser str, recebido {type(chave).__name__}")
    if chave == "":
        raise ValueError("chave nao pode ser vazia")


class Store:
    """Mapa duravel de texto para texto, guardado num diretorio."""

    def __init__(self, diretorio):
        """Cria o diretorio se preciso, abre a conexao e garante o esquema."""
        os.makedirs(diretorio, exist_ok=True)
        self._con = _conectar(os.path.join(diretorio, NOME_ARQUIVO))

    def set(self, chave, valor):
        """Grava. Retorna apenas depois que o dado esta sincronizado em disco."""
        _validar_chave(chave)
        self._con.execute(SQL_SET, (chave, valor))

    def get(self, chave):
        """Devolve o valor, ou None se a chave nao existe."""
        _validar_chave(chave)
        linha = self._con.execute("SELECT valor FROM kv WHERE chave = ?", (chave,)).fetchone()
        return linha[0] if linha is not None else None

    def delete(self, chave):
        """Apaga. Devolve True se a chave existia, False caso contrario."""
        _validar_chave(chave)
        cursor = self._con.execute("DELETE FROM kv WHERE chave = ?", (chave,))
        return cursor.rowcount > 0

    def keys(self):
        """Todas as chaves, em ordem crescente."""
        linhas = self._con.execute("SELECT chave FROM kv ORDER BY chave").fetchall()
        return [linha[0] for linha in linhas]

    def close(self):
        self._con.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
