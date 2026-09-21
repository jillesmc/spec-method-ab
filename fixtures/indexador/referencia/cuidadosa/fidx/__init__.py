"""Referencia CUIDADOSA do indexador: o caminho que um plano deveria achar.

Decide o que mudou pelo CONTEUDO, com hash. Nao e' esperto nem otimizado: e'
so o desenho que responde ao que o enunciado avisa, que a data de modificacao
nao e' confiavel porque os arquivos chegam por rsync e por checkout.

O mtime continua sendo usado, mas so como ATALHO: se a data bate, ainda assim
confere o hash. Isso mantem o ganho de velocidade no caso comum sem herdar o
erro do caso que o enunciado descreve.

Existe para CALIBRAR a suite: tem que passar nas tres camadas. Se ela falhar
no ORACULO, a suite esta cobrando coisa impossivel e e' injusta.
"""

import hashlib
import json
import os
import re
import sys

INDICE = ".fidx-indice.json"
BLOCO = 1 << 20
PALAVRA = re.compile(r"\w+", re.UNICODE)


def _indice(pasta):
    return os.path.join(pasta, INDICE)


def _carregar(pasta):
    try:
        with open(_indice(pasta), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, ValueError):
        return {"arquivos": {}}


def _salvar(pasta, dados):
    with open(_indice(pasta), "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False)


def _varrer(pasta):
    for raiz, _dirs, nomes in os.walk(pasta):
        for nome in nomes:
            if nome == INDICE:
                continue
            caminho = os.path.join(raiz, nome)
            if not os.path.isfile(caminho):
                continue  # link quebrado
            yield os.path.relpath(caminho, pasta)


def _impressao(caminho):
    """Identidade do conteudo. Le em blocos para nao carregar arquivo grande
    inteiro na memoria."""
    h = hashlib.blake2b(digest_size=16)
    try:
        with open(caminho, "rb") as fh:
            while True:
                pedaco = fh.read(BLOCO)
                if not pedaco:
                    break
                h.update(pedaco)
    except OSError:
        return None
    return h.hexdigest()


def _palavras(caminho):
    try:
        with open(caminho, "r", encoding="utf-8", errors="replace") as fh:
            return sorted({p.lower() for p in PALAVRA.findall(fh.read())})
    except OSError:
        return []


def indexar(pasta):
    dados = _carregar(pasta)
    antigos = dados["arquivos"]
    novos = {}
    for rel in _varrer(pasta):
        caminho = os.path.join(pasta, rel)
        try:
            marca = os.stat(caminho).st_mtime
        except OSError:
            continue
        impressao = _impressao(caminho)
        if impressao is None:
            continue
        anterior = antigos.get(rel)
        # O conteudo decide. A data entra so como informacao, nunca como
        # criterio de invalidacao.
        if anterior is not None and anterior.get("hash") == impressao:
            novos[rel] = anterior
        else:
            novos[rel] = {
                "mtime": marca,
                "hash": impressao,
                "palavras": _palavras(caminho),
            }
    dados["arquivos"] = novos
    _salvar(pasta, dados)
    return 0


def buscar(pasta, termo):
    dados = _carregar(pasta)
    alvo = termo.lower()
    for rel in sorted(dados["arquivos"]):
        if alvo in dados["arquivos"][rel].get("palavras", []):
            print(rel)
    return 0


def principal(argv):
    if len(argv) < 2:
        print("uso: python -m fidx <diretorio> <index|search> [termo]", file=sys.stderr)
        return 2
    pasta, comando = argv[0], argv[1]
    if not os.path.isdir(pasta):
        print(f"nao e' um diretorio: {pasta}", file=sys.stderr)
        return 2
    if comando == "index":
        return indexar(pasta)
    if comando == "search":
        if len(argv) < 3 or not argv[2]:
            print("uso: search <termo>", file=sys.stderr)
            return 2
        return buscar(pasta, argv[2])
    print(f"comando desconhecido: {comando}", file=sys.stderr)
    return 2
