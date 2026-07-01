#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Recupera reinscrições dos últimos 60 dias com negócio ausente ou todos fechados.
Idempotente: revalida HubSpot antes de criar; se já houver deal aberto, pula.
Cria novo negócio aberto na primeira etapa + task HIGH para o SDR.
"""
import datetime
import importlib.util
import json
import pathlib
import sys
import time
from zoneinfo import ZoneInfo

ROOT = pathlib.Path('/root/.hermes/zydon-prospeccao')
CTL = ROOT / 'controle'
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('d', ROOT / 'disparo_dinamico.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

BRT = ZoneInfo('America/Sao_Paulo')
PIPE = '671008549'
STAGE = '984052829'
OWNER_NAMES = {'85778446': 'Lucas Batista', '86265630': 'Breno', '88063842': 'Sarah', '76764091': 'Lucas Batista'}
ACTIVE_OWNER = {'76764091': '85778446', '85778446': '85778446', '86265630': '86265630', '88063842': '88063842'}
ROUND = ['85778446', '86265630', '88063842']
INTERNAL_DOMAINS = ('zydon.com.br', 'deloitte.com')


def dt(s):
    try:
        return datetime.datetime.fromisoformat((s or '').replace('Z', '+00:00'))
    except Exception:
        return None


def hs(method, path, payload=None):
    url = 'https://api.hubapi.com' + path
    if method == 'GET':
        return d.hs_request(url)
    return d.hs_request(url, method, payload)


def get_contact_props(cid):
    return hs('GET', f'/crm/v3/objects/contacts/{cid}?properties=email,firstname,lastname,company,lifecyclestage,hubspot_owner_id,phone,hs_searchable_calculated_phone_number,qual_erp_utiliza_,selecione_o_sistema_de_gesto_erp,recent_conversion_date,createdate')


def get_deals(cid):
    assoc = hs('GET', f'/crm/v4/objects/contacts/{cid}/associations/deals?limit=100')
    out = []
    for ar in (assoc or {}).get('results') or []:
        did = str(ar.get('toObjectId') or '')
        deal = hs('GET', f'/crm/v3/objects/deals/{did}?properties=dealname,dealstage,pipeline,hs_is_closed,hubspot_owner_id,e_sql,closedate,createdate,hs_lastmodifieddate')
        if deal:
            out.append({'id': did, **((deal.get('properties') or {}))})
        time.sleep(0.025)
    return out


def is_internal_or_test(x):
    email = (x.get('email') or '').lower()
    comp = (x.get('company') or '').lower()
    name = (x.get('name') or '').lower()
    event = (x.get('event') or '').lower()
    blob = ' '.join([email, comp, name, event])
    if any(email.endswith('@' + dom) for dom in INTERNAL_DOMAINS):
        return True, 'domínio interno/excluído'
    if 'zydon' in comp or 'zydon' in email:
        return True, 'Zydon/interno'
    if any(tok in blob for tok in ['base teste', 'form admin', 'leo testes', 'leonardo tester', 'joao@empresa.com.br', 'empresa ltda', 'teste fake']):
        return True, 'base teste/fake'
    return False, ''


def select_owner(x, contact_props, counts):
    raw = str(x.get('owner_id') or contact_props.get('hubspot_owner_id') or '')
    if raw in ACTIVE_OWNER:
        return ACTIVE_OWNER[raw], 'owner existente/legado mapeado'
    owner = min(ROUND, key=lambda oid: (counts.get(oid, 0), oid))
    counts[owner] = counts.get(owner, 0) + 1
    return owner, 'owner ausente: distribuído em rotação SDR para recuperar reinscrição'


def create_deal(cid, company, owner):
    payload = {
        'properties': {
            'dealname': (company or 'Nova oportunidade') + ' - Nova oportunidade',
            'pipeline': PIPE,
            'dealstage': STAGE,
            'hubspot_owner_id': owner,
        },
        'associations': [{'to': {'id': str(cid)}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 3}]}],
    }
    deal = hs('POST', '/crm/v3/objects/deals', payload)
    return str(deal.get('id'))


def create_task(cid, deal_id, owner, x, created=True):
    subj = f"Follow-up nova oportunidade — {x.get('company') or x.get('email')}"
    body = (
        "Reinscrição recuperada por auditoria Hermes dos últimos 60 dias.\n\n"
        f"O contato reconverteu em {x.get('recent_conversion_date')} via: {x.get('event')}.\n"
        f"Problema anterior: {'sem negócio associado' if x.get('no_deals') else 'todos os negócios associados estavam fechados/perdidos'}.\n"
        f"Ação executada: {'novo negócio criado' if created else 'negócio aberto confirmado'}, primeira etapa {STAGE}. Marcado como MQL no contato; não marcar SQL automaticamente.\n\n"
        f"Empresa: {x.get('company')}\n"
        f"Contato: {x.get('name')}\n"
        f"Email: {x.get('email')}\n"
        f"ERP: {x.get('erp') or 'não informado'}\n\n"
        "Próxima ação: SDR validar contexto da reinscrição e seguir follow-up/diagnóstico conforme conversa."
    )
    payload = {
        'properties': {
            'hs_timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z'),
            'hs_task_subject': subj,
            'hs_task_body': body,
            'hs_task_status': 'NOT_STARTED',
            'hs_task_priority': 'HIGH',
            'hubspot_owner_id': owner,
        },
        'associations': [
            {'to': {'id': str(cid)}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 204}]},
            {'to': {'id': str(deal_id)}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 216}]},
        ],
    }
    task = hs('POST', '/crm/v3/objects/tasks', payload)
    return str(task.get('id'))


def sync_local(created_results):
    now = datetime.datetime.now(BRT).isoformat()
    created_map = {r['email']: r for r in created_results if r.get('status') == 'created'}
    for fn in ['wpp_envios.json', 'mql_execution_queue.json', 'mql_pipeline_queue.json', 'agenda_queue.json']:
        p = CTL / fn
        if not p.exists():
            continue
        data = json.loads(p.read_text())
        if isinstance(data, dict) and isinstance(data.get('envios'), list):
            rows = data['envios']; kind = 'envios'
        elif isinstance(data, dict) and isinstance(data.get('items'), list):
            rows = data['items']; kind = 'items'
        elif isinstance(data, list):
            rows = data; kind = None
        else:
            continue
        for it in rows:
            if not isinstance(it, dict):
                continue
            r = created_map.get(str(it.get('email', '')).lower())
            if not r:
                continue
            it['deal_id'] = r['deal_id']
            it['owner_id'] = r['owner_id']
            it['owner_name'] = r['owner_name']
            it['hubspot_deal_synced_at'] = now
            if fn == 'mql_pipeline_queue.json':
                it['state'] = 'reinscricao_recuperada_novo_deal_60d'
                it['mql_confirmed'] = True
                it['diagnostic_allowed'] = True
        if kind:
            data[kind] = rows; out = data
        else:
            out = rows
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    audit_path = CTL / 'audits' / 'reentry_closed_or_missing_deals_20260701.json'
    audit = json.loads(audit_path.read_text())
    candidates = []
    for x in audit.get('issues', []):
        skip, reason = is_internal_or_test(x)
        if skip:
            candidates.append({**x, '_pre_skip': reason})
        else:
            candidates.append(x)
    candidates.sort(key=lambda x: x.get('recent_conversion_date') or '')

    results = []
    counts = {}
    for idx, x in enumerate(candidates, 1):
        email = (x.get('email') or '').lower()
        cid = str(x.get('contact_id') or '')
        if x.get('_pre_skip'):
            results.append({'email': email, 'company': x.get('company'), 'status': 'skipped_internal_or_test', 'reason': x.get('_pre_skip')})
            continue
        try:
            contact = get_contact_props(cid)
            props = (contact or {}).get('properties') or {}
            deals = get_deals(cid)
            open_deals = [z for z in deals if z.get('hs_is_closed') != 'true']
            if open_deals:
                results.append({'email': email, 'company': x.get('company'), 'status': 'skipped_open_deal_exists', 'open_deal_id': open_deals[0]['id'], 'owner_id': open_deals[0].get('hubspot_owner_id')})
                continue
            owner, owner_reason = select_owner(x, props, counts)
            company = props.get('company') or x.get('company') or email
            patch_props = {'hubspot_owner_id': owner}
            if (props.get('lifecyclestage') or '').lower() != 'customer':
                patch_props['lifecyclestage'] = 'marketingqualifiedlead'
            hs('PATCH', f'/crm/v3/objects/contacts/{cid}', {'properties': patch_props})
            deal_id = create_deal(cid, company, owner)
            hs('PATCH', f'/crm/v3/objects/deals/{deal_id}', {'properties': {'pipeline': PIPE, 'dealstage': STAGE, 'hubspot_owner_id': owner}})
            task_id = create_task(cid, deal_id, owner, x, True)
            results.append({'email': email, 'company': company, 'contact_id': cid, 'status': 'created', 'deal_id': deal_id, 'task_id': task_id, 'owner_id': owner, 'owner_name': OWNER_NAMES.get(owner, owner), 'owner_reason': owner_reason, 'problem': 'sem deal' if x.get('no_deals') else 'todos fechados', 'recent_conversion_date': x.get('recent_conversion_date')})
            time.sleep(0.08)
        except Exception as exc:
            results.append({'email': email, 'company': x.get('company'), 'contact_id': cid, 'status': 'error', 'error': str(exc)[:500]})
        if idx % 25 == 0:
            print(f'progress {idx}/{len(candidates)} created={sum(1 for r in results if r.get("status")=="created")} errors={sum(1 for r in results if r.get("status")=="error")}', flush=True)

    sync_local(results)
    out = {
        'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'source_audit': str(audit_path),
        'candidate_count': len(candidates),
        'created_count': sum(1 for r in results if r.get('status') == 'created'),
        'skipped_open_count': sum(1 for r in results if r.get('status') == 'skipped_open_deal_exists'),
        'skipped_internal_or_test_count': sum(1 for r in results if r.get('status') == 'skipped_internal_or_test'),
        'error_count': sum(1 for r in results if r.get('status') == 'error'),
        'results': results,
    }
    path = CTL / 'audits' / 'reentry_fix_batch_60d_20260701.json'
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    log = CTL / 'audits' / 'reentry_fix_log_20260701.jsonl'
    with log.open('a', encoding='utf-8') as f:
        for r in results:
            f.write(json.dumps({'at': datetime.datetime.now(BRT).isoformat(), 'batch': 'last60d', **r}, ensure_ascii=False) + '\n')
    print(json.dumps({k: out[k] for k in ['candidate_count','created_count','skipped_open_count','skipped_internal_or_test_count','error_count']}, ensure_ascii=False, indent=2))
    print(str(path))


if __name__ == '__main__':
    main()
