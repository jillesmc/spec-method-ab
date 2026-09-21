---
status: completed
title: "Linha de comando"
type: feature
complexity: medium
---

# Linha de comando

## Outcome

Concluir a secao 3 do change `kvstore`.

## Itens

- [x] 3.1 Criar `kvstore/__main__.py` com `argparse`: diretório posicional e os subcomandos
- [x] 3.2 Escrever o valor de `get` como bytes em `sys.stdout.buffer`, sem newline acrescentado —
- [x] 3.3 Aceitar `-` na posição do valor de `set` lendo stdin por inteiro — verificar com teste de
- [x] 3.4 Mapear os desfechos para os códigos de saída `0`/`1`/`2`/`3`, com toda mensagem em stderr e
- [x] 3.5 Confirmar que `del` de chave inexistente sai 0 e que `list` em store vazio sai 0 com stdout

## Contexto

Convertido de `openspec/changes/kvstore/tasks.md` (secao 3).
Leia `openspec/changes/kvstore/proposal.md` e `design.md` quando existirem,
e os deltas em `specs/` antes de editar codigo.

## Verificacao

Rode a verificacao que o change define. Sem uma definida, use a do repositorio.
Depois da implementacao, `openspec validate kvstore --strict` deve passar.

<!-- origem: task_03 -->
