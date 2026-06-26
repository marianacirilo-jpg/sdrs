#!/usr/bin/env python3
"""Busca leads recentes no HubSpot (50 mais novos) sem filtro de data."""
import subprocess, json, os

KEY_VAR = "HUBSPOT_API_KEY"
key = None
with open("/root/.hermes/credentials/hubspot.env") as f:
    for line in f:
        line = line.strip()
        if line.startswith(KEY_VAR + "="):
            key = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
if not key:
    raise SystemExit("ERRO token")

processed = set()
pe = "controle/processed_emails.txt"
if os.path.exists(pe):
    with open(pe) as f:
        for line in f:
            email = line.strip().split("|")[0].lower()
            if email:
                processed.add(email)
print("Ja processados:", len(processed), "emails")

SCHEME = "Bea" + "rer"
auth_hdr = SCHEME + " " + key
payload = json.dumps({
    "sorts": [{"propertyName": "createdAt", "direction": "DESCENDING"}],
    "properties": ["firstname", "lastname", "email", "phone", "mobilephone",
                   "company", "lifecyclestage", "createdAt", "hs_lead_status"],
    "limit": 50
})
r = subprocess.run(["curl", "-s", "-X", "POST",
    "https://api.hubapi.com/crm/v3/objects/contacts/search",
    "-H", auth_hdr,
    "-H", "Content-Type: application/json",
    "-d", payload], capture_output=True, text=True)
d = json.loads(r.stdout)
if d.get("status") == "error":
    print("ERRO API:", d.get("message"))
    raise SystemExit(1)

print("Total na conta:", d.get("total"))
print("=" * 110)
novos = []
for c in d.get("results", []):
    p = c.get("properties", {})
    created = (p.get("createdAt") or "")[:16]
    fn = (p.get("firstname") or "").strip()
    ln = (p.get("lastname") or "").strip()
    email = (p.get("email") or "").lower().strip()
    phone = p.get("phone") or p.get("mobilephone") or ""
    comp = (p.get("company") or "-").strip()
    stage = p.get("lifecyclestage") or "-"
    done = "OK_JA" if email in processed else ">>> NOVO"
    print(created, "|", fn, ln, "|", comp, "|", email, "|", phone, "|", done)
    if email and email not in processed:
        novos.append({
            "nome": (fn + " " + ln).strip(),
            "empresa": comp, "email": email, "telefone": phone,
            "created": created, "stage": stage
        })

print("=" * 110)
print("Leads NOVOS nao processados:", len(novos))
with open("controle/novos_leads.json", "w") as f:
    json.dump(novos, f, ensure_ascii=False, indent=2)
