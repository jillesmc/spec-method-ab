import hashlib
import re
from pathlib import Path
from typing import Iterator
import os


def percorrer(raiz: Path) -> Iterator[Path]:
    """Caminhos relativos a `raiz` dos arquivos regulares elegíveis (regra 4), em qualquer ordem."""
    raiz = Path(raiz)
    for dirpath, dirnames, filenames in os.walk(raiz, followlinks=False):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for nome in filenames:
            if nome.startswith("."):
                continue
            caminho = Path(dirpath) / nome
            if not caminho.is_file():
                continue
            yield Path(caminho.relative_to(raiz).as_posix())


def ler(caminho: Path) -> tuple[str, str] | None:
    """(digest_sha256, texto) do arquivo; None quando não decodifica como UTF-8 ou não pode ser lido."""
    try:
        with open(caminho, "rb") as arquivo:
            dados = arquivo.read()
    except OSError:
        return None
    try:
        texto = dados.decode("utf-8")
    except UnicodeDecodeError:
        return None
    digest = hashlib.sha256(dados).hexdigest()
    return digest, texto


def tokenizar(texto: str) -> set[str]:
    """Palavras Unicode (`\\w+`) em minúsculas. Mesma função para conteúdo e para consulta."""
    return set(re.findall(r"\w+", texto.lower()))
