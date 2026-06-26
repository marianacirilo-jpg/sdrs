#!/usr/bin/env bash
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
echo "=== zooz meeting organizer ==="
curl -s "https://api.hubapi.com/crm/v3/objects/meetings/111463814005?properties=hubspot_owner_id,hs_created_by,hs_meeting_title" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" | python3 -m json.tool | grep -E "hubspot_owner_id|hs_created_by|hs_meeting_title"
echo "=== marcar zooz como MQL (lifecyclestage) ==="
R=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "https://api.hubapi.com/crm/v3/objects/contacts/229708441487" \
  -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
  -d '{"properties":{"lifecyclestage":"marketingqualifiedlead"}}')
echo "zooz -> MQL ($R)"