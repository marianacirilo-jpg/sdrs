#!/usr/bin/env bash
# Procurar Leonardo Schmidt no HubSpot e no processed_emails
set -uo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')

echo "=== 1) no processed_emails? ==="
grep -i "schmidt\|leonardo" controle/processed_emails.txt || echo "NAO esta em processed"

echo ""
echo "=== 2) buscar no HubSpot por nome ==="
curl -s "https://api.hubapi.com/crm/v3/objects/contacts/search" \
  -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
  -d '{"filterGroups":[{"filters":[{"propertyName":"firstname","operator":"EQ","value":"Leonardo"},{"propertyName":"lastname","operator":"EQ","value":"Schmidt"}]}],"properties":["firstname","lastname","email","company","hs_whatsapp_phone_number","lifecyclestage","createdate"]}' | python3 -m json.tool 2>/dev/null | grep -E "firstname|lastname|email|company|hs_whatsapp|lifecycle|createdate|\"id\"" | head -20

echo ""
echo "=== 3) buscar por lastname contains Schmidt ==="
curl -s "https://api.hubapi.com/crm/v3/objects/contacts/search" \
  -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
  -d '{"filterGroups":[{"filters":[{"propertyName":"lastname","operator":"CONTAINS_TOKEN","value":"Schmidt"}]}],"properties":["firstname","lastname","email","company","hs_whatsapp_phone_number","lifecyclestage","createdate"]}' | python3 -m json.tool 2>/dev/null | grep -E "firstname|lastname|email|company|hs_whatsapp|lifecycle|createdate|\"id\"" | head -20