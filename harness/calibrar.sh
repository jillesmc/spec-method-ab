#!/usr/bin/env bash
# Calibra uma suite oculta contra as implementacoes de referencia.
#
#   calibrar.sh <dominio> <referencia> [classe...]
#
# Monta um repo temporario = repo-base + a referencia, e roda a suite oculta
# contra ele exatamente como o runner do experimento roda. Sem isso, "a suite
# discrimina" seria opiniao minha.
set -uo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
DOM="${1:?dominio: store ou indexador}"
REF="${2:?referencia: ingenua ou cuidadosa}"
shift 2
FX="$AQUI/fixture/$DOM"
TMP="$(mktemp -d /tmp/calibrar-XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

cp -r "$FX/repo-base/." "$TMP/"
cp -r "$FX/referencia/$REF/." "$TMP/"

for grupo in "${@:-TestBase TestRobustez TestInvariante}"; do
  saida="$TMP/saida-$grupo.txt"
  ( cd "$TMP" && PYTHONPATH="$TMP" timeout 1800 python3 "$FX/aceite/test_aceite.py" "$grupo" -v ) \
    </dev/null >"$saida" 2>&1
  total=$(sed -n 's/^Ran \([0-9]*\) test.*/\1/p' "$saida" | tail -1)
  ok=$(grep -c '\.\.\. ok$' "$saida")
  printf '%-18s %-16s %s/%s\n' "$DOM/$REF" "$grupo" "${ok:-0}" "${total:-0}"
  grep -E '^(FAIL|ERROR): ' "$saida" | sed 's/^/     /'
done
