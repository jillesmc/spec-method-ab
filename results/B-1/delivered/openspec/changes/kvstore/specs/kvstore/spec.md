# kvstore

## ADDED Requirements

### Requirement: Durabilidade da gravação confirmada

O sistema DEVE retornar sucesso de `set` ou `del` somente depois que a mudança estiver persistida
em disco, incluindo `fsync` do conteúdo do arquivo e `fsync` da entrada de diretório. Depois de um
sucesso, o valor DEVE estar legível por um processo novo, independentemente de o processo que
gravou ter terminado de forma limpa.

#### Scenario: valor sobrevive ao término do processo

- **WHEN** um processo executa `set chave valor`, recebe código de saída 0, e termina
- **THEN** um processo novo executando `get chave` no mesmo diretório escreve `valor` e sai com 0

#### Scenario: fsync do arquivo acontece antes da publicação do nome

- **WHEN** um `set` é executado
- **THEN** ocorre `fsync` no descritor do arquivo temporário **antes** da chamada que o renomeia
  para o nome definitivo

#### Scenario: fsync do diretório acontece antes de responder sucesso

- **WHEN** um `set` ou um `del` é executado
- **THEN** ocorre `fsync` no descritor do diretório do store **depois** da renomeação (ou da
  remoção) e **antes** de a operação retornar sucesso

### Requirement: Atomicidade por chave

O sistema DEVE publicar o valor de uma chave de forma atômica, por renomeação dentro do mesmo
diretório. Uma interrupção em qualquer ponto da gravação DEVE deixar visível o valor anterior
íntegro ou o valor novo íntegro, nunca um valor parcial, truncado ou vazio.

#### Scenario: processo morto no meio de uma gravação preserva o valor anterior

- **GIVEN** a chave `pos` contém `100`
- **WHEN** um processo começa `set pos <valor novo>` e recebe `SIGKILL` depois de escrever o
  arquivo temporário e antes da renomeação
- **THEN** `get pos` num processo novo escreve `100` e sai com 0
- **AND** `list` não expõe nenhuma chave além das gravadas com sucesso

#### Scenario: gravação nunca trunca o valor existente

- **WHEN** uma gravação falha por qualquer erro de E/S
- **THEN** o arquivo definitivo da chave não foi aberto em modo de truncar em nenhum momento

### Requirement: Custo de gravação independente do tamanho do store

O sistema DEVE gravar uma chave sem ler nem reescrever os dados das outras chaves. O custo de um
`set` DEVE ser proporcional ao tamanho do valor gravado, não ao número de chaves nem ao tamanho
total do store. O sistema NÃO DEVE exigir compactação, coleta de lixo ou qualquer manutenção
periódica para continuar funcionando conforme o número de chaves e de gravações cresce.

#### Scenario: gravar uma chave não toca no arquivo de outra

- **GIVEN** as chaves `a` e `b` estão gravadas
- **WHEN** `set a <novo valor>` é executado
- **THEN** o conteúdo e o tempo de modificação do arquivo correspondente a `b` permanecem
  inalterados

#### Scenario: leitura não depende do histórico de gravações

- **GIVEN** a chave `c` recebeu 1.000 gravações sucessivas
- **WHEN** `get c` é executado
- **THEN** o valor da última gravação é escrito, e a operação lê apenas o arquivo dessa chave

### Requirement: Linha de comando

O sistema DEVE oferecer a interface `python -m kvstore <diretorio> <comando> [argumentos]` com os
comandos `set`, `get`, `del` e `list`, usando estes códigos de saída: `0` sucesso, `1` chave não
encontrada, `2` uso inválido ou erro de E/S. Mensagens de erro DEVEM ir para stderr; apenas dados
pedidos DEVEM ir para stdout.

#### Scenario: set grava e get devolve exatamente os mesmos bytes

- **WHEN** `set chave valor` e depois `get chave` são executados
- **THEN** stdout de `get` contém exatamente `valor`, sem newline acrescentada, e o código de
  saída é 0

#### Scenario: get de chave ausente

- **WHEN** `get inexistente` é executado
- **THEN** nada é escrito em stdout e o código de saída é 1

#### Scenario: del remove e é reportado

- **GIVEN** a chave `x` existe
- **WHEN** `del x` é executado
- **THEN** o código de saída é 0 e `get x` passa a sair com 1

#### Scenario: del de chave ausente

- **WHEN** `del inexistente` é executado
- **THEN** o código de saída é 1

#### Scenario: list enumera as chaves em ordem

- **GIVEN** as chaves `b`, `a` e `c` existem
- **WHEN** `list` é executado
- **THEN** stdout contém `a`, `b`, `c`, uma por linha, em ordem crescente, e nada mais

#### Scenario: comando desconhecido ou argumentos faltando

- **WHEN** um comando inexistente ou uma contagem errada de argumentos é passada
- **THEN** uma mensagem de uso vai para stderr e o código de saída é 2

### Requirement: Valores de texto grandes

O sistema DEVE aceitar valores de texto arbitrários, incluindo o valor vazio e caracteres
não-ASCII, codificados em UTF-8. Quando o argumento de valor for omitido em `set`, o valor DEVE
ser lido de stdin. A escrita e a leitura de valores DEVEM ser feitas em blocos, sem exigir que o
valor inteiro esteja em memória de uma só vez.

#### Scenario: valor grande vindo de stdin

- **WHEN** `set chave` é executado com 10 MiB de texto em stdin
- **THEN** o código de saída é 0 e `get chave` reproduz os mesmos 10 MiB byte a byte

#### Scenario: valor vazio é um valor

- **WHEN** `set chave ""` é executado
- **THEN** `get chave` sai com 0 e não escreve nada em stdout

#### Scenario: texto não-ASCII faz ida e volta

- **WHEN** um valor com acentos e emoji é gravado
- **THEN** `get` reproduz exatamente o mesmo texto

### Requirement: Validação de chave

O sistema DEVE rejeitar chave vazia, chave contendo caracteres de controle (`\n`, `\r`, `\0`) e
chave cuja forma codificada ultrapasse o limite de nome de arquivo, com mensagem em stderr e
código de saída 2, sem modificar o store.

#### Scenario: chave com newline é rejeitada

- **WHEN** `set` recebe uma chave contendo `\n`
- **THEN** o código de saída é 2, stderr explica o motivo e nenhum arquivo é criado

#### Scenario: chave longa demais é rejeitada explicitamente

- **WHEN** `set` recebe uma chave cuja forma codificada excede o limite de nome de arquivo
- **THEN** o código de saída é 2 e a mensagem indica o limite, sem truncar a chave

#### Scenario: chave com caracteres especiais de caminho é preservada

- **WHEN** a chave `pos/topico-1` é gravada
- **THEN** `get pos/topico-1` devolve o valor, `list` mostra `pos/topico-1`, e nenhum
  subdiretório é criado

### Requirement: Store ausente ou vazio

O sistema DEVE criar o diretório do store na primeira gravação, garantindo que a própria criação
esteja persistida. Operações de leitura sobre um diretório inexistente DEVEM se comportar como
store vazio, sem criar nada.

#### Scenario: primeira gravação cria o diretório

- **GIVEN** o diretório não existe
- **WHEN** `set chave valor` é executado
- **THEN** o diretório é criado, o código de saída é 0 e `get chave` num processo novo devolve o
  valor

#### Scenario: leitura em diretório inexistente

- **WHEN** `list` é executado sobre um diretório inexistente
- **THEN** stdout fica vazio, o código de saída é 0 e o diretório continua inexistente

#### Scenario: get em diretório inexistente

- **WHEN** `get chave` é executado sobre um diretório inexistente
- **THEN** o código de saída é 1 e o diretório continua inexistente

### Requirement: Layout em disco inspecionável

O sistema DEVE guardar cada chave num arquivo próprio, nomeado de forma reversível a partir da
chave, dentro do diretório do store. Arquivos que não correspondam a esse padrão de nome (por
exemplo, temporários deixados por uma interrupção) DEVEM ser ignorados por todas as operações.

#### Scenario: temporário órfão não vira chave

- **GIVEN** um arquivo temporário sobrou de uma gravação interrompida
- **WHEN** `list` é executado
- **THEN** o temporário não aparece na saída e nenhuma operação falha por causa dele

#### Scenario: nome do arquivo permite identificar a chave

- **WHEN** a chave `foo` é gravada
- **THEN** o diretório contém um arquivo cujo nome deriva de `foo` de forma reversível, e cujo
  conteúdo é exatamente o valor gravado
