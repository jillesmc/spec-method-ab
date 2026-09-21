# Design

## Context

Repositório greenfield: `fidx/__init__.py` vazio, um teste de fumaça em `tests/`, `make test` rodando
`python3 -m unittest discover -s tests -t .`. Restrições que moldam o desenho (motivação em
`proposal.md`; comportamento exigido em `specs/file-index/spec.md`):

- Só biblioteca padrão. `sqlite3`, `hashlib`, `re`, `os`, `argparse` estão disponíveis; nada mais entra.
- `mtime` é ruído: os arquivos chegam por rsync e por checkout, então data antiga pode cobrir conteúdo
  novo e data nova pode cobrir conteúdo idêntico.
- `index` roda por cron, sem ninguém olhando: pode ser interrompido no meio, pode se sobrepor à rodada
  anterior, e o estado que ele deixa tem de continuar utilizável.

## Goals / Non-Goals

**Goals:**
- Custo da rodada de `index` proporcional ao que **mudou**, na parte cara (tokenizar e gravar postings).
- Busca respondida a partir do índice, sem tocar nos arquivos da pasta.
- Índice consistente mesmo se a rodada for morta no meio.

**Non-Goals:**
- Casamento parcial/substring, prefixo, regex ou ranking por relevância — a busca é por palavra inteira.
- Consulta com vários termos, operadores booleanos ou frase.
- Mostrar linha/trecho do arquivo (o requisito é *em quais arquivos* o termo aparece).
- Índice compartilhado entre máquinas ou entre pastas.
- Watcher/daemon: quem dispara é o cron.

## Decisions

### D1 — Staleness por hash do conteúdo, e a conta honesta disso

Chave de decisão: `sha256` dos bytes do arquivo, comparado com o hash guardado na rodada anterior.
`mtime` não é lido em lugar nenhum do código de decisão.

Alternativas descartadas: `mtime`+tamanho (é exatamente o que o enunciado diz que mente); só tamanho
(não detecta edição que preserva o tamanho); `mtime` como pré-filtro rápido com hash de confirmação
(o filtro erra na direção perigosa: arquivo mudado com data antiga seria pulado sem nunca ser hasheado).

Consequência que não dá para esconder: **toda rodada lê todos os bytes da pasta**. O que a
incrementalidade economiza é tokenização, escrita e reconstrução de postings — não o I/O de leitura.
O ganho de fato do projeto está na **busca**, que deixa de reler a pasta. Um `index` incremental que
não relesse tudo exigiria confiar em algum metadado, e é justamente isso que o enunciado proíbe.

### D2 — Armazenamento em SQLite (`sqlite3` da stdlib)

`<diretorio>/.fidx/index.sqlite3`, com duas tabelas:

```sql
files(path TEXT PRIMARY KEY, hash TEXT NOT NULL)
postings(term TEXT NOT NULL, path TEXT NOT NULL, PRIMARY KEY (term, path))
```

A PK composta de `postings` já é o índice de busca por `term` (SQLite materializa a PK como índice,
e a ordem `(term, path)` serve exatamente à consulta `WHERE term = ?`). Versão do formato em
`PRAGMA user_version` — zero tabelas de metadados.

Alternativas descartadas: JSON/pickle (regravar o arquivo inteiro a cada rodada e carregar tudo na
memória para buscar — anula o incremental na gravação e escala mal numa pasta grande); `dbm`/`shelve`
(sem transação e sem consulta, teríamos que serializar listas à mão); FTS5 (não está garantido em toda
build do SQLite e traz uma semântica de casamento que já decidimos não ter).

### D3 — Índice dentro da pasta, e a regra de exclusão

O índice mora em `.fidx/` **dentro** do diretório indexado: é autocontido, viaja com a pasta, e some
com um `rm -rf .fidx`. O preço é escrever na pasta do usuário e ter de excluir o próprio índice da
varredura.

A regra de exclusão é uma só: **entradas cujo nome começa com `.` são ignoradas** (arquivos e
diretórios, podando o diretório na descida). Isso cobre `.fidx/` e, de quebra, o `.git/` do checkout
que o enunciado menciona — indexar objetos do git seria lixo caro. Regra única é mais fácil de
prever do que "ignore só o meu diretório". Symlinks de diretório não são seguidos (`os.walk` já é
assim por padrão), o que evita ciclo.

Alternativa descartada: índice em `~/.cache/fidx/<hash-do-caminho>` — não suja a pasta, mas cria
estado invisível que sobrevive à pasta e quebra quando ela é movida.

### D4 — Tokenização única, usada nos dois lados

`re.findall(r"\w+", texto.casefold())`. `\w` em Python 3 é Unicode por padrão, então `Orçamento`
tokeniza como `orçamento`. A **mesma** função normaliza o termo da busca — é o que garante que
indexação e consulta não divirjam.

Se o termo da busca normalizar para mais de um token (`"nota fiscal"`) ou para nenhum (`"---"`), é
erro de uso. Preferimos recusar a inventar semântica de consulta (AND implícito, frase) que ninguém
pediu; o upgrade path, se aparecer a necessidade, é interseção dos postings.

### D5 — Uma leitura por arquivo

Lê bytes uma vez → `sha256` sobre os bytes → se o hash mudou, decodifica como UTF-8 estrito e
tokeniza. `UnicodeDecodeError` significa "não é texto": o arquivo é pulado e a rodada segue. Nada de
ler o arquivo duas vezes (uma para hash, outra para conteúdo).

### D6 — Consistência por arquivo, não por rodada

Cada arquivo reprocessado é uma transação: apaga os postings antigos daquele path, insere os novos,
atualiza `files.hash`. Uma rodada morta pelo cron no meio deixa o índice **consistente** (todo path
tem hash que casa com seus postings), só incompleto — e a rodada seguinte termina o serviço, porque
os arquivos que faltaram continuam com hash divergente ou ausente.

Alternativa descartada: uma transação única por rodada (all-or-nothing). Dá atomicidade mais bonita,
mas joga fora o trabalho já feito quando a rodada é interrompida, que é o cenário comum num cron.

Os arquivos que sumiram são apagados no fim: `files` que não apareceram na varredura saem, junto com
seus postings.

### D7 — Caminhos relativos, ordem determinística

Os paths são guardados relativos ao diretório indexado e com separador `/`, para a pasta poder ser
movida sem invalidar o índice. A busca devolve `ORDER BY path`, o que dá saída estável e comparável
em teste.

### D8 — Códigos de saída

`0` sucesso; `1` busca sem resultado (convenção do `grep`, útil no cron/script); `2` erro de uso ou
erro operacional (diretório inexistente, termo inválido, busca sem índice) — `2` é o que o `argparse`
já usa, então não inventamos um terceiro dialeto.

### D9 — Dois arquivos, duas camadas

`fidx/__init__.py` com a lógica (`index(dir) -> Resumo` e `search(dir, termo) -> list[str]`) e
`fidx/__main__.py` com `argparse` + tradução de resultado em código de saída. A lógica testa direto,
sem subprocesso; o contrato de CLI testa via `main(argv)` e, no teste de fumaça da CLI, via
`python -m fidx`. Nenhuma camada a mais: sem classe de repositório, sem interface de storage.

## Risks / Trade-offs

- **A rodada de `index` lê a pasta inteira todo dia** → inerente à regra "só o conteúdo vale" (D1).
  Mitigação: é o cron que paga, não a pessoa esperando a busca; o resumo da rodada mostra que o
  trabalho caro (reprocessamento) de fato não acontece.
- **Duas rodadas do cron sobrepostas** → o SQLite trava a segunda. Mitigação: `timeout` no connect e
  mensagem de erro explícita em vez de stack trace; a recomendação operacional é `flock` no crontab.
- **Pasta somente-leitura quebra o `index`** (não dá para criar `.fidx/`) → falha com mensagem clara
  dizendo onde ele queria escrever. Upgrade path, se aparecer: variável de ambiente apontando outro
  lugar. Não agora.
- **Renomear arquivo sem mudar conteúdo reprocessa o arquivo** (a chave é o path). Custo é CPU numa
  rodada; a alternativa (postings endereçados por hash) é uma indireção a mais que não vale antes de
  medir.
- **Busca por palavra inteira não é `grep`**: quem procurava substring (`orcament`) vai achar que
  "sumiu". É comportamento especificado, e o `README` precisa dizer isso.
- **Índice cresce com termos de arquivos gigantes/binários disfarçados de texto** → arquivos
  não-UTF-8 já caem fora; o resto é aceito conscientemente.

## Migration Plan

Greenfield: não há índice anterior nem dado a migrar. Rollback é apagar `.fidx/` — a próxima rodada
reconstrói do zero. Mudança futura de esquema se detecta por `PRAGMA user_version` diferente do
esperado: nesse caso o `index` recria o banco em vez de tentar migrar, porque o índice é derivado e
reconstruível.
