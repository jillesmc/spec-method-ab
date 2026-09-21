"""Referencia CUIDADOSA do store: o caminho que um plano deveria achar.

Log append-only com registro emoldurado e CRC, mais compactacao por rename
atomico. Nao e' esperto nem otimizado: e' so o desenho que responde ao
requisito do enunciado ("quando responde gravei, tem que estar la depois do
restart").

Existe para CALIBRAR a suite: tem que passar nas tres camadas. Se ela falhar
em INVARIANTE, a suite esta cobrando coisa impossivel e e' injusta.

Formato de registro, tudo big-endian:

    op(1) | klen(4) | vlen(4) | crc32(4) | chave | valor

O CRC cobre op+klen+vlen+chave+valor. Leitura para no primeiro registro que
nao fecha: cauda torta de morte no meio da gravacao vira cauda ignorada, nao
arquivo perdido.
"""

import os
import struct
import sys
import zlib

LOG = "log.dat"
TMP = "log.tmp"
CABECALHO = struct.Struct(">cIII")
LIMITE_COMPACTACAO = 4 * 1024 * 1024


def _log(diretorio):
    return os.path.join(diretorio, LOG)


def _moldar(op, chave, valor):
    c, v = chave.encode("utf-8"), valor.encode("utf-8")
    corpo = op + struct.pack(">II", len(c), len(v)) + c + v
    return CABECALHO.pack(op, len(c), len(v), zlib.crc32(corpo)) + c + v


def ler_tudo(diretorio):
    """Devolve (dados, bytes_lidos). Para na primeira moldura quebrada."""
    dados = {}
    caminho = _log(diretorio)
    try:
        bruto = open(caminho, "rb").read()
    except FileNotFoundError:
        return dados, 0
    pos = 0
    while pos + CABECALHO.size <= len(bruto):
        op, klen, vlen, crc = CABECALHO.unpack_from(bruto, pos)
        fim = pos + CABECALHO.size + klen + vlen
        if fim > len(bruto) or op not in (b"S", b"D"):
            break  # cauda torta: morte no meio da gravacao
        c = bruto[pos + CABECALHO.size:pos + CABECALHO.size + klen]
        v = bruto[pos + CABECALHO.size + klen:fim]
        corpo = op + struct.pack(">II", klen, vlen) + c + v
        if zlib.crc32(corpo) != crc:
            break  # registro corrompido: idem
        chave = c.decode("utf-8", "replace")
        if op == b"S":
            dados[chave] = v.decode("utf-8", "replace")
        else:
            dados.pop(chave, None)
        pos = fim
    return dados, pos


def anexar(diretorio, op, chave, valor):
    os.makedirs(diretorio, exist_ok=True)
    fd = os.open(_log(diretorio), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, _moldar(op, chave, valor))
        os.fsync(fd)
    finally:
        os.close(fd)


def compactar_se_precisar(diretorio, dados, lidos):
    """Reescreve so o que esta vivo, e troca por rename atomico. Se morrer no
    meio, o log antigo continua inteiro: o .tmp e' entulho, nao perda."""
    if lidos < LIMITE_COMPACTACAO:
        return
    vivo = sum(len(c) + len(v) + CABECALHO.size for c, v in dados.items())
    if lidos < 2 * vivo:
        return
    tmp = os.path.join(diretorio, TMP)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        for chave, valor in dados.items():
            os.write(fd, _moldar(b"S", chave, valor))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, _log(diretorio))


def principal(argv):
    if len(argv) < 2:
        print("uso: python -m kvstore <diretorio> <set|get|del|list> [...]", file=sys.stderr)
        return 2
    diretorio, comando = argv[0], argv[1]
    resto = argv[2:]

    if os.path.exists(diretorio) and not os.path.isdir(diretorio):
        print(f"nao e' um diretorio: {diretorio}", file=sys.stderr)
        return 2

    try:
        dados, lidos = ler_tudo(diretorio)
    except OSError as erro:
        print(f"nao consegui ler o store: {erro}", file=sys.stderr)
        return 3

    if comando == "set":
        if len(resto) != 2:
            print("uso: set <chave> <valor>", file=sys.stderr)
            return 2
        anexar(diretorio, b"S", resto[0], resto[1])
        dados[resto[0]] = resto[1]
        compactar_se_precisar(diretorio, dados, lidos)
        return 0
    if comando == "get":
        if len(resto) != 1:
            print("uso: get <chave>", file=sys.stderr)
            return 2
        if resto[0] not in dados:
            print("chave ausente", file=sys.stderr)
            return 1
        print(dados[resto[0]])
        return 0
    if comando == "del":
        if len(resto) != 1:
            print("uso: del <chave>", file=sys.stderr)
            return 2
        if resto[0] in dados:
            anexar(diretorio, b"D", resto[0], "")
            dados.pop(resto[0], None)
        return 0
    if comando == "list":
        for chave in sorted(dados):
            print(chave)
        return 0

    print(f"comando desconhecido: {comando}", file=sys.stderr)
    return 2
