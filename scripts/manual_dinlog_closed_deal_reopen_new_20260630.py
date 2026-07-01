#!/usr/bin/env python3
"""Rafael 2026-06-30: se contato está opportunity mas todos os deals associados estão fechados,
criar novo negócio aberto na primeira etapa e task para SDR antes de seguir cadência.
Caso aplicado: Dinlog / GrupoDin.
"""
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path('/root/.hermes/zydon-prospeccao')
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('d', ROOT / 'disparo_dinamico.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

EMAIL = 'gru.vcp.santos@grupodin.com.br'
COMPANY = 'Dinlog Armazém e Logística Aduaneira Integrada'
CONTACT_NAME = 'Luiz Guimarães'
OWNER_ID = '85778446'  # Lucas Batista, SDR owner for this opportunity flow
PIPELINE = d.PIPELINE
FIRST_STAGE = d.STAGE_LEAD_SEM_CONTATO  # 984052829 — primeira etapa / Lead Sem Contato
PORTAL_ID = '48590774'


def hs(url, method='GET', body=None):
    return d.hs_request(url, method, body)


def find_contact():
    body = {
        'filterGroups': [{'filters': [{'propertyName': 'email', 'operator': 'EQ', 'value': EMAIL}]}],
        'properties': ['email', 'firstname', 'lastname', 'phone', 'lifecyclestage', 'hubspot_owner_id', 'company'],
        'limit': 10,
    }
    res = hs('https://api.hubapi.com/crm/v3/objects/contacts/search', 'POST', body)
    rows = (res or {}).get('results') or []
    if not rows:
        raise SystemExit(f'Contato não encontrado: {EMAIL}')
    return rows[0]


def associated_deals(contact_id):
    assoc = hs(f'https://api.hubapi.com/crm/v4/objects/contacts/{contact_id}/associations/deals?limit=100')
    out = []
    for r in (assoc or {}).get('results') or []:
        did = str(r.get('toObjectId') or r.get('id') or '')
        if not did:
            continue
        deal = hs(f'https://api.hubapi.com/crm/v3/objects/deals/{did}?properties=dealname,dealstage,pipeline,hs_is_closed,closedate,hubspot_owner_id,createdate')
        if deal:
            out.append(deal)
    return out


def is_open(deal):
    p = (deal.get('properties') or {})
    return str(p.get('hs_is_closed') or '').lower() != 'true' and str(p.get('pipeline') or '') == PIPELINE


def create_deal(contact_id):
    deal_name = f'{COMPANY} - Nova oportunidade'
    body = {
        'properties': {
            'dealname': deal_name,
            'pipeline': PIPELINE,
            'dealstage': FIRST_STAGE,
            'hubspot_owner_id': OWNER_ID,
        },
        'associations': [
            {
                'to': {'id': str(contact_id)},
                'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 3}],
            }
        ],
    }
    res = hs('https://api.hubapi.com/crm/v3/objects/deals', 'POST', body)
    if not (res or {}).get('id'):
        raise RuntimeError(f'Falha criando deal: {res}')
    return res


def create_task(contact_id, deal_id):
    now = datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M BRT')
    body_text = (
        f'Rafael definiu regra operacional: contato como opportunity com negócio fechado deve receber novo negócio aberto na primeira etapa.\n\n'
        f'Contato: {CONTACT_NAME} <{EMAIL}>\n'
        f'Empresa: {COMPANY}\n'
        f'Novo negócio criado em Lead Sem Contato para follow-up SDR.\n'
        f'Ação sugerida: revisar diagnóstico enviado e conduzir follow-up/contexto comercial.\n'
        f'Criado automaticamente em {now}.'
    )
    body = {
        'properties': {
            'hs_timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'hs_task_subject': f'Follow-up nova oportunidade — {COMPANY}',
            'hs_task_body': body_text,
            'hs_task_status': 'NOT_STARTED',
            'hs_task_priority': 'HIGH',
            'hs_task_type': 'TODO',
            'hubspot_owner_id': OWNER_ID,
        },
        'associations': [
            {'to': {'id': str(contact_id)}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 204}]},
            {'to': {'id': str(deal_id)}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 216}]},
        ],
    }
    res = hs('https://api.hubapi.com/crm/v3/objects/tasks', 'POST', body)
    if not (res or {}).get('id'):
        raise RuntimeError(f'Falha criando task: {res}')
    return res


def append_ledger(contact_id, old_deals, new_deal, task):
    path = ROOT / 'controle' / 'wpp_envios.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        data = {'envios': []}
    if isinstance(data, list):
        envios = data
        wrapper = None
    else:
        envios = data.setdefault('envios', [])
        wrapper = data
    now = datetime.now(ZoneInfo('America/Sao_Paulo'))
    row = {
        'date': now.strftime('%Y-%m-%d %H:%M'),
        'date_tz': now.isoformat(),
        'email': EMAIL,
        'contact_id': str(contact_id),
        'empresa': COMPANY,
        'status': 'opportunity_closed_deal_new_deal_created',
        'msg_type': 'hubspot_deal_reopen_new_opportunity',
        'old_deal_ids': [str(x.get('id')) for x in old_deals],
        'new_deal_id': str(new_deal.get('id')),
        'new_deal_stage': FIRST_STAGE,
        'task_id': str(task.get('id')),
        'owner_id': OWNER_ID,
        'note': 'Contato opportunity tinha apenas negócio fechado; criado novo negócio aberto na primeira etapa e task para SDR conforme regra Rafael.',
    }
    envios.append(row)
    path.write_text(json.dumps(wrapper if wrapper is not None else envios, ensure_ascii=False, indent=2), encoding='utf-8')
    return row


def main():
    contact = find_contact()
    cid = str(contact['id'])
    deals = associated_deals(cid)
    open_deals = [x for x in deals if is_open(x)]
    if open_deals:
        # Primeira execução pode ter criado o negócio e falhado só na task.
        open_deal = open_deals[0]
        task = create_task(cid, open_deal['id'])
        ledger = append_ledger(cid, deals, open_deal, task)
        print(json.dumps({
            'status': 'open_deal_already_exists_task_created',
            'contact_id': cid,
            'open_deal': {
                'id': open_deal.get('id'),
                **(open_deal.get('properties') or {})
            },
            'task': {'id': task.get('id'), 'properties': task.get('properties')},
            'ledger': ledger,
            'deal_url': f'https://app.hubspot.com/contacts/{PORTAL_ID}/record/0-3/{open_deal["id"]}',
        }, ensure_ascii=False, indent=2))
        return
    new_deal = create_deal(cid)
    task = create_task(cid, new_deal['id'])
    ledger = append_ledger(cid, deals, new_deal, task)
    verify = hs(f"https://api.hubapi.com/crm/v3/objects/deals/{new_deal['id']}?properties=dealname,dealstage,pipeline,hs_is_closed,hubspot_owner_id,createdate")
    print(json.dumps({
        'status': 'created_new_open_deal_and_task',
        'contact_id': cid,
        'previous_deals': [{
            'id': x.get('id'),
            **(x.get('properties') or {})
        } for x in deals],
        'new_deal': verify,
        'task': {'id': task.get('id'), 'properties': task.get('properties')},
        'ledger': ledger,
        'deal_url': f'https://app.hubspot.com/contacts/{PORTAL_ID}/record/0-3/{new_deal["id"]}',
        'contact_url': f'https://app.hubspot.com/contacts/{PORTAL_ID}/record/0-1/{cid}',
    }, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
