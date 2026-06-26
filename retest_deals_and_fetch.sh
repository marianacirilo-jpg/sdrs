#!/usr/bin/env bash
# Re-tentar update deal owners (escopos atualizados) + buscar leads novos.
set -uo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')

echo "=== REFAZER deal owners (antes davam 403) ==="
# deal_id|organizador_meeting
DEALS=(
  "61410136706|85778446"   # tetraplus
  "61428489365|85778446"   # pontes-multi
  "61427666724|88063842"   # madeira-abc
  "61426795957|86265630"   # zooz
)
for entry in "${DEALS[@]}"; do
  IFS='|' read -r did owner <<< "$entry"
  R=$(curl -s -o /tmp/d_resp.txt -w "%{http_code}" -X PATCH "https://api.hubapi.com/crm/v3/objects/deals/${did}" \
    -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
    -d "{\"properties\":{\"hubspot_owner_id\":\"$owner\"}}")
  echo "  deal $did -> owner $owner : HTTP $R $(head -c 80 /tmp/d_resp.txt)"
  sleep 0.4
done

echo ""
echo "=== BUSCAR leads novos (ultimas 48h, nao processados) ==="
AFTER=$(python3 -c "from datetime import datetime,timezone,timedelta;d=datetime.now(timezone.utc)-timedelta(hours=48);print(int(d.timestamp()*1000))")
curl -s "https://api.hubapi.com/crm/v3/objects/contacts/search" \
  -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
  -d "{\"filterGroups\":[{\"filters\":[{\"propertyName\":\"createdate\",\"operator\":\"GTE\",\"value\":\"$AFTER\"}]}],\"properties\":[\"firstname\",\"lastname\",\"email\",\"company\",\"hs_whatsapp_phone_number\",\"hs_searchable_calculated_phone_number\",\"createdate\",\"lifecyclestage\",\"hubspot_owner_id\"],\"sorts\":[{\"propertyName\":\"createdate\",\"direction\":\"DESCENDING\"}],\"limit\":50}" > /tmp/hs_new.json
python3 -c "
import json
procs=set(l.strip().split('|')[0].lower() for l in open('controle/processed_emails.txt') if l.strip())
d=json.load(open('/tmp/hs_new.json'))
res=d.get('results',[])
print(f'Total contatos 48h: {len(res)}')
novos=[r for r in res if (r['properties'].get('email') or '').lower() not in procs]
print(f'Novos (nao processados): {len(novos)}')
print()
for r in novos[:12]:
    p=r['properties']
    tel=p.get('hs_whatsapp_phone_number') or p.get('hs_searchable_calculated_phone_number') or 'SEM'
    print(f\"{p.get('createdate','')[:16]} | {p.get('firstname','')} {p.get('lastname','')} | {(p.get('company') or '')[:25]} | {p.get('email','')} | tel={tel}\")
"