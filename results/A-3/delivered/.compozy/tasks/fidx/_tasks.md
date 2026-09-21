---
schema_version: "compozy.tasks/v2"
workflow: fidx
graph:
  nodes:
    - id: task_01
      file: task_01.md
    - id: task_02
      file: task_02.md
    - id: task_03
      file: task_03.md
  edges:
    - from: task_01
      to: task_02
    - from: task_02
      to: task_03
---

# Tasks: fidx

Decomposicao de [`_spec.md`](_spec.md). Tres entregas, cada uma util sozinha, em cadeia: a primeira
resolve o Motivating Problem, a segunda resolve o requisito do cron, a terceira endurece a operacao
desatendida.

| #       | Titulo                                        | Tipo    | Complexidade | Entrega observavel                                                                  | Depende de |
| ------- | --------------------------------------------- | ------- | ------------ | ------------------------------------------------------------------------------------ | ---------- |
| task_01 | Indexar e buscar de ponta a ponta             | feature | medium       | `index` constroi o indice e `search` lista os arquivos do termo, sem varrer a pasta   | —          |
| task_02 | Reindexacao incremental por hash de conteudo  | feature | high         | Rodada de cron reprocessa so o que mudou de conteudo e remove o que sumiu             | task_01    |
| task_03 | Operacao por cron: atomicidade, concorrencia e superficie de erro | feature | high | Rodada interrompida ou concorrente nao corrompe o indice; erros acionaveis e README | task_02    |

## Por que este corte

- **task_01 primeiro** porque ja entrega o valor do enunciado (parar de esperar o `grep`): indexa
  reescrevendo tudo e busca. Ela e tambem quem congela o esquema do SQLite e a superficie da CLI —
  o contrato compartilhado que as duas seguintes consomem, resolvido antes dos consumidores.
- **task_02 depois** porque o incremental so tem onde existir depois que ha esquema e rodada. E o
  risco central do projeto (ADR-001) concentrado em um lugar: quem revisa olha um diff que fala so
  de deteccao de mudanca.
- **task_03 por ultimo** porque atomicidade, lock e superficie de erro endurecem um caminho que
  precisa existir primeiro, e porque so fazem sentido depois que a rodada ja escreve pouco.
- Nao ha task separada para "escrever os testes" nem para "documentacao": cada entrega carrega os
  proprios casos de `_tests.md`, e o README acompanha a ultima mudanca de contrato.

## Cobertura de teste

Cada ID de `_tests.md` pertence a exatamente uma task:

- **task_01** — UT-001 a UT-019, IT-001, E2E-001 a E2E-005.
- **task_02** — UT-020 a UT-029, IT-002 a IT-005, E2E-006.
- **task_03** — UT-030 a UT-033, IT-006 a IT-009, E2E-007 a E2E-009.

Portao unico em todas: `make test` verde, incluindo o `tests/test_fumaca.py` que ja existia.
