"""Ponto de entrada `python -m kvstore`. Traduz sys.argv/stdin em chamadas a Store e
exceção em código de saída. Nunca abre conexão nem emite SQL diretamente (ver `_dx.md` § Errors)."""

import os
import sys

from kvstore import Store

PROG = "kvstore"
USO_GERAL = f"{PROG}: uso: python -m kvstore <diretorio> {{set|get|del|list}} [args]"
USO_SET = f"{PROG}: uso: python -m kvstore <diretorio> set <chave> <valor>"


def _falhar(mensagem, codigo):
    sys.stderr.write(mensagem + "\n")
    sys.stderr.flush()
    sys.exit(codigo)


def _motivo(erro):
    # OSError traz `strerror`/`errno` sem o caminho repetido; erro do motor cai no str() puro.
    if isinstance(erro, OSError) and erro.errno is not None and erro.strerror:
        return f"[Errno {erro.errno}] {erro.strerror}"
    return str(erro)


def _ler_valor_stdin():
    dados = sys.stdin.buffer.read()
    try:
        return dados.decode("utf-8")
    except UnicodeDecodeError as erro:
        _falhar(f"{PROG}: entrada padrao nao e' UTF-8 valido no byte {erro.start}", 2)


def _abrir_store(diretorio):
    try:
        return Store(diretorio)
    except Exception as erro:
        _falhar(f"{PROG}: nao foi possivel abrir {diretorio}: {_motivo(erro)}", 3)


def _executar(func, *args):
    try:
        return func(*args)
    except (ValueError, TypeError) as erro:
        _falhar(f"{PROG}: {erro}", 2)
    except Exception as erro:
        if "locked" in str(erro).lower():
            _falhar(f"{PROG}: armazenamento ocupado por outro processo (5s)", 3)
        _falhar(f"{PROG}: falha ao gravar: {_motivo(erro)}", 3)


def _escrever_sem_pipe_quebrado(escrever):
    try:
        escrever()
        sys.stdout.buffer.flush()
    except BrokenPipeError:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        os.close(devnull)


def _validar_resto(comando, resto):
    if comando == "set":
        if len(resto) == 3 and resto[1] == "-":
            _falhar(f"{PROG}: com '-' o valor vem da entrada padrao; remova o argumento", 2)
        if len(resto) != 2:
            _falhar(USO_SET, 2)
    elif comando in ("get", "del"):
        if len(resto) != 1:
            _falhar(USO_GERAL, 2)
    elif comando == "list":
        if len(resto) != 0:
            _falhar(USO_GERAL, 2)


def _cmd_set(store, resto):
    chave, valor_bruto = resto
    valor = _ler_valor_stdin() if valor_bruto == "-" else valor_bruto
    _executar(store.set, chave, valor)


def _cmd_get(store, resto):
    chave = resto[0]
    valor = _executar(store.get, chave)
    if valor is None:
        _falhar(f"{PROG}: chave nao encontrada: {chave}", 1)
    _escrever_sem_pipe_quebrado(lambda: sys.stdout.buffer.write(valor.encode("utf-8")))


def _cmd_del(store, resto):
    _executar(store.delete, resto[0])


def _cmd_list(store, resto):
    def escrever():
        for chave in _executar(store.keys):
            sys.stdout.buffer.write(chave.encode("utf-8"))
            sys.stdout.buffer.write(b"\n")

    _escrever_sem_pipe_quebrado(escrever)


COMANDOS = {"set": _cmd_set, "get": _cmd_get, "del": _cmd_del, "list": _cmd_list}


def main(argv):
    if len(argv) < 2:
        _falhar(USO_GERAL, 2)
    diretorio, comando, *resto = argv
    if comando not in COMANDOS:
        _falhar(USO_GERAL, 2)
    _validar_resto(comando, resto)
    store = _abrir_store(diretorio)
    try:
        COMANDOS[comando](store, resto)
    finally:
        store.close()


if __name__ == "__main__":
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
