# Memória — task_01 (Núcleo de escrita durável)

## Implementado

- `kvstore/__init__.py`: `_caminho`, `_fsync_dir`, `set`, `set_stream`, `get`, `get_stream`,
  `delete`, `keys`. Só biblioteca padrão (`os`, `io`, `tempfile`, `urllib.parse`).
- `tests/test_kvstore.py`: 22 casos cobrindo ida e volta, valor vazio, não-ASCII, chave com `/`
  (sem criar subdiretório), as quatro formas de chave inválida (vazia, `\n`, `\r`, `\0`, forma
  codificada > 253 bytes), `KeyError` em chave ausente e em diretório ausente (`get` e `delete`),
  `keys` ordenado e ignorando `.tmp-*`, `set_stream`/`get_stream`, ausência de temporário residual,
  isolamento entre chaves (`st_mtime_ns` de uma chave não muda ao regravar outra), e criação do
  diretório na primeira gravação.

## Decisões de implementação

- `set(diretorio, chave, valor)` é um wrapper fino sobre `set_stream` com `io.BytesIO(valor.encode
  ("utf-8"))`; `get` é o inverso sobre `get_stream` com `io.BytesIO()` de saída. Mantém uma única
  implementação real dos passos de durabilidade.
- Fsync do diretório **pai** só acontece quando `set_stream` de fato criou o diretório do store
  agora (`not os.path.isdir(diretorio)` antes do `makedirs`) — não a cada `set`.
- Removi o `.tmp-*` no `finally` só se ainda existir (`os.path.exists(tmp)`), porque no caminho
  feliz ele já não existe mais depois do `os.replace`.

## Verificação executada

- `python3 -m unittest discover -s tests -t . -v` → 22 + 1 (fumaça) testes, todos `ok`.
- `make test` → mesmo resultado, saída limpa.
- Instrumentação manual com `unittest.mock.patch` em `os.write/os.fsync/os.close/os.replace`
  confirmando a ordem exata da Decisão 2 do `design.md` (ver [[MEMORY]]).
- `git status --porcelain` depois dos testes: nenhum diretório temporário deixado para trás pelo
  `tempfile.TemporaryDirectory` do `setUp` (cleanup automático via `addCleanup`).

## Pendência / degradação declarada

- `openspec validate kvstore --strict`, citado na seção "Verificacao" do `task_01.md`, não pôde
  rodar: o binário `openspec` não está instalado neste ambiente (nem via PATH nem via `npx`, que
  falhou por falta de acesso ao registro). Não é um blocker de implementação — o portão real do
  repositório é `make test` (definido no `proposal.md`), que passa. Reportado como degradação
  explícita no output estruturado desta task; mesma situação provavelmente se repete em task_02,
  task_03 e task_04 (todas citam o mesmo comando de verificação).
