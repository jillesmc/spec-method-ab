---
status: completed
title: README e verificação final
type: docs
complexity: low
---

# Task 4: README e verificação final

## Overview

Depois desta tarefa, alguém que chega no repositório sem contexto consegue usar o pacote e, mais
importante, sabe **o que ele garante e o que ele não garante**. O README hoje tem quatro linhas e
descreve um pacote que ainda não existia; ele passa a descrever os quatro verbos, a garantia de
durabilidade, e as duas limitações registradas de propósito na spec — que o arquivo não encolhe depois
de apagar uma chave grande, e que nenhum software cobre hardware que mente sobre `fsync`.

Fase só de documentação, separada das que mexem em código pelo motivo dado em `_spec.md` §
Development Sequencing. Complexidade `low`: nenhum comportamento muda.

## Shippable Outcome

- **Outcome**: o `README.md` descreve os quatro verbos com exemplo real, a garantia de durabilidade nos
  termos em que ela vale, a API Python em processo, e as limitações conhecidas. Um leitor novo não
  precisa abrir `.compozy/tasks/` para usar o pacote.
- **Verify in this task**: revisão do texto contra `_dx.md` — cada invocação citada no README é
  executada de fato e a saída conferida contra o que o texto promete. Fecha `US-008.AC-3`, que é
  asserção sobre documentação e não tem teste automatizado (registrado em `_tests.md` § Coverage
  Decisions).
- **Integration verification**: `none`. Toda a verificação de comportamento já foi feita nas task_01,
  task_02 e task_03.

## Requirements

- **Nenhuma alteração de comportamento.** Se ao escrever o README aparecer uma divergência entre o
  texto e o código, a correção é no código e pertence à tarefa que o criou — não se conserta código
  numa tarefa de documentação sem dizer.
- **O README não pode prometer mais do que a spec.** Em particular: a durabilidade é "gravação
  confirmada sobrevive a morte do processo e a queda da máquina, **salvo hardware que mente sobre
  `fsync`**". A ressalva vai junto, como está em `_spec.md` § Business Rules e em `adrs/adr-002.md`.
- **Documentar as limitações escolhidas**, não escondê-las: o arquivo não encolhe após remoção
  (`US-008.EC-1`), `list` é ambíguo para chaves contendo newline (`US-004.EC-1`), e um escritor de cada
  vez é o desenho (`_spec.md` § Non-Goals).
- **Nenhuma rotina periódica pode aparecer no README.** É o critério `US-008.AC-3`: se o texto acabar
  sugerindo uma manutenção a agendar, o desenho não cumpriu o que prometeu.
- **Toda invocação citada tem de ser executada** antes de entrar no texto. README com comando que não
  roda é o defeito mais comum desta tarefa.
- **Declarar a versão mínima do Python** coerente com o que o código exige (3.11+, conforme o README
  atual e `_spec.md` § Assumptions).

## Subtasks

- [x] 4.1 Reescrever `README.md`: o que é, os quatro verbos com exemplo executado, a garantia de
      durabilidade com a ressalva, `make test`, e a versão mínima do Python.
- [x] 4.2 Acrescentar a seção de uso em processo (`from kvstore import Store`), que é como o serviço
      realmente consome o pacote.
- [x] 4.3 Acrescentar a seção de limitações conhecidas, com as três limitações escolhidas.
- [x] 4.4 Documentar o que o operador encontra dentro do diretório (`kvstore.sqlite3` e os auxiliares
      `-wal`/`-shm`, que não devem ser apagados nem copiados isoladamente com o serviço no ar),
      conforme `_dx.md` § Arquivos em disco.
- [x] 4.5 Executar cada comando citado e conferir a saída contra o texto.
- [x] 4.6 Reler o README inteiro procurando qualquer rotina periódica sugerida; remover se houver.
- [x] 4.7 Rodar `make test` uma última vez e confirmar que os 64 casos atribuídos no grafo estão
      presentes e passando.

## Implementation Details

Só `README.md` muda. O conteúdo vem de `_dx.md` (invocações e saídas, que são a superfície congelada)
e de `_spec.md` § Business Rules e § Assumptions (o que vale e o que não vale). Não reescrever a spec
dentro do README: ele é a porta de entrada, com o caminho feliz e as ressalvas que importam na prática.

Verificação de fechamento do grafo, além do texto: conferir que os IDs de `_tests.md` atribuídos em
`_tasks.md` § Propriedade dos casos de teste existem mesmo na suíte — 30 na task_01, 27 na task_02, 7
na task_03. `IT-022b` está retirado e não deve existir.

### Relevant Files

- `README.md` — hoje com quatro linhas descrevendo um pacote que ainda não existia; é o alvo.
- `_dx.md` — fonte das invocações e saídas; o README é um recorte dele para quem chega.
- `kvstore/__main__.py`, `kvstore/__init__.py` — a verdade contra a qual o texto é conferido.
- `Makefile:2-3` — o comando de teste citado no README.

### Dependent Files

Nenhum: nada no repositório importa o `README.md`.

### Related ADRs

- [ADR-002: WAL com `synchronous=FULL` como nível de durabilidade](adrs/adr-002.md) — a redação exata
  da garantia e da ressalva sobre `fsync` sai daqui.

## Deliverables

- `README.md` reescrito, com todos os comandos citados executados e conferidos.
- Confirmação de que os 64 IDs de `_tests.md` estão implementados e distribuídos como o grafo declara.
- `make test` verde.

## Tests

Nenhum caso novo de `_tests.md` é atribuído a esta tarefa, e isso é decisão registrada: todo ID do
contrato já pertence a task_01, task_02 ou task_03. O que esta tarefa possui é `US-008.AC-3` — "o
operador lê o README e não encontra nenhuma rotina periódica a agendar" — que é asserção sobre
documentação e é verificada por revisão, conforme `_tests.md` § Coverage Decisions. Criar um teste que
faça `grep` no README para popular esta seção seria inventar cobertura.

## Success Criteria

- Todo comando citado no README foi executado e produziu a saída que o texto mostra.
- A garantia de durabilidade aparece com a ressalva sobre `fsync`, e não numa forma mais forte do que
  a spec autoriza.
- As três limitações escolhidas estão documentadas, não omitidas.
- O README não sugere nenhuma rotina de manutenção periódica (`US-008.AC-3`).
- Os 64 casos de `_tests.md` estão implementados, distribuídos como `_tasks.md` declara, e `IT-022b`
  não existe.
- `make test` passa inteiro.
