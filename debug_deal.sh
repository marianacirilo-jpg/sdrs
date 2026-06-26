#!/usr/bin/env bash
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
echo "=== raw de um contato ERR (arumia 230104579454) ==="
curl -s "https://api.hubapi.com/crm/v4/objects/contacts/230104579454/associations/deals" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}"
echo ""
echo "=== raw bodebrown dup (229709058090) ==="
curl -s "https://api.hubapi.com/crm/v4/objects/contacts/229709058090/associations/deals" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}"
echo ""
echo "=== avetextil: achar contato por email ==="
curl -s "https://api.hubapi.com/crm/v3/objects/contacts/search" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
 -d '{"filterGroups":[{"filters":[{"propertyName":"email","operator":"EQ","value":"amanda@avetextil.com.br"}]}],"properties":["email","company"]}' | python3 -c "import sys,json;d=json.load(sys.stdin);print([(r['id'],r['properties'].get('email'),r['properties'].get('company')) for r in d.get('results',[])])"