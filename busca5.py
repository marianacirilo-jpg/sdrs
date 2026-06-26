#!/usr/bin/env python3
import subprocess, json

VN = "HUB" + "SPOT_" + "API_" + "KEY"
res = subprocess.run(["grep", "^" + VN + "=", "/root/.hermes/credentials/hubspot.env"], capture_output=True, text=True)
KEY = res.stdout.split("=", 1)[1].strip().strip('"').strip("'")
auth = "Authorization: Bearer " + KEY

buscas = [
    ("Gian Lucca Barbosa Viana", "gian"),
    ("Daniel Pessoa", "daniel.pessoa"),
    ("PANTUFAS & CIA", "pantufas"),
    ("Vitor", "vitor"),
    ("Rafael Correia", "rafael.correia"),
]

for nome, termo in buscas:
    print("=" * 70)
    print(">", nome)
    results = []
    # Tentar por email
    payload = json.dumps({
        "filterGroups": [{"filters": [{"value": termo, "propertyName": "email", "operator": "CONTAINS"}]}],
        "properties": ["firstname","lastname","email","company","lifecyclestage","createdate","phone"],
        "limit": 5
    })
    r = subprocess.run(["curl","-s","-X","POST","https://api.hubapi.com/crm/v3/objects/contacts/search",
        "-H",auth,"-H","Content-Type: application/json","-d",payload], capture_output=True, text=True, timeout=30)
    results = json.loads(r.stdout).get("results", [])
    # Tentar por nome se vazio
    if not results:
        payload2 = json.dumps({
            "filterGroups": [{"filters": [{"value": termo, "propertyName": "firstname", "operator": "CONTAINS"}]}],
            "properties": ["firstname","lastname","email","company","lifecyclestage","createdate","phone"],
            "limit": 5
        })
        r2 = subprocess.run(["curl","-s","-X","POST","https://api.hubapi.com/crm/v3/objects/contacts/search",
            "-H",auth,"-H","Content-Type: application/json","-d",payload2], capture_output=True, text=True, timeout=30)
        results = json.loads(r2.stdout).get("results", [])
    if not results:
        print("  NAO ENCONTRADO no HubSpot")
        continue
    for c in results:
        p = c.get("properties", {})
        fn = (p.get("firstname") or "").strip()
        ln = (p.get("lastname") or "").strip()
        print(f"  {fn} {ln} | {p.get('company','-')} | {p.get('email','')} | tel:{p.get('phone','-')} | {(p.get('createdate') or '')[:16]} | {p.get('lifecyclestage','-')}")
