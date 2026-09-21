# Tasks

Referência: `specs/kvstore/storage/spec.md` e `specs/kvstore/cli/spec.md` dizem **o que**;
`design.md` diz **como**. Portão final em todas as etapas: `make test` verde.

## 1. Abertura do store e pragmas de durabilidade

- [x] 1.1 Implementar a abertura do store em `kvstore/__init__.py`: cria o diretório sob demanda,
      abre/cria `kvstore.sqlite3`, aplica `auto_vacuum=INCREMENTAL` **antes** do schema, e cria a
      tabela `kv(key TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL)` — verificar com teste que um
      store novo tem a tabela e reporta `pragma auto_vacuum == 2` (D3)
- [x] 1.2 Aplicar `journal_mode=WAL`, `synchronous=FULL`, `busy_timeout` e `journal_size_limit` na
      abertura — verificar com teste que lê os pragmas **efetivos** em tempo de execução e falha se
      `synchronous` não for `2` ou `journal_mode` não for `wal` (D2; é o pragma errado que apaga a
      garantia em silêncio)
- [x] 1.3 Tornar a abertura idempotente e segura em store já existente — verificar com teste que abrir
      duas vezes seguidas não altera dados nem recria o schema

## 2. Operações do store

- [x] 2.1 Implementar `set`: upsert por chave, retorno só depois do `COMMIT` — verificar com teste de
      última-gravação-vence (`v1` depois `v2` devolve `v2`)
- [x] 2.2 Implementar `get` e `delete`, com `delete` idempotente — verificar com testes de chave
      ausente, de remover-e-reler, e de gravar-remover-regravar devolvendo o valor novo
- [x] 2.3 Implementar `list_keys` devolvendo só chaves vivas em ordem lexicográfica — verificar com
      teste que grava `b`, `a`, `c`, remove `b`, e exige exatamente `["a", "c"]`
- [x] 2.4 Validar a chave na fronteira de entrada (vazia, com `\n`, com `NUL`) levantando erro próprio
      antes de qualquer escrita — verificar com teste que a recusa acontece **e** que o disco não mudou
- [x] 2.5 Tratar diretório inexistente como store vazio em `get`/`list_keys`, sem criar nada —
      verificar com teste que `list_keys` vem vazio e nenhum arquivo é criado
- [x] 2.6 Disparar `incremental_vacuum` após remoção — verificar com teste que grava muitas chaves
      grandes, remove todas, e exige que o tamanho do diretório caia para a ordem de grandeza do vazio
- [x] 2.7 Cobrir fidelidade de valor: texto de vários MB, com quebras de linha, acentuação, espaços nas
      pontas e `NUL` embutido — verificar com teste de ida e volta exigindo igualdade exata (D5)

## 3. Linha de comando

- [x] 3.1 Criar `kvstore/__main__.py` com `argparse`: diretório posicional e os subcomandos
      `set`/`get`/`del`/`list` — verificar com teste que `python -m kvstore <dir> set foo bar` seguido
      de `get foo` imprime `bar` e sai com 0
- [x] 3.2 Escrever o valor de `get` como bytes em `sys.stdout.buffer`, sem newline acrescentado —
      verificar com teste que redireciona a saída e compara byte a byte com o valor gravado (D7)
- [x] 3.3 Aceitar `-` na posição do valor de `set` lendo stdin por inteiro — verificar com teste de
      subprocesso que envia vários MB por stdin e relê com `get`
- [x] 3.4 Mapear os desfechos para os códigos de saída `0`/`1`/`2`/`3`, com toda mensagem em stderr e
      stdout limpo — verificar com testes de subprocesso para: sucesso, chave ausente (1), uso inválido
      e chave inválida (2), e falha de E/S como diretório sem permissão de escrita (3)
- [x] 3.5 Confirmar que `del` de chave inexistente sai 0 e que `list` em store vazio sai 0 com stdout
      vazio — verificar com testes de subprocesso

## 4. Testes de falha abrupta (o núcleo da mudança)

- [x] 4.1 Escrever o auxiliar de teste que roda uma gravação num subprocesso e o mata com `SIGKILL`,
      sem encerramento limpo — verificar que o auxiliar de fato mata (código de saída `-9`) e não
      depende de `sleep` para sincronizar
- [x] 4.2 Teste: `set` confirmado seguido de `SIGKILL` imediato — exigir que um processo novo leia o
      valor gravado (requisito "Gravação confirmada é durável")
- [x] 4.3 Teste: `del` confirmado seguido de `SIGKILL` imediato — exigir que a chave continue ausente
      no processo novo
- [x] 4.4 Teste: `SIGKILL` **durante** a gravação, em vários instantes diferentes, sobre uma chave que
      já tinha valor — exigir que a leitura seguinte devolva o valor antigo **ou** o novo, nunca lixo,
      valor truncado ou vazio (requisito "Recuperação devolve exatamente o estado confirmado")
- [x] 4.5 Teste: store com muitas chaves confirmadas, `SIGKILL` no meio de uma gravação nova — exigir
      que todas as chaves anteriores continuem legíveis com os valores corretos (requisito "Nenhuma
      operação normal destrói o estado acumulado")
- [x] 4.6 Teste: abrir um diretório deixado por `SIGKILL` (com `-wal` pendente) — exigir que a primeira
      operação funcione sem reparo manual e sem remoção de arquivo temporário

## 5. Concorrência e crescimento

- [x] 5.1 Teste: N processos gravando chaves diferentes ao mesmo tempo no mesmo diretório — exigir que
      todas as gravações confirmadas sejam legíveis e nenhuma falhe por contenção (`busy_timeout`, D4)
- [x] 5.2 Teste: leitura concorrente com escrita — exigir que a leitura devolva um estado consistente e
      nunca erre por arquivo ausente ou meio-escrito
- [x] 5.3 Teste de crescimento: regravar a mesma chave milhares de vezes — exigir que o tamanho do
      diretório fique na ordem de grandeza do valor vivo, não do total gravado (requisito "Espaço
      proporcional ao estado vivo"); manter a contagem baixa o bastante para o teste rodar em segundos

## 6. Fechamento

- [x] 6.1 Atualizar `README.md` com os quatro comandos, os códigos de saída e o uso de `-` para stdin —
      verificar copiando cada exemplo do README para um shell e conferindo que roda como documentado
- [x] 6.2 Rodar `make test` com a suíte completa e confirmar tudo verde, inclusive `tests/test_fumaca.py`
      que já existia
- [x] 6.3 Registrar a resposta da questão em aberto de `design.md` (cadência do `incremental_vacuum`)
      com o número medido na tarefa 2.6, ou confirmar que a forma simples basta
