#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Envia texto + PDF + thumbnail de um lead para um JID via WhatsApp bridge.
Uso: python3 send_lead.py <slug> <jid> [--note "..."]
Le: pesquisas/<slug>_msg.txt e pdfs/Potencial-Digitalizacao-<slug>.pdf
Gera thumbnail 600x338 JPEG q90 em /tmp.
"""
import os, sys, json, re, subprocess, urllib.request, urllib.error
sys.path.insert(0, '/root/.hermes/zydon-prospeccao/scripts')
from whatsapp_safe_send import safe_post_bridge

PROJ = "/root/zydon-prospeccao"
BRIDGE = "http://127.0.0.1:4600"
HUBSPOT_API = "https://api.hubapi.com"
HUBSPOT_ENV = "/root/.hermes/credentials/hubspot.env"


def hubspot_token():
    """Le HUBSPOT_API_KEY de /root/.hermes/credentials/hubspot.env (fallback: ambiente)."""
    try:
        with open(HUBSPOT_ENV, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("HUBSPOT_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception as e:
        print("  [mql] erro lendo token: " + str(e))
    return os.environ.get("HUBSPOT_API_KEY", "")


def hubspot_req(method, path, token, payload=None):
    """Request a HubSpot via urllib. Retorna (status, dict)."""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(HUBSPOT_API + path, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode()
        return r.status, (json.loads(body) if body else {})


def hubspot_find_contact_by_phone(jid, token):
    """Acha contato no HubSpot pelo telefone do jid. Retorna (contact_id, lifecycle_atual)."""
    digits = re.sub(r"[^0-9]", "", jid or "")
    if not digits or not token:
        return None, None
    # Tenta o numero completo e, se vier com DDI 55, tambem sem o 55 (token mais curto).
    variantes = [digits]
    if digits.startswith("55") and len(digits) >= 12:
        variantes.append(digits[2:])
    for v in variantes:
        payload = {
            "filterGroups": [{"filters": [{
                "propertyName": "hs_searchable_calculated_phone_number",
                "operator": "CONTAINS_TOKEN", "value": v,
            }]}],
            "properties": ["email", "lifecyclestage"],
            "limit": 1,
        }
        try:
            st, d = hubspot_req("POST", "/crm/v3/objects/contacts/search", token, payload)
            results = d.get("results", []) if isinstance(d, dict) else []
            if results:
                props = results[0].get("properties", {}) or {}
                return results[0].get("id"), props.get("lifecyclestage")
        except Exception as e:
            print("  [mql] erro buscando contato (" + v + "): " + str(e))
    return None, None


def marcar_mql_hubspot(contact_id, lifecycle_atual=None):
    """PATCH lifecyclestage=marketingqualifiedlead no contato, se ainda nao for MQL.
    Retorna True se marcou; False se ja era MQL, sem id/token ou em erro.
    Best-effort: nunca derruba o fluxo de disparo."""
    if not contact_id:
        print("  [mql] sem contact_id; nao marcou")
        return False
    if (lifecycle_atual or "").strip().lower() == "marketingqualifiedlead":
        print("  [mql] ja era MQL; nada a fazer")
        return False
    token = hubspot_token()
    if not token:
        print("  [mql] sem token HubSpot; nao marcou")
        return False
    try:
        st, d = hubspot_req(
            "PATCH", "/crm/v3/objects/contacts/" + str(contact_id), token,
            {"properties": {"lifecyclestage": "marketingqualifiedlead"}},
        )
        if isinstance(d, dict) and d.get("status") == "error":
            print("  [mql] ERRO PATCH: " + str(d.get("message")))
            return False
        depois = (d.get("properties", {}) or {}).get("lifecyclestage") if isinstance(d, dict) else None
        print("  [mql] lifecycle " + str(lifecycle_atual) + " -> "
              + str(depois or "marketingqualifiedlead") + " (CID " + str(contact_id) + ")")
        return True
    except Exception as e:
        print("  [mql] ERRO PATCH: " + str(e))
        return False

def gen_thumbnail(pdf_path, slug):
    thumb = "/tmp/thumb_" + slug + ".jpg"
    # pdftoppm pagina 1 em PNG alta resolucao
    prefix = "/tmp/pg_" + slug
    subprocess.run(["pdftoppm", "-png", "-f", "1", "-l", "1", "-r", "200", pdf_path, prefix],
                   check=True, capture_output=True)
    src_png = prefix + "-1.png" if os.path.exists(prefix + "-1.png") else prefix + "-01.png"
    # redimensiona/cropa para 600x338 JPEG q90 via ImageMagick
    subprocess.run(["convert", src_png, "-resize", "600x338^",
                    "-gravity", "center", "-extent", "600x338",
                    "-quality", "90", "-strip", thumb],
                   check=True, capture_output=True)
    os.remove(src_png)
    return thumb

def post(path, payload):
    port = int(BRIDGE.rsplit(':', 1)[-1])
    return json.dumps(safe_post_bridge(port, path, payload, uid='send_lead', timeout=60), ensure_ascii=False)

def main():
    slug = sys.argv[1]
    jid = sys.argv[2]
    msg_path = PROJ + "/pesquisas/" + slug + "_msg.txt"
    pdf_path = PROJ + "/pdfs/Potencial-Digitalizacao-" + slug + ".pdf"
    if not os.path.exists(msg_path):
        print("ERRO: msg nao encontrada " + msg_path); sys.exit(1)
    if not os.path.exists(pdf_path):
        print("ERRO: pdf nao encontrado " + pdf_path); sys.exit(1)
    with open(msg_path, encoding="utf-8") as f:
        text = f.read().strip()
    print("Gerando thumbnail...")
    thumb = gen_thumbnail(pdf_path, slug)
    print("  -> " + thumb + " (" + str(os.path.getsize(thumb)) + " bytes)")
    fname = slug.replace("-", " ").title()
    # remapear nomes bonitos
    pretty = {
        "sharp": "Sharp", "paregesso": "Paregesso", "mercato": "Mercato",
        "legadu-social": "Legadu Social", "onixxbrasil": "Onixxbrasil",
        "neogrid": "Neogrid", "zimermann": "Zimermann",
        "plasticos-piracicaba": "Plasticos Piracicaba",
        "rct-soldas": "RCT Soldas", "dona-parede": "Dona Parede",
        "grupo-american-pool": "Grupo American Pool",
        "arumia-house": "Arumia House", "gift-do-brasil": "Gift do Brasil",
        "dussara": "Dussara", "luma-ville": "Luma Ville",
        "ilson-lorini": "Premier Comunicacao",
    }
    fname = pretty.get(slug, fname)
    pdf_pretty = PROJ + "/pdfs/" + fname + " - Potencial de Digitalizacao B2B.pdf"
    # copia com nome bonito
    import shutil
    shutil.copy(pdf_path, pdf_pretty)

    print("Enviando TEXTO para " + jid + " ...")
    r1 = post("/send", {"to": jid, "text": text})
    print("  text -> " + r1[:200])
    print("Enviando PDF (" + fname + ".pdf) com thumbnail...")
    r2 = post("/send-file", {"to": jid, "filePath": pdf_pretty,
                              "fileName": fname + " - Potencial de Digitalizacao B2B.pdf",
                              "thumbnailPath": thumb})
    print("  file -> " + r2[:200])

    # Disparo ao lead concluido. Como o disparo ao lead so ocorre para MQL
    # (nao-MQL fica so no grupo de qualificacao), marcamos o lifecyclestage
    # como MQL no HubSpot agora -- corrige o bug em que o lead ficava como
    # "lead" mesmo apos o disparo (ex.: Gian Lucca / William).
    print("Atualizando lifecyclestage no HubSpot...")
    token = hubspot_token()
    cid, lifecycle = hubspot_find_contact_by_phone(jid, token)
    marcar_mql_hubspot(cid, lifecycle)

    print("OK " + slug)

if __name__ == "__main__":
    main()
