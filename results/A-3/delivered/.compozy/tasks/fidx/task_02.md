---
status: completed
title: Reindexacao incremental por hash de conteudo
type: feature
complexity: high
---

# Task 2: Reindexacao incremental por hash de conteudo

## Overview

Depois desta task o `index` pode ficar no crontab: cada rodada compara o SHA-256 de cada arquivo com
o que esta gravado e **so** reprocessa o que mudou de conteudo, alem de remover do indice o que sumiu
do disco. E aqui que mora o risco central do projeto — os arquivos chegam por rsync e por checkout,
e a data deles mente nas duas direcoes, entao `mtime` nao participa da decisao (ADR-001).

## Shippable Outcome

- Outcome: numa pasta ja indexada, uma rodada sem alteracao imprime
  `fidx: N arquivos, 0 reindexados, 0 removidos` sem tokenizar nada; um arquivo com conteudo novo e
  data antiga e reindexado; um arquivo apagado some da busca na rodada seguinte.
- Verify in this task: `make test` com UT-020 a UT-029, IT-002 a IT-005 e E2E-006. IT-002 e o caso
  decisivo: ele falha se a implementacao consultar `mtime` em qualquer ponto.
- Integration verification: none.

## Requirements

- **O unico sinal de mudanca e o digest do conteudo.** Nem como pre-filtro, nem como atalho, nem como
  coluna guardada: `mtime`, `ctime`, `inode` e tamanho estao fora da decisao (ADR-001).
- O digest e calculado sobre bytes crus, antes de qualquer decodificacao.
- Arquivo com digest igual ao gravado nao e tokenizado nem regravado — nenhum `INSERT` em `postings`
  para ele. Essa e a economia inteira da feature; UT-020 prova com espiao sobre `tokenize`.
- Reindexar um caminho apaga **todos** os postings antigos dele antes de inserir os novos
  (Safety Invariant 5): nenhum termo do conteudo velho pode sobreviver.
- Caminho presente em `files` e ausente do disco e removido de `files` **e** de `postings` na mesma
  rodada (Safety Invariant 6).
- O digest novo e gravado na mesma transacao que os postings correspondentes — nunca digest novo com
  postings velhos.
- Contadores do resumo com o significado publicado em [`_dx.md`](_dx.md): `total` = arquivos no
  indice ao fim; `reindexados` = novos + com conteudo diferente; `removidos` = caminhos que sumiram.
- `meta.schema_version` diferente de `SCHEMA_VERSION` → derrubar e recriar as tabelas e reindexar
  tudo, com exit 0. Indice ausente (apagado por `rsync --delete`) segue o caminho normal de criacao:
  nao e erro.
- Sem caminho especial para renomeacao: caminho novo com conteudo conhecido e re-tokenizado
  (Non-Goal explicito do `_spec.md`).

## Subtasks

- [x] 2.1 `core.known_files(conn)` — devolve o mapa `{path: sha256}` gravado, em uma consulta.
- [x] 2.2 `index_dir`: comparar digest e pular o arquivo inalterado (sem leitura de texto, sem
      tokenizacao, sem escrita); contar `reindexados` so quando ha trabalho de verdade.
- [x] 2.3 `index_dir`: remover os caminhos que estavam no indice e nao apareceram na varredura, e
      contar `removidos`.
- [x] 2.4 Conferencia de `meta.schema_version` na abertura: divergiu, recria as tabelas.
- [x] 2.5 `tests/test_incremental.py` com UT-020 a UT-029 e IT-002 a IT-005; E2E-006 em
      `tests/test_cli.py`.

## Implementation Details

A mudanca e o `if` dentro do laco de `index_dir` que a task_01 deixou pronto:

```python
    conhecidos = known_files(conn)          # {path: sha256}
    for rel in iter_files(root):
        digest = file_digest(os.path.join(root, rel))
        if conhecidos.get(rel) != digest:   # unico criterio (ADR-001)
            replace_file(conn, rel, digest, tokenize(read_text(...)))
            reindexados += 1
        vistos.add(rel)
    removidos = remove_missing(conn, vistos)  # DELETE ... WHERE path NOT IN vistos
```

Cuidado com `remove_missing` em pasta grande: monte o conjunto de vistos em uma tabela temporaria ou
compare em memoria contra `known_files`, em vez de um `NOT IN (...)` com dezenas de milhares de
parametros — SQLite tem limite de variaveis por statement.

### Relevant Files

- `fidx/core.py` — **modificar**: `known_files`, a comparacao de digest no laco, `remove_missing`, a
  conferencia de versao de esquema.
- `tests/test_incremental.py` — **criar**: UT-020 a UT-029 e IT-002 a IT-005.
- `tests/test_cli.py` — **modificar**: acrescentar E2E-006 (duas rodadas seguidas).

### Dependent Files

- `fidx/__main__.py` — apenas consome a tupla de contadores ja existente; a linha de resumo nao muda
  de formato. Se precisar mudar, `_dx.md` e E2E-001 mudam junto.
- `.compozy/tasks/fidx/_dx.md` — significado publicado dos tres contadores; a implementacao segue ele.

### Related ADRs

- [ADR-001: Hash de conteudo como unico sinal de mudanca](adrs/adr-001.md) — a decisao que esta task
  implementa, com os dois modos de falha do `mtime` que motivaram tudo.
- [ADR-002: SQLite com indice invertido proprio](adrs/adr-002.md) — por que apagar os postings de um
  caminho e barato (indice `postings_path`) e por que o esquema e versionado.

## Deliverables

- `index_dir` incremental: rodada sem mudanca nao escreve em `postings`.
- Remocao de caminhos sumidos e contadores corretos no resumo.
- Reconstrucao automatica quando o indice sumiu ou tem esquema antigo.
- `tests/test_incremental.py` verde, junto de tudo que ja passava.

## Tests

Casos de [`_tests.md`](_tests.md) — leia a definicao de cada um antes de escrever.

- [x] UT-020, UT-023, UT-027 — rodada sem mudanca: nao tokeniza, contadores zerados, indice
      identico (inclui data nova com conteudo igual).
- [x] UT-021, UT-022, UT-029 — mudanca detectada com data mentirosa: data no passado, mesmo
      tamanho/mesma data, e conteudo restaurado ao anterior.
- [x] UT-024, UT-026, UT-028 — substituicao sem posting orfao, rodada mista `(3, 2, 1)`, arquivo
      movido.
- [x] UT-025 — remocao de caminho e de subpasta inteira.
- [x] IT-002, IT-003 — ciclos completos de alteracao com `os.utime` e de remocao (incluindo a janela
      em que o arquivo apagado ainda aparece, US-001.EC-4).
- [x] IT-004, IT-005 — indice apagado entre rodadas e indice com esquema antigo.
- [x] E2E-006 — duas rodadas seguidas pela CLI: a segunda com `0 reindexados, 0 removidos`.

## Success Criteria

- `make test` verde.
- `grep -rn "mtime\|st_mtime\|getmtime\|st_size" fidx/` nao devolve nada.
- Numa arvore de 200 arquivos ja indexada, a segunda rodada nao executa nenhum `INSERT` em
  `postings` — verificavel pelo espiao de UT-020 e pelo despejo identico de UT-027.
- Os tres contadores do resumo batem com os do enunciado em todas as combinacoes de UT-026.
