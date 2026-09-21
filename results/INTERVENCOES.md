# Intervencoes · A/B nº 3

Tudo que mudou depois do congelamento, com motivo e hora.

## 2026-09-20 · ensaio B1 reprovado por gate de cota rigido demais

O ensaio abortou em 14s, antes de gastar qualquer token de agente. O gate de cota recusou o
assento `claude-mm1` com:

    Failed to refresh OAuth token: another Claude Code process is refreshing it or exited
    mid-refresh. This is usually transient; retry in a minute

**Causa, medida e nao suposta:** o daemon permanente do operador usa `claude-mm1` e
`claude-mm2` nos `[roles]` dele, e o refresh de token colidiu com a sonda. Havia tambem tres
processos `claude` vivos na maquina. Nao e' falta de cota: e' disputa de refresh.

**Conserto.** O `gate_cota` passou a separar as duas coisas:

- mensagem com `usage limit`, `rate limit`, `quota`, `limit reached` ou `session limit`
  -> cota esgotada mesmo, aborta na hora, sem insistir
- qualquer outra falha -> transitoria, ate 4 tentativas com 45s entre elas

Derrubar a rodada por um soluco de 30 segundos seria jogar fora hora de fila.

- `rodar.sh` md5 antes: `b560d96554c9aa853ee7ac28ff50c870`
- `rodar.sh` md5 depois: ver `CONGELADO-V4.md5`
- Nenhum token de agente foi gasto antes desta mudanca, e nenhuma medicao existia.

**Isto e' o ensaio fazendo o trabalho dele.** Nas execucoes anteriores eu lancava tudo de uma vez
e descobria esse tipo de coisa depois de perder rodadas.

## 2026-09-20 · sete rodadas perdidas por token revogado, e o conserto que veio disso

Entre 13:10 e 13:36 as sete rodadas restantes falharam. **Causa unica**, e nao e' planejamento:

| rodada | sintoma |
|---|---|
| A1 | `401 OAuth access token has been revoked` no meio da sessao de planejamento |
| A2, B2, B3, A3, A4, B4 | `OAuth session expired and could not be refreshed` no gate, nas 4 tentativas |

O operador refez o login e os tres assentos voltaram a responder. As sete foram para
`bancada/arquivo/ab3-rodadas-auth-revogada-2026-09-20/`, com `ORIGEM.txt`.

### O defeito que isso expos, e ele era serio

Na A1 o `cy-create-spec` ja tinha escrito **66 KB de artefato** (`_spec.md`, `_tests.md`,
`_user_stories.md`, `_dx.md`, dois ADRs) quando o token morreu. O `cy-create-tasks` nunca rodou.
A porta de artefato entao matou a rodada com:

    planejamento nao produziu task em .../tasks/kvstore

**Isso e' uma falha de auth sendo contada contra o metodo de planejamento.** Num A/B
pre-registrado e' exatamente o tipo de erro que enviesa o resultado em silencio, e o pior deles,
porque nao parece erro: parece medicao.

**Conserto.** O detector de `rate_limit` virou `checar_falha_provedor`, e agora cobre todas as
falhas que vem do provedor e nao do trabalho:

    rate_limit · not_authenticated · authentication_failed
    token has been revoked · OAuth session expired

Ele varre o log do daemon E os logs da sessao de planejamento, e roda **antes** da porta de
artefato. Rodada nessas condicoes vira `INVALIDA.txt`, nao nota baixa.

### Correcao de um numero errado no relatorio

A tabela de calibragem do `executar.sh` dizia `store / ingenua 6/10`. Esse valor era da versao do
teste de morte por sorteio, que foi trocada pelo gatilho deterministico ainda na calibragem. O
valor medido tres vezes seguidas e' **3/10**. Corrigido.

- `rodar.sh` md5 antes: `5ca64dfd4c465d294d7e82fa6806961a`
- `executar.sh` md5 antes: `0cdafd6e30265dd927abb3cb690289dd`
- os dois depois: ver `CONGELADO-V4.md5`
- A B1 continua valida e nao foi tocada: ela rodou antes de tudo isto e seu `RESUMO.txt` esta intacto.

## 2026-09-20 14:53 · a mm1 estourou a cota, e a fila parava inteira por causa de um assento

A A1 chegou ate a fase `review-and-fix` e entao o assento `claude-mm1` respondeu
`You've hit your session limit · resets 5:40pm`. O detector novo marcou `INVALIDA.txt` e parou.
Esse pedaco funcionou como devia.

**Medi os tres assentos no minuto seguinte:**

| assento | estado as 14:54 |
|---|---|
| premium | ok |
| claude-mm1 | esgotado ate 17:40 |
| claude-mm2 | ok |

### O defeito

O driver parava a fila INTEIRA quando um assento estourava. Mas cada assento tem cota propria:
com mm2 e premium livres, as rodadas A2, B2, B3 e A3 poderiam ter rodado. Ficaram paradas a toa.

### Conserto: fila em passadas

- rodada barrada pelo gate de cota nao derruba a fila, so fica para a proxima passada
- rodada invalidada no meio vai para `resultados/_invalidas/<item>-<hora>/`, com a evidencia
  inteira, e volta para a fila
- entre passadas o driver **le a hora do reset da propria mensagem de cota** e espera ate la
  sozinho, ate 4 passadas ou 6h de espera

A ordem pre-registrada continua sendo a ordem de tentativa dentro de cada passada. O que muda e'
que uma rodada impedida por cota e' pulada em vez de travar as seguintes.

**O pareamento, que e' a propriedade de desenho que importa, nao e' afetado:** A e B de mesmo
numero continuam no mesmo assento, so nao necessariamente no mesmo horario.

- `executar.sh` md5 antes: `0141e865e86bf97ef52b0d26378b54af`
- depois: ver `CONGELADO-V4.md5`
- A B1 continua valida e intacta.
