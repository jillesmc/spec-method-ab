# fidx

Indice de busca em pasta de arquivos de texto. So biblioteca padrao do Python 3.11+.

    make test
    python -m fidx ./notas index
    python -m fidx ./notas search orcamento

O indice fica em `./notas/.fidx/` (SQLite), junto da pasta indexada. Ele viaja com a pasta e
some com um `rm -rf .fidx`; entradas cujo nome comeca com `.` (inclusive `.fidx/` e `.git/`)
nunca sao indexadas.

## Busca por palavra inteira

`search` casa a palavra inteira, normalizada do mesmo jeito na indexacao e na consulta
(`casefold` + `\w+`): sem substring, sem prefixo, sem regex, sem ranking. Um termo tem que
normalizar para exatamente uma palavra — `"nota fiscal"` ou `"---"` sao erro de uso, nao busca
vazia.

## Codigos de saida

- `0`: sucesso (`index` sempre; `search` com pelo menos um resultado).
- `1`: `search` sem nenhum resultado (convencao do `grep`, util em script/cron).
- `2`: erro de uso ou operacional — diretorio inexistente, termo invalido, `search` numa pasta
  nunca indexada (roda `index` antes), ou indice travado por uma rodada concorrente.
