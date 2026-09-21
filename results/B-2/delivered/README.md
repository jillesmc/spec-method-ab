# kvstore

Armazenamento chave-valor durável em disco. Só biblioteca padrão do Python 3.11+.

    make test

## Uso

    python -m kvstore <diretorio> set <chave> <valor>
    python -m kvstore <diretorio> get <chave>
    python -m kvstore <diretorio> del <chave>
    python -m kvstore <diretorio> list

O diretório é criado sob demanda por `set`; `get`, `del` e `list` tratam um
diretório inexistente como um store vazio, sem criar nada.

Exemplo (cada linha roda como mostrado):

    python -m kvstore ./dados set foo bar
    python -m kvstore ./dados get foo
    # bar
    python -m kvstore ./dados list
    # foo
    python -m kvstore ./dados del foo
    python -m kvstore ./dados list
    # (stdout vazio)

`get` escreve em stdout exatamente o valor gravado, sem quebra de linha
acrescentada — o valor sobrevive a `$(...)` e a redirecionamento para arquivo
byte a byte.

### Valores grandes: `-` para ler de stdin

Como valores podem exceder o limite de tamanho da linha de comando, `set`
aceita `-` na posição do valor para ler o conteúdo inteiro de stdin:

    echo -n "conteúdo grande" | python -m kvstore ./dados set grande -
    python -m kvstore ./dados get grande
    # conteúdo grande

## Códigos de saída

| Código | Significado |
|---|---|
| `0` | sucesso |
| `1` | chave não encontrada (`get` de chave ausente) |
| `2` | erro de uso do CLI, ou chave inválida (vazia, com quebra de linha ou com `NUL`) |
| `3` | falha de dados ou de E/S (permissão negada, disco cheio, corrupção) |

`del` de chave inexistente e `list` num store vazio saem com código `0` — o
resultado pretendido (a chave não estar lá) já foi alcançado nos dois casos.
Toda mensagem de diagnóstico vai para stderr; stdout carrega só o dado pedido.
