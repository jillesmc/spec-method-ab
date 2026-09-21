# Test Specification: kvstore

Contrato canônico de testes do `kvstore`. Companheiro de `_spec.md`. Derivado de `_user_stories.md`
(comportamento), `_spec.md` Part II (componentes) e `_dx.md` (jornadas de linha de comando).

**Numeração agrupada, de propósito:** `UT-001`–`UT-019` são operações de `Store`, `UT-020`–`UT-024` são
invariantes de configuração e limite; `IT-010`+ é durabilidade, `IT-020`+ é concorrência, `IT-030`+ é
crescimento. As lacunas entre os grupos são intencionais e estáveis — ADR-002 já cita `IT-010..IT-014` e
`UT-020/UT-021`. IDs são permanentes: nunca renumerar nem reaproveitar.

## Strategy

- **Framework**: `unittest` da biblioteca padrão, descoberto pelo alvo existente
  `python3 -m unittest discover -s tests -t .`. Zero dependência externa, em execução e em teste.
- **Fixtures**: `tempfile.TemporaryDirectory` por caso. Nenhum caminho fixo, nenhuma ordem de execução
  pressuposta, nenhum resíduo na árvore do repositório.
- **Fakes**: nenhum. O sistema de arquivos real é a coisa sob teste — um `sqlite3` falso provaria que o
  código chama o que achamos que chama, e o que precisa ser provado é que o dado sobrevive.
- **Unidade**: importam `kvstore.Store` direto.
- **Integração**: `subprocess` e `os.kill`. **Sincronização nunca por relógio**: o filho anuncia
  prontidão escrevendo numa pipe e o pai reage a isso; `sleep` só aparece, se aparecer, como teto de
  segurança, nunca como condição de corrida.
- **E2E**: `subprocess.run([sys.executable, "-m", "kvstore", ...])` com as invocações verbatim de
  `_dx.md`, conferindo `stdout`, `stderr` e `returncode`. `sys.executable` garante o mesmo interpretador
  do `make test`.
- **Convenções**: nomes de teste em português, seguindo `tests/test_fumaca.py`. Um comportamento
  observável por caso. Casos que dependem de sinal POSIX usam
  `@unittest.skipUnless(os.name == "posix", ...)`.
- **Arquivos**: `tests/test_store.py` (UT), `tests/test_durabilidade.py` (IT), `tests/test_cli.py`
  (E2E). `tests/test_fumaca.py` permanece como está.

## Coverage Matrix

| Source        | Behavior                                    | Unit                   | Integration     | E2E                  |
| ------------- | ------------------------------------------- | ---------------------- | --------------- | -------------------- |
| US-001.AC-1   | `set` grava e sai com 0                     | UT-001                 | —               | E2E-001              |
| US-001.AC-2   | `set` sobrescreve                           | UT-002                 | —               | E2E-004              |
| US-001.AC-3   | confirmação implica durabilidade            | —                      | IT-010, IT-011  | —                    |
| US-001.EC-1   | chave vazia rejeitada                       | UT-009                 | —               | E2E-005              |
| US-001.EC-2   | valor vazio ≠ ausente                       | UT-008                 | —               | E2E-006              |
| US-001.EC-3   | chave com `/`, `..`, acento, newline        | UT-011                 | —               | E2E-007              |
| US-001.EC-4   | diretório sem permissão de escrita          | UT-016                 | —               | E2E-025              |
| US-001.EC-5   | falha de escrita preserva valor anterior    | —                      | IT-022          | —                    |
| US-002.AC-1   | `get` devolve o valor, sem newline extra    | UT-001                 | —               | E2E-003              |
| US-002.AC-2   | `get` de ausente: stdout vazio, código 1    | UT-003                 | —               | E2E-002              |
| US-002.EC-1   | valor terminado em newline preservado       | UT-018                 | —               | E2E-003              |
| US-002.EC-2   | valor de vários MB não truncado             | UT-012                 | —               | E2E-024              |
| US-002.EC-3   | `get` em diretório virgem → código 1        | —                      | —               | E2E-022              |
| US-003.AC-1   | `del` remove e sai com 0                    | UT-004                 | —               | E2E-008              |
| US-003.AC-2   | remoção é durável                           | —                      | IT-014          | —                    |
| US-003.EC-1   | `del` de ausente é idempotente (código 0)   | UT-005                 | —               | E2E-008              |
| US-003.EC-2   | `del` repetido                              | UT-019                 | —               | E2E-008              |
| US-004.AC-1   | `list` ordenado, uma chave por linha        | UT-006                 | —               | E2E-010              |
| US-004.AC-2   | `list` vazio → saída vazia, código 0        | UT-007                 | —               | E2E-009              |
| US-004.EC-1   | chave com newline: API íntegra, CLI ambígua | UT-024                 | —               | — (ver Decisions)    |
| US-004.EC-2   | muitas chaves, sem truncar                  | —                      | IT-031          | —                    |
| US-004.EC-3   | `list \| head -1` sem `BrokenPipeError`     | —                      | —               | E2E-023              |
| US-005.AC-1   | valor grande por stdin                      | —                      | —               | E2E-011              |
| US-005.AC-2   | stdin vazio → valor vazio                   | —                      | —               | E2E-012              |
| US-005.EC-1   | gravar o texto literal `-`                  | —                      | —               | E2E-027              |
| US-005.EC-2   | stdin e argumento juntos → código 2         | —                      | —               | E2E-013              |
| US-005.EC-3   | stdin não-UTF-8 → código 2                  | —                      | —               | E2E-014              |
| US-006.AC-1   | `Store` em processo, mesma durabilidade     | UT-014                 | IT-010          | —                    |
| US-006.AC-2   | `get` ausente devolve `None`                | UT-003                 | —               | —                    |
| US-006.AC-3   | `delete` devolve `True`/`False`             | UT-004, UT-005         | —               | —                    |
| US-006.EC-1   | uso após `close()` levanta erro             | UT-013                 | —               | —                    |
| US-006.EC-2   | milhares de escritas sem vazar descritor    | UT-017                 | —               | —                    |
| US-006.EC-3   | chave não-`str` → `TypeError`               | UT-010                 | —               | —                    |
| US-007.AC-1   | `SIGKILL` após confirmação não perde dado   | —                      | IT-010, IT-011  | —                    |
| US-007.AC-2   | morte durante escrita: antigo ou novo       | —                      | IT-012          | —                    |
| US-007.AC-3   | nunca volta vazio nem ilegível              | —                      | IT-013          | —                    |
| US-007.EC-1   | `os._exit` sem `close()`/`atexit`/flush     | —                      | IT-010          | —                    |
| US-007.EC-2   | queda de energia da máquina                 | UT-021                 | —               | — (ver Decisions)    |
| US-007.EC-3   | terceiro apagando arquivos auxiliares       | —                      | —               | — (fora de escopo)   |
| US-008.AC-1   | tamanho acompanha o vivo, não a soma        | —                      | IT-030          | —                    |
| US-008.AC-2   | leitura não degrada com o histórico         | —                      | IT-030, IT-031  | —                    |
| US-008.AC-3   | README sem rotina periódica                 | —                      | —               | — (revisão, tarefa 4)|
| US-008.EC-1   | arquivo não encolhe, espaço é reaproveitado | —                      | IT-032          | —                    |
| US-008.EC-2   | muitas chaves grandes, leitura barata       | —                      | IT-031          | —                    |
| US-009.AC-1   | diretório criado no primeiro `set`          | UT-015                 | —               | E2E-018              |
| US-009.AC-2   | `list` em diretório inexistente → vazio     | —                      | —               | E2E-019              |
| US-009.EC-1   | caminho é arquivo comum → código 3          | UT-016                 | —               | E2E-020              |
| US-009.EC-2   | pai sem permissão de criação → código 3     | —                      | —               | E2E-021              |
| US-010.AC-1   | leitor em paralelo com escritor             | —                      | IT-020          | —                    |
| US-010.AC-2   | dois escritores, chaves diferentes          | —                      | IT-021          | —                    |
| US-010.EC-1   | dois escritores, mesma chave                | —                      | IT-022          | —                    |
| US-010.EC-2   | contenção além da espera → código 3         | —                      | IT-023          | —                    |
| `Store`       | pragmas efetivos (invariante 5)             | UT-020, UT-021, UT-022 | —               | —                    |
| `Store`       | escala: muitas chaves, ordem e integridade  | UT-023                 | IT-031          | —                    |
| CLI           | uso, verbo desconhecido, aridade errada     | —                      | —               | E2E-015, E2E-016, E2E-017 |
| CLI           | arquivos em disco vistos pelo operador      | —                      | —               | E2E-026              |
| `_dx.md`      | Golden Path verbatim                        | —                      | —               | E2E-001              |

## Unit Tests

### `Store` — operações (Spec: Implementation Design → Core Interfaces)

Arquivo: `tests/test_store.py`.

- **UT-001** (happy): `set`/`get` — `s.set("posicao", "1042")` seguido de `s.get("posicao")` devolve
  exatamente `"1042"`.
- **UT-002** (happy): sobrescrita — `set("k","a")`, `set("k","b")`, `get("k")` devolve `"b"`.
- **UT-003** (happy): ausência — `s.get("nunca_gravada")` devolve `None`, sem levantar exceção.
- **UT-004** (happy): `delete` de existente — após `set("k","v")`, `s.delete("k")` devolve `True` e
  `s.get("k")` devolve `None`.
- **UT-005** (happy): `delete` de ausente — `s.delete("nunca_gravada")` devolve `False` e não levanta.
- **UT-006** (happy): `keys` ordenado — gravadas `"posicao"`, `"config"`, `"contador"`, `s.keys()`
  devolve `["config", "contador", "posicao"]`, exatamente nessa ordem.
- **UT-007** (boundary): `keys` vazio — em `Store` recém-criado, `s.keys()` devolve `[]`.
- **UT-008** (boundary): valor vazio — `s.set("k", "")` e `s.get("k")` devolve `""`, que é `!= None`;
  o caso prova que ausência e vazio são distinguíveis.
- **UT-009** (error): chave vazia — `s.set("", "v")` levanta `ValueError`, e `s.keys()` continua `[]`
  (nada foi gravado).
- **UT-010** (error): chave não-`str` — `s.set(1, "v")` levanta `TypeError`; idem `s.get(1)` e
  `s.delete(1)`.
- **UT-011** (boundary): chaves hostis — cada uma de `"a/b"`, `"../fuga"`, `"chave com espaço"`,
  `"ação"`, `"com\nnewline"` é gravada e relida literalmente; `keys()` contém todas as cinco.
  Prova que a chave nunca é interpretada como caminho.
- **UT-012** (boundary): valor grande — `"x" * 5_000_000` gravado e relido idêntico, com
  `len(s.get("blob")) == 5_000_000`.
- **UT-013** (state): uso após `close()` — `s.close()` e depois `s.get("k")` levanta
  `sqlite3.ProgrammingError`; a chamada não grava nem devolve valor em silêncio.
- **UT-014** (happy): gerenciador de contexto — `with Store(d) as s: s.set("k","v")`; ao sair do bloco,
  um `Store` novo sobre `d` devolve `"v"`.
- **UT-015** (happy): diretório criado — `Store(os.path.join(tmp, "nao", "existe"))` cria o caminho e
  `set`/`get` funcionam.
- **UT-016** (error): caminho é arquivo comum — criado um arquivo regular em `p`, `Store(p)` levanta
  erro de sistema de arquivos nomeando `p`, sem criar nada ao lado.
- **UT-017** (boundary): sem vazamento de descritor — antes e depois de 5.000 `set` no **mesmo**
  `Store`, a contagem de `os.listdir("/proc/self/fd")` é igual; pulado fora do Linux.
- **UT-018** (boundary): newline final preservado — `s.set("k", "linha\n")` e `s.get("k")` devolve
  `"linha\n"`, com o newline e nada além dele.
- **UT-019** (state): `delete` repetido — `delete("k")` duas vezes após um `set` devolve `True` e
  depois `False`, sem exceção em nenhuma das duas.

### `Store` — invariantes de configuração e escala (Spec: Safety Invariants 1, 5)

Estes três são a defesa contra o risco nomeado em ADR-002: `synchronous` é **por conexão** e some sem
sintoma se algum caminho abrir conexão sem repeti-lo.

- **UT-020** (boundary): `journal_mode` efetivo — num `Store` aberto,
  `s._con.execute("PRAGMA journal_mode").fetchone()[0].lower()` é `"wal"`.
- **UT-021** (boundary): `synchronous` efetivo — `PRAGMA synchronous` devolve `2` (`FULL`). É a única
  cobertura possível de US-007.EC-2 (queda de energia), e a razão está em Coverage Decisions.
- **UT-022** (boundary): `busy_timeout` efetivo — `PRAGMA busy_timeout` devolve `5000`, o valor que a
  mensagem de erro de contenção promete ao operador em `_dx.md`.
- **UT-023** (boundary): escala de chaves — 2.000 chaves `f"chave{i:05d}"` gravadas; `len(s.keys())` é
  2.000, a lista está em ordem crescente, e `s.get("chave01234")` devolve o valor correspondente.
- **UT-024** (boundary): chave com newline em `keys()` — a chave `"a\nb"` aparece íntegra na lista
  devolvida pela API. O caso documenta que a ambiguidade de US-004.EC-1 é da saída de texto da linha de
  comando, não da API.

## Integration Tests

Arquivo: `tests/test_durabilidade.py`. Todos pulados fora de POSIX.

### Durabilidade sob morte abrupta (US-007; Safety Invariants 1–4)

- **IT-010**: morte sem encerramento limpo — um filho (`subprocess` com script via `-c`) abre `Store`,
  faz `set("posicao", "1042")` e chama `os._exit(0)` imediatamente, sem `close()`, sem `__exit__`, sem
  `atexit`, sem flush. O pai espera o filho terminar, abre `Store` no mesmo diretório e espera
  `get("posicao") == "1042"`. É o cenário de OOM do enunciado.
- **IT-011**: `SIGKILL` externo após confirmação — o filho grava, escreve `pronto\n` numa pipe e fica
  bloqueado em leitura; o pai lê `pronto`, envia `SIGKILL`, confirma o código de término `-9`, reabre e
  espera o valor gravado. Sincronização por pipe, nunca por `sleep`.
- **IT-012**: morte **durante** a escrita — a chave `"blob"` tem previamente o valor `"A" * 1_000_000`;
  o filho inicia `set("blob", "B" * 8_000_000)` e o pai envia `SIGKILL` enquanto a escrita corre. Ao
  reabrir, `get("blob")` é **ou** o valor antigo inteiro **ou** o novo inteiro — o teste falha se for
  qualquer outra coisa (prefixo, mistura, `None`) — e a chave `"sentinela"`, gravada antes, continua
  intacta. Repetido algumas vezes para atingir instantes diferentes da escrita.
- **IT-013**: nunca volta vazio — 500 chaves gravadas e confirmadas; um filho grava a 501ª e é morto
  com `SIGKILL` em instante arbitrário. Ao reabrir, as 500 originais estão todas legíveis com os
  valores corretos e `keys()` tem 500 ou 501 entradas. Falha se o armazenamento vier vazio ou ilegível
  — o sintoma exato relatado no enunciado.
- **IT-014**: remoção é durável — o filho faz `delete("posicao")` sobre uma chave existente e chama
  `os._exit(0)`; ao reabrir, `get("posicao")` é `None`. A remoção tem a mesma garantia da gravação.

### Concorrência entre processos (US-010; Safety Invariants 6–8)

- **IT-020**: leitor durante escritor — um filho grava em laço; o pai executa `get` repetidamente no
  mesmo diretório. Toda leitura devolve um valor completo e válido (um dos gravados, nunca parcial) e
  nenhuma levanta exceção.
- **IT-021**: dois escritores, chaves diferentes — dois filhos gravam `"a"` e `"b"` simultaneamente;
  ambos terminam com código 0 e, ao final, as duas chaves têm os valores esperados.
- **IT-022**: dois escritores, mesma chave — dois filhos gravam valores diferentes em `"k"`; ambos
  terminam com 0 e `get("k")` devolve exatamente um dos dois valores, íntegro. Nenhum erro de banco
  travado escapa.
- **IT-023**: contenção além da espera — um filho abre transação de escrita exclusiva
  (`BEGIN IMMEDIATE`) e a segura por mais de 5 s; o pai executa `python -m kvstore <dir> set k v` e
  espera término com código 3, com a mensagem de contenção de `_dx.md` em stderr, em menos de ~10 s.
  Falha se o comando travar indefinidamente.

### Falha de escrita e crescimento (US-001.EC-5, US-008)

- **IT-030** (crescimento): 2.000 `set` na **mesma** chave com valor de 4 KB (soma escrita: 8 MB). Ao
  final, `os.path.getsize` do `kvstore.sqlite3` é inferior a 2 MB, e `get` devolve o último valor. É a
  prova de que o custo não acumula por gravação. **Caso mais lento da suíte** (2.000 `fsync`): se
  passar de poucos segundos, reduzir a contagem sem mudar a asserção.
- **IT-031** (escala): 2.000 chaves com valor de 4 KB; `list` pela linha de comando emite as 2.000
  linhas em ordem, sem truncar, e `get` de uma chave do meio devolve o valor correto. Cobre US-004.EC-2
  e US-008.EC-2 em escala reduzida — ver Coverage Decisions.
- **IT-032** (crescimento): reaproveitamento de espaço — gravado valor de 4 MB, medido o tamanho,
  apagada a chave, medido de novo (o teste espera que **não** tenha encolhido, conforme US-008.EC-1);
  gravado outro valor de 4 MB em chave nova, e o tamanho final continua na ordem de um único valor, não
  de dois. Prova que o espaço liberado volta a ser usado.
- **IT-022b** *(withdrawn — consolidado em IT-022)*.
- **IT-040** (error): falha de escrita preserva o anterior — filho com
  `resource.setrlimit(RLIMIT_FSIZE, (1 MB, 1 MB))` tenta gravar um valor de 5 MB sobre uma chave que já
  vale `"antigo"`. O filho falha (código diferente de 0). Ao reabrir sem o limite, `get` devolve
  `"antigo"` íntegro e o armazenamento continua utilizável para novas gravações. Cobre a classe
  ENOSPC/E-S de US-001.EC-5 sem exigir `root` nem `tmpfs` dedicado.

> A matriz cita `IT-022` para US-010.EC-1 e `IT-040` para US-001.EC-5; a entrada `IT-022b` fica
> registrada como retirada para que o número não seja reaproveitado.

## End-to-End Tests

Arquivo: `tests/test_cli.py`. Todos executam
`subprocess.run([sys.executable, "-m", "kvstore", ...], capture_output=True)` a partir da raiz do
repositório, e conferem `stdout`, `stderr` e `returncode`.

### Jornada principal (US-001, US-002, US-003, US-004)

- **E2E-001**: Golden Path de `_dx.md`, verbatim — `set posicao 1042` → `set config '{"modo":...}'` →
  `list` (saída `config\nposicao\n`) → `get posicao` (saída `1042`, sem newline) → `del posicao` →
  `list` (saída `config\n`). Todos com código 0.
- **E2E-002**: `get inexistente` → `stdout` vazio, `stderr` exatamente
  `kvstore: chave nao encontrada: inexistente\n`, código 1.
- **E2E-003**: fidelidade de `get` — gravado `"linha\n"`, a saída de `get` é exatamente `b"linha\n"`
  (um newline, não dois); gravado `"1042"`, a saída é exatamente `b"1042"` (nenhum newline).
- **E2E-004**: `set` sobrescreve — dois `set` na mesma chave e `get` devolve o segundo valor.
- **E2E-008**: `del` — `del posicao` termina com 0; `get posicao` passa a terminar com 1; `del posicao`
  de novo termina com 0 e não imprime nada (idempotência de US-003.EC-1 e EC-2).
- **E2E-009**: `list` em diretório sem chaves → `stdout` vazio, código 0.
- **E2E-010**: `list` ordenado — gravadas fora de ordem, saída em ordem crescente, uma por linha.

### Entradas e limites (US-001, US-002, US-005)

- **E2E-005**: `set "" v` → `stderr` `kvstore: chave nao pode ser vazia\n`, código 2; `list` continua
  vazio.
- **E2E-006**: `set k ""` → código 0; `get k` → `stdout` vazio **com código 0**, distinto do código 1
  de chave ausente.
- **E2E-007**: chaves hostis pela linha de comando — `set "a/b" v`, `set "../fuga" v`,
  `set "chave com espaço" v` gravam e releem; nenhum arquivo aparece no diretório além de
  `kvstore.sqlite3*`.
- **E2E-011**: valor grande por stdin — arquivo de 10 MB alimentado por `stdin` em `set dump -`;
  código 0, e `get dump` devolve exatamente os mesmos bytes.
- **E2E-012**: `set k -` com `stdin` vazio → código 0; `get k` devolve vazio com código 0.
- **E2E-013**: `set k - extra` → `stderr`
  `kvstore: com '-' o valor vem da entrada padrao; remova o argumento\n`, código 2.
- **E2E-014**: `stdin` com `b"\xff\xfe"` em `set k -` → `stderr` com
  `kvstore: entrada padrao nao e' UTF-8 valido no byte `, código 2, nada gravado.
- **E2E-024**: valor de 5 MB lido por `get` através de pipe → `stdout` tem exatamente 5.000.000 bytes,
  sem truncamento.
- **E2E-027**: gravar o texto literal `-` — `printf -- -` como `stdin` de `set k -` grava `"-"`, e
  `get k` devolve `-`. Documenta a desambiguação de US-005.EC-1.

### Uso e erros de invocação

- **E2E-015**: `python -m kvstore` sem argumentos → `stderr`
  `kvstore: uso: python -m kvstore <diretorio> {set|get|del|list} [args]\n`, código 2.
- **E2E-016**: verbo desconhecido (`pop`) → mesma linha de uso, código 2.
- **E2E-017**: aridade errada (`set posicao`, sem valor) → `stderr`
  `kvstore: uso: python -m kvstore <diretorio> set <chave> <valor>\n`, código 2.

### Diretório e sistema de arquivos (US-009)

- **E2E-018**: diretório inexistente + `set k v` → diretório criado, código 0, `get k` devolve `v`.
- **E2E-019**: diretório inexistente + `list` → `stdout` vazio, código 0.
- **E2E-020**: caminho aponta para arquivo comum → `stderr` começa com
  `kvstore: nao foi possivel abrir ` e nomeia o caminho, código 3.
- **E2E-021**: diretório-pai sem permissão de criação (`chmod 0o500`) → código 3; nenhum diretório
  parcial criado. Pulado quando executado como `root`, que ignora a permissão.
- **E2E-022**: `get k` em diretório que nunca recebeu escrita → código **1** (chave não encontrada),
  não 3; distingue "não existe" de "não consegui ler".
- **E2E-025**: diretório existente sem permissão de escrita → código 3, e nenhum arquivo novo aparece
  dentro dele. Pulado quando executado como `root`.
- **E2E-026**: contrato de arquivos em disco — após um `set` bem-sucedido, `kvstore.sqlite3` existe no
  diretório e nenhum arquivo fora do padrão `kvstore.sqlite3*` foi criado.

### Robustez de saída

- **E2E-023**: `list` com o leitor fechando o pipe (equivalente a `| head -1`) termina sem imprimir
  `BrokenPipeError` nem traceback em `stderr`.

## Coverage Decisions

Cada invariante alterada, sua camada dona e o motivo:

- **Durabilidade por confirmação** (Safety Invariants 1–4) é dona da integração, não da unidade: só um
  processo de verdade morrendo prova o que importa. É por isso que não há fake de `sqlite3` na suíte.
- **Nível de sincronização** (Invariante 5) é dono da unidade, por asserção sobre os pragmas efetivos
  (UT-020, UT-021, UT-022). Escolha deliberada: o risco real registrado em ADR-002 é um caminho de
  código abrir conexão sem repetir `PRAGMA synchronous`, e isso é detectável por leitura de pragma,
  não por um teste de comportamento.
- **US-007.EC-2 (queda de energia) não tem teste de comportamento** e não é lacuna: não se reproduz em
  espaço de usuário sem cortar energia da máquina. O que decide o desfecho sob queda de energia é o
  valor de `synchronous`, e ele é assertado em UT-021. A ressalva sobre hardware que mente em `fsync`
  está registrada em `_spec.md` Business Rules, não prometida a mais.
- **US-007.EC-3 (terceiro apagando os arquivos auxiliares) não recebe teste**: o enunciado estabelece
  que o diretório é exclusivo do serviço, e está em Non-Goals.
- **US-008.AC-3 (README sem rotina periódica) não recebe teste automatizado**: é asserção sobre
  documentação. Conferida na revisão da tarefa 4.
- **US-004.EC-2 e US-008.EC-2 pedem 100.000 chaves; IT-031 usa 2.000.** Motivo explícito: `set` faz um
  `fsync` por gravação (ADR-002), então 100.000 inserções levariam minutos e tornariam `make test`
  inutilizável no dia a dia. 2.000 já exerce as invariantes que importam — ordenação completa, ausência
  de truncamento e leitura de uma chave sem varrer o resto. A afirmação de escala de 100× fica
  registrada como projeção do desenho (índice B-tree), não como medição.
- **US-004.EC-1 (chave com newline) é coberta só na unidade** (UT-024). A ambiguidade da saída de texto
  da linha de comando é limitação documentada em `_spec.md`, decidida e não corrigida com escaping; um
  teste E2E que a congelasse daria a impressão de que a saída é parseável, que é o oposto do registrado.
- **Modos de falha por componente**: `Store` tem UT-009, UT-010, UT-013, UT-016 e IT-040; a linha de
  comando tem E2E-005, E2E-013, E2E-014, E2E-015, E2E-016, E2E-017, E2E-020, E2E-021 e E2E-025. Nenhum
  dos dois componentes fica só com caminho feliz.
- **`tests/test_fumaca.py` continua válido** e não é substituído: cobre que o pacote importa, o que
  continua sendo verdade e permanece barato.
- **Nenhum caso novo duplica a unidade na integração ou no E2E**: a integração só existe onde há
  fronteira de processo (morte, concorrência, tamanho em disco), e o E2E só existe onde há contrato de
  `stdout`/`stderr`/código de saída.

## Case-Writing Rules (aplicadas)

- Casos nomeiam função, comando e valores reais; nenhum caso diz "verificar tratamento de erro".
- Cada caso de unidade carrega sua classe (`happy`, `error`, `boundary`, `state`); os de integração
  carregam `durability`, `concurrency` ou `growth` pela seção em que estão.
- Um comportamento observável por caso.
- Casos de unidade não usam fake algum; integração usa processos reais; E2E passa pela linha de comando
  exatamente como o usuário, com as transcrições de `_dx.md`.
- Sincronização entre processos é por pipe e por sinal. Nenhum caso usa `sleep` como condição de
  corrida — o único `sleep` admitido é o teto de segurança de IT-023, que é justamente sobre tempo.
