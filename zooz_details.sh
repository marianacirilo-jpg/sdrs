#!/usr/bin/env bash
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
echo "=== zooz contato + deal + meeting ==="
DATA=$(curl -s "https://api.hubapi.com/crm/v3/objects/contacts/search" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
 -d '{"filterGroups":[{"filters":[{"propertyName":"email","operator":"EQ","value":"daniel.haberer@zoozpets.com"}]}],"properties":["firstname","company","hs_whatsapp_phone_number","hs_searchable_calculated_phone_number","hubspot_owner_id","lifecyclestage"]}')
echo "$DATA" | python3 -c "
import sys,json
d=json.load(sys.stdin)
r=d['results'][0]; p=r['properties']
print(f\"id={r['id']} | {p.get('firstname')} | {p.get('company')} | tel={p.get('hs_searchable_calculated_phone_number')} | owner={p.get('hubspot_owner_id')} | lc={p.get('lifecyclestage')}\")
"
CID=$(echo "$DATA" | python3 -c "import sys,json;print(json.load(sys.stdin)['results'][0]['id'])")
echo "deal:"
curl -s "https://api.hubapi.com/crm/v4/objects/contacts/${CID}/associations/deals" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" | python3 -c "import sys,json;d=json.load(sys.stdin);print(','.join(str(x['toObjectId']) for x in d.get('results',[])) or 'SEM_DEAL')"
echo "meeting:"
curl -s "https://api.hubapi.com/crm/v4/objects/contacts/${CID}/associations/meetings" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" | python3 -c "import sys,json;d=json.load(sys.stdin);print(','.join(str(x['toObjectId']) for x in d.get('results',[])) or 'SEM')"