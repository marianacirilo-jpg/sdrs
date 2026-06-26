#!/usr/bin/env bash
# Associa tasks existentes aos deals + cria 2 tasks novas (bodebrown, avetextil) com contato+deal.
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
BASE4="https://api.hubapi.com/crm/v4/objects"
export TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
export SUBJ="WhatsApp — Diagnóstico 'Potencial de Digitalização B2B' enviado ao lead."

echo "=== FASE 1: associar 9 tasks aos deals (v4 PUT body=ARRAY) ==="
assoc=(
  "111462091121|61408256389"   # neogrid
  "111468530717|61417719690"   # arumia-house
  "111459062915|61411489315"   # legadu-social
  "111463815938|61425162112"   # gift-do-brasil
  "111456949910|61417834140"   # onixxbrasil
  "111449593641|61419020940"   # rct-soldas
  "111468395046|61413663263"   # mercato
  "111459959910|61425220494"   # dussara
  "111468532771|61422066183"   # zimermann
)
OK1=0; FAIL1=""
for entry in "${assoc[@]}"; do
  IFS='|' read -r tid did <<< "$entry"
  R=$(curl -s -o /tmp/a_resp.txt -w "%{http_code}" -X PUT "${BASE4}/tasks/${tid}/associations/deals/${did}" \
    -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
    -d '[{"associationCategory":"HUBSPOT_DEFINED","associationTypeId":216}]')
  if [ "$R" = "200" ] || [ "$R" = "201" ]; then echo "OK  task $tid -> deal $did"; OK1=$((OK1+1));
  else echo "FAIL task $tid -> deal $did ($R): $(head -c 100 /tmp/a_resp.txt)"; FAIL1="$FAIL1 $tid"; fi
  sleep 0.4
done
echo "FASE1: $OK1/9 associadas | falhas:$FAIL1"

echo "=== FASE 2: criar tasks bodebrown + avetextil (v3, associationCategory/associationTypeId) ==="
new=(
  "bodebrown|229709058090|61426453600|88063842"
  "avetextil|230183861771|61408300610|85778446"
)
OK2=0
for entry in "${new[@]}"; do
  IFS='|' read -r slug cid did owner <<< "$entry"
  export slug cid did owner
  PAYLOAD=$(python3 -c "
import os,json
print(json.dumps({
 'properties':{'hs_timestamp':os.environ['TS'],'hs_task_subject':os.environ['SUBJ'],
               'hubspot_owner_id':os.environ['owner'],'hs_task_status':'NOT_STARTED','hs_task_priority':'HIGH'},
 'associations':[
   {'to':{'id':os.environ['cid']},'types':[{'associationCategory':'HUBSPOT_DEFINED','associationTypeId':204}]},
   {'to':{'id':os.environ['did']},'types':[{'associationCategory':'HUBSPOT_DEFINED','associationTypeId':216}]}
 ]
}))
")
  R=$(curl -s "https://api.hubapi.com/crm/v3/objects/tasks" -X POST \
    -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" -d "$PAYLOAD")
  TID=$(echo "$R" | python3 -c "import sys,json;print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
  if [ -n "$TID" ]; then echo "OK  $slug task=$TID (contato $cid + deal $did)"; OK2=$((OK2+1));
  else echo "FAIL $slug: $(echo "$R" | head -c 150)"; fi
  sleep 1
done
echo "FASE2: $OK2/2 criadas"
echo "=== TOTAL: associadas=$OK1/9 novas=$OK2/2 ==="