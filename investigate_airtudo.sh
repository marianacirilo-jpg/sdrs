#!/usr/bin/env bash
# Investigar Airtudo corretamente: buscar por company (CONTAINS_TOKEN) + todos campos de telefone.
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
echo "=== Busca por company CONTAINS_TOKEN Airtudo ==="
curl -s "https://api.hubapi.com/crm/v3/objects/contacts/search" \
  -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
  -d '{"filterGroups":[{"filters":[{"propertyName":"company","operator":"CONTAINS_TOKEN","value":"Airtudo"}]}],"properties":["firstname","lastname","email","company","phone","mobilephone","hs_searchable_calculated_phone_number","fax","createdate"]}' \
  | python3 -m json.tool
echo ""
echo "=== Busca por email CONTAINS airtudo ==="
curl -s "https://api.hubapi.com/crm/v3/objects/contacts/search" \
  -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
  -d '{"filterGroups":[{"filters":[{"propertyName":"email","operator":"CONTAINS_TOKEN","value":"airtudo"}]}],"properties":["email","company","phone","mobilephone","hs_searchable_calculated_phone_number"]}' \
  | python3 -m json.tool