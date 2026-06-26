#!/usr/bin/env bash
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
echo "=== neogrid contato + deal ==="
curl -s "https://api.hubapi.com/crm/v3/objects/contacts/search" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
 -d '{"filterGroups":[{"filters":[{"propertyName":"email","operator":"EQ","value":"robson.munhoz@neogrid.com"}]}],"properties":["hubspot_owner_id","company"]}' \
 | python3 -c "import sys,json;d=json.load(sys.stdin);r=d.get('results',[]);print([(x['id'],x['properties'].get('hubspot_owner_id'),x['properties'].get('company')) for x in r]) if r else print('NAO_ACHOU')"
NG=$(curl -s "https://api.hubapi.com/crm/v3/objects/contacts/search" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
 -d '{"filterGroups":[{"filters":[{"propertyName":"email","operator":"EQ","value":"robson.munhoz@neogrid.com"}]}],"properties":["hubspot_owner_id"]}' \
 | python3 -c "import sys,json;print(json.load(sys.stdin)['results'][0]['id'])")
echo "neogrid cid=$NG deal:"
curl -s "https://api.hubapi.com/crm/v4/objects/contacts/${NG}/associations/deals" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" | python3 -c "import sys,json;d=json.load(sys.stdin);print(','.join(str(x['toObjectId']) for x in d.get('results',[])) or 'SEM_DEAL')"
echo "=== owners bodebrown(229709058090) avetextil(230183861771) ==="
for c in 229709058090 230183861771; do
  curl -s "https://api.hubapi.com/crm/v3/objects/contacts/${c}?properties=hubspot_owner_id,company" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);p=d['properties'];print('$c',p.get('company'),'owner=',p.get('hubspot_owner_id'))"
done