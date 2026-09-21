---
status: completed
title: Concorrência e crescimento
type: test
complexity: high
---

# Task 3: Concorrência e crescimento

## Overview

Depois desta tarefa, duas afirmações que a spec faz deixam de ser projeto de desenho e passam a ser
resultado medido: que o operador pode rodar `get` e `list` com o serviço escrevendo, sem corromper
nada nem receber erro de banco travado; e que o armazenamento pode crescer indefinidamente, com
ninguém limpando nada, sem exigir rotina de manutenção.

São as duas restrições do enunciado que o desenho resolveu por escolha de motor (`adrs/adr-001.md`) e
não por código próprio — exatamente por isso precisam de prova independente. Complexidade `high` pelo
risco de instabilidade: testes de concorrência escritos com `sleep` passam na máquina de quem escreveu
e falham no CI alheio.

## Shippable Outcome

- **Outcome**: `make test` passa a cobrir as invariantes 6, 7 e 8 de `_spec.md` § Safety Invariants
  (concorrência entre processos) e os critérios de crescimento de `US-008`. Uma regressão futura que
  troque o modo de journal, remova o `busy_timeout` ou reintroduza reescrita total passa a quebrar a
  suíte em vez de chegar em produção.
- **Verify in this task**: os sete casos `IT-020`–`IT-023` e `IT-030`–`IT-032` em
  `tests/test_durabilidade.py`, todos lançando processos reais e, em `IT-023` e `IT-031`, passando
  pela linha de comando de verdade.
- **Integration verification**: `none` — esta **é** a tarefa de verificação de integração do grafo.
  Nenhuma tarefa posterior herda verificação pendente daqui.

## Requirements

- **Sincronização entre processos por pipe e por sinal, nunca por relógio.** Um filho anuncia
  prontidão escrevendo numa pipe; o pai reage a isso. `sleep` só é admitido em `IT-023`, onde a
  passagem do tempo é o objeto do teste, e ainda assim como teto de segurança.
- **Nenhum teste pode travar a suíte.** Todo `subprocess` levantado recebe `timeout`, e `IT-023`
  falha explicitamente se o comando não retornar em ~10 s — travar indefinidamente é justamente o
  defeito que ele procura.
- **Todos os casos usam `tempfile.TemporaryDirectory`**; nenhum banco pode sobrar na árvore do
  repositório.
- **Pulados fora de POSIX** (`@unittest.skipUnless(os.name == "posix", ...)`), como o resto de
  `tests/test_durabilidade.py`.
- **`IT-030` é o caso mais lento da suíte** (2.000 `fsync`, um por gravação confirmada). Se passar de
  poucos segundos, reduzir a contagem **sem** mudar a asserção — o que o caso prova é que o tamanho
  acompanha o dado vivo, não a soma das gravações, e isso não depende do número exato.
- **A asserção de `IT-032` é contraintuitiva de propósito**: depois de apagar uma chave grande, o teste
  espera que o arquivo **não** tenha encolhido. É o comportamento documentado em `US-008.EC-1` e em
  `_spec.md` § Non-Goals (sem `VACUUM`); o que precisa ser provado é que o espaço liberado volta a ser
  usado pela gravação seguinte.
- **Não duplicar a unidade.** Estes casos existem porque há fronteira de processo ou tamanho em disco
  envolvido; qualquer invariante que caiba em `tests/test_store.py` já pertence à task_01.

## Subtasks

- [x] 3.1 Escrever o auxiliar de processo filho usado pelos casos de concorrência (script via
      `python -c`, prontidão anunciada por pipe, `timeout` em toda espera), reaproveitando o padrão já
      criado na task_01 em vez de inventar um segundo.
- [x] 3.2 Implementar `IT-020`, `IT-021` e `IT-022` — leitor durante escritor, dois escritores em
      chaves diferentes, dois escritores na mesma chave.
- [x] 3.3 Implementar `IT-023` — escritor segurando `BEGIN IMMEDIATE` por mais de 5 s, e o comando
      concorrente terminando com código 3 e a mensagem de contenção de `_dx.md`.
- [x] 3.4 Implementar `IT-030` e `IT-032` — crescimento com gravações repetidas e reaproveitamento de
      espaço após remoção.
- [x] 3.5 Implementar `IT-031` — 2.000 chaves, `list` pela linha de comando com as 2.000 linhas em
      ordem e sem truncamento, e `get` de uma chave do meio.
- [x] 3.6 Medir o tempo da suíte completa e registrar no relato da tarefa; ajustar a contagem de
      `IT-030`/`IT-031` se `make test` ficar impraticável para uso diário. Medido: `make test` inteiro
      (65 casos) em ~51-52 s, contra 58 casos em ~36 s antes desta tarefa; os 7 casos novos, isolados,
      rodam em 16-18 s. Considerado aceitável para uso diário — contagens mantidas em 2.000.
- [x] 3.7 Conferir que `make test` passa inteiro.

## Implementation Details

Os casos entram em `tests/test_durabilidade.py`, ao lado dos de morte abrupta da task_01, em classes
separadas por tema (concorrência, crescimento). O arquivo já terá o auxiliar de processo filho criado
lá; reutilizá-lo é o ponto — dois auxiliares diferentes para a mesma coisa é onde a instabilidade
costuma entrar.

`IT-023` precisa de um escritor que segure a trava de escrita sem terminar. O caminho direto é um
processo filho que abre conexão, executa `BEGIN IMMEDIATE`, escreve na pipe que está pronto, e então
bloqueia. O pai só dispara o comando concorrente depois de ler a prontidão — assim o teste não depende
de o filho ter sido escalonado primeiro.

`IT-031` usa a linha de comando de propósito, e não a API: o que ele prova é que `list` não trunca nem
desordena ao sair por `stdout` com 2.000 linhas, que é um comportamento da task_02.

### Relevant Files

- `tests/test_durabilidade.py` — criado na task_01; recebe as classes de concorrência e crescimento.
- `kvstore/__init__.py` — `busy_timeout` e `journal_mode` definidos aqui são o que `IT-020`–`IT-023`
  exercem; se a constante de espera mudar, `IT-023` muda junto.
- `kvstore/__main__.py` — `IT-023` afirma a mensagem de contenção e `IT-031` afirma a saída de `list`,
  ambas definidas na task_02.
- `Makefile:2-3` — o alvo que precisa continuar utilizável no dia a dia depois destes casos.

### Dependent Files

- `README.md` (task_04) — só pode afirmar "nenhuma rotina de manutenção" depois que `IT-030` e
  `IT-032` passarem.

### Related ADRs

- [ADR-001: `sqlite3` da biblioteca padrão como motor de armazenamento](adrs/adr-001.md) — a promessa
  de crescimento sem compactação que `IT-030` e `IT-032` existem para verificar.
- [ADR-002: WAL com `synchronous=FULL` como nível de durabilidade](adrs/adr-002.md) — WAL é o que
  permite leitor e escritor simultâneos (`IT-020`), e `busy_timeout` é o que transforma contenção em
  espera limitada (`IT-023`).

## Deliverables

- Sete casos novos em `tests/test_durabilidade.py`, todos determinísticos e com `timeout`.
- Registro do tempo de execução de `make test` depois deles.
- `make test` verde.

## Tests

Casos atribuídos de [`_tests.md`](_tests.md) — leia a definição de cada um antes de escrever.

- [x] `IT-020` — leitor em paralelo com escritor: toda leitura devolve valor completo e válido, nenhuma
      levanta exceção.
- [x] `IT-021` — dois escritores em chaves diferentes: ambos com código 0, ambas as chaves gravadas.
- [x] `IT-022` — dois escritores na mesma chave: ambos com código 0, o valor final é exatamente um dos
      dois, íntegro, e nenhum erro de banco travado escapa.
- [x] `IT-023` — contenção além dos 5 s: código 3 com a mensagem de contenção, em menos de ~10 s.
      Falha se travar.
- [x] `IT-030` — 2.000 gravações na mesma chave com valor de 4 KB: arquivo abaixo de 2 MB e último
      valor legível.
- [x] `IT-031` — 2.000 chaves: `list` emite as 2.000 linhas em ordem, sem truncar, e `get` de uma
      chave do meio devolve o valor correto. Cobre `US-004.EC-2` e `US-008.EC-2` em escala reduzida,
      pelo motivo registrado em `_tests.md` § Coverage Decisions.
- [x] `IT-032` — reaproveitamento de espaço: o arquivo não encolhe após a remoção, e a gravação
      seguinte reutiliza o espaço em vez de dobrar o tamanho.

## Success Criteria

- A suíte roda dez vezes seguidas sem nenhuma falha intermitente — critério explícito, porque teste de
  concorrência instável é pior que teste ausente: ele treina quem vê a falha a repetir o comando.
- Nenhum caso usa `sleep` como condição de corrida; o único `sleep` presente está em `IT-023`, que é
  sobre tempo.
- Nenhum `subprocess` sem `timeout`.
- O tempo total de `make test` continua aceitável para uso diário, e o número medido está registrado.
- Nenhum arquivo de banco fora de diretório temporário.
- `make test` passa inteiro.
