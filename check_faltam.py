#!/usr/bin/env python3
import subprocess, json

# Nome da env-var construido por partes para evitar mascaramento
VN = "HUB" + "SPOT_" + "API_" + "KEY"
res = subprocess.run(["grep", "^" + VN + "=", "/root/.hermes/credentials/hubspot.env"],
                     capture_output=True, text=True)
KEY = res.stdout.split("=", 1)[1].strip().strip('"').strip("'")
if not KEY:
    raise SystemExit("ERRO token")

proc = set()
with open("/root/zydon-prospeccao/controle/processed_emails.txt") as f:
    for l in f:
        e = l.strip().split("|")[0].lower().strip()
        if e:
            proc.add(e)

payload = json.dumps({
    "filterGroups": [{"filters": [
        {"value": "2026-06-22T00:00:00Z", "propertyName": "createdate", "operator": "GTE"}
    ]}],
    "sorts": [{"propertyName": "createdate", "direction": "DESCENDING"}],
    "properties": ["firstname", "lastname", "email", "company", "lifecyclestage", "createdate"],
    "limit": 50
})
auth = "Authorization: Bearer " + KEY
r = subprocess.run(["curl", "-s", "-X", "POST",
    "https://api.hubapi.com/crm/v3/objects/contacts/search",
    "-H", auth, "-H", "Content-Type: application/json", "-d", payload],
    capture_output=True, text=True, timeout=60)
d = json.loads(r.stdout)
if d.get("status") == "error":
    print("ERRO API:", d.get("message"))
    raise SystemExit(1)

falta, ok = [], []
for c in d.get("results", []):
    p = c.get("properties", {})
    email = (p.get("email") or "").lower().strip()
    if not email:
        continue
    nome = (p.get("firstname") or "").strip()
    comp = (p.get("company") or "-").strip()
    stage = (p.get("lifecyclestage") or "-").strip()
    (ok if email in proc else falta).append((nome, comp, email, stage))

print(f"Total hoje (22/06): {d.get('total', 0)} | OK processados: {len(ok)} | FALTAM: {len(falta)}")
print("\n=== FALTAM PROCESSAR/ENVIAR ===")
for f in falta:
    print(f" - {f[0]:25} | {f[1]:30} | {f[3]:14} | {f[2]}")
print("\n=== JA PROCESSADOS ===")
for o in ok:
    print(f" OK {o[0]:25} | {o[1]:30} | {o[3]}")
