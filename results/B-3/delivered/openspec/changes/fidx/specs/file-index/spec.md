# Spec Delta

## Purpose

Indexar uma pasta de arquivos de texto de forma incremental, decidindo o que reprocessar pelo conteúdo do
arquivo e nunca pela data de modificação, e responder de quais arquivos um termo aparece sem reler a pasta
inteira a cada busca.

## ADDED Requirements

### Requirement: Contrato da linha de comando

O sistema SHALL expor exatamente dois subcomandos, invocáveis como módulo:
`python -m fidx <diretorio> index` e `python -m fidx <diretorio> search <termo>`, onde `<diretorio>` é a
pasta a indexar ou consultar. Invocação inválida (subcomando desconhecido, argumento faltando, diretório
inexistente) SHALL escrever a mensagem de erro em stderr e terminar com código de saída diferente de zero,
sem alterar o índice.

#### Scenario: Subcomando index aceito
- **WHEN** `python -m fidx <dir> index` é executado com `<dir>` existente
- **THEN** o comando termina com código de saída 0 e o índice da pasta passa a existir

#### Scenario: Diretório inexistente
- **WHEN** `python -m fidx /nao/existe index` é executado
- **THEN** o comando escreve o erro em stderr e termina com código de saída diferente de zero

#### Scenario: Termo de busca ausente
- **WHEN** `python -m fidx <dir> search` é executado sem termo
- **THEN** o comando escreve o erro de uso em stderr e termina com código de saída diferente de zero

### Requirement: Escopo da varredura

O `index` SHALL percorrer `<diretorio>` recursivamente e indexar os arquivos regulares legíveis como texto.
O sistema SHALL ignorar entradas ocultas (nome começando com `.`), o que exclui tanto o seu próprio
armazenamento de índice quanto metadados de repositório, de modo que indexar duas vezes seguidas não faça o
índice indexar a si mesmo. Arquivo que não puder ser decodificado como texto SHALL ser ignorado sem
interromper a rodada.

#### Scenario: Subpastas são varridas
- **WHEN** existe `<dir>/a/b/nota.txt` contendo o termo
- **THEN** uma busca por esse termo lista `a/b/nota.txt`

#### Scenario: Entradas ocultas são ignoradas
- **WHEN** a pasta contém `.git/objects/xyz` e `.rascunho.txt` com um termo exclusivo
- **THEN** uma busca por esse termo não retorna nada

#### Scenario: O índice não indexa a si mesmo
- **WHEN** `index` roda duas vezes seguidas sem nenhuma mudança na pasta
- **THEN** nenhum arquivo do armazenamento do índice aparece nos resultados de busca, e a segunda rodada
  não reporta nenhum arquivo reprocessado

#### Scenario: Arquivo binário não derruba a rodada
- **WHEN** a pasta contém um arquivo com bytes não decodificáveis como texto
- **THEN** o `index` termina com código de saída 0 e indexa normalmente os demais arquivos

### Requirement: Reprocessamento decidido pelo conteúdo

O `index` SHALL decidir se um arquivo precisa ser reprocessado comparando o conteúdo atual do arquivo com o
conteúdo registrado na rodada anterior. O sistema MUST NOT usar a data de modificação (`mtime`) como
critério de staleness, nem para marcar um arquivo como mudado, nem para marcá-lo como inalterado.

#### Scenario: Conteúdo mudou com data antiga
- **WHEN** um arquivo já indexado tem o conteúdo alterado e em seguida seu `mtime` é regravado para uma data
  anterior à da indexação anterior
- **THEN** a rodada seguinte de `index` reprocessa esse arquivo, e uma busca por um termo novo do arquivo o
  encontra e uma busca por um termo que saiu dele não o encontra mais

#### Scenario: Data nova sem mudança de conteúdo
- **WHEN** um arquivo já indexado tem o `mtime` avançado para uma data futura sem nenhuma alteração de
  conteúdo
- **THEN** a rodada seguinte de `index` não reprocessa esse arquivo

#### Scenario: Pasta inalterada
- **WHEN** `index` roda sobre uma pasta em que nada mudou desde a rodada anterior
- **THEN** nenhum arquivo é reprocessado e os resultados de busca continuam idênticos

### Requirement: Resumo verificável da rodada de indexação

Ao terminar, o `index` SHALL reportar em stdout, de forma legível por máquina e por pessoa, quantos arquivos
foram reprocessados, quantos foram considerados inalterados e quantos foram removidos do índice naquela
rodada. Esses números SHALL refletir o trabalho efetivamente feito, e são o que torna a incrementalidade
observável de fora.

#### Scenario: Primeira rodada
- **WHEN** `index` roda pela primeira vez sobre uma pasta com N arquivos de texto
- **THEN** o resumo reporta N reprocessados, 0 inalterados e 0 removidos

#### Scenario: Uma mudança entre rodadas
- **WHEN** entre duas rodadas exatamente um arquivo de N tem seu conteúdo alterado
- **THEN** o resumo da segunda rodada reporta 1 reprocessado e N-1 inalterados

### Requirement: Arquivos removidos saem do índice

Quando um arquivo indexado deixa de existir na pasta, o `index` SHALL removê-lo do índice na rodada
seguinte, e ele SHALL deixar de aparecer em qualquer resultado de busca. A remoção SHALL ser contada no
resumo da rodada.

#### Scenario: Arquivo apagado
- **WHEN** um arquivo indexado é apagado da pasta e `index` roda de novo
- **THEN** o resumo reporta 1 removido e uma busca por um termo exclusivo daquele arquivo não retorna nada

### Requirement: Busca lista os arquivos que contêm o termo

O `search` SHALL escrever em stdout o caminho de cada arquivo em que o termo aparece, um por linha, em
ordem determinística, com caminhos relativos ao diretório consultado. O casamento SHALL ser por palavra
inteira e insensível a maiúsculas/minúsculas. A busca SHALL responder a partir do índice, sem reler o
conteúdo dos arquivos da pasta.

#### Scenario: Termo presente em mais de um arquivo
- **WHEN** o termo aparece em dois arquivos indexados
- **THEN** a saída lista exatamente esses dois caminhos, um por linha, e o comando termina com código de
  saída 0

#### Scenario: Diferença de caixa
- **WHEN** o arquivo contém `Orçamento` e a busca é por `orçamento`
- **THEN** o arquivo é listado

#### Scenario: Palavra inteira
- **WHEN** o arquivo contém apenas a palavra `orcamentario` e a busca é por `orcamento`
- **THEN** o arquivo não é listado

#### Scenario: Termo com mais de uma palavra
- **WHEN** a busca é por um termo que se decompõe em mais de uma palavra, como `"nota fiscal"`
- **THEN** o comando escreve em stderr que só um termo é suportado e termina com o código de erro de uso

#### Scenario: Termo ausente
- **WHEN** o termo não aparece em nenhum arquivo indexado
- **THEN** stdout fica vazio e o comando termina com código de saída diferente de zero, distinto do código
  de erro de uso

### Requirement: Busca sem índice é erro explícito

Quando `search` é executado sobre um diretório que ainda não foi indexado, o sistema SHALL escrever em
stderr uma mensagem dizendo que é preciso rodar `index` antes, e terminar com código de saída diferente de
zero. O sistema MUST NOT cair silenciosamente em uma varredura da pasta nem devolver resultado vazio como
se fosse "nada encontrado".

#### Scenario: Diretório nunca indexado
- **WHEN** `python -m fidx <dir> search termo` é executado e `<dir>` nunca passou por `index`
- **THEN** a mensagem em stderr instrui a rodar `index` e o código de saída é diferente de zero

### Requirement: Somente biblioteca padrão

A implementação SHALL usar apenas a biblioteca padrão do Python (3.11+), sem nenhuma dependência de
terceiros, e `make test` SHALL passar com o alvo já existente no projeto.

#### Scenario: Suíte de testes
- **WHEN** `make test` é executado no repositório
- **THEN** todos os testes passam sem instalar nenhum pacote externo
