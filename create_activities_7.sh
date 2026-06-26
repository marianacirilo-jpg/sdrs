#!/usr/bin/env bash
# Cria atividades no HubSpot para os 5 MQLs (enviado) + 2 NAO_MQL (nao qualificado).
set -uo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
export TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
export SUBJ_MQL="WhatsApp — Diagnóstico 'Potencial de Digitalização B2B' enviado ao lead."
export SUBJ_NAO="Lead não qualificado como MQL (fora do perfil B2B atacado/distribuidor/indústria)."

# 5 MQLs: slug|contact_id|deal_id|owner|tipo(mql/nao)
LEADS=(
  "tetraplus|230184732285|61410136706|85778446|mql"
  "pontes-multi|230211201144|61428489365|85778446|mql"
  "madeira-abc|230190210058|61427666724|88063842|mql"
  "brightgear|230183961698|61426947935|85778446|mql"
  "zooz|229708441487|61426795957|86265630|mql"
  "ib-silva|230219422874|61428212015|88063842|nao"
  "airtudo|230243438596||88063842|nao"
)
OK=0; FAIL=""
for entry in "${LEADS[@]}"; do
  IFS='|' read -r slug cid did owner tipo <<< "$entry"
  if [ "$tipo" = "mql" ]; then export SUBJ_USE="$SUBJ_MQL"; else export SUBJ_USE="$SUBJ_NAO"; fi
  export cid did owner
  # monta associacoes (contato 204 + deal 216 se houver)
  PAYLOAD=$(python3 -c "
import os,json
assocs=[{'to':{'id':os.environ['cid']},'types':[{'associationCategory':'HUBSPOT_DEFINED','associationTypeId':204}]}]
if os.environ.get('did'):
    assocs.append({'to':{'id':os.environ['did']},'types':[{'associationCategory':'HUBSPOT_DEFINED','associationTypeId':216}]})
print(json.dumps({
 'properties':{'hs_timestamp':os.environ['TS'],'hs_task_subject':os.environ['SUBJ_USE'],
               'hubspot_owner_id':os.environ['owner'],'hs_task_status':'COMPLETED','hs_task_priority':'HIGH'},
 'associations':assocs
}))
")
  R=$(curl -s "https://api.hubapi.com/crm/v3/objects/tasks" -X POST \
    -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" -d "$PAYLOAD")
  TID=$(echo "$R" | python3 -c "import sys,json;print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
  if [ -n "$TID" ]; then echo "OK  $slug [$tipo] task=$TID (contato+${did:+negocio})"; OK=$((OK+1));
  else echo "FAIL $slug: $(echo "$R" | head -c 120)"; FAIL="$FAIL $slug"; fi
  sleep 1
done
echo "=== $OK/7 atividades criadas | falhas:$FAIL ==="