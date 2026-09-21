# task_06 — Fechamento

## Status

Implementada e verificada. `status: completed` em `task_06.md`.

## O que foi feito

- **6.1** — `README.md` reescrito: os quatro comandos (`set`/`get`/`del`/`list`), o uso
  de `-` para ler `set` de stdin, e a tabela de códigos de saída (`0`/`1`/`2`/`3`).
  Cada exemplo do README foi colado literalmente num shell contra um diretório
  temporário antes de escrever o arquivo — todos rodaram como documentado (saída,
  stdout/stderr e exit code conferidos um a um).
- **6.2** — `make test`: **verde, 40/40**, rodado 3x seguidas sem falha depois da
  correção abaixo (antes da correção, falhava de forma intermitente — ver "Bug real
  encontrado e corrigido").
- **6.3** — Resposta registrada em `design.md`, seção "Open Questions": a forma
  simples (`incremental_vacuum` a cada remoção) basta. Medido nesta máquina: 50
  remoções de valores de 200 KiB custam ~26 ms/op com `wal_checkpoint(TRUNCATE)` +
  `incremental_vacuum` acoplados, contra ~15 ms/op de um `DELETE`+`commit` isolado (o
  próprio fsync de `synchronous=FULL`) — o vacuum acrescenta ~11 ms/op, irrelevante
  para a carga que motiva a mudança (configuração, contadores, posição de
  processamento, não remoção em massa).

## Bug real encontrado e corrigido (fora do escopo textual de 6.1/6.3, mas bloqueava 6.2)

`tests.test_concorrencia_e_crescimento.TestLeituraConcorrenteComEscrita` (5.2,
já implementado por `task_05`) era **flakey**: falhava de duas formas diferentes em
execuções repetidas —
1. `AssertionError: [] is not true` (nenhuma leitura bem-sucedida durante toda a
   janela de escrita);
2. o **escritor** (`_escritor_continuo`, um `set` comum) morrendo com
   `sqlite3.OperationalError: database is locked`, apesar de `busy_timeout=5000`.

Isolei com um script de reprodução fora da suíte (loop de `get`/`list_keys` direto
contra um diretório enquanto um subprocesso regrava a mesma chave 300x): sem
mudança nenhuma no teste, medi chamadas individuais de `kvstore.get()` levando
até **~2.7 s** cada, e por eliminação (testei cada pragma de `_connect` isolado)
a causa é **`PRAGMA auto_vacuum = INCREMENTAL` reaplicado em toda abertura de
conexão**, inclusive nas de leitura. Mesmo virando no-op num banco não-vazio (D3
em design.md já dizia isso), a *forma de atribuição* do pragma gera contenção real
entre conexões concorrentes no mesmo arquivo — confirmado comparando com a *forma
de consulta* (`PRAGMA auto_vacuum` sem `=`), que é barata (~34 ms mesmo sob a
mesma carga) e nunca contende.

**Correção em `kvstore/__init__.py::_connect`**: consultar o valor efetivo primeiro
(`conn.execute("PRAGMA auto_vacuum").fetchone()[0]`) e só emitir a forma de
atribuição quando ainda não é `2`. Resultado: `make test` caiu de ~27 s (com
contenção) para ~12-13 s, e o teste 5.2 parou de falhar em 8 execuções isoladas
consecutivas + 3 rodadas completas de `make test`. Nenhuma mudança de
comportamento observável pelas specs — `auto_vacuum` continua sendo aplicado
corretamente em todo store novo (a condição `!= 2` é verdadeira quando a tabela
ainda não existe), só deixou de ser reemitido em toda reabertura de um store já
existente.

**Para tarefas futuras que tocarem `_connect`**: qualquer pragma de *atribuição*
(não de consulta) reaplicado em toda abertura de conexão é candidato a este mesmo
problema — meça com um script de contenção real (um escritor em loop + um leitor
em loop, dois processos/objetos de conexão distintos) antes de assumir que "é
idempotente, então é barato".

## Verificação executada

- Reprodução isolada do bug (fora da árvore de testes, script descartável): 8-15
  execuções antes da correção, falha visível em ~1 a cada 3-5 tentativas
  (`reads=0` ou `rc=1` no escritor); 0 falhas em 8 execuções depois da correção.
- `python3 -m unittest tests.test_concorrencia_e_crescimento -v`: 5 execuções
  seguidas, 3/3 testes OK em todas.
- `make test`: 3 execuções seguidas, 40/40 OK (~12-13 s cada).
- Exemplos do README: colados manualmente num shell contra `./dados_readme_check`
  (removido depois), todos com a saída e o exit code documentados.
- `openspec validate kvstore --strict`: **não executável nesta máquina** (mesmo
  bloqueio já registrado em `MEMORY.md` — `openspec` ausente de `PATH`, `npx` e
  `pip`). Comando que seria rodado: `openspec validate kvstore --strict`.

## Nota sobre os checkboxes de `openspec/changes/kvstore/tasks.md`

As seções 2, 3 e 5 desse arquivo (a "origem" citada em cada task) seguem
desmarcadas mesmo com `task_02`/`task_03`/`task_05` completas — confirmado que é
o padrão já estabelecido pelas tarefas anteriores (cada uma só marca os
checkboxes no seu próprio `.compozy/tasks/os-kvstore/task_0N.md`, que é a fonte
de verdade real da workflow). Segui o mesmo padrão: marquei os itens 6.1-6.3
apenas em `task_06.md`, sem tocar no arquivo de origem do openspec.
