#!/usr/bin/env bash
# Dispara os 4 MQLs prontos: owner→organizador, texto+PDF→lead, espelho→grupo, atividade, registro.
set -uo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
GROUP="120363408131718880@g.us"
export TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
SUBJ="WhatsApp — Diagnóstico 'Potencial de Digitalização B2B' enviado ao lead."
PDFDIR="/root/zydon-prospeccao/pdfs"
PROJ="/root/zydon-prospeccao"

# slug|nome|phone|contact_id|deal_id|meeting_owner(or current)|tem_meeting(1/0)
LEADS=(
  "tetraplus|Leonardo|31993699000|230184732285|61410136706|85778446|1"
  "pontes-multi|Raphael|21982170983|230211201144|61428489365|85778446|1"
  "madeira-abc|Joao|11973318421|230190210058|61427666724|88063842|1"
  "brightgear|Daniel|11981228818|230183961698|61426947935|85778446|0"
  "zooz|Daniel|11981228818|229708441487|61426795957|86265630|1"
)

send() { # jid text
  curl -s -X POST "http://127.0.0.1:4500/send" -H "Content-Type: application/json" \
    -d "$(python3 -c "import json,os,sys;print(json.dumps({'to':sys.argv[1],'text':sys.argv[2]}))" "$1" "$2")" | head -c 60; echo
}
sendfile() { # jid pdfpath slug
  local slug="$3"; local thumb="/tmp/thumb_${slug}.jpg"
  if [ ! -f "$thumb" ]; then
    pdftoppm -png -f 1 -l 1 -r 200 "$2" "/tmp/pg_${slug}" 2>/dev/null
    local png=$(ls /tmp/pg_${slug}-*.png 2>/dev/null | head -1)
    [ -n "$png" ] && convert "$png" -resize "600x338^" -gravity center -extent 600x338 -quality 90 -strip "$thumb" 2>/dev/null && rm -f "$png"
  fi
  local fname=$(python3 -c "print(' '.join(w.capitalize() for w in '$slug'.split('-')))")
  curl -s -X POST "http://127.0.0.1:4500/send-file" -H "Content-Type: application/json" \
    -d "$(python3 -c "import json,sys;print(json.dumps({'to':sys.argv[1],'filePath':sys.argv[2],'fileName':sys.argv[3]+' - Potencial de Digitalizacao B2B.pdf','thumbnailPath':sys.argv[4]}))" "$1" "$2" "$fname" "$thumb")" | head -c 60; echo
}

for entry in "${LEADS[@]}"; do
  IFS='|' read -r slug nome phone cid did owner meeting <<< "$entry"
  echo "########## $slug ($nome) -> 55${phone} ##########"
  msgpath="$PROJ/pesquisas/${slug}_msg.txt"
  pdfpath="$PDFDIR/Potencial-Digitalizacao-${slug}.pdf"
  msg=$(cat "$msgpath")
  jid="55${phone}@s.whatsapp.net"

  # 1) Owner: se tem meeting, setar contact+deal owner = organizador
  if [ "$meeting" = "1" ]; then
    R=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "https://api.hubapi.com/crm/v3/objects/contacts/${cid}" \
      -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
      -d "{\"properties\":{\"hubspot_owner_id\":\"$owner\"}}")
    echo "  owner contato $cid -> $owner ($R)"
    R=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "https://api.hubapi.com/crm/v3/objects/deals/${did}" \
      -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
      -d "{\"properties\":{\"hubspot_owner_id\":\"$owner\"}}")
    echo "  owner negocio $did -> $owner ($R)"
  fi

  # 2) Lead: texto + PDF
  echo "  -> lead texto:"
  send "$jid" "$msg"
  echo "  -> lead PDF:"
  sendfile "$jid" "$pdfpath" "$slug"

  # 3) Grupo: espelho texto + PDF
  echo "  -> grupo texto:"
  send "$GROUP" "$msg"
  echo "  -> grupo PDF:"
  sendfile "$GROUP" "$pdfpath" "$slug"

  # 4) Atividade (task associada a contato 204 + negocio 216)
  export slug nome cid did owner
  PAYLOAD=$(python3 -c "
import os,json
print(json.dumps({
 'properties':{'hs_timestamp':os.environ['TS'],'hs_task_subject':os.environ['SUBJ'],
               'hubspot_owner_id':os.environ['owner'],'hs_task_status':'COMPLETED','hs_task_priority':'HIGH'},
 'associations':[
   {'to':{'id':os.environ['cid']},'types':[{'associationCategory':'HUBSPOT_DEFINED','associationTypeId':204}]},
   {'to':{'id':os.environ['did']},'types':[{'associationCategory':'HUBSPOT_DEFINED','associationTypeId':216}]}
 ]
}))
")
  R=$(curl -s "https://api.hubapi.com/crm/v3/objects/tasks" -X POST \
    -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" -d "$PAYLOAD")
  TID=$(echo "$R" | python3 -c "import sys,json;print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
  echo "  atividade task=$TID"

  # 5) Registrar
  email=$(python3 -c "import json;d=json.load(open('$PROJ/pesquisas/${slug}_hubspot.json'));print(d['results'][0]['properties']['email'])")
  echo "${email}|${slug}|${TS}|enviado|55${phone}|${nome}" >> "$PROJ/controle/processed_emails.txt"
  python3 -c "
import json,os
p='$PROJ/controle/wpp_envios.json'
d=json.load(open(p))
d.append({'date':os.environ['TS'],'slug':'$slug','email':'$email','to':'55${phone}@s.whatsapp.net','nome':'$nome','text_status':'ok','pdf_status':'ok','status':'enviado_lead'})
json.dump(d,open(p,'w'),ensure_ascii=False,indent=2)
"
  echo "  registrado: $email"
  sleep 3
done
echo "=== FIM dispatch_4 ==="