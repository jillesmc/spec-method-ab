# Resultado do A/B nº 3 · tarefa com armadilha · dois dominios

Gerado em 2026-09-21T04:02:52-03:00. Regras em PRE-REGISTRO-V4.md, congelado antes da primeira
execucao. Desvios em resultados/INTERVENCOES.md.

Planejamento: **premium / claude-opus-5** nas oito rodadas.
Execucao: **sonnet**. Assento PAREADO: A e B da mesma rodada usam o mesmo.

| rodada | dominio | assento | **PRIMARIA** | robustez | base | make test | implement | review |
|---|---|---|---|---|---|---|---|---|
| B1 | store | claude-mm1/sonnet | **9/10** | 12/12 | 8/8 | 0 | done (745s) | done (202s) |
| A1 | store | claude-mm1/sonnet | **9/10** | 12/12 | 8/8 | 0 | done (2617s) | done (201s) |
| B2 | store | claude-mm2/sonnet | **9/10** | 12/12 | 8/8 | 0 | done (2799s) | done (725s) |
| A2 | store | claude-mm2/sonnet | **10/10** | 12/12 | 8/8 | 0 | done (2175s) | done (181s) |
| B3 | indexador | claude/sonnet | **12/12** | 10/10 | 8/8 | 0 | done (705s) | done (806s) |
| A3 | indexador | claude/sonnet | **12/12** | 10/10 | 8/8 | 0 | done (1087s) | done (543s) |
| B4 | indexador | claude-mm1/sonnet | **12/12** | 10/10 | 8/8 | 0 | done (704s) | done (101s) |
| A4 | indexador | claude-mm1/sonnet | **12/12** | 10/10 | 8/8 | 0 | done (926s) | failed (3284s) |

## Veredito

A camada primaria e' **INVARIANTE** no dominio store (durabilidade sob morte do
processo) e **ORACULO** no indexador (incremental == reconstrucao do zero).

| | store (2 rodadas) | indexador (2 rodadas) | **somado** |
|---|---|---|---|
| **Braco A** (spec-cycle) | 19/20 (95%) | 24/24 (100%) | **43/44 (98%)** |
| **Braco B** (OpenSpec) | 18/20 (90%) | 24/24 (100%) | **42/44 (95%)** |

Rodadas validas: braco A 4 de 4, braco B 4 de 4.

**Regra de decisao, pre-registrada:** empate se a diferenca dos percentuais somados
for menor que 10 pontos. Nao ha teste estatistico: com n=2 por dominio nao haveria
poder para sustentar um, e fingir que ha seria pior que nao ter.

## Calibragem das suites, medida antes de qualquer rodada

As duas armadilhas foram provadas contra implementacoes de referencia escritas a mao,
antes de gastar token. Sem isto, "a suite discrimina" seria opiniao.

| dominio | referencia | base | robustez | **primaria** |
|---|---|---|---|---|
| store | cuidadosa | 8/8 | 12/12 | **10/10** |
| store | ingenua (reescreve o arquivo inteiro) | 8/8 | 12/12 | **3/10** |
| indexador | cuidadosa | 8/8 | 10/10 | **12/12** |
| indexador | ingenua (cache por mtime) | 8/8 | 10/10 | **8/12** |

A ingenua passa em TUDO menos na camada que importa. E' o que faltava nos dois A/B
anteriores, onde os dois bracos bateram no teto e o experimento empatou.

## Auditoria de assento

Medida, nao declarada: contagem de pares provider/model nos meta.json das sessoes
que o daemon de cada rodada abriu. O par de rodadas A e B de mesmo numero tem que
mostrar o mesmo assento, senao o desenho pareado nao valeu.

| rodada | declarado (exec) | medido |
|---|---|---|
| B1 | claude-mm1/sonnet | claude/claude-opus-5:1 claude-mm1/sonnet:5 |
| A1 | claude-mm1/sonnet | claude/claude-opus-5:1 claude-mm1/sonnet:5 |
| B2 | claude-mm2/sonnet | claude/claude-opus-5:1 claude-mm2/sonnet:9 |
| A2 | claude-mm2/sonnet | claude/claude-opus-5:1 claude-mm2/sonnet:4 |
| B3 | claude/sonnet | claude/claude-opus-5:1 claude/sonnet:10 |
| A3 | claude/sonnet | claude/claude-opus-5:1 claude/sonnet:6 |
| B4 | claude-mm1/sonnet | claude/claude-opus-5:1 claude-mm1/sonnet:6 |
| A4 | claude-mm1/sonnet | claude/claude-opus-5:1 claude-mm1/sonnet:19 |

## Ressalvas obrigatorias na leitura

1. **n=2 por dominio nao sustenta veredito de equivalencia.** Uma rodada fora da
   curva move metade da media daquele dominio. O somado por TESTE tem resolucao
   melhor que o somado por rodada, e e' por isso que o veredito le o somado.
2. O bug do YAML do `cy-create-tasks` e' real mas INTERMITENTE: depende do titulo
   que o agente escreve. O saneador roda nos dois bracos; `saneador_agiu` em cada
   rodada diz se ele precisou mexer.
3. Planejamento e execucao rodam em modelos diferentes por desenho. O que se compara
   e' a qualidade do PLANO, com a execucao constante nos dois bracos.
