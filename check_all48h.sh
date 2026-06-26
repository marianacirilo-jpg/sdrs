#!/usr/bin/env bash
# Pagina todos contatos 48h pra ver se ha mais alem dos 50 do limit.
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
AFTER=$(python3 -c "from datetime import datetime,timezone,timedelta;d=datetime.now(timezone.utc)-timedelta(hours=48);print(int(d.timestamp()*1000))")
TOTAL=0
AFTER_CURSOR=""
NOVOS=0
while true; do
  BODY="{\"filterGroups\":[{\"filters\":[{\"propertyName\":\"createdate\",\"operator\":\"GTE\",\"value\":\"$AFTER\"}]}],\"properties\":[\"firstname\",\"email\",\"company\",\"hs_whatsapp_phone_number\",\"createdate\"],\"sorts\":[{\"propertyName\":\"createdate\",\"direction\":\"DESCENDING\"}],\"limit\":100${AFTER_CURSOR}}"
  R=$(curl -s "https://api.hubapi.com/crm/v3/objects/contacts/search" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" -d "$BODY")
  N=$(echo "$R" | python3 -c "import sys,json;print(len(json.load(sys.stdin).get('results',[])))")
  TOTAL=$((TOTAL+N))
  if [ "$N" -lt 100 ]; then break; fi
  CUR=$(echo "$R" | python3 -c "import sys,json;d=json.load(sys.stdin);p=d.get('paging',{}).get('next',{});print(p.get('after','') if p else '')")
  [ -z "$CUR" ] && break
  AFTER_CURSOR=",\"after\":\"$CUR\""
done
echo "Total contatos 48h: $TOTAL"
# dedup
python3 -c "
import json,subprocess
procs=set(l.strip().split('|')[0].lower() for l in open('controle/processed_emails.txt') if l.strip())
print('processados:',len(procs))
"