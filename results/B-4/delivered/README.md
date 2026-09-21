# fidx

Indice de busca em pasta de arquivos de texto. So biblioteca padrao do Python 3.11+.

    make test
    python -m fidx ./notas index
    python -m fidx ./notas search orcamento

## Comandos

- `python -m fidx <directory> index` — percorre `<directory>` e atualiza o indice de
  forma incremental e content-addressed (SHA-256 dos bytes de cada arquivo, nao mtime).
  Imprime em stdout o relatorio da rodada: `seen=N reprocessed=N removed=N`.
- `python -m fidx <directory> search <term>` — busca `<term>` no indice e imprime, um por
  linha em stdout, os caminhos (relativos a `<directory>`) dos arquivos que contem o
  termo. Nao le nem escreve os arquivos da pasta, so o indice. Com mais de uma palavra em
  `<term>`, exige todas.

## Indice

O indice fica em `<directory>/.fidx/index.sqlite3` (SQLite). Entradas cujo nome comeca com
`.` — inclusive a propria `.fidx/` — nunca sao indexadas nem retornadas em buscas.

## Exit codes

- `0` — sucesso: `index` completou, ou `search` encontrou ao menos um resultado.
- `1` — `search` sem nenhum resultado (stdout vazio).
- `2` — erro de uso ou operacional: `<directory>` inexistente, indice ausente (rode
  `index` antes de `search`), ou termo de busca vazio apos normalizacao. Mensagem em
  stderr.
