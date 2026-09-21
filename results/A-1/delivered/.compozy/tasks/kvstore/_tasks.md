---
schema_version: "compozy.tasks/v2"
workflow: kvstore
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
      to: task_02
    - from: task_02
      to: task_03
    - from: task_03
      to: task_04
---

# Task Graph: kvstore

Decomposição de [_spec.md](_spec.md). A cadeia é linear porque cada etapa precisa da anterior
existindo de verdade: a linha de comando chama `Store`, e os testes de concorrência e de crescimento
matam e disputam processos que usam **as duas** superfícies.

| # | Task | Tipo | Complexidade | Depende de | Entrega observável |
|---|------|------|--------------|------------|--------------------|
| 1 | [Camada de armazenamento durável (`Store`)](task_01.md) | feature | critical | — | Gravação confirmada sobrevive a `SIGKILL` e a OOM |
| 2 | [Linha de comando `python -m kvstore`](task_02.md) | feature | medium | task_01 | Os quatro verbos do enunciado, com códigos de saída |
| 3 | [Concorrência e crescimento](task_03.md) | test | high | task_02 | Prova de que dois processos e o crescimento infinito não quebram nada |
| 4 | [README e verificação final](task_04.md) | docs | low | task_03 | Alguém que chega agora usa o pacote sem perguntar nada |

## Fatias de entrega

Correspondem ao MVP Boundary de `_spec.md`:

- **Fatia 1 — task_01.** Resolve o Motivating Problem e **prova**: `Store` durável, com os testes de
  morte abrupta (`IT-010`..`IT-014`) dentro da própria tarefa. Ao fim dela, gravar, matar com
  `SIGKILL` e reler devolve o valor. O serviço já pode adotar o pacote em processo neste ponto.
- **Fatia 2 — task_02.** A superfície pedida no enunciado, para o operador.
- **Fatia 3 — task_03 e task_04.** Endurecimento (concorrência, crescimento) e documentação.

A fatia 1 é deliberadamente a tarefa mais pesada: ela carrega toda a garantia que motiva a spec. As
seguintes são finas de propósito.

## Ordem das arestas, e por que não há paralelismo

- **task_01 → task_02**: a linha de comando é uma camada fina sobre `Store` e depende da assinatura
  congelada em `_spec.md` Part II → Core Interfaces. A fronteira arquitetural proíbe `__main__.py` de
  importar `sqlite3`, então não há como escrevê-la antes.
- **task_02 → task_03**: `IT-023` (contenção além da espera) e `IT-031` (escala via `list`) executam
  `python -m kvstore` de verdade; sem a task_02 não há o que executar.
- **task_03 → task_04**: o README afirma a garantia de durabilidade e a ausência de rotina de
  manutenção. Documentar isso antes de `IT-030`/`IT-032` passarem seria escrever promessa não
  verificada.

Os verbos `set`/`get` e `del`/`list` **não** foram separados em tarefas distintas de propósito: eles
compartilham o mesmo analisador de argumentos e a mesma tabela de erros de `_dx.md`. Partir esse
contrato entre duas tarefas criaria uma fronteira que teria de ser renegociada na segunda.

## Propriedade dos casos de teste

Todo ID de `_tests.md` é atribuído a exatamente uma tarefa:

| Tarefa  | Casos | Total |
|---------|-------|-------|
| task_01 | `UT-001`–`UT-024`, `IT-010`–`IT-014`, `IT-040` | 30 |
| task_02 | `E2E-001`–`E2E-027` | 27 |
| task_03 | `IT-020`–`IT-023`, `IT-030`–`IT-032` | 7 |
| task_04 | nenhum novo — ver a tarefa | 0 |

`IT-022b` está marcado como retirado em `_tests.md` e não pertence a nenhuma tarefa; o número fica
reservado. `tests/test_fumaca.py` continua válido, não é reescrito por nenhuma tarefa, e nenhum caso
novo duplica o que ele já cobre.

## Verificação comum a todas as tarefas

`make test` (`python3 -m unittest discover -s tests -t . -v`) tem de passar ao fim de cada tarefa, não
só no fim da última — é o contrato de verificação que o enunciado fixa. Nenhuma tarefa pode introduzir
dependência fora da biblioteca padrão, nem em execução nem em teste.

## Questões em aberto que não bloqueiam a execução

As duas Open Questions de `_spec.md` foram verificadas contra este grafo e **nenhuma tarefa depende
delas**:

1. **Importar o JSON legado do serviço** — seria uma tarefa adicional (um laço de `set` sobre o
   dicionário carregado) que não altera nenhum contrato definido aqui.
2. **A espera de 5 s sob contenção** — muda uma constante em `kvstore/__init__.py` e o valor esperado
   em `UT-022` e `IT-023`.
