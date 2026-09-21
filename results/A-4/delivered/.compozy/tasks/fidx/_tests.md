# Test Specification: fidx

Contrato de testes canônico do fidx. Companheiro de `_spec.md`.
Derivado de `_user_stories.md` (comportamento), `_spec.md` Parte II (componentes) e `_dx.md` (jornadas de
CLI).

## Strategy

- **Framework**: `unittest` da stdlib. Nenhuma dependência nova — é restrição do enunciado.
- **Execução**: `make test` → `python3 -m unittest discover -s tests -t . -v`. Todo arquivo novo mora em
  `tests/` e se chama `test_*.py`, senão o discover não o encontra.
- **Fixtures**: `tempfile.TemporaryDirectory` por teste, com a árvore escrita pelo próprio caso. Nenhuma
  fixture versionada no repositório.
- **Fakes**: nenhum. sqlite em arquivo temporário e sistema de arquivos real — fake aqui esconderia
  exatamente o que precisa ser provado (digest, bloqueio, transação).
- **`mtime` mentiroso**: forjado com `os.utime(caminho, (t, t))`, para o passado e para o futuro.
- **Concorrência**: simulada com uma segunda conexão sqlite que segura `BEGIN IMMEDIATE`, não com processo
  paralelo — determinístico e sem `sleep`.
- **Convenções**: um arquivo por componente (`tests/test_scan.py`, `tests/test_store.py`,
  `tests/test_index.py`, `tests/test_cli.py`); nome do método descrevendo o comportamento, não o número do
  caso; o ID do caso no docstring.
- Testes que dependem de permissão de arquivo (`UT-008`, `IT-017`) usam
  `@unittest.skipIf(os.geteuid() == 0, ...)` — como root, `chmod 000` não impede leitura e o caso seria
  falso-positivo.

## Coverage Matrix

| Fonte         | Comportamento                                    | Unit                    | Integration | E2E              |
| ------------- | ------------------------------------------------ | ----------------------- | ----------- | ---------------- |
| US-001.AC-1   | Índice criado e resumo impresso                  | —                       | IT-001      | E2E-001          |
| US-001.AC-2   | Busca responde pelo índice, sem varrer            | —                       | IT-001      | E2E-001          |
| US-001.AC-3   | O próprio índice não é indexado                   | UT-012                  | —           | —                |
| US-001.EC-1   | Diretório vazio                                   | UT-013                  | IT-011      | —                |
| US-001.EC-2   | Diretório inexistente                             | —                       | —           | E2E-004          |
| US-001.EC-3   | Arquivo binário ignorado                          | UT-007                  | IT-010      | —                |
| US-001.EC-4   | Entradas ocultas e `.git/` puladas                | UT-012                  | IT-010      | —                |
| US-001.EC-5   | Pasta sem permissão de escrita                    | —                       | IT-017      | —                |
| US-001.EC-6   | Arquivo sem permissão de leitura                  | UT-008                  | —           | —                |
| US-002.AC-1   | Caminhos relativos, um por linha, ordenados       | UT-029                  | IT-001      | E2E-001          |
| US-002.AC-2   | Busca insensível a caixa                          | UT-002                  | —           | E2E-007          |
| US-002.AC-3   | Sem resultado → stdout vazio, saída 1             | UT-025                  | —           | E2E-002          |
| US-002.EC-1   | Busca antes de qualquer `index`                   | UT-021                  | —           | E2E-003          |
| US-002.EC-2   | Termo com mais de uma palavra é conjunção         | UT-026                  | —           | E2E-006          |
| US-002.EC-3   | Termo vazio ou só pontuação                       | UT-004, UT-027          | —           | —                |
| US-002.EC-4   | Pedaço de palavra não casa                        | UT-005                  | —           | —                |
| US-002.EC-5   | Busca reflete o último `index`, não o disco       | —                       | IT-016      | —                |
| US-003.AC-1   | Rodada sem mudança não reprocessa nada            | —                       | IT-002      | E2E-008          |
| US-003.AC-2   | Só o arquivo alterado é reprocessado              | —                       | IT-006      | —                |
| US-003.AC-3   | Arquivo novo entra e vira buscável                | —                       | IT-005      | —                |
| US-003.EC-1   | Renomeado com conteúdo idêntico                   | —                       | IT-008      | —                |
| US-003.EC-2   | `schema_version` divergente reconstrói            | UT-028                  | —           | —                |
| US-003.EC-3   | Dois `index` simultâneos                          | UT-031                  | IT-014      | —                |
| US-003.EC-4   | `index` interrompido não deixa índice pela metade | —                       | IT-013      | —                |
| US-003.EC-5   | `search` durante um `index` em andamento          | —                       | IT-015      | —                |
| US-004.AC-1   | Conteúdo novo com data antiga é reprocessado      | UT-009                  | IT-003      | —                |
| US-004.AC-2   | Data nova sem mudança de conteúdo é inalterado    | UT-009                  | IT-004      | —                |
| US-004.AC-3   | Termo da versão antiga deixa de apontar           | UT-023                  | IT-003      | —                |
| US-004.EC-1   | Mesmo tamanho, conteúdo diferente                 | UT-010                  | —           | —                |
| US-004.EC-2   | Dois arquivos com conteúdo idêntico               | UT-032                  | —           | —                |
| US-005.AC-1   | Arquivo apagado sai do índice                     | UT-024                  | IT-007      | —                |
| US-005.AC-2   | Arquivo que virou ignorado sai do índice          | —                       | IT-009      | —                |
| US-005.EC-1   | Todos os arquivos removidos                       | —                       | IT-012      | —                |
| US-005.EC-2   | Pasta inteira removida entre rodadas              | —                       | —           | E2E-004          |
| US-006.AC-1   | Sucesso → saída 0                                 | —                       | —           | E2E-001          |
| US-006.AC-2   | Busca vazia → saída 1                             | —                       | —           | E2E-002          |
| US-006.AC-3   | Erro de operação → saída 2 e stderr               | —                       | —           | E2E-003, E2E-004 |
| US-006.EC-1   | Subcomando ausente ou desconhecido                | —                       | —           | E2E-005          |
| US-006.EC-2   | stdout e stderr separados                         | —                       | —           | E2E-002, E2E-003 (asserções de stdout vazio + stderr preenchido; não precisa de caso próprio) |
| `fidx/scan.py`   | Elegibilidade, leitura, digest, tokenização    | UT-001–UT-014           | —           | —                |
| `fidx/store.py`  | Esquema, gravação, remoção, consulta, bloqueio | UT-020–UT-032           | —           | —                |
| `fidx/__main__.py` | Laço do `index`, resumo, contrato de CLI     | —                       | IT-001–IT-017 | E2E-001–E2E-008 |
| `fidx/__init__.py` | Pacote importável                            | coberto por `tests/test_fumaca.py` (já existe) | — | —      |

## Unit Tests

### `fidx/scan.py` (Spec: Implementation Design → Core Interfaces)

- **UT-001** (happy): `tokenizar("Orçamento Q3 aprovado")` → `{"orçamento", "q3", "aprovado"}` — acento
  preservado, sem normalização.
- **UT-002** (happy): `tokenizar("GREP grep Grep")` → `{"grep"}` — um único termo, em minúsculas.
- **UT-003** (happy): `tokenizar("a-b, c.d\ne_f")` → `{"a", "b", "c", "d", "e_f"}` — pontuação e quebra de
  linha separam; `_` é caractere de palavra.
- **UT-004** (boundary): `tokenizar("")` → `set()` e `tokenizar("--- ... ///")` → `set()`.
- **UT-005** (boundary): `"orca" not in tokenizar("orcamento anual")` — a unidade é a palavra inteira.
- **UT-006** (happy): `ler()` de um arquivo com `"nota de reuniao"` → tupla `(digest, texto)` com o texto
  idêntico ao gravado e `digest == hashlib.sha256(b"nota de reuniao").hexdigest()`.
- **UT-007** (error): `ler()` de um arquivo com os bytes `b"\xff\xfe\x00\x01PK"` → `None`.
- **UT-008** (error): `ler()` de um arquivo em modo `0o000` → `None` (não levanta). Pulado como root.
- **UT-009** (happy): `ler()` do mesmo conteúdo antes e depois de `os.utime(p, (0, 0))` e de
  `os.utime(p, (futuro, futuro))` → mesmo digest nas três leituras.
- **UT-010** (boundary): `ler()` de `b"aaaa"` e de `b"aaab"` → digests diferentes (mesmo tamanho em bytes).
- **UT-011** (happy): `percorrer()` de uma árvore com `a.txt` e `sub/b.txt` → `{"a.txt", "sub/b.txt"}`,
  relativos e com `/`.
- **UT-012** (boundary): `percorrer()` de uma árvore com `visivel.txt`, `.oculto.txt`, `.fidx.sqlite3` e
  `.git/config` → `{"visivel.txt"}`.
- **UT-013** (boundary): `percorrer()` de um diretório vazio → conjunto vazio.
- **UT-014** (state): `percorrer()` numa árvore com um link simbólico de diretório apontando para a própria
  raiz → termina e não devolve caminho repetido.

### `fidx/store.py` (Spec: Implementation Design → Data Models; ADR-002)

- **UT-020** (happy): `Indice.abrir(raiz, criar=True)` numa pasta sem índice → cria
  `<raiz>/.fidx.sqlite3`, e `digests()` devolve `{}`.
- **UT-021** (error): `Indice.abrir(raiz, criar=False)` sem índice no disco → `FileNotFoundError`, e nenhum
  arquivo é criado.
- **UT-022** (happy): `gravar("a.txt", "d1", {"orcamento"})` → `buscar({"orcamento"})` devolve `["a.txt"]`.
- **UT-023** (state): após `gravar("a.txt", "d1", {"velho"})` e depois
  `gravar("a.txt", "d2", {"novo"})` → `buscar({"velho"})` devolve `[]`, `buscar({"novo"})` devolve
  `["a.txt"]`, e `digests()["a.txt"] == "d2"`.
- **UT-024** (state): após `remover(["a.txt"])` → `"a.txt"` some de `digests()` e de qualquer `buscar()`.
- **UT-025** (boundary): `buscar({"jabuticaba"})` num índice populado → `[]`.
- **UT-026** (happy): com `a.txt` contendo `{"relatorio","mensal"}` e `b.txt` contendo `{"relatorio"}` →
  `buscar({"relatorio","mensal"})` devolve `["a.txt"]`.
- **UT-027** (boundary): `buscar(set())` → `[]` (nunca "todos os arquivos").
- **UT-028** (state): índice gravado com `meta.schema_version = "0"` → `Indice.abrir(criar=True)` o
  descarta e devolve um índice vazio (`digests() == {}`), sem levantar exceção.
- **UT-029** (happy): com `c.txt`, `a.txt` e `b.txt` contendo o mesmo termo → `buscar()` devolve
  `["a.txt", "b.txt", "c.txt"]`.
- **UT-030** (happy): `digests()` após gravar três caminhos → o dicionário exato `{caminho: digest}` dos três.
- **UT-031** (concurrency): com uma segunda conexão sqlite segurando `BEGIN IMMEDIATE` no mesmo arquivo →
  `Indice.abrir(raiz, criar=True)` (que também abre transação imediata) levanta `IndiceEmUso` dentro do
  `timeout`, e não `sqlite3.OperationalError`.
- **UT-032** (happy): `gravar("a.txt","d","{orcamento}")` e `gravar("copia.txt","d",{"orcamento"})` com o
  **mesmo** digest → `buscar({"orcamento"})` devolve os dois caminhos.

## Integration Tests

### Laço do `index` sobre `store` e `scan` reais (`tests/test_index.py`)

Todos montam uma árvore em `TemporaryDirectory` e chamam a função de indexação de `fidx/__main__.py`
diretamente, conferindo o dicionário de contagens que ela devolve e o estado do índice.

- **IT-001**: três arquivos de texto, pasta sem índice; indexar → contagens
  `novos=3, alterados=0, removidos=0, inalterados=0, ignorados=0`; `buscar` pelo termo exclusivo do segundo
  arquivo devolve só o caminho dele.
- **IT-002**: indexar duas vezes sem tocar em nada → a segunda devolve
  `novos=0, alterados=0, removidos=0, inalterados=3`, e `Indice.gravar` não é chamada nenhuma vez na segunda
  rodada (espionada com `unittest.mock.patch.object(..., wraps=...)`).
- **IT-003**: indexar; reescrever `a.txt` trocando `orcamento` por `previsao`; `os.utime(a.txt, (0, 0))`
  (data de 1970); indexar → `alterados=1`; `buscar({"previsao"})` devolve `["a.txt"]` e
  `buscar({"orcamento"})` devolve `[]`.
- **IT-004**: indexar; `os.utime(a.txt, (futuro, futuro))` sem alterar o conteúdo; indexar →
  `alterados=0, inalterados=3`.
- **IT-005**: indexar; criar `novo.txt` com o termo `jabuticaba`; indexar → `novos=1`, e
  `buscar({"jabuticaba"})` devolve `["novo.txt"]`.
- **IT-006**: indexar três arquivos; alterar só o conteúdo de `b.txt`; indexar →
  `novos=0, alterados=1, inalterados=2`.
- **IT-007**: indexar; apagar `a.txt`; indexar → `removidos=1`, e `buscar` pelo termo exclusivo de `a.txt`
  devolve `[]`.
- **IT-008**: indexar; renomear `a.txt` para `sub/renomeado.txt` sem mudar o conteúdo; indexar →
  `novos=1, removidos=1`, e a busca pelo termo devolve `["sub/renomeado.txt"]`.
- **IT-009**: indexar; sobrescrever `a.txt` com bytes não-UTF-8; indexar → `removidos=1, ignorados=1`, e a
  busca pelo termo antigo devolve `[]`.
- **IT-010**: árvore com `nota.txt`, `dump.bin` (bytes inválidos), `.oculto.txt` e `.git/config`; indexar →
  `novos=1, ignorados=1`, e `digests()` contém exatamente `{"nota.txt"}`.
- **IT-011**: diretório vazio; indexar → todas as contagens em zero e o índice é criado.
- **IT-012**: indexar três arquivos; apagar os três; indexar → `removidos=3`, `digests() == {}`, sem exceção.
- **IT-013** (idempotency/state): indexar; alterar dois arquivos; rodar a indexação com `scan.ler`
  injetado para levantar `RuntimeError` no segundo arquivo → a exceção propaga e, reabrindo o índice,
  `digests()` e as buscas são idênticos aos da primeira rodada (nada da rodada interrompida ficou).
- **IT-014** (concurrency): indexar; abrir uma segunda conexão segurando `BEGIN IMMEDIATE`; rodar a
  indexação → levanta `IndiceEmUso` e o índice permanece consultável com o conteúdo da rodada anterior.
- **IT-015** (concurrency): indexar; abrir uma conexão de escrita segurando a transação; `buscar` numa
  conexão de leitura → devolve o resultado da rodada anterior sem erro e sem esperar o `timeout`.
- **IT-016**: indexar; alterar o conteúdo de `a.txt` **sem** reindexar; `buscar` pelo termo antigo → ainda
  devolve `["a.txt"]` (a busca responde pelo índice, não pelo disco).
- **IT-017** (error): pasta em modo `0o555` sem índice; indexar → levanta o erro de gravação do índice
  (`sqlite3.OperationalError`/`PermissionError`) que `__main__` traduz na mensagem de `_dx.md`. Pulado como
  root.

## End-to-End Tests

### CLI pública (`tests/test_cli.py`)

Todos rodam `subprocess.run([sys.executable, "-m", "fidx", ...], capture_output=True, text=True)` a partir
de um `TemporaryDirectory`, e conferem `stdout`, `stderr` e `returncode` como em `_dx.md`.

- **E2E-001** (US-001, US-002, US-006): pasta com `orcamento-q3.txt` (contém `orcamento`) e
  `relatorios/2026-01.txt` (contém `orcamento`) → `index` sai 0 e imprime uma linha começando com
  `2 arquivos:` com as cinco contagens; `search orcamento` imprime exatamente
  `orcamento-q3.txt\nrelatorios/2026-01.txt\n` e sai 0.
- **E2E-002** (US-002, US-006): após indexar, `search jabuticaba` → `stdout == ""`, `returncode == 1`.
- **E2E-003** (US-002.EC-1, US-006.AC-3): `search orcamento` numa pasta nunca indexada → `stdout == ""`,
  `stderr` contém `indice nao encontrado` e a instrução de rodar `index`, `returncode == 2`.
- **E2E-004** (US-001.EC-2, US-005.EC-2): `index` e `search` num caminho inexistente → `stdout == ""`,
  `stderr` contém `nao e um diretorio` com o caminho, `returncode == 2`, e nada é criado no disco.
- **E2E-005** (US-006.EC-1): `python -m fidx <dir>` sem subcomando e `python -m fidx <dir> listar` →
  `returncode == 2` e `usage:` em `stderr` nos dois.
- **E2E-006** (US-002.EC-2): `a.txt` com `relatorio mensal`, `b.txt` só com `relatorio`;
  `search "relatorio mensal"` → imprime só `a.txt`, sai 0.
- **E2E-007** (US-002.AC-2): arquivo contendo `Orçamento aprovado`; `search orçamento` → imprime o caminho,
  sai 0.
- **E2E-008** (US-003.AC-1): `index` duas vezes seguidas → a segunda linha traz
  `0 novos, 0 alterados, 0 removidos` e o total de inalterados igual ao número de arquivos.

## Coverage Decisions

- Cada invariante alterado tem um dono: a elegibilidade e a tokenização ficam no nível de unidade de
  `scan`; o formato e o bloqueio do índice, no nível de unidade de `store`; as regras de negócio 1 a 3
  (incremental, espelho, substituição) na integração, porque só aparecem no laço; o contrato de saída e de
  código de saída no E2E, porque é a superfície pública.
- `tests/test_fumaca.py` continua sendo o dono de "o pacote importa"; nenhum caso novo duplica isso.
- US-006.EC-2 (stdout e stderr separados) não recebe ID próprio: as asserções de `stdout == ""` com `stderr`
  preenchido em E2E-002/003/004 já são a prova.
- Concorrência aparece em dois níveis de propósito: UT-031 prova a tradução do erro do sqlite, IT-014 prova
  o efeito no laço inteiro. Não há terceiro caso na CLI — o código de saída 2 já é coberto por E2E-003/004.
- Nenhum caso mede tempo de execução. "Mais rápido que o `grep`" não é asserção estável em CI; a garantia
  testável equivalente é IT-016 (a busca não lê a pasta) e IT-002 (a rodada sem mudança não grava nada).
