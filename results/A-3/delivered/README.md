# fidx

Indice de busca em pasta de arquivos de texto. So biblioteca padrao do Python 3.11+.

    make test
    python -m fidx ./notas index
    python -m fidx ./notas search orcamento

O indice mora em `<diretorio>/.fidx.sqlite3`, dentro da propria pasta indexada. Apagar o arquivo e
seguro: a proxima rodada de `index` reconstroi tudo do zero.

`index` grava o resumo da rodada em `stdout`:

    fidx: <total> arquivos, <reindexados> reindexados, <removidos> removidos

`search` casa por **token inteiro**, sem distincao de maiuscula: `search log` acha `log` e `Log`,
mas **nao** acha `logs` nem `catalogo` — diferente do `grep -r`, que casa substring.

## Exit codes

| Codigo | Significado                                                                          |
| ------ | ------------------------------------------------------------------------------------- |
| 0      | Rodada ou busca bem-sucedida (avisos de arquivo pulado nao mudam isto)                 |
| 1      | Busca sem nenhuma ocorrencia                                                           |
| 2      | Voce ou o estado esta errado: diretorio invalido, indice ausente, termo sem token indexavel, uso invalido, ou pasta sem permissao para criar o indice |
| 3      | Indice ocupado por outra rodada de `index` concorrente — tente de novo depois          |

Toda mensagem de erro e aviso vai para `stderr` com o prefixo `fidx: `; `stdout` carrega so
resultado (caminhos de `search`) ou o resumo da rodada de `index`.
