---
status: completed
title: "Os testes que sustentam a promessa de incrementalidade"
type: feature
complexity: medium
---

# Os testes que sustentam a promessa de incrementalidade

## Outcome

Concluir a secao 2 do change `fidx`.

## Itens

- [x] 2.1 Teste "conteúdo mudou com data antiga": indexar, alterar o conteúdo de um arquivo, forçar
- [x] 2.2 Teste "data nova sem mudança de conteúdo": indexar, avançar o `mtime` com `os.utime` sem tocar
- [x] 2.3 Teste "pasta inalterada": duas rodadas seguidas sem mudança devolvem `(0, N, 0)` na segunda e
- [x] 2.4 Teste "arquivo removido": apagar um arquivo indexado, reindexar e verificar 1 removido e busca
- [x] 2.5 Teste "o índice não indexa a si mesmo": duas rodadas seguidas, verificar que nenhum path sob
- [x] 2.6 Teste "arquivo binário": pasta com bytes não decodificáveis — `index` termina sem exceção e os

## Contexto

Convertido de `openspec/changes/fidx/tasks.md` (secao 2).
Leia `openspec/changes/fidx/proposal.md` e `design.md` quando existirem,
e os deltas em `specs/` antes de editar codigo.

## Verificacao

Rode a verificacao que o change define. Sem uma definida, use a do repositorio.
Depois da implementacao, `openspec validate fidx --strict` deve passar.

<!-- origem: task_02 -->
