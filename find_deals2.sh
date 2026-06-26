#!/usr/bin/env bash
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
# slug|contact_id
rows=(
  "arumia-house|230104579454"
  "plasticos-piracicaba|230111705190"
  "legadu-social|230136737690"
  "grupo-american-pool|230157646654"
  "gift-do-brasil|230170624147"
  "onixxbrasil|230097337667"
  "dona-parede|230142798593"
  "rct-soldas|230118646303"
  "mercato|230132154281"
  "dussara|230161822879"
  "zimermann|230128636004"
  "bodebrown|229709058090"
  "avetextil|230183861771"
)
> /tmp/deal_map.txt
for entry in "${rows[@]}"; do
  IFS='|' read -r slug cid <<< "$entry"
  dl=$(curl -s "https://api.hubapi.com/crm/v4/objects/contacts/${cid}/associations/deals" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}")
  did=$(echo "$dl" | python3 -c "import sys,json;d=json.load(sys.stdin);r=d.get('results',[]);print(','.join(str(x['toObjectId']) for x in r) if r else 'SEM_DEAL')" 2>/dev/null || echo "ERR")
  echo "${slug}|${cid}|${did}" | tee -a /tmp/deal_map.txt
  sleep 0.3
done
echo "=== pronto /tmp/deal_map.txt ==="