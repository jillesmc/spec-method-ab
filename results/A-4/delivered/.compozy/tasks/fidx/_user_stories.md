# User Stories: fidx

Catálogo canônico de comportamento do fidx. Companheiro de `_spec.md`; consumido por
`_spec.md` Parte II (mapa de componentes) e `_tests.md` (matriz de cobertura).

## Personas

- **Operador** — dono da pasta de notas, relatórios exportados e dumps. Hoje usa `grep -r` e espera.
  Quer achar em qual arquivo um termo aparece, rápido, pela linha de comando.
- **Cron** — o agendador que roda `python -m fidx <dir> index` de tempos em tempos, sem ninguém olhando.
  Precisa de execução curta, saída previsível e código de saída honesto.

## Story Index

| ID     | Área            | Persona  | Story                                                              |
| ------ | --------------- | -------- | ------------------------------------------------------------------ |
| US-001 | Indexação       | Operador | Construir o índice da pasta na primeira vez                        |
| US-002 | Busca           | Operador | Descobrir em quais arquivos um termo aparece                       |
| US-003 | Indexação       | Cron     | Reindexar sem reprocessar o que não mudou                          |
| US-004 | Confiabilidade  | Operador | Mudança de conteúdo entra no índice mesmo com data de modificação mentirosa |
| US-005 | Confiabilidade  | Operador | Arquivo removido some dos resultados                               |
| US-006 | Operação        | Cron     | Falha diagnosticável por mensagem e código de saída                |

## Indexação

### US-001: Construir o índice da pasta

**As a** Operador, **I want** rodar `python -m fidx <diretorio> index` numa pasta ainda não indexada,
**so that** as buscas seguintes não precisem varrer a pasta inteira.

Acceptance criteria:

- AC-1: Dado um diretório com arquivos de texto e sem índice, quando rodo `index`, então o índice é criado
  dentro do diretório e o comando imprime quantos arquivos foram indexados.
- AC-2: Dado que o `index` terminou com sucesso, quando rodo `search` por um termo que existe num dos
  arquivos, então aquele arquivo aparece no resultado sem nova varredura da pasta.
- AC-3: Dado um diretório, quando rodo `index`, então o próprio arquivo de índice não é indexado.

Edge cases:

- EC-1: Diretório vazio → índice é criado, saída informa `0 arquivos`, saída 0.
- EC-2: Diretório inexistente ou que não é diretório → mensagem em stderr nomeando o caminho, saída 2, nada é criado.
- EC-3: Arquivo binário (não decodificável como UTF-8) → é contado como ignorado, não entra no índice, e o
  restante da pasta é indexado normalmente.
- EC-4: Entradas ocultas (nome começando com `.`, incluindo `.git/`) → não são varridas nem indexadas.
- EC-5: Diretório sem permissão de escrita → mensagem em stderr dizendo que o índice não pôde ser criado, saída 2.
- EC-6: Arquivo sem permissão de leitura → contado como ignorado; o `index` termina com saída 0.

## Busca

### US-002: Descobrir em quais arquivos um termo aparece

**As a** Operador, **I want** rodar `python -m fidx <diretorio> search <termo>`,
**so that** eu veja a lista de arquivos que contêm o termo, sem esperar um `grep -r`.

Acceptance criteria:

- AC-1: Dado um índice construído, quando busco um termo presente em dois arquivos, então os dois caminhos
  são impressos, um por linha, relativos ao diretório, em ordem alfabética, e a saída é 0.
- AC-2: Dado um índice construído, quando busco um termo com caixa diferente da que está no arquivo
  (`Orçamento` vs `orçamento`), então o arquivo é encontrado.
- AC-3: Dado um índice construído, quando busco um termo que não existe em nenhum arquivo, então nada é
  impresso em stdout e a saída é 1.

Edge cases:

- EC-1: Busca antes de qualquer `index` → mensagem em stderr instruindo rodar `index`, saída 2.
- EC-2: Termo com mais de uma palavra (`"relatorio mensal"`) → retorna os arquivos que contêm **todas** as
  palavras, em qualquer posição do arquivo.
- EC-3: Termo só de pontuação ou vazio (`""`, `"---"`) → nenhuma palavra a buscar; nada em stdout, saída 1.
- EC-4: Termo que é pedaço de palavra (`orca` para `orcamento`) → não casa; a busca é por palavra inteira.
- EC-5: Índice existe mas está desatualizado em relação ao disco → a busca responde pelo índice; o resultado
  reflete o último `index` (o comando não varre a pasta).

## Confiabilidade

### US-003: Reindexar sem reprocessar o que não mudou

**As a** Cron, **I want** que o `index` reprocesse apenas o que mudou desde a última rodada,
**so that** a execução periódica não custe uma reindexação inteira toda hora.

Acceptance criteria:

- AC-1: Dado um índice atualizado, quando rodo `index` de novo sem alterar nada, então a saída informa
  `0 novos, 0 alterados, 0 removidos` e todos os arquivos como inalterados.
- AC-2: Dado um índice atualizado, quando altero o conteúdo de um arquivo e rodo `index`, então só aquele
  arquivo é reprocessado (contado como alterado) e os demais aparecem como inalterados.
- AC-3: Dado um arquivo novo na pasta, quando rodo `index`, então ele é contado como novo e passa a ser
  encontrável pelo `search`.

Edge cases:

- EC-1: Arquivo renomeado com conteúdo idêntico → o caminho antigo é removido e o novo é adicionado; a busca
  passa a devolver o novo caminho.
- EC-2: Índice gravado por uma versão anterior do formato → é descartado e reconstruído do zero, sem erro
  para o operador.
- EC-3: Duas execuções de `index` ao mesmo tempo → a segunda não corrompe nem espera indefinidamente:
  termina com mensagem de índice em uso e saída 2.
- EC-4: `index` interrompido no meio (exceção, `SIGKILL` do lote anterior) → o índice permanece no estado da
  última execução bem-sucedida; nenhuma atualização pela metade é observável.
- EC-5: Um `search` disparado enquanto um `index` roda → responde com o índice da execução anterior, sem erro.

### US-004: Mudança de conteúdo entra no índice mesmo com data mentirosa

**As a** Operador (cujos arquivos chegam por rsync e por checkout), **I want** que a decisão de reprocessar
dependa do conteúdo, **so that** nenhuma alteração seja perdida por causa de `mtime` não confiável.

Acceptance criteria:

- AC-1: Dado um arquivo já indexado, quando seu conteúdo muda e sua data de modificação volta para o
  passado, então o `index` o reprocessa e o termo novo passa a ser encontrável.
- AC-2: Dado um arquivo já indexado, quando sua data de modificação avança sem que o conteúdo mude, então o
  `index` o conta como inalterado e não reescreve suas entradas.
- AC-3: Dado um arquivo cujo conteúdo mudou, quando o `index` o reprocessa, então os termos que só existiam
  na versão antiga deixam de apontar para ele.

Edge cases:

- EC-1: Conteúdo muda mantendo o mesmo tamanho em bytes → ainda assim detectado como alterado.
- EC-2: Dois arquivos com conteúdo idêntico → ambos indexados e ambos devolvidos na busca.

### US-005: Arquivo removido some dos resultados

**As a** Operador, **I want** que arquivos apagados da pasta saiam do índice na próxima rodada,
**so that** a busca não me mande abrir arquivo que não existe mais.

Acceptance criteria:

- AC-1: Dado um arquivo indexado, quando ele é apagado da pasta e o `index` roda, então ele é contado como
  removido e não aparece mais em nenhuma busca.
- AC-2: Dado um arquivo que passou a ser ignorado (virou binário, perdeu permissão de leitura), quando o
  `index` roda, então ele deixa de aparecer nas buscas.

Edge cases:

- EC-1: Todos os arquivos removidos → índice fica vazio, buscas retornam saída 1, e o comando não falha.
- EC-2: Diretório inteiro removido entre duas rodadas → `index` falha com mensagem de diretório inexistente
  (saída 2); como o índice morava dentro da pasta, ele se foi junto, e volta a ser construído do zero se a
  pasta voltar.

## Operação

### US-006: Falha diagnosticável por mensagem e código de saída

**As a** Cron, **I want** códigos de saída distintos e mensagens em stderr,
**so that** o agendamento saiba diferenciar "nada encontrado" de "não consegui rodar".

Acceptance criteria:

- AC-1: Sucesso (`index` concluído, `search` com ao menos um resultado) → saída 0.
- AC-2: `search` sem resultado → saída 1, stdout vazio.
- AC-3: Erro de operação (uso incorreto, diretório inválido, índice ausente ou em uso) → saída 2 e mensagem
  em stderr; stdout permanece vazio.

Edge cases:

- EC-1: Subcomando desconhecido ou argumento faltando → uso impresso em stderr, saída 2.
- EC-2: stdout redirecionado para arquivo → apenas os caminhos (no `search`) ou o resumo (no `index`) vão
  para o arquivo; mensagens de erro vão para stderr.
