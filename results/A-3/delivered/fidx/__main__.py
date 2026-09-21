"""Porta de entrada unica: le sys.argv, chama fidx.core, formata saida e exit code."""

import os
import sys

from fidx import core

_USO = (
    "fidx: uso: python3 -m fidx <diretorio> index\n"
    "            python3 -m fidx <diretorio> search <termo>"
)


def _uso() -> int:
    print(_USO, file=sys.stderr)
    return 2


def _avisa_pulado(caminho: str, motivo: str) -> None:
    print(f"fidx: aviso: pulado {caminho}: {motivo}", file=sys.stderr)


def _cmd_index(directory: str) -> int:
    try:
        total, reindexados, removidos = core.index_dir(directory, on_pulado=_avisa_pulado)
    except core.NotADirectory as exc:
        print(f"fidx: nao e um diretorio: {exc.path}", file=sys.stderr)
        return 2
    except core.IndexCreateError as exc:
        print(f"fidx: nao foi possivel criar o indice: {exc.path}: {exc.reason}", file=sys.stderr)
        return 2
    except core.IndexBusy as exc:
        print(f"fidx: indice ocupado por outra rodada: {exc.path}", file=sys.stderr)
        return 3
    print(f"fidx: {total} arquivos, {reindexados} reindexados, {removidos} removidos")
    return 0


def _cmd_search(directory: str, term: str) -> int:
    try:
        paths = core.search(directory, term)
    except core.NotADirectory as exc:
        print(f"fidx: nao e um diretorio: {exc.path}", file=sys.stderr)
        return 2
    except core.IndexMissing as exc:
        print(f"fidx: indice nao encontrado: {exc.path}", file=sys.stderr)
        print(f"fidx: rode primeiro: python3 -m fidx {directory} index", file=sys.stderr)
        return 2
    except core.EmptyTerm as exc:
        print(f"fidx: termo sem token indexavel: '{exc.term}'", file=sys.stderr)
        return 2
    if not paths:
        return 1
    for path in paths:
        print(os.path.join(directory, path))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2:
        return _uso()
    directory, command, *rest = argv
    if command == "index":
        return _cmd_index(directory)
    if command == "search":
        if not rest:
            return _uso()
        return _cmd_search(directory, " ".join(rest))
    return _uso()


if __name__ == "__main__":
    sys.exit(main())
