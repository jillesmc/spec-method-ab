# Tasks — kvstore

Ordem pensada para que a durabilidade seja escrita e testada **antes** da interface. Cada tarefa
termina com `python3 -m unittest discover -s tests -t . -v` passando.

## 1. Núcleo de escrita durável (`kvstore/__init__.py`)

- [ ] 1.1 `_caminho(diretorio, chave)`: valida a chave (não vazia, sem `\n`, `\r`, `\0`, forma
      codificada ≤ 253 bytes) e devolve `<diretorio>/k.<quote(chave, safe="")>`. Erro de validação
      levanta `ValueError` com mensagem que nomeia o motivo e o limite.
- [ ] 1.2 `_fsync_dir(caminho)`: `os.open(caminho, os.O_RDONLY)`, `os.fsync`, `os.close`.
- [ ] 1.3 `set(diretorio, chave, valor)` e `set_stream(diretorio, chave, entrada)`: cria o
      diretório se preciso (e faz `fsync` no diretório pai quando ele foi criado agora), abre um
      temporário com `tempfile.mkstemp(dir=diretorio, prefix=".tmp-")`, escreve em blocos,
      `os.fsync(fd)`, `os.close(fd)`, `os.replace(tmp, alvo)`, `_fsync_dir(diretorio)`. `finally`
      remove o temporário se ele ainda existir. Nenhuma abertura do arquivo definitivo em modo de
      truncar, em ponto nenhum.
- [ ] 1.4 `get(diretorio, chave)` e `get_stream(diretorio, chave, saida)`: lê o arquivo em blocos;
      `FileNotFoundError` (arquivo ou diretório) vira `KeyError`.
- [ ] 1.5 `delete(diretorio, chave)`: `os.unlink` e `_fsync_dir` antes de retornar; ausência vira
      `KeyError`.
- [ ] 1.6 `keys(diretorio)`: `os.listdir`, mantém só os nomes com prefixo `k.`, `unquote` do
      resto, devolve ordenado. Diretório inexistente devolve lista vazia.

**Verificação:** `tests/test_kvstore.py` cobrindo ida e volta, valor vazio, não-ASCII, chave com
`/`, chave inválida, `KeyError` em chave e diretório ausentes, `keys` ordenado e ignorando
`.tmp-*`.

## 2. Provas de durabilidade (`tests/test_durabilidade.py`)

- [ ] 2.1 Ordem das operações: com `unittest.mock.patch` em `os.fsync`, `os.replace` e
      `os.close`, registrar a sequência de chamadas de um `set` e afirmar que houve `fsync` do fd
      do arquivo **antes** do `replace` e `fsync` do fd do diretório **depois** dele, antes do
      retorno. Mesma prova para `del` (unlink → fsync do diretório → retorno).
- [ ] 2.2 Crash real: script auxiliar rodado com `subprocess`, que grava a chave e se mata com
      `os.kill(os.getpid(), signal.SIGKILL)` num ponto injetado (antes do `replace`; e depois do
      `replace`, antes do `fsync` do diretório). O teste pai afirma: valor antigo íntegro no
      primeiro caso, store legível nos dois, `keys()` sem entradas espúrias.
- [ ] 2.3 Escrever no topo do arquivo de teste, em comentário, a limitação declarada no design:
      `SIGKILL` prova a ordem sob morte de processo, não sobrevivência a queda de energia — essa
      parte é coberta pela asserção de que `fsync` é chamado (2.1).
- [ ] 2.4 Isolamento entre chaves: gravar `a` e `b`, capturar `stat` do arquivo de `b`, regravar
      `a`, afirmar que `b` não mudou (conteúdo e `st_mtime_ns`).
- [ ] 2.5 Valor grande: `set` de ~10 MiB e `get` conferindo byte a byte, com afirmação de que a
      leitura e a escrita são feitas em blocos (o valor inteiro nunca é concatenado em memória).

## 3. Linha de comando (`kvstore/__main__.py`)

- [ ] 3.1 Parse com `argparse`: `<diretorio>` posicional, subcomandos `set` (chave, valor
      opcional), `get` (chave), `del` (chave), `list`.
- [ ] 3.2 `set` sem o argumento de valor lê de `sys.stdin.buffer` em blocos, direto para o
      temporário.
- [ ] 3.3 `get` escreve em `sys.stdout.buffer` em blocos, sem newline acrescentada.
- [ ] 3.4 `list` imprime uma chave por linha, ordenado.
- [ ] 3.5 Códigos de saída: 0 sucesso; 1 `KeyError`; 2 `ValueError`, uso inválido e `OSError`.
      Mensagens de erro só em stderr.

**Verificação:** `tests/test_cli.py` chamando `sys.executable -m kvstore` via `subprocess` num
diretório temporário — cada cenário da seção "Linha de comando" da spec, mais valor grande por
stdin e diretório inexistente em `get`/`list`.

## 4. Fechamento

- [ ] 4.1 Substituir `tests/test_fumaca.py` (o teste de importação do esqueleto) pelos testes
      reais, ou mantê-lo se ainda fizer sentido como checagem barata de pacote.
- [ ] 4.2 Atualizar o `README.md` com os quatro comandos, os códigos de saída, o valor por stdin e
      uma frase sobre o contrato: sucesso significa persistido.
- [ ] 4.3 `make test` verde do zero num diretório limpo, conferindo que nenhum teste deixa
      diretório temporário para trás.
