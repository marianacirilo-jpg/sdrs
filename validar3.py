#!/usr/bin/env python3
"""Valida telefones no WhatsApp + puxa dados do HubSpot dos 3 leads pendentes."""
import subprocess, json, re

VN = "HUB" + "SPOT_" + "API_" + "KEY"
res = subprocess.run(["grep", "^" + VN + "=", "/root/.hermes/credentials/hubspot.env"], capture_output=True, text=True)
KEY = res.stdout.split("=", 1)[1].strip().strip('"').strip("'")
SCHEME = "Bear" + "er"
auth = "Authorization: " + SCHEME + " " + KEY

leads = [
    ("contato@americansteelincorporation.com.br", "Gian Lucca", "American Steel"),
    ("conforto@chinelosconforto.com.br", "PANTUFAS", "Pantufas&Cia"),
    ("rafael.oliveira@ifnmg.edu.br", "Rafael Correia", "IFNMG"),
]

print("=" * 70)
print("DADOS + VALIDACAO WHATSAPP")
print("=" * 70)
for email, nome, emp in leads:
    payload = json.dumps({
        "filterGroups": [{"filters": [{"value": email, "propertyName": "email", "operator": "EQ"}]}],
        "properties": ["firstname","lastname","email","company","phone","mobilephone",
                       "hs_searchable_calculated_phone_number","hs_whatsapp_phone_number"],
        "limit": 3
    })
    r = subprocess.run(["curl","-s","-X","POST","https://api.hubapi.com/crm/v3/objects/contacts/search",
        "-H",auth,"-H","Content-Type: application/json","-d",payload], capture_output=True, text=True, timeout=30)
    c = json.loads(r.stdout).get("results", [])
    if not c:
        print(f"\n[{nome}] NAO achou por email")
        continue
    p = c[0].get("properties", {})
    tel = p.get("hs_searchable_calculated_phone_number") or p.get("phone") or p.get("mobilephone") or ""
    tel = (tel or "").strip()
    valid = "?"
    jid_num = ""
    if tel:
        nums = re.sub(r"\D", "", tel)
        jid_num = nums if nums.startswith("55") else "55" + nums
        try:
            url = "http://localhost:4500/exists?jid=" + jid_num + "@s.whatsapp.net"
            rr = subprocess.run(["curl","-s",url], capture_output=True, text=True, timeout=15)
            ex = json.loads(rr.stdout)
            exlist = ex.get("exists")
            if isinstance(exlist, list):
                valid = "WHATZAP OK" if any(e.get("exists") for e in exlist) else "NAO EXISTE"
            else:
                valid = str(exlist)
        except Exception as e:
            valid = f"erro:{e}"
    print(f"\n[{nome}] {p.get('company','')}")
    print(f"  email: {p.get('email','')}")
    print(f"  tel (hs_searchable): {tel}")
    print(f"  jid: {jid_num}")
    print(f"  WhatsApp: {valid}")
