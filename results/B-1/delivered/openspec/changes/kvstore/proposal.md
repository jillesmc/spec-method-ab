# kvstore — armazenamento chave-valor durável em disco

## Por quê

O serviço guarda configuração, contadores e posição de processamento num único JSON que é
reescrito inteiro a cada mudança. Esse padrão tem duas falhas que já custaram dados:

1. **Reescrita destrutiva sem atomicidade.** Abrir o arquivo em modo de truncar e escrever por
   cima destrói o conteúdo antigo antes do novo existir. Um OOM ou um deploy no meio da escrita
   deixa o arquivo vazio ou cortado — é exatamente o "voltou com o arquivo zerado".
2. **Confirmação sem durabilidade.** Um `write()` que retorna sem `fsync` só encheu o cache do
   kernel. O serviço responde "gravei" para quem chamou, o processo morre, e o dado nunca chegou
   ao disco. O contrato "se eu disse que gravei, está lá depois do restart" não é cumprido hoje.

O serviço reinicia várias vezes por dia por deploy e por OOM, então essas janelas não são
teóricas: são amostradas várias vezes por dia.

Some-se a isso o custo: reescrever o arquivo inteiro faz cada gravação custar o tamanho de
**todo** o estado. Como a quantidade de chaves e de gravações cresce e ninguém limpa nada, o
custo por gravação cresce indefinidamente — e uma escrita mais longa é uma janela de perda mais
longa.

## O que muda

Um pacote `kvstore`, só com a biblioteca padrão do Python, que expõe uma API de biblioteca e uma
linha de comando:

```
python -m kvstore <diretorio> set <chave> <valor>
python -m kvstore <diretorio> get <chave>
python -m kvstore <diretorio> del <chave>
python -m kvstore <diretorio> list
```

O núcleo da mudança é a disciplina de escrita, não a interface:

- **Um arquivo por chave**, dentro do diretório do store. Gravar uma chave não toca nas outras,
  então o custo da gravação é o tamanho do valor, não o tamanho do store.
- **Troca atômica**: escreve num arquivo temporário no mesmo diretório, `fsync` no arquivo,
  `os.replace` por cima do definitivo, `fsync` no diretório. Um crash em qualquer ponto deixa o
  valor **antigo** inteiro ou o **novo** inteiro — nunca um meio-termo, nunca vazio.
- **`set` e `del` só retornam sucesso depois do `fsync` do diretório.** Sucesso retornado passa a
  significar "sobrevive ao restart", que é o contrato pedido.

## Fora de escopo

- Transações entre várias chaves (não há pedido de escrever duas chaves atomicamente).
- Concorrência entre múltiplos escritores. O diretório é nosso e o serviço é o único escritor;
  a suposição fica registrada no design e é o que permite dispensar lock.
- Índice, busca por valor, TTL, cache em memória, compactação, servidor ou rede.
- Migração automática do JSON atual. Se for preciso importar, é um laço de `set` sobre o JSON
  velho, feito uma vez por quem opera — não é código de produção.

## Impacto

- Novo: `kvstore/__init__.py` (API + implementação), `kvstore/__main__.py` (CLI),
  `tests/test_kvstore.py`, `tests/test_cli.py`, `tests/test_durabilidade.py`.
- `make test` continua sendo o portão: `python3 -m unittest discover`, sem dependência externa.
- No serviço, a troca é ponto a ponto: onde hoje se carrega/salva o JSON inteiro, passa a chamar
  `get`/`set`. Essa troca é trabalho do serviço, não deste change.
- Formato em disco novo e incompatível com o JSON atual — por isso um diretório novo, e o JSON
  velho fica intacto até alguém decidir apagá-lo.
