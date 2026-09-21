"""Referencia INGENUA do store: o caminho natural.

Reescreve o arquivo inteiro a cada gravacao. E' o que o enunciado diz que eles
ja fazem hoje, e e' o que sai de quem nao planejou durabilidade.

Existe para CALIBRAR a suite: tem que passar BASE inteiro e quase toda a
ROBUSTEZ, e tem que morrer na camada INVARIANTE. Se ela passar em INVARIANTE,
a suite nao discrimina e o experimento nao serve.
"""

import json
import os
import sys

ARQUIVO = "store.json"


def _caminho(diretorio):
    return os.path.join(diretorio, ARQUIVO)


def carregar(diretorio):
    try:
        with open(_caminho(diretorio), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}


def salvar(diretorio, dados):
    os.makedirs(diretorio, exist_ok=True)
    with open(_caminho(diretorio), "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False)


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
        dados = carregar(diretorio)
    except (OSError, ValueError) as erro:
        print(f"nao consegui ler o store: {erro}", file=sys.stderr)
        return 3

    if comando == "set":
        if len(resto) != 2:
            print("uso: set <chave> <valor>", file=sys.stderr)
            return 2
        dados[resto[0]] = resto[1]
        salvar(diretorio, dados)
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
        dados.pop(resto[0], None)
        salvar(diretorio, dados)
        return 0
    if comando == "list":
        for chave in sorted(dados):
            print(chave)
        return 0

    print(f"comando desconhecido: {comando}", file=sys.stderr)
    return 2
