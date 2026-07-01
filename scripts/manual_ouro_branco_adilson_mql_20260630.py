#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Override explícito Rafael 2026-06-30: Ouro Branco / Adilson preencheu 2+ vezes; marcar MQL e disparar diagnóstico."""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p  # noqa: E402

EMAIL = 'adilson@ourobrancoatacado.com.br'
CID = '134311197299'
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
    for k in ('HUBSPOT_API_KEY','HUBSPOT_TOKEN','HUBSPOT_PRIVATE_APP_TOKEN','HUBSPOT_ACCESS_TOKEN'):
        if os.environ.get(k):
            return os.environ[k]
    env = Path('/root/.hermes/credentials/hubspot.env')
    for line in env.read_text().splitlines():
        if '=' not in line or line.strip().startswith('#'):
            continue
        k, v = line.split('=', 1)
        k = k.strip(); v = v.strip().strip('"\'')
        if k in ('HUBSPOT_API_KEY','HUBSPOT_TOKEN','HUBSPOT_PRIVATE_APP_TOKEN','HUBSPOT_ACCESS_TOKEN'):
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
    phone = props.get('hs_searchable_calculated_phone_number') or props.get('hs_whatsapp_phone_number') or props.get('phone') or '33988366966'
    return {
        'id': c.get('id') or CID,
        'email': EMAIL,
        'firstname': props.get('firstname') or 'Adilson',
        'lastname': props.get('lastname') or '',
        'company': props.get('company') or 'Ouro Branco Soluções Tecnológicas',
        'phone': phone,
        'phone_valid': bool(p.phone_variants_with_optional_9(phone)),
        'phone_invalid_reason': '' if p.phone_variants_with_optional_9(phone) else 'sem telefone BR normalizável',
        'createdate': props.get('createdate') or '',
        'gate_trigger': 'manual_hubspot_mql',
        'hs_lastmodifieddate': props.get('lastmodifieddate') or '',
        'properties': props,
        'manual_override_by': 'Rafael Calixto',
        'manual_override_reason': 'Rafael orientou em 30/06/2026 marcar como MQL porque o lead preencheu o formulário mais de uma vez; tratar como exceção auditável e disparar diagnóstico.',
    }

def main():
    p.RESEARCH[EMAIL] = {
        'slug': 'ouro-branco-solucoes-tecnologicas-adilson',
        'mql': True,
        'empresa_real': 'Ouro Branco Soluções Tecnológicas — lead de Facebook com múltiplas conversões/formulários e domínio ourobrancoatacado.com.br. Reclassificado manualmente por Rafael para diagnóstico consultivo.',
        'dominio_site': 'ourobrancoatacado.com.br — não validou publicamente no ciclo automático por timeout; decisão MQL é override manual do Rafael por recorrência de preenchimento e intenção comercial.',
        'redes': 'Reclassificação manual Rafael 2026-06-30: o lead preencheu mais de uma vez. Pesquisa automática anterior não comprovou atacado/distribuição, então registrar como exceção auditável e não alterar a regra geral do crivo.',
        'segmento': 'Instaladores/integradores de segurança com potencial de venda B2B/atacado tecnológico a ser diagnosticado; formulário informa WhatsApp/ligação, 2 a 5 vendedores, dor de escalar sem contratar mais gente e interesse recorrente por formulário.',
        'motivo': 'Override manual Rafael: marcar como MQL porque houve reentrada/múltiplos preenchimentos e o lead já está em lifecycle MQL no HubSpot. Apesar do fail-closed automático anterior, seguir diagnóstico consultivo para entender se há operação B2B/atacado real por trás do domínio ourobrancoatacado.com.br.',
        'insight': 'entender se existe venda recorrente de equipamentos/soluções de segurança para clientes empresas, integradores ou revendas, e se um portal com login, catálogo, tabela comercial e pedido direto reduziria atendimento por WhatsApp/ligação',
        'telefone_publico': 'Telefone do HubSpot/formulário: +55 33 98836-6966.',
        'whatsapp_publico': 'Usar telefone informado no formulário/HubSpot: +55 33 98836-6966.',
    }
    p.TEXT_TO_PDF_DELAY_SECONDS = 60
    p.PDF_TO_QUESTION_DELAY_SECONDS = 30
    payload = {
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
