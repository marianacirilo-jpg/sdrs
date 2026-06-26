# -*- coding: utf-8 -*-
"""Create HubSpot tasks/activities for processed leads."""
import json, os, urllib.request, urllib.error

CRED = os.path.expanduser("~/.hermes/credentials/hubspot.env")
key = None
for line in open(CRED):
    line = line.strip()
    if line.startswith("HUBSPOT_API_KEY="):
        key = line.split("=", 1)[1].strip().strip('"').strip("'")
assert key, "no key"

def api(method, path, body=None):
    url = "https://api.hubapi.com" + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return 0, {"error": str(e)}

SUBJ_MQL = "WhatsApp — Diagnóstico 'Potencial de Digitalização B2B' enviado ao lead."

def create_task(contact_id, subject, deal_id=None, deal_assoc_ok=True):
    import time
    assoc = [{"to": {"id": contact_id}, "associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 204}]
    if deal_id and deal_assoc_ok:
        assoc.append({"to": {"id": deal_id}, "associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 216})
    body = {
        "properties": {
            "hs_timestamp": str(int(time.time() * 1000)),
            "hs_task_subject": subject,
            "hs_task_body": subject,
            "hs_task_status": "COMPLETED",
            "hs_task_priority": "MEDIUM",
        },
        "associations": assoc,
    }
    st, d = api("POST", "/crm/v3/objects/tasks", body)
    return st, d

def find_deal(contact_id):
    st, d = api("GET", f"/crm/v4/objects/contacts/{contact_id}/associations/deals")
    print("  deal assoc resp:", st, json.dumps(d)[:300])
    if st == 200 and d.get("results"):
        r = d["results"][0]
        return r.get("id") or r.get("toObjectId") or r.get("_id")
    return None

def set_lifecycle(contact_id, stage="marketingqualifiedlead"):
    st, d = api("PATCH", f"/crm/v3/objects/contacts/{contact_id}",
                {"properties": {"lifecyclestage": stage}})
    return st, d

# ---- LUMAVILLE (MQL) ----
print("=== LUMAVILLE (MQL) ===")
cid = "230163493229"
did = find_deal(cid)
print("deal:", did)
st, d = set_lifecycle(cid)
print("lifecycle set:", st, d.get("status") if st != 204 else "OK(204)")
st, d = create_task(cid, SUBJ_MQL, deal_id=did)
print("task (contact+deal):", st, json.dumps(d)[:300])
if st not in (200, 201) and did:
    # retry without deal assoc (deal PATCH/assoc can 403)
    st, d = create_task(cid, SUBJ_MQL, deal_id=did, deal_assoc_ok=False)
    print("task (contact only, fallback):", st, json.dumps(d)[:300])

# ---- COPPERBRAS (NAO-MQL) ----
print("\n=== COPPERBRAS (NAO-MQL) ===")
cid = "230274731386"
motivo_c = "Lead nao qualificado (nao-MQL): representante comercial de fabricas de material de construcao, sem operacao propria de distribuicao. Fora do ICP atacado/distribuidor/industria."
st, d = create_task(cid, "Lead nao-MQL — fora do ICP (representante comercial)")
print("task:", st, json.dumps(d)[:200])

# ---- PREMIERCOM (NAO-MQL) ----
print("\n=== PREMIERCOM (NAO-MQL) ===")
cid = "230167768698"
st, d = create_task(cid, "Lead nao-MQL — fora do ICP (agencia de servicos/comunicacao)")
print("task:", st, json.dumps(d)[:200])

print("\n=== HUBSPOT ACTIVITIES DONE ===")
