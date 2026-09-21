---
status: completed
title: "CLI (`fidx/__main__.py`)"
type: feature
complexity: medium
---

# CLI (`fidx/__main__.py`)

## Outcome

Concluir a secao 3 do change `fidx`.

## Itens

- [x] 3.1 Montar o `argparse` com o contrato `<diretorio> {index,search}` (e `<termo>` no `search`) e
- [x] 3.2 `index`: validar que o diretório existe, chamar `index()`, imprimir o resumo em uma linha
- [x] 3.3 `search`: imprimir um path por linha, sair 0 com resultado e 1 sem resultado; teste verifica os
- [x] 3.4 Erros operacionais com mensagem em stderr e código 2: diretório inexistente, busca em diretório
- [x] 3.5 Tratar `sqlite3.OperationalError` de banco travado (rodadas de cron sobrepostas) com `timeout`

## Contexto

Convertido de `openspec/changes/fidx/tasks.md` (secao 3).
Leia `openspec/changes/fidx/proposal.md` e `design.md` quando existirem,
e os deltas em `specs/` antes de editar codigo.

## Verificacao

Rode a verificacao que o change define. Sem uma definida, use a do repositorio.
Depois da implementacao, `openspec validate fidx --strict` deve passar.

<!-- origem: task_03 -->
