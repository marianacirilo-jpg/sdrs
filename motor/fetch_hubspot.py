#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import urllib.request, urllib.error, json, os, sys, time

HUBSPOT_API_KEY = os.environ.get("HUBSPOT_API_KEY") or os.environ.get("HUBSPOT_ACCESS_TOKEN")
if not HUBSPOT_API_KEY:
    raise SystemExit("Set HUBSPOT_API_KEY or HUBSPOT_ACCESS_TOKEN in the environment")
HUBSPOT_REGION="na1"
BASE_URL="https://api.hubapi.com"

# Lista de domínios/sufixos de email para buscar telefones dos pendentes
email_domains = [
    "glassway.com",
    "marcksuprimentos.com",
    "sharpmetal.com",
    "resoma.com",
    "onixxbrasil.com",
    "escardcartoes.com",
]

properties = "email,phone,firstname,lastname,company,lifecyclestage"

headers = {
    "Authorization": f"Bearer {HUBSPOT_API_KEY}",
    "Content-Type": "application/json"
}

all_contacts = {}

for domain in email_domains:
    payload = json.dumps({
        "filterGroups": [{"filters": [{"propertyName": "email", "operator": "CONTAINS", "value": domain}]}],
        "properties": ["email","phone","firstname","lastname","company","lifecyclestage"],
        "limit": 50
    }).encode()

    req = urllib.request.Request(
        f"{BASE_URL}/crm/v3/objects/contacts/search",
        data=payload,
        headers=headers,
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
            results = data.get("results", [])
            for contact in results:
                email = contact["properties"].get("email","")
                phone = contact["properties"].get("phone","")
                if email:
                    all_contacts[email.lower()] = {
                        "phone": phone,
                        "name": f"{contact['properties'].get('firstname','')} {contact['properties'].get('lastname','')}",
                        "company": contact["properties"].get("company","")
                    }
    except Exception as e:
        print(f"Error fetching {domain}: {e}")
    time.sleep(0.3)

print(json.dumps(all_contacts, indent=2, ensure_ascii=False))
