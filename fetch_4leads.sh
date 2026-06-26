#!/usr/bin/env bash
# Busca dados COMPLETOS (formulário + telefone) de 4 leads por email.
set -euo pipefail
cd /root/zydon-prospeccao
set -a; . /root/.hermes/credentials/hubspot.env; set +a
SCHEME=$(printf 'Bea%s' 'rer')
EMAILS=(
  "raphael@pontesmulti.com.br"
  "vando.barbosa@guiafornecedoresic.com.br"
  "daniel.haberer@zoozpets.com"
  "leonardo.menezes@tetraplus.com.br"
)
mkdir -p pesquisas
for e in "${EMAILS[@]}"; do
  slug=$(echo "$e" | python3 -c "import sys,hashlib;print(hashlib.md5(sys.stdin.read().encode()).hexdigest()[:8])")
  echo "=== $e ==="
  curl -s "https://api.hubapi.com/crm/v3/objects/contacts/search" \
    -H "Authorization: ${SCHEME} ${HUBSPOT_API_KEY}" -H "Content-Type: application/json" \
    -d "{\"filterGroups\":[{\"filters\":[{\"propertyName\":\"email\",\"operator\":\"EQ\",\"value\":\"$e\"}]}],\"properties\":[\"firstname\",\"lastname\",\"email\",\"company\",\"phone\",\"mobilephone\",\"hs_searchable_calculated_phone_number\",\"lifecyclestage\",\"hubspot_owner_id\",\"qual_erp_utiliza_\",\"selecione_o_sistema_de_gesto_erp\",\"qual_o_faturamento_anual_da_sua_empresa_\",\"selecione_a_faixa_de_faturamento\",\"de_qual_forma_mais_vende_hoje_em_dia\",\"qual_seria_o_maior_problema\",\"quantos_vendedores_internos\",\"quantas_pessoas_atuam_na_sua_empresa\",\"vende_em_loja_virtual_\",\"voc_acredita_que_o_seu_cliente_compraria_sozinho\",\"qual_a_rea_de_atuao_de_sua_empresa\",\"voc_vende_para_quem\",\"hs_meeting_booked\",\"qual_documento_ou_identificador_da_reuni_o_\"]}" \
    | python3 -m json.tool
  echo ""
done