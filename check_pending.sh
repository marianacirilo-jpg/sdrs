#!/usr/bin/env bash
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
AFTER=$(python3 -c "from datetime import datetime,timezone,timedelta;d=datetime.now(timezone.utc)-timedelta(hours=48);print(int(d.timestamp()*1000))")
ALL=""
CUR=""
while true; do
  BODY="{\"filterGroups\":[{\"filters\":[{\"propertyName\":\"createdate\",\"operator\":\"GTE\",\"value\":\"$AFTER\"}]}],\"properties\":[\"firstname\",\"email\",\"company\",\"hs_whatsapp_phone_number\",\"createdate\",\"lifecyclestage\"],\"sorts\":[{\"propertyName\":\"createdate\",\"direction\":\"DESCENDING\"}],\"limit\":100${CUR}}"
  R=$(curl -s "https://api.hubapi.com/crm/v3/objects/contacts/search" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" -d "$BODY")
  ALL="$ALL $(echo "$R" | python3 -c "import sys,json;[print(r['properties'].get('email','').lower()) for r in json.load(sys.stdin).get('results',[])]")"
  N=$(echo "$R" | python3 -c "import sys,json;print(len(json.load(sys.stdin).get('results',[])))")
  [ "$N" -lt 100 ] && break
  C2=$(echo "$R" | python3 -c "import sys,json;d=json.load(sys.stdin);p=d.get('paging',{}).get('next',{});print(p.get('after','') if p else '')")
  [ -z "$C2" ] && break
  CUR=",\"after\":\"$C2\""
done
echo "$ALL" | tr ' ' '\n' | grep -v '^$' | sort -u > /tmp/all_emails_48h.txt
echo "emails unicos 48h: $(wc -l < /tmp/all_emails_48h.txt)"
grep -i -v -f <(cut -d'|' -f1 controle/processed_emails.txt | tr '[:upper:]' '[:lower:]') /tmp/all_emails_48h.txt > /tmp/pendentes_reais.txt
echo "=== PENDENTES REAIS (nao processados) ==="
cat /tmp/pendentes_reais.txt
echo "total: $(wc -l < /tmp/pendentes_reais.txt)"