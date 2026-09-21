---
status: completed
title: Linha de comando `python -m kvstore`
type: feature
complexity: medium
---

# Task 2: Linha de comando `python -m kvstore`

## Overview

Depois desta tarefa, o operador tem os quatro verbos que o enunciado pede —
`python -m kvstore <diretorio> {set|get|del|list}` — e consegue descobrir, conferir e corrigir o estado
do serviço durante um incidente, sem escrever código e sem derrubar o processo. A durabilidade já veio
da task_01; esta tarefa é a tradução entre `sys.argv` e `Store`, e entre exceção e código de saída.

Complexidade `medium`: não há risco de perda de dado aqui, mas há uma tabela de contratos observáveis
(código de saída, texto exato em `stderr`, ausência de newline em `get`) que scripts do operador vão
depender e que é fácil violar sem perceber.

## Shippable Outcome

- **Outcome**: o Golden Path de `_dx.md` roda de ponta a ponta num terminal — gravar, listar, ler,
  apagar — com os códigos de saída da tabela de Errors, incluindo a distinção entre chave ausente
  (código 1), erro de uso (2) e erro de armazenamento (3).
- **Verify in this task**: `tests/test_cli.py` (`E2E-001`–`E2E-027`), executando
  `subprocess.run([sys.executable, "-m", "kvstore", ...])` com as invocações verbatim de `_dx.md` e
  conferindo `stdout`, `stderr` e `returncode`. A verificação é pelo caminho de entrada real: o
  processo é de fato lançado, não é uma chamada de função disfarçada.
- **Integration verification**: `none`. A contenção entre processos (`IT-023`) e a escala de `list`
  (`IT-031`) pertencem à task_03 e não são pré-requisito de aceitação desta.

## Requirements

- **`kvstore/__main__.py` não pode importar `sqlite3` nem emitir SQL.** Fronteira arquitetural de
  `_spec.md`: toda interação com o motor passa por `Store`, para que a garantia de durabilidade tenha
  um dono só. Abrir conexão aqui perderia `synchronous=FULL` em silêncio.
- **A tabela de Errors de [`_dx.md`](_dx.md) é contrato literal**, não sugestão: cada mensagem em
  `stderr` é comparada caractere a caractere pelos testes. Toda mensagem leva o prefixo `kvstore: `.
- **`stdout` é só para dado.** Nenhuma mensagem de erro, aviso ou diagnóstico vai para lá — é o que
  permite `valor=$(python -m kvstore ./dados get k)` funcionar.
- **`get` não acrescenta newline.** O valor sai exatamente como entrou, para que
  `get dump > copia.json` reproduza o arquivo byte a byte. Escrever em `sys.stdout.buffer`, não em
  `print`.
- **UTF-8 explícito** em `stdin`, `stdout` e `stderr`, independente do locale da máquina.
- **`del` de chave ausente termina com 0** (idempotente). Decisão registrada em `_spec.md` §
  Assumptions — a pós-condição desejada já vale, e num serviço que reinicia várias vezes por dia a
  repetição de comando é a norma.
- **`-` no lugar do valor lê a entrada padrão.** Existe porque o enunciado diz que os valores podem ser
  grandes e o limite de tamanho de argumentos do sistema operacional é da ordem de 2 MiB. Passar `-`
  **e** um argumento de valor é erro de uso (código 2), não uma das duas fontes escolhida em silêncio.
- **O diretório vem antes do verbo**, conforme o enunciado: `python -m kvstore <diretorio> <comando>`.
- **`list` escreve à medida que itera**, sem materializar todas as chaves formatadas de uma vez, e
  termina sem traceback quando o leitor fecha o pipe.
- **Sem `--json` e sem flags.** Decidido em `_spec.md` § Key Decisions: valores são texto opaco, e o
  único parâmetro é o diretório.
- Os quatro verbos ficam **nesta** tarefa de propósito: partilham o mesmo analisador de argumentos e a
  mesma tabela de erros. Separá-los criaria uma fronteira a renegociar.

## Subtasks

- [x] 2.1 Criar `kvstore/__main__.py` com o analisador de argumentos: diretório, verbo, aridade por
      verbo, e as duas linhas de uso (a geral e a específica de `set`).
- [x] 2.2 Implementar `set`, incluindo a leitura de `stdin` quando o valor é `-` e a rejeição de `-`
      acompanhado de argumento.
- [x] 2.3 Implementar `get` (valor cru em `sys.stdout.buffer`, código 1 quando ausente), `del`
      (idempotente) e `list` (uma chave por linha, em ordem, escrita incremental).
- [x] 2.4 Implementar o mapeamento de exceção para código de saída: `ValueError`/`TypeError`/uso → 2,
      `sqlite3.Error` e erro de sistema de arquivos → 3, com as mensagens exatas de `_dx.md`;
      incluindo a mensagem de contenção que nomeia os 5 s.
- [x] 2.5 Tratar `BrokenPipeError` em `list` e em `get` para terminar sem traceback.
- [x] 2.6 Escrever `tests/test_cli.py` com os 27 casos `E2E`, agrupados como em `_tests.md`.
- [x] 2.7 Conferir que `make test` passa inteiro.

## Implementation Details

`kvstore/__main__.py` é novo. Ele abre um `Store`, executa **uma** operação e fecha — não há laço nem
estado entre invocações. A forma geral e a saída esperada de cada verbo estão em `_dx.md` § CLI; a
tabela de código × condição × mensagem está em `_dx.md` § Errors. Implemente contra esses dois, que
são a superfície congelada.

Pontos onde o contrato é mais fino do que parece:

- `get` de chave ausente escreve **nada** em `stdout` e termina com 1; `get` de valor vazio escreve
  **nada** em `stdout` e termina com **0**. Os dois casos têm `stdout` idêntico e códigos diferentes —
  é o código que carrega a informação (`E2E-002` e `E2E-006`).
- `get` em diretório que nunca recebeu escrita é código 1 (chave não encontrada), não 3: o diretório é
  criado, o armazenamento é válido, a chave é que não existe (`E2E-022`).
- Chaves com `/`, `..` ou espaço são chaves comuns e não viram caminho de arquivo. `E2E-007` confere
  que nenhum arquivo além de `kvstore.sqlite3*` aparece no diretório.
- A validação de chave vazia pode chegar como `ValueError` vindo de `Store`; a mensagem apresentada ao
  usuário é a de `_dx.md` (`kvstore: chave nao pode ser vazia`), não o texto da exceção.

### Relevant Files

- `kvstore/__main__.py` — novo; ponto de entrada de `python -m kvstore`.
- `kvstore/__init__.py` — a classe `Store` entregue pela task_01; consumida, nunca contornada.
- `tests/test_cli.py` — novo; os 27 casos E2E.
- `README.md:4-5` — já mostra `python -m kvstore ./dados set foo bar`; a invocação implementada tem de
  bater com essa linha (o README completo é atualizado na task_04).
- `Makefile:2-3` — descobre o arquivo de teste novo sozinho.

### Dependent Files

- `tests/test_durabilidade.py` (task_03) — `IT-023` e `IT-031` executam esta linha de comando; a
  mensagem de contenção e a saída de `list` criadas aqui são o que aqueles casos afirmam.
- `README.md` (task_04) — documenta os verbos definidos aqui.

### Related ADRs

- [ADR-002: WAL com `synchronous=FULL` como nível de durabilidade](adrs/adr-002.md) — origem do valor
  de 5 s que a mensagem de contenção promete ao operador; se a constante mudar, a mensagem muda junto.

## Deliverables

- `kvstore/__main__.py` com os quatro verbos, a leitura de `stdin` e o mapeamento completo de erros.
- `tests/test_cli.py` com os 27 casos E2E.
- `make test` verde.

## Tests

Casos atribuídos de [`_tests.md`](_tests.md) — leia a definição de cada um antes de escrever.

- [x] `E2E-001`, `E2E-002`, `E2E-003`, `E2E-004`, `E2E-008`, `E2E-009`, `E2E-010` — jornada principal:
      Golden Path verbatim, chave ausente, fidelidade de saída sem newline, sobrescrita, `del`
      idempotente, `list` vazio e `list` ordenado.
- [x] `E2E-005`, `E2E-006`, `E2E-007`, `E2E-011`, `E2E-012`, `E2E-013`, `E2E-014`, `E2E-024`,
      `E2E-027` — entradas e limites: chave vazia, valor vazio, chaves hostis, 10 MB por `stdin`,
      `stdin` vazio, `-` com argumento extra, `stdin` não-UTF-8, valor de 5 MB por pipe, e o texto
      literal `-`.
- [x] `E2E-015`, `E2E-016`, `E2E-017` — descobribilidade: sem argumentos, verbo desconhecido, aridade
      errada.
- [x] `E2E-018`, `E2E-019`, `E2E-020`, `E2E-021`, `E2E-022`, `E2E-025`, `E2E-026` — diretório e sistema
      de arquivos: criação implícita, `list` em diretório inexistente, caminho que é arquivo comum,
      pai sem permissão, `get` em diretório virgem, diretório somente-leitura, e o contrato de quais
      arquivos aparecem em disco.
- [x] `E2E-023` — `list` com o leitor fechando o pipe, sem `BrokenPipeError` em `stderr`.

`E2E-021` e `E2E-025` dependem de permissão de arquivo e devem ser pulados quando a suíte roda como
`root`, que as ignora.

## Success Criteria

- Cada uma das nove linhas da tabela de Errors de `_dx.md` é alcançável por uma invocação real e
  produz exatamente o código e o texto documentados.
- `python -m kvstore ./dados get chave > arquivo` reproduz o valor byte a byte, sem newline
  acrescentado, para valor com e sem newline final.
- `grep` por `sqlite3` e por `SELECT`/`INSERT` em `kvstore/__main__.py` não retorna nada — a fronteira
  arquitetural está de pé.
- Nenhuma mensagem de diagnóstico aparece em `stdout` em nenhum dos 27 casos.
- `make test` passa inteiro.
