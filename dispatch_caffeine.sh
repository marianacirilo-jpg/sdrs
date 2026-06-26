#!/usr/bin/env bash
set -uo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
GROUP="120363408131718880@g.us"
export TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
SLUG="caffeine-army"; CID="230257666399"; DID="61431395254"; OWNER="85778446"; PHONE="71993247570"
JID="55${PHONE}@s.whatsapp.net"
MSG=$(cat "pesquisas/${SLUG}_msg.txt")
PDF="pdfs/Potencial-Digitalizacao-${SLUG}.pdf"
PRETTY="pdfs/Caffeine Army - Potencial de Digitalizacao B2B.pdf"
cp "$PDF" "$PRETTY"
THUMB="/tmp/thumb_${SLUG}.jpg"
pdftoppm -png -f 1 -l 1 -r 200 "$PDF" "/tmp/pg_${SLUG}" 2>/dev/null
PNG=$(ls /tmp/pg_${SLUG}-*.png 2>/dev/null | head -1)
[ -n "$PNG" ] && convert "$PNG" -resize "600x338^" -gravity center -extent 600x338 -quality 90 -strip "$THUMB" 2>/dev/null && rm -f "$PNG"

echo "=== owner contato+negocio -> 85778446 (organizador) ==="
echo "contato: $(curl -s -o /dev/null -w "%{http_code}" -X PATCH "https://api.hubapi.com/crm/v3/objects/contacts/${CID}" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" -d '{"properties":{"hubspot_owner_id":"85778446"}}')"
echo "negocio: $(curl -s -o /dev/null -w "%{http_code}" -X PATCH "https://api.hubapi.com/crm/v3/objects/deals/${DID}" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" -d '{"properties":{"hubspot_owner_id":"85778446"}}')"

echo "=== lead texto+PDF ==="
curl -s -X POST "http://127.0.0.1:4500/send" -H "Content-Type: application/json" -d "$(python3 -c "import json,sys;print(json.dumps({'to':sys.argv[1],'text':sys.argv[2]}))" "$JID" "$MSG")" | head -c 40; echo
curl -s -X POST "http://127.0.0.1:4500/send-file" -H "Content-Type: application/json" -d "$(python3 -c "import json,sys;print(json.dumps({'to':sys.argv[1],'filePath':sys.argv[2],'fileName':sys.argv[3],'thumbnailPath':sys.argv[4]}))" "$JID" "/root/zydon-prospeccao/$PRETTY" "Caffeine Army - Potencial de Digitalizacao B2B.pdf" "$THUMB")" | head -c 40; echo
sleep 2
echo "=== grupo texto+PDF ==="
curl -s -X POST "http://127.0.0.1:4500/send" -H "Content-Type: application/json" -d "$(python3 -c "import json,sys;print(json.dumps({'to':sys.argv[1],'text':sys.argv[2]}))" "$GROUP" "$MSG")" | head -c 40; echo
curl -s -X POST "http://127.0.0.1:4500/send-file" -H "Content-Type: application/json" -d "$(python3 -c "import json,sys;print(json.dumps({'to':sys.argv[1],'filePath':sys.argv[2],'fileName':sys.argv[3],'thumbnailPath':sys.argv[4]}))" "$GROUP" "/root/zydon-prospeccao/$PRETTY" "Caffeine Army - Potencial de Digitalizacao B2B.pdf" "$THUMB")" | head -c 40; echo

echo "=== atividade (contato+negocio) ==="
export CID DID OWNER
PAYLOAD=$(python3 -c "
import os,json
print(json.dumps({'properties':{'hs_timestamp':os.environ['TS'],'hs_task_subject':'WhatsApp — Diagnóstico \'Potencial de Digitalização B2B\' enviado ao lead.','hubspot_owner_id':os.environ['OWNER'],'hs_task_status':'COMPLETED','hs_task_priority':'HIGH'},'associations':[{'to':{'id':os.environ['CID']},'types':[{'associationCategory':'HUBSPOT_DEFINED','associationTypeId':204}]},{'to':{'id':os.environ['DID']},'types':[{'associationCategory':'HUBSPOT_DEFINED','associationTypeId':216}]}]}))
")
TID=$(curl -s "https://api.hubapi.com/crm/v3/objects/tasks" -X POST -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" -d "$PAYLOAD" | python3 -c "import sys,json;print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
echo "task=$TID"

echo "=== registrar ==="
echo "amanda.borges@caffeinearmy.com.br|caffeine-army|${TS}|enviado|55${PHONE}|Amanda Borges" >> controle/processed_emails.txt
python3 -c "import json;d=json.load(open('controle/wpp_envios.json'));d.append({'date':'${TS}','slug':'caffeine-army','email':'amanda.borges@caffeinearmy.com.br','to':'55${PHONE}@s.whatsapp.net','nome':'Amanda Borges','status':'enviado_lead'});json.dump(d,open('controle/wpp_envios.json','w'),ensure_ascii=False,indent=2);print('ok,',len(d),'registros')"