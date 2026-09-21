---
status: completed
title: "Comandos index e search ponta a ponta, com incremental"
type: feature
complexity: medium
---

# Task 3: Comandos index e search ponta a ponta, com incremental

## Overview

Costura `store` e `scan` em `fidx/__main__.py` e entrega os dois comandos prometidos no `README.md`. É a
**slice 1**: quando ela mergeia, o operador roda `python -m fidx <dir> index` e
`python -m fidx <dir> search <termo>`, recebe a lista de arquivos sem varrer a pasta, e a rodada seguinte do
cron reprocessa apenas o que mudou. É a task que resolve o Motivating Problem.

## Shippable Outcome

- Outcome: os dois verbos funcionam pela entrada real (`python -m fidx ...`) — o `index` constrói e
  atualiza o índice reprocessando só o que mudou e imprime o resumo de cinco contagens; o `search` imprime
  os caminhos encontrados, ordenados, e sai 0.
- Verify in this task: `tests/test_index.py` (IT-001–IT-012, IT-016) e `tests/test_cli.py`
  (E2E-001, E2E-006, E2E-007, E2E-008) — este último por subprocesso, na entrada real.
- Integration verification: task_04, que fecha o contrato de falha (códigos 1 e 2, mensagens, atomicidade e
  concorrência).

## Requirements

- Superfície exatamente como em [`_dx.md`](_dx.md): os dois verbos, a linha de resumo com as cinco
  contagens **nesta ordem** (`novos, alterados, removidos, inalterados, ignorados`), e o resultado da busca
  como um caminho por linha.
- Incremental pela regra de negócio 1: comparar o digest devolvido por `scan.ler` com o de
  `store.digests()`. Digest igual → conta inalterado e **não chama `gravar`**. `mtime` não é consultado.
- Regra de negócio 2 (espelho): ao fim da rodada, os caminhos do índice são exatamente os arquivos
  indexáveis vistos na varredura — o que sumiu, foi ignorado ou virou ilegível é removido e contado em
  `removidos`.
- Arquivo ignorado (`scan.ler` devolve `None`) é contado em `ignorados` e não entra no índice.
- `search` tokeniza o termo com a **mesma** `scan.tokenizar` usada na indexação, e devolve a interseção.
- `search` não abre nenhum arquivo da pasta (Safety Invariant 6): o resultado vem do índice.
- Toda a indexação acontece dentro de uma transação (`with Indice.abrir(...)`) — a garantia é de task_01,
  aqui é só usar o gerenciador de contexto e não abrir `COMMIT` no meio.
- `argparse` com `diretorio` posicional seguido dos subcomandos `index` e `search`, como no `README.md`.
- Único módulo que escreve em stdout. Nesta task basta o caminho feliz; os códigos 1 e 2 e as mensagens de
  erro são de task_04.
- Acrescentar `.fidx.sqlite3` ao `.gitignore` e a linha sobre o arquivo de índice no `README.md`.

## Subtasks

- [x] 3.1 Criar `fidx/__main__.py` com o `argparse` dos dois verbos.
- [x] 3.2 Implementar a função de indexação (recebe a raiz, devolve as cinco contagens) usando
      `store.Indice` e `scan`, com a comparação de digest e a remoção dos caminhos não vistos.
- [x] 3.3 Implementar o `search`: tokenizar, consultar, imprimir os caminhos ordenados.
- [x] 3.4 Imprimir a linha de resumo do `index` no formato de `_dx.md`.
- [x] 3.5 Acrescentar `.fidx.sqlite3` ao `.gitignore` e documentar o arquivo de índice no `README.md`.
- [x] 3.6 Escrever `tests/test_index.py` e a parte de caminho feliz de `tests/test_cli.py`.

## Implementation Details

Arquivos a criar: `fidx/__main__.py`, `tests/test_index.py`, `tests/test_cli.py`.
Arquivos a modificar: `.gitignore`, `README.md`.

A função de indexação deve ser chamável **sem passar pela CLI** (recebe a raiz e devolve as contagens) — é o
que permite os casos IT-* assertarem contadores sem parsear texto, e é o que a task_04 injeta para testar
interrupção.

Fluxo, como em `_spec.md` → System Architecture: validar diretório → abrir índice → `digests()` →
para cada caminho de `scan.percorrer`: `ler` → ignorado, inalterado ou `gravar` → ao fim `remover` dos
caminhos não vistos → sair do `with` (COMMIT) → imprimir.

### Relevant Files

- `fidx/store.py` (task_01) — `Indice.abrir`, `digests`, `gravar`, `remover`, `buscar` e o gerenciador de
  contexto que dá a transação.
- `fidx/scan.py` (task_02) — `percorrer`, `ler`, `tokenizar`.
- `README.md` — as duas invocações já prometidas ao operador; a CLI precisa bater com elas.
- `_dx.md` — o formato exato do resumo e do resultado da busca.
- `Makefile:2-4` — o discover das suítes novas.

### Dependent Files

- `.gitignore` — passa a ignorar `.fidx.sqlite3`.
- `fidx/__init__.py` — continua vazio e importável; `tests/test_fumaca.py` segue valendo.

### Related ADRs

- [ADR-001](adrs/adr-001.md) — a comparação de digest que decide reprocessar.
- [ADR-002](adrs/adr-002.md) — onde o índice mora e por que ele não aparece na própria varredura.

## Deliverables

- `fidx/__main__.py` com `index` e `search` funcionando pela entrada real.
- `tests/test_index.py` e `tests/test_cli.py` (caminho feliz).
- `.gitignore` e `README.md` atualizados.

## Tests

Casos atribuídos de [`_tests.md`](_tests.md) — ler cada definição antes de escrever o teste.

- [x] IT-001, IT-005, IT-011 — primeira indexação, arquivo novo, pasta vazia.
- [x] IT-002, IT-006 — rodada sem mudança não grava nada; só o arquivo alterado é reprocessado.
- [x] IT-003, IT-004 — `mtime` recuado com conteúdo novo reprocessa; `mtime` avançado sem mudança não.
- [x] IT-007, IT-008, IT-009, IT-012 — remoção, renomeação, arquivo que virou ignorado, pasta esvaziada.
- [x] IT-010 — binário e entradas ocultas não entram no índice.
- [x] IT-016 — a busca responde pelo índice, não pelo disco.
- [x] E2E-001 — jornada completa pela CLI: `index` e `search` com saída 0.
- [x] E2E-006, E2E-007 — termo com duas palavras (conjunção) e busca insensível a caixa.
- [x] E2E-008 — segunda rodada do `index` com `0 novos, 0 alterados, 0 removidos`.

## Success Criteria

- `make test` passa com todas as suítes.
- A transcrição do Golden Path de `_dx.md` roda numa pasta de teste e produz a saída descrita, incluindo a
  ordem das cinco contagens.
- Rodar `index` duas vezes seguidas não altera o arquivo de índice além do esperado: nenhuma chamada a
  `gravar` na segunda rodada (asserção de IT-002).
- `grep -n "mtime" fidx/__main__.py` não devolve nada.
