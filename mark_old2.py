#!/usr/bin/env python3
"""Marca TODOS leads 19-20/06 como done (range + paginacao) e busca os 2 novos."""
import sys, json, urllib.request
sys.path.insert(0, "motor")
from ciclo import HEADERS, BASE_URL, load_processed, save_processed

processed = load_processed()
print("Ja processados antes:", len(processed))

def search_range(start_iso, end_iso, after=None):
    data = {
        "filterGroups": [{"filters": [
            {"propertyName": "createdate", "operator": "GTE", "value": start_iso},
            {"propertyName": "createdate", "operator": "LT", "value": end_iso}
        ]}],
        "properties": ["firstname", "lastname", "email", "phone", "company", "createdate"],
        "limit": 100
    }
    if after:
        data["after"] = after
    req = urllib.request.Request(f"{BASE_URL}/crm/v3/objects/contacts/search",
        data=json.dumps(data).encode(), headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())

# Marcar 19-20/06 (range 19/06 a 21/06 exclusive)
all_old = []
after = None
for _ in range(5):
    r = search_range("2026-06-19T00:00:00Z", "2026-06-21T00:00:00Z", after)
    results = r.get("results", [])
    all_old.extend(results)
    after = r.get("paging", {}).get("next", {}).get("after")
    if not after:
        break

print(f"Contatos 19-20/06 encontrados: {len(all_old)}")
marked = []
for c in all_old:
    email = (c.get("properties", {}).get("email") or "").lower().strip()
    if email and email not in processed:
        marked.append(email)
        save_processed(email)
print("Marcados como FEITO:", len(marked))
for e in marked:
    print("  +", e)

# Buscar os 2 novos por dominio
print("\n" + "=" * 60)
print("DADOS DOS 2 NOVOS:")
def fetch_domain(dom):
    data = {"filterGroups": [{"filters": [{"propertyName": "email", "operator": "CONTAINS_TOKEN", "value": dom}]}],
            "properties": ["firstname","lastname","email","phone","mobilephone","company","lifecyclestage",
                "de_qual_forma_mais_vende_hoje_em_dia","qual_erp_utiliza_",
                "qual_o_faturamento_anual_da_sua_empresa_","quantas_pessoas_atuam_na_sua_empresa",
                "vende_em_loja_virtual_","qual_a_rea_de_atuao_de_sua_empresa","voc_vende_para_quem"],
            "limit": 10}
    req = urllib.request.Request(f"{BASE_URL}/crm/v3/objects/contacts/search",
        data=json.dumps(data).encode(), headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode()).get("results", [])

novos = []
for dom in ["bodebrown", "avetextil"]:
    for c in fetch_domain(dom):
        p = c.get("properties", {})
        email = (p.get("email") or "").lower()
        # bodebrown: pegar o MQL (email correto); ave textil: unico
        if "avetextil" in email or (email == "alexandre.spier@bodebrown.com.br"):
            d = {k: p.get(k) for k in p if p.get(k) and k not in ["createdate","lastmodifieddate","hs_object_id","hs_all_owner_ids","hubspot_owner_id"]}
            novos.append(d)
            print(json.dumps(d, ensure_ascii=False, indent=2))
            print("-" * 40)

with open("controle/novos_2_leads.json", "w") as f:
    json.dump(novos, f, ensure_ascii=False, indent=2)
print("Total processados agora:", len(load_processed()))
