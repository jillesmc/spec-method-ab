# Memória: task_03 — Linha de comando

## Status

Implementada e verificada. `status: completed` em `task_03.md`.

## O que foi feito

- `kvstore/__main__.py`: `argparse` com `directory` posicional e subparsers
  `set <key> <value>` / `get <key>` / `del <key>` / `list` (D6 em design.md — zero
  regra de negócio aqui, só tradução).
  - `set`: se `value == "-"`, lê `sys.stdin.read()` por inteiro antes de chamar
    `kvstore.set`.
  - `get`: escreve `value.encode("utf-8")` direto em `sys.stdout.buffer` (+`flush()`),
    nunca `print()` — evita o `\n` extra e a reconfiguração de encoding do terminal
    (D7).
  - `del`/`list`: chamam `kvstore.delete`/`kvstore.list_keys` direto; `list` usa
    `print(key)` por linha (aceitável, só chaves — já validadas sem `\n`).
  - Mapeamento de exceção → exit code: `KeyNotFoundError`→1, `InvalidKeyError`→2,
    `(sqlite3.Error, OSError)`→3 (cobre permissão negada, disco cheio, arquivo
    corrompido). Erro de uso do próprio `argparse` (comando desconhecido, aridade
    errada) já sai 2 sozinho — nenhum tratamento extra precisou ser escrito.
- `tests/test_cli.py` (13 testes novos, subprocess contra `python -m kvstore`),
  cobrindo 3.1–3.5 do `tasks.md`: ida-e-volta set/get, comando desconhecido e
  aridade errada (exit 2, diretório não tocado), valor byte-a-byte com acentuação/
  quebras/espaços, chave ausente (exit 1, stdout vazio), stdin grande (3 MiB) em
  `set ... -`, valor literal comum, chave inválida (exit 2, nada gravado), falha de
  E/S por diretório somente-leitura (exit 3, `skipIf(geteuid()==0)`), `del`
  idempotente (exit 0) e `list` em store vazio/inexistente (exit 0, stdout vazio).

## Decisões que a próxima tarefa (testes de crash) deve conhecer

- O `__main__` não amortece nada: qualquer `sqlite3.Error`/`OSError` fora dos casos
  de negócio já mapeados vira exit 3 com a mensagem crua da exceção em stderr. Se
  `task_04` (SIGKILL) espera outro exit code para corrupção específica, verificar
  aqui antes de assumir.
- Testes de CLI rodam via `subprocess.run([sys.executable, "-m", "kvstore", ...],
  cwd=<repo root>)` — sem setar `PYTHONPATH`, já funciona porque o subprocess herda
  o cwd na raiz do repo e Python resolve `kvstore` como pacote local a partir do
  `cwd` (comportamento de `python -m` com pacote no diretório atual). Reusar esse
  padrão em `task_04`/`test_falha_abrupta.py` para os testes de `SIGKILL`.
- Teste de permissão negada pula com `unittest.skipIf(os.geteuid() == 0, ...)` —
  necessário porque root ignora bits de permissão do sistema de arquivos.

## Verificação executada

- `make test` (`python3 -m unittest discover -s tests -t . -v`): 30 testes, todos
  OK (4 de `task_01` + 1 smoke test + 15 de `task_02` + 13 novos de `task_03` — a
  soma bate porque nenhum teste anterior foi alterado).
- Verificação manual do golden path do README:
  `python -m kvstore /tmp/... set foo bar` seguido de `get foo` imprime `bar` e sai
  0, com `cwd` na raiz do repo (mesma forma documentada no README).
- `openspec validate kvstore --strict`: **não executável neste ambiente** (mesmo
  bloqueio já registrado em `MEMORY.md`; reconfirmado agora — `command -v openspec`
  vazio, `python3 -c "import openspec"` falha, `pip show openspec` não encontra
  nada). Comando que seria rodado: `openspec validate kvstore --strict`.

## Sem pendências de escopo

Testes de crash com `SIGKILL` (task_04), concorrência e crescimento (task_05) e
fechamento/README (task_06) continuam fora do escopo desta tarefa.
