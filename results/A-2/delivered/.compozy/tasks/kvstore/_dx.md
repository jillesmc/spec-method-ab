# Developer Experience: kvstore

Public-surface contract for kvstore. Companion to `_spec.md` (Part II serves this surface) and
`_tests.md` (the E2E journeys use these exact invocations, byte for byte).

Sections omitted because the feature has no such surface: YAML, HTTP/UDS API, `config.toml`, native tools.

## Golden Path

Thirty seconds from an empty directory to a value that survives a kill:

```console
$ python -m kvstore ./dados set posicao 1042
$ python -m kvstore ./dados set modo rapido
$ python -m kvstore ./dados list
modo
posicao
$ python -m kvstore ./dados get posicao
1042
$ ls ./dados
kvstore.db  kvstore.db-shm  kvstore.db-wal
```

`set` printed nothing and exited 0: that is the acknowledgement, and it happened after the write reached
the disk. Prove it by destroying the process that could have been holding it in memory — there is none:

```console
$ pkill -9 -f 'kvstore' ; python -m kvstore ./dados get posicao
1042
```

Clean up one key and see it go:

```console
$ python -m kvstore ./dados del modo
$ python -m kvstore ./dados list
posicao
```

## CLI

Invocation shape: `python -m kvstore <diretorio> <comando> [argumentos]`. The directory always comes
first, because every command operates on exactly one store.

### `set <chave> <valor>`

```console
$ python -m kvstore ./dados set modo rapido
$ echo $?
0
```

No output on success. The command returns only after the write is committed and flushed; exit code 0 is
the durability acknowledgement. Overwriting is the same call:

```console
$ python -m kvstore ./dados set modo lento
$ python -m kvstore ./dados get modo
lento
```

The directory is created if it does not exist:

```console
$ ls ./novo
ls: cannot access './novo': No such file or directory
$ python -m kvstore ./novo set k v
$ ls ./novo
kvstore.db  kvstore.db-shm  kvstore.db-wal
```

A value of `-` means "read the value from stdin", for values too large for the argument list:

```console
$ python -m kvstore ./dados set relatorio - < relatorio.txt
$ python -m kvstore ./dados get relatorio | cmp - relatorio.txt && echo identico
identico
```

Failures:

```console
$ python -m kvstore ./dados set "" valor
kvstore: chave vazia
$ echo $?
2
```

```console
$ python -m kvstore ./dados set 'a
b' valor
kvstore: chave nao pode conter quebra de linha ou NUL
$ echo $?
2
```

```console
$ python -m kvstore ./arquivo.txt set k v
kvstore: ./arquivo.txt nao e um diretorio
$ echo $?
3
```

```console
$ python -m kvstore /somente-leitura set k v
kvstore: erro ao abrir /somente-leitura: Permission denied
$ echo $?
3
```

### `get <chave>`

```console
$ python -m kvstore ./dados get modo
rapido
```

The value is written to stdout verbatim, with no newline appended. The `rapido` above appears on its own
line only because a shell prompt follows it; a value ending without a newline leaves the prompt on the
same line. Byte-exactness is the contract:

```console
$ printf 'com\nquebras\n' | python -m kvstore ./dados set texto -
$ python -m kvstore ./dados get texto | xxd | tail -1
00000000: 636f 6d0a 7175 6562 7261 730a            com.quebras.
```

Failure:

```console
$ python -m kvstore ./dados get ausente
kvstore: chave nao encontrada: ausente
$ echo $?
1
```

stdout is empty in that case, so `valor=$(python -m kvstore ./dados get ausente)` yields an empty string
and a non-zero status.

### `del <chave>`

```console
$ python -m kvstore ./dados del modo
$ echo $?
0
```

No output on success; the removal is durable when the command returns. A key that was not there is
reported rather than silently accepted:

```console
$ python -m kvstore ./dados del modo
kvstore: chave nao encontrada: modo
$ echo $?
1
```

### `list`

```console
$ python -m kvstore ./dados list
modo
posicao
relatorio
```

One key per line, sorted, each line terminated by a newline. An empty store prints nothing and exits 0:

```console
$ python -m kvstore ./vazio list
$ echo $?
0
```

### Usage

Called with no arguments, an unknown command, or the wrong number of arguments:

```console
$ python -m kvstore
uso: python -m kvstore <diretorio> <comando> [argumentos]

comandos:
  set <chave> <valor>   grava o valor; use - no lugar do valor para ler do stdin
  get <chave>           escreve o valor no stdout, sem newline extra
  del <chave>           remove a chave
  list                  lista as chaves, uma por linha

codigos de saida: 0 ok, 1 chave nao encontrada, 2 uso incorreto, 3 erro do store
$ echo $?
2
```

```console
$ python -m kvstore ./dados dump
kvstore: comando desconhecido: dump
$ echo $?
2
```

The usage block goes to stdout when it is the whole response to a bare invocation, and to stderr when it
accompanies an error.

## SDK / Python API

The CLI is a wrapper; the service can call the same store in-process and get the same guarantee.

```python
from kvstore import Store, KeyNotFound

with Store("./dados") as s:
    s.set("posicao", "1042")          # returns only after the write is on disk
    print(s.get("posicao"))           # -> 1042
    print(s.list())                   # -> ['modo', 'posicao']
    print(s.delete("modo"))           # -> True
    print(s.delete("modo"))           # -> False
    try:
        s.get("ausente")
    except KeyNotFound as e:
        print(e)                      # -> chave nao encontrada: ausente
```

Everything the package exports:

```python
from kvstore import (
    Store,              # the store
    KVStoreError,       # base class for every error below
    KeyNotFound,        # get() on an absent key; also a KeyError
    InvalidKey,         # empty key, or one containing a newline or NUL; also a ValueError
    StoreBusy,          # another process held the write lock past the timeout
    IncompatibleStore,  # directory written by a newer on-disk format version
    FORMAT_VERSION,     # 1
)
```

The write-lock timeout is the only tunable, and it is not exposed on the CLI:

```python
s = Store("./dados", timeout=30.0)   # default is 5.0 seconds
```

`Store` does not need to be closed for writes to be durable — durability happens at each `set`/`delete`,
not at `close()`. Closing releases the connection, and the context manager is the tidy way to do it.

## On-disk Contract

Inside the state directory, kvstore owns exactly these files and creates no others:

| File               | What it is                                                                   |
| ------------------ | ---------------------------------------------------------------------------- |
| `kvstore.db`       | The SQLite database holding the key-value table                              |
| `kvstore.db-wal`   | The write-ahead log; recent commits live here until a checkpoint moves them  |
| `kvstore.db-shm`   | The shared-memory index for the WAL, recreated as needed                     |

Copying a store means copying all three files together, or using `sqlite3 kvstore.db ".backup dest.db"`.
Any other file in the directory is left strictly untouched.

The store is an ordinary SQLite database, so the operator's escape hatch is the `sqlite3` shell:

```console
$ sqlite3 ./dados/kvstore.db 'SELECT k, length(v) FROM kv ORDER BY k'
modo|6
posicao|4
$ sqlite3 ./dados/kvstore.db 'PRAGMA user_version'
1
```

## Errors

| Condition                                      | Message (stderr)                                              | Exit | Python exception     |
| ---------------------------------------------- | ------------------------------------------------------------- | ---- | -------------------- |
| `get`/`del` on a key that is not there          | `kvstore: chave nao encontrada: <chave>`                       | 1    | `KeyNotFound`        |
| Empty key                                       | `kvstore: chave vazia`                                         | 2    | `InvalidKey`         |
| Key containing a newline or NUL                 | `kvstore: chave nao pode conter quebra de linha ou NUL`        | 2    | `InvalidKey`         |
| Unknown command                                 | `kvstore: comando desconhecido: <cmd>`                         | 2    | —                    |
| Missing or extra arguments                      | the usage block                                                | 2    | —                    |
| Given path is not a directory                   | `kvstore: <caminho> nao e um diretorio`                        | 3    | `KVStoreError`       |
| Directory cannot be opened or written           | `kvstore: erro ao abrir <caminho>: <motivo do sistema>`        | 3    | `KVStoreError`       |
| Another process held the write lock too long    | `kvstore: banco ocupado por outro processo (timeout 5.0s)`     | 3    | `StoreBusy`          |
| Directory written by a newer format version     | `kvstore: formato do diretorio e versao <n>, esta versao le ate 1` | 3 | `IncompatibleStore`  |
| Database file is corrupt                        | `kvstore: banco corrompido em <caminho>: <motivo do sqlite>`   | 3    | `KVStoreError`       |

Every failure prints one line to stderr and nothing to stdout, so a caller can distinguish "no value" from
"a value that happens to look like an error message". The exit code classes are stable: 1 means the key is
not there, 2 means the command was wrong, 3 means the store could not serve the request.
