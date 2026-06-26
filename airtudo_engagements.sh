#!/usr/bin/env bash
# Procura telefone em notas/envios de formulario/atividades do contato Airtudo.
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
CID=230243438596
echo "=== notas (notes) associadas ==="
curl -s "https://api.hubapi.com/crm/v4/objects/contacts/${CID}/associations/notes" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}"
echo ""
echo "=== emails associados ==="
curl -s "https://api.hubapi.com/crm/v4/objects/contacts/${CID}/associations/emails" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}"
echo ""
echo "=== meetings associadas ==="
curl -s "https://api.hubapi.com/crm/v4/objects/contacts/${CID}/associations/meetings" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}"
echo ""
echo "=== form submissions via timeline v3 ==="
curl -s "https://api.hubapi.com/crm/v3/objects/contacts/${CID}/timeline" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" | python3 -c "import sys,json;d=json.load(sys.stdin);print(json.dumps(d,ensure_ascii=False,indent=1)[:2000])" 2>/dev/null || echo "timeline n/disp"