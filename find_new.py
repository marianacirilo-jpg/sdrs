#!/usr/bin/env python3
"""Busca leads novos no HubSpot após o último processado."""
import subprocess, json, datetime, os

KEY_VAR = "HUBSPOT_API_KEY"

key = None
with open("/root/.hermes/credentials/hubspot.env") as f:
    for line in f:
        line = line.strip()
        if line.startswith(KEY_VAR + "="):
            key = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
if not key:
    print("ERRO: token nao encontrado")
    raise SystemExit(1)
print("Token len:", len(key), "| prefix:", key[:6])

processed = set()
pe = "controle/processed_emails.txt"
if os.path.exists(pe):
    with open(pe) as f:
        for line in f:
            email = line.strip().split("|")[0].lower()
            if email:
                processed.add(email)
print(f"Ja processados: {len(processed)} emails")

threshold = int(datetime.datetime(2026, 6, 11, tzinfo=datetime.timezone.utc).timestamp() * 1000)
payload = json.dumps({
    "filterGroups": [{"filters": [
        {"value": str(threshold), "propertyName": "createdAt", "operator": "GT"}
    ]}],
    "sorts": [{"propertyName": "createdAt", "direction": "DESCENDING"}],
    "properties": ["firstname", "lastname", "email", "phone", "mobilephone",
                   "company", "lifecyclestage", "createdAt"],
    "limit": 50
})
r = subprocess.run(["curl", "-s", "-X", "POST",
    "https://api.hubapi.com/crm/v3/objects/contacts/search",
    "-H", "Authorization: Bearer " + key,
    "-H", "Content-Type: application/json",
    "-d", payload], capture_output=True, text=True)
d = json.loads(r.stdout)
if d.get("status") == "error":
    print("ERRO API:", d.get("message"))
    raise SystemExit(1)

print(f"\nTotal contatos novos (apos 11/06): {d.get('total')}")
print("=" * 100)
novos_nao_processados = []
for c in d.get("results", []):
    p = c.get("properties", {})
    created = (p.get("createdAt") or "")[:16]
    fn = (p.get("firstname") or "").strip()
    ln = (p.get("lastname") or "").strip()
    email = (p.get("email") or "").lower().strip()
    phone = p.get("phone") or p.get("mobilephone") or ""
    comp = (p.get("company") or "-").strip()
    stage = p.get("lifecyclestage") or "-"
    done = "OK_JA" if email in processed else "NOVO"
    print(f"{created} | {fn} {ln:20} | {comp:25} | {email:40} | {phone:15} | {done}")
    if email and email not in processed:
        novos_nao_processados.append({
            "nome": (fn + " " + ln).strip(),
            "empresa": comp, "email": email, "telefone": phone,
            "created": created, "stage": stage
        })

print("\n" + "=" * 100)
print(f"Leads NOVOS nao processados: {len(novos_nao_processados)}")
with open("controle/novos_leads.json", "w") as f:
    json.dump(novos_nao_processados, f, ensure_ascii=False, indent=2)
print("Salvo em controle/novos_leads.json")
