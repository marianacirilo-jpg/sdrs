#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Disparo manual autorizado Rafael 2026-06-30: Dbianco / Alan Bianco MQL.

Contexto: fluxo autônomo marcou MQL, gerou PDF e task, mas bloqueou WhatsApp por
limite operacional de chips. Rafael autorizou explicitamente: "pode disparar fica
tranquilo faz o follow". Este script usa o fluxo oficial process_gate_once, mas
bypassa o limite por chip só para este envio pontual e não envia agenda imediata.
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

EMAIL = 'alanbianco@estacaoy.com.br'
CID = '232362769447'

PROPS = [
    'firstname','lastname','email','company','phone','hs_whatsapp_phone_number',
    'hs_searchable_calculated_phone_number','lifecyclestage','hs_lead_status',
    'hubspot_owner_id','createdate','lastmodifieddate','recent_conversion_date',
    'recent_conversion_event_name','num_conversion_events','num_unique_conversion_events',
    'hs_object_source','hs_object_source_label','hs_analytics_source','hs_latest_source',
    'hs_latest_source_data_1','hs_latest_source_data_2','qual_erp_utiliza_',
    'selecione_o_sistema_de_gesto_erp','qual_o_faturamento_anual_da_sua_empresa_',
    'e_qual_faturamento_anual_da_sua_empresa','qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados',
    'de_qual_forma_mais_vende_hoje_em_dia','quantas_pessoas_atuam_na_sua_empresa',
    'quantos_vendedores_internos','quantos_vendedores_internos_sua_empresa_possui',
    'vende_em_loja_virtual_','voc_acredita_que_o_seu_cliente_compraria_sozinho_na_sua_loja_24h_por_dia_sem_precisar_de_vendedor',
    'qual_seria_o_maior_problema_que_voc_enfrenta_em_sua_operao_atualmente','principais_dores',
]


def token():
    txt = Path('/root/.hermes/credentials/hubspot.env').read_text(errors='ignore')
    m = re.search(r'pat-[A-Za-z0-9_\-]+', txt)
    if m:
        return m.group(0)
    for line in txt.splitlines():
        if '=' not in line or line.strip().startswith('#'):
            continue
        k, v = line.split('=', 1)
        if 'TOKEN' in k.upper() or 'HUBSPOT' in k.upper():
            v = v.strip().strip('"\'')
            if v:
                return v
    raise SystemExit('sem token HubSpot')


def hs_get_contact():
    req = urllib.request.Request(
        f'https://api.hubapi.com/crm/v3/objects/contacts/{CID}?properties={",".join(PROPS)}',
        headers={'Authorization': 'Bearer ' + token()},
        method='GET',
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))


def lead_for():
    c = hs_get_contact()
    props = c.get('properties') or {}
    phone = props.get('hs_searchable_calculated_phone_number') or '11983140135'
    return {
        'id': c.get('id') or CID,
        'email': EMAIL,
        'firstname': props.get('firstname') or 'Alan',
        'lastname': props.get('lastname') or 'Bianco',
        'company': props.get('company') or 'Dbianco',
        'phone': phone,
        'phone_valid': bool(p.phone_variants_with_optional_9(phone)),
        'phone_invalid_reason': '' if p.phone_variants_with_optional_9(phone) else 'sem telefone BR normalizável',
        'createdate': props.get('createdate') or '',
        'gate_trigger': 'manual_hubspot_mql',
        'hs_lastmodifieddate': props.get('lastmodifieddate') or '',
        'properties': props,
        'manual_override_by': 'Rafael Calixto',
        'manual_override_reason': 'Rafael confirmou Dbianco como MQL e autorizou disparo apesar do limite operacional de chips em 30/06/2026.',
    }


def main():
    # Pesquisa já gravada no process_gate_once pelo fluxo autônomo; reforço aqui para
    # este script ser autocontido caso o arquivo principal mude.
    p.RESEARCH[EMAIL] = {
        'slug': 'dbianco-cosmeticos-alan-bianco',
        'mql': True,
        'empresa_real': 'D’Bianco / DBianco Professional — marca/fábrica de cosméticos capilares com e-commerce próprio em dbianco.com.br, linha profissional e home care, contato Alan Bianco.',
        'dominio_site': 'estacaoy.com.br é o domínio do e-mail, mas a operação pública validada está em dbianco.com.br, site oficial Shopify ativo da DBianco Professional com catálogo, carrinho, WhatsApp público e página “Seja um Distribuidor”.',
        'redes': 'Site dbianco.com.br confirma loja virtual, catálogo, redes sociais, frete nacional e página para distribuidores oficiais/parceiros/salões.',
        'segmento': 'Fábrica/marca de cosméticos capilares com canal digital próprio, linha profissional e home care, venda por WhatsApp/e-commerce e programa de distribuidores/parceiros para salões de beleza e consumidores recorrentes.',
        'motivo': 'Rafael confirmou MQL. A análise também passa no crivo: fábrica/marca própria de cosméticos, loja virtual ativa, faturamento de R$500 mil a R$1 milhão/ano, venda por WhatsApp, ERP Outro, dor de carteira parada e página explícita para distribuidores/salões/parceiros.',
        'insight': 'distribuidores, salões e parceiros consultarem catálogo, preço e disponibilidade das linhas profissionais e home care para repor produtos sem depender de cada atendimento no WhatsApp',
        'telefone_publico': 'Telefone celular válido recebido no HubSpot/formulário: +55 11 98314-0135; site oficial também publica WhatsApp +55 11 98314-0135.',
        'whatsapp_publico': 'Usar telefone informado no formulário/HubSpot: +55 11 98314-0135.',
    }

    # Cadência oficial até a pergunta. Agenda não sai neste script para não colar
    # link imediatamente após autorização manual; Lucas/HubSpot seguem pelo follow.
    p.TEXT_TO_PDF_DELAY_SECONDS = 60
    p.PDF_TO_QUESTION_DELAY_SECONDS = 30
    p.QUESTION_TO_AGENDA_DELAY_SECONDS = 1
    p.should_send_agenda = lambda *args, **kwargs: (False, 'agenda não enviada neste disparo manual; Rafael autorizou follow/diagnóstico e Lucas segue pelo HubSpot')

    # Rafael autorizou superar o bloqueio de limite para este lead pontual.
    original_limit = p.port_within_external_limits
    p.port_within_external_limits = lambda envios, port: (True, f'override Rafael 30/06 para {EMAIL}; limite ignorado só neste envio')

    payload = {
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'count': 1,
        'cutoff_window_h': 24,
        'manual_authorized_send': True,
        'leads': [lead_for()],
        'duplicates': [],
    }
    Path('/tmp/gate_qualified.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print('gate manual escrito:', EMAIL, flush=True)
    try:
        p.main()
    finally:
        p.port_within_external_limits = original_limit


if __name__ == '__main__':
    main()
