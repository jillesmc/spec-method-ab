---
status: completed
title: "Núcleo de escrita durável (`kvstore/__init__.py`)"
type: feature
complexity: medium
---

# Núcleo de escrita durável (`kvstore/__init__.py`)

## Outcome

Concluir a secao 1 do change `kvstore`.

## Itens

- [x] 1.1 `_caminho(diretorio, chave)`: valida a chave (não vazia, sem `\n`, `\r`, `\0`, forma
- [x] 1.2 `_fsync_dir(caminho)`: `os.open(caminho, os.O_RDONLY)`, `os.fsync`, `os.close`.
- [x] 1.3 `set(diretorio, chave, valor)` e `set_stream(diretorio, chave, entrada)`: cria o
- [x] 1.4 `get(diretorio, chave)` e `get_stream(diretorio, chave, saida)`: lê o arquivo em blocos;
- [x] 1.5 `delete(diretorio, chave)`: `os.unlink` e `_fsync_dir` antes de retornar; ausência vira
- [x] 1.6 `keys(diretorio)`: `os.listdir`, mantém só os nomes com prefixo `k.`, `unquote` do

## Contexto

Convertido de `openspec/changes/kvstore/tasks.md` (secao 1).
Leia `openspec/changes/kvstore/proposal.md` e `design.md` quando existirem,
e os deltas em `specs/` antes de editar codigo.

## Verificacao

Rode a verificacao que o change define. Sem uma definida, use a do repositorio.
Depois da implementacao, `openspec validate kvstore --strict` deve passar.

<!-- origem: task_01 -->
