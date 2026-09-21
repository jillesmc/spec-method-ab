---
status: completed
title: Camada de armazenamento durável (`Store`)
type: feature
complexity: critical
---

# Task 1: Camada de armazenamento durável (`Store`)

## Overview

Depois desta tarefa, o serviço pode importar `kvstore.Store` e gravar configuração, contadores e
posição de processamento com a garantia que hoje não existe: quando `set` retorna, o dado está
sincronizado em disco e sobrevive a `SIGKILL`, a OOM e à queda da máquina. É a tarefa que resolve o
Motivating Problem de `_spec.md` — o arquivo zerado depois do restart — e ela carrega junto a prova,
porque uma garantia de durabilidade sem teste de morte abrupta é uma afirmação, não um resultado.

Complexidade `critical` pelo risco, não pelo tamanho: todo o contrato de sobrevivência do dado mora
aqui, e a forma de falhar é silenciosa (uma conexão aberta sem `PRAGMA synchronous=FULL` continua
funcionando e perde a garantia sem nenhum sintoma).

## Shippable Outcome

- **Outcome**: `from kvstore import Store` funciona; `Store(diretorio).set(chave, valor)` grava de
  forma durável e atômica, e `get`/`delete`/`keys` operam sobre o mesmo diretório. Matar o processo a
  qualquer instante nunca deixa o armazenamento vazio, ilegível, nem com valor parcial.
- **Verify in this task**: `tests/test_store.py` (`UT-001`–`UT-024`) e a parte de durabilidade de
  `tests/test_durabilidade.py` (`IT-010`–`IT-014`, `IT-040`). A prova de entrada real é `IT-010`: um
  processo filho grava e chama `os._exit(0)` — sem `close()`, sem `atexit`, sem flush — e o pai relê o
  valor.
- **Integration verification**: `none`. Concorrência entre processos e crescimento em disco ficam na
  task_03; nada aqui depende delas para ser aceito.

## Requirements

- **Só biblioteca padrão.** Nenhuma dependência nova, em execução ou em teste.
- **Compatível com Python 3.11**, conforme o README. Consequência concreta: `isolation_level=None` na
  conexão, **nunca** `sqlite3.Connection.autocommit`, que só existe a partir do 3.12.
- **Um único ponto de abertura de conexão** no pacote. É a fronteira que sustenta a invariante 5 de
  `_spec.md` § Safety Invariants. Um segundo caminho que esqueça `PRAGMA synchronous = FULL` derruba a
  garantia sem sintoma — é o risco nomeado em `adrs/adr-002.md`.
- **`journal_mode = WAL`, `synchronous = FULL`, `busy_timeout = 5000`** reafirmados a **cada** conexão.
  `journal_mode` persiste no arquivo; os outros dois **não persistem** e precisam ser reexecutados.
- **`kvstore/__init__.py` não escreve em `stdout`/`stderr` e não chama `sys.exit`.** Ele levanta
  exceção; quem traduz para o usuário é a task_02.
- **Sem hierarquia de exceção própria**: `ValueError` para chave vazia, `TypeError` para chave que não
  é `str`, `sqlite3.Error` para falha de armazenamento. Decidido em `_spec.md` § Key Decisions.
- **Uma instrução por escrita.** `set` usa `INSERT ... ON CONFLICT ... DO UPDATE`, para que a
  atomicidade venha da transação implícita e não de código de coordenação.
- **`keys()` ordena em SQL** (`ORDER BY chave`), não em Python.
- Contratos compartilhados que **não** devem ser copiados para cá: a assinatura pública está congelada
  em [`_dx.md`](_dx.md) § SDK e em [`_spec.md`](_spec.md) § Core Interfaces. Implemente contra elas.

## Subtasks

- [x] 1.1 Implementar a abertura de conexão em `kvstore/__init__.py`: criar o diretório
      (`os.makedirs(..., exist_ok=True)`), conectar com `isolation_level=None`, aplicar os três pragmas
      e criar a tabela `kv` com `CREATE TABLE IF NOT EXISTS`.
- [x] 1.2 Implementar `Store.set`, `Store.get`, `Store.delete`, `Store.keys`, `Store.close` e o
      protocolo de gerenciador de contexto, conforme as assinaturas congeladas.
- [x] 1.3 Implementar a validação de chave na fronteira Python (vazia → `ValueError`, não-`str` →
      `TypeError`), antes de qualquer SQL.
- [x] 1.4 Escrever `tests/test_store.py` com `UT-001`–`UT-019` (operações e regras).
- [x] 1.5 Escrever `UT-020`–`UT-024` no mesmo arquivo: os três casos de pragma efetivo, o de escala de
      chaves e o de chave com newline.
- [x] 1.6 Escrever `tests/test_durabilidade.py` com `IT-010`–`IT-014`, usando pipe e sinal para
      sincronizar entre processos — nunca `sleep` como condição de corrida.
- [x] 1.7 Acrescentar `IT-040` ao mesmo arquivo, usando `resource.setrlimit(RLIMIT_FSIZE)` no filho
      para produzir falha de escrita sem precisar de `root` nem de `tmpfs` dedicado.
- [x] 1.8 Conferir que `make test` passa inteiro, incluindo o `test_fumaca.py` existente.

## Implementation Details

Criar `kvstore/__init__.py` (hoje vazio) com a classe `Store` e a função privada de conexão. O padrão
de código — pragmas, SQL de `set`, esquema da tabela — está em `_spec.md` § Implementation Design →
Core Interfaces e Data Models; implemente a partir de lá em vez de reinventar.

Dois pontos onde é fácil errar e o erro não aparece:

- A tabela é **com rowid** (o padrão). Não usar `WITHOUT ROWID`: ela guardaria a linha inteira dentro
  da árvore B do índice, e os valores aqui podem ser grandes (`adrs/adr-001.md`).
- `PRAGMA journal_mode = WAL` não pode rodar dentro de transação. Com `isolation_level=None` a conexão
  está em autocommit, então executá-lo logo após conectar funciona — em qualquer outra configuração,
  não.

### Relevant Files

- `kvstore/__init__.py` — arquivo vazio hoje; recebe toda a camada de armazenamento. É o ponto único
  de abertura de conexão de que dependem as invariantes 1, 4 e 5.
- `tests/test_store.py` — novo; casos de unidade.
- `tests/test_durabilidade.py` — novo; casos de morte abrupta e de falha de escrita.
- `tests/test_fumaca.py` — estabelece o estilo a seguir (`unittest.TestCase`, nomes em português);
  permanece inalterado.
- `tests/__init__.py` — já existe e torna `tests` um pacote; o `-t .` do `make test` depende disso
  para que `import kvstore` resolva a partir da raiz.
- `Makefile:2-3` — o alvo `test` descobre arquivos novos em `tests/` sozinho; nada a alterar nele.

### Dependent Files

- `kvstore/__main__.py` (task_02) — consumidor único desta camada; toda assinatura criada aqui é
  contrato para ele. A fronteira proíbe que ele importe `sqlite3`.

### Related ADRs

- [ADR-001: `sqlite3` da biblioteca padrão como motor de armazenamento](adrs/adr-001.md) — decide o
  motor, o esquema e a tabela com rowid; as Implementation Notes dele são o guia direto desta tarefa.
- [ADR-002: WAL com `synchronous=FULL` como nível de durabilidade](adrs/adr-002.md) — decide os três
  pragmas e registra o risco do pragma por conexão que `UT-020`–`UT-022` existem para pegar.

## Deliverables

- `kvstore/__init__.py` com a classe `Store` completa e um único caminho de abertura de conexão.
- `tests/test_store.py` com os 24 casos de unidade.
- `tests/test_durabilidade.py` com os seis casos de durabilidade e falha de escrita.
- `make test` verde.

## Tests

Casos atribuídos de [`_tests.md`](_tests.md) — leia a definição de cada um antes de escrever.

- [x] `UT-001`, `UT-002`, `UT-003`, `UT-004`, `UT-005`, `UT-006`, `UT-007`, `UT-008` — round-trip,
      sobrescrita, ausência (`None`), remoção (`True`/`False`), ordenação de `keys`, `keys` vazio e
      valor vazio distinto de ausente.
- [x] `UT-009`, `UT-010`, `UT-013`, `UT-016` — modos de falha: chave vazia (`ValueError`), chave
      não-`str` (`TypeError`), uso após `close()` e caminho que é arquivo comum.
- [x] `UT-011`, `UT-012`, `UT-014`, `UT-015`, `UT-017`, `UT-018`, `UT-019` — chaves hostis (`/`, `..`,
      espaço, acento, newline), valor de 5 MB, gerenciador de contexto, criação implícita do
      diretório, ausência de vazamento de descritor em 5.000 escritas, newline final preservado e
      remoção repetida.
- [x] `UT-020`, `UT-021`, `UT-022` — pragmas efetivos (`wal`, `2`, `5000`) lidos de um `Store` aberto.
      São a defesa contra o risco de `adrs/adr-002.md` e a única cobertura possível de `US-007.EC-2`.
- [x] `UT-023`, `UT-024` — escala de 2.000 chaves com ordenação e integridade, e chave com newline
      íntegra na API.
- [x] `IT-010`, `IT-011` — morte abrupta após confirmação: `os._exit(0)` sem encerramento limpo, e
      `SIGKILL` externo sincronizado por pipe.
- [x] `IT-012` — `SIGKILL` **durante** a escrita de um valor de 8 MB: aceita o valor antigo inteiro ou
      o novo inteiro, falha em qualquer prefixo, mistura ou `None`, e confere a chave sentinela.
- [x] `IT-013` — 500 chaves confirmadas e morte na 501ª: nenhuma das 500 pode sumir. É o sintoma exato
      relatado no enunciado.
- [x] `IT-014` — a remoção tem a mesma durabilidade da gravação.
- [x] `IT-040` — falha de escrita por `RLIMIT_FSIZE` preserva o valor anterior íntegro e deixa o
      armazenamento utilizável.

## Success Criteria

- Um processo que grava e é morto com `SIGKILL` em **qualquer** instante nunca produz armazenamento
  vazio, ilegível ou com valor parcial — verificado por `IT-012` e `IT-013`, não afirmado.
- Os três pragmas são verificáveis em tempo de execução a partir de um `Store` aberto, e existe um
  único lugar no pacote que os aplica.
- `kvstore/__init__.py` não contém nenhuma escrita em `stdout`/`stderr` nem chamada a `sys.exit`, e
  não importa nada fora da biblioteca padrão.
- Nenhum teste deixa arquivo de banco na árvore do repositório (todos usam diretório temporário) e
  nenhum usa `sleep` como condição de corrida.
- `make test` passa inteiro.
