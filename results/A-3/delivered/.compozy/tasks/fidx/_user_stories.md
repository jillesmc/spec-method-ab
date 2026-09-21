# User Stories: fidx

Catalogo canonico de comportamento do fidx. Companheiro de `_spec.md`; consumido por
`_spec.md` Part II (mapeamento de componentes) e `_tests.md` (matriz de cobertura).
Sem `_uiux.md`: a feature e CLI.

## Personas

- **Operador** — dono da pasta de notas/relatorios/dumps na propria maquina. Hoje usa `grep -r` e
  espera. Quer perguntar "em quais arquivos aparece X" e receber a lista na hora. Roda os comandos
  no terminal e edita o proprio crontab.
- **Cron** — persona nao-humana que executa `index` de tempos em tempos, sem ninguem olhando. Nao le
  texto: consome exit code e a linha de resumo no log. Nao sabe reagir a pergunta interativa, nao
  tem TTY, e pode disparar de novo antes de a rodada anterior terminar.

## Story Index

| ID     | Feature Area | Persona  | Story                                                         |
| ------ | ------------ | -------- | ------------------------------------------------------------- |
| US-001 | Busca        | Operador | Descobrir em quais arquivos um termo aparece, sem varrer       |
| US-002 | Indexacao    | Operador | Indexar a pasta pela primeira vez                              |
| US-003 | Incremental  | Cron     | Reindexar so o que mudou, rodada apos rodada                   |
| US-004 | Incremental  | Operador | Mudanca detectada mesmo quando a data do arquivo mente         |
| US-005 | Incremental  | Operador | Arquivo apagado deixa de aparecer na busca                     |
| US-006 | Erros        | Operador | Receber erro acionavel em vez de resultado errado              |
| US-007 | Operacao     | Cron     | Rodada interrompida ou concorrente nao corrompe o indice       |

## Busca

### US-001: Descobrir em quais arquivos um termo aparece

**As a** Operador, **I want** consultar um indice ja construido, **so that** eu ache o arquivo certo
sem esperar uma varredura da pasta inteira.

Acceptance criteria:

- AC-1: Dado um indice construido em que `orcamento` aparece em 3 arquivos, quando eu rodo
  `python3 -m fidx ./notas search orcamento`, entao os 3 caminhos sao impressos, um por linha,
  em ordem crescente, e o comando sai com codigo 0.
- AC-2: Dado um arquivo contendo `Orcamento Anual`, quando eu busco `ORCAMENTO`, entao o arquivo
  aparece no resultado (casamento e insensivel a maiuscula/minuscula nos dois lados).
- AC-3: Dado um arquivo A contendo `orcamento` e `2026`, e um arquivo B contendo so `orcamento`,
  quando eu busco `orcamento 2026`, entao so o arquivo A aparece (todos os tokens tem de estar no
  mesmo arquivo).
- AC-4: Dado um indice de uma pasta grande, quando eu busco qualquer termo, entao a resposta chega em
  tempo interativo, porque nenhum arquivo da pasta e aberto durante a busca.
- AC-5: Dado um arquivo com `orcamento` repetido dez vezes, quando eu busco `orcamento`, entao o
  caminho aparece uma unica vez.

Edge cases:

- EC-1: termo que nao esta em nenhum arquivo → nada em `stdout` e exit 1 (mesma convencao do `grep`,
  para encadear com `&&`/`||`).
- EC-2: termo sem nenhum token indexavel (`---`, `!!!`, string vazia) → erro em `stderr` dizendo que
  o termo nao tem token e exit 2, em vez de "nenhum resultado".
- EC-3: busca antes de existir indice → erro em `stderr` com o comando exato de indexacao e exit 2.
- EC-4: arquivo apagado do disco depois da ultima rodada de `index` → ainda pode ser listado; o
  resultado e a foto da ultima rodada, e a rodada seguinte o remove (ver US-005).
- EC-5: busca com termo que existe so em arquivo ignorado pela varredura (dentro de `.git/`) → nao
  aparece, porque nunca foi indexado.
- EC-6: busca enquanto uma rodada de `index` esta escrevendo → responde com o indice da rodada
  anterior, completo e consistente, sem esperar (ver US-007.AC-3).

## Indexacao

### US-002: Indexar a pasta pela primeira vez

**As a** Operador, **I want** construir o indice de uma pasta com um comando, **so that** as buscas
seguintes sejam imediatas.

Acceptance criteria:

- AC-1: Dada uma pasta com 12 arquivos de texto e nenhum indice, quando eu rodo
  `python3 -m fidx ./notas index`, entao `./notas/.fidx.sqlite3` passa a existir e a saida e
  `fidx: 12 arquivos, 12 reindexados, 0 removidos`, com exit 0.
- AC-2: Dado que a pasta tem subpastas em varios niveis, quando eu indexo, entao os arquivos das
  subpastas tambem sao encontraveis, e o caminho impresso na busca inclui o subdiretorio.
- AC-3: Dada uma pasta que contem `.git/` e o proprio `.fidx.sqlite3`, quando eu indexo, entao
  nenhuma entrada iniciada por `.` entra no indice (o indice nunca indexa a si mesmo).
- AC-4: Dado um arquivo com acento (`orçamento`), quando eu busco `orçamento`, entao o arquivo
  aparece — o token preserva o acento e nao e quebrado em pedacos.

Edge cases:

- EC-1: pasta vazia → indice criado, `fidx: 0 arquivos, 0 reindexados, 0 removidos`, exit 0; busca
  seguinte sai com 1.
- EC-2: arquivo sem permissao de leitura → e pulado com um aviso em `stderr` nomeando o caminho, os
  demais sao indexados, e a rodada sai com 0.
- EC-3: arquivo apagado entre a varredura e a leitura → tratado como o EC-2: pulado com aviso, sem
  derrubar a rodada.
- EC-4: arquivo binario/com bytes que nao decodificam em UTF-8 → indexado com os bytes invalidos
  descartados, sem excecao e sem abortar a rodada.
- EC-5: arquivo vazio → registrado no indice, sem nenhum token; conta no total de arquivos.
- EC-6: symlink para diretorio (inclusive apontando para um ancestral) → nao seguido; a varredura
  termina, sem recursao infinita.
- EC-7: o caminho passado nao e uma pasta (nao existe, ou e um arquivo) → erro e exit 2, sem criar
  nada (ver US-006).

## Incremental

### US-003: Reindexar so o que mudou, rodada apos rodada

**As a** Cron, **I want** que cada rodada processe apenas os arquivos cujo conteudo mudou,
**so that** rodar de hora em hora numa pasta grande seja viavel.

Acceptance criteria:

- AC-1: Dada uma pasta ja indexada em que nada mudou, quando a rodada roda de novo, entao a saida e
  `fidx: N arquivos, 0 reindexados, 0 removidos` e nenhum arquivo e re-tokenizado.
- AC-2: Dada uma pasta ja indexada em que 1 de 500 arquivos teve o conteudo alterado, quando a
  rodada roda, entao o resumo diz `1 reindexados` e so os registros daquele arquivo sao reescritos.
- AC-3: Dado um arquivo novo que apareceu na pasta depois da ultima rodada, quando a rodada roda,
  entao ele e indexado e conta como reindexado.
- AC-4: Dado um arquivo cujo conteudo mudou, quando a rodada termina, entao os termos que sairam do
  arquivo deixam de retorna-lo na busca e os que entraram passam a retorna-lo.

Edge cases:

- EC-1: indice apagado entre rodadas (por exemplo por `rsync --delete`) → a rodada reconstroi tudo e
  sai com 0; nao e erro.
- EC-2: indice gravado por uma versao de esquema anterior → tabelas recriadas e pasta reindexada do
  zero, com exit 0.
- EC-3: arquivo que muda de lugar sem mudar de conteudo → o caminho antigo e removido e o novo e
  indexado (conta como 1 reindexado e 1 removido); o conteudo continua encontravel.
- EC-4: todos os arquivos mudaram → comporta-se como a primeira indexacao, sem caminho especial.
- EC-5: rodada sobre pasta onde so houve remocao → `0 reindexados, K removidos`.

### US-004: Mudanca detectada mesmo quando a data do arquivo mente

**As a** Operador cuja pasta chega por rsync e por checkout, **I want** que a deteccao de mudanca
ignore a data do arquivo, **so that** eu nunca busque um conteudo que o indice ja deveria conhecer.

Acceptance criteria:

- AC-1: Dado um arquivo indexado, quando o conteudo e trocado e a data de modificacao e colocada
  **no passado**, entao a rodada seguinte o reindexa e a busca pelo termo novo o encontra.
- AC-2: Dado um arquivo indexado, quando a data de modificacao e atualizada para agora mas o
  conteudo e identico, entao a rodada seguinte **nao** o reindexa (`0 reindexados`).
- AC-3: Dado um arquivo cujo conteudo foi trocado por outro de mesmo tamanho e mesma data, entao a
  mudanca e detectada mesmo assim.

Edge cases:

- EC-1: arquivo restaurado exatamente ao conteudo anterior depois de ter sido alterado e indexado →
  a rodada o reindexa (o hash voltou a divergir do que estava gravado) e o resultado final e correto.
- EC-2: dois arquivos diferentes com conteudo identico → ambos sao indexados e ambos aparecem na
  busca; um nao suprime o outro.

### US-005: Arquivo apagado deixa de aparecer na busca

**As a** Operador, **I want** que o indice acompanhe remocoes, **so that** a busca nao me mande abrir
um arquivo que nao existe mais.

Acceptance criteria:

- AC-1: Dado um arquivo indexado que foi apagado do disco, quando a rodada seguinte roda, entao o
  resumo conta `1 removidos` e a busca pelos termos dele nao o lista mais.
- AC-2: Dada uma subpasta inteira apagada, quando a rodada roda, entao todos os seus caminhos sao
  removidos do indice na mesma rodada.

Edge cases:

- EC-1: arquivo apagado e outro com o mesmo conteudo permanece → o que permanece continua sendo
  encontrado.
- EC-2: termo que so existia no arquivo apagado → a busca passa a sair com 1 (sem resultado).
- EC-3: arquivo que deixou de ser visivel por passar a ser symlink → tratado como removido.

## Erros

### US-006: Receber erro acionavel em vez de resultado errado

**As a** Operador, **I want** mensagens que digam o que fazer, **so that** eu nao confunda erro de
uso com ausencia de ocorrencia.

Acceptance criteria:

- AC-1: Dado um caminho que nao existe, quando eu rodo `index` ou `search` nele, entao a mensagem
  nomeia o caminho, vai para `stderr`, e o exit code e 2.
- AC-2: Dado um caminho que e um arquivo e nao uma pasta, entao o comportamento e o de AC-1.
- AC-3: Dado um subcomando desconhecido, ou a falta do termo em `search`, entao a linha de uso e
  impressa e o exit code e 2.
- AC-4: Dado que nao existe indice, quando eu busco, entao a mensagem inclui o comando exato de
  indexacao daquela pasta e o exit code e 2 — distinto do exit 1 de "sem resultado".

Edge cases:

- EC-1: `python3 -m fidx` sem nenhum argumento → linha de uso, exit 2.
- EC-2: pasta sem permissao de escrita no `index` → erro nomeando a impossibilidade de criar o
  indice, exit 2, sem arquivo parcial deixado para tras.
- EC-3: argumentos extras depois do termo de busca → tratados como parte do termo (varios tokens,
  regra do E logico), nao como erro de uso.

## Operacao

### US-007: Rodada interrompida ou concorrente nao corrompe o indice

**As a** Cron, **I want** que a rodada seja tudo-ou-nada e que duas rodadas nao se atropelem,
**so that** o operador nunca busque num indice meio-escrito.

Acceptance criteria:

- AC-1: Dada uma rodada interrompida no meio (excecao, `SIGKILL`), quando eu busco depois, entao o
  indice responde com o estado da ultima rodada **completa**, sem arquivos parcialmente atualizados.
- AC-2: Dada uma rodada ja escrevendo no indice, quando uma segunda rodada comeca, entao ela espera
  ate o timeout e, se a primeira nao terminar, sai com exit 3 e mensagem de indice ocupado, sem
  gravar nada.
- AC-3: Dada uma rodada em andamento, quando eu busco no meio dela, entao recebo o resultado da
  rodada anterior imediatamente, sem bloquear e sem erro.

Edge cases:

- EC-1: arquivos `-wal`/`-shm` deixados por uma interrupcao → a rodada seguinte se recupera sozinha,
  e eles nunca entram no indice (comecam com `.`).
- EC-2: rodadas de cron mais frequentes que a duracao da rodada → a segunda sai com 3, de forma
  deterministica e repetivel, em vez de duas escritas simultaneas.
- EC-3: interrupcao na primeira indexacao (nao havia indice antes) → a busca seguinte se comporta
  como "sem indice" ou responde um indice vazio, nunca um indice parcial.
