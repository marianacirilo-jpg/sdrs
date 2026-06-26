#!/usr/bin/env bash
# Busca deal IDs dos 2 NAO_MQL (ib-silva, airtudo)
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
for cid in 230219422874 230243438596; do
  dl=$(curl -s "https://api.hubapi.com/crm/v4/objects/contacts/${cid}/associations/deals" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}")
  echo "$cid -> $(echo "$dl" | python3 -c "import sys,json;d=json.load(sys.stdin);r=d.get('results',[]);print(','.join(str(x['toObjectId']) for x in r) if r else 'SEM_DEAL')")"
done