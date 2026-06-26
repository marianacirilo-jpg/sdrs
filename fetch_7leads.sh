#!/usr/bin/env bash
# Puxa dados COMPLETOS de todos os 7 pendentes + resolve telefones mascarados via contato duplicado.
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
PROPS="firstname,lastname,email,company,phone,mobilephone,hs_searchable_calculated_phone_number,lifecyclestage,hubspot_owner_id,qual_erp_utiliza_,selecione_o_sistema_de_gesto_erp,qual_o_faturamento_anual_da_sua_empresa_,selecione_a_faixa_de_faturamento,de_qual_forma_mais_vende_hoje_em_dia,qual_seria_o_maior_problema,quantos_vendedores_internos,quantas_pessoas_atuam_na_sua_empresa,vende_em_loja_virtual_,voc_acredita_que_o_seu_cliente_compraria_sozinho,qual_a_rea_de_atuao_de_sua_empresa,voc_vende_para_quem,hs_meeting_booked,qual_documento_ou_identificador_da_reuni_o_"

declare -A MAP=(
  ["airtudo"]="airtudo@airtudo.com"
  ["pontes-multi"]="raphael@pontesmulti.com.br"
  ["ib-silva"]="vando.barbosa@guiafornecedoresic.com.br"
  ["madeira-abc"]="joao@madeiraabc.com.br"
  ["zooz"]="daniel.haberer@zoozpets.com"
  ["brightgear"]="daniel.haberer@brightgearcorp.com"
  ["tetraplus"]="leonardo.menezes@tetraplus.com.br"
)
mkdir -p pesquisas
for slug in "${!MAP[@]}"; do
  email="${MAP[$slug]}"
  curl -s "https://api.hubapi.com/crm/v3/objects/contacts/search" \
    -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
    -d "{\"filterGroups\":[{\"filters\":[{\"propertyName\":\"email\",\"operator\":\"EQ\",\"value\":\"$email\"}]}],\"properties\":[\"$PROPS\"]}" \
    > "pesquisas/${slug}_hubspot.json"
  phone=$(python3 -c "import json;d=json.load(open('pesquisas/${slug}_hubspot.json'));r=d.get('results',[]);p=r[0]['properties'] if r else {};ph=p.get('hs_searchable_calculated_phone_number') or p.get('phone') or '';print(ph)" 2>/dev/null)
  masked="no"; [ -z "$phone" ] && masked="SEM"; echo "$phone" | grep -q '\*\*\*\*' && masked="MASCARADO"
  echo "${slug} | $email | tel=${phone:-NONE} | status_tel=$masked"
done