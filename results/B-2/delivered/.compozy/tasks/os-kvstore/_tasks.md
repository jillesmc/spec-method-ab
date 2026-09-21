---
schema_version: "compozy.tasks/v2"
workflow: os-kvstore
graph:
  nodes:
    - id: task_01
      file: task_01.md
    - id: task_02
      file: task_02.md
    - id: task_03
      file: task_03.md
    - id: task_04
      file: task_04.md
    - id: task_05
      file: task_05.md
    - id: task_06
      file: task_06.md
  edges:
    - from: task_01
      to: task_02
    - from: task_02
      to: task_03
    - from: task_03
      to: task_04
    - from: task_04
      to: task_05
    - from: task_05
      to: task_06
---

# Tasks: os-kvstore

Convertido de `openspec/changes/kvstore/tasks.md`.
Dependencias sao uma cadeia sequencial inferida da numeracao; ajuste `graph.edges`
se dois blocos forem de fato independentes.

| Task | Titulo | Status | Depende de |
|---|---|---|---|
| task_01 | Abertura do store e pragmas de durabilidade | completed | -- |
| task_02 | Operações do store | completed | task_01 |
| task_03 | Linha de comando | completed | task_02 |
| task_04 | Testes de falha abrupta (o núcleo da mudança) | completed | task_03 |
| task_05 | Concorrência e crescimento | completed | task_04 |
| task_06 | Fechamento | completed | task_05 |
