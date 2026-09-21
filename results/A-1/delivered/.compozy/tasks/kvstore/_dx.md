# Developer Experience: kvstore

Contrato de superfície pública do `kvstore`. Companheiro de `_spec.md` (a Part II é desenhada para
servir esta superfície) e de `_tests.md` (as jornadas E2E usam exatamente estas invocações).

Escrito como se já tivesse sido entregue. Seções do template sem superfície aqui (YAML, HTTP/UDS,
config.toml, native tools, bridges) foram removidas: o pacote é uma biblioteca Python com linha de
comando, sem daemon, sem rede e sem arquivo de configuração.

## Golden Path

Do nada ao valor, em trinta segundos:

```console
$ python -m kvstore ./dados set posicao 1042
$ echo $?
0
$ python -m kvstore ./dados set config '{"modo":"producao"}'
$ python -m kvstore ./dados list
config
posicao
$ python -m kvstore ./dados get posicao
1042
$ python -m kvstore ./dados del posicao
$ python -m kvstore ./dados list
config
```

E do serviço, em processo:

```python
from kvstore import Store

with Store("./dados") as s:
    s.set("posicao", "1042")      # retorna quando o dado esta no disco
    s.get("posicao")              # '1042'
    s.get("ausente")              # None
    s.delete("posicao")           # True  (existia)
    s.delete("posicao")           # False (nao existia; nao e' erro)
    s.keys()                      # ['config']
```

## CLI

Forma geral: `python -m kvstore <diretorio> <comando> [argumentos]`.

O `<diretorio>` vem **antes** do comando, conforme o enunciado. Se não existir, é criado.

### `set`

```console
$ python -m kvstore ./dados set posicao 1042
$ echo $?
0
```

Não imprime nada em caso de sucesso. Quando o comando retorna 0, o valor já está em disco e sobrevive
à morte do processo e à queda da máquina (ver Errors e `adrs/adr-002.md`).

Sobrescrita é o comportamento normal:

```console
$ python -m kvstore ./dados set posicao 2000
$ python -m kvstore ./dados get posicao
2000
```

Valor grande, pela entrada padrão, com `-` no lugar do valor:

```console
$ ls -l dump.json
-rw-r--r-- 1 svc svc 12582912 Sep 20 17:02 dump.json
$ python -m kvstore ./dados set dump - < dump.json
$ echo $?
0
$ python -m kvstore ./dados get dump | wc -c
12582912
```

### `get`

```console
$ python -m kvstore ./dados get posicao
1042
```

O valor sai em stdout **exatamente como foi gravado, sem newline adicionado**. O `1042` acima aparece
colado no prompt seguinte num terminal real; isso é intencional, para que
`python -m kvstore ./dados get dump > copia.json` reproduza o conteúdo byte a byte.

Chave ausente:

```console
$ python -m kvstore ./dados get inexistente
kvstore: chave nao encontrada: inexistente
$ echo $?
1
```

Nada é escrito em stdout nesse caso, então `valor=$(python -m kvstore ./dados get inexistente)` deixa
`valor` vazio e `$?` em 1.

### `del`

```console
$ python -m kvstore ./dados del posicao
$ echo $?
0
```

Idempotente: apagar uma chave que não existe também termina com 0 e não imprime nada.

```console
$ python -m kvstore ./dados del posicao
$ echo $?
0
```

### `list`

```console
$ python -m kvstore ./dados list
config
contador
posicao
```

Uma chave por linha, em ordem crescente de código de caractere. Diretório vazio imprime nada e
termina com 0.

## SDK

A API Python que o serviço usa em processo. `kvstore/__init__.py` exporta apenas isto:

```python
class Store:
    def __init__(self, diretorio: str | os.PathLike) -> None: ...
    def set(self, chave: str, valor: str) -> None: ...
    def get(self, chave: str) -> str | None: ...
    def delete(self, chave: str) -> bool: ...
    def keys(self) -> list[str]: ...
    def close(self) -> None: ...
    def __enter__(self) -> "Store": ...
    def __exit__(self, *exc) -> None: ...
```

Uso longo, típico do serviço — abre uma vez, grava muitas:

```python
from kvstore import Store

store = Store("/var/lib/servico/estado")   # cria o diretorio se preciso
for evento in fila:
    processar(evento)
    store.set("posicao", str(evento.offset))   # duravel a cada chamada
```

Erros vêm como exceções do próprio Python, sem hierarquia nova:

```python
store.set("", "x")        # ValueError: chave nao pode ser vazia
store.set(1, "x")         # TypeError: chave deve ser str, recebido int
store.close(); store.get("k")   # sqlite3.ProgrammingError: Cannot operate on a closed database.
```

## Errors

Superfície determinística de falha da linha de comando. Mensagens vão para **stderr**, sempre com o
prefixo `kvstore: `, e stdout fica vazio.

| Código | Condição                                            | Saída em stderr                                                        | Ação que aponta                          |
| ------ | --------------------------------------------------- | ---------------------------------------------------------------------- | ---------------------------------------- |
| 0      | sucesso                                             | —                                                                       | —                                        |
| 1      | `get` de chave ausente                              | `kvstore: chave nao encontrada: <chave>`                                | conferir o nome com `list`               |
| 2      | nenhum argumento, ou comando desconhecido           | `kvstore: uso: python -m kvstore <diretorio> {set|get|del|list} [args]` | corrigir a invocação                     |
| 2      | número errado de argumentos para o comando          | `kvstore: uso: python -m kvstore <diretorio> set <chave> <valor>`       | corrigir a invocação                     |
| 2      | chave vazia                                         | `kvstore: chave nao pode ser vazia`                                     | passar uma chave                         |
| 2      | `set k - valor` (stdin e argumento ao mesmo tempo)  | `kvstore: com '-' o valor vem da entrada padrao; remova o argumento`    | escolher uma das duas fontes             |
| 2      | stdin com bytes que não são UTF-8                   | `kvstore: entrada padrao nao e' UTF-8 valido no byte <n>`               | converter o conteúdo para UTF-8          |
| 3      | diretório não é diretório, ou sem permissão         | `kvstore: nao foi possivel abrir <caminho>: <motivo>`                   | conferir permissão e caminho             |
| 3      | contenção de escrita além da espera configurada     | `kvstore: armazenamento ocupado por outro processo (5s)`                | repetir depois                           |
| 3      | disco cheio ou falha de E/S na gravação             | `kvstore: falha ao gravar: <motivo>`                                    | liberar espaço e repetir                 |

Invocação de uso, completa:

```console
$ python -m kvstore
kvstore: uso: python -m kvstore <diretorio> {set|get|del|list} [args]
$ echo $?
2

$ python -m kvstore ./dados pop x
kvstore: uso: python -m kvstore <diretorio> {set|get|del|list} [args]
$ echo $?
2

$ python -m kvstore ./dados set posicao
kvstore: uso: python -m kvstore <diretorio> set <chave> <valor>
$ echo $?
2
```

Diretório inacessível:

```console
$ python -m kvstore /proc/impossivel set k v
kvstore: nao foi possivel abrir /proc/impossivel: [Errno 13] Permission denied
$ echo $?
3
```

## Arquivos em disco

O que o operador encontra dentro de `<diretorio>` — parte do contrato porque é o que ele vê num
incidente:

```console
$ ls -a ./dados
.  ..  kvstore.sqlite3  kvstore.sqlite3-shm  kvstore.sqlite3-wal
```

`kvstore.sqlite3` é um banco SQLite comum, inspecionável com qualquer ferramenta SQLite; os arquivos
`-wal` e `-shm` são do journal e podem aparecer e sumir entre execuções. Nenhum dos três deve ser
apagado ou copiado isoladamente com o serviço no ar.
