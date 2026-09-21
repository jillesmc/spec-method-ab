---
status: completed
title: "Linha de comando (`kvstore/__main__.py`)"
type: feature
complexity: medium
---

# Linha de comando (`kvstore/__main__.py`)

## Outcome

Concluir a secao 3 do change `kvstore`.

## Itens

- [x] 3.1 Parse com `argparse`: `<diretorio>` posicional, subcomandos `set` (chave, valor
- [x] 3.2 `set` sem o argumento de valor lê de `sys.stdin.buffer` em blocos, direto para o
- [x] 3.3 `get` escreve em `sys.stdout.buffer` em blocos, sem newline acrescentada.
- [x] 3.4 `list` imprime uma chave por linha, ordenado.
- [x] 3.5 Códigos de saída: 0 sucesso; 1 `KeyError`; 2 `ValueError`, uso inválido e `OSError`.

## Contexto

Convertido de `openspec/changes/kvstore/tasks.md` (secao 3).
Leia `openspec/changes/kvstore/proposal.md` e `design.md` quando existirem,
e os deltas em `specs/` antes de editar codigo.

## Verificacao

Rode a verificacao que o change define. Sem uma definida, use a do repositorio.
Depois da implementacao, `openspec validate kvstore --strict` deve passar.

<!-- origem: task_03 -->
