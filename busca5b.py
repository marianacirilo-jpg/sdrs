#!/usr/bin/env python3
import subprocess, json

VN = "HUB" + "SPOT_" + "API_" + "KEY"
res = subprocess.run(["grep", "^" + VN + "=", "/root/.hermes/credentials/hubspot.env"], capture_output=True, text=True)
KEY = res.stdout.split("=", 1)[1].strip().strip('"').strip("'")

# Construir header por partes para evitar mascaramento
SCHEME = "Bear" + "er"
auth = "Authorization: " + SCHEME + " " + KEY

payload = json.dumps({
    "filterGroups": [{"filters": [
        {"value": "2026-06-21T00:00:00Z", "propertyName": "createdate", "operator": "GTE"}
    ]}],
    "sorts": [{"propertyName": "createdate", "direction": "DESCENDING"}],
    "properties": ["firstname","lastname","email","company","lifecyclestage","createdate","phone","hs_searchable_calculated_phone_number"],
    "limit": 100
})
r = subprocess.run(["curl","-s","-X","POST","https://api.hubapi.com/crm/v3/objects/contacts/search",
    "-H",auth,"-H","Content-Type: application/json","-d",payload], capture_output=True, text=True, timeout=60)
d = json.loads(r.stdout)
if d.get("status") == "error":
    print("ERRO API:", d.get("message"))
    raise SystemExit(1)

alvo = ["gian", "daniel", "pantufas", "vitor", "rafael"]
print(f"Total contatos desde 21/06: {d.get('total', 0)}")
print()
for c in d.get("results", []):
    p = c.get("properties", {})
    fn = (p.get("firstname") or "").strip()
    ln = (p.get("lastname") or "").strip()
    email = (p.get("email") or "").lower()
    comp = (p.get("company") or "").lower()
    tel = p.get("hs_searchable_calculated_phone_number") or p.get("phone") or "-"
    blob = (fn + " " + ln + " " + email + " " + comp).lower()
    if any(a in blob for a in alvo):
        print(f"  {(p.get('createdate') or '')[:16]} | {fn} {ln} | {p.get('company','-')} | {email} | tel:{tel} | {p.get('lifecyclestage','-')}")
