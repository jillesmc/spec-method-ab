# Design

## Context

Motivação em proposal.md — "Why". Estado atual: `kvstore/__init__.py` está vazio, `tests/test_fumaca.py`
só verifica que o pacote importa, e `make test` roda `python3 -m unittest discover -s tests -t .`.

Restrições que moldam a escolha:

- **Só stdlib**, Python 3.11+ (a máquina de verificação tem 3.14.7 com SQLite 3.53.1).
- **Um processo por operação**: cada comando do CLI é um processo novo. Custo de abertura e de leitura
  é pago em toda operação, então "reconstruir o estado inteiro na abertura" é caro à medida que o
  histórico cresce.
- **O volume cresce e ninguém limpa** — a recuperação de espaço tem de ser interna e automática.
- **Linux, sistema de arquivos local**, diretório de uso exclusivo do pacote.
- O contrato observável está nas specs (`kvstore/storage`, `kvstore/cli`); este documento escolhe o
  mecanismo que o cumpre.

## Goals / Non-Goals

**Goals:**

- Cumprir o contrato de durabilidade com o **menor volume de código proprietário possível**: cada linha
  de código de recuperação de falha que escrevemos é uma linha que temos de acertar sozinhos, e ela é
  exercitada exatamente na hora em que ninguém está olhando.
- Custo de `get` independente do total histórico de gravações.
- Falha de gravação nunca se apresenta como sucesso.

**Non-Goals:**

- Sistema de arquivos em rede (NFS, SMB): o travamento entre processos usado aqui não é confiável lá.
- Windows.
- Valores acima de 1 GB.
- Formato em disco legível a olho nu. O acesso é pelo CLI.

## Decisions

### D1 — O armazenamento é `sqlite3` da stdlib, não um log append-only escrito à mão

Um arquivo `kvstore.sqlite3` dentro do diretório, com uma tabela
`kv(key TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL)`.

O desenho "óbvio" para este enunciado é um log append-only com checksum por registro, descarte da cauda
parcial na leitura, compactação por arquivo temporário + `rename`, e `flock` entre processos. Ele foi a
primeira escolha aqui e foi descartado: são quatro subsistemas de segurança de dados escritos por nós,
e cada um só é exercitado no caminho de falha. O `sqlite3` entrega os quatro — atomicidade por
transação, recuperação automática no `open`, travamento entre processos e reuso de espaço — em código C
testado contra escrita rasgada, corte de energia e setor parcial por duas décadas. Aqui, "não seja
preguiçoso com perda de dados" e "use a stdlib antes de escrever código" apontam para o mesmo lado.

Ganho secundário que importa ao enunciado: `get` é busca por índice, O(log n), enquanto o log exigiria
reler o histórico inteiro **a cada invocação do CLI** — e o enunciado diz explicitamente que o número
de gravações cresce sem parar.

Alternativas consideradas:

- **JSON reescrito com temporário + `fsync` + `rename`.** Corrige a falha atual e é atômico, mas cada
  gravação custa o estado inteiro (CPU, disco e memória) e o enunciado promete crescimento contínuo.
  Rejeitado por escala, não por segurança.
- **Log append-only + compactação + `flock`.** Ver acima. Rejeitado por volume de código de falha
  próprio, e por custo de leitura proporcional ao histórico.
- **`dbm` / `shelve`.** Stdlib, mas o backend disponível varia por máquina e o `dbm.dumb` é
  documentadamente não resistente a interrupção. Rejeitado: o backend efetivo não seria uma decisão
  nossa, e a promessa central depende dele.
- **Um arquivo por chave (`write` temporário + `rename`).** Durável e simples por chave, mas o número
  de inodes cresce com o número de chaves, `list` vira varredura de diretório, e ainda precisaríamos do
  `fsync` de diretório a cada criação. Rejeitado.

### D2 — `journal_mode=WAL` com `synchronous=FULL`, explicitamente

Este par **é** o contrato de durabilidade: em modo WAL, `synchronous=FULL` sincroniza o WAL a cada
`COMMIT`, então uma gravação confirmada sobreviveu ao disco. O valor `NORMAL`, que é o que a maioria
das receitas de WAL na internet recomenda por desempenho, **não** sincroniza por commit — adotá-lo por
inércia apagaria em silêncio a única coisa que esta mudança existe para garantir.

Consequência prática: `set`/`del` só retornam depois do `COMMIT`. Nenhum `fsync` manual nosso, nenhum
`fsync` de diretório manual — o SQLite faz os dois nos pontos em que são necessários.

Por serem pragmas, e por serem invisíveis quando errados, os dois valores efetivos são verificados em
tempo de execução por teste (ver tasks.md), não apenas escritos no código.

### D3 — Recuperação de espaço por `auto_vacuum=INCREMENTAL`

`PRAGMA auto_vacuum=2` (INCREMENTAL) definido **no banco vazio, antes da criação da tabela** — depois
disso ele só muda com um `VACUUM` completo; verificado nesta máquina. Páginas liberadas por remoção ou
sobrescrita já são reusadas pelo SQLite, o que sozinho mantém o arquivo proporcional ao pico de estado
vivo; o `PRAGMA incremental_vacuum` executado após remoções devolve as páginas ao sistema de arquivos,
o que faz o arquivo encolher de verdade depois de uma limpeza em massa. `PRAGMA journal_size_limit`
impede que o WAL fique grande permanentemente depois de um pico de escrita.

### D4 — Concorrência é do SQLite, com `busy_timeout`

Sem `flock` nosso. Escritores serializam pelo travamento do próprio SQLite; leitores em WAL não são
bloqueados por escritores. `PRAGMA busy_timeout` (alguns segundos) transforma contenção momentânea
entre invocações do CLI em espera, em vez de erro imediato — que seria uma falha visível ao serviço
por um motivo que não é dele.

Teto conhecido: escrita é serializada globalmente no diretório. Para a carga descrita — configuração,
contadores, posição de processamento — isso é folgado.

### D5 — Valores como `TEXT`, chaves validadas na entrada

Chave e valor são `str`. O risco conhecido de truncamento em `NUL` dentro de `TEXT` foi verificado
nesta máquina e **não** se reproduz (ida e volta de `"x\x00y"` preservada); ainda assim um teste fixa
esse comportamento, para que uma regressão de versão apareça como teste vermelho e não como dado
perdido em produção.

Chaves com `\n`, com `NUL`, ou vazias são recusadas na fronteira de entrada com erro de uso: `list`
imprime uma chave por linha, e uma chave com quebra de linha tornaria a saída ambígua para quem a
consome. Valores não sofrem restrição.

### D6 — Camadas: `kvstore/__init__.py` é a API, `kvstore/__main__.py` é só tradução

A API (`set`/`get`/`delete`/`list_keys`, recebendo o diretório) contém a lógica e levanta exceções
próprias. O `__main__` faz apenas: `argparse` → chamada → escrita em stdout/stderr → código de saída.
Nenhuma regra de negócio no `__main__`, para que os testes exercitem a API diretamente e os testes de
crash exercitem o CLI como o serviço o usa.

O `argparse` já sai com código 2 em erro de uso, que é exatamente o código que a spec do CLI exige —
nenhum tratamento extra é necessário para esse caso.

### D7 — `get` escreve bytes crus em `sys.stdout.buffer`

Para cumprir "sem newline extra e byte a byte", a escrita é do UTF-8 do valor em `sys.stdout.buffer`,
não `print()`. `print()` acrescentaria `\n` e passaria pela reconfiguração de encoding do terminal.

## Risks / Trade-offs

- **Pragma errado apaga a garantia em silêncio** (o modo de falha mais perigoso deste desenho) →
  teste que lê `pragma synchronous` e `pragma journal_mode` efetivos em tempo de execução, **mais** o
  teste de matar o processo com `SIGKILL` logo após a confirmação, que falha se a garantia não existir
  de fato.
- **`auto_vacuum` só pode ser definido antes da primeira tabela** → o pragma fica no caminho de criação,
  antes do schema, e um teste afirma `pragma auto_vacuum == 2` num store recém-criado.
- **Arquivo binário não é mais inspecionável com `cat`**, ao contrário do JSON atual → `list` e `get`
  cobrem a inspeção operacional; o `sqlite3(1)` cobre a forense.
- **WAL exige memória compartilhada (`-shm`) e travamento POSIX**, o que quebra em NFS → registrado como
  não-objetivo; o diretório é local por premissa do enunciado.
- **Escrita serializada por diretório** → aceitável para a carga descrita; se um dia deixar de ser, o
  caminho é agrupar várias gravações numa transação só, não trocar o armazenamento.
- **`incremental_vacuum` custa E/S na operação que o dispara** → ver Open Questions.

## Migration Plan

Não há formato anterior gravado por este pacote, então não há migração de dados: a mudança é a primeira
implementação. O serviço que hoje guarda um JSON próprio continua com ele; adotar o `kvstore` e
transportar aquele conteúdo é trabalho do serviço, fora desta mudança (registrado em proposal.md —
Impact).

Reversão: apagar o diretório do store. Nenhum estado fora dele é tocado.

## Open Questions

- **Cadência do `incremental_vacuum`**: resolvida — a forma simples (a cada remoção) basta. Medido na
  tarefa 2.6 nesta máquina: 50 remoções de valores de 200 KiB custam **~26 ms/op** com
  `wal_checkpoint(TRUNCATE)` + `incremental_vacuum` acoplados, contra **~15 ms/op** de um `DELETE` +
  `commit` isolado (o próprio `fsync` de `synchronous=FULL`, já pago por toda escrita confirmada, ver
  D2) — o vacuum acrescenta cerca de **11 ms/op**, e sem ele o diretório fica no tamanho cheio (~10 MB
  nesse cenário, contra <10% depois do vacuum). Para a carga que motiva esta mudança — configuração,
  contadores, posição de processamento, não remoção em massa — esse custo por operação é irrelevante, e
  não há motivo para complicar com um limite de páginas livres antes de medir necessidade real.
