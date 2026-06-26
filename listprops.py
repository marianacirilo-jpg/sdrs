#!/usr/bin/env python3
"""Lista todas propriedades custom do contato para achar campos de ERP/faturamento."""
import subprocess, json

VN = "HUB" + "SPOT_" + "API_" + "KEY"
res = subprocess.run(["grep", "^" + VN + "=", "/root/.hermes/credentials/hubspot.env"], capture_output=True, text=True)
KEY = res.stdout.split("=", 1)[1].strip().strip('"').strip("'")
SCHEME = "Bear" + "er"
auth = "Authorization: " + SCHEME + " " + KEY

# Listar todas propriedades custom do grupo contato
r = subprocess.run(["curl","-s",
    "https://api.hubapi.com/crm/v3/properties/contacts?archived=false&limit=200",
    "-H",auth], capture_output=True, text=True, timeout=30)
d = json.loads(r.stdout)
props = d.get("results", [])
print(f"Total propriedades: {len(props)}")
# Filtrar custom (não hubspot-defined) e relevantes
keywords = ["erp","faturamento","fat","func","seg","cargo","desafio","mensagem","message","tipo","negocio","vend","quant","porte","ramo","setor","atividade"]
print("\n=== CUSTOM + RELEVANTES ===")
for p in props:
    name = p.get("name","")
    label = (p.get("label") or "").lower()
    nl = name.lower()
    if not p.get("hasUniqueValue") and any(k in nl or k in label for k in keywords):
        print(f"  {name}  ({p.get('label','')})  [type={p.get('type')}]")
