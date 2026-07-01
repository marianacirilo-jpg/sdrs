#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reclassificação explícita Rafael 2026-06-29: Schutzmann/Maximilian virou MQL após validar sentido no WhatsApp.
Fluxo conservador: usa process_gate_once, com override manual auditável e respiros curtos para concluir ainda hoje.
"""
import json, os, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p  # noqa: E402

EMAIL = 'maxcordioli@schutzmann.com.br'
CID = '231545774511'
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
    'quantos_vendedores_internos','quantos_vendedores_internos_sua_empresa_possui',
]

def token():
    for k in ('HUBSPOT_API_KEY','HUBSPOT_TOKEN','HUBSPOT_PRIVATE_APP_TOKEN','HUBSPOT_ACCESS_TOKEN'):
        if os.environ.get(k): return os.environ[k]
    env=Path('/root/.hermes/credentials/hubspot.env')
    for line in env.read_text().splitlines():
        if '=' not in line or line.strip().startswith('#'): continue
        k,v=line.split('=',1); k=k.strip(); v=v.strip().strip('"\'')
        if k in ('HUBSPOT_API_KEY','HUBSPOT_TOKEN','HUBSPOT_PRIVATE_APP_TOKEN','HUBSPOT_ACCESS_TOKEN'):
            return v
    raise SystemExit('sem token HubSpot')

def hs_get_contact():
    req=urllib.request.Request(
        f'https://api.hubapi.com/crm/v3/objects/contacts/{CID}?properties={",".join(PROPS)}',
        headers={'Authorization':'Bearer '+token()}, method='GET')
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())

def lead_for():
    c=hs_get_contact(); props=c.get('properties') or {}
    phone = props.get('hs_searchable_calculated_phone_number') or props.get('hs_whatsapp_phone_number') or props.get('phone') or ''
    return {
        'id': c.get('id'),
        'email': EMAIL,
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
        'manual_override_reason': 'Rafael orientou converter após o lead responder "Legal" à explicação de portal B2B para restaurantes; seguir com consultor, diagnóstico, agenda e follow-up.',
        # Antigo Não-MQL em conversa no chip Rafael: manter o mesmo comunicador se o script for reusado.
        'force_bridge_port': 4607,
    }

def main():
    # Reclassifica o registro de pesquisa anterior de não-MQL para MQL manual, sem alterar regra geral do crivo.
    p.RESEARCH[EMAIL] = {
        'slug': 'schutzmann-maximilian-cordioli',
        'mql': True,
        'empresa_real': 'Schutzmann / Maximilian Cordioli — lead reaberto manualmente por Rafael após conversa WhatsApp sobre portal B2B para operação que vende para restaurantes.',
        'dominio_site': 'schutzmann.com.br — histórico público anterior apontava serviços/consultoria; o override atual é comercial/manual, baseado na conversa e na hipótese operacional validada por Rafael.',
        'redes': 'Reclassificação manual Rafael 2026-06-29. Conversa WhatsApp: foi mostrado portal de referência e explicado login, catálogo, tabela comercial, condição e pedido direto; lead respondeu "Legal".',
        'segmento': 'Operação em validação comercial para venda/atendimento B2B a restaurantes, com ERP Bling informado no formulário e uso potencial de portal com login, catálogo, tabela comercial e condição por cliente.',
        'motivo': 'Override manual Rafael: tratar como MQL para apresentação consultiva. O lead demonstrou aderência mínima na conversa; seguir com diagnóstico e consultor, sem enviar proposta direta antes da demonstração.',
        'insight': 'restaurantes acessarem um portal com login para consultar catálogo, tabela comercial e condição, montando pedidos sem depender de atendimento manual',
        'telefone_publico': 'Telefone do HubSpot e conversa WhatsApp: +55 11 98183-9853.',
        'whatsapp_publico': 'Usar o mesmo WhatsApp já em conversa: +55 11 98183-9853.',
    }
    # Respiros curtos para este override pontual, porque Rafael pediu já colocar agenda; mantém ordem segura.
    p.TEXT_TO_PDF_DELAY_SECONDS = 60
    p.PDF_TO_QUESTION_DELAY_SECONDS = 30
    p.QUESTION_TO_AGENDA_DELAY_SECONDS = 180
    payload={
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'count': 1,
        'cutoff_window_h': 24,
        'manual_reclassification': True,
        'leads': [lead_for()],
        'duplicates': [],
    }
    Path('/tmp/gate_qualified.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print('gate manual escrito:', EMAIL, flush=True)
    p.main()

if __name__ == '__main__':
    main()
