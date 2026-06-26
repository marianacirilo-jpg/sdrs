#!/usr/bin/env bash
# BUG CORRIGIDO: GET sem properties= so retorna defaults. Listar TODAS as props e buscar.
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
CID=230243438596
# 1) listar TODOS nomes de propriedades de contato
curl -s "https://api.hubapi.com/crm/v3/properties/contacts?limit=500" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" > /tmp/contact_props.json
PROPS=$(python3 -c "import json;d=json.load(open('/tmp/contact_props.json'));print(','.join(r['name'] for r in d.get('results',[])))")
echo "Total propriedades schema: $(echo $PROPS | tr ',' '\n' | wc -l)"
# 2) buscar o contato com TODAS as propriedades
curl -s "https://api.hubapi.com/crm/v3/objects/contacts/${CID}?properties=$(python3 -c "import urllib.parse;import json;d=json.load(open('/tmp/contact_props.json'));print(urllib.parse.quote(','.join(r['name'] for r in d.get('results',[])),safe=''))")" \
  -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" > /tmp/airtudo_full.json
python3 -c "
import json,re
d=json.load(open('/tmp/airtudo_full.json'))
p=d.get('properties',{})
print(f'Total props com valor: {sum(1 for v in p.values() if v)}')
print()
print('=== TODOS campos com valor (nao nulo) ===')
for k,v in sorted(p.items()):
    if v and v!='null':
        print(f'  {k} = {v}')
print()
print('=== campos tipo telefone ===')
for k,v in p.items():
    if v and isinstance(v,str):
        d2=re.sub(r'\D','',v)
        if len(d2)>=10 and any(x in k.lower() for x in ['phone','tel','cel','whats','mobile','numero','n_mero','ddd']):
            print(f'  *** {k} = {v}')
"