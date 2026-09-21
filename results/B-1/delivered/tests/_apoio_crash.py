"""Script auxiliar de `tests/test_durabilidade.py`, rodado via `subprocess`.

Grava uma chave e se mata com `os.kill(os.getpid(), signal.SIGKILL)` num ponto injetado
em `os.replace`: antes da troca atômica acontecer, ou logo depois dela, antes do
`fsync` do diretório. Usado para provar, com um crash real de processo, que a ordem de
escrita da Decisão 2 do design deixa o store sempre legível.
"""
import os
import signal
import sys

import kvstore


def main():
    diretorio, chave, valor, ponto = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    replace_original = os.replace

    def replace_e_morre_antes(_src, _dst):
        os.kill(os.getpid(), signal.SIGKILL)

    def replace_e_morre_depois(src, dst):
        replace_original(src, dst)
        os.kill(os.getpid(), signal.SIGKILL)

    if ponto == "antes_replace":
        os.replace = replace_e_morre_antes
    elif ponto == "depois_replace":
        os.replace = replace_e_morre_depois
    else:
        raise ValueError(f"ponto desconhecido: {ponto}")

    kvstore.set(diretorio, chave, valor)
    # Nunca deveria chegar aqui: o processo se mata dentro de os.replace.
    sys.exit(3)


if __name__ == "__main__":
    main()
