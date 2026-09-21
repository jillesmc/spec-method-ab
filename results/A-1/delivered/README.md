# kvstore

Armazenamento chave-valor durável em disco, sobre SQLite. Só biblioteca padrão do Python
3.11+ — nenhuma dependência externa, em tempo de execução ou de teste.

Quatro verbos, pela linha de comando ou em processo: `set`, `get`, `del`, `list`.

## Uso pela linha de comando

Forma geral: `python -m kvstore <diretorio> <comando> [argumentos]`. O `<diretorio>` vem
**antes** do comando; se não existir, é criado na primeira operação.

```console
$ python -m kvstore ./dados set posicao 1042
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

`get` de uma chave ausente termina com código 1 e não imprime nada em stdout:

```console
$ python -m kvstore ./dados get inexistente
kvstore: chave nao encontrada: inexistente
$ echo $?
1
```

Valor grande, pela entrada padrão, com `-` no lugar do valor:

```console
$ python -m kvstore ./dados set dump - < dump.json
$ python -m kvstore ./dados get dump | wc -c
12582912
```

Erros de uso terminam com código 2 e mostram a linha de uso:

```console
$ python -m kvstore
kvstore: uso: python -m kvstore <diretorio> {set|get|del|list} [args]
```

## Uso em processo

A forma como um serviço embutido consome o pacote: abre uma vez, grava muitas.

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

Erros vêm como exceções do próprio Python, sem hierarquia nova: `ValueError` para chave
vazia, `TypeError` para chave que não é `str`, e as exceções normais do `sqlite3` (por
exemplo `ProgrammingError` ao usar o `Store` depois de `close()`).

## Garantia de durabilidade

Quando `set` ou `delete` retornam com sucesso — em qualquer das duas superfícies —, a
mudança já está sincronizada em disco e sobrevive à morte do processo (`SIGKILL`, OOM,
deploy) **e** à queda da máquina (energia, pânico do kernel), salvo hardware que mente
sobre `fsync`, o que está fora do alcance de qualquer software. Não há versionamento: um
`set` numa chave existente substitui o valor anterior, que não é recuperável. Detalhes da
escolha de `journal_mode`/`synchronous` em `.compozy/tasks/kvstore/adrs/adr-002.md`.

## Limitações conhecidas

- **O arquivo não encolhe depois de apagar uma chave grande.** O espaço é reaproveitado
  internamente pelo SQLite para gravações futuras, mas o tamanho do arquivo em disco não
  diminui. Não há comando de compactação nem `VACUUM` — decisão deliberada, para não exigir
  o dobro do espaço em disco durante a operação.
- **`list` é ambíguo para chaves contendo newline.** Como a saída é uma chave por linha,
  uma chave que contém `\n` (permitido pelo contrato) aparece como se fossem várias linhas.
- **Um escritor de cada vez.** Sob dois escritores concorrentes, o segundo espera até 5s
  (`busy_timeout`) e falha com código 3 se a contenção não se resolver nesse prazo. Leitores
  não disputam essa trava.

Nenhuma dessas limitações exige rotina periódica de manutenção — não existe uma a agendar.

## Arquivos em disco

O que aparece dentro de `<diretorio>`:

```console
$ ls -a ./dados
.  ..  kvstore.sqlite3
```

`kvstore.sqlite3` é um banco SQLite comum, inspecionável com qualquer ferramenta SQLite.
Os auxiliares `kvstore.sqlite3-wal` e `kvstore.sqlite3-shm` são do journal do SQLite e podem
aparecer e sumir entre execuções. Nenhum dos três arquivos deve ser apagado ou copiado
isoladamente com o serviço no ar.

## Testes

```console
$ make test
```

Roda `python3 -m unittest discover -s tests -t .`, sem dependência externa.
