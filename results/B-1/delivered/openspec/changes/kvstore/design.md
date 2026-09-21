# Design — kvstore

## Contexto

Estado pequeno em número de bytes por chave, mas com valores que podem ser grandes; chaves e
gravações crescem sem limite e ninguém limpa. O processo morre com frequência (deploy, OOM), o
que significa que qualquer janela de inconsistência é amostrada muitas vezes por dia. Só
biblioteca padrão, Python 3.11+.

## Decisão 1 — um arquivo por chave

Cada chave é um arquivo dentro do diretório do store. Gravar uma chave não lê nem reescreve
nenhuma outra.

**Alternativas consideradas:**

| opção | por que não |
|---|---|
| Arquivo único reescrito com `tmp` + `os.replace` | Corrige a atomicidade, mas mantém o custo: cada gravação custa o **store inteiro**. Com valores grandes e crescimento sem limpeza, o custo por `set` cresce para sempre — e é preciso carregar tudo em memória num serviço que já morre de OOM. |
| Log append-only + compactação | Escrita barata, mas cada comando da CLI é um **processo novo**: um `get` teria que reproduzir o log inteiro para responder. Com valores grandes isso é caro por leitura, e exige compactação (mais código, mais um ponto de falha, mais uma escrita que pode ser interrompida). Sem nada disso, o log cresce sem fim — exatamente o cenário descrito. |
| `sqlite3` da stdlib em modo WAL | Resolve durabilidade de verdade e seria defensável. Rejeitado por ser um formato opaco para o operador (`ls` e `cat` deixam de servir) e por trazer um motor inteiro para um mapa de chaves; a disciplina de `fsync` que precisamos são ~10 linhas. **Se um dia forem necessárias transações entre chaves, esta é a migração certa.** |

O custo de `set` passa a ser proporcional ao valor gravado, e `get` é uma leitura direta de
arquivo — nada de replay, nada de compactação, nada para limpar.

## Decisão 2 — sequência exata de escrita

A ordem abaixo é o coração deste change; tudo mais é interface.

```
set:
  1. makedirs(dir)                     # se criou o diretório, fsync no pai
  2. fd, tmp = mkstemp(dir=dir, prefix=".tmp-")
  3. escreve o valor em blocos no fd   # streaming: não carrega tudo na memória
  4. os.fsync(fd); os.close(fd)        # bytes no disco, ainda sem nome definitivo
  5. os.replace(tmp, alvo)             # troca atômica (rename POSIX)
  6. fsync no diretório                # a entrada do nome no disco
  7. só agora retorna sucesso
```

Cada passo existe por um motivo:

- **(4) antes de (5)**: sem esse `fsync`, o `replace` pode publicar um nome que aponta para um
  arquivo cujo conteúdo ainda está só no cache. Crash aí → arquivo com tamanho certo e conteúdo
  zerado, o sintoma que o serviço já viu.
- **(5)**: `os.replace` é `rename(2)`, atômico no mesmo sistema de arquivos. O temporário é criado
  **no próprio diretório do store** justamente para garantir "mesmo sistema de arquivos" — um tmp
  em `/tmp` viraria cópia entre dispositivos e perderia a atomicidade.
- **(6)**: `fsync` no arquivo não persiste a **entrada de diretório**. Sem o `fsync` do diretório,
  o restart pode não encontrar o nome novo. Essa é a parte mais esquecida e a que fecha o contrato
  "respondi gravei, então está lá".
- **(7)**: sucesso é retornado depois de (6), nunca antes. É isso que faz o "gravei" ser verdade.

`del` segue a mesma lógica: `os.unlink` e `fsync` no diretório antes de retornar sucesso.

Crash em qualquer ponto deixa o valor **antigo** íntegro (antes de 5) ou o **novo** íntegro
(depois de 5). Não existe estado intermediário visível.

**Temporários órfãos:** um crash entre (2) e (5) deixa um `.tmp-*`. Eles são ignorados por `list`
(que só considera o prefixo `k.`) e não são varridos por ninguém: são raros, pequenos em número e
removê-los em background arriscaria apagar o temporário de uma escrita em andamento. O caminho
normal remove o seu próprio temporário num `finally`.

## Decisão 3 — nome do arquivo = `k.` + chave percent-encoded

`k.` + `urllib.parse.quote(chave, safe="")`. Exemplos: `foo` → `k.foo`;
`pos/topico-1` → `k.pos%2Ftopico-1`.

- **Reversível**: `list` é `os.listdir` + `unquote`, sem abrir um único arquivo — importante
  porque os valores são grandes.
- **Legível**: `ls` no diretório mostra as chaves. Num incidente às 3 da manhã isso vale mais do
  que economizar bytes.
- **O prefixo `k.`** resolve três coisas de uma vez: as chaves `.` e `..` não colidem com entradas
  do próprio diretório (`quote` não escapa `.`), nenhuma chave vira arquivo oculto, e qualquer
  outro arquivo no diretório (temporário, lixo) é distinguível de uma chave por prefixo.

**Limites aceitos e documentados:** o nome codificado fica limitado a 253 bytes (255 do ext4 menos
o prefixo), então chaves cuja forma codificada passe disso são **rejeitadas com erro explícito** —
falhar alto é melhor do que truncar. E o esquema assume sistema de arquivos **sensível a
maiúsculas**: em APFS/ExFAT, `Foo` e `foo` colidiriam. Se isso um dia for necessário, a troca é
nomear pelo sha256 da chave e guardar a chave numa primeira linha de cabeçalho dentro do arquivo —
mais robusto, menos legível, e `list` passaria a abrir todos os arquivos.

## Decisão 4 — validação de chave na fronteira

`set` e `del` rejeitam chave vazia, chave com caracteres de controle (`\n`, `\r`, `\0`) e chave
longa demais (acima). Motivo: `list` imprime uma chave por linha, e uma chave com `\n` tornaria a
saída ambígua — um consumidor da saída leria uma chave como duas. Validar na entrada mantém a
saída não-ambígua sem inventar um formato de escape.

## Decisão 5 — valores grandes entram e saem em streaming

`set <chave> <valor>` recebe o valor como argumento. Se `<valor>` for **omitido**, o valor é lido
de **stdin** — é o caminho para valores grandes, que não cabem confortavelmente em `ARG_MAX`. Nos
dois casos a escrita para o temporário é feita em blocos, e `get` também escreve em blocos para o
stdout. Num serviço que morre de OOM, não duplicar o valor na memória não é luxo.

Valores são texto, codificados em **UTF-8**. `get` escreve exatamente os bytes gravados, **sem
newline extra**, para que `set` e `get` sejam ida e volta exata.

## Decisão 6 — sem lock, e por quê

O enunciado diz que o diretório é nosso e o serviço é o escritor. Sem concorrência declarada, um
lockfile seria código para um problema que não existe — e lockfile mal feito cria travas que
sobrevivem a OOM, que é justamente o que mais acontece aqui.

Vale registrar o que o desenho já garante de graça: como toda publicação é `rename`, dois
escritores simultâneos na mesma chave produzem **um dos dois valores inteiro**, nunca uma mistura.
O que não há é serialização de "leia-modifique-grave" — se isso for preciso (um contador
incrementado por dois processos), a resposta é `os.O_EXCL` ou sqlite, não um lock caseiro.

## Decisão 7 — como provar durabilidade no `make test`

Três níveis, porque nenhum sozinho fecha:

1. **Ordem das operações** (`unittest.mock.patch` em `os.fsync`/`os.replace`): prova que houve
   `fsync` do arquivo **antes** do `replace` e `fsync` do diretório **depois** dele. É a asserção
   direta sobre a sequência da Decisão 2.
2. **Crash real** (subprocesso com `os.kill(os.getpid(), SIGKILL)` injetado entre os passos):
   prova que um processo morto no meio deixa o store legível e o valor antigo íntegro.
3. **Ida e volta** com valor grande e não-ASCII, e a garantia de que gravar uma chave não altera
   o arquivo de outra.

**Limitação declarada:** `SIGKILL` mata o processo, não a máquina — o page cache do kernel
sobrevive. O teste (2) prova a ordem das operações sob morte do processo, que é a causa real aqui
(deploy e OOM). Perda de energia só seria provada com o `fsync` de fato executado, e é o teste (1)
que assegura que ele é chamado. Dizer que (2) prova durabilidade contra queda de energia seria
falso, e fica anotado para ninguém concluir isso depois.

## Riscos

| risco | mitigação |
|---|---|
| Muitos inodes se o número de chaves explodir | Aceito: é um arquivo por chave, e o enunciado descreve estado de serviço (config, contadores, posição), não dados de usuário. Se virar milhões de chaves, o gatilho de migração é sqlite. |
| `fsync` por gravação limita a taxa de escrita | É o preço do contrato pedido. Sem ele não há "gravei". Não há knob para desligar, porque o knob seria usado. |
| Diretório apontado por engano na linha de comando é tratado como store vazio | Aceito e documentado: leituras num diretório inexistente respondem como store vazio, sem criar nada. |
