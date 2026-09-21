# fidx

Indice de busca em pasta de arquivos de texto. So biblioteca padrao do Python 3.11+.

    make test
    python -m fidx ./notas index
    python -m fidx ./notas search orcamento

O `index` grava o índice em `./notas/.fidx.sqlite3`; apague o arquivo para reconstruir do zero.
