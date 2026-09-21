# task_03 — Search

## Implementado

`fidx/__init__.py`:

- `IndexNotFoundError(Exception)`: erro dedicado para "diretorio sem indice".
- `search(directory, term)`:
  - `os.path.isfile(index_path(directory))` antes de qualquer coisa; se ausente, levanta
    `IndexNotFoundError` com mensagem citando o comando `index` (`python -m fidx
    <directory> index`) — task_04 (CLI) pode capturar esse tipo especifico e mapear para
    o exit code 2 de "operational failure" (design.md decisao 6) sem reinspecionar nada.
  - `tokens(term)` normaliza a query (mesma funcao usada na indexacao, design.md decisao
    4). Se o resultado for vazio (`term` so espaco/pontuacao), levanta `ValueError` — nao
    pedido literalmente pelos itens 3.1-3.3, mas e o requirement "Empty search term" do
    spec delta (`content-search/spec.md`); decidi resolver aqui, na funcao, para que
    task_04 so precise mapear tipos de excecao para exit codes, sem duplicar a logica de
    normalizacao vazia na CLI.
  - Conexao **read-only**: `sqlite3.connect(f"file:{quote(os.path.abspath(path))}?mode=ro",
    uri=True)` — `quote()` do `urllib.parse` para paths com caracteres especiais (nao
    testado com esses caracteres, mas evita quebrar a URI). Nunca chama `os.walk` nem
    escreve; confirmado manualmente que um `INSERT` nessa conexao levanta
    `sqlite3.OperationalError: attempt to write a readonly database`.
  - Para cada termo da query, `SELECT path FROM postings WHERE term = ?`, intersecao dos
    sets resultantes (AND entre termos quando a query normaliza para mais de um termo,
    exatamente o requirement 3.1). `sorted(matches)` no final — set garante path unico,
    `sorted` garante ordem deterministica.

`tests/test_search.py` (8 testes, todos verdes com `make test`):

- `TestSearchMatching`: two-of-three-files (3.1a), termo repetido no mesmo arquivo conta
  uma vez (3.1b), query com case diferente do arquivo (3.1c), query de duas palavras exige
  ambas (3.1d), termo sem match retorna lista vazia (implicito, nao um item mas cobre o
  caminho "sem match" que `search()` sozinha precisa suportar), query vazia levanta
  `ValueError`.
- `TestSearchIsReadOnly`: chmod 000 no arquivo indexado, `search()` ainda acha o match, e o
  `index_directory()` seguinte reporta `reprocessed == 0` (3.2, teste literal do item).
- `TestSearchMissingIndex`: diretorio nunca indexado -> `fidx.IndexNotFoundError` com
  "index" na mensagem (3.3, teste literal do item).

## Decisoes desta tarefa (nao estavam explicitas no design.md)

- `ValueError` para query vazia em vez de uma excecao dedicada: e o mesmo tipo que
  `argparse`/erros de uso naturalmente produzem, entao a CLI (task_04) pode tratar
  "invalid invocation" de forma uniforme.
- Optei por **nao** reescrever os testes de `test_refresh.py` que leem `postings`
  diretamente via sqlite3 (helper `paths_for_term`) para usar `fidx.search()` agora que
  ela existe — nao pedido por este item, e mudar esses testes e escopo da task_02, ja
  fechada. Deixei como estava.

## Para as proximas tarefas (task_04+)

- CLI (secao 4) deve capturar `fidx.IndexNotFoundError` e `ValueError` de `search()` e
  mapear ambos para o exit code de "usage/operational failure" (2, conforme design.md
  decisao 6); "sem match" (lista vazia, sem excecao) mapeia para exit code 1.
- `search()` abre e fecha sua propria conexao (como `index_directory()`) — task_04 so
  precisa chamar a funcao e imprimir os paths, um por linha, sem gerenciar conexao.

## Bloqueio conhecido (nao desta tarefa, mas repetido em todas)

`openspec` CLI nao esta instalado nesta maquina (`which openspec` falha, confirmado de
novo nesta tarefa). `openspec validate fidx --strict` nao pode ser executado; ver nota em
`MEMORY.md`.
