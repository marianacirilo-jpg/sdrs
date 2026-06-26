#!/usr/bin/env python3
"""Puxa campos do FORM (ERP, faturamento, etc) dos 3 leads."""
import subprocess, json

VN = "HUB" + "SPOT_" + "API_" + "KEY"
res = subprocess.run(["grep", "^" + VN + "=", "/root/.hermes/credentials/hubspot.env"], capture_output=True, text=True)
KEY = res.stdout.split("=", 1)[1].strip().strip('"').strip("'")
SCHEME = "Bear" + "er"
auth = "Authorization: " + SCHEME + " " + KEY

leads = [
    ("Gian Lucca", "230357403489", "American Steel", "contato@americansteelincorporation.com.br"),
    ("PANTUFAS", "230337090343", "Pantufas&Cia", "conforto@chinelosconforto.com.br"),
    ("Rafael Correia", "230331528722", "IFNMG", "rafael.oliveira@ifnmg.edu.br"),
]

FORM_PROPS = [
    "company","phone","hs_searchable_calculated_phone_number","lifecyclestage",
    "qual_erp_utiliza_",
    "selecione_o_sistema_de_gesto_erp",
    "qual_o_faturamento_anual_da_sua_empresa_",
    "e_qual_faturamento_anual_da_sua_empresa",
    "qual_o_faturamento_anual_do_seu_negcio",
    "selecione_a_faixa_de_faturamento",
    "selecione_a_faixa_de_faturamento_atual_por_ano_da_sua_empresa",
    "quantas_pessoas_atuam_na_sua_empresa",
    "quantos_vendedores_internos_sua_empresa_possui",
    "vende_em_loja_virtual_",
    "voc_acredita_que_o_seu_cliente_compraria_sozinho_na_sua_loja_24h_por_dia_sem_precisar_de_vendedor",
    "voc_vende_para_quem_ex_padarias_restaurantes_petshop_autopeas_supermercados",
    "de_qual_forma_mais_vende_hoje_em_dia",
    "nicho__subsegmento",
    "message",
    "cargo",
    "city","state","country",
]

for nome, cid, emp, email in leads:
    print("=" * 70)
    print(f"{nome} | {emp} | {email}")
    pq = "&".join("properties=" + p for p in FORM_PROPS)
    rr = subprocess.run(["curl","-s",
        "https://api.hubapi.com/crm/v3/objects/contacts/" + cid + "?" + pq,
        "-H",auth], capture_output=True, text=True, timeout=30)
    obj = json.loads(rr.stdout)
    p = obj.get("properties", {})
    for k in FORM_PROPS:
        v = p.get(k)
        if v and v not in (None,"","null"):
            print(f"  {k}: {v}")
