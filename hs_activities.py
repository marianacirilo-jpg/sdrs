#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cria notas/atividades no HubSpot associadas a contato e negócio."""
import json, os, time, urllib.request, urllib.error

os.system("set -a; . /root/.hermes/credentials/hubspot.env; set +a")
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
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def create_note(body_text, contact_id, deal_id=None):
    assoc = [{"to": {"id": contact_id}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]}]
    if deal_id:
        assoc.append({"to": {"id": deal_id}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 304}]})
    code, resp = hs("POST", "/crm/v3/objects/notes", {
        "properties": {"hs_note_body": body_text, "hs_timestamp": TS},
        "associations": assoc
    })
    return code, resp

SUBJECT = "WhatsApp — Diagnóstico 'Potencial de Digitalização B2B' enviado ao lead."

leads = [
    ("PONTES MULTI", 230211201144, 61428489365,
     f"{SUBJECT}\n\nLead classificado MQL: indústria/distribuição de alimentos (palmito de pupunha), ERP Omie (nativo). Mensagem + PDF enviados via WhatsApp e espelhados no grupo de qualificação."),
    ("Madeira ABC", 230190210058, 61427666724,
     f"{SUBJECT}\n\nLead MQL: distribuidora de madeiras (atacado B2B), ERP Bling (nativo). Mensagem + PDF enviados via WhatsApp e espelhados no grupo de qualificação."),
    ("I B Silva", 230219422874, 61428212015,
     "Lead fora do ICP — guia/diretório digital de fornecedores da construção (mídia/publicidade), não distribuidora/indústria. ERP 'Outro', faturamento até R$250mil. Sem documento gerado. Motivo registrado no grupo de qualificação."),
]

for nome, cid, did, body in leads:
    deal = did if nome != "I B Silva" else None
    code, resp = create_note(body, cid, deal)
    nid = resp.get("id") if isinstance(resp, dict) else "?"
    print(f"{nome}: HTTP {code} noteId={nid}")
