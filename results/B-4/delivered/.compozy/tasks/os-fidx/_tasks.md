---
schema_version: "compozy.tasks/v2"
workflow: os-fidx
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
  edges:
    - from: task_01
      to: task_02
    - from: task_02
      to: task_03
    - from: task_03
      to: task_04
    - from: task_04
      to: task_05
---

# Tasks: os-fidx

Convertido de `openspec/changes/fidx/tasks.md`.
Dependencias sao uma cadeia sequencial inferida da numeracao; ajuste `graph.edges`
se dois blocos forem de fato independentes.

| Task | Titulo | Status | Depende de |
|---|---|---|---|
| task_01 | Storage and tokenising | completed | -- |
| task_02 | Content-addressed refresh | completed | task_01 |
| task_03 | Search | completed | task_02 |
| task_04 | CLI | completed | task_03 |
| task_05 | Wrap-up | completed | task_04 |
