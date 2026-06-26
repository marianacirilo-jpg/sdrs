#!/usr/bin/env python3
"""Fetch full properties for a list of contact IDs from HubSpot."""
import json
import os
import sys
import urllib.parse
import urllib.request

# Load creds
cred_path = os.path.expanduser("~/.hermes/credentials/hubspot.env")
key = None
with open(cred_path) as f:
    for line in f:
        line = line.strip()
        if line.startswith("HUBSPOT_API_KEY="):
            # strip optional quotes
            val = line.split("=", 1)[1].strip().strip('"').strip("'")
            key = val
if not key:
    print("ERROR: no HUBSPOT_API_KEY found"); sys.exit(1)

PROPS = ",".join([
    "email","firstname","lastname","company","phone","mobilephone",
    "hs_whatsapp_phone_number","hs_searchable_calculated_phone_number",
    "lifecyclestage","hs_lead_status","hubspot_owner_id","hs_meeting_booked",
    "qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados",
    "qual_erp_utiliza_","selecione_o_sistema_de_gesto_erp",
    "qual_o_faturamento_mensal_aproximado_da_sua_empresa",
    "qual_a_sua_maior_dor_hoje_na_gestao_de_pedidos",
    "voc_vende_para_quem","quantos_vendedores_voc_tem",
    "quantas_pessoas_trabalham_na_empresa","voc_tem_loja_virtual",
    "seus_clientes_podem_comprar_por_autosservico","cargo_e_rea",
    "qual_documento_ou_identificador_da_reuni_o_","createdate",
])

cids = sys.argv[1:]
for cid in cids:
    url = f"https://api.hubapi.com/crm/v3/objects/contacts/{cid}?properties={urllib.parse.quote(PROPS)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    print(f"===== CONTACT {cid} =====")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            d = json.loads(resp.read())
    except Exception as e:
        print(f"  ERROR: {e}")
        continue
    p = d.get("properties", {})
    for k in sorted(p.keys()):
        v = p.get(k)
        if v is not None and v != "":
            print(f"  {k} = {repr(v)}")
    print()
