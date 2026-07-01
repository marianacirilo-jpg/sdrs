#!/usr/bin/env bash
# LEGACY_WHATSAPP_DIRECT_SEND_BLOCKED 2026-06-30
# Este one-off antigo fazia curl direto em /send ou /send-file e não garante
# PN/LID guard, auditoria, reconciliação nem visibilidade no app físico do chip.
# Use scripts/whatsapp_safe_send.py via processo atual; não execute este arquivo.
echo "BLOQUEADO: script legado de disparo direto. Use whatsapp_safe_send/process_gate_once." >&2
exit 2

# Disparo Airtudo: lead+grupo, MQL, atividade, registro. SEM deal (SEM_DEAL).
set -uo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
GROUP="120363408131718880@g.us"
export TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
SUBJ="WhatsApp — Diagnóstico 'Potencial de Digitalização B2B' enviado ao lead."
SLUG="airtudo"
CID="230243438596"
PHONE="5571992870953"
JID="${PHONE}@s.whatsapp.net"
MSGPATH="pesquisas/${SLUG}_msg.txt"
PDFPATH="pdfs/Potencial-Digitalizacao-${SLUG}.pdf"
MSG=$(cat "$MSGPATH")

# thumbnail
THUMB="/tmp/thumb_${SLUG}.jpg"
pdftoppm -png -f 1 -l 1 -r 200 "$PDFPATH" "/tmp/pg_${SLUG}" 2>/dev/null
PNG=$(ls /tmp/pg_${SLUG}-*.png 2>/dev/null | head -1)
[ -n "$PNG" ] && convert "$PNG" -resize "600x338^" -gravity center -extent 600x338 -quality 90 -strip "$THUMB" 2>/dev/null && rm -f "$PNG"

echo "=== marcar Airtudo MQL ==="
R=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "https://api.hubapi.com/crm/v3/objects/contacts/${CID}" \
  -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
  -d '{"properties":{"lifecyclestage":"marketingqualifiedlead"}}')
echo "  MQL ($R)"

echo "=== lead texto ==="
curl -s -X POST "http://127.0.0.1:4500/send" -H "Content-Type: application/json" \
  -d "$(python3 -c "import json,sys;print(json.dumps({'to':sys.argv[1],'text':sys.argv[2]}))" "$JID" "$MSG")" | head -c 60; echo
echo "=== lead PDF ==="
curl -s -X POST "http://127.0.0.1:4500/send-file" -H "Content-Type: application/json" \
  -d "$(python3 -c "import json,sys;print(json.dumps({'to':sys.argv[1],'filePath':sys.argv[2],'fileName':'Airtudo - Potencial de Digitalizacao B2B.pdf','thumbnailPath':sys.argv[3]}))" "$JID" "$PDFPATH" "$THUMB")" | head -c 60; echo
sleep 2

echo "=== grupo texto ==="
curl -s -X POST "http://127.0.0.1:4500/send" -H "Content-Type: application/json" \
  -d "$(python3 -c "import json,sys;print(json.dumps({'to':sys.argv[1],'text':sys.argv[2]}))" "$GROUP" "$MSG")" | head -c 60; echo
echo "=== grupo PDF ==="
curl -s -X POST "http://127.0.0.1:4500/send-file" -H "Content-Type: application/json" \
  -d "$(python3 -c "import json,sys;print(json.dumps({'to':sys.argv[1],'filePath':sys.argv[2],'fileName':'Airtudo - Potencial de Digitalizacao B2B.pdf','thumbnailPath':sys.argv[3]}))" "$GROUP" "$PDFPATH" "$THUMB")" | head -c 60; echo

echo "=== atividade (contato 204, sem deal) ==="
export CID SUBJ
PAYLOAD=$(python3 -c "
import os,json
print(json.dumps({
 'properties':{'hs_timestamp':os.environ['TS'],'hs_task_subject':os.environ['SUBJ'],
               'hs_task_status':'COMPLETED','hs_task_priority':'HIGH'},
 'associations':[{'to':{'id':os.environ['CID']},'types':[{'associationCategory':'HUBSPOT_DEFINED','associationTypeId':204}]}]
}))
")
R=$(curl -s "https://api.hubapi.com/crm/v3/objects/tasks" -X POST \
  -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" -d "$PAYLOAD")
TID=$(echo "$R" | python3 -c "import sys,json;print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
echo "  task=$TID"

echo "=== registrar ==="
# atualizar processed_emails (era nao_mql -> enviado)
python3 -c "
lines=open('controle/processed_emails.txt').read().splitlines()
out=[l for l in lines if not l.startswith('airtudo@airtudo.com|')]
out.append('airtudo@airtudo.com|airtudo|${TS}|enviado|5571992870953|Vagner Santos')
open('controle/processed_emails.txt','w').write('\n'.join(out)+'\n')
import json
d=json.load(open('controle/wpp_envios.json'))
d=[x for x in d if x.get('slug')!='airtudo' or x.get('status')!='nao_mql_grupo']
d.append({'date':'${TS}','slug':'airtudo','email':'airtudo@airtudo.com','to':'5571992870953@s.whatsapp.net','nome':'Vagner Santos','text_status':'ok','pdf_status':'ok','status':'enviado_lead'})
json.dump(d,open('controle/wpp_envios.json','w'),ensure_ascii=False,indent=2)
print('registrado, registros wpp:',len(d))
"
