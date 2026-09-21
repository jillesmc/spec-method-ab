"""Subprocesso auxiliar do teste de leitura concorrente com escrita
(`tests/test_concorrencia_e_crescimento.py`, tarefa 5.2).

Grava a mesma chave `n` vezes seguidas, cada gravação com um valor diferente e
confirmada antes de a próxima começar, para dar ao processo pai uma janela real
de escritas em andamento contra a qual testar leituras concorrentes vindas de
outro processo.

Uso: python3 -m tests._escritor_continuo <diretorio> <chave> <n> <prefixo>
"""

import sys

import kvstore


def main() -> None:
    directory, key, n, prefix = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    for i in range(n):
        kvstore.set(directory, key, f"{prefix}-{i}")


if __name__ == "__main__":
    main()
