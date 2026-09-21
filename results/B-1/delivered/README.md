# kvstore

Armazenamento chave-valor em disco. So biblioteca padrao do Python 3.11+.

    make test

## Uso

    python -m kvstore <diretorio> set <chave> [valor]
    python -m kvstore <diretorio> get <chave>
    python -m kvstore <diretorio> del <chave>
    python -m kvstore <diretorio> list

Se `valor` for omitido em `set`, o valor é lido de `stdin` em blocos — é o caminho para valores
grandes, que não cabem confortavelmente como argumento de linha de comando:

    python -m kvstore ./dados set foo bar
    cat arquivo-grande | python -m kvstore ./dados set foo
    python -m kvstore ./dados get foo
    python -m kvstore ./dados del foo
    python -m kvstore ./dados list

`get` escreve em `stdout` exatamente os bytes gravados, sem newline acrescentada; `list` imprime
uma chave por linha, ordenadas.

## Códigos de saída

| código | significado |
|---|---|
| 0 | sucesso |
| 1 | chave não encontrada (`get`/`del`) |
| 2 | uso inválido, chave inválida ou erro de E/S |

Mensagens de erro só em `stderr`; `stdout` recebe somente os dados pedidos.

## Contrato de durabilidade

Sucesso retornado por `set` ou `del` significa **persistido**: a operação só retorna depois do
`fsync` do arquivo e do diretório, então o dado sobrevive a um crash do processo ou a um restart —
nunca fica um "gravei" que na verdade só encheu o cache do kernel.
