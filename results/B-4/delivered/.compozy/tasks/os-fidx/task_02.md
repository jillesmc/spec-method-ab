---
status: completed
title: "Content-addressed refresh"
type: feature
complexity: medium
---

# Content-addressed refresh

## Outcome

Concluir a secao 2 do change `fidx`.

## Itens

- [x] 2.1 Implement the directory walk that skips every entry whose name starts with `.`; verify with
- [x] 2.2 Implement `index_directory(directory)`: stream a SHA-256 per file with
- [x] 2.3 Delete from the index every path not seen in the walk; verify with a test that a deleted
- [x] 2.4 Report unreadable files on stderr, count them, keep their previous entry, and continue;
- [x] 2.5 **Timestamp trap A**: verify with a test that a file whose content is replaced and whose
- [x] 2.6 **Timestamp trap B**: verify with a test that touching a file's mtime to now without
- [x] 2.7 Verify with a test that a file moved to a new path with identical content is reported only

## Contexto

Convertido de `openspec/changes/fidx/tasks.md` (secao 2).
Leia `openspec/changes/fidx/proposal.md` e `design.md` quando existirem,
e os deltas em `specs/` antes de editar codigo.

## Verificacao

Rode a verificacao que o change define. Sem uma definida, use a do repositorio.
Depois da implementacao, `openspec validate fidx --strict` deve passar.

### Evidencia

- `make test` (`python3 -m unittest discover -s tests -t . -v`): 15 testes, todos `ok`
  (7 anteriores + 8 novos em `tests/test_refresh.py`, um por item 2.1-2.7 mais um
  cenario extra de exclusao do `.fidx` na propria arvore).
- `openspec validate fidx --strict`: **bloqueado** — `openspec` continua ausente nesta
  maquina (`which openspec` falha, `npx openspec --version` falha com
  "could not determine executable to run"). Mesmo bloqueio de task_01, nao especifico
  desta tarefa.

<!-- origem: task_02 -->
