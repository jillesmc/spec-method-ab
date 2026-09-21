# User Stories: kvstore

Catálogo canônico de comportamento do `kvstore`. Companheiro de `_spec.md`; consumido por
`_spec.md` Part II (mapeamento de componentes) e `_tests.md` (matriz de cobertura).

Títulos de seção em inglês seguem o template; o conteúdo acompanha a língua do repositório.

## Personas

- **Serviço** — o processo que guarda configuração, contadores e posição de processamento. Reinicia
  várias vezes por dia (deploy e OOM). Escreve com frequência, lê no boot. Precisa que "gravei"
  signifique "está no disco".
- **Desenvolvedor integrador** — quem embute o `kvstore` no serviço. Importa o pacote em processo e
  quer uma API pequena, sem cerimônia de configuração.
- **Operador** — quem opera o serviço em produção. Inspeciona e corrige estado pela linha de comando,
  em geral durante um incidente, com o serviço parado ou rodando.

## Story Index

| ID     | Feature Area   | Persona      | Story                                                      |
| ------ | -------------- | ------------ | ---------------------------------------------------------- |
| US-001 | Escrita        | Operador     | Gravar uma chave pela linha de comando                     |
| US-002 | Leitura        | Operador     | Ler o valor de uma chave                                   |
| US-003 | Escrita        | Operador     | Apagar uma chave                                           |
| US-004 | Leitura        | Operador     | Listar as chaves existentes                                |
| US-005 | Escrita        | Operador     | Gravar um valor grande sem esbarrar no limite de argumentos |
| US-006 | API            | Integrador   | Usar o armazenamento em processo, sem abrir subprocesso     |
| US-007 | Durabilidade   | Serviço      | Não perder nada quando o processo morre                     |
| US-008 | Operação       | Operador     | Crescer indefinidamente sem rotina de manutenção            |
| US-009 | Operação       | Operador     | Primeira execução em um diretório que ainda não existe      |
| US-010 | Concorrência   | Serviço      | Dois processos no mesmo diretório ao mesmo tempo            |

## Escrita

### US-001: Gravar uma chave pela linha de comando

**As a** Operador, **I want** gravar um valor em uma chave com um comando, **so that** eu consiga
corrigir estado do serviço sem escrever código.

Acceptance criteria:

- AC-1: Dado um diretório de dados, quando executo `python -m kvstore <dir> set posicao 1042`, então o
  comando termina com código 0 e não imprime nada em stdout.
- AC-2: Dado que `posicao` já vale `1042`, quando executo `set posicao 2000`, então o valor passa a ser
  `2000` e o antigo não é recuperável (sobrescrita, não versionamento).
- AC-3: Dado que o comando `set` terminou com código 0, quando qualquer processo abre o mesmo diretório
  depois, então lê o valor gravado — independente de o processo que gravou ter encerrado bem ou não.

Edge cases:

- EC-1: chave vazia (`set "" x`) → rejeitada com mensagem de uso em stderr e código 2; nada é gravado.
- EC-2: valor vazio (`set k ""`) → aceito; `get k` devolve string vazia e código 0, que é diferente de
  chave ausente (código 1).
- EC-3: chave com espaços, acentos, `/`, `..` ou newline → gravada e lida literalmente; nenhum caractere
  tem significado especial, porque a chave nunca vira nome de arquivo.
- EC-4: diretório de dados sem permissão de escrita → erro de armazenamento em stderr e código 3;
  nenhum arquivo parcial fica para trás.
- EC-5: disco cheio no meio da gravação → `set` falha com código 3 e o valor anterior da chave continua
  íntegro e legível.

### US-003: Apagar uma chave

**As a** Operador, **I want** remover uma chave, **so that** eu consiga limpar estado inválido que está
travando o serviço.

Acceptance criteria:

- AC-1: Dado que `posicao` existe, quando executo `del posicao`, então o comando termina com 0 e
  `get posicao` passa a terminar com 1.
- AC-2: Dado que a remoção terminou com 0, quando o processo é morto logo em seguida, então após o
  restart a chave continua ausente — a remoção é tão durável quanto a gravação.

Edge cases:

- EC-1: `del` de chave que não existe → termina com 0 e não imprime nada; a operação é idempotente
  porque a pós-condição desejada (chave ausente) já vale. Ver Assumptions em `_spec.md`.
- EC-2: `del` repetido duas vezes seguidas → mesmo resultado da primeira, código 0 nas duas.

### US-005: Gravar um valor grande sem esbarrar no limite de argumentos

**As a** Operador, **I want** passar o valor pela entrada padrão, **so that** eu consiga gravar
conteúdos maiores que o limite de tamanho de argumentos do sistema operacional.

Acceptance criteria:

- AC-1: Dado um arquivo de 10 MB, quando executo `python -m kvstore <dir> set blob - < arquivo.txt`,
  então o conteúdo inteiro é gravado e `get blob` devolve os mesmos bytes.
- AC-2: Dado `set k -`, quando stdin está vazio, então a chave recebe string vazia e o comando termina
  com 0.

Edge cases:

- EC-1: valor literal `-` desejado → `set k -` sempre lê stdin; para gravar o texto `-` o operador usa
  `printf -- - | python -m kvstore <dir> set k -`. Comportamento documentado, não ambíguo em silêncio.
- EC-2: `set k - valor_extra` (stdin e argumento juntos) → rejeitado com código 2, para não gravar
  silenciosamente a fonte errada.
- EC-3: stdin com bytes que não são UTF-8 válido → rejeitado com código 2 e mensagem nomeando a posição
  inválida; o armazenamento é de texto.

## Leitura

### US-002: Ler o valor de uma chave

**As a** Operador, **I want** ler o valor de uma chave, **so that** eu consiga conferir o estado do
serviço durante um incidente.

Acceptance criteria:

- AC-1: Dado que `posicao` vale `1042`, quando executo `get posicao`, então stdout recebe exatamente
  `1042`, sem newline adicionado, e o código de saída é 0.
- AC-2: Dado que a chave não existe, quando executo `get ausente`, então stdout fica vazio, stderr
  recebe `kvstore: chave nao encontrada: ausente` e o código de saída é 1.

Edge cases:

- EC-1: valor que termina em newline → devolvido com o newline, sem nada a mais; `kvstore get k > f`
  reproduz o arquivo original byte a byte.
- EC-2: valor de vários MB → escrito inteiro em stdout; o pipe do leitor não é truncado.
- EC-3: `get` em diretório que nunca recebeu escrita → código 1 (chave não encontrada), não erro de
  armazenamento.

### US-004: Listar as chaves existentes

**As a** Operador, **I want** ver todas as chaves, **so that** eu consiga descobrir o que o serviço
guarda sem conhecer os nomes de antemão.

Acceptance criteria:

- AC-1: Dado `config`, `posicao` e `contador` gravados, quando executo `list`, então stdout recebe as
  três chaves, uma por linha, em ordem crescente, e o código de saída é 0.
- AC-2: Dado um diretório sem nenhuma chave, quando executo `list`, então stdout fica vazio e o código
  de saída é 0 — vazio não é erro.

Edge cases:

- EC-1: chave contendo newline → ainda sai uma "linha" por chave, o que torna a saída ambígua para
  quem faz parsing; limitação documentada em `_spec.md` Assumptions, não corrigida com escaping.
- EC-2: 100.000 chaves → lista inteira sai sem carregar tudo em memória de uma vez e sem truncar.
- EC-3: `list` com stdout fechado pelo leitor (`| head -1`) → termina sem stack trace de `BrokenPipeError`.

## API

### US-006: Usar o armazenamento em processo

**As a** Desenvolvedor integrador, **I want** importar o pacote e gravar direto, **so that** o serviço
não precise abrir um subprocesso a cada contador atualizado.

Acceptance criteria:

- AC-1: Dado `from kvstore import Store`, quando faço `with Store(dir) as s: s.set("k", "v")`, então o
  valor fica gravado com a mesma garantia de durabilidade da linha de comando.
- AC-2: Dado um `Store` aberto, quando chamo `s.get("ausente")`, então recebo `None` — ausência não é
  exceção.
- AC-3: Dado um `Store` aberto, quando chamo `s.delete("k")`, então recebo `True` se a chave existia e
  `False` se não existia, e as duas chamadas são bem-sucedidas.

Edge cases:

- EC-1: `Store` usado depois de `close()` → levanta erro claro, não grava em silêncio.
- EC-2: mesmo `Store` reaproveitado por milhares de escritas seguidas → funciona sem reabrir conexão e
  sem vazar descritores de arquivo.
- EC-3: chave que não é `str` (por exemplo `int`) → levanta `TypeError` na fronteira da API, em vez de
  gravar um valor convertido por acidente.

## Durabilidade

### US-007: Não perder nada quando o processo morre

**As a** Serviço, **I want** que toda gravação confirmada sobreviva a uma morte abrupta, **so that** um
OOM ou um deploy no meio de uma escrita não me faça voltar com estado zerado.

Acceptance criteria:

- AC-1: Dado que uma gravação retornou sucesso, quando o processo é morto com `SIGKILL` no instante
  seguinte, então uma leitura posterior devolve o valor gravado.
- AC-2: Dado que o processo é morto **durante** uma gravação, quando o diretório é reaberto, então a
  chave tem ou o valor antigo ou o novo, nunca um valor parcial, e nenhuma outra chave é afetada.
- AC-3: Dado um diretório com muitas chaves, quando o processo é morto a qualquer momento, então o
  armazenamento continua legível — nunca volta vazio.

Edge cases:

- EC-1: morte abrupta sem `close()` e sem `atexit` (`os._exit`) → dados confirmados permanecem; a
  durabilidade não depende de encerramento limpo.
- EC-2: queda de energia da máquina → gravações confirmadas permanecem, salvo hardware que mente sobre
  `fsync`; essa ressalva é explícita e não é testável em espaço de usuário.
- EC-3: arquivos auxiliares de journal apagados por terceiro entre execuções → fora de escopo; o
  diretório é do serviço, conforme enunciado.

## Operação

### US-008: Crescer indefinidamente sem rotina de manutenção

**As a** Operador, **I want** que ninguém precise rodar compactação, **so that** o armazenamento não
vire mais uma tarefa que alguém esquece de fazer.

Acceptance criteria:

- AC-1: Dado 50.000 gravações na **mesma** chave, quando olho o tamanho em disco, então ele fica na
  ordem do valor vivo, não da soma de todas as gravações.
- AC-2: Dado esse mesmo volume, quando executo `get` e `list`, então o tempo de resposta não degrada em
  função do número de gravações passadas.
- AC-3: Dado que nenhum comando de manutenção é documentado, quando o operador lê o README, então não
  encontra nenhuma rotina periódica a agendar.

Edge cases:

- EC-1: apagar uma chave muito grande → o arquivo em disco não encolhe; o espaço é reaproveitado pelas
  gravações seguintes. Limitação documentada, sem `VACUUM`.
- EC-2: 100.000 chaves com valores grandes → leitura de uma chave continua barata, sem varrer o resto.

### US-009: Primeira execução em diretório inexistente

**As a** Operador, **I want** apontar para um diretório que ainda não existe, **so that** eu não
precise de um passo de preparação antes do primeiro uso.

Acceptance criteria:

- AC-1: Dado um caminho inexistente, quando executo `set k v`, então o diretório é criado e a gravação
  acontece, com código 0.
- AC-2: Dado um caminho inexistente, quando executo `list`, então a saída é vazia com código 0.

Edge cases:

- EC-1: caminho existe mas é um arquivo comum, não um diretório → erro de armazenamento com código 3 e
  mensagem nomeando o caminho.
- EC-2: diretório-pai sem permissão de criação → código 3, sem deixar diretório pela metade.

### US-010: Dois processos no mesmo diretório ao mesmo tempo

**As a** Serviço, **I want** que uma execução da linha de comando durante o meu funcionamento não
corrompa nem falhe, **so that** o operador possa inspecionar estado sem me derrubar.

Acceptance criteria:

- AC-1: Dado o serviço gravando, quando o operador executa `get` em paralelo, então a leitura devolve
  um estado consistente e termina com 0.
- AC-2: Dados dois processos gravando chaves diferentes ao mesmo tempo, quando ambos terminam com 0,
  então as duas chaves estão gravadas.

Edge cases:

- EC-1: dois escritores disputando a mesma chave → um espera o outro e ambos terminam com 0; o último
  a confirmar vence, sem erro de "banco travado" imediato.
- EC-2: escritor que segura a escrita por mais tempo que a espera configurada → o segundo falha com
  código 3 e mensagem de contenção, em vez de travar para sempre.
