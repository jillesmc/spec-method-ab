---
status: completed
title: Indexar e buscar de ponta a ponta
type: feature
complexity: medium
---

# Task 1: Indexar e buscar de ponta a ponta

## Overview

Depois desta task o operador para de esperar o `grep -r`: `python3 -m fidx ./notas index` constroi um
indice em `./notas/.fidx.sqlite3` e `python3 -m fidx ./notas search orcamento` lista os arquivos que
contem o termo sem abrir nenhum arquivo da pasta. E a entrega do Motivating Problem inteiro. Esta
rodada ainda reescreve o indice todo a cada execucao — o incremental e a task_02 —, mas ja congela o
esquema do SQLite e a superficie da CLI que as duas tasks seguintes consomem.

## Shippable Outcome

- Outcome: `index` seguido de `search` funciona pela CLI real, com os caminhos, a ordem, o formato do
  resumo e os exit codes descritos em [`_dx.md`](_dx.md).
- Verify in this task: `make test` com os casos UT-001 a UT-019, IT-001 e E2E-001 a E2E-005; os E2E
  rodam `python3 -m fidx` em subprocesso, que e o caminho de entrada de verdade.
- Integration verification: none — as tasks 02 e 03 tem seus proprios portoes.

## Requirements

- **So stdlib** (`hashlib`, `os`, `re`, `sqlite3`, `pathlib`, `sys`). Nenhuma dependencia nova.
- Esquema do SQLite exatamente como em [`_spec.md`](_spec.md) § Data Models (`meta`, `files`,
  `postings`, indice `postings_path`, `meta.schema_version = 1`). As tasks seguintes dependem dele.
- Separacao de camadas de [`_spec.md`](_spec.md) § Architectural Boundaries: `core.py` devolve dados
  ou levanta excecao — nao imprime, nao le `sys.argv`, nao chama `sys.exit`. Todo `print` e todo
  exit code ficam em `__main__.py`. Sem isso, os UT precisariam de subprocesso.
- Tokenizacao e casamento conforme Business Rules 4 e 5: minusculas, `re.findall(r"\w+")` com
  Unicode (acento dentro do token), casamento por token inteiro, varios tokens = E logico.
- Varredura conforme Business Rule 6: pula toda entrada com `.` inicial e **todo** symlink, de
  arquivo ou de diretorio. `os.walk(..., followlinks=False)` nao basta para arquivos: filtre
  explicitamente com `os.path.islink`.
- Caminho gravado e sempre relativo a raiz, com `/` como separador, inclusive no Windows (use
  `pathlib.PurePath.as_posix`).
- Mensagens em portugues sem acento, prefixadas com `fidx: `, como o `README.md` atual; erro e aviso
  em `stderr`, resultado e resumo em `stdout`.
- Nesta task a rodada pode reindexar todos os arquivos, mas ja deve **gravar** o `sha256` de cada um
  em `files` e devolver a tupla `(total, reindexados, removidos)` — a task_02 usa essa coluna e esses
  contadores, nao os cria.
- `search` abre o indice somente para leitura e **nunca** o cria: sem indice e `IndexMissing`
  (exit 2), nunca resultado vazio (exit 1).

## Subtasks

- [x] 1.1 `fidx/core.py`: `tokenize`, `file_digest` (leitura em blocos de 1 MiB), `iter_files`.
- [x] 1.2 `fidx/core.py`: abertura/criacao do indice com o esquema, `PRAGMA journal_mode=WAL`, e as
      excecoes `FidxError`/`NotADirectory`/`IndexMissing`/`EmptyTerm`.
- [x] 1.3 `fidx/core.py`: `index_dir(root)` — varre, hasheia, tokeniza, grava `files` e `postings`,
      devolve `(total, reindexados, removidos)`.
- [x] 1.4 `fidx/core.py`: `search(root, term)` — tokeniza o termo, intersecao dos postings, lista
      ordenada e sem repeticao.
- [x] 1.5 `fidx/__main__.py`: parse manual de `<dir> <comando> [termo...]`, linha de uso, impressao
      do resumo e dos caminhos (diretorio como digitado + caminho relativo), traducao de excecao em
      exit code (0/1/2).
- [x] 1.6 `tests/test_core.py` com UT-001 a UT-019 e IT-001; `tests/test_cli.py` com E2E-001 a
      E2E-005.

## Implementation Details

Padroes de codigo e assinaturas em [`_spec.md`](_spec.md) § Implementation Design.

Esqueleto do `index_dir` desta task (a task_02 troca apenas o `if` de decisao):

```python
def index_dir(root: str) -> tuple[int, int, int]:
    if not os.path.isdir(root):
        raise NotADirectory(root)
    conn = open_index(root, create=True)
    with conn:                       # COMMIT no fim, ROLLBACK em excecao
        vistos, reindexados = set(), 0
        for rel in iter_files(root):
            digest = file_digest(os.path.join(root, rel))
            replace_file(conn, rel, digest, tokenize(read_text(os.path.join(root, rel))))
            vistos.add(rel)
            reindexados += 1
        removidos = remove_missing(conn, vistos)
    return len(vistos), reindexados, removidos
```

### Relevant Files

- `fidx/core.py` — **criar**: toda a logica (varredura, conteudo, armazenamento, as duas operacoes).
- `fidx/__main__.py` — **criar**: unica porta de entrada; argv, saida e exit codes.
- `fidx/__init__.py` — permanece vazio; so precisa seguir importavel.
- `tests/test_core.py` — **criar**: UT-001 a UT-019 e IT-001.
- `tests/test_cli.py` — **criar**: E2E-001 a E2E-005 por `subprocess`.

### Dependent Files

- `tests/test_fumaca.py:1-14` — teste existente que importa `fidx`; nao pode quebrar, e e o estilo a
  seguir (`unittest.TestCase`, sem framework, sem fixture).
- `Makefile:1-4` — `python3 -m unittest discover -s tests -t .` ja descobre os arquivos novos; nao
  precisa mudar, e nao deve.
- `README.md:1-8` — ja publica estas tres invocacoes; a CLI entregue tem de bater com elas
  (a atualizacao do texto e da task_03).

### Related ADRs

- [ADR-002: SQLite com indice invertido proprio](adrs/adr-002.md) — o esquema criado aqui e o dele;
  em especial `WITHOUT ROWID`, o indice por `path` e `search` abrindo somente leitura.
- [ADR-001: Hash de conteudo como unico sinal de mudanca](adrs/adr-001.md) — por que a coluna
  `files.sha256` ja e gravada nesta task, mesmo antes de ser usada para decidir.

## Deliverables

- `fidx/core.py` e `fidx/__main__.py` funcionando pelas invocacoes de `_dx.md`.
- Indice SQLite com o esquema congelado (`schema_version = 1`).
- `tests/test_core.py` e `tests/test_cli.py` verdes junto com o teste de fumaca existente.

## Tests

Casos de [`_tests.md`](_tests.md) — leia a definicao de cada um antes de escrever.

- [x] UT-001, UT-002, UT-003, UT-004 — tokenizacao (acento, pontuacao, vazio).
- [x] UT-005, UT-006, UT-007 — digest de conteudo, incluindo arquivo maior que o bloco de leitura.
- [x] UT-008, UT-009, UT-010, UT-011, UT-012 — varredura: subpastas, dot-entries, symlinks, vazio.
- [x] UT-013, UT-014, UT-016, UT-018, UT-019 — ciclo indexa/busca: ordem, dedupe, E logico,
      contadores da primeira rodada, insensibilidade a maiuscula.
- [x] UT-015, UT-017 — erros de `search`: indice ausente, termo sem token.
- [x] IT-001 — ciclo completo sobre arvore temporaria com acento e `.git/`.
- [x] E2E-001, E2E-002, E2E-003, E2E-004, E2E-005 — transcricoes literais de `_dx.md`.

## Success Criteria

- `make test` verde, incluindo `tests/test_fumaca.py`.
- Nenhum import fora da stdlib em `fidx/`.
- `grep -rn "mtime\|st_mtime\|getmtime" fidx/` nao devolve nada: a decisao de conteudo e do ADR-001 e
  nao pode entrar por atalho nem nesta task.
- Buscar um termo nao abre nenhum arquivo da pasta indexada (`search` toca apenas o `.fidx.sqlite3`).
