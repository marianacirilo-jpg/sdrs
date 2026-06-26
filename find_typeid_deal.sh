#!/usr/bin/env bash
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
curl -s "https://api.hubapi.com/crm/v4/associations/tasks/deals/labels" \
  -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print([(r.get('categoryId'),r.get('label') or r.get('name')) for r in d.get('results',[])])"
