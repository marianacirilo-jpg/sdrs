#!/usr/bin/env bash
# Dispatch lumaville MQL: text -> PDF to lead, then mirror text+PDF to grupo.
set -u
PROJ="/root/zydon-prospeccao"
BRIDGE="http://127.0.0.1:4500"
LEAD_JID="553788086699@s.whatsapp.net"
GRUPO="120363408131718880@g.us"
PDF="$PROJ/Potencial-Digitalizacao-lumaville.pdf"
THUMB="$PROJ/pdfs/lumaville_thumb.jpg"

MSG='Bom dia, Lucilene, tudo bem? Aqui é a Mariana, da Zydon.
A partir do que você respondeu no nosso diagnóstico, preparei um material sobre o potencial de digitalização B2B da Luma Ville. Te mando em PDF aqui.
Em resumo, dá pras suas revendedoras e lojistas pedirem coleção direto pelo catálogo, a qualquer hora, em vez de depender só do showroom e do WhatsApp. Um consultor nosso jaja entra em contato com você para fazer um diagnóstico mais completo da Luma Ville e te mostrar isso na prática. Pode ser?'

echo "=== 1. TEXT -> LEAD ==="
curl -s -m 30 -X POST "$BRIDGE/send" -H "Content-Type: application/json" \
  -d "$(python3 -c "import json,sys; print(json.dumps({'to':'$LEAD_JID','text':sys.argv[1]}))" "$MSG")"
echo ""

echo "=== 2. PDF -> LEAD ==="
curl -s -m 60 -X POST "$BRIDGE/send-file" -H "Content-Type: application/json" \
  -d "{\"to\":\"$LEAD_JID\",\"filePath\":\"$PDF\",\"fileName\":\"Potencial-Digitalizacao-Luma-Ville.pdf\",\"thumbnailPath\":\"$THUMB\"}"
echo ""

echo "=== 3. TEXT -> GRUPO (mirror) ==="
curl -s -m 30 -X POST "$BRIDGE/send" -H "Content-Type: application/json" \
  -d "$(python3 -c "import json,sys; print(json.dumps({'to':'$GRUPO','text':sys.argv[1]}))" "$MSG")"
echo ""

echo "=== 4. PDF -> GRUPO (mirror) ==="
curl -s -m 60 -X POST "$BRIDGE/send-file" -H "Content-Type: application/json" \
  -d "{\"to\":\"$GRUPO\",\"filePath\":\"$PDF\",\"fileName\":\"Potencial-Digitalizacao-Luma-Ville.pdf\",\"thumbnailPath\":\"$THUMB\"}"
echo ""
echo "=== DISPATCH DONE ==="
