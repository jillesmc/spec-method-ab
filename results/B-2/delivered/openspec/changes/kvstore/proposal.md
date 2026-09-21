# Proposal

## Why

O serviço guarda configuração, contadores e posição de processamento num único JSON reescrito por
inteiro a cada mudança. Como ele reinicia várias vezes por dia (deploy e OOM), uma reescrita
interrompida no meio já deixou o arquivo zerado e o estado foi perdido. O contrato que falta é
simples e absoluto: **quando a gravação responde "gravei", o dado tem que estar lá depois do
restart** — e o arquivo nunca pode ficar num estado que perde tudo.

Hoje não existe implementação: `kvstore/__init__.py` está vazio e o único teste (`tests/test_fumaca.py`)
apenas confirma que o pacote importa. Esta mudança define o comportamento do pacote antes de escrevê-lo.

## What Changes

- **Contrato de durabilidade explícito**: `set` e `del` só retornam sucesso depois de o dado estar
  sincronizado no disco. Enquanto não retornaram, não prometem nada.
- **Tudo-ou-nada por operação**: uma interrupção no meio de uma gravação deixa o valor anterior ou o
  novo, nunca um estado pela metade, e nunca o estado inteiro zerado — que é exatamente a falha que o
  JSON reescrito por inteiro produziu.
- **Recuperação automática no restart**: abrir o diretório depois de um `SIGKILL` funciona na primeira
  tentativa, sem comando de reparo nem limpeza manual de temporário.
- **Espaço proporcional ao estado vivo, não ao histórico**: o enunciado diz que as gravações crescem e
  ninguém limpa nada, então a recuperação de espaço tem de ser automática e interna.
- **Interface de linha de comando** `python -m kvstore <diretorio> set|get|del|list`, com formato de
  saída e códigos de saída definidos (chave ausente ≠ erro de uso ≠ falha de dados).
- **Acesso simultâneo seguro** entre invocações concorrentes do CLI sobre o mesmo diretório.
- Apenas biblioteca padrão do Python (3.11+). `make test` (`unittest discover`) continua sendo o
  portão de verificação.

Não há quebra de compatibilidade: não existe formato anterior gravado por este pacote. A migração do
JSON legado do serviço **não** faz parte desta mudança (ver Impact).

## Capabilities

### New Capabilities

- `kvstore/storage`: semântica do armazenamento chave-valor durável em um diretório — o contrato de
  durabilidade da gravação confirmada, o comportamento na volta de um restart abrupto, a recuperação
  de registro parcial, e a compactação que mantém o disco proporcional ao estado vivo.
- `kvstore/cli`: a superfície `python -m kvstore <diretorio> <comando>` — os quatro comandos, o que
  cada um escreve em stdout/stderr, e o código de saída de cada desfecho.

### Modified Capabilities

Nenhuma. O projeto ainda não tem specs (`openspec list --specs` retorna vazio).

## Impact

- **Código**: `kvstore/__init__.py` (API do store), `kvstore/__main__.py` (novo, o CLI), e testes novos
  em `tests/` — inclusive testes de crash que matam um subprocesso no meio da gravação.
- **Formato em disco**: o diretório passa a ter um layout definido pelo pacote e de uso exclusivo dele,
  como o enunciado garante. O mecanismo escolhido está em design.md.
- **Dependências**: nenhuma nova. Só stdlib (`sqlite3`, `os`, `argparse`, `unittest`).
- **Portabilidade**: alvo é Linux, num sistema de arquivos local. Sistema de arquivos em rede fica
  fora de escopo, pelo motivo registrado em design.md.
- **Fora de escopo**: migrar o JSON atual do serviço para o novo formato, API de rede, transações
  multi-chave, TTL, e qualquer limpeza/expiração de chaves.

## Assunções registradas

Decisões pequenas tomadas sem consultar, ajustáveis na revisão:

1. `get` escreve o valor **exatamente** como foi gravado, sem newline extra, para que o valor
   sobreviva a `$(...)` e a redirecionamento.
2. `del` de chave inexistente é sucesso (idempotente); `get` de chave inexistente sai com código 1.
3. `set <chave> -` lê o valor de stdin, porque o enunciado diz que os valores podem ser grandes e
   `ARG_MAX` limita o que cabe em argv.
4. Chaves e valores são texto UTF-8; chave vazia ou com `\n`/NUL é recusada (`list` é uma chave por linha).
