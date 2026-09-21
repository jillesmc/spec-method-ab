# Spec Delta

## Purpose

Guarda pares chave-valor de texto num diretório em disco com uma promessa única e absoluta: uma
gravação confirmada sobrevive a qualquer interrupção posterior do processo — deploy, `SIGKILL` ou OOM —
e nenhuma operação normal pode deixar o estado inteiro irrecuperável.

## ADDED Requirements

### Requirement: Gravação confirmada é durável

O store SHALL persistir o registro em disco, incluindo a sincronização dos dados com o dispositivo
(não apenas com o cache do sistema operacional), **antes** de reportar sucesso ao chamador de uma
gravação ou de uma remoção. Uma operação que ainda não retornou sucesso NÃO tem garantia alguma.

#### Scenario: Valor gravado sobrevive a kill imediato

- **WHEN** uma gravação de `k`→`v` retorna sucesso e o processo é terminado com `SIGKILL` no instante
  seguinte, sem qualquer encerramento limpo
- **THEN** uma leitura de `k` num processo novo sobre o mesmo diretório devolve `v`

#### Scenario: Remoção confirmada sobrevive a kill imediato

- **WHEN** a remoção de `k` retorna sucesso e o processo é terminado com `SIGKILL` no instante seguinte
- **THEN** uma leitura de `k` num processo novo reporta chave ausente, e `k` não aparece na listagem

#### Scenario: Criação do diretório também é durável

- **WHEN** a primeira gravação num diretório novo retorna sucesso e a máquina perde energia em seguida
- **THEN** ao voltar, o diretório e o arquivo de dados existem e contêm essa gravação

### Requirement: Nenhuma operação normal destrói o estado acumulado

O store SHALL preservar continuamente em disco o estado já confirmado. Nenhuma operação de leitura,
gravação, remoção ou manutenção pode criar um instante em que um restart encontre o estado vazio ou
parcialmente apagado — qualquer que seja o ponto da interrupção.

#### Scenario: Interrupção durante gravação preserva o que já existia

- **WHEN** o store contém 100 chaves confirmadas e o processo é morto em qualquer instante durante uma
  gravação nova
- **THEN** um processo novo sobre o mesmo diretório lê as 100 chaves anteriores com os valores que
  tinham, sem perda

#### Scenario: Interrupção durante manutenção preserva o estado

- **WHEN** o processo é morto em qualquer instante durante a reorganização interna do arquivo
  (compactação)
- **THEN** um processo novo lê exatamente o mesmo conjunto de chaves e valores confirmados que existia
  antes da interrupção

### Requirement: Recuperação devolve exatamente o estado confirmado

Depois de uma interrupção abrupta, a primeira leitura SHALL devolver exatamente o estado das operações
confirmadas: nem menos (nada confirmado se perde) nem mais (uma operação que não chegou a ser
confirmada não aparece). Uma operação interrompida no meio é tudo-ou-nada: ela nunca deixa um valor
pela metade nem uma chave meio-removida. A recuperação SHALL ser automática, sem comando de reparo
manual.

#### Scenario: Gravação interrompida antes da confirmação não aparece

- **WHEN** o processo é morto durante uma gravação de `k`→`v_novo`, antes de ela retornar sucesso, e
  `k` valia `v_antigo`
- **THEN** a leitura seguinte devolve `v_antigo` ou `v_novo`, nunca um valor truncado, misturado ou
  vazio, e a listagem permanece consistente com o valor devolvido

#### Scenario: Nenhum reparo manual é necessário

- **WHEN** um processo novo abre um diretório deixado por uma interrupção abrupta
- **THEN** ele opera normalmente na primeira tentativa, sem exigir comando de reparo, limpeza de
  arquivo temporário ou intervenção do operador

#### Scenario: Corrupção real é reportada, não escondida

- **WHEN** os dados em disco estão corrompidos por causa externa (dano de mídia, alteração por
  terceiro) e não por uma escrita interrompida
- **THEN** a operação falha com erro explícito, e NÃO devolve silenciosamente um estado parcial como se
  fosse o estado real

### Requirement: Semântica de chave e valor

O store SHALL tratar uma chave como associada a no máximo um valor, com a última gravação confirmada
vencendo as anteriores, e uma remoção confirmada apagando a associação. Chaves e valores são texto
Unicode. O store SHALL aceitar valores grandes, na ordem de megabytes, preservando-os byte a byte.

#### Scenario: Última gravação vence

- **WHEN** `k` é gravada com `v1` e depois com `v2`, ambas confirmadas
- **THEN** a leitura de `k` devolve `v2`

#### Scenario: Regravar depois de remover

- **WHEN** `k` é gravada, removida, e gravada de novo com `v3`, todas as operações confirmadas
- **THEN** a leitura de `k` devolve `v3` e `k` aparece na listagem

#### Scenario: Valor grande sobrevive intacto

- **WHEN** um valor de vários megabytes, contendo quebras de linha e caracteres não-ASCII, é gravado e
  confirmado
- **THEN** a leitura posterior devolve exatamente o mesmo texto, sem truncamento, reencodificação ou
  alteração de espaços em branco

#### Scenario: Chave inválida é recusada

- **WHEN** uma gravação usa chave vazia, ou chave contendo quebra de linha ou byte NUL
- **THEN** a operação falha com erro de validação e nada é gravado em disco

### Requirement: Espaço em disco proporcional ao estado vivo

Como o número de gravações cresce indefinidamente e nada é limpo externamente, o store SHALL
reorganizar seu armazenamento de forma que o espaço ocupado permaneça proporcional ao estado vivo
(chaves atualmente existentes e seus valores), e não ao total histórico de operações. A reorganização
SHALL ser automática — não depende de comando ou rotina externa — e preserva integralmente o contrato
de durabilidade acima.

#### Scenario: Reescrita repetida da mesma chave não cresce sem limite

- **WHEN** a mesma chave é regravada dezenas de milhares de vezes
- **THEN** o espaço ocupado pelo diretório permanece da ordem de grandeza do valor vivo, e não do total
  gravado ao longo do tempo

#### Scenario: Chaves removidas liberam espaço

- **WHEN** muitas chaves são gravadas e depois removidas, todas confirmadas
- **THEN** o espaço ocupado pelo diretório volta a ser proporcional apenas às chaves restantes

#### Scenario: Estado permanece correto através da reorganização

- **WHEN** a reorganização ocorre durante uma sequência de operações
- **THEN** toda leitura antes, durante e depois devolve o mesmo estado confirmado, e nenhum valor
  confirmado é perdido

### Requirement: Operações concorrentes de processos distintos não se corrompem

O diretório é de uso exclusivo do pacote, mas pode ser acessado por mais de um processo ao mesmo tempo.
O store SHALL serializar as operações de escrita entre processos, de modo que registros concorrentes
não se intercalem e que nenhuma leitura observe um estado inconsistente.

#### Scenario: Gravações simultâneas de processos distintos

- **WHEN** vários processos gravam chaves diferentes ao mesmo tempo no mesmo diretório e todas as
  operações retornam sucesso
- **THEN** todas as chaves são legíveis com seus valores corretos, e nenhum registro fica corrompido

#### Scenario: Leitura durante reorganização

- **WHEN** um processo lê o store enquanto outro está reorganizando o armazenamento
- **THEN** a leitura devolve um estado confirmado consistente — o anterior ou o posterior à
  reorganização — e nunca falha por arquivo ausente ou meio-escrito

### Requirement: Diretório ausente ou vazio é um store vazio

O store SHALL tratar um diretório inexistente ou sem dados como um store vazio para operações de
leitura, sem erro, e SHALL criá-lo sob demanda na primeira gravação. Isso evita que o serviço falhe no
primeiro boot antes de qualquer gravação.

#### Scenario: Leitura antes da primeira gravação

- **WHEN** uma leitura ou listagem é feita sobre um diretório que ainda não existe
- **THEN** a listagem vem vazia e a leitura reporta chave ausente, sem erro e sem criar nada

#### Scenario: Primeira gravação cria o diretório

- **WHEN** uma gravação é feita sobre um caminho de diretório que ainda não existe
- **THEN** o diretório é criado e a gravação é confirmada com a mesma garantia de durabilidade
