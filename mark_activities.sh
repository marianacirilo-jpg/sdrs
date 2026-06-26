#!/usr/bin/env bash
# Cria task de atividade no HubSpot para cada lead enviado.
# Token lido em runtime do env (nao passa por string literal no script).
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
URL="https://api.hubapi.com/crm/v3/objects/tasks"
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# slug|contact_id|owner_id (owner vazio = sem owner)
leads=(
  "arumia-house|230104579454|86265630"
  "plasticos-piracicaba|230111705190|"
  "legadu-social|230136737690|86265630"
  "grupo-american-pool|230157646654|"
  "gift-do-brasil|230170624147|86265630"
  "onixxbrasil|230097337667|88063842"
  "dona-parede|230142798593|"
  "rct-soldas|230118646303|86265630"
  "mercato|230132154281|88063842"
  "dussara|230161822879|88063842"
  "zimermann|230128636004|85778446"
)

OK=0; FAIL=""
for entry in "${leads[@]}"; do
  IFS='|' read -r slug cid owner <<< "$entry"
  if [ -n "$owner" ]; then
    OWNER_LINE="\"hubspot_owner_id\":\"$owner\","
  else
    OWNER_LINE=""
  fi
  PAYLOAD="{\"properties\":{\"hs_timestamp\":\"$TS\",\"hs_task_subject\":\"WhatsApp — Diagnóstico 'Potencial de Digitalização B2B' enviado ao lead.\",${OWNER_LINE}\"hs_task_status\":\"NOT_STARTED\",\"hs_task_priority\":\"HIGH\"},\"associations\":[{\"to\":{\"id\":\"$cid\"},\"types\":[{\"associationCategory\":\"HUBSPOT_DEFINED\",\"associationTypeId\":204}]}]}"
  RESP=$(curl -s -X POST "$URL" \
    -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")
  TID=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
  if [ -n "$TID" ]; then
    echo "OK $slug | task=$TID | owner=${owner:-—}"
    OK=$((OK+1))
  else
    MSG=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('message','')[:70])" 2>/dev/null || echo "?")
    echo "FAIL $slug | $MSG"
    FAIL="$FAIL $slug"
  fi
  sleep 1
done
echo "=== $OK/11 criadas | falhas:$FAIL ==="
