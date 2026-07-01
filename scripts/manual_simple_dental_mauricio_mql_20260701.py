#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Override/regra Rafael 2026-07-01: em dúvida inicial/pending_review, considerar MQL.
Caso: Simple Dental Center / Mauricio — reclassificar como MQL e rodar diagnóstico.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p  # noqa: E402

EMAIL = 'mauricio@simpledentalcenter.com.br'

PROPS = [
    'firstname','lastname','email','company','phone','mobilephone','hs_whatsapp_phone_number',
    'hs_searchable_calculated_phone_number','lifecyclestage','hs_lead_status',
    'hubspot_owner_id','createdate','lastmodifieddate','recent_conversion_date',
    'recent_conversion_event_name','num_conversion_events','num_unique_conversion_events',
    'hs_object_source','hs_object_source_label','hs_analytics_source','hs_latest_source',
    'hs_analytics_source_data_1','hs_latest_source_data_2','qual_erp_utiliza_',
    'selecione_o_sistema_de_gesto_erp','qual_o_faturamento_anual_da_sua_empresa_',
    'e_qual_faturamento_anual_da_sua_empresa',
    'qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados',
    'de_qual_forma_mais_vende_hoje_em_dia','quantas_pessoas_atuam_na_sua_empresa',
    'quantos_vendedores_internos_sua_empresa_possui','vende_em_loja_virtual_',
    'voc_acredita_que_o_seu_cliente_compraria_sozinho_na_sua_loja_24h_por_dia_sem_precisar_de_vendedor',
    'qual_seria_o_maior_problema_que_voc_enfrenta_em_sua_operao_atualmente',
]

RESEARCH = {
    'slug': 'simple-dental-center-mauricio',
    'mql': True,
    'empresa_real': 'Simple Dental Center / Simple Supplies Ltda — operação odontológica digital aprovada como MQL pela regra Rafael em 01/07/2026: em dúvida inicial/pending_review, considerar MQL neste primeiro momento.',
    'dominio_site': 'simpledentalcenter.com.br — site oficial confirma centro de negócios para fluxo digital odontológico, scan/pedidos/prótese e atendimento a dentistas.',
    'redes': 'Ciclo automático anterior encontrou site real e operação digital odontológica, mas reprovou por fail-closed por não comprovar atacado/distribuição/indústria. Rafael ajustou a regra: em dúvida inicial, considerar MQL para validar comercialmente com diagnóstico.',
    'segmento': 'Centro/fornecedor de soluções odontológicas digitais com pedidos, fluxo de trabalho e atendimento a dentistas/laboratórios; potencial B2B a validar no diagnóstico.',
    'motivo': 'MQL por orientação Rafael: o caso estava pendente/dúbio; apesar de não haver prova pública suficiente de atacado/distribuição, há operação real, site oficial e fluxo digital/pedidos em saúde odontológica. Neste primeiro momento, dúvidas de pending_review devem seguir como MQL para diagnóstico e follow-up, sem cair em Não-MQL.',
    'insight': 'dentistas, clínicas e laboratórios acompanharem pedidos, arquivos/scan, status e solicitações por um portal 24h, reduzindo troca manual por WhatsApp e aumentando previsibilidade operacional',
    'telefone_publico': 'Telefone celular válido recebido no HubSpot/formulário: +55 11 95498-8448.',
    'whatsapp_publico': 'Usar telefone informado no formulário/HubSpot: +55 11 95498-8448.',
}


def token():
    if os.environ.get('HUBSPOT_PRIVATE_APP_TOKEN'):
        return os.environ['HUBSPOT_PRIVATE_APP_TOKEN']
    env = Path('/root/.hermes/credentials/hubspot.env')
    if env.exists():
        for line in env.read_text(encoding='utf-8', errors='ignore').splitlines():
            m = re.match(r'\s*(?:export\s+)?(?:HUBSPOT_PRIVATE_APP_TOKEN|HUBSPOT_TOKEN|HUBSPOT_API_KEY)=["\']?([^"\'\s]+)', line)
            if m:
                return m.group(1)
    return ''


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
    phone = props.get('hs_searchable_calculated_phone_number') or props.get('hs_whatsapp_phone_number') or props.get('mobilephone') or props.get('phone') or ''
    return {
        'id': c.get('id'),
        'email': email,
        'firstname': props.get('firstname') or '',
        'lastname': props.get('lastname') or '',
        'company': props.get('company') or 'Simple Dental Center',
        'phone': phone,
        'phone_valid': bool(p.phone_variants_with_optional_9(phone)),
        'phone_invalid_reason': '' if p.phone_variants_with_optional_9(phone) else 'sem telefone BR normalizável',
        'createdate': props.get('createdate') or '',
        'gate_trigger': 'manual_hubspot_mql',
        'hs_lastmodifieddate': props.get('lastmodifieddate') or '',
        'properties': props,
        'manual_override_by': 'Rafael Calixto',
        'manual_override_reason': 'Rafael definiu: em dúvida inicial/pending_review, considerar MQL neste primeiro momento.',
    }


def update_pipeline_status(email, contact_id):
    path = PROJ / 'controle' / 'mql_pipeline_queue.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return
    items = data.get('items') if isinstance(data, dict) else (data if isinstance(data, list) else [])
    now = datetime.now(timezone.utc).isoformat()
    for it in items:
        if not isinstance(it, dict):
            continue
        if str(it.get('email') or '').lower() == email or str(it.get('contact_id') or '') == str(contact_id):
            it['state'] = 'mql_confirmado_regra_duvida_rafael'
            it['mql_confirmed'] = True
            it['diagnostic_allowed'] = True
            it['updated_at'] = now
            it['previous_auto_state'] = 'nao_mql_grupo'
            it.setdefault('events', []).append({'at': now, 'state': 'mql_confirmado_regra_duvida_rafael', 'reason': 'Rafael: em dúvida inicial/pending_review, considerar MQL.'})
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def update_pending_alert(email):
    path = PROJ / 'controle' / 'pending_lead_alerts.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return
    row = data.get(email) if isinstance(data, dict) else None
    if isinstance(row, dict):
        row['channel'] = 'final_analysis_completed'
        row['final_status'] = 'mql_confirmado_regra_duvida_rafael'
        row['finalized_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        row['final_reason'] = 'Rafael definiu que, em dúvida inicial/pending_review, deve considerar MQL; reclassificado para diagnóstico.'
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def supersede_non_mql_ledger(email):
    path = PROJ / 'controle' / 'wpp_envios.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return 0
    rows = data.get('envios') if isinstance(data, dict) else (data if isinstance(data, list) else [])
    n = 0
    now = datetime.now(timezone.utc).isoformat()
    for r in rows:
        if not isinstance(r, dict):
            continue
        if str(r.get('email') or '').lower() == email and str(r.get('status') or '').lower() == 'nao_mql_grupo':
            r['status'] = 'nao_mql_superseded_by_regra_duvida_mql'
            r['superseded_at'] = now
            r['superseded_reason'] = 'Rafael: em dúvida inicial/pending_review, considerar MQL.'
            n += 1
    if isinstance(data, dict):
        data['envios'] = rows
        out = data
    else:
        out = rows
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    return n


def main():
    p.RESEARCH[EMAIL] = RESEARCH
    lead = lead_for(EMAIL)
    update_pipeline_status(EMAIL, lead['id'])
    update_pending_alert(EMAIL)
    superseded = supersede_non_mql_ledger(EMAIL)
    payload = {
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'count': 1,
        'cutoff_window_h': 24,
        'manual_reclassification': True,
        'leads': [lead],
        'duplicates': [],
    }
    Path('/tmp/gate_qualified.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'gate manual escrito: {EMAIL}; nao_mql_superseded={superseded}', flush=True)
    p.main()


if __name__ == '__main__':
    main()
