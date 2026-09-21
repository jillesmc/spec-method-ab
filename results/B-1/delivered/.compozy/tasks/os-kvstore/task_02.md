---
status: completed
title: "Provas de durabilidade (`tests/test_durabilidade.py`)"
type: feature
complexity: medium
---

# Provas de durabilidade (`tests/test_durabilidade.py`)

## Outcome

Concluir a secao 2 do change `kvstore`.

## Itens

- [x] 2.1 Ordem das operações: com `unittest.mock.patch` em `os.fsync`, `os.replace` e
- [x] 2.2 Crash real: script auxiliar rodado com `subprocess`, que grava a chave e se mata com
- [x] 2.3 Escrever no topo do arquivo de teste, em comentário, a limitação declarada no design:
- [x] 2.4 Isolamento entre chaves: gravar `a` e `b`, capturar `stat` do arquivo de `b`, regravar
- [x] 2.5 Valor grande: `set` de ~10 MiB e `get` conferindo byte a byte, com afirmação de que a

## Contexto

Convertido de `openspec/changes/kvstore/tasks.md` (secao 2).
Leia `openspec/changes/kvstore/proposal.md` e `design.md` quando existirem,
e os deltas em `specs/` antes de editar codigo.

## Verificacao

Rode a verificacao que o change define. Sem uma definida, use a do repositorio.
Depois da implementacao, `openspec validate kvstore --strict` deve passar.

<!-- origem: task_02 -->
