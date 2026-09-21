# Developer Experience: fidx

Contrato de superfície pública do fidx. Companheiro de `_spec.md` (a Parte II é desenhada para servir esta
superfície) e de `_tests.md` (os casos E2E usam exatamente estas invocações).

A única superfície do fidx é a CLI `python -m fidx`. Não há YAML, HTTP, SDK, `config.toml` nem tool nativa.

## Golden Path

```console
$ ls ~/notas | head -3
2025-fechamento.md
orcamento-q3.txt
reuniao-plataforma.md

$ python -m fidx ~/notas index
1240 arquivos: 1240 novos, 0 alterados, 0 removidos, 0 inalterados, 4 ignorados

$ python -m fidx ~/notas search orcamento
orcamento-q3.txt
relatorios/2026-01.txt
$ echo $?
0

# o cron roda de novo mais tarde; quase nada mudou
$ python -m fidx ~/notas index
1241 arquivos: 1 novos, 2 alterados, 0 removidos, 1238 inalterados, 4 ignorados
```

## CLI

### `python -m fidx <diretorio> index`

Varre `<diretorio>` recursivamente e atualiza o índice em `<diretorio>/.fidx.sqlite3`.

```console
$ python -m fidx ./notas index
1240 arquivos: 12 novos, 3 alterados, 2 removidos, 1225 inalterados, 4 ignorados
$ echo $?
0
```

Leitura da linha de resumo:

- `1240 arquivos` — arquivos presentes no índice ao fim da execução.
- `novos` — estavam no disco e não no índice.
- `alterados` — estavam no índice com outro conteúdo.
- `removidos` — estavam no índice e não foram mais encontrados (apagados, ocultos ou ignorados agora).
- `inalterados` — mesmo conteúdo da rodada anterior; não foram reprocessados.
- `ignorados` — encontrados mas não indexáveis (não decodificam como UTF-8, ou ilegíveis).

Primeira execução numa pasta vazia:

```console
$ python -m fidx ./vazia index
0 arquivos: 0 novos, 0 alterados, 0 removidos, 0 inalterados, 0 ignorados
$ echo $?
0
```

### `python -m fidx <diretorio> search <termo>`

Consulta o índice. Não toca nos arquivos da pasta.

```console
$ python -m fidx ./notas search orcamento
orcamento-q3.txt
relatorios/2026-01.txt
$ echo $?
0
```

Caminhos são relativos a `<diretorio>`, um por linha, em ordem alfabética.

Busca sem resultado — stdout vazio, saída 1 (convenção do `grep`):

```console
$ python -m fidx ./notas search jabuticaba
$ echo $?
1
```

Termo com mais de uma palavra: devolve os arquivos que contêm **todas** as palavras.

```console
$ python -m fidx ./notas search "relatorio mensal"
relatorios/2026-01.txt
```

A busca é por palavra inteira, insensível a caixa. `orca` não encontra `orcamento`.

## Errors

Toda mensagem de erro vai para **stderr**; stdout fica vazio.

| Condição                                     | Saída em stderr                                                                     | Código |
| -------------------------------------------- | ----------------------------------------------------------------------------------- | ------ |
| Diretório não existe ou não é diretório       | `fidx: nao e um diretorio: ./naoexiste`                                              | 2      |
| `search` antes de qualquer `index`            | `fidx: indice nao encontrado em ./notas; rode: python -m fidx ./notas index`          | 2      |
| Outro `index` rodando na mesma pasta          | `fidx: indice em uso por outra execucao: ./notas`                                     | 2      |
| Pasta sem permissão de escrita (no `index`)   | `fidx: nao foi possivel gravar o indice em ./notas: Permission denied`                | 2      |
| Subcomando ausente ou desconhecido            | uso do `argparse` (`usage: fidx [-h] diretorio {index,search} ...`)                   | 2      |

Códigos de saída:

| Código | Significado                                                                |
| ------ | --------------------------------------------------------------------------- |
| 0      | `index` concluído, ou `search` com ao menos um arquivo encontrado           |
| 1      | `search` sem nenhum arquivo encontrado                                      |
| 2      | não foi possível executar (uso, diretório, índice ausente, índice em uso)    |
