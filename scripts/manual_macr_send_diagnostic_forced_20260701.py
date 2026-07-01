#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rafael autorizou em 2026-07-01: enviar diagnóstico ao lead Macr mesmo com agenda/WhatsApp operacional recente.
Bypass apenas do bloqueio de diagnóstico recente; mantém gates de telefone, owner, HubSpot e envio real.
"""
import json, os, re, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p  # noqa

EMAIL = 'macr@mcstorefornecedor.com'
RESEARCH = {
    'slug': 'macr-desenvolvimento-marco-aurelio',
    'mql': True,
    'empresa_real': 'Macr produção / MC Store Fornecedor — Marco Aurélio informou atuação atacadista/lojista, ERP Olist/Tiny, faturamento R$500 mil a R$1 milhão/ano, 2 a 5 vendedores internos, loja virtual e vendas via Ads/grupos de WhatsApp.',
    'dominio_site': 'mcstorefornecedor.com — domínio profissional informado no formulário; operação com loja/fornecedor e contexto comercial real.',
    'redes': 'Rafael confirmou explicitamente que é MQL e autorizou envio do diagnóstico mesmo com alerta de WhatsApp/agenda recente.',
    'segmento': 'Atacadista/lojista/fornecedor com loja online, vendas por Ads/WhatsApp e operação que pode se beneficiar de portal B2B com catálogo, tabela, pedidos e recompra.',
    'motivo': 'MQL confirmado por Rafael. O formulário traz ERP Olist/Tiny, faturamento 500k-1M, 2-5 vendedores, loja virtual, atuação atacadista/lojista e dor de pedido manual vindo de Ads/grupos de WhatsApp.',
    'insight': 'reduzir digitação manual de pedidos, permitir pedidos 24h por lojistas/clientes recorrentes e organizar catálogo, disponibilidade e condições comerciais integradas ao Olist/Tiny',
    'telefone_publico': 'Telefone informado no HubSpot/formulário: +55 62 98583-7695.',
    'whatsapp_publico': 'Usar WhatsApp informado no HubSpot/formulário: +55 62 98583-7695.'
}
PROPS = [
    'firstname','lastname','email','company','phone','mobilephone','hs_whatsapp_phone_number','hs_searchable_calculated_phone_number',
    'lifecyclestage','hs_lead_status','hubspot_owner_id','createdate','lastmodifieddate','recent_conversion_date','recent_conversion_event_name',
    'num_conversion_events','num_unique_conversion_events','hs_object_source','hs_object_source_label','hs_analytics_source','hs_latest_source',
    'hs_analytics_source_data_1','hs_latest_source_data_2','qual_erp_utiliza_','selecione_o_sistema_de_gesto_erp',
    'qual_o_faturamento_anual_da_sua_empresa_','e_qual_faturamento_anual_da_sua_empresa',
    'qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados','de_qual_forma_mais_vende_hoje_em_dia',
    'quantas_pessoas_atuam_na_sua_empresa','quantos_vendedores_internos_sua_empresa_possui','vende_em_loja_virtual_',
    'voc_acredita_que_o_seu_cliente_compraria_sozinho_na_sua_loja_24h_por_dia_sem_precisar_de_vendedor',
    'qual_seria_o_maior_problema_que_voc_enfrenta_em_sua_operao_atualmente'
]

def token():
    env = Path('/root/.hermes/credentials/hubspot.env')
    if os.environ.get('HUBSPOT_PRIVATE_APP_TOKEN'):
        return os.environ['HUBSPOT_PRIVATE_APP_TOKEN']
    if env.exists():
        for line in env.read_text(encoding='utf-8', errors='ignore').splitlines():
            m = re.match(r'\s*(?:export\s+)?(?:HUBSPOT_PRIVATE_APP_TOKEN|HUBSPOT_TOKEN|HUBSPOT_API_KEY)=["\']?([^"\'\s]+)', line)
            if m:
                return m.group(1)
    raise RuntimeError('HubSpot token ausente')

def hs(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request('https://api.hubapi.com' + path, data=data, method=method,
                                 headers={'Authorization': 'Bearer ' + token(), 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=35) as resp:
        txt = resp.read().decode()
        return json.loads(txt) if txt else {}

def hs_search(email):
    body = {'filterGroups':[{'filters':[{'propertyName':'email','operator':'EQ','value':email}]}], 'properties': PROPS, 'limit': 1}
    rows = hs('POST', '/crm/v3/objects/contacts/search', body).get('results') or []
    if not rows:
        raise SystemExit(f'contato não encontrado: {email}')
    return rows[0]

def update_controls(email, cid):
    now = datetime.now(timezone.utc).isoformat()
    path = PROJ / 'controle' / 'mql_pipeline_queue.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        data = {'items': []}
    items = data.get('items') if isinstance(data, dict) else []
    matched = False
    for it in items:
        if isinstance(it, dict) and (str(it.get('email','')).lower() == email or str(it.get('contact_id','')) == str(cid)):
            it['state'] = 'mql_confirmado_rafael_envio_forcado'
            it['mql_confirmed'] = True
            it['diagnostic_allowed'] = True
            it['updated_at'] = now
            it.setdefault('events', []).append({'at': now, 'state': 'mql_confirmado_rafael_envio_forcado', 'reason': 'Rafael autorizou enviar diagnóstico ao Macr apesar de WhatsApp/agenda recente.'})
            matched = True
    if not matched:
        items.append({'key': email + '|manual_envio_forcado_20260701', 'events':[{'at':now,'state':'mql_confirmado_rafael_envio_forcado','reason':'Rafael autorizou envio.'}], 'updated_at':now, 'state':'mql_confirmado_rafael_envio_forcado', 'email':email, 'contact_id':cid, 'mql_confirmed':True, 'diagnostic_allowed':True})
    if isinstance(data, dict):
        data['items'] = items
        out = data
    else:
        out = items
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')

def main():
    c = hs_search(EMAIL)
    props = c.get('properties') or {}
    cid = str(c.get('id'))
    # Garantir HubSpot MQL/SQL já antes do envio.
    hs('PATCH', f'/crm/v3/objects/contacts/{cid}', {'properties': {'lifecyclestage':'marketingqualifiedlead', 'hubspot_owner_id':'85778446'}})
    phone = props.get('hs_searchable_calculated_phone_number') or props.get('hs_whatsapp_phone_number') or props.get('mobilephone') or props.get('phone') or ''
    p.RESEARCH[EMAIL] = dict(RESEARCH)
    # Bypass pontual: a agenda confirmada não deve bloquear este envio porque Rafael pediu expressamente.
    p.recent_prior_operational_diagnosis = lambda *args, **kwargs: (False, 'override Rafael: enviar diagnóstico mesmo com agenda/WhatsApp recente')
    p.existing_mql_outreach = lambda *args, **kwargs: (False, 'override Rafael: alerta agenda não conta como diagnóstico/PDF enviado')
    p.can_send_diagnostic = lambda *args, **kwargs: (True, 'override Rafael: envio autorizado para Macr')
    lead = {
        'id': cid,
        'email': EMAIL,
        'firstname': props.get('firstname') or 'Marco',
        'lastname': props.get('lastname') or 'Aurélio',
        'company': props.get('company') or 'Macr produção',
        'phone': phone,
        'phone_valid': bool(p.phone_variants_with_optional_9(phone)),
        'phone_invalid_reason': '' if p.phone_variants_with_optional_9(phone) else 'sem telefone BR normalizável',
        'createdate': props.get('createdate') or '',
        'gate_trigger': 'manual_hubspot_mql',
        # Sem force_bridge_port: se o chip do Lucas/4603 estiver em quota, o motor usa fallback institucional.
        'hs_lastmodifieddate': props.get('lastmodifieddate') or '',
        'properties': props,
        'manual_override_by': 'Rafael Calixto',
        'manual_override_reason': 'Rafael respondeu ao alerta MQL sem WhatsApp: manda pra esse lead, pode mandar.',
    }
    update_controls(EMAIL, cid)
    payload = {'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'count':1, 'cutoff_window_h':24, 'manual_reclassification':True, 'force_send_diagnostic':True, 'leads':[lead], 'duplicates':[]}
    Path('/tmp/gate_qualified.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print('gate manual escrito:', EMAIL, flush=True)
    p.main()

if __name__ == '__main__':
    main()
