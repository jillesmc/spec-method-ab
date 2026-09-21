"""CLI entry point: `python -m kvstore <diretorio> <comando> [argumentos]`."""

import os
import sys

from kvstore import IncompatibleStore, InvalidKey, KeyNotFound, KVStoreError, Store, StoreBusy

_USAGE = (
    "uso: python -m kvstore <diretorio> <comando> [argumentos]\n"
    "\n"
    "comandos:\n"
    "  set <chave> <valor>   grava o valor; use - no lugar do valor para ler do stdin\n"
    "  get <chave>           escreve o valor no stdout, sem newline extra\n"
    "  del <chave>           remove a chave\n"
    "  list                  lista as chaves, uma por linha\n"
    "\n"
    "codigos de saida: 0 ok, 1 chave nao encontrada, 2 uso incorreto, 3 erro do store\n"
)

_COMMANDS = {"set": 2, "get": 1, "del": 1, "list": 0}


def _write_stdout(data: bytes) -> None:
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def _write_stderr(data: bytes) -> None:
    sys.stderr.buffer.write(data)
    sys.stderr.buffer.flush()


def _error(message: str) -> None:
    _write_stderr(f"kvstore: {message}\n".encode("utf-8"))


def main(argv: "list[str] | None" = None) -> int:
    args = sys.argv[1:] if argv is None else argv

    if not args:
        _write_stdout(_USAGE.encode("utf-8"))
        return 2

    directory = args[0]

    if len(args) == 1:
        _write_stderr(_USAGE.encode("utf-8"))
        return 2

    command = args[1]
    rest = args[2:]

    if command not in _COMMANDS:
        _error(f"comando desconhecido: {command}")
        return 2

    if len(rest) != _COMMANDS[command]:
        _write_stderr(_USAGE.encode("utf-8"))
        return 2

    store = Store(directory)
    try:
        if command == "set":
            key, value = rest
            if value == "-":
                value = sys.stdin.buffer.read().decode("utf-8")
            store.set(key, value)
            return 0

        if command == "get":
            (key,) = rest
            value = store.get(key)
            _write_stdout(value.encode("utf-8"))
            return 0

        if command == "del":
            (key,) = rest
            existed = store.delete(key)
            if not existed:
                _error(f"chave nao encontrada: {key}")
                return 1
            return 0

        # command == "list"
        keys = store.list()
        for key in keys:
            _write_stdout((key + "\n").encode("utf-8"))
        return 0
    except KeyNotFound as exc:
        _error(str(exc))
        return 1
    except InvalidKey as exc:
        _error(str(exc))
        return 2
    except (StoreBusy, IncompatibleStore, KVStoreError) as exc:
        _error(str(exc))
        return 3


if __name__ == "__main__":
    _codigo_saida = main()
    # Exit without an orderly connection close: SQLite auto-deletes the -wal/-shm
    # files when the last connection to a database closes cleanly, which would
    # make every command checkpoint away the files `_dx.md`'s golden path expects
    # to still be there. Relying on the OS to tear down the process (like the
    # kill -9 case) leaves them exactly as the last commit left them.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_codigo_saida)
