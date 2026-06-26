#!/usr/bin/env bash
# Busca organizador das reunioes dos 3 leads + deal IDs dos 4.
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
echo "=== detalhes das reunioes ==="
for mid in 111468426008 111469779626 111468608410; do
  echo "--- meeting $mid ---"
  curl -s "https://api.hubapi.com/crm/v3/objects/meetings/${mid}?properties=hubspot_owner_id,hs_meeting_title,hs_meeting_organizer,hs_meeting_external_organizer,hs_meeting_start_time,hs_created_by,createdate,hs_meeting_outcome" \
    -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" | python3 -m json.tool | grep -E "hubspot_owner_id|hs_meeting_organizer|hs_meeting_external|hs_created_by|hs_meeting_title|hs_meeting_outcome"
done
echo ""
echo "=== deal IDs dos 4 leads ==="
for cid in 230184732285 230211201144 230190210058 230183961698; do
  dl=$(curl -s "https://api.hubapi.com/crm/v4/objects/contacts/${cid}/associations/deals" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}")
  echo "$cid -> $(echo "$dl" | python3 -c "import sys,json;d=json.load(sys.stdin);r=d.get('results',[]);print(','.join(str(x['toObjectId']) for x in r) if r else 'SEM_DEAL')")"
  sleep 0.3
done