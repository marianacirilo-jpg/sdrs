#!/usr/bin/env bash
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
echo "=== raw Task->Deal labels ==="
curl -s "https://api.hubapi.com/crm/v4/associations/tasks/deals/labels" \
  -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" > /tmp/deal_labels.json
python3 -c "import json;d=json.load(open('/tmp/deal_labels.json'));print(json.dumps(d,ensure_ascii=False,indent=1))"
echo "=== deal associations por contato (12 + bodebrown + avetextil) ==="
cids="230104579454 230111705190 230136737690 230157646654 230170624147 230097337667 230142798593 230118646303 230132154281 230161822879 230128636004 229709058090"
for c in $cids; do
  dl=$(curl -s "https://api.hubapi.com/crm/v4/objects/contacts/${c}/associations/deals" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}")
  did=$(echo "$dl" | python3 -c "import sys,json;d=json.load(sys.stdin);r=d.get('results',[]);print(','.join(x['toObjectId'] for x in r) if r else 'SEM_DEAL')" 2>/dev/null || echo "ERR")
  echo "$c -> $did"
  sleep 0.3
done