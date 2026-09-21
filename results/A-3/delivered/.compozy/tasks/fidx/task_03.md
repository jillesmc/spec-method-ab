---
status: completed
title: "Operacao por cron: atomicidade, concorrencia e superficie de erro"
type: feature
complexity: high
---

# Task 3: Operacao por cron: atomicidade, concorrencia e superficie de erro

## Overview

Esta task torna o `index` seguro para rodar sozinho, sem ninguem olhando: uma rodada interrompida
deixa o indice no estado da ultima rodada completa, duas rodadas atropeladas nao escrevem juntas
(a segunda sai com exit 3), arquivos ilegiveis ou com bytes indecifraveis nao derrubam a varredura, e
todo erro tem mensagem acionavel com exit code distinto de "nao achei". Fecha tambem o README com o
contrato publicado.

## Shippable Outcome

- Outcome: a entrada de crontab de [`_dx.md`](_dx.md) pode ficar ligada sem supervisao — interrupcao,
  concorrencia, arquivo sem permissao e dump binario produzem resultado deterministico e documentado,
  nunca indice corrompido.
- Verify in this task: `make test` com UT-030 a UT-033, IT-006 a IT-009 e E2E-007 a E2E-009; IT-006 e
  IT-007 sao os portoes dos Safety Invariants 1 a 4.
- Integration verification: none — esta e a ultima entrega da sequencia.

## Requirements

- **Tudo ou nada** (Safety Invariants 1 e 2): a rodada inteira em uma transacao, `COMMIT` so depois
  do ultimo arquivo. Excecao no meio = `ROLLBACK`; o indice segue respondendo o estado anterior.
- **Um escritor por vez** (Invariant 4): `sqlite3.connect(..., timeout=BUSY_TIMEOUT_S)` com 30 s;
  esgotado o timeout, o `sqlite3.OperationalError` de lock vira `IndexBusy` → exit 3 com a mensagem
  de `_dx.md`, sem nada gravado. O timeout tem de ser injetavel no teste (parametro ou constante de
  modulo), para IT-007 nao esperar 30 s.
- **Leitura durante escrita** (Invariant 3): `PRAGMA journal_mode=WAL` garantido na abertura (e nos
  indices ja criados pela task_01/02), e `search` abrindo somente leitura sem esperar o escritor.
- Arquivo ilegivel ou que sumiu entre a varredura e a leitura: pulado, aviso `fidx: aviso: pulado
  <caminho>: <motivo>` em `stderr`, rodada continua e termina com exit 0 (Business Rule 7). O aviso
  nasce em `core` como dado (lista de pulados ou callback) e e impresso por `__main__` — `core` nao
  imprime.
- Bytes que nao decodificam: `errors="ignore"` na decodificacao; o digest continua sendo dos bytes
  crus. Arquivo vazio e valido e conta no total.
- Pasta sem permissao de escrita: erro `fidx: nao foi possivel criar o indice: ...` com exit 2, sem
  deixar arquivo parcial.
- Superficie de erro completa conforme a tabela de [`_dx.md`](_dx.md) § Errors — mensagem, destino
  (`stderr`) e exit code de cada condicao. `stdout` continua carregando so caminhos e resumo.
- README atualizado com: os dois comandos, o formato do resumo, a tabela de exit codes, a regra de
  **token inteiro** (`search log` nao acha `logs` — diferenca deliberada em relacao ao `grep`), onde
  mora o indice e que apagar o indice e seguro.
- Nenhuma regressao de contrato: as transcricoes de `_dx.md` cobertas por E2E-001 a E2E-006 seguem
  identicas.

## Subtasks

- [x] 3.1 Garantir a transacao unica e o `ROLLBACK` em excecao; cobrir tambem a rodada inicial
      (indice recem-criado interrompido no meio).
- [x] 3.2 `BUSY_TIMEOUT_S` injetavel, traducao de lock em `IndexBusy` e exit 3 em `__main__`.
- [x] 3.3 WAL garantido na abertura, inclusive para indice criado antes desta task; `search` em modo
      somente leitura que nao espera o escritor.
- [x] 3.4 Pular arquivo ilegivel/sumido com aviso; decodificacao com `errors="ignore"`.
- [x] 3.5 Fechar a superficie de erro de `__main__` contra a tabela de `_dx.md` (linha de uso,
      termo sem token, pasta so-leitura).
- [x] 3.6 Atualizar `README.md`.
- [x] 3.7 `tests/test_operacao.py` com UT-030 a UT-033 e IT-006 a IT-009; E2E-007 a E2E-009 em
      `tests/test_cli.py`.

## Implementation Details

- IT-006/IT-009 injetam a falha sem `mock` de framework: um `iter_files` que levanta excecao apos o
  primeiro item (monkeypatch simples no modulo) ja exercita o `ROLLBACK`.
- IT-007/IT-008 nao precisam de segundo processo: uma segunda `sqlite3.connect` executando
  `BEGIN IMMEDIATE` segura a escrita; `index_dir` com timeout curto tem de levantar `IndexBusy`, e
  `search` tem de responder na hora.
- UT-032 e E2E-009 dependem de permissao de arquivo: `skipTest` quando `os.geteuid() == 0`, porque
  root ignora o bit de permissao e o caso viraria falso-negativo.
- Cuidado para nao esconder erro real: capture apenas `OSError` ao redor da leitura de **um**
  arquivo; excecao de SQLite e de programacao tem de continuar subindo e derrubando a rodada (e
  disparando o `ROLLBACK`).

### Relevant Files

- `fidx/core.py` — **modificar**: transacao, `BUSY_TIMEOUT_S`/`IndexBusy`, WAL, leitura tolerante,
  coleta dos avisos.
- `fidx/__main__.py` — **modificar**: exit 3, impressao dos avisos em `stderr`, tabela de erros
  completa.
- `tests/test_operacao.py` — **criar**: UT-030 a UT-033 e IT-006 a IT-009.
- `tests/test_cli.py` — **modificar**: acrescentar E2E-007, E2E-008 e E2E-009.
- `README.md:1-8` — **modificar**: comandos, exit codes, regra de token inteiro, local do indice.

### Dependent Files

- `.compozy/tasks/fidx/_dx.md` § Errors — a tabela que esta task tem de reproduzir literalmente.
- `.compozy/tasks/fidx/_spec.md` § Safety Invariants — os seis invariantes que os IT desta task
  verificam.
- `tests/test_fumaca.py:1-14` — continua verde, sem alteracao.

### Related ADRs

- [ADR-002: SQLite com indice invertido proprio](adrs/adr-002.md) — a escolha de armazenamento que
  entrega transacao, lock entre processos e WAL sem codigo proprio de concorrencia.
- [ADR-001: Hash de conteudo como unico sinal de mudanca](adrs/adr-001.md) — por que o digest e dos
  bytes crus, antes da decodificacao tolerante introduzida aqui.

## Deliverables

- Rodada atomica com `ROLLBACK` comprovado por teste de interrupcao.
- Exit 3 deterministico para rodada concorrente, com timeout injetavel.
- Busca que responde durante a rodada, com a foto anterior.
- Varredura tolerante a arquivo ilegivel, sumido, vazio ou binario.
- Tabela de erros de `_dx.md` implementada por inteiro.
- `README.md` com o contrato publicado.

## Tests

Casos de [`_tests.md`](_tests.md) — leia a definicao de cada um antes de escrever.

- [x] UT-030, UT-031 — bytes indecifraveis e arquivo vazio.
- [x] UT-032, UT-033 — arquivo sem permissao e arquivo que some no meio da rodada (ambos com aviso e
      rodada terminando bem).
- [x] IT-006, IT-009 — interrupcao com indice anterior e interrupcao na rodada inicial.
- [x] IT-007 — rodada concorrente: `IndexBusy` dentro do timeout, indice intacto.
- [x] IT-008 — busca durante rodada devolve a foto anterior, sem bloquear.
- [x] E2E-007, E2E-008, E2E-009 — termo sem token, linha de uso, pasta so-leitura.

## Success Criteria

- `make test` verde, com todos os casos das tres tasks.
- Os seis Safety Invariants de `_spec.md` tem dono: 1, 2 e 5/6 em IT-006 e IT-009; 3 em IT-008; 4 em
  IT-007.
- Toda linha da tabela `_dx.md` § Errors e produzida pelo binario com a mensagem e o exit code
  escritos la.
- `README.md` descreve os exit codes e a diferenca de casamento em relacao ao `grep`.
