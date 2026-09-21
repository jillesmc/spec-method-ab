"""Linha de comando do kvstore.

``python -m kvstore <diretorio> <comando> [argumentos]`` com os comandos
``set``, ``get``, ``del`` e ``list``. Códigos de saída: 0 sucesso, 1
``KeyError`` (chave ausente), 2 uso inválido, ``ValueError`` (chave
inválida) ou ``OSError``. Mensagens de erro só em stderr; stdout recebe
somente os dados pedidos.
"""

import argparse
import io
import sys

from kvstore import delete, get_stream, keys, set_stream


def _construir_parser():
    parser = argparse.ArgumentParser(prog="kvstore")
    parser.add_argument("diretorio")
    subparsers = parser.add_subparsers(dest="comando", required=True)

    set_parser = subparsers.add_parser("set")
    set_parser.add_argument("chave")
    set_parser.add_argument("valor", nargs="?")

    get_parser = subparsers.add_parser("get")
    get_parser.add_argument("chave")

    del_parser = subparsers.add_parser("del")
    del_parser.add_argument("chave")

    subparsers.add_parser("list")

    return parser


def main(argv=None):
    parser = _construir_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    try:
        if args.comando == "set":
            if args.valor is None:
                set_stream(args.diretorio, args.chave, sys.stdin.buffer)
            else:
                set_stream(args.diretorio, args.chave, io.BytesIO(args.valor.encode("utf-8")))
        elif args.comando == "get":
            try:
                get_stream(args.diretorio, args.chave, sys.stdout.buffer)
            except KeyError:
                print(f"chave nao encontrada: {args.chave}", file=sys.stderr)
                return 1
            sys.stdout.buffer.flush()
        elif args.comando == "del":
            try:
                delete(args.diretorio, args.chave)
            except KeyError:
                print(f"chave nao encontrada: {args.chave}", file=sys.stderr)
                return 1
        elif args.comando == "list":
            for chave in keys(args.diretorio):
                print(chave)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
