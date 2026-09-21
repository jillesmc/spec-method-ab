---
status: completed
title: "Operações do store"
type: feature
complexity: medium
---

# Operações do store

## Outcome

Concluir a secao 2 do change `kvstore`.

## Itens

- [x] 2.1 Implementar `set`: upsert por chave, retorno só depois do `COMMIT` — verificar com teste de
- [x] 2.2 Implementar `get` e `delete`, com `delete` idempotente — verificar com testes de chave
- [x] 2.3 Implementar `list_keys` devolvendo só chaves vivas em ordem lexicográfica — verificar com
- [x] 2.4 Validar a chave na fronteira de entrada (vazia, com `\n`, com `NUL`) levantando erro próprio
- [x] 2.5 Tratar diretório inexistente como store vazio em `get`/`list_keys`, sem criar nada —
- [x] 2.6 Disparar `incremental_vacuum` após remoção — verificar com teste que grava muitas chaves
- [x] 2.7 Cobrir fidelidade de valor: texto de vários MB, com quebras de linha, acentuação, espaços nas

## Contexto

Convertido de `openspec/changes/kvstore/tasks.md` (secao 2).
Leia `openspec/changes/kvstore/proposal.md` e `design.md` quando existirem,
e os deltas em `specs/` antes de editar codigo.

## Verificacao

Rode a verificacao que o change define. Sem uma definida, use a do repositorio.
Depois da implementacao, `openspec validate kvstore --strict` deve passar.

<!-- origem: task_02 -->
