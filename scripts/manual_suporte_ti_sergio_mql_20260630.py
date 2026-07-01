#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Override explícito Rafael 2026-06-30: Suporte de TI / Sergio é MQL.

Gera gate manual e chama process_gate_once para lifecycle, PDF, WhatsApp,
HubSpot task e ledger, preservando auditoria da decisão humana.
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

EMAIL = 'sergio.afonso@arenadesk.com.br'

PROPS = [
    'firstname','lastname','email','company','phone','hs_whatsapp_phone_number',
    'hs_searchable_calculated_phone_number','lifecyclestage','hs_lead_status',
    'hubspot_owner_id','createdate','lastmodifieddate','recent_conversion_date',
    'recent_conversion_event_name','num_conversion_events','num_unique_conversion_events',
    'hs_object_source','hs_object_source_label','hs_analytics_source','hs_latest_source',
    'hs_analytics_source_data_1','hs_latest_source_data_2','qual_erp_utiliza_',
    'selecione_o_sistema_de_gesto_erp','qual_o_faturamento_anual_da_sua_empresa_',
    'e_qual_faturamento_anual_da_sua_empresa',
    'qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados',
    'de_qual_forma_mais_vende_hoje_em_dia','quantas_pessoas_atuam_na_sua_empresa',
    'quantos_vendedores_internos_sua_empresa_possui',
    'vende_em_loja_virtual_',
    'voc_acredita_que_o_seu_cliente_compraria_sozinho_na_sua_loja_24h_por_dia_sem_precisar_de_vendedor',
    'qual_seria_o_maior_problema_que_voc_enfrenta_em_sua_operao_atualmente',
]

RESEARCH = {
    'slug': 'suporte-ti-sergio-afonso-arenadesk',
    'mql': True,
    'empresa_real': 'Suporte de TI / ArenaDesk — lead de formulário Facebook aprovado manualmente por Rafael Calixto como MQL em 30/06/2026 após revisão humana.',
    'dominio_site': 'arenadesk.com.br — no ciclo automático abriu página padrão/login Plesk e não trouxe catálogo público; a aprovação MQL é manual de Rafael, sobrepondo o fail-closed automático.',
    'redes': 'Pesquisa automática anterior não achou fonte pública suficiente; Rafael confirmou que pode considerar MQL. Não inventar evidência pública: seguir como override humano/auditável.',
    'segmento': 'Operação informada como Suporte de TI/ArenaDesk, com formulário indicando loja virtual, venda para revendedores/clientes finais, time pequeno e dor de escalar sem contratar mais gente.',
    'motivo': 'Override explícito Rafael: apesar do fail-closed automático por falta de site/catálogo público, Rafael autorizou considerar MQL. Formulário indica loja virtual, autosserviço 24h e dor de escala, portanto seguir diagnóstico como MQL aprovado manualmente.',
    'insight': 'clientes e revendedores acessarem um portal 24h com catálogo, condições e pedido autônomo para reduzir dependência de atendimento manual e apoiar escala sem aumentar equipe',
    'telefone_publico': 'Telefone celular válido recebido no HubSpot/formulário: +55 71 99987-6391.',
    'whatsapp_publico': 'Usar o celular válido recebido no HubSpot/formulário: +55 71 99987-6391.',
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
        'manual_override_reason': 'Rafael respondeu “Pode considerar MQL” para Suporte de TI / Sergio após alerta pendente.',
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
            it['state'] = 'mql_confirmado_rafael_manual'
            it['mql_confirmed'] = True
            it['diagnostic_allowed'] = True
            it['updated_at'] = now
            it.setdefault('events', []).append({'at': now, 'state': 'mql_confirmado_rafael_manual', 'reason': 'Rafael autorizou: “Pode considerar MQL”.'})
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
        row['final_status'] = 'mql_confirmado_rafael_manual'
        row['finalized_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        row['final_reason'] = 'Rafael autorizou considerar MQL após revisão humana.'
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    p.RESEARCH[EMAIL] = RESEARCH
    lead = lead_for(EMAIL)
    update_pipeline_status(EMAIL, lead['id'])
    update_pending_alert(EMAIL)
    payload = {
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'count': 1,
        'cutoff_window_h': 24,
        'manual_reclassification': True,
        'leads': [lead],
        'duplicates': [],
    }
    Path('/tmp/gate_qualified.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print('gate manual escrito:', EMAIL, flush=True)
    p.main()


if __name__ == '__main__':
    main()
