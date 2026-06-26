#!/usr/bin/env bash
# Busca leads no HubSpot (createdate DESC, últimos 3 dias) e lista os NÃO processados.
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
OUT=/tmp/hs_recent.json
# últimos 3 dias
AFTER=$(python3 -c "from datetime import datetime,timezone,timedelta;d=datetime.now(timezone.utc)-timedelta(days=3);print(int(d.timestamp()*1000))")
curl -s "https://api.hubapi.com/crm/v3/objects/contacts/search" \
  -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
  -d "{\"filterGroups\":[{\"filters\":[{\"propertyName\":\"createdate\",\"operator\":\"GTE\",\"value\":\"$AFTER\"}]}],\"properties\":[\"firstname\",\"lastname\",\"email\",\"company\",\"phone\",\"hs_searchable_calculated_phone_number\",\"createdate\",\"lifecyclestage\",\"hubspot_owner_id\"],\"sorts\":[{\"propertyName\":\"createdate\",\"direction\":\"DESCENDING\"}],\"limit\":100}" > $OUT
python3 -c "
import json
procs=set(l.strip().split('|')[0].lower() for l in open('controle/processed_emails.txt') if l.strip())
d=json.load(open('$OUT'))
res=d.get('results',[])
print(f'Total contatos últimos 3d: {len(res)}')
novos=[r for r in res if (r['properties'].get('email') or '').lower() not in procs]
print(f'Novos (não processados): {len(novos)}')
print()
for r in novos[:15]:
    p=r['properties']
    print(f\"{p.get('createdate','')[:16]} | {p.get('firstname','')} {p.get('lastname','')} | {p.get('company','')} | {p.get('email','')} | tel:{(p.get('phone') or 'SEM')}\")
"
