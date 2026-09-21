# task_02 — Content-addressed refresh

## Implementado

`fidx/__init__.py`: `index_directory(directory)` (design.md decisao 3, um passo, uma
transacao):

- `os.walk(directory)` com `dirnames[:] = [d for d in dirnames if not d.startswith(".")]`
  (poda em qualquer profundidade — exclui `.git/` e o proprio `.fidx/`) e mesmo filtro
  para `filenames`.
- Para cada arquivo: `path = os.path.relpath(full_path, directory)` (separador nativo
  do SO, so testado em Linux); digest via `hashlib.file_digest` em modo `"rb"`.
- Arquivo ilegivel (`OSError` no open/`file_digest`): mensagem em stderr
  (`fidx: cannot read <path>: <exc>`), `stats["unreadable"] += 1`, path adicionado a
  `seen_paths` (para nao ser removido na reconciliacao) e **pulado** — entrada anterior
  em `files`/`postings` fica intocada.
- Digest igual ao armazenado: pulado sem reabrir para tokenizar (o ganho incremental).
  Digest novo/diferente: reabre em modo texto (`encoding="utf-8", errors="replace"`),
  `DELETE FROM postings WHERE path=?` + insere tokens novos + `INSERT OR REPLACE INTO
  files`.
- Reconciliacao de remocao: `stored_paths - seen_paths` ao final do walk, delete em
  `files` e `postings`.
- Um unico `conn.commit()` no final (a transacao inteira); `conn.close()` antes de
  retornar `stats`.

`tests/test_refresh.py` (8 testes, todos verdes com `make test`) — um por item do
`tasks.md` secao 2, mais um extra:

- `TestWalkSkipsHidden`: `.git/config` e `.hidden.txt` nunca indexados (2.1a); apos um
  primeiro `index_directory`, o `.fidx/` recem-criado tambem nao aparece num segundo
  run (2.1b, cobre a auto-exclusao do storage).
- `TestFirstRun`: primeiro run indexa tudo, `reprocessed == seen` (2.2).
- `TestRemoval`: arquivo apagado -> `removed == 1`, termo unico dele para de casar
  (2.3). Como `search()` (secao 3) ainda nao existe, a verificacao le `postings`
  diretamente via uma conexao sqlite3 separada (helper `paths_for_term` no proprio
  arquivo de teste) — nao e chamada de API publica.
- `TestUnreadableFile`: chmod 000 num arquivo ja indexado, roda de novo, confirma
  `unreadable == 1`, `reprocessed == 0`, entrada antiga preservada; `skipTest` se
  `os.geteuid() == 0` (2.4).
- `TestTimestampTrapA`: troca conteudo + `os.utime` para o passado -> `reprocessed == 1`,
  termo novo casa, termo velho nao (2.5).
- `TestTimestampTrapB`: `os.utime` para o futuro sem mudar bytes -> `reprocessed == 0`
  (2.6).
- `TestMovedFile`: `os.rename` com mesmo conteudo -> so o path novo aparece em
  `postings`/`files` apos o refresh seguinte (2.7).

## Decisoes desta tarefa (nao estavam no design.md explicitamente)

- Path armazenado em `files`/`postings` e o `os.path.relpath(full_path, directory)`
  bruto — sem normalizar separador para `/`. So testado em Linux (`os.sep == "/"`),
  entao nao ha diferenca observavel agora; se a busca (task_03) rodar em outro SO isso
  precisa de atencao, mas nao esta no escopo desta tarefa.
- `INSERT OR REPLACE INTO files` (nao `ON CONFLICT DO UPDATE`): a tabela so tem
  `path`/`digest`, entao substituir a linha inteira e equivalente e mais simples; sqlite
  bundado (3.53.1) suportaria upsert tambem, mas nao ha necessidade.
- Arquivo ilegivel entra em `seen_paths` (para nao ser removido) mas nao em nenhuma
  outra estrutura — se nunca esteve no indice, so fica de fora silenciosamente (nao ha
  "entrada anterior" para manter, e o design.md nao pede nada alem disso).

## Para as proximas tarefas (task_03+)

- `search()` ainda nao existe. Os testes desta tarefa que precisavam confirmar "um termo
  casa/nao casa" leem a tabela `postings` diretamente — task_03 pode (mas nao precisa)
  reescrever esses asserts usando `fidx.search()` depois que ela existir; nao fiz isso
  aqui para nao extrapolar o escopo da secao 2.
- `index_directory()` abre e fecha sua propria conexao (via `open_index` + `conn.close()`
  no final) — task_04 (CLI) so precisa chamar a funcao e imprimir `stats`, sem gerenciar
  conexao.

## Bloqueio conhecido (nao desta tarefa, mas repetido em todas)

`openspec` CLI nao esta instalado nesta maquina. `openspec validate fidx --strict`
nao pode ser executado; ver nota em `MEMORY.md`.
