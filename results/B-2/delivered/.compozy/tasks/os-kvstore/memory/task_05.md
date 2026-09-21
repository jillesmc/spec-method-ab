# task_05 — Concorrência e crescimento

## O que foi feito

Novo `tests/test_concorrencia_e_crescimento.py` (3 testes, 5.1–5.3) e um novo
auxiliar `tests/_escritor_continuo.py` (subprocesso, não é módulo de teste).
Nenhuma mudança em `kvstore/__init__.py` ou `kvstore/__main__.py`: a seção 5 é
só de teste, o comportamento já existia (D4/D3 em design.md).

- **5.1** — `N=10` processos reais (`subprocess.Popen`, todos disparados antes
  de qualquer `communicate`) gravando chaves diferentes no mesmo diretório;
  confere `returncode == 0` para todos (nenhum erro de contenção — o
  `busy_timeout` de 5s absorve a serialização) e que todas as chaves ficam
  legíveis com os valores certos.
- **5.2** — subprocesso auxiliar `_escritor_continuo` regrava a mesma chave
  N=300 vezes em sequência (cada `set` confirmado antes do próximo); o
  processo de teste, em paralelo, faz um laço apertado de `get`/`list_keys`
  diretos (sem subprocesso) enquanto `escritor.poll() is None`. Único erro
  aceito no laço é `KeyNotFoundError` (só pode acontecer antes da primeira
  gravação); qualquer outra exceção teria estourado o teste. `list_keys` só
  pode devolver `[]` ou `["k"]` a qualquer instante.
- **5.3** — regravar a mesma chave 1000 vezes com valor de 512 bytes; o
  diretório final fica achatado em ~16 KiB independente de N (medido de
  N=100 a N=1000 antes de escrever o teste — ver "Armadilha" abaixo).

## Armadilha medida: `synchronous=FULL` custa ~13–17 ms por `set`, não por byte

Cada `kvstore.set` faz um `fsync` de verdade no commit (é o próprio contrato
de durabilidade da mudança, D2 em design.md). Medido nesta máquina (disco
real em `/tmp`, ext4, não tmpfs): **~13–17 ms por chamada, quase todo do
fsync**, então o tempo escala com o número de `set`s, não com o tamanho do
valor. 3000 regravações de um valor de 4 KiB levaram **42 s**. A tarefa 5.3
pede "milhares" de regravações mas também manda "manter a contagem baixa o
bastante para o teste rodar em segundos" — as duas frases colidem com esse
custo medido. Resolvido com N=1000 (~13–17 s sozinho): é "milhares" no
sentido literal mais fraco (mil), e a evidência (tamanho do diretório já
achatado em 16 KiB desde N=100) mostra que o comportamento sob teste não
muda com N maior — o SQLite já reusa a página da linha em cada `UPDATE` de
mesmo tamanho, então N maior só dá mais "tentativas" de expor um vazamento
que não existe. Qualquer tarefa futura que precise de mais regravações
sequenciais nesta suíte deve orçar por essa taxa (~15 ms/op) antes de
escolher N, não estimar por "parece rápido".

## Decisões que próximas tarefas devem reusar

- Auxiliar de subprocesso para escrita contínua (não kill, ao contrário de
  `_sigkill_worker.py`): `tests/_escritor_continuo.py`, uso
  `python3 -m tests._escritor_continuo <dir> <chave> <n> <prefixo>`. Grava
  `<chave>` com `f"{prefixo}-{i}"` para `i` em `range(n)`, sequencialmente,
  cada `set` confirmado antes do próximo — dá ao processo pai uma janela real
  de escritas em andamento.
- Padrão para "leitura concorrente com escrita entre processos distintos":
  iniciar o escritor com `Popen` (não bloqueante) e fazer o laço de leitura
  no processo de teste enquanto `escritor.poll() is None` — sem `sleep`, sem
  threads, a concorrência real vem de serem dois processos de SO distintos
  contra o mesmo diretório sqlite3.
- `_dir_size` (soma de `os.path.getsize` via `os.walk`) foi redefinida aqui
  igual à de `tests/test_operacoes.py` (é privada por arquivo, sem import
  cruzado entre módulos de teste no repo — só `_sigkill_worker` é importado,
  e é um subprocesso, não um helper).

## Verificação

- `python3 -m unittest tests.test_concorrencia_e_crescimento -v` — 3/3 ok,
  rodado duas vezes (17 s e 31 s, variação vem do fsync sob carga de disco,
  não de flakiness lógica).
- `make test` — suíte completa, 40/40 ok (~31 s; antes desta tarefa eram 37
  testes em ~9 s — o aumento é majoritariamente os 1000 `fsync`s da 5.3).
- `openspec validate kvstore --strict`: **não executado** — `openspec` CLI
  segue ausente desta máquina (mesmo bloqueio de `MEMORY.md`; reconfirmado
  com `which`, `npx openspec --version` e `pip show openspec`, todos
  falham).
