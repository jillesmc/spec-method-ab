"""kvstore: armazenamento chave-valor durável em disco, um arquivo por chave.

Cada chave vira um arquivo `k.<chave percent-encoded>` no diretório do store. `set`
escreve num temporário, faz `fsync` do arquivo, publica com `os.replace` e faz
`fsync` do diretório antes de retornar — só assim sucesso significa persistido.
"""

import os
import io
import tempfile
from urllib.parse import quote, unquote

_PREFIXO = "k."
_LIMITE_CHAVE_CODIFICADA = 253
_TAMANHO_BLOCO = 65536


def _caminho(diretorio, chave):
    if chave == "":
        raise ValueError("chave nao pode ser vazia")
    for caractere, nome in (("\n", "\\n"), ("\r", "\\r"), ("\0", "\\0")):
        if caractere in chave:
            raise ValueError(f"chave nao pode conter o caractere {nome}")
    codificada = quote(chave, safe="")
    if len(codificada) > _LIMITE_CHAVE_CODIFICADA:
        raise ValueError(
            f"forma codificada da chave tem {len(codificada)} bytes, "
            f"acima do limite de {_LIMITE_CHAVE_CODIFICADA}"
        )
    return os.path.join(diretorio, _PREFIXO + codificada)


def _fsync_dir(caminho):
    fd = os.open(caminho, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def set_stream(diretorio, chave, entrada):
    alvo = _caminho(diretorio, chave)
    if not os.path.isdir(diretorio):
        os.makedirs(diretorio, exist_ok=True)
        pai = os.path.dirname(os.path.abspath(diretorio)) or os.sep
        _fsync_dir(pai)
    fd, tmp = tempfile.mkstemp(dir=diretorio, prefix=".tmp-")
    try:
        try:
            while True:
                bloco = entrada.read(_TAMANHO_BLOCO)
                if not bloco:
                    break
                if isinstance(bloco, str):
                    bloco = bloco.encode("utf-8")
                os.write(fd, bloco)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, alvo)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    _fsync_dir(diretorio)


def set(diretorio, chave, valor):
    set_stream(diretorio, chave, io.BytesIO(valor.encode("utf-8")))


def get_stream(diretorio, chave, saida):
    caminho = _caminho(diretorio, chave)
    try:
        with open(caminho, "rb") as arquivo:
            while True:
                bloco = arquivo.read(_TAMANHO_BLOCO)
                if not bloco:
                    break
                saida.write(bloco)
    except FileNotFoundError as exc:
        raise KeyError(chave) from exc


def get(diretorio, chave):
    saida = io.BytesIO()
    get_stream(diretorio, chave, saida)
    return saida.getvalue().decode("utf-8")


def delete(diretorio, chave):
    caminho = _caminho(diretorio, chave)
    try:
        os.unlink(caminho)
    except FileNotFoundError as exc:
        raise KeyError(chave) from exc
    _fsync_dir(diretorio)


def keys(diretorio):
    try:
        nomes = os.listdir(diretorio)
    except FileNotFoundError:
        return []
    return sorted(
        unquote(nome[len(_PREFIXO):])
        for nome in nomes
        if nome.startswith(_PREFIXO)
    )
