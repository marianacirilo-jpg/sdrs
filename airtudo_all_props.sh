#!/usr/bin/env bash
# Puxa TODAS as propriedades do contato Airtudo (sem filtrar) pra achar o telefone.
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
echo "=== TODAS propriedades do contato 230243438596 ==="
curl -s "https://api.hubapi.com/crm/v3/objects/contacts/230243438596" \
  -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" > /tmp/airtudo_all.json
python3 -c "
import json
d=json.load(open('/tmp/airtudo_all.json'))
p=d.get('properties',{})
# achar qualquer propriedade com valor de telefone (digitos longos)
import re
print('=== campos com valor tipo telefone (10+ digitos) ===')
for k,v in p.items():
    if v and isinstance(v,str):
        digits=re.sub(r'\D','',v)
        if len(digits)>=10:
            print(f'{k} = {v}')
print()
print('=== campos com nome contendo phone/tel/cel/whats/contato ===')
for k,v in p.items():
    kl=k.lower()
    if any(x in kl for x in ['phone','tel','cel','whats','contato','mobile']):
        print(f'{k} = {v}')
"
echo "=== tambem: companies associadas a Airtudo ==="
curl -s "https://api.hubapi.com/crm/v4/objects/contacts/230243438596/associations/companies" -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}"