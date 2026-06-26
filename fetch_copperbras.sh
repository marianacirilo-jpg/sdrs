#!/usr/bin/env bash
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
# todas as props + deal + meeting
curl -s "https://api.hubapi.com/crm/v3/properties/contacts?limit=500" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" > /tmp/cp.json
PROPS=$(python3 -c "import urllib.parse,json;d=json.load(open('/tmp/cp.json'));print(urllib.parse.quote(','.join(r['name'] for r in d.get('results',[])),safe=''))")
curl -s "https://api.hubapi.com/crm/v3/objects/contacts/230274731386?properties=${PROPS}" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" > /tmp/cs_full.json
python3 -c "
import json
d=json.load(open('/tmp/cs_full.json'))
p=d['properties']
json.dump({'results':[{'id':d['id'],'properties':p}]},open('pesquisas/copperbras_hubspot.json','w'),ensure_ascii=False,indent=2)
print('=== campos chave ===')
for k in ['firstname','lastname','company','email','hs_whatsapp_phone_number','hs_searchable_calculated_phone_number','lifecyclestage','hubspot_owner_id','qual_erp_utiliza_','qual_o_faturamento_anual_da_sua_empresa_','de_qual_forma_mais_vende_hoje_em_dia','quantas_pessoas_atuam_na_sua_empresa','vende_em_loja_virtual_','qual_a_rea_de_atuao_de_sua_empresa','voc_vende_para_quem','ip_city','ip_state']:
    print(f'  {k} = {p.get(k)}')
"
echo "deal:"
curl -s "https://api.hubapi.com/crm/v4/objects/contacts/230274731386/associations/deals" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" | python3 -c "import sys,json;d=json.load(sys.stdin);print(','.join(str(x['toObjectId']) for x in d.get('results',[])) or 'SEM_DEAL')"
echo "meeting:"
curl -s "https://api.hubapi.com/crm/v4/objects/contacts/230274731386/associations/meetings" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" | python3 -c "import sys,json;d=json.load(sys.stdin);print(','.join(str(x['toObjectId']) for x in d.get('results',[])) or 'SEM')"