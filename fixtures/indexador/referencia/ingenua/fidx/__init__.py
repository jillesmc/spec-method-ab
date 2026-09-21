"""Referencia INGENUA do indexador: o caminho natural.

Cache por data de modificacao. E' o reflexo de quem vai direto para o codigo:
mtime e' o primeiro sinal que qualquer um lembra para "mudou ou nao".

Existe para CALIBRAR a suite: tem que passar BASE inteiro e quase toda a
ROBUSTEZ, e tem que morrer no ORACULO. Se ela passar no ORACULO, a suite nao
discrimina e o experimento nao serve.
"""

import json
import os
import re
import sys

INDICE = ".fidx-indice.json"
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
        anterior = antigos.get(rel)
        # AQUI ESTA A ARMADILHA: so reprocessa se a data mudou.
        if anterior is not None and anterior.get("mtime") == marca:
            novos[rel] = anterior
        else:
            novos[rel] = {"mtime": marca, "palavras": _palavras(caminho)}
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
