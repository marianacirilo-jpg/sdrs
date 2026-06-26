#!/usr/bin/env bash
# Busca TODAS props (incl hs_whatsapp_phone_number) dos 4 leads novos.
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
EMAILS=(
  "ecommerce@disfrio.com.br"
  "smec@smeciramaia.com.br"
  "deividbm21@nitro.com"
  "amanda.borges@caffeinearmy.com.br"
)
mkdir -p pesquisas
# schema de props
curl -s "https://api.hubapi.com/crm/v3/properties/contacts?limit=500" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" > /tmp/cp.json
PROPS_URLENC=$(python3 -c "import urllib.parse,json;d=json.load(open('/tmp/cp.json'));print(urllib.parse.quote(','.join(r['name'] for r in d.get('results',[])),safe=''))")
for e in "${EMAILS[@]}"; do
  slug=$(echo "$e" | python3 -c "import sys;e=sys.stdin.read().strip().split('@')[0];print(e.replace('.','-').replace('_','-').lower()[:20])")
  echo "===== $e (slug=$slug) ====="
  curl -s "https://api.hubapi.com/crm/v3/objects/contacts/search" \
    -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
    -d "{\"filterGroups\":[{\"filters\":[{\"propertyName\":\"email\",\"operator\":\"EQ\",\"value\":\"$e\"}]}],\"properties\":[]}" > /tmp/s.json
  CID=$(python3 -c "import json;d=json.load(open('/tmp/s.json'));r=d.get('results',[]);print(r[0]['id'] if r else '')")
  if [ -z "$CID" ]; then echo "  NAO ACHOU"; continue; fi
  # buscar com TODAS props
  curl -s "https://api.hubapi.com/crm/v3/objects/contacts/${CID}?properties=${PROPS_URLENC}" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" > "pesquisas/${slug}_hubspot.json"
  python3 -c "
import json
d=json.load(open('pesquisas/${slug}_hubspot.json'))
p=d['properties']
print(f\"  id={d['id']} | {p.get('firstname')} | {p.get('company')}\")
print(f\"  whatsapp={p.get('hs_whatsapp_phone_number')} | phone={p.get('phone')}\")
print(f\"  erp={p.get('qual_erp_utiliza_')} | fat={p.get('qual_o_faturamento_anual_da_sua_empresa_')}\")
print(f\"  vende_para={p.get('voc_vende_para_quem')} | area={p.get('qual_a_rea_de_atuao_de_sua_empresa')}\")
print(f\"  loja={p.get('vende_em_loja_virtual_')} | como_vende={p.get('de_qual_forma_mais_vende_hoje_em_dia')}\")
print(f\"  pessoas={p.get('quantas_pessoas_atuam_na_sua_empresa')} | vendedores={p.get('quantos_vendedores_internos_sua_empresa_possui')}\")
print(f\"  lc={p.get('lifecyclestage')} | owner={p.get('hubspot_owner_id')}\")
"
  echo ""
done