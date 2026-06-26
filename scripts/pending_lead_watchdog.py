#!/usr/bin/env python3
"""Alert Discord when a new HubSpot form lead is pending diagnosis.

This DOES NOT send WhatsApp, DOES NOT mark the lead as processed, and DOES NOT advance the MQL gate cutoff.
It only writes controle/pending_lead_alerts.json to avoid duplicate Discord alerts.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path('/root/.hermes/zydon-prospeccao')
CONTROL = ROOT / 'controle'
PROCESSED = CONTROL / 'processed_emails.txt'
ALERTS = CONTROL / 'pending_lead_alerts.json'
HS = 'https://api.hubapi.com'

PROPS = [
    'email','firstname','lastname','company','phone','hs_searchable_calculated_phone_number',
    'createdate','recent_conversion_date','recent_conversion_event_name',
    'lifecyclestage','hubspot_owner_id','hs_object_source','hs_object_source_label',
    'qual_erp_utiliza_','selecione_o_sistema_de_gesto_erp','quantas_pessoas_atuam_na_sua_empresa',
    'qual_o_faturamento_anual_da_sua_empresa_','de_qual_forma_mais_vende_hoje_em_dia',
    'vende_em_loja_virtual_','hs_analytics_source','hs_analytics_source_data_1','hs_analytics_source_data_2',
    'hs_latest_source','hs_latest_source_data_1','hs_latest_source_data_2'
]
OWNER_NAMES = {
    '88063842': 'Sarah',
    '86265630': 'Breno',
    '85778446': 'Lucas Batista',
}

def load_env():
    env = Path('/root/.hermes/credentials/hubspot.env')
    if env.exists():
        for line in env.read_text(errors='ignore').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def token():
    load_env()
    t = (os.environ.get('HUBSPOT_PRIVATE_APP_TOKEN')
         or os.environ.get('HUBSPOT_TOKEN')
         or os.environ.get('HUBSPOT_API_KEY'))
    if not t:
        raise RuntimeError('HubSpot token ausente')
    return t

def hs_search_recent():
    since = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    body = {
        # OR: contato criado agora OU contato antigo que reenviou formulário agora.
        'filterGroups': [
            {'filters': [
                {'propertyName': 'createdate', 'operator': 'GTE', 'value': since},
                {'propertyName': 'hs_object_source', 'operator': 'EQ', 'value': 'FORM'},
            ]},
            {'filters': [
                {'propertyName': 'recent_conversion_date', 'operator': 'GTE', 'value': since},
            ]},
        ],
        'properties': PROPS,
        'limit': 50,
        'sorts': [{'propertyName': 'createdate', 'direction': 'ASCENDING'}],
    }
    req = urllib.request.Request(
        HS + '/crm/v3/objects/contacts/search',
        data=json.dumps(body).encode(),
        headers={'Authorization': 'Bearer ' + token(), 'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode()).get('results', [])

def load_processed():
    if not PROCESSED.exists():
        return set()
    out = set()
    for line in PROCESSED.read_text(errors='ignore').splitlines():
        if line.strip():
            out.add(line.split('|', 1)[0].strip().lower())
    return out

def load_alerts():
    if not ALERTS.exists():
        return {}
    try:
        return json.loads(ALERTS.read_text(errors='ignore') or '{}')
    except Exception:
        return {}

def save_alerts(data):
    CONTROL.mkdir(exist_ok=True)
    ALERTS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def only_digits(x):
    return re.sub(r'\D', '', x or '')

def is_landline_br(d):
    # 55 + DDD + 8 digits, or DDD + 8 digits => likely landline. Mobile has 9 after DDD.
    if len(d) == 12 and d.startswith('55'):
        d = d[2:]
    return len(d) == 10

def fmt_brt(s):
    try:
        dt = datetime.fromisoformat((s or '').replace('Z', '+00:00'))
        return dt.astimezone(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M BRT')
    except Exception:
        return s or 'não informado'

def erp_line(p):
    v = (p.get('qual_erp_utiliza_') or p.get('selecione_o_sistema_de_gesto_erp') or '').strip()
    return f'ERP informado: {v}\n' if v else ''

def source_line(p):
    vals = []
    for k in ('hs_analytics_source','hs_analytics_source_data_1','hs_analytics_source_data_2','hs_latest_source','hs_latest_source_data_1','hs_latest_source_data_2'):
        v = (p.get(k) or '').strip()
        if v and v not in vals:
            vals.append(v)
    return ' / '.join(vals[:2]) + ((' | ' + vals[2]) if len(vals) > 2 else '') if vals else 'não informado'

def mql_likely(p):
    lifecycle = (p.get('lifecyclestage') or '').lower()
    if lifecycle == 'marketingqualifiedlead':
        return True
    strong_revenue = 'R$10 a R$50 milhões' in (p.get('qual_o_faturamento_anual_da_sua_empresa_') or '')
    people = p.get('quantas_pessoas_atuam_na_sua_empresa') or ''
    return strong_revenue or people in {'26_a_50','51_a_100','101_a_150','+151'}

def _dt(s):
    try:
        return datetime.fromisoformat((s or '').replace('Z', '+00:00'))
    except Exception:
        return None


def main():
    processed = load_processed()
    alerts = load_alerts()
    contacts = hs_search_recent()
    sent = []
    for c in contacts:
        p = c.get('properties') or {}
        email = (p.get('email') or '').strip().lower()
        recent_dt = _dt(p.get('recent_conversion_date'))
        created_dt = _dt(p.get('createdate'))
        is_reentry = bool(recent_dt and created_dt and (recent_dt - created_dt).total_seconds() > 300)
        alert_key = f'{email}|{p.get("recent_conversion_date")}' if is_reentry else email
        if not email or (email in processed and not is_reentry) or alert_key in alerts:
            continue
        if (p.get('hs_object_source') or '').upper() != 'FORM' and not p.get('recent_conversion_date'):
            continue
        if (p.get('lifecyclestage') or '').lower() == 'customer':
            continue
        company = (p.get('company') or '').strip() or 'não informado'
        first = (p.get('firstname') or '').strip() or 'não informado'
        owner = OWNER_NAMES.get(p.get('hubspot_owner_id') or '', 'sem dono definido')
        phone = p.get('hs_searchable_calculated_phone_number') or p.get('phone') or ''
        digits = only_digits(phone)
        phone_note = ''
        if not digits:
            phone_note = '\nTelefone: ausente/mascarado — precisa confirmar WhatsApp'
        elif is_landline_br(digits):
            phone_note = f'\nTelefone informado: {phone} — parece fixo/inválido para WhatsApp'
        if is_reentry:
            label = '🔁 Lead voltou a preencher o formulário — iniciei análise'
        else:
            label = '✅ Lead novo possivelmente MQL — iniciei análise' if mql_likely(p) else '🟡 Lead novo — iniciei qualificação'
        text = (f'{label}\n'
                f'Empresa: {company}\n'
                f'Contato: {first}\n'
                f'Email: {email}\n'
                f'{erp_line(p)}'
                f'Entrada: {fmt_brt(p.get("recent_conversion_date") or p.get("createdate"))}\n'
                f'Criativo/origem: {source_line(p)}\n'
                f'Responsável: {owner}'
                f'{phone_note}\n\n'
                f'Status: já está na fila para qualificação. Se fizer sentido, o consultor responsável recebe para agir logo em seguida.')
        alerts[alert_key] = {
            'contact_id': c.get('id'),
            'email': email,
            'createdate': p.get('createdate'),
            'recent_conversion_date': p.get('recent_conversion_date'),
            'alerted_at': datetime.now(timezone.utc).isoformat(),
            'channel': 'discord_only',
        }
        sent.append(text)
    save_alerts(alerts)
    # no_agent: stdout vazio => silêncio quando nada novo. Só reporta ao Discord quando alertou.
    if sent:
        print('\n\n'.join(sent))

if __name__ == '__main__':
    main()
