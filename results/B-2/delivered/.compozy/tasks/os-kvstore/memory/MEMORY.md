# Memória compartilhada: os-kvstore

## Estado atual

- `task_01` (abertura do store e pragmas) implementada e verificada. `kvstore/__init__.py`
  expõe `_connect(directory) -> sqlite3.Connection`: cria o diretório sob demanda, aplica
  `auto_vacuum=INCREMENTAL` antes do `CREATE TABLE IF NOT EXISTS kv`, e os pragmas
  `journal_mode=WAL`, `synchronous=FULL`, `busy_timeout=5000`, `journal_size_limit=64MiB`.
  Idempotente: reabrir não recria schema nem altera dados (auto_vacuum vira no-op em banco
  não-vazio, `CREATE TABLE IF NOT EXISTS` idem).

## Decisões que as próximas tarefas devem reusar

- **Não recriar a lógica de abertura.** `task_02` (operações do store) deve chamar
  `kvstore._connect(directory)` a cada operação pública (`set`/`get`/`delete`/`list_keys`),
  não abrir o sqlite3 diretamente — a política de pragmas mora só em `_connect`.
- Nome do arquivo do banco: `kvstore.sqlite3` (constante `kvstore._DB_FILENAME`).
- Tabela: `kv(key TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL)`.

- `task_02` (operações do store) implementada e verificada. `kvstore/__init__.py` agora
  expõe `set`/`get`/`delete`/`list_keys(directory, ...)`, todas chamando `_connect`
  internamente. Erros próprios: `InvalidKeyError` (chave vazia/`\n`/NUL, levantada antes
  de qualquer `_connect`) e `KeyNotFoundError` (só em `get`; `delete` de chave ausente é
  sucesso silencioso). `get`/`list_keys` checam `os.path.isfile(_db_path(directory))`
  antes de conectar, para não criar diretório/arquivo num store "vazio". `task_03` (CLI)
  deve mapear `InvalidKeyError`→exit 2 e `KeyNotFoundError`→exit 1.
- **Armadilha de `sqlite3` stdlib**: `conn.execute("PRAGMA ...")` sem `.fetchall()` (ou
  `.fetchone()`) não termina de executar o pragma — confirmado com `wal_checkpoint` e
  `incremental_vacuum`, que pareciam não fazer nada mesmo com `commit()` depois. Qualquer
  tarefa futura que rode pragmas com efeito (`wal_checkpoint`, `incremental_vacuum`,
  `optimize`, etc.) via `sqlite3` da stdlib deve sempre consumir o cursor. Detalhe em
  `memory/task_02.md`.

- `task_03` (CLI) implementada e verificada. `kvstore/__main__.py` expõe
  `main(argv=None) -> int` e `python -m kvstore <dir> set/get/del/list`. Mapeamento de
  exceção → exit code, para reuso: `KeyNotFoundError`→1, `InvalidKeyError`→2 (mesmo
  código de erro de uso do `argparse`), `(sqlite3.Error, OSError)`→3 (permissão negada,
  disco cheio, corrupção). `get` escreve em `sys.stdout.buffer` (nunca `print()`) para não
  acrescentar `\n`. `set` lê `sys.stdin.read()` inteiro quando o valor é `-`.
  `tests/test_cli.py` roda o CLI via `subprocess.run([sys.executable, "-m", "kvstore",
  ...], cwd=<repo root>)` — sem precisar setar `PYTHONPATH`, porque `python -m` resolve o
  pacote a partir do `cwd`. Detalhe em `memory/task_03.md`.

- `task_04` (testes de falha abrupta) implementada e verificada. Novo
  `tests/_sigkill_worker.py` (subprocesso auxiliar, não é módulo de teste) e
  `tests/test_falha_abrupta.py` (7 testes, 4.1–4.6). Padrão reusável: kill
  **depois de uma confirmação** sincroniza por uma linha em stdout do worker
  (nunca `sleep`); kill **durante** uma gravação usa `sleep(atraso)` como
  varredura de instantes (não como sincronização) sobre um valor grande
  (2 MiB) para dar janela real de tempo à operação. Para garantir um `-wal`
  pendente no diretório (cenário 4.6), é preciso **repetir** o kill com
  atrasos crescentes até a condição aparecer — um kill cedo demais não chega
  a abrir a conexão, um kill tarde demais cai depois do fechamento limpo
  (que já dispara checkpoint automático do SQLite). Detalhe em
  `memory/task_04.md`.

- `task_05` (concorrência e crescimento) implementada e verificada. Novo
  `tests/test_concorrencia_e_crescimento.py` (3 testes, 5.1–5.3) e
  `tests/_escritor_continuo.py` (subprocesso auxiliar que regrava uma chave
  N vezes em sequência, para testes de leitura-concorrente-com-escrita).
  Nenhuma mudança em `kvstore/__init__.py`/`__main__.py`: a seção 5 é só de
  teste, o comportamento (D3/D4 em design.md) já existia desde `task_02`.
  **Custo medido de `synchronous=FULL`: ~13–17 ms por `set`, dominado pelo
  `fsync` do commit, não pelo tamanho do valor.** Qualquer teste futuro que
  faça muitas gravações sequenciais na mesma suíte deve orçar por essa taxa
  antes de escolher a contagem — 3000 regravações de 4 KiB mediram 42 s.
  Detalhe (incluindo por que N=1000, não "dezenas de milhares", basta para
  5.3) em `memory/task_05.md`.

- `task_06` (Fechamento) implementada e verificada. `README.md` documenta os quatro
  comandos, `-` para stdin e a tabela de códigos de saída (cada exemplo colado num
  shell antes de escrever). `design.md`/Open Questions resolvido: a forma simples de
  `incremental_vacuum` (a cada remoção) basta — custo medido ~11 ms/op acima do
  `DELETE`+`commit` isolado, irrelevante para a carga do enunciado.
  **Bug real corrigido em `kvstore/__init__.py::_connect`**: `PRAGMA auto_vacuum =
  INCREMENTAL` (forma de atribuição) estava sendo reaplicado em **toda** abertura de
  conexão, inclusive leituras. Mesmo virando no-op num banco não-vazio, essa forma do
  pragma gera contenção real entre conexões concorrentes (medido: chamadas individuais
  de `get()` chegando a ~2.7 s, e o próprio `set` do escritor falhando com "database is
  locked" apesar de `busy_timeout=5000`) — é o que fazia `tests.test_concorrencia_e_
  crescimento` (5.2, de `task_05`) falhar de forma intermitente. Corrigido consultando
  o valor efetivo primeiro (`PRAGMA auto_vacuum`, forma de consulta, barata e sem
  contenção) e só emitindo a atribuição quando ainda não é `2`. `make test` caiu de
  ~27 s para ~12-13 s. **Qualquer pragma de atribuição reaplicado em toda abertura de
  `_connect` é candidato ao mesmo problema** — meça com um leitor e um escritor reais
  em loop antes de assumir que "idempotente" quer dizer "barato". Detalhe em
  `memory/task_06.md`.

## Bloqueio ambiental (vale para toda a workflow)

- O binário `openspec` (CLI) **não está instalado** nesta máquina/ambiente — não há em
  `PATH`, `npx openspec` falha (`could not determine executable to run`), `pip show
  openspec` não encontra nada. `openspec validate kvstore --strict`, citado na seção
  "Verificacao" de cada task, não pôde ser executado por nenhuma tarefa até novo aviso.
  Não tente reinstalar por conta própria sem autorização — reporte o comando teria sido
  rodado e siga com o resto da verificação (`make test`).
