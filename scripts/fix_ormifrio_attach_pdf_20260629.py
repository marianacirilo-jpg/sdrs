#!/usr/bin/env python3
import json, os, re, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path('/root/.hermes/zydon-prospeccao')
ENV = Path('/root/.hermes/credentials/hubspot.env')
DEAL_ID = '61732194925'
CONTACT_ID = '231844457883'
TASK_ID_OLD = '111863506820'
FILE_ID = '216019296380'
PDF_PATH = ROOT / 'pdfs/Ormifrio - Potencial de Digitalizacao B2B.pdf'
OWNER_ID = '85778446'


def load_token():
    txt = ENV.read_text(encoding='utf-8')
    m = re.search(r'^(?:HUBSPOT_API_KEY|HUBSPOT_TOKEN)=(.+)$', txt, re.M)
    if not m:
        raise SystemExit('HubSpot token não encontrado')
    return m.group(1).strip().strip('"\'')

TOK = load_token()
BASE = 'https://api.hubapi.com'

def hs(method, path, body=None, timeout=60):
    data = None if body is None else json.dumps(body).encode('utf-8')
    headers = {'Authorization': 'Bearer ' + TOK, 'Content-Type': 'application/json'}
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode('utf-8')
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        raise RuntimeError(f'HubSpot HTTP {e.code} {method} {path}: {raw[:1000]}')


def assoc_ids(from_obj, from_id, to_obj):
    status, data = hs('GET', f'/crm/v4/objects/{from_obj}/{from_id}/associations/{to_obj}?limit=500')
    return [str(r.get('toObjectId')) for r in data.get('results', [])]


def task_props(task_id):
    status, data = hs('GET', f'/crm/v3/objects/tasks/{task_id}?properties=hs_task_subject,hs_attachment_ids,hs_task_body,hs_task_status')
    return data.get('properties') or {}


def create_task_with_pdf():
    props = {
        'hs_timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        'hs_task_subject': "Dexter — PDF do diagnóstico anexado ao negócio",
        'hs_task_body': (
            "Correção operacional: o diagnóstico da Ormifrio havia sido enviado ao WhatsApp e subido ao HubSpot Files, "
            "mas a atividade original não ficou anexada ao negócio porque o registro de envio não carregou o deal_id no ledger naquele momento.\n\n"
            f"PDF anexado: {PDF_PATH.name}\n"
            f"HubSpot file_id: {FILE_ID}\n"
            "WhatsApp original: diagnóstico enviado em 28/06 pelo João Pedro; negócio/agenda depois ficou com Lucas Batista."
        ),
        'hs_task_status': 'COMPLETED',
        'hs_task_priority': 'MEDIUM',
        'hs_task_type': 'TODO',
        'hubspot_owner_id': OWNER_ID,
        'hs_attachment_ids': FILE_ID,
    }
    associations = [
        {'to': {'id': CONTACT_ID}, 'types': [{'associationCategory':'HUBSPOT_DEFINED','associationTypeId':204}]},
        {'to': {'id': DEAL_ID}, 'types': [{'associationCategory':'HUBSPOT_DEFINED','associationTypeId':216}]},
    ]
    status, data = hs('POST', '/crm/v3/objects/tasks', {'properties': props, 'associations': associations})
    return data.get('id'), data


def main():
    if not PDF_PATH.exists():
        raise SystemExit(f'PDF local não encontrado: {PDF_PATH}')
    file_status, file_meta = hs('GET', f'/files/v3/files/{FILE_ID}')
    old_props = task_props(TASK_ID_OLD)
    old_task_deals = assoc_ids('tasks', TASK_ID_OLD, 'deals')
    old_task_contacts = assoc_ids('tasks', TASK_ID_OLD, 'contacts')
    deal_tasks_before = assoc_ids('deals', DEAL_ID, 'tasks')
    created_id = None
    created = None
    if FILE_ID not in str(old_props.get('hs_attachment_ids') or '') or DEAL_ID not in old_task_deals:
        created_id, created = create_task_with_pdf()
    deal_tasks_after = assoc_ids('deals', DEAL_ID, 'tasks')
    result = {
        'pdf_exists': True,
        'pdf_path': str(PDF_PATH),
        'pdf_size': PDF_PATH.stat().st_size,
        'file_id': FILE_ID,
        'file_access': file_meta.get('access'),
        'file_url': file_meta.get('defaultHostingUrl') or file_meta.get('url'),
        'old_task_id': TASK_ID_OLD,
        'old_task_attachment_ids': old_props.get('hs_attachment_ids'),
        'old_task_deals': old_task_deals,
        'old_task_contacts': old_task_contacts,
        'deal_tasks_before_count': len(deal_tasks_before),
        'created_task_id': created_id,
        'deal_tasks_after_has_created': created_id in deal_tasks_after if created_id else None,
        'deal_tasks_after_count': len(deal_tasks_after),
    }
    out = ROOT / 'controle' / 'runtime' / 'fix_ormifrio_attach_pdf_20260629.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
