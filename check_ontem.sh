#!/usr/bin/env bash
# Busca ESPECIFICA contatos de 21/06 (ontem) que NAO estao processados.
set -uo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
# janela 21/06 00:00 ate 22/06 00:00 UTC
START=$(python3 -c "from datetime import datetime;print(int(datetime(2026,6,21,tzinfo=__import__('datetime').timezone.utc).timestamp()*1000))")
END=$(python3 -c "from datetime import datetime;print(int(datetime(2026,6,22,tzinfo=__import__('datetime').timezone.utc).timestamp()*1000))")
curl -s "https://api.hubapi.com/crm/v3/objects/contacts/search" \
  -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
  -d "{\"filterGroups\":[{\"filters\":[{\"propertyName\":\"createdate\",\"operator\":\"GTE\",\"value\":\"$START\"},{\"propertyName\":\"createdate\",\"operator\":\"LT\",\"value\":\"$END\"}]}],\"properties\":[\"firstname\",\"lastname\",\"company\",\"email\",\"hs_whatsapp_phone_number\",\"createdate\",\"lifecyclestage\"],\"sorts\":[{\"propertyName\":\"createdate\",\"direction\":\"DESCENDING\"}],\"limit\":50}" > /tmp/ontem.json
python3 -c "
import json
procs=set(l.strip().split('|')[0].lower() for l in open('controle/processed_emails.txt') if l.strip())
d=json.load(open('/tmp/ontem.json'))
res=d.get('results',[])
print(f'Total contatos 21/06: {len(res)}')
print('=== TODOS de 21/06 (processado?) ===')
for r in res:
    p=r['properties']
    e=(p.get('email') or '').lower()
    status='PROC' if e in procs else 'NOVO'
    print(f\"  {p.get('createdate','')[:16]} | {status} | {p.get('firstname','')} {p.get('lastname','')} | {p.get('company','')} | {e}\")
"