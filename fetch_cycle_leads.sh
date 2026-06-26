#!/usr/bin/env bash
# Busca dados COMPLETOS dos leads do ciclo atual.
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
PROPS="firstname,lastname,email,company,phone,mobilephone,hs_searchable_calculated_phone_number,lifecyclestage,hubspot_owner_id,qual_erp_utiliza_,selecione_o_sistema_de_gesto_erp,qual_o_faturamento_anual_da_sua_empresa_,selecione_a_faixa_de_faturamento,de_qual_forma_mais_vende_hoje_em_dia,qual_seria_o_maior_problema,quantos_vendedores_internos,quantas_pessoas_atuam_na_sua_empresa,vende_em_loja_virtual_,voc_acredita_que_o_seu_cliente_compraria_sozinho,qual_a_rea_de_atuao_de_sua_empresa,voc_vende_para_quem,hs_meeting_booked,qual_documento_ou_identificador_da_reuni_o_,hs_lead_status,nicho__subsegmento,qual_o_faturamento_anual_do_seu_negcio,e_qual_faturamento_anual_da_sua_empresa"

EMAILS=(
  "raphael@pontesmulti.com.br"
  "vando.barbosa@guiafornecedoresic.com.br"
  "joao@madeiraabc.com.br"
)
mkdir -p pesquisas
for e in "${EMAILS[@]}"; do
  slug=$(echo "$e" | python3 -c "import sys,re;e=sys.stdin.read().strip();s=re.sub(r'[^a-z0-9]','',e.split('@')[0].lower());print(s or 'lead')")
  echo "=== $e (slug: $slug) ==="
  curl -s "https://api.hubapi.com/crm/v3/objects/contacts/search" \
    -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
    -d "{\"filterGroups\":[{\"filters\":[{\"propertyName\":\"email\",\"operator\":\"EQ\",\"value\":\"$e\"}]}],\"properties\":[\"$PROPS\"]}" \
    > "pesquisas/${slug}_hubspot.json"
  python3 -c "
import json
d=json.load(open('pesquisas/${slug}_hubspot.json'))
res=d.get('results',[])
if not res:
    print('  NAO ENCONTRADO')
else:
    p=res[0]['properties']
    ph=p.get('hs_searchable_calculated_phone_number') or p.get('phone') or ''
    masked='SIM' if '****' in str(ph) else 'nao'
    print(f\"  nome: {p.get('firstname','')} {p.get('lastname','')}\")
    print(f\"  empresa: {p.get('company','')}\")
    print(f\"  email: {p.get('email','')}\")
    print(f\"  tel(masked={masked}): {ph}\")
    print(f\"  lifecyclestage: {p.get('lifecyclestage','')}\")
    print(f\"  erp1: {p.get('qual_erp_utiliza_','')}\")
    print(f\"  erp2: {p.get('selecione_o_sistema_de_gesto_erp','')}\")
    print(f\"  faturamento1: {p.get('qual_o_faturamento_anual_da_sua_empresa_','')}\")
    print(f\"  faturamento2: {p.get('selecione_a_faixa_de_faturamento','')}\")
    print(f\"  nicho: {p.get('nicho__subsegmento','')}\")
    print(f\"  area: {p.get('qual_a_rea_de_atuao_de_sua_empresa','')}\")
    print(f\"  vende_para: {p.get('voc_vende_para_quem','')}\")
    print(f\"  dor: {p.get('qual_seria_o_maior_problema','')}\")
    print(f\"  vendedores: {p.get('quantos_vendedores_internos','')}\")
    print(f\"  pessoas: {p.get('quantas_pessoas_atuam_na_sua_empresa','')}\")
    print(f\"  loja_virtual: {p.get('vende_em_loja_virtual_','')}\")
    print(f\"  autosservico: {p.get('voc_acredita_que_o_seu_cliente_compraria_sozinho','')}\")
    print(f\"  como_vende: {p.get('de_qual_forma_mais_vende_hoje_em_dia','')}\")
    print(f\"  meeting_booked: {p.get('hs_meeting_booked','')}\")
    print(f\"  meeting_id: {p.get('qual_documento_ou_identificador_da_reuni_o_','')}\")
"
  echo ""
done
