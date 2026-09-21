"""Indice de busca incremental por conteudo sobre uma pasta de arquivos de texto."""

import hashlib
import os
import re
import sqlite3
from typing import NamedTuple

_TOKEN_RE = re.compile(r"\w+")
_SCHEMA_VERSION = 1
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS postings (
    term TEXT NOT NULL,
    path TEXT NOT NULL,
    PRIMARY KEY (term, path)
);
"""


class Resumo(NamedTuple):
    reprocessados: int
    inalterados: int
    removidos: int


def _varrer(diretorio: str) -> list[str]:
    """Caminhos relativos (com '/') dos arquivos regulares, ignorando entradas ocultas."""
    caminhos = []
    for raiz, subdirs, arquivos in os.walk(diretorio):
        subdirs[:] = [d for d in subdirs if not d.startswith(".")]
        for nome in arquivos:
            if nome.startswith("."):
                continue
            completo = os.path.join(raiz, nome)
            if os.path.islink(completo) or not os.path.isfile(completo):
                continue
            relativo = os.path.relpath(completo, diretorio).replace(os.sep, "/")
            caminhos.append(relativo)
    return sorted(caminhos)


def _tokenizar(texto: str) -> list[str]:
    return _TOKEN_RE.findall(texto.casefold())


def _conectar(diretorio: str) -> sqlite3.Connection:
    fidx_dir = os.path.join(diretorio, ".fidx")
    try:
        os.makedirs(fidx_dir, exist_ok=True)
    except PermissionError as erro:
        raise PermissionError(f"sem permissao para escrever em {fidx_dir!r}: {erro}") from erro
    conexao = sqlite3.connect(os.path.join(fidx_dir, "index.sqlite3"), timeout=30)
    versao = conexao.execute("PRAGMA user_version").fetchone()[0]
    if versao != _SCHEMA_VERSION:
        conexao.executescript("DROP TABLE IF EXISTS files; DROP TABLE IF EXISTS postings;")
        conexao.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
    conexao.executescript(_SCHEMA_SQL)
    conexao.commit()
    return conexao


def index(diretorio: str) -> Resumo:
    conexao = _conectar(diretorio)
    try:
        existentes = dict(conexao.execute("SELECT path, hash FROM files"))
        atuais = _varrer(diretorio)
        vistos = set()
        reprocessados = inalterados = ilegiveis = 0
        for caminho in atuais:
            vistos.add(caminho)
            with open(os.path.join(diretorio, caminho), "rb") as arquivo:
                bruto = arquivo.read()
            digest = hashlib.sha256(bruto).hexdigest()
            if existentes.get(caminho) == digest:
                inalterados += 1
                continue
            try:
                texto = bruto.decode("utf-8")
            except UnicodeDecodeError:
                if caminho in existentes:
                    with conexao:
                        conexao.execute("DELETE FROM postings WHERE path = ?", (caminho,))
                        conexao.execute("DELETE FROM files WHERE path = ?", (caminho,))
                    ilegiveis += 1
                continue
            termos = set(_tokenizar(texto))
            with conexao:
                conexao.execute("DELETE FROM postings WHERE path = ?", (caminho,))
                conexao.executemany(
                    "INSERT INTO postings (term, path) VALUES (?, ?)",
                    [(termo, caminho) for termo in termos],
                )
                conexao.execute(
                    "INSERT INTO files (path, hash) VALUES (?, ?) "
                    "ON CONFLICT(path) DO UPDATE SET hash = excluded.hash",
                    (caminho, digest),
                )
            reprocessados += 1
        sumidos = existentes.keys() - vistos
        for caminho in sumidos:
            with conexao:
                conexao.execute("DELETE FROM files WHERE path = ?", (caminho,))
                conexao.execute("DELETE FROM postings WHERE path = ?", (caminho,))
        return Resumo(reprocessados, inalterados, len(sumidos) + ilegiveis)
    finally:
        conexao.close()


def search(diretorio: str, termo: str) -> list[str]:
    termos = _tokenizar(termo)
    if len(termos) != 1:
        raise ValueError(f"termo de busca deve normalizar para uma unica palavra: {termo!r}")
    caminho_banco = os.path.join(diretorio, ".fidx", "index.sqlite3")
    if not os.path.exists(caminho_banco):
        raise FileNotFoundError(f"{diretorio!r} nunca foi indexado; rode 'index' antes de buscar")
    conexao = sqlite3.connect(caminho_banco, timeout=30)
    try:
        linhas = conexao.execute(
            "SELECT path FROM postings WHERE term = ? ORDER BY path", (termos[0],)
        )
        return [linha[0] for linha in linhas]
    finally:
        conexao.close()
