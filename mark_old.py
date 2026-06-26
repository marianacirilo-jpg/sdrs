#!/usr/bin/env python3
"""Marca leads antigos (19-20/06) como done e busca dados dos 2 novos."""
import sys, json, os
sys.path.insert(0, "motor")
from ciclo import hubspot_search_contacts, load_processed, save_processed

processed = load_processed()
print("Ja processados antes:", len(processed))

search = hubspot_search_contacts(days=4)
contacts = search.get("results", []) if search else []
print("Contatos (4 dias):", len(contacts))

# 1. Marcar 19-20/06 como done
marked = []
for c in contacts:
    p = c.get("properties", {})
    created = p.get("createdate") or ""
    email = (p.get("email") or "").lower().strip()
    if not email:
        continue
    # So 19/06 e 20/06 = antigos
    if created.startswith("2026-06-19") or created.startswith("2026-06-20"):
        if email not in processed:
            marked.append(email)
            save_processed(email)

print("\nMarcados como FEITO (19-20/06):", len(marked))
for e in marked:
    print("  +", e)

# 2. Dados dos 2 novos (BodeBrown + Ave Textil)
print("\n" + "=" * 70)
print("DADOS DOS 2 LEADS NOVOS (22/06):")
print("=" * 70)
novos = []
for c in contacts:
    p = c.get("properties", {})
    email = (p.get("email") or "").lower()
    if "bodebrown" in email or "avetextil" in email:
        d = {}
        for k in ["firstname", "lastname", "email", "phone", "mobilephone", "company",
                  "lifecyclestage", "de_qual_forma_mais_vende_hoje_em_dia",
                  "qual_erp_utiliza_", "qual_o_faturamento_anual_da_sua_empresa_",
                  "quantas_pessoas_atuam_na_sua_empresa", "vende_em_loja_virtual_",
                  "qual_seria_o_maior_problema", "qual_a_rea_de_atuao_de_sua_empresa",
                  "voc_vende_para_quem"]:
            d[k] = p.get(k)
        # so o MQL do bodebrown (email correto) e ave textil
        if d.get("lifecyclestage") or "avetextil" in email:
            novos.append(d)
            print(json.dumps(d, ensure_ascii=False, indent=2))
            print("-" * 40)

with open("controle/novos_2_leads.json", "w") as f:
    json.dump(novos, f, ensure_ascii=False, indent=2)
print("\nSalvo: controle/novos_2_leads.json")
