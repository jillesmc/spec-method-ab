# Developer Experience: fidx

Contrato de superficie publica do fidx. Companheiro de `_spec.md` (a Part II e desenhada para servir
esta superficie) e de `_tests.md` (os casos E2E usam estas invocacoes literalmente).

A superficie inteira e a CLI: nao ha YAML, HTTP/UDS, SDK, `config.toml` nem tool nativa — as secoes
correspondentes nao existem nesta feature.

## Golden Path

Do nada ate a primeira busca, em tres comandos:

```console
$ python3 -m fidx ./notas index
fidx: 1284 arquivos, 1284 reindexados, 0 removidos

$ python3 -m fidx ./notas search orcamento
./notas/2025/orcamento-q3.md
./notas/2026/plano-orcamento.txt
./notas/reunioes/2026-03-12.md

$ crontab -l | tail -1
*/30 * * * * cd <home> && python3 -m fidx ./notas index
```

A partir da segunda rodada, so o que mudou custa:

```console
$ python3 -m fidx ./notas index
fidx: 1285 arquivos, 2 reindexados, 1 removidos
```

## CLI

### `python3 -m fidx <diretorio> index`

Constroi ou atualiza o indice em `<diretorio>/.fidx.sqlite3`. Idempotente: rodar duas vezes seguidas
nao muda o indice na segunda.

```console
$ python3 -m fidx ./notas index
fidx: 1284 arquivos, 12 reindexados, 3 removidos
$ echo $?
0
```

Formato da linha de resumo, estavel para log de cron:

```
fidx: <total> arquivos, <reindexados> reindexados, <removidos> removidos
```

- `<total>` — arquivos no indice ao fim da rodada.
- `<reindexados>` — arquivos lidos, tokenizados e regravados (novos ou com conteudo diferente).
- `<removidos>` — caminhos que estavam no indice e nao existem mais no disco.

Pasta vazia:

```console
$ python3 -m fidx ./vazia index
fidx: 0 arquivos, 0 reindexados, 0 removidos
```

Arquivo que nao pode ser lido: a rodada continua e o aviso vai para `stderr`.

```console
$ python3 -m fidx ./notas index
fidx: aviso: pulado ./notas/privado/cofre.txt: Permission denied
fidx: 1283 arquivos, 0 reindexados, 0 removidos
$ echo $?
0
```

Caminho invalido:

```console
$ python3 -m fidx ./nao-existe index
fidx: nao e um diretorio: ./nao-existe
$ echo $?
2
```

Outra rodada segurando o indice:

```console
$ python3 -m fidx ./notas index
fidx: indice ocupado por outra rodada: ./notas/.fidx.sqlite3
$ echo $?
3
```

Sem saida estruturada (`--json`): a linha de resumo e o exit code sao o contrato de maquina.

### `python3 -m fidx <diretorio> search <termo>`

Consulta o indice. Nao abre nenhum arquivo da pasta.

```console
$ python3 -m fidx ./notas search orcamento
./notas/2025/orcamento-q3.md
./notas/2026/plano-orcamento.txt
./notas/reunioes/2026-03-12.md
$ echo $?
0
```

- Um caminho por linha, ordem crescente, sem repeticao.
- O caminho impresso e o diretorio **como voce digitou** mais o caminho relativo — pronto para
  `xargs`, `less` ou `$EDITOR`.
- Casamento e por **token inteiro**, sem distincao de maiuscula: `search LOG` acha `log` e `Log`,
  mas **nao** acha `logs` nem `catalogo`. Isto difere do `grep -r`, que casa substring.

Varios tokens: retorna os arquivos que contem todos eles, em qualquer posicao.

```console
$ python3 -m fidx ./notas search orcamento 2026
./notas/2026/plano-orcamento.txt
```

Sem ocorrencia — nada em `stdout`, exit 1, como o `grep`:

```console
$ python3 -m fidx ./notas search jabuticaba
$ echo $?
1
```

Encadeando:

```console
$ python3 -m fidx ./notas search orcamento | xargs -r $EDITOR
$ python3 -m fidx ./notas search orcamento || echo "nao achei"
```

Sem indice:

```console
$ python3 -m fidx ./notas search orcamento
fidx: indice nao encontrado: ./notas/.fidx.sqlite3
fidx: rode primeiro: python3 -m fidx ./notas index
$ echo $?
2
```

Termo sem token indexavel:

```console
$ python3 -m fidx ./notas search '---'
fidx: termo sem token indexavel: '---'
$ echo $?
2
```

### Uso

Sem argumentos, subcomando desconhecido, ou `search` sem termo:

```console
$ python3 -m fidx
fidx: uso: python3 -m fidx <diretorio> index
            python3 -m fidx <diretorio> search <termo>
$ echo $?
2
```

## Errors

Toda mensagem de erro e aviso vai para `stderr` com o prefixo `fidx: `; `stdout` carrega so
resultado (caminhos) ou o resumo da rodada.

| Condicao                                     | Saida (stderr)                                                                            | Exit |
| -------------------------------------------- | ----------------------------------------------------------------------------------------- | ---- |
| Rodada ou busca bem-sucedida                  | —                                                                                           | 0    |
| Busca sem nenhuma ocorrencia                  | —                                                                                           | 1    |
| Diretorio inexistente ou que e um arquivo     | `fidx: nao e um diretorio: <caminho>`                                                       | 2    |
| Busca sem indice (ou indice de esquema antigo)| `fidx: indice nao encontrado: <dir>/.fidx.sqlite3` + `fidx: rode primeiro: python3 -m fidx <dir> index` | 2 |
| Termo sem token indexavel                     | `fidx: termo sem token indexavel: '<termo>'`                                                | 2    |
| Uso invalido (sem args, subcomando, sem termo)| linha de uso                                                                                | 2    |
| Nao da para criar o indice (pasta so-leitura) | `fidx: nao foi possivel criar o indice: <dir>/.fidx.sqlite3: <motivo>`                      | 2    |
| Indice ocupado por outra rodada               | `fidx: indice ocupado por outra rodada: <dir>/.fidx.sqlite3`                                | 3    |
| Arquivo pulado durante a rodada (aviso)       | `fidx: aviso: pulado <caminho>: <motivo>`                                                   | 0    |

Distincao que importa no dia a dia: **1 = nao achei**, **2 = voce ou o estado esta errado**,
**3 = tente de novo depois**.
