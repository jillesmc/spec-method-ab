# Memória compartilhada — change `kvstore`

- Ordem de escrita implementada em `kvstore/__init__.py` (task_01): `os.write*` no fd do
  temporário → `os.fsync(fd)` → `os.close(fd)` → `os.replace(tmp, alvo)` → `_fsync_dir(diretorio)`.
  Confirmado por instrumentação com `unittest.mock.patch` antes de fechar a task — qualquer teste
  de ordem em task_02 (`tests/test_durabilidade.py`) deve bater com essa sequência exata.
- `_caminho` valida e levanta `ValueError`; `get`/`delete` traduzem `FileNotFoundError` (arquivo
  OU diretório ausente) em `KeyError` — não há tratamento separado para "diretório não existe".
- Limite de nome: `quote(chave, safe="")` tem que ter ≤ 253 bytes; o prefixo `k.` (2 bytes) fecha
  em 255 (limite ext4). O limite é sobre a chave codificada, não sobre o nome do arquivo inteiro.
- `openspec` (CLI) não está instalado neste ambiente (`which openspec` falha, `npx openspec`
  falha por falta de rede/registro). `openspec validate kvstore --strict`, citado nas seções de
  verificação das tasks, não pôde ser executado em nenhuma task desta cadeia — reportar como
  degradação, não como bloqueio, já que `make test` é o portão real definido no `proposal.md`.
- Escopo por task confirmado lendo `openspec/changes/kvstore/tasks.md`: task_01 = seção 1 (núcleo)
  + `tests/test_kvstore.py`; task_02 = seção 2 (`tests/test_durabilidade.py`); task_03 = seção 3
  (`kvstore/__main__.py` + `tests/test_cli.py`); task_04 = fechamento (README, `test_fumaca.py`,
  `make test` limpo). Não implementar `__main__.py` nem `test_durabilidade.py` em task_01.
- task_02 concluída: `tests/test_durabilidade.py` (6 testes) + script auxiliar
  `tests/_apoio_crash.py` (prefixo `_` para não ser coletado por `unittest discover`, que só pega
  `test*.py`). Detalhes de instrumentação em [[task_02]]. Padrão reusável se task_03/04 precisarem
  de mais scripts auxiliares via `subprocess`: rodar com `cwd=<raiz do repo>` e
  `PYTHONPATH=<raiz do repo>` no ambiente, não `sys.path`, porque o script roda como arquivo
  (não `-m`).
- Degradação de `openspec validate kvstore --strict` confirmada de novo em task_02 (mesma causa
  de task_01: binário ausente, sem rede para `npx`). Reportar como degradação em toda task desta
  cadeia, não como blocker — `make test` é o portão real.
- task_03 concluída: `kvstore/__main__.py` (CLI com `argparse`) + `tests/test_cli.py` (13
  testes via `subprocess`, mesmo padrão `cwd`/`PYTHONPATH` da task_02). `argparse` com
  subparsers `required=True` já cobre "comando desconhecido/args faltando → exit 2" de graça,
  sem código extra. Duas camadas de `try/except`: interna só para `KeyError` (get/del → 1),
  externa para `ValueError`/`OSError` (chave inválida ou erro de E/S → 2) — assim chave
  inválida em `get`/`del` cai em 2, não em 1. Detalhes e o `SystemExit`/`--help` (`exc.code
  == 0` é falsy, cuidado com `exc.code if exc.code else 2`) em [[task_03]].
- Degradação de `openspec validate kvstore --strict` confirmada de novo em task_03 (mesma
  causa das tasks anteriores). Ainda não é blocker — `make test` (41 testes) é o portão real e
  está verde.
- task_04 (Fechamento) concluída, cadeia completa: `README.md` reescrito com os quatro
  comandos, a leitura por `stdin` em `set` sem valor, os códigos de saída e a frase do contrato
  de durabilidade. `tests/test_fumaca.py` mantido como checagem barata (as duas opções do item
  eram válidas; ver [[task_04]] para o porquê). `make test` confirmado verde do zero com
  snapshot de `/tmp` antes/depois — nenhum diretório temporário sobra, porque todo `setUp` usa
  `tempfile.TemporaryDirectory()` + `addCleanup`. Degradação de `openspec validate` confirmada
  pela quarta vez, mesma causa.
