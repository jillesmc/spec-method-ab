---
status: completed
title: "CLI"
type: feature
complexity: medium
---

# CLI

## Outcome

Concluir a secao 4 do change `fidx`.

## Itens

- [x] 4.1 Implement `fidx/__main__.py` with `argparse`: positional `directory`, then `index` and
- [x] 4.2 Print the refresh report (files seen, reprocessed, removed) on stdout from `index`; verify
- [x] 4.3 Wire the exit codes — `0` on success or at least one match, `1` for a search with no match

## Contexto

Convertido de `openspec/changes/fidx/tasks.md` (secao 4).
Leia `openspec/changes/fidx/proposal.md` e `design.md` quando existirem,
e os deltas em `specs/` antes de editar codigo.

## Verificacao

Rode a verificacao que o change define. Sem uma definida, use a do repositorio.
Depois da implementacao, `openspec validate fidx --strict` deve passar.

<!-- origem: task_04 -->
