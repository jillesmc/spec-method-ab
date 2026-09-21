---
status: completed
title: "Storage and tokenising"
type: feature
complexity: medium
---

# Storage and tokenising

## Outcome

Concluir a secao 1 do change `fidx`.

## Itens

- [x] 1.1 Implement `tokens(text)` — `re.findall(r"\w+", text.casefold())` returned as a set — and
- [x] 1.2 Implement opening the index at `<directory>/.fidx/index.sqlite3`: create the directory and
- [x] 1.3 Make a `user_version` mismatch discard and rebuild the database instead of failing; verify

## Contexto

Convertido de `openspec/changes/fidx/tasks.md` (secao 1).
Leia `openspec/changes/fidx/proposal.md` e `design.md` quando existirem,
e os deltas em `specs/` antes de editar codigo.

## Verificacao

Rode a verificacao que o change define. Sem uma definida, use a do repositorio.
Depois da implementacao, `openspec validate fidx --strict` deve passar.

### Evidencia

- `make test` (`python3 -m unittest discover -s tests -t . -v`): 7 testes, todos `ok`
  (`test_fumaca` + 6 novos em `tests/test_storage.py` cobrindo 1.1, 1.2 e 1.3).
- `openspec validate fidx --strict`: **bloqueado** — o binario `openspec` nao esta
  instalado nesta maquina (`which openspec` e `npx openspec --version` falham). Nao
  executado; nenhum outro passo de verificacao depende dele.

<!-- origem: task_01 -->
