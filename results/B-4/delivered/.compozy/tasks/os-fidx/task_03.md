---
status: completed
title: "Search"
type: feature
complexity: medium
---

# Search

## Outcome

Concluir a secao 3 do change `fidx`.

## Itens

- [x] 3.1 Implement `search(directory, term)` returning matching paths relative to the directory,
- [x] 3.2 Make search read only the index: it opens the database read-only, never walks the folder,
- [x] 3.3 Make search on a directory with no index raise a distinct error naming the `index` command;

## Contexto

Convertido de `openspec/changes/fidx/tasks.md` (secao 3).
Leia `openspec/changes/fidx/proposal.md` e `design.md` quando existirem,
e os deltas em `specs/` antes de editar codigo.

## Verificacao

Rode a verificacao que o change define. Sem uma definida, use a do repositorio.
Depois da implementacao, `openspec validate fidx --strict` deve passar.

<!-- origem: task_03 -->
