#!/usr/bin/env bash
set -uo pipefail
cd /root/zydon-prospeccao
GROUP="120363408131718880@g.us"
export TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# NAO_MQL ib-silva
MSG1="⛔ Não qualificado (MQL): Vando / I B silva — opera o Guia Fornecedores da Indústria da Construção, uma plataforma de mídia/diretório que vende espaço publicitário, não produtos físicos. Sem catálogo nem pedidos recorrentes de mercadoria. Fora do perfil de atacado/distribuidor/indústria — sem diagnóstico enviado."
echo "-> grupo ib-silva:"
curl -s -X POST "http://127.0.0.1:4500/send" -H "Content-Type: application/json" \
  -d "$(python3 -c "import json,sys;print(json.dumps({'to':sys.argv[1],'text':sys.argv[2]}))" "$GROUP" "$MSG1")" | head -c 60; echo
sleep 3

# NAO_MQL airtudo
MSG2="⛔ Não qualificado (MQL): Vagner / Airtudo — é varejo B2C de armas, airsoft, munição e equipamentos táticos (a categoria '3D' do site são chaveiros impressos; 'insumos' são recarga de munição), não e-commerce B2B de impressão 3D como constava no cadastro. Varejo ao consumidor final, fora do perfil B2B — sem diagnóstico enviado."
echo "-> grupo airtudo:"
curl -s -X POST "http://127.0.0.1:4500/send" -H "Content-Type: application/json" \
  -d "$(python3 -c "import json,sys;print(json.dumps({'to':sys.argv[1],'text':sys.argv[2]}))" "$GROUP" "$MSG2")" | head -c 60; echo

# Registrar NAO_MQL em processed_emails
echo "vando.barbosa@guiafornecedoresic.com.br|ib-silva|${TS}|nao_mql|11996142513|Vando Barboza" >> controle/processed_emails.txt
echo "airtudo@airtudo.com|airtudo|${TS}|nao_mql|5571992870953|Vagner Santos" >> controle/processed_emails.txt
python3 -c "
import json
d=json.load(open('controle/wpp_envios.json'))
d.append({'date':'${TS}','slug':'ib-silva','email':'vando.barbosa@guiafornecedoresic.com.br','to':'grupo','status':'nao_mql_grupo'})
d.append({'date':'${TS}','slug':'airtudo','email':'airtudo@airtudo.com','to':'grupo','status':'nao_mql_grupo'})
json.dump(d,open('controle/wpp_envios.json','w'),ensure_ascii=False,indent=2)
print('registrados ib-silva + airtudo como nao_mql')
"
echo "=== processed_emails total ==="
wc -l controle/processed_emails.txt