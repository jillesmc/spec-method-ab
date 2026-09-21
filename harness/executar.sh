#!/usr/bin/env bash
# Driver unico do A/B nº 3.
#
#   executar.sh ensaio       roda SO a B1, e para. Portao das outras sete.
#   executar.sh restantes    A1 A2 B2 B3 A3 A4 B4, na ordem pre-registrada
#   executar.sh relatorio    gera resultados/RESULTADO.md do que existir
#
# LOCKFILE: um driver por vez. A segunda invocacao recusa na hora em vez de
# entrar em fila, porque esperar escondia o erro em vez de mostra-lo. Veio da
# v2 do A/B nº 2, onde dois drivers rodaram juntos e dobraram a queima de cota.
set -uo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
DIARIO="$AQUI/resultados/SEQUENCIA.log"
TRAVA="$AQUI/.driver.lock"

# Ordem pre-registrada. Alterna braco e alterna dominio, e nunca empilha o
# mesmo braco duas vezes seguidas no mesmo dominio.
FILA_COMPLETA=(B1 A1 A2 B2 B3 A3 A4 B4)

registrar() { printf '%s  %s\n' "$(date -Is)" "$*" | tee -a "$DIARIO"; }

# Arquiva uma rodada invalidada, com o motivo, para ela poder ser refeita sem
# apagar a evidencia de por que caiu.
arquivar_invalida() {
  local item="$1" dir="$AQUI/resultados/${1:0:1}-${1:1:1}" destino
  destino="$AQUI/resultados/_invalidas/${item}-$(date +%H%M%S)"
  mkdir -p "$(dirname "$destino")"
  mv "$dir" "$destino" 2>/dev/null
  mv "$AQUI/resultados/${item}.log" "$destino/" 2>/dev/null
  registrar "  $item arquivada em $(basename "$destino")"
}

# Le "resets 5:40pm" da mensagem de cota e devolve quantos segundos faltam.
# Sem isto eu teria que ficar perguntando de hora em hora se a cota voltou.
segundos_ate_reset() {
  local msg="$1" hora alvo agora
  hora=$(printf '%s' "$msg" | grep -oiE 'resets [0-9]{1,2}:[0-9]{2} ?(am|pm)?' | head -1 | sed 's/[Rr]esets //')
  [ -n "$hora" ] || return 1
  alvo=$(date -d "$hora" +%s 2>/dev/null) || return 1
  agora=$(date +%s)
  [ "$alvo" -le "$agora" ] && alvo=$((alvo + 86400))
  printf '%s' $((alvo - agora + 180))
}

uma_rodada() {
  local item="$1" braco="${1:0:1}" n="${1:1:1}" t0 st
  if [ -f "$AQUI/resultados/${braco}-${n}/RESUMO.txt" ]; then
    return 0
  fi
  registrar "$item comecando"
  t0=$(date +%s)
  "$AQUI/rodar.sh" tudo "$braco" "$n" >"$AQUI/resultados/${item}.log" 2>&1
  st=$?
  "$AQUI/rodar.sh" encerrar "$braco" "$n" >/dev/null 2>&1
  registrar "$item terminou status=$st em $(( $(date +%s) - t0 ))s"
  if [ -f "$AQUI/resultados/${braco}-${n}/INVALIDA.txt" ]; then
    registrar "  $item INVALIDA:"
    sed 's/^/    /' "$AQUI/resultados/${braco}-${n}/INVALIDA.txt" | head -5 | tee -a "$DIARIO"
    ULTIMA_MENSAGEM=$(grep -ho "resets [0-9:apm ]*" "$AQUI/resultados/${braco}-${n}/INVALIDA.txt" 2>/dev/null | head -1)
    arquivar_invalida "$item"
    return 11
  fi
  if [ -f "$AQUI/resultados/${braco}-${n}/RESUMO.txt" ]; then
    sed 's/^/    /' "$AQUI/resultados/${braco}-${n}/RESUMO.txt" | tee -a "$DIARIO"
    return 0
  fi
  # Sem RESUMO e sem INVALIDA: o gate de cota barrou antes de comecar. Nao e'
  # perda, e' economia. A rodada fica para a proxima passada.
  ULTIMA_MENSAGEM=$(grep -ho "resets [0-9:apm ]*" "$AQUI/resultados/${item}.log" 2>/dev/null | head -1)
  registrar "  $item adiada (ver resultados/${item}.log)"
  return 1
}

cmd_ensaio() {
  registrar "ENSAIO: so a B1 (dominio store). As outras sete so saem depois."
  "$AQUI/rodar.sh" semear B 1
  uma_rodada B1
  local rc=$?
  if [ "$rc" = 0 ]; then
    registrar "ENSAIO APROVADO. Proximo: executar.sh restantes"
  else
    registrar "ENSAIO REPROVADO (rc=$rc). NAO lance as outras: conserte antes."
  fi
  return $rc
}

cmd_restantes() {
  [ -f "$AQUI/resultados/B-1/RESUMO.txt" ] || {
    registrar "portao fechado: a B1 nao produziu RESUMO. Rode 'executar.sh ensaio' primeiro."
    exit 3
  }
  "$AQUI/rodar.sh" semear A 3 >/dev/null 2>&1

  # EM PASSADAS, e nao numa varrida so. Cada assento tem cota propria, entao
  # uma rodada barrada por cota nao diz nada sobre as outras: a versao anterior
  # parava a fila inteira quando UM assento estourava, e as rodadas dos outros
  # dois assentos ficavam paradas a toa.
  #
  # Entre passadas, se algum assento avisou a hora em que a cota volta, o
  # driver espera ate la sozinho. Melhor ele dormir do que eu perguntar de hora
  # em hora se ja deu.
  local passada item pendentes progresso
  ULTIMA_MENSAGEM=""
  for passada in 1 2 3 4; do
    progresso=0
    pendentes=()
    for item in "${FILA_COMPLETA[@]:1}"; do
      [ -f "$AQUI/resultados/${item:0:1}-${item:1:1}/RESUMO.txt" ] && continue
      pendentes+=("$item")
    done
    [ ${#pendentes[@]} -eq 0 ] && { registrar "todas as rodadas fecharam"; break; }
    registrar "passada $passada, pendentes: ${pendentes[*]}"
    for item in "${pendentes[@]}"; do
      uma_rodada "$item"
      [ -f "$AQUI/resultados/${item:0:1}-${item:1:1}/RESUMO.txt" ] && progresso=$((progresso + 1))
    done
    pendentes=()
    for item in "${FILA_COMPLETA[@]:1}"; do
      [ -f "$AQUI/resultados/${item:0:1}-${item:1:1}/RESUMO.txt" ] && continue
      pendentes+=("$item")
    done
    [ ${#pendentes[@]} -eq 0 ] && { registrar "todas as rodadas fecharam"; break; }

    local espera=""
    [ -n "$ULTIMA_MENSAGEM" ] && espera=$(segundos_ate_reset "$ULTIMA_MENSAGEM")
    if [ -z "$espera" ] || [ "$espera" -gt 21600 ]; then
      registrar "passada $passada: $progresso rodada(s) fecharam, ${#pendentes[@]} pendente(s), e nao sei quando a cota volta. Parando."
      break
    fi
    registrar "passada $passada: $progresso fecharam. Esperando ${espera}s ate a cota voltar ($ULTIMA_MENSAGEM)."
    sleep "$espera"
    ULTIMA_MENSAGEM=""
  done
  cmd_relatorio
}

# ---------------------------------------------------------------- relatorio
cmd_relatorio() {
  campo() { sed -n "s/^$2=//p" "$1" 2>/dev/null | head -1; }
  # O "diga" do esperar_run escreve no mesmo canal de onde o estado terminal e
  # capturado, entao o campo sai como "implement-tasks: done em 1168sdone".
  # O estado real e' o sufixo e o tempo esta no meio.
  estado() { campo "$1" "$2" | grep -oE '(done|no-op|blocked|failed|exhausted|stalled|timeout|rate-limited)$'; }
  duracao() { campo "$1" "$2" | grep -oE '[0-9]+s' | tail -1; }
  resumo() { printf '%s/resultados/%s-%s/RESUMO.txt' "$AQUI" "${1:0:1}" "${1:1:1}"; }
  invalida() { [ -f "$AQUI/resultados/${1:0:1}-${1:1:1}/INVALIDA.txt" ]; }

  # "passou total" somado sobre as rodadas validas de um braco num dominio.
  # Somar TESTE, nao media de rodada: com n=2 por dominio a media de duas
  # rodadas tem resolucao pessima, e o total de testes tem resolucao fina.
  somar() {  # <braco> <rodadas...> -> "passou total validas"
    local b="$1"; shift
    local soma=0 tot=0 validas=0 v f
    for n in "$@"; do
      invalida "$b$n" && continue
      f="$(resumo "$b$n")"
      v=$(campo "$f" primaria)
      [ -n "$v" ] || continue
      soma=$((soma + ${v%%/*})); tot=$((tot + ${v##*/})); validas=$((validas + 1))
    done
    printf '%s %s %s' "$soma" "$tot" "$validas"
  }
  pct() { [ "${2:-0}" -gt 0 ] && awk "BEGIN{printf \"%.0f\", 100*$1/$2}" || printf -- '--'; }

  {
    echo "# Resultado do A/B nº 3 · tarefa com armadilha · dois dominios"
    echo
    echo "Gerado em $(date -Is). Regras em PRE-REGISTRO-V4.md, congelado antes da primeira"
    echo "execucao. Desvios em resultados/INTERVENCOES.md."
    echo
    echo "Planejamento: **premium / claude-opus-5** nas oito rodadas."
    echo "Execucao: **sonnet**. Assento PAREADO: A e B da mesma rodada usam o mesmo."
    echo
    echo "| rodada | dominio | assento | **PRIMARIA** | robustez | base | make test | implement | review |"
    echo "|---|---|---|---|---|---|---|---|---|"
    local item f
    for item in B1 A1 B2 A2 B3 A3 B4 A4; do
      f="$(resumo "$item")"
      if invalida "$item"; then
        printf '| %s | -- | -- | INVALIDA | -- | -- | -- | -- | -- |\n' "$item"
      elif [ -f "$f" ]; then
        printf '| %s | %s | %s | **%s** | %s | %s | %s | %s (%s) | %s (%s) |\n' "$item" \
          "$(campo "$f" dominio)" "$(campo "$f" assento_exec)" \
          "$(campo "$f" primaria)" "$(campo "$f" robustez)" "$(campo "$f" base)" \
          "$(sed -n 's/^make_test=make-test=//p' "$f" | head -1)" \
          "$(estado "$f" implement_estado)" "$(duracao "$f" implement_estado)" \
          "$(estado "$f" review_estado)" "$(duracao "$f" review_estado)"
      else
        printf '| %s | -- | -- | nao rodou | -- | -- | -- | -- | -- |\n' "$item"
      fi
    done
    echo
    echo "## Veredito"
    echo
    echo "A camada primaria e' **INVARIANTE** no dominio store (durabilidade sob morte do"
    echo "processo) e **ORACULO** no indexador (incremental == reconstrucao do zero)."
    echo
    echo "| | store (2 rodadas) | indexador (2 rodadas) | **somado** |"
    echo "|---|---|---|---|"
    local b sa ta va si ti vi
    for b in A B; do
      read -r sa ta va <<< "$(somar "$b" 1 2)"
      read -r si ti vi <<< "$(somar "$b" 3 4)"
      printf '| **Braco %s** (%s) | %s/%s (%s%%) | %s/%s (%s%%) | **%s/%s (%s%%)** |\n' \
        "$b" "$([ "$b" = A ] && echo spec-cycle || echo OpenSpec)" \
        "$sa" "$ta" "$(pct "$sa" "$ta")" \
        "$si" "$ti" "$(pct "$si" "$ti")" \
        "$((sa + si))" "$((ta + ti))" "$(pct "$((sa + si))" "$((ta + ti))")"
    done
    echo
    read -r sa ta va <<< "$(somar A 1 2 3 4)"
    read -r si ti vi <<< "$(somar B 1 2 3 4)"
    echo "Rodadas validas: braco A $va de 4, braco B $vi de 4."
    echo
    echo "**Regra de decisao, pre-registrada:** empate se a diferenca dos percentuais somados"
    echo "for menor que 10 pontos. Nao ha teste estatistico: com n=2 por dominio nao haveria"
    echo "poder para sustentar um, e fingir que ha seria pior que nao ter."
    echo
    echo "## Calibragem das suites, medida antes de qualquer rodada"
    echo
    echo "As duas armadilhas foram provadas contra implementacoes de referencia escritas a mao,"
    echo "antes de gastar token. Sem isto, \"a suite discrimina\" seria opiniao."
    echo
    echo "| dominio | referencia | base | robustez | **primaria** |"
    echo "|---|---|---|---|---|"
    echo "| store | cuidadosa | 8/8 | 12/12 | **10/10** |"
    echo "| store | ingenua (reescreve o arquivo inteiro) | 8/8 | 12/12 | **3/10** |"
    echo "| indexador | cuidadosa | 8/8 | 10/10 | **12/12** |"
    echo "| indexador | ingenua (cache por mtime) | 8/8 | 10/10 | **8/12** |"
    echo
    echo "A ingenua passa em TUDO menos na camada que importa. E' o que faltava nos dois A/B"
    echo "anteriores, onde os dois bracos bateram no teto e o experimento empatou."
    echo
    echo "## Auditoria de assento"
    echo
    echo "Medida, nao declarada: contagem de pares provider/model nos meta.json das sessoes"
    echo "que o daemon de cada rodada abriu. O par de rodadas A e B de mesmo numero tem que"
    echo "mostrar o mesmo assento, senao o desenho pareado nao valeu."
    echo
    echo "| rodada | declarado (exec) | medido |"
    echo "|---|---|---|"
    for item in B1 A1 B2 A2 B3 A3 B4 A4; do
      f="$(resumo "$item")"
      [ -f "$f" ] || continue
      printf '| %s | %s | %s |\n' "$item" "$(campo "$f" assento_exec)" "$(campo "$f" assentos_medidos)"
    done
    echo
    echo "## Ressalvas obrigatorias na leitura"
    echo
    echo "1. **n=2 por dominio nao sustenta veredito de equivalencia.** Uma rodada fora da"
    echo "   curva move metade da media daquele dominio. O somado por TESTE tem resolucao"
    echo "   melhor que o somado por rodada, e e' por isso que o veredito le o somado."
    echo "2. O bug do YAML do \`cy-create-tasks\` e' real mas INTERMITENTE: depende do titulo"
    echo "   que o agente escreve. O saneador roda nos dois bracos; \`saneador_agiu\` em cada"
    echo "   rodada diz se ele precisou mexer."
    echo "3. Planejamento e execucao rodam em modelos diferentes por desenho. O que se compara"
    echo "   e' a qualidade do PLANO, com a execucao constante nos dois bracos."
  } > "$AQUI/resultados/RESULTADO.md"
  registrar "RESULTADO.md escrito"
}

acao="${1:-}"
case "$acao" in
  ensaio|restantes|relatorio) : ;;
  *) sed -n '2,15p' "$0" | sed 's/^# \?//'; exit 2 ;;
esac

if [ "$acao" = relatorio ]; then cmd_relatorio; exit $?; fi

exec 9>"$TRAVA"
flock -n 9 || { echo "ja existe um driver rodando (trava $TRAVA). Um por vez." >&2; exit 1; }

case "$acao" in
  ensaio)    cmd_ensaio ;;
  restantes) cmd_restantes ;;
esac
