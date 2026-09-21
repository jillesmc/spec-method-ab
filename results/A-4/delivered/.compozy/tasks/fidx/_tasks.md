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
    - id: task_04
      file: task_04.md
  edges:
    - from: task_01
      to: task_03
    - from: task_02
      to: task_03
    - from: task_03
      to: task_04
---

# Tasks: fidx

Decomposição de [`_spec.md`](_spec.md). Quatro tasks; todas fazem parte do MVP.

| #       | Título                                                        | Tipo    | Complexidade | Depende de       | Casos de teste                                    |
| ------- | ------------------------------------------------------------- | ------- | ------------ | ---------------- | ------------------------------------------------- |
| task_01 | Índice sqlite3: esquema, gravação, remoção e consulta          | backend | medium       | —                | UT-020–UT-032                                     |
| task_02 | Varredura da pasta: elegibilidade, digest e tokenização        | backend | low          | —                | UT-001–UT-014                                     |
| task_03 | Comandos `index` e `search` ponta a ponta, com incremental     | feature | medium       | task_01, task_02 | IT-001–IT-012, IT-016, E2E-001, E2E-006–E2E-008   |
| task_04 | Contrato de operação: códigos de saída, erros, atomicidade     | feature | medium       | task_03          | IT-013–IT-015, IT-017, E2E-002–E2E-005            |

## Ordem e motivo

- **task_01 e task_02 são folhas e correm em paralelo.** Uma não importa a outra
  (`_spec.md` → Architectural Boundaries), e cada uma verifica a própria fronteira pela suíte de unidade.
- **task_03 é a slice 1**: é ela que resolve o Motivating Problem — depois dela o operador já roda
  `index` e `search` e aposenta o `grep -r` no uso normal. Só começa depois que as duas assinaturas de
  task_01 e task_02 existem, porque é ela quem as costura.
- **task_04 fecha o contrato que o cron precisa**: código de saída por classe, mensagem em stderr,
  atomicidade da rodada e execução concorrente. Depende de task_03 porque endurece o caminho que ela abriu.

Sem task de QA separada: a superfície é uma CLI de dois verbos, e task_04 já é a verificação de integração
pela superfície pública. Sem `_uiux.md` e sem Visual Contract — a feature não tem superfície visual.
