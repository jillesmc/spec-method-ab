#!/usr/bin/env bash
# Executa UMA rodada do A/B. Desenho v3: modelo por fase.
#
#   rodar.sh semear    <A|B> <n>   cria o repo-semente do dominio daquela rodada
#   rodar.sh preparar  <A|B> <n>   home isolado + daemon + clone do commit canonico
#   rodar.sh planejar  <A|B> <n>   a camada que difere entre os bracos (premium/Opus)
#   rodar.sh implementar <A|B> <n> loop implement-tasks (assento da rodada/Sonnet)
#   rodar.sh revisar   <A|B> <n>   loop review-and-fix  (assento da rodada/Sonnet)
#   rodar.sh medir     <A|B> <n>   suite oculta + make test + auditoria de assento
#   rodar.sh encerrar  <A|B> <n>   derruba o daemon da rodada
#   rodar.sh tudo      <A|B> <n>   as seis acima em ordem
#
# MODELO POR FASE, que e a mudanca da v3:
#   PLANEJAR   provider claude (premium) + claude-opus-5, IGUAL nos dois bracos
#   EXECUTAR   provider do rodizio + sonnet, via --runtime worker=/judge=
# O planejamento e a fatia curta. Execucao mais revisao foram 82% do tempo nas
# medicoes anteriores, e e essa fatia que desce para Sonnet.
#
# DESENHO PAREADO. O numero da rodada decide dominio E assento, e os dois
# bracos da mesma rodada usam o MESMO assento. Assim a comparacao A contra B
# dentro de uma rodada fica livre de efeito de assento, que com n=2 por dominio
# vale mais que rodizio.
#
#   n=1  store      claude-mm1
#   n=2  store      claude-mm2
#   n=3  indexador  claude (premium)
#   n=4  indexador  claude-mm1
#
# Cada braco ve o mesmo conjunto de assentos: mm1 duas vezes, mm2 uma, premium
# uma.
#
# ISOLAMENTO: COMPOZY_HOME proprio por rodada e porta propria. O ~/.compozy do
# operador nao e lido nem escrito.
set -uo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
CONVERSOR="$AQUI/../instrumento/openspec-importar.py"
SANEADOR="$AQUI/../instrumento/sanear-tasks.py"
LIGADOR="$AQUI/../instrumento/openspec.sh"
PORTA_BASE=2210
ACP_VER='0.77.0'   # travado: @latest andaria entre os bracos
MODELO_PLANO="claude-opus-5"
MODELO_EXEC="sonnet"
ASSENTO_PLANO="claude"   # premium, igual nas seis rodadas
ESPERA_PLANO="25m"       # o CLI recusa acima de 30m
TETO_LOOP=14400          # 4h por Loop

BRACO="${2:-}"; N="${3:-}"
# Diferente da v3: o "semear" tambem precisa de braco e rodada, porque e' a
# rodada que diz de qual dominio e' a semente.
[[ "$BRACO" =~ ^[AB]$ ]] || { echo "braco tem que ser A ou B" >&2; exit 2; }
[[ "$N" =~ ^[1-4]$ ]]    || { echo "n tem que ser 1..4" >&2; exit 2; }

# Dominio e assento saem os dois do numero da rodada. Uma tabela so.
DOMINIO=""
ASSENTO_EXEC=""
case "$N" in
  1) DOMINIO="store";     ASSENTO_EXEC="claude-mm1" ;;
  2) DOMINIO="store";     ASSENTO_EXEC="claude-mm2" ;;
  3) DOMINIO="indexador"; ASSENTO_EXEC="claude" ;;
  4) DOMINIO="indexador"; ASSENTO_EXEC="claude-mm1" ;;
  *) echo "rodada tem que ser 1..4 (1-2 store, 3-4 indexador)" >&2; exit 2 ;;
esac
case "$DOMINIO" in
  store)     PACOTE="kvstore"; PRIMARIA="TestInvariante" ;;
  indexador) PACOTE="fidx";    PRIMARIA="TestOraculo" ;;
esac
FIXTURE="$AQUI/fixture/$DOMINIO"
SEMENTE="$AQUI/.semente-$DOMINIO"
SLUG_A="$PACOTE"
SLUG_B="os-$PACOTE"
SAIDA="$AQUI/resultados/${BRACO}-${N}"
export COMPOZY_HOME="$SAIDA/home"
REPO="$SAIDA/repo"
LOG="$SAIDA/daemon.log"
WS="vago-${BRACO}${N}"

# Porta e slug so existem quando ha braco. "semear" roda sem os dois, e
# BRACO == "A" dentro de $(( )) seria lido como variavel aritmetica, nao string.
PORTA=0
SLUG=""
if [ "$BRACO" = "A" ]; then
  PORTA=$((PORTA_BASE + N * 2)); SLUG="$SLUG_A"
else
  PORTA=$((PORTA_BASE + N * 2 + 1)); SLUG="$SLUG_B"
fi

diga() { printf '  %s\n' "$*"; }

# Diretorio de credencial de cada assento. Unica funcao que sabe esse mapa.
dir_do_assento() {
  case "$1" in
    claude)     printf '%s/.claude' "$HOME" ;;
    claude-mm1) printf '%s/.claude-mm1' "$HOME" ;;
    claude-mm2) printf '%s/.claude-mm2' "$HOME" ;;
    *) return 1 ;;
  esac
}

# ------------------------------------------------------------ gate de cota
# CONSERTO 1 da v3. O gate antigo lia "compozy-claude-auth-status", que devolve
# "authenticated" mesmo com a cota zerada: uma rodada queimou 2h20 para produzir
# 0/0. Aqui a checagem e uma chamada REAL ao provider, de poucos tokens, que so
# passa se o assento puder de fato trabalhar agora.
gate_cota() {
  local assento="$1" dir resposta rc tentativa
  dir="$(dir_do_assento "$assento")" || { echo "assento desconhecido: $assento" >&2; return 1; }
  for tentativa in 1 2 3 4; do
    resposta=$(CLAUDE_CONFIG_DIR="$dir" timeout 150 claude -p --model "$MODELO_EXEC" \
               --max-turns 1 'responda apenas: ok' 2>&1)
    rc=$?
    # Cota de verdade acabou: nao adianta insistir, a rodada nao comeca.
    if printf '%s' "$resposta" | grep -qiE 'usage limit|rate limit|quota|limit reached|session limit'; then
      echo "cota esgotada no assento $assento: $(printf '%s' "$resposta" | head -1)" >&2
      return 1
    fi
    [ "$rc" = 0 ] && { diga "cota   : $assento respondeu, pode trabalhar${tentativa:+ (tentativa $tentativa)}"; return 0; }
    # Falha transitoria. A mais comum aqui e' disputa de refresh de OAuth: o
    # daemon permanente do operador usa claude-mm1 e claude-mm2 nos papeis
    # dele, e o proprio CLI diz "this is usually transient; retry in a minute".
    # Derrubar a rodada por isso seria jogar fora hora de fila por um soluco
    # de 30 segundos.
    diga "cota   : $assento falhou na tentativa $tentativa, tentando de novo"
    printf '    %s\n' "$(printf '%s' "$resposta" | head -1 | cut -c1-140)" >&2
    [ "$tentativa" -lt 4 ] && sleep 45
  done
  echo "assento $assento nao respondeu em 4 tentativas: $(printf '%s' "$resposta" | head -1)" >&2
  return 1
}

# ---------------------------------------------------------------- semear
# Um unico commit canonico. Todas as 6 rodadas clonam DAQUI, entao "mesmo
# commit de partida" e literal, nao aproximado.
cmd_semear() {
  [ -d "$SEMENTE" ] && { diga "semente ja existe: $(git -C "$SEMENTE" rev-parse --short HEAD)"; return 0; }
  mkdir -p "$SEMENTE"
  cp -r "$FIXTURE/repo-base/." "$SEMENTE/"
  find "$SEMENTE" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null
  git -C "$SEMENTE" init -q -b main
  git -C "$SEMENTE" add -A
  GIT_AUTHOR_DATE="2026-01-01T00:00:00Z" GIT_COMMITTER_DATE="2026-01-01T00:00:00Z" \
    git -C "$SEMENTE" -c user.name=bancada -c user.email=bancada@local \
    commit -q -m "$PACOTE: esqueleto, implementacao a fazer"
  diga "semente: $(git -C "$SEMENTE" rev-parse HEAD)"
}

# ---------------------------------------------------------------- preparar
cmd_preparar() {
  [ -d "$SEMENTE" ] || { echo "rode 'semear' primeiro" >&2; exit 2; }

  # Cota ANTES de apagar qualquer coisa: se o assento nao pode trabalhar, a
  # rodada nao comeca e nada e destruido.
  gate_cota "$ASSENTO_PLANO" || exit 5
  [ "$ASSENTO_EXEC" = "$ASSENTO_PLANO" ] || gate_cota "$ASSENTO_EXEC" || exit 5

  rm -rf "$SAIDA"; mkdir -p "$COMPOZY_HOME" "$SAIDA"
  git clone -q "$SEMENTE" "$REPO"

  cat > "$COMPOZY_HOME/config.toml" <<EOF
[defaults]
agent = "general"
provider = "$ASSENTO_PLANO"

[permissions]
mode = "approve-all"

[http]
host = "localhost"
port = $PORTA

[memory]
enabled = false

# --------------------------------------------------------------- assentos
# Os tres sao declarados em toda rodada. Qual e usado em cada fase e decidido
# pelos flags (--provider no planejamento, --runtime na execucao), nao por
# config, para que o rodizio fique explicito no comando e auditavel no log.
# ACP travado em $ACP_VER nos tres: @latest andaria entre os bracos.

[providers.claude]
auth_mode = "native_cli"
auth_status_command = "$HOME/.local/bin/compozy-claude-auth-status"
command = "npx -y @agentclientprotocol/claude-agent-acp@${ACP_VER}"
display_name = "Claude premium"
env_policy = "filtered"
harness = "acp"
runtime_provider = "claude"
[providers.claude.models]
default = "$MODELO_PLANO"
[[providers.claude.models.curated]]
id = "$MODELO_PLANO"
[[providers.claude.models.curated]]
id = "$MODELO_EXEC"

[providers.claude-mm1]
auth_mode = "native_cli"
auth_status_command = "env CLAUDE_CONFIG_DIR=$HOME/.claude-mm1 $HOME/.local/bin/compozy-claude-auth-status"
command = "env CLAUDE_CONFIG_DIR=$HOME/.claude-mm1 npx -y @agentclientprotocol/claude-agent-acp@${ACP_VER}"
display_name = "Claude mm1"
env_policy = "filtered"
harness = "acp"
runtime_provider = "claude"
[providers.claude-mm1.models]
default = "$MODELO_EXEC"
[[providers.claude-mm1.models.curated]]
id = "$MODELO_EXEC"
[[providers.claude-mm1.models.curated]]
id = "$MODELO_PLANO"

[providers.claude-mm2]
auth_mode = "native_cli"
auth_status_command = "env CLAUDE_CONFIG_DIR=$HOME/.claude-mm2 $HOME/.local/bin/compozy-claude-auth-status"
command = "env CLAUDE_CONFIG_DIR=$HOME/.claude-mm2 npx -y @agentclientprotocol/claude-agent-acp@${ACP_VER}"
display_name = "Claude mm2"
env_policy = "filtered"
harness = "acp"
runtime_provider = "claude"
[providers.claude-mm2.models]
default = "$MODELO_EXEC"
[[providers.claude-mm2.models.curated]]
id = "$MODELO_EXEC"
[[providers.claude-mm2.models.curated]]
id = "$MODELO_PLANO"

# Papeis de fundo desligados: nesta rodada so pode existir UM consumidor de
# assento, senao coordinator e auto_title entram na conta de tokens do braco.
[roles.coordinator]
enabled = false
[roles.auto_title]
enabled = false
[roles.checkpoint_summary]
enabled = false
[roles.dream]
enabled = false
[roles.memory_extractor]
enabled = false
[roles.memory_controller]
enabled = false
EOF

  # A porta tem que estar LIVRE antes de subir. Sem isso o daemon morre em
  # "bind: address already in use", o compozy status responde por outro caminho,
  # e a rodada segue contra um daemon morto. Foi assim que quase perdi uma.
  for _ in $(seq 1 30); do
    ss -ltn 2>/dev/null | grep -q ":$PORTA " || break
    sleep 1
  done
  if ss -ltn 2>/dev/null | grep -q ":$PORTA "; then
    echo "porta $PORTA ainda ocupada; encerre o daemon anterior" >&2; exit 4
  fi

  ( compozy daemon start --foreground >"$LOG" 2>&1 & echo $! > "$SAIDA/daemon.pid" )
  for _ in $(seq 1 60); do compozy status >/dev/null 2>&1 && break; sleep 1; done

  # O workspace tem que existir ANTES do gate: "compozy loop list" sem workspace
  # devolve lista VAZIA em silencio, em vez de erro, e o gate leria isso como
  # "extensao nao subiu". Registrar primeiro, perguntar depois.
  compozy workspace add "$REPO" --name "$WS" </dev/null >"$SAIDA/workspace.txt" 2>&1

  # Gate de prontidao REAL: os dois Loops do spec-cycle tem que aparecer.
  # "compozy status" sozinho nao prova que a extensao subiu.
  local pronto=0
  for _ in $(seq 1 90); do
    if compozy loop list --workspace "$WS" -o json </dev/null 2>/dev/null | grep -q implement-tasks; then
      pronto=1; break
    fi
    sleep 2
  done
  [ "$pronto" = 1 ] || { echo "daemon nao ficou pronto; ver $LOG" >&2; tail -5 "$LOG" >&2; exit 4; }

  # Os tres assentos tem que estar visiveis ao daemon, senao o --runtime da
  # execucao devolve 422 unknown_provider depois do planejamento ja gasto.
  local faltando=""
  for a in claude claude-mm1 claude-mm2; do
    compozy provider list -o json </dev/null 2>/dev/null | grep -q "\"$a\"" || faltando="$faltando $a"
  done
  [ -z "$faltando" ] || { echo "assento(s) invisiveis ao daemon:$faltando" >&2; exit 4; }

  diga "home   : $COMPOZY_HOME"
  diga "porta  : $PORTA   pid $(cat "$SAIDA/daemon.pid")"
  diga "commit : $(git -C "$REPO" rev-parse --short HEAD)"
  diga "compozy: $(compozy version </dev/null 2>/dev/null | head -1)"
  diga "plano  : $ASSENTO_PLANO / $MODELO_PLANO"
  diga "exec   : $ASSENTO_EXEC / $MODELO_EXEC"
  diga "loops  : $(compozy loop list --workspace "$WS" -o json </dev/null 2>/dev/null | grep -c '"name"') registrados"
  compozy roles list </dev/null 2>&1 | sed -n '4,12p' | sed 's/^/    /'
}

com_repo() { ( cd "$REPO" && "$@" ); }

# Sobe o daemon de uma rodada JA preparada, sem tocar em nada do disco. Existe
# para nao jogar fora planejamento valido quando so a fase seguinte falhou.
cmd_retomar() {
  [ -d "$REPO" ] || { echo "rodada $BRACO-$N nao foi preparada" >&2; exit 2; }
  for _ in $(seq 1 30); do ss -ltn 2>/dev/null | grep -q ":$PORTA " || break; sleep 1; done
  ( compozy daemon start --foreground >>"$LOG" 2>&1 & echo $! > "$SAIDA/daemon.pid" )
  local pronto=0
  for _ in $(seq 1 90); do
    if compozy loop list --workspace "$WS" -o json </dev/null 2>/dev/null | grep -q implement-tasks; then pronto=1; break; fi
    sleep 2
  done
  [ "$pronto" = 1 ] || { echo "daemon nao ficou pronto; ver $LOG" >&2; exit 4; }
  diga "retomada: porta $PORTA, $(find "$REPO/.compozy/tasks/$SLUG" -name 'task_*.md' 2>/dev/null | wc -l) tasks no disco"
}

# ---------------------------------------------------------------- planejar
# A UNICA fase que difere entre os bracos. Tudo depois disto e identico.
# Assento e modelo sao os mesmos nas seis rodadas: premium + Opus.
cmd_planejar() {
  local enunciado; enunciado="$(cat "$FIXTURE/ENUNCIADO.md")"
  local prompt
  if [ "$BRACO" = "A" ]; then
    prompt="Use a skill cy-create-spec e depois a skill cy-create-tasks para planejar o trabalho abaixo sob o slug '${SLUG_A}'. Nao implemente nada ainda: pare quando as tasks estiverem escritas em .compozy/tasks/${SLUG_A}/.

--- ENUNCIADO ---
${enunciado}"
  else
    "$LIGADOR" ligar "$REPO" >"$SAIDA/openspec-init.txt" 2>&1
    prompt="Use a skill openspec-propose para planejar o trabalho abaixo como um change chamado '${SLUG_A}'. Nao implemente nada ainda: pare quando proposal, design, specs e tasks estiverem escritos em openspec/changes/${SLUG_A}/.

--- ENUNCIADO ---
${enunciado}"
  fi
  local sid
  sid="$(com_repo compozy session new --workspace "$WS" -o json </dev/null 2>/dev/null | grep -o '"id"[: ]*"[^"]*"' | head -1 | cut -d'"' -f4)"
  [ -n "$sid" ] || { echo "nao consegui criar sessao" >&2; exit 5; }
  echo "$sid" > "$SAIDA/sessao-plano.txt"
  diga "sessao : $sid  ($ASSENTO_PLANO / $MODELO_PLANO)"
  printf '%s\n' "$prompt" > "$SAIDA/prompt-plano.txt"
  com_repo compozy session prompt "$sid" "$prompt" \
    --provider "$ASSENTO_PLANO" --model "$MODELO_PLANO" \
    </dev/null >"$SAIDA/plano-prompt.log" 2>&1
  # session wait recusa --timeout junto com --unbounded (grupo mutuamente
  # exclusivo). E session prompt volta quando a mensagem e ENTREGUE, nao quando
  # o turno termina: sem este wait, o stop abaixo mata o agente em segundos.
  com_repo compozy session wait "$sid" --until idle,waiting-for-input --timeout "$ESPERA_PLANO" \
    </dev/null >"$SAIDA/plano-wait.log" 2>&1
  local espera=$?
  grep -q '^error:' "$SAIDA/plano-wait.log" 2>/dev/null && { echo "session wait falhou:" >&2; cat "$SAIDA/plano-wait.log" >&2; exit 7; }
  [ "$espera" = 0 ] || diga "aviso: wait devolveu $espera (pode ter estourado $ESPERA_PLANO)"
  com_repo compozy session stop "$sid" </dev/null >/dev/null 2>&1

  # CONSERTO 2: falha de provedor durante o planejamento nao pode virar "plano
  # ruim". Vira rodada invalida. A checagem vem ANTES da porta de artefato,
  # senao "0 tasks por token revogado" seria lido como "0 tasks porque o metodo
  # nao produziu nada".
  if checar_falha_provedor "planejamento"; then exit 11; fi

  if [ "$BRACO" = "B" ]; then
    python3 "$CONVERSOR" "$REPO" "$SLUG_A" >"$SAIDA/conversao.txt" 2>&1 \
      || { echo "conversor falhou; ver $SAIDA/conversao.txt" >&2; exit 6; }
    cat "$SAIDA/conversao.txt"
  fi
  # Saneia frontmatter antes da porta de artefato. Roda nos DOIS bracos por
  # simetria, mesmo que o braco B nunca precise (o conversor ja cita).
  # Motivo: o cy-create-tasks escreve "title: Foo: bar" sem aspas, e o
  # importador Go recusa o diretorio inteiro com "mapping values are not
  # allowed in this context". Issue aberta upstream; aqui o saneador existe
  # para o experimento medir planejamento, nao esse defeito.
  python3 "$SANEADOR" "$REPO/.compozy/tasks/$SLUG" 2>&1 | tee "$SAIDA/saneamento.txt" | sed 's/^/  /'

  local n_tasks; n_tasks=$(find "$REPO/.compozy/tasks/$SLUG" -name 'task_*.md' 2>/dev/null | wc -l)
  diga "tasks  : $n_tasks"
  # PORTA DE ARTEFATO. Sem isto, planejamento vazio segue para o Loop, o Loop
  # nao acha task nenhuma, e a rodada termina com status=0 medindo nada.
  if [ "$n_tasks" -eq 0 ]; then
    echo "planejamento nao produziu task em $REPO/.compozy/tasks/$SLUG" >&2
    echo "  transcript: compozy session history $sid" >&2
    exit 8
  fi
}

# --------------------------------------- conserto 2: falha do PROVEDOR
# Nao e' so cota. Sao todas as falhas que vem do provedor e nao do trabalho:
# cota estourada, token revogado, sessao de OAuth expirada. Em qualquer uma
# delas a rodada nao mede planejamento, mede infraestrutura, e tem que ser
# marcada INVALIDA em vez de virar nota baixa.
#
# Isto veio de uma execucao real: o token do assento premium foi revogado no
# meio da A1, o cy-create-spec ja tinha escrito 66 KB de artefato, o
# cy-create-tasks nunca rodou, e a rodada saiu como "planejamento nao produziu
# task". Ou seja: uma falha de auth seria contada contra o metodo de
# planejamento. Num A/B pre-registrado isso e' exatamente o tipo de erro que
# enviesa o resultado em silencio.
#
# Retorna 0 (sucesso) QUANDO ACHA o sintoma, para ler como "if checar; then abortar".
checar_falha_provedor() {
  local fase="$1" achado="" f
  for f in "$LOG" "$SAIDA/plano-prompt.log" "$SAIDA/plano-wait.log"; do
    [ -f "$f" ] || continue
    achado=$(grep -hoiE 'rate_limit|not_authenticated|authentication_failed|token has been revoked|OAuth session expired' "$f" 2>/dev/null | head -1)
    [ -n "$achado" ] && break
  done
  [ -n "$achado" ] || return 1
  {
    echo "RODADA INVALIDA"
    echo "fase=$fase"
    echo "motivo=$achado"
    echo "arquivo=$f"
    echo "assento_plano=$ASSENTO_PLANO"
    echo "assento_exec=$ASSENTO_EXEC"
    echo "quando=$(date -Is)"
    grep -hiE 'rate_limit|not_authenticated|authentication_failed|token has been revoked|OAuth session expired' "$f" 2>/dev/null | head -2 | cut -c1-400
  } > "$SAIDA/INVALIDA.txt"
  echo "FALHA DE PROVEDOR ($achado) durante $fase: rodada $BRACO-$N invalidada" >&2
  return 0
}

# ---------------------------------------------------------------- implementar
# "compozy loop run" DISPARA e volta na hora com status=running. Sem esperar o
# estado terminal, a fase de medicao roda com o Loop ainda trabalhando.
# Os seis estados terminais vem do contrato do proprio Loop.
esperar_run() {
  local rid="$1" rotulo="$2" limite="${3:-$TETO_LOOP}" t0 st
  t0=$(date +%s)
  while :; do
    st=$(com_repo compozy loop status --run-id "$rid" --workspace "$WS" -o json </dev/null 2>/dev/null \
         | sed -n 's/.*"status": *"\([a-z-]*\)".*/\1/p' | head -1)
    case "$st" in
      done|no-op|blocked|failed|exhausted|stalled)
        diga "$rotulo: $st em $(( $(date +%s) - t0 ))s"; printf '%s' "$st"; return 0 ;;
    esac
    # Conserto 2: cortar assim que o sintoma aparece, em vez de queimar o teto.
    if checar_falha_provedor "$rotulo"; then
      com_repo compozy loop cancel --run-id "$rid" --workspace "$WS" </dev/null >/dev/null 2>&1
      printf 'rate-limited'; return 2
    fi
    if [ $(( $(date +%s) - t0 )) -gt "$limite" ]; then
      diga "$rotulo: estourou ${limite}s com status=$st"; printf 'timeout'; return 1
    fi
    sleep 20
  done
}

# Os Loops do spec-cycle sao concurrency: forbid. Um daemon morto no meio deixa
# o run marcado como running para sempre, e o proximo start morre com
# active_loop_run_exists. Liquidar o orfao antes de comecar.
cancelar_orfaos() {
  local loop="$1" rid
  for rid in $(com_repo compozy loop runs --loop "$loop" --workspace "$WS" -o json </dev/null 2>/dev/null \
               | sed -n 's/.*"id": *"\(looprun-[a-z0-9]*\)".*/\1/p'); do
    local st
    st=$(com_repo compozy loop status --run-id "$rid" --workspace "$WS" -o json </dev/null 2>/dev/null \
         | sed -n 's/.*"status": *"\([a-z-]*\)".*/\1/p' | head -1)
    case "$st" in
      running|paused|pending)
        diga "cancelando orfao $rid ($loop, $st)"
        com_repo compozy loop cancel --run-id "$rid" --workspace "$WS" </dev/null >/dev/null 2>&1
        sleep 3 ;;
    esac
  done
}

# worker e judge cobrem os dois papeis que os Loops do spec-cycle instanciam.
# O flag escreve em RuntimeDefaults, que e config de RUN, nao input de Loop,
# entao alcanca tambem o review-and-fix, que nao declara input de runtime.
# Os quatro agentes da extensao nao declaram provider nem model no AGENT.md
# deles, entao herdam daqui em vez de fixar Opus.
runtime_exec=(--runtime "worker=${ASSENTO_EXEC}/${MODELO_EXEC}"
              --runtime "judge=${ASSENTO_EXEC}/${MODELO_EXEC}")

# Cinto E suspensorio. O implement-tasks declara quatro inputs proprios de
# runtime (default/backend/frontend/orchestrator), todos {} na definicao. {} e
# no-op e o dry-run confirma que os --runtime chegam mesmo sem isto, mas com
# eles o direcionamento fica explicito no nivel do proprio Loop e nao depende
# de "vazio nao sobrescreve" continuar verdade na proxima versao.
# O review-and-fix nao tem input nenhum de runtime: la o --runtime e o unico
# caminho, que e exatamente o que a checagem 1 estabeleceu.
runtime_json="{\"provider\":\"${ASSENTO_EXEC}\",\"model\":\"${MODELO_EXEC}\"}"
runtime_inputs=(--input "default_runtime=$runtime_json"
                --input "backend_runtime=$runtime_json"
                --input "frontend_runtime=$runtime_json"
                --input "orchestrator_runtime=$runtime_json")

cmd_implementar() {
  cancelar_orfaos implement-tasks
  diga "runtime: ${ASSENTO_EXEC}/${MODELO_EXEC} em worker e judge"
  com_repo compozy loop run --name implement-tasks --input "slug=$SLUG" --workspace "$WS" \
    "${runtime_exec[@]}" "${runtime_inputs[@]}" --no-prompt -o json \
    </dev/null >"$SAIDA/implement-run.json" 2>&1
  local rid; rid=$(sed -n 's/.*"id": *"\(looprun-[a-z0-9]*\)".*/\1/p' "$SAIDA/implement-run.json" | head -1)
  [ -n "$rid" ] || { echo "sem run id; ver $SAIDA/implement-run.json" >&2; tail -c 400 "$SAIDA/implement-run.json" >&2; exit 9; }
  echo "$rid" > "$SAIDA/implement-run-id.txt"
  esperar_run "$rid" "implement-tasks" "$TETO_LOOP" > "$SAIDA/implement-estado.txt"
  local rc=$?
  com_repo compozy loop status --run-id "$rid" --workspace "$WS" -o json </dev/null 2>/dev/null > "$SAIDA/implement-final.json"
  diga "estado : $(cat "$SAIDA/implement-estado.txt")"
  [ "$rc" = 2 ] && exit 11
  return 0
}

cmd_revisar() {
  cancelar_orfaos review-and-fix
  # O review-and-fix recebe task_name, NAO slug. Passar slug devolve
  # 422 unknown_input e a fase vira ruido silencioso.
  com_repo compozy loop run --name review-and-fix --input "task_name=$SLUG" --workspace "$WS" \
    "${runtime_exec[@]}" --no-prompt -o json \
    </dev/null >"$SAIDA/review-run.json" 2>&1
  local rid; rid=$(sed -n 's/.*"id": *"\(looprun-[a-z0-9]*\)".*/\1/p' "$SAIDA/review-run.json" | head -1)
  if [ -z "$rid" ]; then
    diga "review-and-fix nao iniciou:"; tail -c 300 "$SAIDA/review-run.json"; return 0
  fi
  esperar_run "$rid" "review-and-fix" "$TETO_LOOP" > "$SAIDA/review-estado.txt"
  local rc=$?
  com_repo compozy loop status --run-id "$rid" --workspace "$WS" -o json </dev/null 2>/dev/null > "$SAIDA/review-final.json"
  [ "$rc" = 2 ] && exit 11
  return 0
}

# ------------------------------------------------- auditoria de assento
# Metrica 6 da v3, e nao e opcional: sem ela nao da para AFIRMAR que o rodizio
# foi respeitado, so declarar. Cada sessao que o daemon abre grava provider e
# model no proprio meta.json; isto conta os pares de fato usados.
auditar_assentos() {
  python3 - "$COMPOZY_HOME/sessions" <<'PY'
import glob, json, os, sys, collections
raiz = sys.argv[1]
pares = collections.Counter()
for f in glob.glob(os.path.join(raiz, "*", "meta.json")):
    try:
        d = json.load(open(f))
    except Exception:
        continue
    pares[(d.get("provider", "?"), d.get("model", "?"))] += 1
if not pares:
    print("sem-sessoes")
else:
    print(" ".join(f"{p}/{m}:{n}" for (p, m), n in sorted(pares.items())))
PY
}

# ---------------------------------------------------------------- medir
cmd_medir() {
  com_repo make test </dev/null >"$SAIDA/make-test.txt" 2>&1
  echo "make-test=$?" >> "$SAIDA/make-test.txt"

  # Rodar por CLASSE. No modo -v o unittest imprime a docstring no lugar do
  # nome quando o teste tem uma, entao contar por prefixo test_F/test_R seria
  # fragil. Por classe, "Ran N tests" e' inequivoco.
  local grupo
  for grupo in TestBase TestRobustez "$PRIMARIA"; do
    ( cd "$REPO" && PYTHONPATH="$REPO" timeout 2400 python3 "$FIXTURE/aceite/test_aceite.py" "$grupo" -v ) \
      </dev/null >"$SAIDA/aceite-${grupo}.txt" 2>&1
  done
  cat "$SAIDA/aceite-TestBase.txt" "$SAIDA/aceite-TestRobustez.txt" \
      "$SAIDA/aceite-$PRIMARIA.txt" > "$SAIDA/aceite.txt"

  conta() {  # <arquivo> -> "passou/total"
    local f="$1" t p
    t=$(sed -n 's/^Ran \([0-9]*\) test.*/\1/p' "$f" 2>/dev/null | tail -1); t=${t:-0}
    p=$(grep -c '\.\.\. ok$' "$f" 2>/dev/null); p=${p:-0}
    printf '%s/%s' "$p" "$t"
  }
  local base robustez primaria
  base=$(conta "$SAIDA/aceite-TestBase.txt")
  robustez=$(conta "$SAIDA/aceite-TestRobustez.txt")
  primaria=$(conta "$SAIDA/aceite-$PRIMARIA.txt")

  if grep -rql 'test_aceite' "$REPO" 2>/dev/null; then
    echo "VAZAMENTO: test_aceite citado dentro do repo" | tee -a "$SAIDA/aceite.txt"
  fi

  com_repo compozy loop runs --loop implement-tasks --workspace "$WS" -o json </dev/null >"$SAIDA/loop-runs.json" 2>&1
  {
    echo "braco=$BRACO rodada=$N"
    echo "commit_partida=$(git -C "$SEMENTE" rev-parse HEAD)"
    echo "acp_version=$ACP_VER"
    echo "compozy_version=$(compozy version </dev/null 2>/dev/null | head -1 | grep -o '0\.[0-9.a-z-]*')"
    echo "dominio=$DOMINIO"
    echo "camada_primaria=$PRIMARIA"
    echo "primaria=$primaria"
    echo "robustez=$robustez"
    echo "base=$base"
    echo "make_test=$(tail -1 "$SAIDA/make-test.txt")"
    echo "implement_estado=$(tr -d '\n' < "$SAIDA/implement-estado.txt" 2>/dev/null)"
    echo "review_estado=$(tr -d '\n' < "$SAIDA/review-estado.txt" 2>/dev/null)"
    echo "review_rodadas=$(find "$REPO/.compozy/tasks/$SLUG" -maxdepth 1 -name 'reviews-*' -type d 2>/dev/null | wc -l)"
    echo "assento_plano=$ASSENTO_PLANO/$MODELO_PLANO"
    echo "assento_exec=$ASSENTO_EXEC/$MODELO_EXEC"
    echo "assentos_medidos=$(auditar_assentos)"
    # Registra se o bug do YAML do cy-create-tasks disparou NESTA rodada. Ele
    # e' real mas intermitente: depende do titulo que o agente escreve. Sem
    # este campo eu so poderia afirmar que o defeito existe, nao com que
    # frequencia ele aparece.
    echo "saneador_agiu=$(grep -qi 'nada a sanear' "$SAIDA/saneamento.txt" 2>/dev/null && echo nao || echo sim)"
  } | tee "$SAIDA/RESUMO.txt"
}

cmd_encerrar() {
  local p h mortos=0
  # NUNCA use pkill -f "compozy daemon" aqui. O servico permanente do operador
  # roda com a MESMA linha de comando, e um pkill largo derruba o daemon de
  # trabalho dele. Casar pelo COMPOZY_HOME da rodada e o unico jeito seguro.
  for p in $(pgrep -f 'compozy daemon start' 2>/dev/null); do
    h=$(tr '\0' '\n' < "/proc/$p/environ" 2>/dev/null | grep '^COMPOZY_HOME=' | cut -d= -f2-)
    [ "$h" = "$COMPOZY_HOME" ] || continue
    kill "$p" 2>/dev/null && mortos=$((mortos + 1))
  done
  sleep 2
  diga "daemon da rodada encerrado ($mortos processo(s))"
}

case "${1:-}" in
  semear)      cmd_semear ;;
  retomar)     cmd_retomar ;;
  preparar)    cmd_preparar ;;
  planejar)    cmd_planejar ;;
  implementar) cmd_implementar ;;
  revisar)     cmd_revisar ;;
  medir)       cmd_medir ;;
  encerrar)    cmd_encerrar ;;
  tudo)        cmd_preparar && cmd_planejar && cmd_implementar && cmd_revisar && cmd_medir; cmd_encerrar ;;
  *) sed -n '2,20p' "$0" | sed 's/^# \?//'; exit 2 ;;
esac
