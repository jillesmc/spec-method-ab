# task_04 — CLI

## Implementado

`fidx/__main__.py` (novo arquivo):

- `build_parser()`: `argparse.ArgumentParser`, positional `directory`, subparsers
  (`dest="command", required=True`) com `index` (sem argumentos) e `search` (positional
  `term`). `required=True` faz o `argparse` sair com codigo 2 (usage) sozinho quando o
  sub-comando falta — nao precisei tratar esse caso a mao.
- `main(argv=None)`: parseia, depois `os.path.isdir(args.directory)` **antes** de
  despachar para `index`/`search` — checagem explicita porque `index_directory()` faz
  `os.makedirs(..., exist_ok=True)` no `.fidx/`, que cria silenciosamente os diretorios
  pais ausentes (inclusive um `directory` inexistente/typo). Sem essa checagem um path
  errado "funcionaria" (seen=0, reprocessed=0) em vez de reportar erro — decidido aqui,
  nao pedido explicitamente pelo item mas exigido pela design.md decisao 6 ("2 para
  diretorio ausente").
- `run_index(directory)`: chama `fidx.index_directory`, imprime
  `seen={n} reprocessed={n} removed={n}` em stdout (formato proprio, nao especificado
  pelo spec — so exige "the counts"; virgula-separado K=V para ficar grep-avel), retorna
  0.
- `run_search(directory, term)`: chama `fidx.search`; `except (fidx.IndexNotFoundError,
  ValueError)` cobre os dois casos que task_03 deixou documentados (indice ausente,
  query vazia apos normalizacao) e imprime `fidx: {exc}` em **stderr**, retorna 2. Sem
  excecao: imprime cada path em stdout (um por linha), retorna 0 se `matches` nao-vazio
  senao 1.
- `if __name__ == "__main__": sys.exit(main())` — padrao stdlib para expor exit code ao
  shell.

`tests/test_cli.py` (novo, 8 testes, subprocess contra `python -m fidx`):

- `run_cli(*args)`: helper que roda `[sys.executable, "-m", "fidx", *args]` com
  `cwd=REPO_ROOT` (raiz do repo, dois niveis acima de `tests/test_cli.py`) — precisa do
  cwd certo para que `import fidx` resolva dentro do subprocess sem depender de
  `PYTHONPATH` do ambiente de teste.
- `TestIndexAndSearchThroughSubprocess`: index + search end-to-end, paths esperados em
  `stdout.splitlines()` (4.1, teste literal do item).
- `TestIndexReportsRefreshCounts`: dois arquivos indexados, um alterado, segunda rodada
  de `index` — assert `seen=2`, `reprocessed=1`, `removed=0` presentes no stdout (4.2).
- `TestExitCodes` (4.3, um teste por cenario do spec delta):
  - match -> exit 0;
  - sem match -> exit 1, stdout vazio;
  - diretorio ausente -> exit 2, stdout vazio, stderr nao-vazio;
  - indice ausente (diretorio existe, nunca indexado) -> exit 2, stdout vazio, stderr
    contem "index" (mesma mensagem que `IndexNotFoundError` ja carrega, task_03);
  - query vazia (`"   "`) -> exit 2, stdout vazio, stderr nao-vazio.

## Decisoes desta tarefa (nao estavam explicitas no design.md)

- Formato do relatorio de `index` (`seen=N reprocessed=N removed=N`) e decisao minha —
  o spec so pede "the counts for a run with exactly one changed file" sem formato
  fixo. Se uma tarefa futura precisar de um formato diferente (JSON, por exemplo), e
  mudanca isolada em `run_index`.
- Nao imprimi `unreadable` no relatorio: o item 4.2 lista soh "seen, reprocessed,
  removed"; `unreadable` ja e reportado por arquivo em stderr dentro de
  `index_directory()` (task_02), entao nao haveria double-report sem necessidade.
- Checagem de diretorio (`os.path.isdir`) fica em `main()`, comum a `index` e `search`,
  em vez de duplicada em `run_index`/`run_search` — os dois sub-comandos precisam dela
  igualmente (design.md decisao 6 nao distingue).

## Bloqueio conhecido (nao desta tarefa, mas repetido em todas)

`openspec` CLI nao esta instalado nesta maquina (`which openspec` falha, confirmado de
novo nesta tarefa). `openspec validate fidx --strict` nao pode ser executado; ver nota em
`MEMORY.md`.

## Verificacao

`make test` (= `python3 -m unittest discover -s tests -t . -v`): 30 testes, todos
verdes (22 anteriores + 8 novos de `test_cli.py`).
