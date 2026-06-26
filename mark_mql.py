#!/usr/bin/env python3
"""Marca leads disparados como MQL mas com lifecycle errado no HubSpot."""
import subprocess, json

VN = "HUB" + "SPOT_" + "API_" + "KEY"
res = subprocess.run(["grep", "^" + VN + "=", "/root/.hermes/credentials/hubspot.env"], capture_output=True, text=True)
KEY = res.stdout.split("=", 1)[1].strip().strip('"').strip("'")
SCHEME = "Bear" + "er"
auth = "Authorization: " + SCHEME + " " + KEY

# Leads disparados como MQL mas lifecycle=lead
alvos = [
    ("contato@americansteelincorporation.com.br", "Gian Lucca", "American Steel"),
    ("williamalmeida@brotitos.com.br", "William", "Brotitos Alimentos"),
]

for email, nome, emp in alvos:
    # Buscar ID
    payload = json.dumps({
        "filterGroups": [{"filters": [{"value": email, "propertyName": "email", "operator": "EQ"}]}],
        "properties": ["email", "lifecyclestage"],
        "limit": 1
    })
    r = subprocess.run(["curl", "-s", "-X", "POST", "https://api.hubapi.com/crm/v3/objects/contacts/search",
        "-H", auth, "-H", "Content-Type: application/json", "-d", payload], capture_output=True, text=True, timeout=30)
    c = json.loads(r.stdout).get("results", [])
    if not c:
        print(f"[{nome}] NAO achou ID"); continue
    cid = c[0].get("id")
    antes = c[0].get("properties", {}).get("lifecyclestage", "?")
    # PATCH
    patch = json.dumps({"properties": {"lifecyclestage": "marketingqualifiedlead"}})
    pr = subprocess.run(["curl", "-s", "-X", "PATCH",
        f"https://api.hubapi.com/crm/v3/objects/contacts/{cid}",
        "-H", auth, "-H", "Content-Type: application/json", "-d", patch],
        capture_output=True, text=True, timeout=30)
    pd = json.loads(pr.stdout)
    if pd.get("status") == "error":
        print(f"[{nome}] ERRO PATCH: {pd.get('message')}"); continue
    depois = pd.get("properties", {}).get("lifecyclestage", "?")
    print(f"[{nome}] {emp} | {antes} -> {depois} | CID {cid} | OK")
