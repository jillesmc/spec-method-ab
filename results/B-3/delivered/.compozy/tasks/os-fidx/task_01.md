---
status: completed
title: "Núcleo do índice (`fidx/__init__.py`)"
type: feature
complexity: medium
---

# Núcleo do índice (`fidx/__init__.py`)

## Outcome

Concluir a secao 1 do change `fidx`.

## Itens

- [x] 1.1 Implementar a varredura (`os.walk`, poda de entradas que começam com `.`, só arquivos
- [x] 1.2 Implementar a tokenização única (`re.findall(r"\w+", texto.casefold())`) usada na indexação e
- [x] 1.3 Criar/abrir o banco em `<dir>/.fidx/index.sqlite3` com as tabelas `files` e `postings` e
- [x] 1.4 Implementar `index(dir)`: ler bytes uma vez por arquivo, `sha256`, pular quem não decodifica
- [x] 1.5 Implementar `search(dir, termo)`: normalizar o termo com a mesma tokenização, consultar

## Contexto

Convertido de `openspec/changes/fidx/tasks.md` (secao 1).
Leia `openspec/changes/fidx/proposal.md` e `design.md` quando existirem,
e os deltas em `specs/` antes de editar codigo.

## Verificacao

Rode a verificacao que o change define. Sem uma definida, use a do repositorio.
Depois da implementacao, `openspec validate fidx --strict` deve passar.

<!-- origem: task_01 -->
