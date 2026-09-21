# Tasks

## 1. Núcleo do índice (`fidx/__init__.py`)

- [ ] 1.1 Implementar a varredura (`os.walk`, poda de entradas que começam com `.`, só arquivos
      regulares, caminhos relativos com `/`) e verificar com um teste que uma pasta temporária com
      `a/b/nota.txt`, `.git/objects/x` e `.rascunho.txt` produz exatamente `["a/b/nota.txt"]`
- [ ] 1.2 Implementar a tokenização única (`re.findall(r"\w+", texto.casefold())`) usada na indexação e
      na consulta, e verificar com um teste que `"Orçamento: R$ 10"` tokeniza como
      `["orçamento", "r", "10"]`
- [ ] 1.3 Criar/abrir o banco em `<dir>/.fidx/index.sqlite3` com as tabelas `files` e `postings` e
      `PRAGMA user_version`, recriando o banco quando a versão divergir, e verificar com um teste que
      abrir duas vezes não duplica esquema e que versão divergente reconstrói do zero
- [ ] 1.4 Implementar `index(dir)`: ler bytes uma vez por arquivo, `sha256`, pular quem não decodifica
      em UTF-8, reprocessar só quem tem hash divergente (transação por arquivo), apagar do índice os
      paths que sumiram, e devolver o resumo `(reprocessados, inalterados, removidos)`; verificar com um
      teste que a primeira rodada sobre N arquivos devolve `(N, 0, 0)`
- [ ] 1.5 Implementar `search(dir, termo)`: normalizar o termo com a mesma tokenização, consultar
      `postings` e devolver os paths `ORDER BY path`; verificar com um teste que um termo presente em
      dois arquivos devolve os dois caminhos na ordem esperada

## 2. Os testes que sustentam a promessa de incrementalidade

- [ ] 2.1 Teste "conteúdo mudou com data antiga": indexar, alterar o conteúdo de um arquivo, forçar
      `os.utime` para uma data anterior à indexação, reindexar e verificar que o resumo reporta 1
      reprocessado, que o termo novo é encontrado e que o termo antigo não é mais
- [ ] 2.2 Teste "data nova sem mudança de conteúdo": indexar, avançar o `mtime` com `os.utime` sem tocar
      no conteúdo, reindexar e verificar que o resumo reporta 0 reprocessados
- [ ] 2.3 Teste "pasta inalterada": duas rodadas seguidas sem mudança devolvem `(0, N, 0)` na segunda e
      resultados de busca idênticos
- [ ] 2.4 Teste "arquivo removido": apagar um arquivo indexado, reindexar e verificar 1 removido e busca
      vazia para um termo exclusivo dele
- [ ] 2.5 Teste "o índice não indexa a si mesmo": duas rodadas seguidas, verificar que nenhum path sob
      `.fidx/` entra no índice e que a segunda rodada reporta 0 reprocessados
- [ ] 2.6 Teste "arquivo binário": pasta com bytes não decodificáveis — `index` termina sem exceção e os
      demais arquivos continuam indexados

## 3. CLI (`fidx/__main__.py`)

- [ ] 3.1 Montar o `argparse` com o contrato `<diretorio> {index,search}` (e `<termo>` no `search`) e
      verificar com testes que subcomando desconhecido e argumento faltando saem com código 2 e mensagem
      em stderr
- [ ] 3.2 `index`: validar que o diretório existe, chamar `index()`, imprimir o resumo em uma linha
      legível por pessoa e por máquina, sair 0; teste verifica a linha de resumo e o código de saída
- [ ] 3.3 `search`: imprimir um path por linha, sair 0 com resultado e 1 sem resultado; teste verifica os
      dois códigos e a saída vazia no caso sem resultado
- [ ] 3.4 Erros operacionais com mensagem em stderr e código 2: diretório inexistente, busca em diretório
      nunca indexado (mensagem manda rodar `index` antes, sem cair em varredura), termo que normaliza
      para nenhuma ou mais de uma palavra; um teste por caso
- [ ] 3.5 Tratar `sqlite3.OperationalError` de banco travado (rodadas de cron sobrepostas) com `timeout`
      no connect e mensagem clara em vez de stack trace; verificar abrindo uma transação exclusiva em
      paralelo dentro do teste

## 4. Fechamento

- [ ] 4.1 Teste de fumaça da CLI de ponta a ponta com `subprocess` chamando `python -m fidx` (index e
      search) numa pasta temporária, garantindo que o módulo é executável como o README promete
- [ ] 4.2 Atualizar o `README.md` com a semântica de busca por palavra inteira, os códigos de saída e o
      fato de o índice viver em `.fidx/` dentro da pasta
- [ ] 4.3 Rodar `make test` e verificar que toda a suíte passa sem nenhuma dependência externa instalada
