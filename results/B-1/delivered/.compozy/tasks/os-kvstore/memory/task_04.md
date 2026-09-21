# task_04 — Fechamento

- 4.1: mantido `tests/test_fumaca.py` como está, em vez de substituí-lo. O item dava as duas
  opções ("substituir... ou mantê-lo se ainda fizer sentido como checagem barata de pacote").
  Os testes reais (`test_kvstore.py`, `test_cli.py`, `test_durabilidade.py`) já cobrem a
  importação do pacote de sobra, mas o fumaça continua sendo o teste mais barato e mais rápido
  de ler quando alguém só quer confirmar que o pacote importa — não conflita com nada, decidido
  manter.
- 4.2: `README.md` reescrito com os quatro comandos (`set`/`get`/`del`/`list`), a nota de que
  `set` sem `valor` lê de `stdin` em blocos (caminho para valor grande), a tabela de códigos de
  saída (0/1/2, mesmos do CLI implementado em task_03) e a frase do contrato de durabilidade
  ("sucesso significa persistido").
- 4.3: `make test` rodado do zero (41 testes, `OK`) com snapshot de `/tmp` antes/depois via
  `diff <(ls /tmp antes) <(ls /tmp depois)` — vazio, confirmando que nenhum teste deixa
  diretório temporário para trás. Todos os `setUp` já usam
  `tempfile.TemporaryDirectory()` + `self.addCleanup(self._tmp.cleanup)`, que limpa mesmo em
  falha de teste.
- `openspec validate kvstore --strict` degradado de novo, mesma causa das tasks anteriores
  (`which openspec` falha, `npx openspec` falha sem rede/registro — confirmado de novo aqui).
  `make test` é o portão real e está verde.
- Cadeia `os-kvstore` completa: task_01 a task_04 todas `completed`.
