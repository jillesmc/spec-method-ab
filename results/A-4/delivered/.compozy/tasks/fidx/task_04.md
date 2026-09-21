---
status: completed
title: "Contrato de operação: códigos de saída, erros, atomicidade"
type: feature
complexity: medium
---

# Task 4: Contrato de operação: códigos de saída, erros, atomicidade

## Overview

Fecha a superfície que o cron precisa. Depois desta task, o agendamento distingue pelo código de saída
"não achei nada" (1) de "não consegui rodar" (2), toda falha tem mensagem em stderr com stdout limpo, uma
rodada interrompida não deixa índice pela metade e duas execuções simultâneas não se atropelam.

## Shippable Outcome

- Outcome: `python -m fidx` responde com o código de saída e a mensagem certos em cada classe de falha de
  [`_dx.md`](_dx.md), e o índice sobrevive a interrupção e a concorrência.
- Verify in this task: `tests/test_cli.py` (E2E-002–E2E-005, por subprocesso, na entrada real) e
  `tests/test_index.py` (IT-013–IT-015, IT-017).
- Integration verification: none — esta task **é** a verificação de integração da entrega.

## Requirements

- Códigos de saída conforme a regra de negócio 9 e a tabela de `_dx.md`: `0` sucesso; `1` busca sem
  resultado (stdout vazio, nada impresso); `2` não foi possível executar.
- Mensagens de erro exatamente com o texto da tabela de `_dx.md`, todas em **stderr**, sempre com stdout
  vazio:
  - diretório inexistente ou que não é diretório;
  - `search` antes de qualquer `index` (a mensagem inclui o comando a rodar);
  - índice em uso por outra execução;
  - pasta sem permissão de escrita no `index`.
- Traduzir as exceções, não vazá-las: `IndiceEmUso` (task_01), `FileNotFoundError` do
  `Indice.abrir(criar=False)` e o erro de permissão viram mensagem + saída 2. Nenhum traceback na saída do
  cron.
- `argparse` cuida de uso incorreto (saída 2 com `usage:`) — não reimplementar.
- Atomicidade (Safety Invariants 1–3): confirmar que a indexação inteira roda numa transação e que uma
  exceção no meio deixa o índice no estado da rodada anterior. Se a task_03 não fechou isso, é aqui que
  fecha.
- Não alterar o formato do resumo nem o do resultado da busca entregues na task_03.

## Subtasks

- [x] 4.1 Centralizar a validação do diretório e a tradução de exceções em `fidx/__main__.py`, com retorno
      do código de saída por `sys.exit`.
- [x] 4.2 Implementar a saída 1 do `search` sem resultado (stdout vazio).
- [x] 4.3 Conferir/ajustar a transação única do `index` e a tradução de `IndiceEmUso`.
- [x] 4.4 Escrever os casos de falha em `tests/test_cli.py` e os de atomicidade e concorrência em
      `tests/test_index.py`.
- [x] 4.5 Rodar `make test` e conferir a suíte inteira verde.

## Implementation Details

Arquivo a modificar: `fidx/__main__.py`. Arquivos a estender: `tests/test_cli.py`, `tests/test_index.py`.

Concorrência é simulada com uma segunda conexão sqlite segurando `BEGIN IMMEDIATE` no mesmo arquivo — não
com processo paralelo e `sleep`, que produz teste instável. Interrupção é simulada injetando um `scan.ler`
que levanta `RuntimeError` no segundo arquivo.

IT-017 e qualquer caso baseado em permissão são pulados quando `os.geteuid() == 0`: como root, `chmod`
não impede a escrita e o caso passaria por engano.

### Relevant Files

- `fidx/__main__.py` (task_03) — onde a tradução de erro e o `sys.exit` entram; é o único lugar que decide
  código de saída (`_spec.md` → Architectural Boundaries).
- `fidx/store.py` (task_01) — `IndiceEmUso`, `FileNotFoundError` e o gerenciador de contexto com rollback.
- `_dx.md` → seção `Errors` — a tabela que estas mensagens têm de reproduzir.
- `_spec.md` → Safety Invariants — a lista numerada que os casos IT-013–IT-015 provam.

### Dependent Files

- `tests/test_cli.py`, `tests/test_index.py` — criados na task_03, estendidos aqui.

### Related ADRs

- [ADR-002](adrs/adr-002.md) — o bloqueio do sqlite e a transação única que dão esses comportamentos sem
  lockfile próprio.

## Deliverables

- `fidx/__main__.py` com o contrato de erro e de código de saída completo.
- Casos de falha, atomicidade e concorrência nas duas suítes.

## Tests

Casos atribuídos de [`_tests.md`](_tests.md) — ler cada definição antes de escrever o teste.

- [x] IT-013 — indexação interrompida no meio deixa o índice no estado da rodada anterior.
- [x] IT-014 — segunda indexação simultânea levanta `IndiceEmUso` e o índice segue consultável.
- [x] IT-015 — `search` durante um `index` em andamento responde sem erro e sem esperar o `timeout`.
- [x] IT-017 — pasta sem permissão de escrita produz o erro que vira a mensagem de `_dx.md`.
- [x] E2E-002 — busca sem resultado: stdout vazio, saída 1.
- [x] E2E-003 — busca antes de qualquer `index`: stderr com a instrução, saída 2.
- [x] E2E-004 — caminho inexistente em `index` e em `search`: stderr, saída 2, nada criado no disco.
- [x] E2E-005 — subcomando ausente e subcomando desconhecido: `usage:` em stderr, saída 2.

## Success Criteria

- `make test` verde, com todas as suítes das quatro tasks.
- Nenhuma invocação de falha imprime traceback: em E2E-002–E2E-005, `stderr` não contém `Traceback` e
  `stdout` é string vazia.
- Os seis Safety Invariants de `_spec.md` têm dono: 1–3 em IT-013, 4 em IT-014, 5 em IT-015, 6 em IT-016
  (task_03).
- A tabela de códigos de saída de `_dx.md` está inteira coberta: 0 (E2E-001), 1 (E2E-002), 2 (E2E-003,
  E2E-004, E2E-005).
