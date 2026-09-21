# Test Specification: fidx

Contrato canonico de teste do fidx. Companheiro de `_spec.md`.
Derivado de `_user_stories.md` (comportamento), `_spec.md` Part II (componentes) e `_dx.md`
(transcricoes de CLI). Sem `_uiux.md`: nao ha jornada de navegador.

## Strategy

- **Framework**: `unittest` da stdlib. Descoberto por `make test`
  (`python3 -m unittest discover -s tests -t .`), que e o unico portao de verificacao do repo.
- **Execucao**: tudo roda em um processo, exceto os casos `E2E-*`, que usam
  `subprocess.run([sys.executable, "-m", "fidx", ...], capture_output=True, text=True)`.
- **Fixtures**: `tempfile.TemporaryDirectory` com arvores de arquivos reais, montadas por um helper
  `arvore(raiz, {"sub/a.md": "texto"})` em cada arquivo de teste. Filesystem e SQLite sao reais em
  todos os niveis — sao o objeto da medicao, nao um I/O a ser fingido. O unico dublê permitido e um
  espiao sobre `fidx.core.tokenize` (UT-020), para provar que arquivo inalterado nao e reprocessado.
- **Convencoes**: um `TestCase` por area; nomes em portugues como o `tests/test_fumaca.py`
  existente; manipulacao de data sempre por `os.utime` explicito, nunca por `sleep`; nenhum teste
  depende de relogio de parede nem de ordem entre arquivos de teste.
- **Arquivos**: `tests/test_core.py` (UT de `core` + IT-001), `tests/test_cli.py` (E2E),
  `tests/test_incremental.py` (task_02), `tests/test_operacao.py` (task_03). O
  `tests/test_fumaca.py` existente continua como esta e nao pode quebrar.

## Coverage Matrix

| Source                   | Behavior                                              | Unit                   | Integration | E2E             |
| ------------------------ | ----------------------------------------------------- | ---------------------- | ----------- | --------------- |
| US-001 (AC-1, AC-5)      | Busca lista os arquivos do termo, ordenados, sem repetir | UT-013, UT-014         | IT-001      | E2E-001         |
| US-001.AC-2              | Casamento insensivel a maiuscula                       | UT-019                 | —           | —               |
| US-001.AC-3              | Varios tokens = E logico                               | UT-016                 | —           | E2E-005         |
| US-001.AC-4              | Resposta interativa                                    | —                      | —           | —               |
| US-001.EC-1              | Sem ocorrencia → exit 1                                | —                      | —           | E2E-002         |
| US-001.EC-2              | Termo sem token → exit 2                               | UT-017                 | —           | E2E-007         |
| US-001.EC-3              | Busca sem indice → exit 2 com instrucao                | UT-015                 | —           | E2E-003         |
| US-001.EC-4              | Arquivo apagado ainda listado ate a proxima rodada     | —                      | IT-003      | —               |
| US-001.EC-5              | Termo so dentro de `.git/` nao e achado                | UT-009                 | —           | —               |
| US-001.EC-6              | Busca durante rodada le a foto anterior                | —                      | IT-008      | —               |
| US-002.AC-1              | Primeira rodada cria o indice e resume a contagem      | UT-018                 | IT-001      | E2E-001         |
| US-002.AC-2              | Subpastas indexadas, caminho relativo preservado       | UT-008                 | IT-001      | —               |
| US-002.AC-3              | Entradas iniciadas por `.` ignoradas                   | UT-009                 | —           | —               |
| US-002.AC-4              | Acento preservado no token                             | UT-002, UT-019         | IT-001      | —               |
| US-002.EC-1              | Pasta vazia                                            | UT-012                 | —           | —               |
| US-002.EC-2              | Arquivo sem permissao → pulado com aviso               | UT-032                 | —           | —               |
| US-002.EC-3              | Arquivo some entre varredura e leitura → pulado        | UT-033                 | —           | —               |
| US-002.EC-4              | Bytes indecifraveis                                    | UT-030                 | —           | —               |
| US-002.EC-5              | Arquivo vazio                                          | UT-031                 | —           | —               |
| US-002.EC-6              | Symlink de diretorio nao seguido                       | UT-010                 | —           | —               |
| US-002.EC-7              | Caminho que nao e diretorio → exit 2                   | —                      | —           | E2E-004         |
| US-003 (AC-1)            | Rodada sem mudanca nao reprocessa                      | UT-020, UT-027         | —           | E2E-006         |
| US-003.AC-2, AC-4        | So o arquivo mudado e reescrito, sem posting velho     | UT-024, UT-026         | IT-002      | —               |
| US-003.AC-3              | Arquivo novo entra e conta como reindexado             | UT-026                 | —           | —               |
| US-003.EC-1              | Indice apagado entre rodadas → reconstroi              | —                      | IT-004      | —               |
| US-003.EC-2              | Esquema antigo → recria e reindexa                     | —                      | IT-005      | —               |
| US-003.EC-3              | Arquivo movido, mesmo conteudo                         | UT-028                 | —           | —               |
| US-003.EC-4              | Tudo mudou → igual a primeira rodada                   | UT-026                 | —           | —               |
| US-003.EC-5              | So remocoes na rodada                                  | UT-025                 | IT-003      | —               |
| US-004.AC-1              | Conteudo novo com data antiga e detectado              | UT-021                 | IT-002      | —               |
| US-004.AC-2              | Data nova com conteudo igual nao reindexa              | UT-023                 | —           | —               |
| US-004.AC-3              | Mesmo tamanho e mesma data, conteudo diferente         | UT-022                 | —           | —               |
| US-004.EC-1              | Conteudo restaurado ao anterior                        | UT-029                 | —           | —               |
| US-004.EC-2              | Dois arquivos com conteudo identico                    | UT-014                 | —           | —               |
| US-005.AC-1              | Arquivo apagado sai do indice                          | UT-025                 | IT-003      | —               |
| US-005.AC-2              | Subpasta inteira apagada                               | UT-025                 | —           | —               |
| US-005.EC-1              | Gemeo por conteudo permanece encontravel               | UT-014                 | —           | —               |
| US-005.EC-2              | Termo orfao passa a sair com 1                         | —                      | IT-003      | —               |
| US-005.EC-3              | Arquivo que virou symlink conta como removido          | UT-011                 | —           | —               |
| US-006.AC-1, AC-2        | Caminho invalido → exit 2                              | —                      | —           | E2E-004         |
| US-006.AC-3, EC-1        | Uso invalido → linha de uso, exit 2                    | —                      | —           | E2E-008         |
| US-006.AC-4              | Indice ausente distinto de "sem resultado"             | UT-015                 | —           | E2E-003         |
| US-006.EC-2              | Pasta so-leitura → exit 2 sem arquivo parcial          | —                      | —           | E2E-009         |
| US-006.EC-3              | Argumentos extras viram tokens do termo                | —                      | —           | E2E-005         |
| US-007.AC-1, EC-3        | Rodada interrompida nao deixa indice parcial           | —                      | IT-006, IT-009 | —            |
| US-007.AC-2, EC-2        | Rodada concorrente → exit 3, nada gravado              | —                      | IT-007      | —               |
| US-007.AC-3              | Busca durante rodada nao bloqueia                      | —                      | IT-008      | —               |
| US-007.EC-1              | `-wal`/`-shm` nunca indexados                          | UT-009                 | —           | —               |
| `core.file_digest`       | Digest de conteudo (base do ADR-001)                   | UT-005, UT-006, UT-007 | —           | —               |
| `core.tokenize`          | Normalizacao e quebra em tokens                        | UT-001–UT-004          | —           | —               |
| `__main__` resumo        | Linha de resumo no formato de `_dx.md`                 | —                      | —           | E2E-001, E2E-006 |

**US-001.AC-4 (resposta interativa)** nao tem caso automatizado: cronometrar e instavel em CI. A
propriedade e estrutural e ja esta coberta indiretamente — `search` abre somente o SQLite
(UT-015 falha se ela tentar varrer a pasta, e IT-008 prova que responde sem esperar a rodada).
Medicao de tempo fica para verificacao manual na pasta real do operador.

## Unit Tests

### `core.tokenize` (Spec: Implementation Design → Core Interfaces)

- **UT-001** (happy): `tokenize("Orcamento Anual 2026")` → `["orcamento", "anual", "2026"]`.
- **UT-002** (happy): `tokenize("Orçamento do mês")` → `["orçamento", "do", "mês"]` — acento faz
  parte do token, nao o quebra.
- **UT-003** (boundary): `tokenize("a,b\nc-d;e_f")` → `["a", "b", "c", "d", "e_f"]` — pontuacao e
  quebra de linha separam, `_` nao.
- **UT-004** (boundary): `tokenize("")` → `[]` e `tokenize("--- !!! ---")` → `[]`.

### `core.file_digest` (Spec: ADR-001)

- **UT-005** (happy): arquivo com `b"conteudo\n"` → digest igual a
  `hashlib.sha256(b"conteudo\n").hexdigest()`.
- **UT-006** (boundary): arquivo vazio → `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- **UT-007** (boundary): arquivo de 3 MiB (maior que o bloco de leitura de 1 MiB) → digest igual ao
  `hashlib.sha256` sobre os bytes inteiros, provando que a leitura em blocos nao perde dado.

### `core.iter_files` (Spec: Business Rules 6)

- **UT-008** (happy): arvore `a.md`, `sub/b.txt`, `sub/dir/c.md` → `["a.md", "sub/b.txt",
  "sub/dir/c.md"]`, caminhos relativos com `/`, em ordem estavel entre duas chamadas.
- **UT-009** (boundary): arvore com `.git/config`, `.oculto.md`, `.fidx.sqlite3`,
  `.fidx.sqlite3-wal` e `visivel.md` → so `["visivel.md"]`.
- **UT-010** (boundary): `sub/loop` e symlink para a raiz → a chamada termina, nao entra em recursao
  e `sub/loop` nao aparece na lista.
- **UT-011** (boundary): `link.md` e symlink para `a.md` → so `a.md` e listado.
- **UT-012** (boundary): diretorio vazio → `[]`.

### `core.index_dir` e `core.search` — ciclo basico (Spec: System Architecture)

- **UT-013** (happy): apos `index_dir` numa arvore em que `orcamento` esta em `a.md` e `sub/b.md`,
  `search(raiz, "orcamento")` → `["a.md", "sub/b.md"]`.
- **UT-014** (happy): `orcamento` repetido 10 vezes em `a.md` e presente em `copia.md` com conteudo
  identico ao de `a.md` → resultado tem os dois caminhos, cada um uma vez, em ordem crescente.
- **UT-015** (error): `search` em diretorio valido mas sem `.fidx.sqlite3` → levanta `IndexMissing`,
  e nenhum arquivo `.fidx.sqlite3` e criado pela tentativa.
- **UT-016** (happy): `a.md` contem "orcamento 2026", `b.md` contem so "orcamento" →
  `search(raiz, "orcamento 2026")` → `["a.md"]`.
- **UT-017** (error): `search(raiz, "---")` e `search(raiz, "")` → levantam `EmptyTerm` (distinto de
  resultado vazio).
- **UT-018** (happy): primeira `index_dir` numa arvore de 12 arquivos → devolve `(12, 12, 0)` e o
  arquivo `.fidx.sqlite3` passa a existir na raiz.
- **UT-019** (happy): `a.md` contem "Orçamento Anual" → `search(raiz, "ORÇAMENTO")` → `["a.md"]`.

### `core.index_dir` — incremental por conteudo (Spec: ADR-001)

- **UT-020** (state): duas `index_dir` seguidas sem mudanca, com espiao em `core.tokenize` → o
  espiao nao e chamado na segunda rodada, e o retorno e `(N, 0, 0)`.
- **UT-021** (state): arquivo indexado tem conteudo trocado e `os.utime` o coloca em 2020 → a rodada
  seguinte devolve `1` reindexado e `search` acha o termo novo.
- **UT-022** (state): conteudo trocado por outro de **mesmo tamanho**, com `os.utime` restaurando o
  `mtime` original → a rodada seguinte devolve `1` reindexado.
- **UT-023** (state): conteudo identico e `os.utime` com a data de agora → a rodada devolve
  `(N, 0, 0)`.
- **UT-024** (state): `a.md` tinha "alfa", passa a ter "beta" → depois da rodada,
  `search("alfa")` → `[]` e `search("beta")` → `["a.md"]`; nenhum posting orfao de `a.md` sobra.
- **UT-025** (state): `sub/` inteira apagada (2 arquivos) → a rodada devolve `2` removidos, e nem
  `files` nem `postings` tem linha com caminho iniciado por `sub/`.
- **UT-026** (boundary): rodada mista sobre 4 arquivos — 1 novo, 1 alterado, 1 apagado, 1 intacto →
  retorno `(3, 2, 1)`.
- **UT-027** (idempotency): duas rodadas seguidas sem mudanca → o despejo ordenado de `files` e de
  `postings` e byte a byte identico depois da segunda.
- **UT-028** (state): `a.md` movido para `sub/a.md` com o mesmo conteudo → retorno `(N, 1, 1)`, e
  `search` do termo devolve apenas `sub/a.md`.
- **UT-029** (state): `a.md` alterado, indexado, e depois restaurado ao conteudo original → a rodada
  seguinte reindexa e `search` devolve o resultado do conteudo original.

### `core.index_dir` — robustez de leitura (Spec: Business Rules 7 e 8)

- **UT-030** (error): arquivo com `b"\xff\xfe ola mundo"` → a rodada termina sem excecao, conta o
  arquivo no total, e `search("ola")` o devolve.
- **UT-031** (boundary): arquivo vazio → conta no total da rodada, tem linha em `files`, e nenhuma
  linha em `postings`.
- **UT-032** (error): arquivo com `chmod 0o000` → e pulado, a mensagem de aviso nomeia o caminho, os
  demais arquivos sao indexados e a rodada termina normalmente. (Pulado com `skipTest` quando os
  testes rodam como root, onde a permissao nao se aplica.)
- **UT-033** (error): arquivo removido entre a varredura e a leitura (simulado apagando o arquivo
  dentro do iterador) → pulado com aviso, rodada termina com os demais indexados.

## Integration Tests

### Ciclo indexa → busca (task_01)

- **IT-001**: arvore temporaria com `notas/a.md`, `notas/sub/b.txt` (com acento) e `.git/config`;
  roda `index_dir` e depois tres `search` — termo em um arquivo, termo em dois, termo so dentro de
  `.git/` → resultados `["a.md"]`, `["a.md", "sub/b.txt"]` e `[]`, com os caminhos relativos posix.

### Ciclo indexa → muda → reindexa (task_02)

- **IT-002**: indexa; reescreve `a.md` trocando "alfa" por "beta" e aplica `os.utime` com data de
  2020 (mais antiga que a original); reindexa → o resumo conta 1 reindexado, `search("alfa")` e `[]`
  e `search("beta")` e `["a.md"]`. Este e o caso que falha se a implementacao consultar `mtime`.
- **IT-003**: indexa 2 arquivos; apaga `b.md`; **antes** de reindexar, `search` do termo exclusivo de
  `b.md` ainda devolve `["b.md"]` (US-001.EC-4); reindexa → resumo com 1 removido e o mesmo `search`
  devolve `[]`.
- **IT-004**: indexa; apaga `.fidx.sqlite3` (e `-wal`/`-shm`, como um `rsync --delete` faria);
  reindexa → reconstroi tudo, resumo com todos reindexados, busca volta a funcionar, sem erro.
- **IT-005**: indexa; grava `meta.schema_version = '0'` por uma conexao direta; reindexa → as tabelas
  sao recriadas, todos os arquivos reindexados, e a busca responde certo.

### Operacao por cron (task_03)

- **IT-006**: com um indice ja completo, dispara uma rodada que levanta excecao apos o primeiro
  arquivo processado → a excecao sai, e depois dela o indice ainda responde exatamente o conteudo da
  rodada anterior (mesmos `files` e `postings`), sem nenhuma atualizacao parcial.
- **IT-007**: uma segunda conexao SQLite mantem uma transacao de escrita aberta sobre o indice;
  `index_dir` com timeout curto → levanta `IndexBusy` dentro do timeout e nao grava nada (o indice
  segue identico ao estado anterior).
- **IT-008**: com uma transacao de escrita aberta por outra conexao, `search` devolve o resultado da
  rodada anterior imediatamente, sem erro e sem esperar o timeout.
- **IT-009**: rodada **inicial** (sem indice anterior) interrompida por excecao no meio → a busca
  seguinte levanta `IndexMissing` ou devolve `[]`, nunca um resultado parcial; a rodada seguinte
  completa indexa tudo.

## End-to-End Tests

Invocacoes literais de `_dx.md`, por `subprocess`, conferindo `stdout`, `stderr` e `returncode`.

### Caminho feliz (US-001, US-002) — task_01

- **E2E-001**: `python3 -m fidx <tmp> index` → `stdout` casa
  `fidx: 3 arquivos, 3 reindexados, 0 removidos`, exit 0; em seguida
  `python3 -m fidx <tmp> search orcamento` → os caminhos no formato `<tmp>/sub/a.md`, um por linha,
  ordenados, exit 0.
- **E2E-002**: `python3 -m fidx <tmp> search jabuticaba` → `stdout` vazio, exit 1.
- **E2E-003**: `search` antes de qualquer `index` → `stderr` com
  `fidx: indice nao encontrado:` e a linha `fidx: rode primeiro: python3 -m fidx <tmp> index`,
  exit 2.
- **E2E-004**: `python3 -m fidx <tmp>/nao-existe index` → `stderr` `fidx: nao e um diretorio:`,
  exit 2; e o mesmo com `search`.
- **E2E-005**: `python3 -m fidx <tmp> search orcamento 2026` → so o arquivo que tem os dois tokens,
  exit 0 (prova tambem que argumento extra vira token, nao erro de uso — US-006.EC-3).

### Rodada de cron (US-003) — task_02

- **E2E-006**: dois `index` seguidos sem nenhuma alteracao → a segunda saida e
  `fidx: N arquivos, 0 reindexados, 0 removidos`, exit 0.

### Superficie de erro (US-006) — task_03

- **E2E-007**: `python3 -m fidx <tmp> search '---'` → `stderr`
  `fidx: termo sem token indexavel: '---'`, exit 2.
- **E2E-008**: `python3 -m fidx` sem argumentos → `stderr` com a linha de uso das duas formas,
  exit 2; idem para subcomando desconhecido e para `search` sem termo.
- **E2E-009**: `index` numa pasta com `chmod 0o500` (sem escrita) → `stderr`
  `fidx: nao foi possivel criar o indice:`, exit 2, e nenhum `.fidx.sqlite3` deixado para tras.
  (Pulado com `skipTest` quando rodando como root.)
