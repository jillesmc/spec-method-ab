"""Tradução de linha de comando sobre a API de `kvstore` (ver D6 em design.md).

Nenhuma regra de negócio mora aqui: `argparse` → chamada à API → escrita em
stdout/stderr → código de saída. `argparse` já sai com 2 em erro de uso (comando
desconhecido, número de argumentos errado), então não há tratamento extra para
esses casos.
"""

import argparse
import sqlite3
import sys

import kvstore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m kvstore")
    parser.add_argument("directory", help="diretório do store")
    subparsers = parser.add_subparsers(dest="command", required=True)

    set_parser = subparsers.add_parser("set", help="grava chave/valor")
    set_parser.add_argument("key")
    set_parser.add_argument("value", help="valor, ou '-' para ler de stdin")

    get_parser = subparsers.add_parser("get", help="lê o valor de uma chave")
    get_parser.add_argument("key")

    del_parser = subparsers.add_parser("del", help="remove uma chave")
    del_parser.add_argument("key")

    subparsers.add_parser("list", help="lista as chaves vivas")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        if args.command == "set":
            value = sys.stdin.read() if args.value == "-" else args.value
            kvstore.set(args.directory, args.key, value)
        elif args.command == "get":
            value = kvstore.get(args.directory, args.key)
            sys.stdout.buffer.write(value.encode("utf-8"))
            sys.stdout.buffer.flush()
        elif args.command == "del":
            kvstore.delete(args.directory, args.key)
        elif args.command == "list":
            for key in kvstore.list_keys(args.directory):
                print(key)
    except kvstore.KeyNotFoundError as exc:
        print(f"chave não encontrada: {exc.key}", file=sys.stderr)
        return 1
    except kvstore.InvalidKeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (sqlite3.Error, OSError) as exc:
        print(f"falha de dados ou de E/S em {args.directory!r}: {exc}", file=sys.stderr)
        return 3

    return 0


if __name__ == "__main__":
    sys.exit(main())
