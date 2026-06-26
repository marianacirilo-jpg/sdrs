#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create HubSpot task with PDF attachment for Strano lead"""
import json, os, urllib.request, urllib.error
from datetime import datetime, timezone

# Load credentials
env = {}
with open(os.path.expanduser("~/.hermes/credentials/hubspot.env")) as f:
    for line in f:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            env[key.strip()] = val.strip().strip('"')

TOKEN = env.get("HUBSPOT_API_KEY")
CONTACT_ID = "230944551687"
DEAL_ID = "61572899919"
FILE_PATH = "/root/.hermes/zydon-prospeccao/pdfs/Potencial-Digitalizacao-strano.pdf"

# Step 1: Upload PDF to HubSpot Files
file_id = None
try:
    boundary = "----ZydonBoundary7MA4YWxk"
    with open(FILE_PATH, "rb") as f:
        file_data = f.read()

    body = b""
    body += f"--{boundary}\r\n".encode()
    body += b'Content-Disposition: form-data; name="file"; filename="Potencial-Digitalizacao-strano.pdf"\r\n'
    body += b'Content-Type: application/pdf\r\n\r\n'
    body += file_data
    body += f"\r\n--{boundary}\r\n".encode()
    body += b'Content-Disposition: form-data; name="options"\r\n'
    body += b'Content-Type: application/json\r\n\r\n'
    body += json.dumps({"access": "PUBLIC_NOT_INDEXABLE", "overwrite": False}).encode()
    body += f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        "https://api.hubapi.com/files/v3/files",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=30)
    result = json.loads(resp.read())
    file_id = result.get("id")
    print(f"File uploaded: id={file_id}, access={result.get('access')}")
except Exception as e:
    print(f"File upload failed (scope?): {e}")

# Step 2: Create task
task_body = (
    "Diagnóstico enviado ao lead Yhuri (Strano) via WhatsApp pela Mariana. "
    "Lead qualificado como MQL: distribuidora de EPI com e-commerce próprio, "
    "ERP Olist (Tiny) nativo, faturamento R$1-5M. "
    "Responsável: Sarah. PDF gerado e enviado."
)
if not file_id:
    task_body += " | PDF não anexado por falta de scope Files no PAT."

task_data = {
    "properties": {
        "hs_task_subject": "WhatsApp — Diagnóstico 'Potencial de Digitalização B2B' enviado ao lead.",
        "hs_task_body": task_body,
        "hs_task_status": "COMPLETED",
        "hs_task_priority": "MEDIUM",
        "hs_task_type": "TODO",
        "hs_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    },
    "associations": [
        {
            "to": {"id": CONTACT_ID},
            "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 204}],
        },
        {
            "to": {"id": DEAL_ID},
            "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 216}],
        },
    ],
}

if file_id:
    task_data["properties"]["hs_attachment_ids"] = str(file_id)
    print(f"Attaching file_id: {file_id}")

req = urllib.request.Request(
    "https://api.hubapi.com/crm/v3/objects/tasks",
    data=json.dumps(task_data).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    },
    method="POST",
)
try:
    resp = urllib.request.urlopen(req, timeout=20)
    result = json.loads(resp.read())
    print(f"Task created: id={result.get('id')}")
    print(f"Task subject: {result['properties'].get('hs_task_subject')}")
except urllib.error.HTTPError as e:
    err_body = e.read().decode()
    print(f"Task creation failed: {e.code} {err_body}")
