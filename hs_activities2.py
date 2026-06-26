#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cria notas no HubSpot no CONTATO e depois associa ao NEGÓCIO."""
import json, os, time, urllib.request, urllib.error

SCHEME = "Bearer"
KEY = os.environ["HUBSPOT_API_KEY"]
TS = str(int(time.time() * 1000))

def hs(method, path, body=None):
    url = f"https://api.hubapi.com{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method,
        headers={"Authorization": f"{SCHEME} {KEY}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, (json.loads(raw) if raw.strip() else {})

SUBJECT = "WhatsApp — Diagnóstico 'Potencial de Digitalização B2B' enviado ao lead."

leads = [
    ("Madeira ABC", 230190210058, 61427666724,
     f"{SUBJECT}\n\nLead MQL: distribuidora de madeiras (atacado B2B), ERP Bling (nativo). Mensagem + PDF enviados via WhatsApp e espelhados no grupo de qualificação."),
]

for nome, cid, did, body in leads:
    # 1. create note on contact (typeId 202)
    code, resp = hs("POST", "/crm/v3/objects/notes", {
        "properties": {"hs_note_body": body, "hs_timestamp": TS},
        "associations": [{"to": {"id": cid},
            "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]}]
    })
    nid = resp.get("id") if isinstance(resp, dict) else "?"
    print(f"{nome}: note HTTP {code} noteId={nid}")
    # 2. associate note -> deal
    if nid and nid != "?":
        c2, r2 = hs("PUT", f"/crm/v3/objects/notes/{nid}/associations/deal/{did}",
                    {"types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 4}]})
        print(f"  deal assoc HTTP {c2}")
