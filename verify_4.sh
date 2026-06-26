#!/usr/bin/env bash
# Re-verifica telefone (hs_whatsapp_phone_number) + agenda (meeting owner) dos 4 leads prontos.
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
EMAILS=(
  "leonardo.menezes@tetraplus.com.br"
  "raphael@pontesmulti.com.br"
  "joao@madeiraabc.com.br"
  "daniel.haberer@brightgearcorp.com"
)
for e in "${EMAILS[@]}"; do
  echo "===== $e ====="
  DATA=$(curl -s "https://api.hubapi.com/crm/v3/objects/contacts/search" \
    -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
    -d "{\"filterGroups\":[{\"filters\":[{\"propertyName\":\"email\",\"operator\":\"EQ\",\"value\":\"$e\"}]}],\"properties\":[\"firstname\",\"company\",\"hs_whatsapp_phone_number\",\"hs_searchable_calculated_phone_number\",\"lifecyclestage\",\"hubspot_owner_id\",\"hs_meeting_booked\",\"qual_documento_ou_identificador_da_reuni_o_\"]}")
  echo "$DATA" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for r in d.get('results',[]):
    p=r['properties']
    print(f\"  id={r['id']} | {p.get('firstname')} | {p.get('company')}\")
    print(f\"  whatsapp={p.get('hs_whatsapp_phone_number')} | calc={p.get('hs_searchable_calculated_phone_number')}\")
    print(f\"  owner={p.get('hubspot_owner_id')} | meeting_booked={p.get('hs_meeting_booked')} | lc={p.get('lifecyclestage')}\")
"
  # meetings associadas
  CID=$(echo "$DATA" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['results'][0]['id'] if d.get('results') else '')")
  if [ -n "$CID" ]; then
    curl -s "https://api.hubapi.com/crm/v4/objects/contacts/${CID}/associations/meetings" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" | python3 -c "import sys,json;d=json.load(sys.stdin);r=d.get('results',[]);print(f'  meetings: {len(r)}', [str(x[\"toObjectId\"]) for x in r] if r else '')" 2>/dev/null || echo "  meetings: ERR"
  fi
  echo ""
done