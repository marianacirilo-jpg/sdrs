#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reclassificação explícita Rafael 2026-06-28: Promedix e Lleida são MQL.

Gera /tmp/gate_qualified.json com gate_trigger=manual_hubspot_mql e chama
process_gate_once.main() para enviar diagnóstico, furando Não-MQL anterior de
forma auditável.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p  # noqa: E402

EMAILS = ['juliana@medix.ind.br', 'leonardo@lleida.com.br']
PROPS = [
    'firstname','lastname','email','company','phone','hs_whatsapp_phone_number',
    'hs_searchable_calculated_phone_number','lifecyclestage','hs_lead_status',
    'hubspot_owner_id','createdate','lastmodifieddate','recent_conversion_date',
    'recent_conversion_event_name','num_conversion_events','num_unique_conversion_events',
    'hs_object_source','hs_object_source_label','hs_analytics_source','hs_latest_source',
    'hs_latest_source_data_1','hs_latest_source_data_2','qual_erp_utiliza_',
    'selecione_o_sistema_de_gesto_erp','qual_o_faturamento_anual_da_sua_empresa_',
    'qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados',
    'de_qual_forma_mais_vende_hoje_em_dia','quantas_pessoas_atuam_na_sua_empresa',
]


def token():
    return os.environ.get('HUBSPOT_API_KEY') or os.environ.get('HUBSPOT_TOKEN') or os.environ.get('HUBSPOT_PRIVATE_APP_TOKEN')


def hs_search(email):
    body = {
        'filterGroups': [{'filters': [{'propertyName': 'email', 'operator': 'EQ', 'value': email}]}],
        'properties': PROPS,
        'limit': 10,
    }
    req = urllib.request.Request(
        'https://api.hubapi.com/crm/v3/objects/contacts/search',
        data=json.dumps(body).encode('utf-8'),
        headers={'Authorization': 'Bearer ' + token(), 'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    results = data.get('results') or []
    if not results:
        raise SystemExit(f'contato não encontrado: {email}')
    return results[0]


def lead_for(email):
    c = hs_search(email)
    props = c.get('properties') or {}
    phone = props.get('hs_searchable_calculated_phone_number') or props.get('hs_whatsapp_phone_number') or props.get('phone') or ''
    return {
        'id': c.get('id'),
        'email': email,
        'firstname': props.get('firstname') or '',
        'lastname': props.get('lastname') or '',
        'company': props.get('company') or '',
        'phone': phone,
        'phone_valid': bool(p.phone_variants_with_optional_9(phone)),
        'phone_invalid_reason': '' if p.phone_variants_with_optional_9(phone) else 'sem telefone BR normalizável',
        'createdate': props.get('createdate') or '',
        'gate_trigger': 'manual_hubspot_mql',
        'hs_lastmodifieddate': props.get('lastmodifieddate') or '',
        'properties': props,
        'manual_override_by': 'Rafael Calixto',
        'manual_override_reason': 'Rafael afirmou que Promedix e Lleida são MQL após aviso Não-MQL no grupo.',
    }


def main():
    missing = [e for e in EMAILS if e not in p.RESEARCH]
    if missing:
        raise SystemExit('sem pesquisa no process_gate_once.RESEARCH: ' + ', '.join(missing))
    leads = [lead_for(e) for e in EMAILS]
    payload = {
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'count': len(leads),
        'cutoff_window_h': 24,
        'manual_reclassification': True,
        'leads': leads,
        'duplicates': [],
    }
    Path('/tmp/gate_qualified.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print('gate manual escrito:', ', '.join(EMAILS), flush=True)
    p.main()


if __name__ == '__main__':
    main()
