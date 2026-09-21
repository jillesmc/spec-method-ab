---
status: completed
title: "Varredura da pasta: elegibilidade, digest e tokenização"
type: backend
complexity: low
---

# Task 2: Varredura da pasta: elegibilidade, digest e tokenização

## Overview

Cria `fidx/scan.py`, o módulo que olha para o disco. Depois desta task existe a resposta para as três
perguntas que a indexação faz a cada arquivo: ele é elegível, qual é o digest do conteúdo dele, e quais
palavras ele contém. É aqui que mora a decisão da [ADR-001](adrs/adr-001.md) — o veredito vem do conteúdo,
nunca da data de modificação. É a outra metade do alicerce da task_03.

## Shippable Outcome

- Outcome: dada uma raiz, o código enumera os arquivos indexáveis, devolve digest e texto de cada um, e
  transforma texto em conjunto de termos — com a mesma função usada depois para tokenizar a consulta.
- Verify in this task: `tests/test_scan.py` (UT-001–UT-014), rodando por `make test`, contra árvores reais
  em diretório temporário.
- Integration verification: task_03 (laço do `index` sobre arquivos reais).

## Requirements

- Assinaturas como em `_spec.md` → Implementation Design → Core Interfaces: `percorrer`, `ler`, `tokenizar`.
- **Uma única função de tokenização** serve conteúdo e consulta: `re.findall(r"\w+", texto.lower())` como
  conjunto. Acentos preservados — nada de `unicodedata` removendo acento
  (`_spec.md` → Key Decisions).
- Elegibilidade (regra de negócio 4): arquivo regular cujo nome e cujos diretórios-pai relativos à raiz não
  começam com `.`. A regra é "começa com ponto", não uma lista de exclusões — é ela que exclui `.git/` e o
  próprio `.fidx.sqlite3`.
- `os.walk` sem seguir links simbólicos de diretório (padrão `followlinks=False`), o que também elimina
  ciclo.
- Um único `open(..., "rb").read()` por arquivo: os mesmos bytes alimentam o SHA-256 e a decodificação
  UTF-8 estrita (ADR-001 → Implementation Notes).
- Conteúdo que não decodifica como UTF-8, ou arquivo que não pode ser lido (`OSError`), devolve `None` —
  **não levanta**. Nada de `errors="ignore"`, que colocaria lixo de binário como termo no índice.
- **Não importar `fidx.store`**, não imprimir, não chamar `sys.exit`. O módulo é folha.
- Caminhos devolvidos são relativos à raiz e com `/` (`PurePath.as_posix()`).
- Só stdlib (`os`, `re`, `hashlib`, `pathlib`).

## Subtasks

- [x] 2.1 Criar `fidx/scan.py` com `tokenizar`.
- [x] 2.2 Implementar `percorrer(raiz)` com a regra de entradas ocultas (podando também os diretórios, para
      não descer em `.git/`).
- [x] 2.3 Implementar `ler(caminho)` devolvendo `(digest, texto)` ou `None`.
- [x] 2.4 Escrever `tests/test_scan.py` com os casos atribuídos, incluindo os de `mtime` forjado com
      `os.utime` e o de link simbólico cíclico.

## Implementation Details

Arquivo a criar: `fidx/scan.py`. Nenhum arquivo existente é modificado nesta task.

Na poda de diretórios do `os.walk`, alterar a lista `dirnames` **no lugar** (`dirnames[:] = [...]`) — é o
que impede a descida em `.git/`; filtrar depois não evita a varredura.

### Relevant Files

- `Makefile:2-4` — o discover que precisa achar `tests/test_scan.py`.
- `tests/test_fumaca.py` — convenção de `unittest` a seguir.

### Dependent Files

- `fidx/__main__.py` (criado na task_03) — único consumidor; chama `tokenizar` tanto no conteúdo quanto no
  termo de busca.

### Related ADRs

- [ADR-001: Detecção de mudança por hash de conteúdo, não por mtime](adrs/adr-001.md) — por que o digest
  sai da leitura, e por que `mtime` não aparece em lugar nenhum deste módulo.

## Deliverables

- `fidx/scan.py` com `percorrer`, `ler` e `tokenizar`.
- `tests/test_scan.py` cobrindo UT-001–UT-014.

## Tests

Casos atribuídos de [`_tests.md`](_tests.md) — ler cada definição antes de escrever o teste.

- [x] UT-001, UT-002, UT-003, UT-004, UT-005 — tokenização: acento, caixa, pontuação, vazio, palavra
      inteira.
- [x] UT-006, UT-007, UT-008 — leitura: texto, binário e arquivo sem permissão.
- [x] UT-009, UT-010 — digest: imune a `mtime`, sensível a um byte com o mesmo tamanho.
- [x] UT-011, UT-012, UT-013, UT-014 — varredura: recursão, entradas ocultas, pasta vazia, ciclo por link
      simbólico.

## Success Criteria

- `make test` passa com a suíte nova.
- `grep -n "mtime\|st_mtime\|getmtime" fidx/scan.py` não devolve nada — a ADR-001 é verificável no fonte.
- Nenhum `print`, nenhum `sys.exit` e nenhum `import` de `fidx.store` em `fidx/scan.py`.
