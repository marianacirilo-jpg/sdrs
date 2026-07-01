#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Override explícito Rafael 2026-06-30: Solút.io / Jordi Guerra deve virar MQL e receber diagnóstico."""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p  # noqa: E402

EMAIL = 'jordi.guerra@sempreceub.com'
CID = '232268719360'
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
    phone = props.get('hs_searchable_calculated_phone_number') or props.get('hs_whatsapp_phone_number') or props.get('phone') or '556199490420'
    return {
        'id': c.get('id') or CID,
        'email': EMAIL,
        'firstname': props.get('firstname') or 'Jord',
        'lastname': props.get('lastname') or '',
        'company': props.get('company') or 'Solút.io',
        'phone': phone,
        'phone_valid': bool(p.phone_variants_with_optional_9(phone)),
        'phone_invalid_reason': '' if p.phone_variants_with_optional_9(phone) else 'sem telefone BR normalizável',
        'createdate': props.get('createdate') or '',
        'gate_trigger': 'manual_hubspot_mql',
        'hs_lastmodifieddate': props.get('lastmodifieddate') or '',
        'properties': props,
        'manual_override_by': 'Rafael Calixto',
        'manual_override_reason': 'Rafael autorizou explicitamente em 30/06/2026 marcar Solút.io/Jordi como MQL e disparar diagnóstico, apesar do fail-closed automático anterior.',
    }

def main():
    p.RESEARCH[EMAIL] = {
        'slug': 'solut-io-jord-guerra',
        'mql': True,
        'empresa_real': 'Solút.io — lead convertido manualmente por Rafael para diagnóstico consultivo. O formulário indica intenção de digitalização, ERP Omie, loja virtual e dor de integração com ERP.',
        'dominio_site': 'solut.io respondeu com página mínima no ciclo automático; sempreceub.com não resolveu. A decisão MQL aqui é override manual do Rafael, não alteração geral do crivo.',
        'redes': 'Reclassificação manual Rafael 2026-06-30 após revisão no Discord. Pesquisa automática anterior não comprovou operação B2B pública, por isso o fluxo fica registrado como exceção auditável.',
        'segmento': 'Operação em validação comercial com intenção de ecommerce/loja virtual, ERP Omie, equipe de 51 a 150 pessoas e 2 a 5 vendedores internos; hipótese de aderência para diagnosticar digitalização B2B e integração comercial.',
        'motivo': 'Override manual Rafael: marcar como MQL e disparar diagnóstico. Há sinais de intenção digital no formulário: ERP Omie, loja virtual, dor de integração ERP cara/complicada e crença de compra autônoma 24h; seguir diagnóstico consultivo sem transformar este caso em regra geral do crivo.',
        'insight': 'avaliar como clientes poderiam acessar um portal com login, catálogo, tabela comercial e condição para comprar com mais autonomia, reduzindo dependência de integração manual e atendimento vendedor a vendedor',
        'telefone_publico': 'Telefone do HubSpot/formulário: +55 61 99490-420.',
        'whatsapp_publico': 'Usar telefone informado no formulário/HubSpot: +55 61 99490-420.',
    }
    # Para concluir a solicitação agora, mantém cadência aprovada do diagnóstico até pergunta;
    # agenda fica na fila posterior idempotente do processo principal.
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
