#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audita reconversões reais dos últimos 60 dias que perderam diagnóstico.
Fonte primária: HubSpot contacts search por recent_conversion_date.
Critério de reconversão real: contact.createdate existe e recent_conversion_date > createdate + 5min.
Classifica evento: formulário/anúncio/reunião/outro.
Cruza deals abertos/fechados e wpp_envios para detectar diagnóstico/PDF já enviado.
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
OUT = CTL / 'audits' / 'hubspot_reconversions_lost_diagnostics_60d_20260701.json'
CONTACT_PROPS = [
    'email','firstname','lastname','company','createdate','recent_conversion_date','recent_conversion_event_name',
    'num_conversion_events','num_unique_conversion_events','lifecyclestage','hubspot_owner_id','phone','mobilephone',
    'hs_whatsapp_phone_number','hs_searchable_calculated_phone_number','qual_erp_utiliza_','selecione_o_sistema_de_gesto_erp',
    'hs_analytics_source','hs_latest_source','hs_object_source','hs_object_source_label'
]
INTERNAL_TEST_TERMS = ['zydon.com.br','deloitte.com','leo testes','leonardo tester','joao@empresa.com.br','empresa ltda','base teste','form admin']
FORM_TERMS = ['form', 'facebook lead ads', 'lead ads', 'demonstra', 'diagnóstico', 'diagnostico', 'vencedor', 'anúncio', 'anuncio', 'landing']
MEETING_TERMS = ['meetings link', 'meeting']


def parse_dt(s):
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except Exception:
        return None


def hs(method, path, payload=None, attempts=5):
    last = None
    for i in range(attempts):
        try:
            url = 'https://api.hubapi.com' + path
            return d.hs_request(url) if method == 'GET' else d.hs_request(url, method, payload)
        except Exception as e:
            last = e
            time.sleep(1.4 * (i + 1))
    raise last


def search_contacts(cutoff_iso):
    after = None
    out = []
    while True:
        body = {
            'filterGroups': [
                {'filters': [{'propertyName': 'recent_conversion_date', 'operator': 'GTE', 'value': cutoff_iso}]}
            ],
            'properties': CONTACT_PROPS,
            'sorts': [{'propertyName': 'recent_conversion_date', 'direction': 'DESCENDING'}],
            'limit': 100,
        }
        if after:
            body['after'] = after
        data = hs('POST', '/crm/v3/objects/contacts/search', body)
        rows = data.get('results') or []
        out.extend(rows)
        after = ((data.get('paging') or {}).get('next') or {}).get('after')
        if not after or not rows:
            break
        time.sleep(0.15)
    return out


def get_deals(cid):
    assoc = hs('GET', f'/crm/v4/objects/contacts/{cid}/associations/deals?limit=100')
    deals = []
    for ar in (assoc or {}).get('results') or []:
        did = str(ar.get('toObjectId') or '')
        if not did:
            continue
        deal = hs('GET', f'/crm/v3/objects/deals/{did}?properties=dealname,dealstage,pipeline,hs_is_closed,hubspot_owner_id,e_sql,createdate,closedate,hs_lastmodifieddate')
        deals.append({'id': did, **((deal or {}).get('properties') or {})})
        time.sleep(0.03)
    return deals


def load_wpp():
    p = CTL / 'wpp_envios.json'
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding='utf-8'))
    return data.get('envios', []) if isinstance(data, dict) else data


def has_diag(wpp, email, cid, deal_ids, phone):
    terms = [str(email or '').lower(), str(cid or '').lower()] + [str(x).lower() for x in deal_ids if x] + [str(phone or '').lower()]
    diag = []
    any_operational = []
    for r in wpp:
        if not isinstance(r, dict):
            continue
        s = json.dumps(r, ensure_ascii=False).lower()
        if not any(t and t in s for t in terms):
            continue
        status = str(r.get('status') or r.get('legacy_status') or '').lower()
        camp = str(r.get('campaign_id') or '').lower()
        msg = str(r.get('msg_type') or r.get('legacy_msg_type') or '').lower()
        row = {k: r.get(k) for k in ['date_tz','status','campaign_id','msg_type','bridge_port','hubspot_file_id','task_id','deal_id','contact_id'] if k in r}
        any_operational.append(row)
        # Diagnóstico real: PDF/file id/pdf_path ou campanha MQL de diagnóstico; excluir confirmação de agenda/reunião.
        if ('agenda_confirmacao' in msg) or ('diagnostico_agendado' in camp):
            continue
        if r.get('hubspot_file_id') or r.get('pdf_path') or 'diagnostico_mql' in camp or 'mql_diagnostico' in status or status == 'enviado_lead':
            diag.append(row)
    return bool(diag), diag, any_operational[-5:]


def event_type(event):
    e = (event or '').lower()
    if any(t in e for t in FORM_TERMS):
        return 'form_or_ad'
    if any(t in e for t in MEETING_TERMS):
        return 'meeting_link'
    return 'other_conversion'


def is_test(props):
    blob = ' '.join(str(props.get(k) or '') for k in ['email','company','firstname','lastname','recent_conversion_event_name']).lower()
    return any(t in blob for t in INTERNAL_TEST_TERMS)


def main():
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=60)
    rows = search_contacts(cutoff.isoformat().replace('+00:00', 'Z'))
    wpp = load_wpp()
    audited = []
    counts = {}
    for c in rows:
        cid = str(c.get('id'))
        p = c.get('properties') or {}
        created = parse_dt(p.get('createdate'))
        recent = parse_dt(p.get('recent_conversion_date'))
        if not recent or recent < cutoff:
            continue
        gap_min = ((recent - created).total_seconds() / 60.0) if created and recent else None
        real_reconversion = bool(created and recent and gap_min > 5)
        et = event_type(p.get('recent_conversion_event_name'))
        test = is_test(p)
        if not real_reconversion:
            bucket = 'new_or_same_creation'
        elif test:
            bucket = 'test_internal'
        else:
            bucket = 'real_reconversion'
        deals = get_deals(cid)
        open_deals = [x for x in deals if x.get('hs_is_closed') != 'true']
        closed_deals = [x for x in deals if x.get('hs_is_closed') == 'true']
        phone = p.get('hs_searchable_calculated_phone_number') or p.get('hs_whatsapp_phone_number') or p.get('mobilephone') or p.get('phone') or ''
        diag, diag_rows, ops = has_diag(wpp, p.get('email'), cid, [x['id'] for x in deals], phone)
        issue = None
        if bucket == 'real_reconversion' and et in {'form_or_ad','meeting_link'} and not diag:
            if not open_deals:
                issue = 'needs_open_deal_and_diagnostic'
            else:
                issue = 'needs_diagnostic_only'
        elif bucket == 'real_reconversion' and et == 'other_conversion' and not diag and not open_deals:
            issue = 'review_other_conversion_no_open_deal'
        rec = {
            'contact_id': cid,
            'email': p.get('email'),
            'company': p.get('company'),
            'name': ' '.join(x for x in [p.get('firstname'), p.get('lastname')] if x),
            'createdate': p.get('createdate'),
            'recent_conversion_date': p.get('recent_conversion_date'),
            'conversion_gap_minutes': round(gap_min, 1) if gap_min is not None else None,
            'real_reconversion': real_reconversion,
            'event': p.get('recent_conversion_event_name'),
            'event_type': et,
            'bucket': bucket,
            'lifecycle': p.get('lifecyclestage'),
            'owner_id': p.get('hubspot_owner_id'),
            'erp': p.get('qual_erp_utiliza_') or p.get('selecione_o_sistema_de_gesto_erp'),
            'phone': phone,
            'open_deals': [{'id': x['id'], 'stage': x.get('dealstage'), 'owner': x.get('hubspot_owner_id'), 'e_sql': x.get('e_sql')} for x in open_deals],
            'closed_deals': [{'id': x['id'], 'stage': x.get('dealstage'), 'closedate': x.get('closedate'), 'owner': x.get('hubspot_owner_id'), 'e_sql': x.get('e_sql')} for x in closed_deals],
            'has_diagnostic': diag,
            'diagnostic_rows': diag_rows[-3:],
            'recent_operational_rows': ops,
            'issue': issue,
        }
        audited.append(rec)
        key = f"{bucket}|{et}|diag={diag}|open={bool(open_deals)}|issue={issue or '-'}"
        counts[key] = counts.get(key, 0) + 1
        time.sleep(0.02)
    out = {
        'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'cutoff_utc': cutoff.isoformat(),
        'contacts_with_recent_conversion': len(rows),
        'counts': counts,
        'summary': {
            'real_reconversions': sum(1 for x in audited if x['bucket'] == 'real_reconversion'),
            'real_reconversion_form_or_ad': sum(1 for x in audited if x['bucket'] == 'real_reconversion' and x['event_type'] == 'form_or_ad'),
            'real_reconversion_meeting_link': sum(1 for x in audited if x['bucket'] == 'real_reconversion' and x['event_type'] == 'meeting_link'),
            'lost_needs_diagnostic_only': sum(1 for x in audited if x['issue'] == 'needs_diagnostic_only'),
            'lost_needs_open_deal_and_diagnostic': sum(1 for x in audited if x['issue'] == 'needs_open_deal_and_diagnostic'),
            'review_other_conversion_no_open_deal': sum(1 for x in audited if x['issue'] == 'review_other_conversion_no_open_deal'),
            'already_has_diagnostic': sum(1 for x in audited if x['bucket'] == 'real_reconversion' and x['has_diagnostic']),
            'new_or_same_creation': sum(1 for x in audited if x['bucket'] == 'new_or_same_creation'),
            'test_internal': sum(1 for x in audited if x['bucket'] == 'test_internal'),
        },
        'lost': [x for x in audited if x['issue']],
        'audited': audited,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'out': str(OUT), **out['summary']}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
