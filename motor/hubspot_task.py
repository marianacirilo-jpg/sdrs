# -*- coding: utf-8 -*-
import os, json, urllib.request, datetime

TOKEN = os.environ.get("HUBSPOT_API_KEY", "")
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
CID = "230388353654"
DID = "61437745942"
now = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

task_body = {
    "properties": {
        "hs_timestamp": now,
        "hs_task_subject": "WhatsApp — Diagnóstico 'Potencial de Digitalização B2B' enviado ao lead.",
        "hs_task_body": "Diagnóstico de Potencial de Digitalização B2B enviado ao lead Moises Gil (Sustenpack) via WhatsApp pela Mariana/Zydon, porta 4600.",
        "hs_task_status": "COMPLETED",
        "hs_task_priority": "HIGH",
        "hs_task_type": "TODO",
    }
}
req = urllib.request.Request("https://api.hubapi.com/crm/v3/objects/tasks",
                             data=json.dumps(task_body).encode(), headers=H, method="POST")
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        t = json.loads(r.read())
    tid = t.get("id")
    print("TASK criada:", tid)
except urllib.error.HTTPError as e:
    print("TASK ERRO:", e.code, e.read().decode()[:500])
    raise SystemExit(1)


def assoc(obj_type, obj_id, atype):
    url = f"https://api.hubapi.com/crm/v4/objects/tasks/{tid}/associations/{obj_type}/{obj_id}"
    body = json.dumps([{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": atype}]).encode()
    r2 = urllib.request.Request(url, data=body, headers=H, method="PUT")
    try:
        with urllib.request.urlopen(r2, timeout=30) as resp:
            print(f"ASSOC task->{obj_type}({atype}):", resp.status)
    except urllib.error.HTTPError as e:
        print(f"ASSOC task->{obj_type}({atype}) ERRO:", e.code, e.read().decode()[:300])


assoc("contacts", CID, 204)
assoc("deals", DID, 216)
