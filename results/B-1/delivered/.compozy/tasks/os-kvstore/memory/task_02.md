# Memória — task_02 (Provas de durabilidade)

## Implementado

- `tests/test_durabilidade.py`: 6 testes em 4 classes.
  - `TestOrdemDasOperacoes`: instrumenta `os.fsync`/`os.close`/`os.replace` (para `set`) e
    `os.unlink`/`os.fsync`/`os.close` (para `delete`) com `side_effect` que registra o nome da
    chamada e delega para a função original (capturada por valor no argumento padrão do
    `side_effect`, antes do `mock.patch` substituir o atributo). Assert é a lista de nomes exata:
    `["fsync", "close", "replace", "fsync", "close"]` e `["unlink", "fsync", "close"]` — a sequência
    inteira, não só "antes/depois" isolado, porque só há duas chamadas de `fsync` no caminho de
    `set` (arquivo e diretório) e a ordem entre elas com o `replace` no meio já é a prova pedida.
  - `TestCrashReal`: script auxiliar `tests/_apoio_crash.py`, rodado via `subprocess.run` com
    `cwd=<raiz do repo>` e `PYTHONPATH=<raiz do repo>` (não `sys.path`, porque o script roda como
    arquivo, não como `-m`). O script sobrescreve `os.replace` no processo filho para matar-se com
    `SIGKILL` antes ou depois de chamar o `os.replace` original. Dois cenários: `antes_replace`
    (valor antigo sobrevive, sobra `.tmp-*` órfão) e `depois_replace` (valor novo já publicado,
    sem órfão porque o rename já tinha acontecido). Os dois casos afirmam `kvstore.keys() ==
    ["chave"]` (sem entradas espúrias) e `returncode == -signal.SIGKILL`.
  - `TestIsolamentoEntreChaves`: mesma prova que já existia em `test_kvstore.py`
    (`test_regravar_chave_nao_afeta_outra`), duplicada aqui porque o item 2.4 da task pede
    explicitamente esse teste neste arquivo — decisão: manter as duas cópias (uma por arquivo/tema)
    em vez de remover uma, já que `tasks.md` atribui a prova a arquivos diferentes por seção.
  - `TestValorGrande`: em vez de instrumentar `os.write`/`os.read` (que exigiria mexer em detalhes
    internos como buffering do `open()`), passei envelopes próprios como `entrada`/`saida` para
    `set_stream`/`get_stream` (`_FonteContada`/`_DestinoContado`) que só contam os tamanhos de cada
    `.read(n)`/`.write(bloco)`. Prova que o valor de 10 MiB nunca é lido/escrito de uma vez: todo
    `read` (exceto o último) pede exatamente `kvstore._TAMANHO_BLOCO`, e nenhum `write` excede esse
    tamanho. Usa `os.urandom` (bytes, não `str`) porque o teste é "byte a byte" e `set_stream`/
    `get_stream` não fazem round-trip UTF-8 (isso é só em `set`/`get`).
- `tests/_apoio_crash.py`: novo arquivo auxiliar, prefixo `_` para não ser coletado por
  `unittest discover` (padrão `test*.py`).
- Comentário de módulo no topo de `test_durabilidade.py` (item 2.3) registrando a limitação:
  SIGKILL prova ordem sob morte de processo, não sobrevivência a queda de energia.

## Verificação executada

- `python3 -m unittest tests.test_durabilidade -v` → 6/6 `ok`.
- `make test` → 28 testes (22 de `test_kvstore.py` + 1 de `test_fumaca.py` + 6 novos), todos `ok`.
- `git status --porcelain` após rodar os testes duas vezes: nenhum diretório temporário novo
  (os `TemporaryDirectory` de cada `setUp` limpam via `addCleanup`; o processo filho do crash real
  também escreve só dentro do `self.diretorio` do teste pai).

## Pendência / degradação declarada

- `openspec validate kvstore --strict` não pôde rodar (binário ausente, mesma situação já
  registrada em [[MEMORY]] e na memória de task_01). Confirmado de novo nesta task: `which
  openspec` falha e `npx openspec` falha por não haver rede/registro. `make test` continua sendo o
  portão real e passa limpo.
