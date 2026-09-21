# Memória: task_02 — Operações do store

## Status

Implementada e verificada. `status: completed` em `task_02.md`.

## O que foi feito

- `kvstore/__init__.py` ganhou a API pública, chamando `_connect(directory)` internamente
  em cada operação (nunca abrindo `sqlite3` cru fora dela, como a `task_01` já pedia):
  - `set(directory, key, value)`: `INSERT ... ON CONFLICT(key) DO UPDATE`, retorno só
    depois do `commit()`.
  - `get(directory, key)`: levanta `KeyNotFoundError` se a chave não existir. Antes de
    conectar, checa `os.path.isfile(_db_path(directory))` — se o arquivo do banco não
    existe, trata como store vazio e levanta `KeyNotFoundError` sem criar nada.
  - `delete(directory, key)`: idempotente (`DELETE` sem matched rows não é erro); dispara
    `wal_checkpoint(TRUNCATE)` seguido de `incremental_vacuum` após o `commit` do delete.
  - `list_keys(directory)`: mesma checagem de arquivo ausente do `get`; senão,
    `SELECT key FROM kv ORDER BY key`.
  - `_validate_key`: recusa chave vazia, com `\n` ou com `\x00`, levantando
    `InvalidKeyError`. Chamada **antes** de `_connect` em `set`/`get`/`delete`, então uma
    chave inválida nunca cria diretório nem abre conexão.
  - Exceções novas: `KvstoreError` (base), `InvalidKeyError(KvstoreError, ValueError)`,
    `KeyNotFoundError(KvstoreError, LookupError)` com atributo `.key`.
- `tests/test_operacoes.py` (15 testes novos, cobrindo 2.1–2.7 do `tasks.md`).

## Decisão importante que a próxima tarefa (CLI) deve conhecer

- `get`/`delete`/`list_keys` fora de escopo de erro de uso devolvem/levantam:
  - `get` de chave ausente → `KeyNotFoundError` (mapear para exit code 1 no CLI).
  - `set`/`get`/`delete` de chave inválida (vazia, `\n`, NUL) → `InvalidKeyError`
    (mapear para exit code 2, junto com erro de uso do `argparse`).
  - `delete` de chave ausente **não** levanta nada (idempotente, sucesso silencioso).

## Achado não-óbvio (armadilha real, não só nota de estilo)

**`conn.execute("PRAGMA ...")` sem `.fetchall()`/`.fetchone()` não conclui o pragma.**
Descobri isso porque `incremental_vacuum` parecia não liberar página nenhuma mesmo com
`wal_checkpoint(TRUNCATE)` antes e `commit()` depois — o `freelist_count` só crescia a
cada `delete()`. A causa: nem `wal_checkpoint(TRUNCATE)` nem `incremental_vacuum`
executam de fato até o cursor do `sqlite3` (stdlib) ser consumido; sem isso o statement
fica parcialmente executado (o checkpoint não termina, o vacuum não libera páginas),
mesmo que um `commit()` seguinte não acuse erro. A correção é sempre `.fetchall()` os
dois pragmas em `delete()` antes do commit final — comentado no código. Se `task_05`
(concorrência/crescimento) tocar nesse trecho de novo, preservar o `.fetchall()`.

Ordem que importa dentro de `delete()`: `DELETE` → `commit()` →
`wal_checkpoint(TRUNCATE)` (com fetch) → `incremental_vacuum` (com fetch) → `commit()`.
Sem o checkpoint antes do vacuum, a página apagada ainda está só no WAL e o
`incremental_vacuum` (que só enxerga o arquivo principal) não acha nada pra liberar.

## Verificação executada

- `make test` (`python3 -m unittest discover -s tests -t . -v`): 19 testes, todos OK
  (4 de `task_01` + 1 smoke test + 15 novos de `task_02`, incluindo o teste de
  `incremental_vacuum` que grava 50 chaves de 200 KiB e exige que o diretório encolha
  para menos de 10% do tamanho cheio depois de remover tudo).
- `openspec validate kvstore --strict`: **não executável neste ambiente** (mesmo
  bloqueio já registrado em `MEMORY.md` — `openspec` ausente de `PATH`, `npx` e `pip`).
  Comando que seria rodado: `openspec validate kvstore --strict`.

## Sem pendências de escopo

CLI (`kvstore/__main__.py`), testes de crash com `SIGKILL`, concorrência e fechamento
ficam para `task_03`–`task_06`, nessa ordem.
