#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Override Rafael 2026-07-01: Diversita / Karen é MQL e deve receber diagnóstico.
Não marcar SQL; apenas MQL no contato, negócio aberto/task/diagnóstico.
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

EMAIL = 'karen@alkbio.com.br'
OWNER_LUCAS = '85778446'
FORCE_PORT = 4600  # mesmo chip do aviso interno anterior para passar segurança Não-MQL→MQL

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
    'slug': 'diversita-karen-leidens',
    'mql': True,
    'empresa_real': 'Diversita / Karen Leidens — lead de campanha Facebook Lead Ads reclassificado como MQL por Rafael em 01/07/2026.',
    'dominio_site': 'alkbio.com.br — fonte pública apontou P&D/assessoria técnica de cosméticos, mas o formulário traz contexto comercial relevante e Rafael autorizou seguir como MQL.',
    'redes': 'Formulário indica venda para padarias, restaurantes, supermercados e hotéis, televendas e dor de vendedor tirando pedido manualmente; discrepância pública será validada no follow-up comercial.',
    'segmento': 'Operação comercial com venda recorrente indicada no formulário; potencial B2B a validar no diagnóstico.',
    'motivo': 'MQL por orientação explícita de Rafael: leads recentes dos anúncios/formulários, inclusive pendentes/dúbios, devem seguir como MQL e receber diagnóstico; só desqualificar teste/fake/sem empresa/sem estrutura clara. Este caso não é teste/fake e tem telefone/formulário válido.',
    'insight': 'centralizar pedidos e recompra em portal B2B para reduzir pedido manual por televendas/WhatsApp e facilitar atendimento recorrente a canais como padarias, restaurantes, supermercados e hotéis',
    'telefone_publico': 'Telefone válido recebido no HubSpot/formulário: +55 48 99969-0989.',
    'whatsapp_publico': 'Usar telefone informado no formulário/HubSpot: +55 48 99969-0989.',
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


def hs(path, method='GET', payload=None):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = urllib.request.Request('https://api.hubapi.com' + path, data=data, headers={'Authorization': 'Bearer ' + token(), 'Content-Type': 'application/json'}, method=method)
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode('utf-8'))


def hs_search(email):
    body = {'filterGroups': [{'filters': [{'propertyName': 'email', 'operator': 'EQ', 'value': email}]}], 'properties': PROPS, 'limit': 10}
    data = hs('/crm/v3/objects/contacts/search', 'POST', body)
    results = data.get('results') or []
    if not results:
        raise SystemExit(f'contato não encontrado: {email}')
    return results[0]


def contact_deals(cid):
    assoc = hs(f'/crm/v4/objects/contacts/{cid}/associations/deals?limit=100')
    out = []
    for ar in assoc.get('results') or []:
        did = str(ar.get('toObjectId') or '')
        if not did:
            continue
        deal = hs(f'/crm/v3/objects/deals/{did}?properties=dealname,dealstage,pipeline,hs_is_closed,hubspot_owner_id,e_sql')
        out.append({'id': did, **(deal.get('properties') or {})})
    return out


def ensure_owner_and_open_deal(cid, props):
    # marcar MQL e owner, sem SQL
    hs(f'/crm/v3/objects/contacts/{cid}', 'PATCH', {'properties': {'lifecyclestage': 'marketingqualifiedlead', 'hubspot_owner_id': OWNER_LUCAS}})
    deals = contact_deals(cid)
    open_deals = [d for d in deals if d.get('hs_is_closed') != 'true']
    if open_deals:
        did = open_deals[0]['id']
        hs(f'/crm/v3/objects/deals/{did}', 'PATCH', {'properties': {'pipeline': '671008549', 'dealstage': open_deals[0].get('dealstage') or '984052829', 'hubspot_owner_id': OWNER_LUCAS, 'e_sql': ''}})
        return did, 'open_exists'
    company = props.get('company') or 'Diversita'
    deal = hs('/crm/v3/objects/deals', 'POST', {
        'properties': {'dealname': company + ' - Nova oportunidade', 'pipeline': '671008549', 'dealstage': '984052829', 'hubspot_owner_id': OWNER_LUCAS, 'e_sql': ''},
        'associations': [{'to': {'id': str(cid)}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 3}]}],
    })
    return str(deal.get('id')), 'created'


def lead_for(email):
    c = hs_search(email)
    props = c.get('properties') or {}
    deal_id, deal_mode = ensure_owner_and_open_deal(c.get('id'), props)
    # Recarregar props depois do patch
    c = hs_search(email)
    props = c.get('properties') or props
    phone = props.get('hs_searchable_calculated_phone_number') or props.get('hs_whatsapp_phone_number') or props.get('mobilephone') or props.get('phone') or ''
    return {
        'id': c.get('id'),
        'email': email,
        'firstname': props.get('firstname') or '',
        'lastname': props.get('lastname') or '',
        'company': props.get('company') or 'Diversita',
        'phone': phone,
        'phone_valid': bool(p.phone_variants_with_optional_9(phone)),
        'phone_invalid_reason': '' if p.phone_variants_with_optional_9(phone) else 'sem telefone BR normalizável',
        'createdate': props.get('createdate') or '',
        'gate_trigger': 'manual_hubspot_mql',
        'force_bridge_port': FORCE_PORT,
        'hs_lastmodifieddate': props.get('lastmodifieddate') or '',
        'properties': props,
        'manual_override_by': 'Rafael Calixto',
        'manual_override_reason': 'Rafael confirmou: pode marcar como MQL e mandar diagnóstico; não marcar SQL.',
        'deal_id': deal_id,
        'deal_mode': deal_mode,
    }


def update_json_files(email, contact_id, deal_id):
    now = datetime.now(timezone.utc).isoformat()
    # pipeline
    path = PROJ / 'controle' / 'mql_pipeline_queue.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    for it in data.get('items', []):
        if isinstance(it, dict) and str(it.get('email','')).lower() == email:
            it['state'] = 'mql_confirmado_rafael_manual'
            it['mql_confirmed'] = True
            it['diagnostic_allowed'] = True
            it['status'] = 'pending_manual_dispatch'
            it['deal_id'] = deal_id
            it['owner_id'] = OWNER_LUCAS
            it['owner_name'] = 'Lucas Batista'
            it['updated_at'] = now
            it.setdefault('events', []).append({'at': now, 'state': 'mql_confirmado_rafael_manual', 'reason': 'Rafael confirmou MQL e autorizou diagnóstico; não marcar SQL.'})
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    # pending
    path = PROJ / 'controle' / 'pending_lead_alerts.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    row = data.get(email)
    if isinstance(row, dict):
        row['final_status'] = 'mql_confirmado_rafael_manual'
        row['finalized_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        row['final_reason'] = 'Rafael confirmou MQL e autorizou diagnóstico; não marcar SQL.'
        row['owner_id'] = OWNER_LUCAS
        row['owner_name'] = 'Lucas Batista'
        row['deal_id'] = deal_id
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    # supersede wpp non-mql/pending local statuses (mantém auditoria, mas evita conflito)
    path = PROJ / 'controle' / 'wpp_envios.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    rows = data.get('envios') if isinstance(data, dict) else data
    superseded = 0
    for r in rows:
        if isinstance(r, dict) and str(r.get('email','')).lower() == email and str(r.get('status','')).lower() in {'nao_mql_grupo','pending_review_grupo'}:
            r['status'] = str(r.get('status')) + '_superseded_by_rafael_mql'
            r['superseded_at'] = now
            r['superseded_reason'] = 'Rafael confirmou MQL e autorizou diagnóstico; não marcar SQL.'
            superseded += 1
    if isinstance(data, dict):
        data['envios'] = rows
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return superseded


def main():
    p.RESEARCH[EMAIL] = RESEARCH
    lead = lead_for(EMAIL)
    superseded = update_json_files(EMAIL, lead['id'], lead['deal_id'])
    payload = {'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'count': 1, 'cutoff_window_h': 24, 'manual_reclassification': True, 'leads': [lead], 'duplicates': []}
    Path('/tmp/gate_qualified.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'gate manual escrito: {EMAIL}; deal={lead["deal_id"]} mode={lead["deal_mode"]}; superseded={superseded}', flush=True)
    p.main()

if __name__ == '__main__':
    main()
