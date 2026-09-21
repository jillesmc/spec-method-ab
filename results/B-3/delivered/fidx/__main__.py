"""CLI: `python -m fidx <diretorio> {index,search} [<termo>]`."""

import argparse
import os
import sqlite3
import sys

import fidx


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fidx")
    parser.add_argument("diretorio")
    subparsers = parser.add_subparsers(dest="comando", required=True)
    subparsers.add_parser("index")
    busca = subparsers.add_parser("search")
    busca.add_argument("termo")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if not os.path.isdir(args.diretorio):
        print(f"fidx: diretorio inexistente: {args.diretorio!r}", file=sys.stderr)
        return 2

    try:
        if args.comando == "index":
            resumo = fidx.index(args.diretorio)
            print(
                f"reprocessados={resumo.reprocessados} "
                f"inalterados={resumo.inalterados} removidos={resumo.removidos}"
            )
            return 0

        caminhos = fidx.search(args.diretorio, args.termo)
        for caminho in caminhos:
            print(caminho)
        return 0 if caminhos else 1
    except (ValueError, FileNotFoundError, PermissionError) as erro:
        print(f"fidx: {erro}", file=sys.stderr)
        return 2
    except sqlite3.OperationalError as erro:
        print(f"fidx: indice ocupado, tente novamente (rodada concorrente?): {erro}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
