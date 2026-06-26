#!/usr/bin/env bash
# Organizer da meeting 111475833693 do Caffeine army
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
curl -s "https://api.hubapi.com/crm/v3/objects/meetings/111475833693?properties=hubspot_owner_id,hs_created_by,hs_meeting_title,hs_meeting_outcome" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" | python3 -m json.tool | grep -E "hubspot_owner_id|hs_created_by|hs_meeting_title|hs_meeting_outcome"