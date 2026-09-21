# Pré-registro · A/B nº 3 · tarefa com armadilha, dois domínios

**Congelado antes da primeira execução.** Auto-contido: quem retomar lê este arquivo primeiro.

Data: 2026-09-20. Runtime: **CompozyOS 0.3.0-beta.27**.

---

## 1 · Por que existe um terceiro A/B

Os dois anteriores **empataram no teto**. O nº 1 (enunciado detalhado) deu 22/22 nos dois braços.
O nº 2 (enunciado vago) deu 10/10 nas seis rodadas.

O diagnóstico não é que as ferramentas sejam equivalentes. É que **a tarefa não tinha armadilha**:
qualquer decomposição decente do `logsum` funcionava, e o Opus não produz decomposição ruim.

Para planejar pagar alguma coisa, a tarefa precisa de um **caminho natural que passa em todo o
caminho feliz e quebra num invariante**. Quem planeja evita; quem vai direto ao código cai.

> **A pergunta:** quando existe uma armadilha, planejar melhor evita cair nela?

---

## 2 · As duas armadilhas

### Domínio 1 · store (durabilidade)

O enunciado diz o requisito em linguagem de negócio e **não nomeia técnica nenhuma**:

> "Esse serviço reinicia sozinho várias vezes por dia, por deploy e por OOM. Quando o serviço
> responde 'gravei' para quem chamou, aquilo tem que estar lá depois do restart, aconteça o que
> acontecer."

| | |
|---|---|
| caminho natural | reescrever o JSON inteiro a cada gravação (é o que o enunciado diz que eles fazem hoje) |
| caminho planejado | gravação que sobrevive à morte do processo no meio |

### Domínio 2 · indexador (invalidação de cache)

> "Eles chegam por rsync e por checkout de repositório, então a data de modificação deles não é
> confiável: já vi arquivo voltar com data antiga depois de mudar de conteúdo, e vi arquivo com
> data nova sem ter mudado nada. O que vale é o conteúdo."

| | |
|---|---|
| caminho natural | cache por `mtime`, que é o reflexo de todo mundo |
| caminho planejado | decidir o que mudou pelo conteúdo |

**A linha de justiça, e ela é a mesma nos dois:** o **requisito** está no enunciado, a **técnica**
não. Traduzir requisito em técnica é exatamente o trabalho que planejar deveria fazer.

---

## 3 · As camadas, e onde mora a métrica primária

| camada | store | indexador | papel |
|---|---|---|---|
| BASE | 8 | 8 | o básico funciona. Existe para não premiar quem trata a borda e não entrega a função |
| ROBUSTEZ | 12 | 10 | bordas que o enunciado não cita |
| **PRIMÁRIA** | **INVARIANTE, 10** | **ORÁCULO, 12** | onde a armadilha aparece |

**INVARIANTE (store).** Mesmo critério nos dez: toda chave cuja gravação foi **confirmada**
(processo saiu com 0) tem que continuar legível; a que estava em voo pode sumir; reabrir não pode
explodir; e o store não pode travar.

**ORÁCULO (indexador).** Dispensa meu julgamento por completo:

```
índice incremental  ==  índice reconstruído do zero
```

Nenhum formato, nenhuma estrutura, nenhuma API são cobrados. Só a igualdade dos dois caminhos.

---

## 4 · A calibragem, medida antes de gastar um token

Escrevi duas implementações de referência por domínio, à mão, e rodei a suíte contra elas com o
mesmo comando que o runner usa. Sem isto, "a suíte discrimina" seria opinião minha.

| domínio | referência | BASE | ROBUSTEZ | **PRIMÁRIA** |
|---|---|---|---|---|
| store | cuidadosa (log append + CRC + rename atômico) | 8/8 | 12/12 | **10/10** |
| store | ingênua (reescreve o arquivo inteiro) | 8/8 | 12/12 | **3/10** |
| indexador | cuidadosa (hash de conteúdo) | 8/8 | 10/10 | **12/12** |
| indexador | ingênua (cache por mtime) | 8/8 | 10/10 | **8/12** |

**A ingênua passa em tudo menos na camada que importa.** É exatamente o que faltava nos dois A/B
anteriores.

### Três coisas que consertei na calibragem, e todas contra mim

1. **Valor de 1 MB não passa por `argv`.** O Linux corta um argumento em 128 KB
   (`MAX_ARG_STRLEN`) e o teste estourava no `subprocess` em vez de medir o store. Baixado para
   100 KB.
2. **Matar o processo por tempo virava sorteio.** A primeira versão media o tempo médio de um
   `set` e sorteava o instante da morte. O resultado oscilou entre execuções: às vezes a morte
   caía na subida do interpretador, antes de qualquer byte tocar o disco, e o teste passava sem
   ter testado nada. Agora a morte acontece **no instante em que o disco começa a mudar**, o que
   é determinístico e não favorece desenho nenhum: quem reescreve tudo trunca no `open` e perde o
   confirmado; quem anexa perde no máximo o registro em voo; quem usa `tmp` mais `rename` não
   perde nada. As três leituras estão certas.
3. **O teste de tempo não separava os desenhos.** Medi: o custo dominante é a subida do
   interpretador (~50 ms por chamada), não a gravação. Trocado por um teste de morte com o store
   grande, que é onde a janela de vulnerabilidade realmente cresce em quem reescreve tudo.

**Determinismo verificado:** a camada INVARIANTE foi rodada três vezes contra cada referência e
deu o mesmo placar nas três.

---

## 5 · Desenho pareado por assento

Com n=2 por domínio, o assento não pode ser uma fonte de variação. Então os dois braços da mesma
rodada rodam no **mesmo** assento, e a diferença A contra B dentro da rodada fica livre dele.

| rodada | domínio | assento de execução (os dois braços) |
|---|---|---|
| 1 | store | `claude-mm1` |
| 2 | store | `claude-mm2` |
| 3 | indexador | `claude` (premium) |
| 4 | indexador | `claude-mm1` |

Cada braço vê o mesmo conjunto: mm1 duas vezes, mm2 uma, premium uma. O número da rodada decide
domínio **e** assento, numa tabela só dentro do `rodar.sh`.

---

## 6 · Modelo por fase

```
PLANEJAR   compozy session prompt --provider claude --model claude-opus-5
           premium + Opus, IGUAL nas oito rodadas

EXECUTAR   compozy loop run --runtime worker=<assento>/sonnet
                            --runtime judge=<assento>/sonnet
                            + os quatro inputs de runtime do implement-tasks
```

É o padrão de uso do operador, e foi validado de ponta a ponta no A/B nº 2: a auditoria mostrou 1
sessão em premium/Opus e 4 a 9 em Sonnet no assento certo, em todas as seis rodadas, por duas
fontes independentes.

Rodar a execução em Sonnet **ajuda** a pergunta: um executor mais barato depende mais do plano.

---

## 7 · O que vem pronto do A/B nº 2

Os três consertos continuam, cada um vindo de uma falha observada:

| # | conserto | veio de |
|---|---|---|
| 1 | gate de cota real (`claude -p --max-turns 1`), porque `auth status` diz `authenticated` com a cota zerada | uma rodada queimou 2h20 para produzir 0/0 |
| 2 | abortar em `rate_limited` lendo o literal no log do daemon, marcando `INVALIDA.txt` | uma rodada seguiu 1h produzindo lixo |
| 3 | lockfile de driver com `flock -n`, que **recusa** em vez de enfileirar | dois drivers rodaram juntos e dobraram a queima |

E também: porta de artefato, cancelamento de run órfão, saneador de frontmatter nos dois braços,
teto de 4h por Loop, e matar daemon só casando o `COMPOZY_HOME` da rodada.

**Novo aqui:** o `RESUMO.txt` grava `saneador_agiu`, para eu poder dizer com que frequência o bug
do YAML aparece, em vez de só afirmar que ele existe.

---

## 8 · Medição e regra de decisão

**Primária: total de testes da camada primária que passam, somado por braço.**

Somar teste, não média de rodada. Com n=2 por domínio, a média de duas rodadas tem resolução
péssima; o total de testes tem resolução fina. Por braço: 2 × 10 (store) + 2 × 12 (indexador) =
**44 testes**.

| # | métrica | fonte | tipo |
|---|---|---|---|
| **1** | **primária somada, de 44** | suíte oculta | **primária** |
| 2 | primária por domínio | suíte oculta | secundária |
| 3 | ROBUSTEZ e BASE | suíte oculta | guarda |
| 4 | `make test` do repo entregue | o repo | guarda |
| 5 | estado terminal e tempo dos Loops | `compozy loop status` | secundária |
| 6 | assento e modelo efetivos | `sessions/*/meta.json` | auditoria |
| 7 | `saneador_agiu` | `saneamento.txt` | auditoria |

**Regra de decisão, fixada agora:** empate se a diferença dos percentuais somados for menor que
**10 pontos**.

**Não haverá teste estatístico.** Com n=2 por domínio não há poder para sustentar um, e fingir
que há seria pior que não ter.

Rodada com `INVALIDA.txt` não entra em soma nenhuma.

---

## 9 · Ordem e ensaio obrigatório

```
B1 · A1 · A2 · B2 · B3 · A3 · A4 · B4
```

Alterna braço e alterna domínio, e nunca empilha o mesmo braço duas vezes seguidas no mesmo
domínio.

**A B1 roda sozinha primeiro** (`executar.sh ensaio`). As outras sete só saem quando ela devolver
um placar real. O `executar.sh restantes` tem portão: recusa se a `B-1` não tiver `RESUMO.txt`.

---

## 10 · O que não muda

| constante | valor | motivo |
|---|---|---|
| commit de partida, store | `1e75e8bee75410934f4e35547f5110d04cadb6c8` | as 4 rodadas do domínio clonam do mesmo |
| commit de partida, indexador | `d7e4e336551f37710e8124e6ee139d0afdd15655` | idem |
| CompozyOS | `0.3.0-beta.27` | a mesma do A/B nº 2 |
| adaptador ACP | `0.77.0`, travado nos três assentos | `@latest` andaria entre os braços |
| papéis de fundo | os seis desligados | senão haveria outro consumidor de assento na conta |
| `COMPOZY_HOME` | isolado por rodada | o `~/.compozy` do operador roteia para mm1/mm2 e contaminaria |
| saneador | roda nos **dois** braços | o braço B nunca precisa, mas simetria manda |

---

## 11 · Limitações, ditas antes e não depois

1. **n=2 por domínio não sustenta veredito de equivalência.** Uma rodada fora da curva move
   metade da média daquele domínio. Foi escolha do operador cobrir dois domínios em vez de um com
   n=3, com a ressalva registrada na hora.
2. **Duas tarefas não são "programação".** O resultado vale para estas duas armadilhas, não para
   desenvolvimento em geral.
3. **A suíte é minha.** A calibragem contra duas referências limita o viés, mas não o elimina.
4. **Empate no teto continua possível.** Se os dois braços evitarem as duas armadilhas, o
   resultado é que ambos os métodos as evitam nesta tarefa. É um achado legítimo, só não é um
   desempate.

---

## 12 · Artefatos congelados

Os md5 estão em `CONGELADO-V4.md5`, gerado na mesma hora deste arquivo. Qualquer mudança neles
depois de congelado é desvio e vai para `resultados/INTERVENCOES.md`, com motivo e hora.
