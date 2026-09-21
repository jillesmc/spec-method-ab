# task_03 — Linha de comando (`kvstore/__main__.py`)

- Implementado `kvstore/__main__.py` com `argparse`: posicional `diretorio` +
  subparsers `set` (chave, valor opcional), `get` (chave), `del` (chave), `list`. `set` sem
  `valor` lê `sys.stdin.buffer` direto para `set_stream`; com `valor`, empacota em
  `io.BytesIO` e usa o mesmo `set_stream` — um único caminho de escrita, sem duplicar lógica
  de streaming. `get` escreve via `get_stream` em `sys.stdout.buffer` (sem newline). `list`
  usa `kvstore.keys` (já ordenado) e imprime uma por linha com `print`.
- Códigos de saída: `argparse` já sai com 2 em uso inválido/comando desconhecido/args
  faltando (`required=True` nos subparsers) — não precisei reimplementar isso. `KeyError` de
  `get_stream`/`delete` → 1. `ValueError` (chave inválida, de `_caminho`) e `OSError` → 2.
  Try/except em duas camadas: a interna só pega `KeyError` por comando (`get`/`del`), a
  externa pega `ValueError`/`OSError` ao redor de tudo — assim uma chave inválida em `get`
  também cai em 2, não em 1 (a checagem de forma acontece antes da checagem de existência).
- **Cuidado que quase virou bug:** capturar `SystemExit` do `parser.parse_args()` para
  devolver `exc.code` teria que tratar `exc.code == 0` (caso de `--help`) sem cair no `else
  2` — um `exc.code if exc.code else 2` ingênuo trata `0` como falsy e devolveria 2 para
  `--help`. Corrigido para `exc.code if isinstance(exc.code, int) else 2`. Testado
  manualmente (`python3 -m kvstore --help` → exit 0), não coberto por teste automatizado
  porque não é cenário da spec, mas vale registrar caso `--help` vire relevante depois.
- `tests/test_cli.py` (13 testes) chama `sys.executable -m kvstore` via `subprocess`, com
  `cwd=<raiz>` e `PYTHONPATH=<raiz>` (mesmo padrão de `tests/_apoio_crash.py` da task_02,
  ver `MEMORY.md`) — cobre todos os cenários da seção "Linha de comando" da spec: ida e volta,
  `get`/`del` ausentes (1), comando desconhecido e args faltando (2), chave inválida (2, sem
  criar arquivo), valor grande por stdin (~10.8 MiB), valor vazio por argumento, diretório
  inexistente em `get` (1) e `list` (0, stdout vazio, diretório continua ausente), primeira
  gravação cria o diretório.
- Erro de teste próprio durante o desenvolvimento: primeira versão de
  `test_valor_grande_por_stdin` gerava só 1.8 MB (`"conteudo-" * 200_000`) e a asserção de
  tamanho mínimo (`> 10 MiB`) falhava — não era bug do CLI, era conta errada no multiplicador
  do teste. Corrigido para `* 1_200_000` (~10.8 MiB).
- `openspec validate kvstore --strict` continua indisponível neste ambiente (mesma causa das
  tasks anteriores — ver `MEMORY.md`); reportado como degradação, não bloqueio.
- `make test`: 41 testes, verde, sem diretório temporário deixado para trás (todos os testes
  usam `tempfile.TemporaryDirectory` com `addCleanup`).
