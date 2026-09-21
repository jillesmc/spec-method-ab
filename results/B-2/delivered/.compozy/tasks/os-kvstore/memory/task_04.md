# Memória: task_04 — Testes de falha abrupta (o núcleo da mudança)

## Status

Implementada e verificada. `status: completed` em `task_04.md`.

## O que foi feito

- `tests/_sigkill_worker.py` (novo, não é módulo de teste — não começa com
  `test`, então `unittest discover` não o pega): subprocesso que roda **uma**
  operação (`set` com valor lido de stdin, ou `del`) contra `kvstore` e, assim
  que ela retorna (confirmada), escreve a linha `confirmado` em stdout e trava
  em `signal.pause()` esperando o pai mandar `SIGKILL`. Invocado como
  `python3 -m tests._sigkill_worker <dir> set|del <chave>` com `cwd` na raiz do
  repo — mesmo truque de resolução de pacote do `test_cli.py` (`-m` soma o
  `cwd` a `sys.path`), sem precisar setar `PYTHONPATH`.
- `tests/test_falha_abrupta.py` (novo, 7 testes cobrindo 4.1–4.6):
  - **Sincronização sem `sleep` (4.1)**: `_gravar_e_matar_apos_confirmacao` /
    `_remover_e_matar_apos_confirmacao` escrevem no stdin do worker, fecham,
    e fazem `proc.stdout.readline()` **bloqueante** até a linha `confirmado`
    aparecer — só então mandam `SIGKILL`. Isso garante que o kill nunca
    acontece antes da confirmação, sem apostar em um valor de `sleep`.
  - **Kill "durante" a gravação (4.4/4.5/4.6)**: não há como sincronizar com
    um evento que, por definição, ainda não aconteceu — aqui `sleep(atraso)`
    é uma varredura de instantes, não uma sincronização, e é o padrão correto
    para esse caso (distinto de 4.1). `_matar_durante_gravacao` escreve um
    valor grande (`_VALOR_GRANDE`, 2 MiB) no stdin do worker e mata depois de
    `atraso` segundos, sem esperar confirmação.
  - 4.4 varre 8 atrasos (0 a 20 ms) sobre uma chave com valor prévio, exigindo
    que a leitura seguinte seja **exatamente** o valor antigo ou o novo —
    nunca outra coisa.
  - 4.5 usa exatamente 100 chaves confirmadas (número literal do cenário em
    `design.md`/`storage/spec.md`), mata durante a gravação de uma chave nova,
    e confere as 100 anteriores por `kvstore.get` (rápido) mais uma checagem
    via `list` num processo novo (CLI).
  - 4.6 usa `_matar_ate_deixar_wal_pendente`: repete o kill com atrasos
    crescentes (fator 1.7×, até 10 tentativas) até o diretório ficar com
    `kvstore.sqlite3-wal` em disco — só killar não basta, porque um kill cedo
    demais nem chega a abrir a conexão, e um kill tarde demais cai depois do
    fechamento limpo (que dispara checkpoint automático do SQLite e apaga o
    `-wal`). Sem essa repetição o teste ficaria dependente de sorte de
    timing. Depois disso, roda `list` via CLI sem tocar em nenhum arquivo
    antes, e exige exit 0.
  - Todos os `Popen` fecham `stdout`/`stderr` explicitamente no fim (helper
    `_matar_e_fechar`) — sem isso, `unittest -W error::ResourceWarning`
    reclama de `ResourceWarning: unclosed file` (pipes de `stderr`/`stdout`
    nunca lidos até o fim).

## Decisões que a próxima tarefa (concorrência e crescimento) deve conhecer

- O padrão `python3 -m tests._sigkill_worker ...` com `cwd` na raiz do repo é
  reusável para qualquer subprocesso auxiliar futuro que precise importar
  `kvstore` e/ou `tests` como pacotes — `tests/__init__.py` já existe, então
  `tests` é um pacote de verdade.
- `_VALOR_GRANDE = "n" * 2 MiB` é grande o bastante para o `set` demorar um
  tempo mensurável (várias páginas de WAL) sem deixar os testes lentos: os 37
  testes da suíte inteira (30 anteriores + 7 novos) rodam em ~9s.
- Testes de timing (4.4/4.6) são inerentemente não-determinísticos quanto a
  **onde exatamente** o kill cai dentro da gravação — isso é uma limitação
  conhecida de testar crash-consistency sem instrumentação de I/O (tipo
  ALICE/CrashMonkey). A varredura de instantes (4.4) e a repetição até
  condição (4.6) são a forma prática de cobrir isso com `unittest` puro; a
  asserção em si (nunca lixo / sempre `-wal` antes de checar) continua válida
  em qualquer máquina, só a probabilidade de acertar o instante exato muda.
  Rodei a suíte 3× seguidas sem falha para checar estabilidade.

## Verificação executada

- `make test` (`python3 -m unittest discover -s tests -t . -v`): 37 testes,
  todos OK (30 anteriores + 7 novos de `test_falha_abrupta.py`).
- `python3 -W error::ResourceWarning -m unittest discover -s tests -t .`: OK,
  sem warnings de arquivo não fechado.
- Suíte completa rodada 3× seguidas para checar flakiness dos testes de
  timing: 3/3 OK.
- `openspec validate kvstore --strict`: **não executável neste ambiente**
  (mesmo bloqueio já registrado em `MEMORY.md` e reconfirmado por
  `task_03`/`command -v openspec` vazio). Comando que seria rodado:
  `openspec validate kvstore --strict`.

## Sem pendências de escopo

Concorrência e crescimento (task_05) e fechamento/README (task_06) continuam
fora do escopo desta tarefa. Não toquei nas seções 2/3 de `tasks.md`
(operações e CLI), nem em `kvstore/__init__.py`/`__main__.py`.
