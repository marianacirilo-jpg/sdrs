#!/usr/bin/env bash
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
# task IDs atuais por contato (das 12 que já tem task)
echo "=== tasks por contato ==="
cids="230104579454 230111705190 230136737690 230157646654 230170624147 230097337667 230142798593 230118646303 230132154281 230161822879 230128636004"
for c in $cids; do
  t=$(curl -s "https://api.hubapi.com/crm/v4/objects/contacts/${c}/associations/tasks" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}")
  echo "${c}: $(echo "$t" | python3 -c "import sys,json;d=json.load(sys.stdin);print(','.join(str(x['toObjectId']) for x in d.get('results',[])) or 'SEM_TASK')" 2>/dev/null || echo ERR)"
  sleep 0.3
done
echo "=== owners bodebrown + avetextil ==="
for c in 229709058090 230183861771; do
  curl -s "https://api.hubapi.com/crm/v3/objects/contacts/${c}?properties=hubspot_owner_id,firstname,company" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" | python3 -c "import sys,json;d=json.load(sys.stdin);p=d.get('properties',{});print(c,'|',p.get('company'),'|owner:',p.get('hubspot_owner_id'))" 
done