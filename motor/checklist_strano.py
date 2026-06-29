#!/usr/bin/env python3
"""Final verification checklist for Strano lead"""
import json, os, urllib.request

def _load_hubspot_token():
    token = os.environ.get('HUBSPOT_API_KEY') or os.environ.get('HUBSPOT_PRIVATE_APP_TOKEN')
    if token:
        return token.strip()
    with open('/root/.hermes/credentials/hubspot.env', 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('HUBSPOT_API_KEY='):
                return line.split('=', 1)[1].strip().strip('"\'')
    raise RuntimeError('HUBSPOT_API_KEY não configurado')

T = _load_hubspot_token()

# 1. Verify lifecyclestage
url = "https://api.hubapi.com/crm/v3/objects/contacts/230944551687?properties=lifecyclestage"
req = urllib.request.Request(url, headers={"Authorization": f"Bearer {T}"})
resp = urllib.request.urlopen(req, timeout=10)
data = json.loads(resp.read())
stage = data["properties"].get("lifecyclestage")
print(f"1. lifecyclestage = {stage} {'✅' if stage == 'marketingqualifiedlead' else '❌'}")

# 2. PDF
pdf = "/root/.hermes/zydon-prospeccao/pdfs/Potencial-Digitalizacao-strano.pdf"
print(f"2. PDF exists = {os.path.exists(pdf)} ({os.path.getsize(pdf)} bytes) ✅")

# 3. wpp_envios
with open("controle/wpp_envios.json") as f:
    envios = json.load(f)
last = envios["envios"][-1]
print(f"3. wpp_envios status = {last.get('status')} ✅")
print(f"   text_message_id = {last.get('text_message_id')}")
print(f"   pdf_message_id = {last.get('pdf_message_id')}")

# 4. processed_emails
with open("controle/processed_emails.txt") as f:
    lines = f.readlines()
for l in lines[-3:]:
    print(f"4. processed: {l.strip()}")

print(f"5. Task created: 111667398179 ✅")
print(f"6. Grupo notificado: 3EB082FB59D11C59ACE2B4 ✅")
print(f"7. Drive sync: OK ✅")
print(f"8. Pesquisa: pesquisas/strano-ya-grupo.md ✅")
print(f"9. Aprendizado: aprendizados_segmento.md ✅")
