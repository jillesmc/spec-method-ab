"""Subprocesso auxiliar dos testes de falha abrupta (`tests/test_falha_abrupta.py`).

Roda exatamente uma operação (`set` ou `del`) contra `kvstore` e, assim que ela
retorna — ou seja, confirmada —, escreve uma linha em stdout e trava esperando o
pai mandar `SIGKILL`. O pai sincroniza lendo essa linha, nunca com `sleep`, então
o kill só acontece depois que a gravação de fato confirmou (tarefas 4.1/4.2/4.3).
Para os testes que matam *durante* a gravação (4.4/4.5/4.6), o pai ignora essa
linha e mata depois de um atraso; este processo pode nem chegar a escrevê-la.

Para o cenário "Interrupção durante manutenção preserva o estado" (storage/spec.md),
o pai precisa matar durante a janela de `wal_checkpoint`/`incremental_vacuum` que
`kvstore.delete()` dispara *depois* do `DELETE` já confirmado — matar por um atraso
fixo a partir do início do processo arriscaria cair antes dessa janela até abrir. Com
a variável de ambiente `KVSTORE_TEST_SINALIZAR_INICIO_DA_COMPACTACAO=1`, o worker
instrumenta `sqlite3.Connection.execute` para emitir `CONFIRMACAO_COMPACTACAO` assim
que o `PRAGMA wal_checkpoint` da compactação começa a rodar, dando ao pai um ponto de
sincronização real para o kill cair dentro da janela.

Uso: python3 -m tests._sigkill_worker <diretorio> set <chave>   (valor via stdin)
     python3 -m tests._sigkill_worker <diretorio> del <chave>
"""

import os
import signal
import sqlite3
import sys

import kvstore

CONFIRMACAO = "confirmado"
CONFIRMACAO_COMPACTACAO = "compactando"

_SINALIZAR_INICIO_DA_COMPACTACAO = "KVSTORE_TEST_SINALIZAR_INICIO_DA_COMPACTACAO"


class _ConexaoInstrumentada(sqlite3.Connection):
    def execute(self, sql, *args, **kwargs):
        if isinstance(sql, str) and sql.startswith("PRAGMA wal_checkpoint"):
            print(CONFIRMACAO_COMPACTACAO, flush=True)
        return super().execute(sql, *args, **kwargs)


def _instrumentar_inicio_da_compactacao() -> None:
    """`sqlite3.Connection` é um tipo imutável — não dá para trocar `execute` nele
    diretamente. Em vez disso, troca `sqlite3.connect` por uma versão que usa
    `factory=_ConexaoInstrumentada`; como `kvstore/__init__.py` chama
    `sqlite3.connect(...)` por atributo do módulo (não por referência importada),
    a troca vale para a próxima conexão que `delete()` abrir.
    """
    connect_original = sqlite3.connect

    def connect_instrumentado(*args, **kwargs):
        kwargs.setdefault("factory", _ConexaoInstrumentada)
        return connect_original(*args, **kwargs)

    sqlite3.connect = connect_instrumentado


def main() -> None:
    directory, op, key = sys.argv[1], sys.argv[2], sys.argv[3]
    if op == "set":
        value = sys.stdin.read()
        kvstore.set(directory, key, value)
    elif op == "del":
        if os.environ.get(_SINALIZAR_INICIO_DA_COMPACTACAO) == "1":
            _instrumentar_inicio_da_compactacao()
        kvstore.delete(directory, key)
    else:
        raise SystemExit(f"operação desconhecida: {op!r}")

    print(CONFIRMACAO, flush=True)
    while True:
        signal.pause()


if __name__ == "__main__":
    main()
