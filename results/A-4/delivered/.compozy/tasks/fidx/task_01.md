---
status: completed
title: "Índice sqlite3: esquema, gravação, remoção e consulta"
type: backend
complexity: medium
---

# Task 1: Índice sqlite3: esquema, gravação, remoção e consulta

## Overview

Cria `fidx/store.py`, o módulo que é dono do arquivo de índice. Depois desta task existe um índice
persistente em `<raiz>/.fidx.sqlite3` capaz de guardar o digest de cada arquivo, substituir os termos de um
arquivo, apagar arquivos que sumiram e responder "quais caminhos contêm todos estes termos" — que é a
consulta que o `search` vai fazer. É a metade do alicerce que a task_03 costura.

## Shippable Outcome

- Outcome: o formato do índice existe e é operável por código — abrir/criar, gravar, remover, consultar, e
  falhar de forma nomeada quando outra execução está escrevendo.
- Verify in this task: `tests/test_store.py` (UT-020–UT-032), rodando por `make test`, contra um arquivo
  sqlite real em diretório temporário.
- Integration verification: task_03 (laço do `index`) e task_04 (concorrência e atomicidade pela CLI).

## Requirements

- Esquema exatamente como em [ADR-002](adrs/adr-002.md): `meta`, `arquivos`, `termos` e o índice
  `termos_caminho`. `schema_version = "1"` em `meta`.
- Assinaturas como em `_spec.md` → Implementation Design → Core Interfaces. Não inventar métodos que
  ninguém chama.
- **Não importar `fidx.scan`**, não imprimir, não chamar `sys.exit`. O módulo é folha
  (`_spec.md` → Architectural Boundaries).
- Só stdlib (`sqlite3`, `pathlib`).
- Caminhos são sempre relativos à raiz e com `/` (`PurePath.as_posix()`), tanto na gravação quanto na
  consulta.
- `PRAGMA journal_mode=WAL` na criação, para que a leitura funcione durante uma escrita
  (`_spec.md` → Safety Invariants 5).
- Transação explícita: `isolation_level=None` e `BEGIN IMMEDIATE` no `__enter__`, `COMMIT` no `__exit__`
  sem exceção, `ROLLBACK` com exceção (Safety Invariants 1–3).
- `timeout` de 2 s na conexão de escrita; `sqlite3.OperationalError` de "database is locked" vira
  `IndiceEmUso`, exceção do próprio módulo (Safety Invariants 4).
- `schema_version` divergente ou ausente → apagar o arquivo e recriar vazio, sem levantar exceção.
- `buscar(set())` devolve `[]`, nunca "todos os caminhos".

## Subtasks

- [x] 1.1 Criar `fidx/store.py` com a exceção `IndiceEmUso` e a constante do nome do arquivo de índice.
- [x] 1.2 Implementar `Indice.abrir(raiz, *, criar)`: criação do esquema, WAL, verificação de
      `schema_version` com reconstrução, e `FileNotFoundError` quando `criar=False` e o arquivo não existe.
- [x] 1.3 Implementar `digests()`, `gravar(caminho, digest, termos)` (apagando os termos antigos do caminho
      antes de inserir os novos) e `remover(caminhos)`.
- [x] 1.4 Implementar `buscar(termos)` com interseção e resultado ordenado.
- [x] 1.5 Implementar o protocolo de contexto (`BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK`) e a tradução do
      bloqueio para `IndiceEmUso`.
- [x] 1.6 Escrever `tests/test_store.py` com os casos atribuídos.

## Implementation Details

Arquivo a criar: `fidx/store.py`. Nenhum arquivo existente é modificado nesta task.

A interseção do `buscar` pode ser feita em SQL (`GROUP BY caminho HAVING COUNT(*) = ?` sobre
`termo IN (...)`) ou em Python sobre os conjuntos de cada termo. Qualquer uma serve; a de SQL evita trazer
listas grandes para a memória e é a preferida.

### Relevant Files

- `Makefile:2-4` — o discover que precisa achar `tests/test_store.py`.
- `tests/test_fumaca.py` — convenção de `unittest` a seguir.

### Dependent Files

- `fidx/__main__.py` (criado na task_03) — único consumidor deste módulo; as assinaturas daqui são o
  contrato dele.

### Related ADRs

- [ADR-002: Índice em sqlite3 com tabela invertida própria](adrs/adr-002.md) — esquema, WAL, transação
  única e o porquê de não usar FTS5.
- [ADR-001: Detecção de mudança por hash de conteúdo](adrs/adr-001.md) — o que a coluna `digest` guarda e
  por quê.

## Deliverables

- `fidx/store.py` com `Indice`, `IndiceEmUso` e o esquema.
- `tests/test_store.py` cobrindo UT-020–UT-032.

## Tests

Casos atribuídos de [`_tests.md`](_tests.md) — ler cada definição antes de escrever o teste.

- [x] UT-020, UT-021, UT-028 — abertura, criação, ausência e `schema_version` divergente.
- [x] UT-022, UT-023, UT-024, UT-030, UT-032 — gravação, substituição, remoção e estado devolvido.
- [x] UT-025, UT-026, UT-027, UT-029 — consulta: sem resultado, interseção, conjunto vazio, ordenação.
- [x] UT-031 — bloqueio por outra escrita vira `IndiceEmUso` dentro do `timeout`.

## Success Criteria

- `make test` passa com a suíte nova.
- Nenhum `print`, nenhum `sys.exit` e nenhum `import` de `fidx.scan` em `fidx/store.py`.
- Um índice escrito por esta task é inspecionável por fora:
  `sqlite3 <raiz>/.fidx.sqlite3 "select count(*) from arquivos"` responde sem erro.
