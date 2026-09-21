---
status: completed
title: "Testes de falha abrupta (o núcleo da mudança)"
type: feature
complexity: medium
---

# Testes de falha abrupta (o núcleo da mudança)

## Outcome

Concluir a secao 4 do change `kvstore`.

## Itens

- [x] 4.1 Escrever o auxiliar de teste que roda uma gravação num subprocesso e o mata com `SIGKILL`,
- [x] 4.2 Teste: `set` confirmado seguido de `SIGKILL` imediato — exigir que um processo novo leia o
- [x] 4.3 Teste: `del` confirmado seguido de `SIGKILL` imediato — exigir que a chave continue ausente
- [x] 4.4 Teste: `SIGKILL` **durante** a gravação, em vários instantes diferentes, sobre uma chave que
- [x] 4.5 Teste: store com muitas chaves confirmadas, `SIGKILL` no meio de uma gravação nova — exigir
- [x] 4.6 Teste: abrir um diretório deixado por `SIGKILL` (com `-wal` pendente) — exigir que a primeira

## Contexto

Convertido de `openspec/changes/kvstore/tasks.md` (secao 4).
Leia `openspec/changes/kvstore/proposal.md` e `design.md` quando existirem,
e os deltas em `specs/` antes de editar codigo.

## Verificacao

Rode a verificacao que o change define. Sem uma definida, use a do repositorio.
Depois da implementacao, `openspec validate kvstore --strict` deve passar.

<!-- origem: task_04 -->
