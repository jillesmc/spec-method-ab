# kvstore

Armazenamento chave-valor durável em disco. Só biblioteca padrão do Python 3.11+.

    make test
    python -m kvstore ./dados set posicao 1042

## Uso

    python -m kvstore <diretorio> <comando> [argumentos]

| Comando               | O que faz                                                              |
| --------------------- | ----------------------------------------------------------------------- |
| `set <chave> <valor>` | grava o valor; use `-` no lugar do valor para ler do stdin              |
| `get <chave>`         | escreve o valor no stdout, sem newline extra                            |
| `del <chave>`         | remove a chave                                                          |
| `list`                | lista as chaves, uma por linha                                          |

O diretório é criado automaticamente no primeiro `set`, se ainda não existir. Um valor
grande demais para a linha de comando entra pelo stdin:

    printf 'conteudo grande' | python -m kvstore ./dados set relatorio -

## Códigos de saída

| Código | Significado           |
| ------ | ---------------------- |
| `0`    | sucesso                |
| `1`    | chave não encontrada   |
| `2`    | uso incorreto           |
| `3`    | erro do store           |

`set` e `del` não imprimem nada em caso de sucesso: sair com código `0` é a confirmação.
Em particular, `set` só retorna (e só sai com `0`) depois que a escrita já está
confirmada e gravada em disco — se o processo for morto no instante seguinte, o valor
já gravado continua lá para o próximo processo que abrir o mesmo diretório.

## API Python

```python
from kvstore import Store, KeyNotFound

with Store("./dados") as s:
    s.set("posicao", "1042")
    print(s.get("posicao"))   # -> 1042
    print(s.list())           # -> ['posicao']
```
