---
status: completed
title: "Abertura do store e pragmas de durabilidade"
type: feature
complexity: medium
---

# Abertura do store e pragmas de durabilidade

## Outcome

Concluir a secao 1 do change `kvstore`.

## Itens

- [x] 1.1 Implementar a abertura do store em `kvstore/__init__.py`: cria o diretório sob demanda,
- [x] 1.2 Aplicar `journal_mode=WAL`, `synchronous=FULL`, `busy_timeout` e `journal_size_limit` na
- [x] 1.3 Tornar a abertura idempotente e segura em store já existente — verificar com teste que abrir

## Contexto

Convertido de `openspec/changes/kvstore/tasks.md` (secao 1).
Leia `openspec/changes/kvstore/proposal.md` e `design.md` quando existirem,
e os deltas em `specs/` antes de editar codigo.

## Verificacao

Rode a verificacao que o change define. Sem uma definida, use a do repositorio.
Depois da implementacao, `openspec validate kvstore --strict` deve passar.

<!-- origem: task_01 -->
