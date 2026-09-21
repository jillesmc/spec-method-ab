# Proposal

## Why

Buscar um termo numa pasta grande de arquivos de texto hoje custa um `grep -r` que relê tudo a cada
consulta. Queremos pagar a leitura uma vez, num `index` que roda por cron, e responder a busca a partir
do índice. Como os arquivos chegam por rsync e por checkout de repositório, o `mtime` mente nas duas
direções (data antiga com conteúdo novo, data nova com conteúdo igual), então o que decide se um arquivo
precisa ser reprocessado é o **conteúdo**, não a data.

## What Changes

- Novo pacote executável `fidx` com duas subcomandos:
  - `python -m fidx <diretorio> index` — varre a pasta e atualiza o índice invertido.
  - `python -m fidx <diretorio> search <termo>` — lista os arquivos em que o termo aparece.
- O `index` é **incremental por conteúdo**: cada arquivo é lido e tem seu hash calculado; só os arquivos
  cujo hash mudou desde a rodada anterior são re-tokenizados e regravados no índice. O `mtime` nunca é
  consultado para decidir staleness.
- Arquivos que sumiram da pasta saem do índice na rodada seguinte.
- O `index` imprime um resumo da rodada (quantos reprocessados, inalterados, removidos) — é o que torna a
  promessa de incrementalidade verificável em teste.
- O índice mora em `<diretorio>/.fidx/index.sqlite3` e é excluído da própria varredura.
- Busca por token: casamento de palavra inteira, case-insensitive. Não é substring como o `grep`.
- Só biblioteca padrão (`sqlite3`, `hashlib`, `re`, `os`, `argparse`). Nenhuma dependência nova.

## Capabilities

### New Capabilities
- `file-index`: indexação incremental por conteúdo de uma pasta de arquivos de texto e busca por termo
  sobre esse índice, incluindo o contrato da CLI `python -m fidx`.

### Modified Capabilities
<!-- Nenhuma: o projeto ainda não tem specs publicadas. -->

## Impact

- Código: pacote `fidx/` (hoje só um `__init__.py` vazio) ganha `__main__.py` e os módulos de índice e
  busca; `tests/` ganha os testes da capability. `README.md` já descreve a CLI proposta.
- Dados em disco: cria `<diretorio>/.fidx/` dentro da pasta indexada (novo artefato no diretório do
  usuário).
- Dependências: nenhuma. Python 3.11+ como já declarado no README; `make test`
  (`python3 -m unittest discover`) continua sendo o portão.
- Sem API pública além da CLI; sem breaking change (não há versão anterior).
