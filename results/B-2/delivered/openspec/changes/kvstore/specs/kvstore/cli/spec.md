# Spec Delta

## Purpose

Expõe o store durável como um comando de linha componível — `python -m kvstore <diretorio> ...` — com
saída previsível e códigos de saída que distinguem chave ausente, erro de uso e falha de dados, para
que scripts do serviço possam ramificar sem interpretar texto.

## ADDED Requirements

### Requirement: Superfície de comandos

O CLI SHALL aceitar a forma `python -m kvstore <diretorio> <comando> [argumentos]` com exatamente
quatro comandos: `set <chave> <valor>`, `get <chave>`, `del <chave>` e `list`. O primeiro argumento
posicional é sempre o diretório do store.

#### Scenario: Gravar e ler de volta

- **WHEN** `python -m kvstore ./dados set foo bar` é executado e depois `python -m kvstore ./dados get foo`
- **THEN** o primeiro comando sai com código 0 e o segundo escreve `bar` em stdout e sai com código 0

#### Scenario: Comando desconhecido

- **WHEN** o comando informado não é um dos quatro
- **THEN** o CLI escreve a mensagem de uso em stderr e sai com código 2, sem tocar no diretório

#### Scenario: Número de argumentos errado

- **WHEN** `set` é chamado sem valor, ou `list` é chamado com um argumento extra
- **THEN** o CLI escreve a mensagem de uso em stderr e sai com código 2, sem tocar no diretório

### Requirement: `get` escreve o valor sem alterá-lo

O comando `get` SHALL escrever em stdout exatamente o texto gravado, sem acrescentar quebra de linha,
sem aspas e sem qualquer outro enfeite, para que o valor sobreviva a captura por substituição de
comando e a redirecionamento para arquivo. Nada além do valor vai para stdout.

#### Scenario: Valor volta byte a byte

- **WHEN** um valor com quebras de linha internas, espaços nas pontas e acentuação é gravado e depois
  lido com `get` redirecionado para um arquivo
- **THEN** o arquivo contém exatamente o texto original, sem byte a mais nem a menos

#### Scenario: Chave ausente

- **WHEN** `get` é chamado para uma chave que não existe
- **THEN** stdout fica vazio, uma mensagem de chave não encontrada vai para stderr, e o código de saída
  é 1

### Requirement: `set` aceita valor grande via stdin

Como os valores podem exceder o limite de tamanho da linha de comando do sistema, o CLI SHALL aceitar
`-` na posição do valor, significando que o valor deve ser lido integralmente de stdin.

#### Scenario: Valor lido de stdin

- **WHEN** `python -m kvstore ./dados set grande -` é executado com um texto de vários megabytes em stdin
- **THEN** o comando sai com código 0 e um `get grande` posterior devolve exatamente aquele texto

#### Scenario: Valor literal continua funcionando

- **WHEN** o valor é passado diretamente na linha de comando
- **THEN** ele é gravado como está, inclusive se for o texto de um único hífen escapado pelo usuário
  por outro meio que não a posição do valor

### Requirement: `del` é idempotente

O comando `del` SHALL sair com código 0 tanto quando a chave existia quanto quando não existia,
porque o resultado pretendido — a chave não estar mais lá — foi alcançado nos dois casos.

#### Scenario: Remover chave existente

- **WHEN** `del` é chamado para uma chave existente
- **THEN** o comando sai com código 0 e um `get` posterior para essa chave sai com código 1

#### Scenario: Remover chave inexistente

- **WHEN** `del` é chamado para uma chave que não existe
- **THEN** o comando sai com código 0 e nada é alterado no conjunto de chaves

### Requirement: `list` lista as chaves vivas, uma por linha, ordenadas

O comando `list` SHALL escrever em stdout apenas as chaves atualmente existentes, uma por linha, em
ordem lexicográfica estável, e nenhum valor. Chaves removidas não aparecem.

#### Scenario: Listagem ordenada

- **WHEN** as chaves `b`, `a` e `c` foram gravadas e `b` foi removida
- **THEN** stdout contém exatamente as linhas `a` e `c`, nessa ordem

#### Scenario: Store vazio

- **WHEN** `list` é chamado num diretório sem nenhuma chave, ou que ainda não existe
- **THEN** stdout fica vazio e o código de saída é 0

### Requirement: Códigos de saída distinguem os desfechos

O CLI SHALL usar códigos de saída estáveis para que scripts possam ramificar sem ler mensagens:
`0` sucesso, `1` chave não encontrada, `2` erro de uso ou de validação de entrada, `3` falha de dados
ou de entrada/saída (corrupção detectada, permissão negada, disco cheio). Mensagens de diagnóstico vão
sempre para stderr, nunca para stdout.

#### Scenario: Falha de gravação não é confundida com sucesso

- **WHEN** a gravação não pode ser concluída e sincronizada em disco, por exemplo por falta de espaço
  ou permissão
- **THEN** o comando sai com código 3 e a mensagem em stderr, e o chamador NÃO recebe sinal de sucesso
  para um dado que não foi persistido

#### Scenario: Chave inválida é erro de uso

- **WHEN** `set` é chamado com chave vazia ou com quebra de linha na chave
- **THEN** o comando sai com código 2, com mensagem em stderr, e nada é gravado

#### Scenario: Corrupção detectada é erro de dados

- **WHEN** uma leitura encontra corrupção que não pode ser atribuída a uma escrita interrompida
- **THEN** o comando sai com código 3 e a mensagem em stderr nomeia o diretório afetado
