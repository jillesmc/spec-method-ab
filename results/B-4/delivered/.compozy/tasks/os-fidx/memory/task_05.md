# task_05 — Wrap-up

## Implementado

- `README.md`: adicionadas tres secoes depois do bloco de exemplo existente (mantido
  intacto) — `## Comandos` (os dois subcomandos e o que cada um imprime), `## Indice`
  (localizacao `<directory>/.fidx/index.sqlite3` e a regra de exclusao de entradas
  `.`-prefixadas), `## Exit codes` (0/1/2, cada um com a condicao exata que task_04 ja
  implementa).

## Verificacao

- `make test`: 30 testes, todos verdes (mesma contagem que task_04 — nenhum teste novo
  nesta tarefa, 5.2 e so confirmar a suite, incluindo `tests/test_fumaca.py`).
- 5.1 pede rodar os comandos exatamente como documentados contra um diretorio scratch:
  feito em `/tmp` com `PYTHONPATH=<repo>` (necessario porque `fidx` so resolve com o repo
  no path, mesmo padrao que `tests/test_cli.py` usa via `cwd=REPO_ROOT`). Confirmado:
  `index` cria `.fidx/index.sqlite3` e imprime `seen=N reprocessed=N removed=N`; `search`
  com termo acentuado (`orçamento`) casa o arquivo que contem `Orçamento` (exit 0) —
  tokens() preserva acentos (casefold, nao strip), entao um termo sem acento (`orcamento`)
  legitimamente da exit 1 (nao e bug, e o comportamento documentado em design.md decisao
  4); diretorio ausente -> exit 2; indice ausente -> exit 2; termo vazio apos normalizar
  -> exit 2.

## Bloqueio conhecido (repetido de todas as tarefas anteriores)

`openspec` CLI nao esta instalado nesta maquina (`which openspec` -> not found,
reconfirmado nesta tarefa). `openspec validate fidx --strict` nao pode ser executado
localmente — bloqueio de ferramenta externa, nao da implementacao.

## Estado final do change `fidx`

Todas as 5 secoes de `openspec/changes/fidx/tasks.md` implementadas e verificadas
(task_01–task_05). Suite completa: 30 testes, todos verdes.
