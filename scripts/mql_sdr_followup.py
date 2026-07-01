#!/usr/bin/env python3
"""Follow-up 1 SDR para leads MQL que já receberam diagnóstico/PDF.

Consulta o ledger compartilhado controle/wpp_envios.json, encontra envios diretos
`status=enviado_lead` cujo owner é Sarah/Breno/Lucas Batista e envia o Follow-up 1
oficial. Não existe "follow-up manual" pós-diagnóstico: depois do diagnóstico o
próximo contato é sempre a régua determinística Follow-up 1, no mesmo dia ou no
dia posterior, com estudo do negócio e ponte para portal real coerente.

Seguro por padrão:
- não envia para grupo;
- não duplica se já houver follow-up 1 MQL para o mesmo deal/telefone;
- não envia pergunta genérica pós-diagnóstico;
- se o lead respondeu ao diagnóstico, não envia follow-up automático; cria tarefa e só move para Retorno Contato se o negócio ainda estiver em etapa inicial (nunca regredir Introdução+);
- respeita limite por execução, por hora e por dia.
"""
import argparse
import importlib.util
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path('/root/.hermes/zydon-prospeccao')
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DISPARO = ROOT / 'disparo_dinamico.py'
WA_DATA = Path('/root/.hermes/whatsapp-extra/channel_data')

spec = importlib.util.spec_from_file_location('disparo_dinamico', str(DISPARO))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

CADENCIA = ROOT / 'scripts' / 'cadencia_primeiro_contato.py'
spec_cad = importlib.util.spec_from_file_location('cadencia_primeiro_contato', str(CADENCIA))
cad = importlib.util.module_from_spec(spec_cad)
spec_cad.loader.exec_module(cad)

BRT = timezone(timedelta(hours=-3))
OWNER_TO_KEY = {v['owner_id']: k for k, v in d.BRIDGES.items()}
OWNER_TO_NAME = {v['owner_id']: v['owner_name'] for v in d.BRIDGES.values()}
MSG_TYPE = 'mql_followup1_deterministico'
LEGACY_MSG_TYPES = {'mql_sdr_followup', MSG_TYPE}
DIRECT_STATUSES = {'enviado_lead', 'enviado_mql'}
STAGE_PRIMEIRO_CONTATO_FEITO = '1214320997'  # Pipeline Principal: Primeiro Contato
STAGE_RETORNO_CONTATO = '998099482'  # Lead respondeu depois do diagnóstico
# Rafael 30/06: nunca regredir lead em Introdução ou etapa superior para Retorno.
PROTECTED_STAGE_ORDER = {
    '1269308723': 6,  # Introdução
    '1269710168': 7,  # Diagnóstico EC
    '990617426': 8,   # Apresentação Comercial
    '1269308724': 9,  # Apresentação Técnica
    '984052831': 10,  # Proposta / Negociação
    '1213797817': 11, # Termos e condições
    '984052834': 12,  # Fechado
    '984052835': 13,  # Perdido
}


def parse_dt(raw):
    if not raw:
        return None
    s = str(raw).strip()
    try:
        if s.endswith('Z'):
            return datetime.fromisoformat(s[:-1] + '+00:00')
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=BRT)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(s[:19], fmt).replace(tzinfo=BRT).astimezone(timezone.utc)
        except Exception:
            pass
    return None


def phone_key(value):
    return d.normalize_phone(str(value or '').replace('@c.us', '@s.whatsapp.net'))


def jid_variants(jid_or_phone):
    p = phone_key(jid_or_phone)
    if not p:
        return set()
    return {p, '55'+p, f'55{p}@s.whatsapp.net', f'55{p}@c.us'}


def message_text(m):
    for key in ('text', 'body', 'message', 'caption', 'content'):
        val = m.get(key)
        if isinstance(val, str) and val.strip():
            return re.sub(r'\s+', ' ', val).strip()
    msg = m.get('message')
    if isinstance(msg, dict):
        for key in ('conversation', 'extendedTextMessage'):
            val = msg.get(key)
            if isinstance(val, str) and val.strip():
                return re.sub(r'\s+', ' ', val).strip()
            if isinstance(val, dict):
                t = val.get('text')
                if isinstance(t, str) and t.strip():
                    return re.sub(r'\s+', ' ', t).strip()
    return ''


WEAK_RESPONSES = {'oi','olá','ola','bom dia','boa tarde','boa noite','ok','okk','obrigado','obrigada','sim','whatsapp','wpp','zap'}
EFFECTIVE_TERMS = (
    'faz sentido','quanto custa','preço','preco','valor','plano','ligar','ligação','ligacao',
    'agenda','agendar','reunião','reuniao','demonstração','demonstracao','proposta',
    'erp','bling','omie','tiny','sankhya','portal','pedido','vendedor','cliente','tabela',
    'restaurante','revenda','distribuidor','atacado','pode falar','contato dele','contato dela'
)


def is_effective_interaction_text(text):
    """Só evolui para Retorno Contato quando há interação efetiva com a cadência inicial."""
    low = re.sub(r'\s+', ' ', (text or '').lower()).strip()
    cleaned = re.sub(r'[^a-z0-9áàâãéêíóôõúç ]+', '', low).strip()
    if not cleaned:
        return False
    if cleaned in WEAK_RESPONSES or len(cleaned.split()) <= 2:
        return any(t in low for t in EFFECTIVE_TERMS)
    return True


def incoming_messages_after(jid, after_dt):
    """Mensagens do lead depois do diagnóstico.

    Rafael: se o lead respondeu o diagnóstico, o SDR deve priorizar o
    follow-up na primeira hora útil, totalmente contextualizado ao que foi dito.
    """
    if not jid or not after_dt or not WA_DATA.exists():
        return []
    vars_ = jid_variants(jid)
    out = []
    for path in WA_DATA.glob('history_*.json'):
        try:
            rows = json.loads(path.read_text())
        except Exception:
            continue
        if not isinstance(rows, list):
            continue
        for m in rows:
            if not isinstance(m, dict) or m.get('fromMe'):
                continue
            chat = str(m.get('chat') or m.get('remoteJid') or '')
            if not any(v and v in chat for v in vars_):
                continue
            dt = parse_dt(m.get('timestamp'))
            text = message_text(m)
            if dt and dt > after_dt and is_effective_interaction_text(text):
                out.append({'dt': dt, 'text': text, 'source': path.name})
    out.sort(key=lambda x: x['dt'])
    return out


def incoming_after(jid, after_dt):
    return bool(incoming_messages_after(jid, after_dt))


def first_name(rec):
    for key in ('nome', 'contato', 'firstname'):
        val = str(rec.get(key) or '').strip()
        if val and val.lower() not in ('contato', 'lead', 'cliente'):
            return val.split()[0].capitalize()
    txt = str(rec.get('text') or '')
    m = re.search(r'(?:Boa tarde|Bom dia|Boa noite|Oi|Olá),\s*([^,!.\n]+)', txt, re.I)
    if m:
        return m.group(1).strip().split()[0].capitalize()
    return 'tudo bem'


def company(rec):
    for key in ('empresa', 'dealname'):
        val = str(rec.get(key) or '').strip()
        if val:
            return val
    summary = str(rec.get('group_summary') or '')
    m = re.search(r'Empresa:\s*(.+)', summary)
    if m:
        return m.group(1).strip()
    slug = str(rec.get('slug') or '').replace('-', ' ').strip()
    return slug.title() if slug else 'sua empresa'


def study_context(rec):
    """Extrai o estudo usado no Follow-up 1.

    Não pode virar uma pergunta genérica. Se o diagnóstico já foi enviado, a
    primeira mensagem seguinte precisa mostrar que a operação foi entendida.
    """
    blobs = [
        str(rec.get('research_basis') or ''),
        str(rec.get('group_summary') or ''),
        str(rec.get('text') or ''),
        str(rec.get('question_text') or ''),
        str(rec.get('agenda_text') or ''),
    ]
    text = '\n'.join(b for b in blobs if b)
    summary = str(rec.get('group_summary') or '')
    if re.search(r'sorveterias|açaiterias|acaiterias|açaí|acai|sorvete', text, re.I) and re.search(r'WhatsApp|telefone|planilha', text, re.I):
        return 'vocês vendem para sorveterias, açaiterias e operações de delivery de açaí/sorvete, e o gargalo aparece quando pedido chega por WhatsApp, telefone e planilha'
    for pattern in (
        r'• Oportunidade:\s*(.+)',
        r'• Dor[^\n]*(pedidos.+)',
        r'• Dor[^\n]*:\s*(.+)',
        r'• Formulário[^\n]*:\s*(.+)',
        r'• Perfil aderente:\s*(.+)',
        r'• Empresa validada:\s*(.+)',
        r'•\s*(.+?(?:WhatsApp|telefone|planilha|catálogo|catalogo|pedido|pedidos|reposição|reposicao|atacado|distribui|sorveterias|açaiterias).*)',
    ):
        m = re.search(pattern, summary, re.I)
        if m:
            val = re.sub(r'\s+', ' ', m.group(1)).strip(' .')
            if len(val) >= 25:
                return val[:260]
    if re.search(r'sorveterias|açaiterias|acaiterias|açaí|acai|sorvete', text, re.I):
        return 'vocês vendem para sorveterias, açaiterias e operações de delivery de açaí/sorvete, e o gargalo aparece quando pedido chega por WhatsApp, telefone e planilha'
    if re.search(r'cosm[eé]tico|beleza|perfumaria|est[eé]tica', text, re.I):
        return 'vocês trabalham com produtos de beleza/cosméticos e podem organizar catálogo, tabela comercial e recompras B2B em um portal próprio'
    if re.search(r't[eê]xtil|confec|moda|roupa|vestu[aá]rio', text, re.I):
        return 'vocês trabalham com linha de produtos têxteis/moda e podem organizar catálogo, grade, tabela comercial e reposição em um portal B2B'
    if re.search(r'autope[cç]as|pe[çc]as|oficina|frota|mec[aâ]nic', text, re.I):
        return 'vocês têm uma operação de peças/produtos recorrentes em que o cliente precisa consultar catálogo, preço e disponibilidade antes de pedir'
    if re.search(r'distribui|atacad|revenda|lojista|representante|vendedor', text, re.I):
        return 'vocês têm venda B2B recorrente e o cliente precisa consultar catálogo, tabela comercial, preço e disponibilidade antes de tirar pedido'
    return ''


def portal_for_context(rec):
    text = ' '.join(str(rec.get(k) or '') for k in ('research_basis', 'group_summary', 'text', 'empresa', 'slug'))
    norm = text.lower()
    if re.search(r'sorveterias|açaiterias|acaiterias|açaí|acai|sorvete|alimento|foodservice|delivery', norm):
        return {'name': 'Ceasa Mais', 'url': 'https://portal.ceasamais.com.br/', 'buyer_context': 'Esse cliente vende para mercados, padarias, restaurantes e compradores de food service.'}
    if re.search(r'artigos esportivos|esportivo|esporte|roupa esportiva|moda fitness|confec|vestu[aá]rio|t[eê]xtil', norm):
        if re.search(r'esport|fitness', norm):
            return {'name': 'Bullpadel B2B', 'url': 'https://b2b.bullpadelbr.com/', 'buyer_context': 'Esse cliente vende para lojas, academias e pontos ligados a artigos esportivos.'}
        return {'name': 'Fiação Itabaiana', 'url': 'https://compreonline.fiacaoitabaiana.com.br/', 'buyer_context': 'Esse cliente vende para confecções, lojistas e compradores do setor têxtil.'}
    if re.search(r'cosm[eé]tico|beleza|perfumaria|est[eé]tica|dermo', norm):
        return {'name': 'Provanza', 'url': 'https://lojista.provanza.com.br/', 'buyer_context': 'Esse cliente vende para revendas, salões e lojistas de beleza.'}
    if re.search(r'pet|veterin|ração|racao|agropecu', norm):
        return {'name': 'Mouragro', 'url': 'https://loja.mouragro.com.br/', 'buyer_context': 'Esse cliente vende para pet shops, clínicas veterinárias e compradores do agro/pet.'}
    if re.search(r'autope[cç]as|mec[aâ]nic|oficina|frota|automot', norm):
        return {'name': 'Siga Importados', 'url': 'https://siga.knakasaki.com/', 'buyer_context': 'Esse cliente vende para oficinas, auto centers e compradores de reposição automotiva.'}
    if re.search(r'constru|material|home center|acabamento|obra|decor', norm):
        return {'name': 'Stoky Distribuidora', 'url': 'https://stoky.com.br/', 'buyer_context': 'Esse cliente vende para lojistas, revendas e compradores recorrentes do atacado.'}
    return {'name': 'Stoky Distribuidora', 'url': 'https://stoky.com.br/', 'buyer_context': 'Esse cliente vende para lojistas, revendas e compradores recorrentes do atacado.'}


FOLLOWUP1_MSG_TYPE = 'mql_followup1_deterministico'
MIN_HOURS_AFTER_DIAG_FOR_SDR_FOLLOW = 3.0


def compose(rec, sender_name):
    """Renderiza o Follow-up 1 oficial aprovado por Rafael.

    Não cria copy nova. Só substitui variáveis permitidas no manifesto F1:
    nome, empresa, portal_segmento, portal_url e portal_buyer_context.
    """
    portal = portal_for_context(rec)
    lead = {
        'nome': first_name(rec),
        'empresa': company(rec),
        'deal_id': rec.get('deal_id') or rec.get('dealId') or '',
        'jid': rec.get('to') or '',
    }
    old_portal_example_for = cad.portal_example_for
    try:
        cad.portal_example_for = lambda _lead: portal
        text = cad.extract_message_variation(lead, 1)
        gate_ok, gate_reason = cad.approved_followup_template_gate(text, 1, lead)
        if not gate_ok:
            raise RuntimeError(f'Follow 1 aprovado bloqueado: {gate_reason}')
        return text
    finally:
        cad.portal_example_for = old_portal_example_for


def find_contact_by_email(email):
    if not email:
        return None
    body = {
        'filterGroups': [{'filters': [{'propertyName': 'email', 'operator': 'EQ', 'value': email}]}],
        'properties': ['firstname', 'email'],
        'limit': 1,
    }
    res = d.hs_request('https://api.hubapi.com/crm/v3/objects/contacts/search', 'POST', body)
    rows = (res or {}).get('results') or []
    return rows[0] if rows else None


def deals_for_contact(contact_id):
    res = d.hs_request(f'https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}/associations/deals')
    return [str(x.get('id')) for x in (res or {}).get('results', []) if x.get('id')]


def deal_owner(deal_id):
    res = d.hs_request(f'https://api.hubapi.com/crm/v3/objects/deals/{deal_id}?properties=hubspot_owner_id,createdate,dealname')
    return ((res or {}).get('properties') or {}).get('hubspot_owner_id') or ''


def deal_stage(deal_id):
    if not deal_id:
        return ''
    res = d.hs_request(f'https://api.hubapi.com/crm/v3/objects/deals/{deal_id}?properties=dealstage')
    return str(((res or {}).get('properties') or {}).get('dealstage') or '')


def is_protected_stage(stage):
    return str(stage or '') in PROTECTED_STAGE_ORDER


def move_deal_stage(deal_id, stage):
    if not deal_id:
        return None
    current = deal_stage(deal_id)
    if is_protected_stage(current) and stage in {STAGE_RETORNO_CONTATO, STAGE_PRIMEIRO_CONTATO_FEITO}:
        return f'protected_stage_skip:{current}'
    res = d.hs_request(
        f'https://api.hubapi.com/crm/v3/objects/deals/{deal_id}',
        'PATCH',
        {'properties': {'dealstage': stage}},
    )
    return ((res or {}).get('properties') or {}).get('dealstage')


def move_deal_to_primeiro_contato_feito(deal_id):
    """Após follow-up SDR confirmado, move o negócio para a coluna
    Primeiro Contato ("primeiro contato feito" no processo do Rafael).
    """
    return move_deal_stage(deal_id, STAGE_PRIMEIRO_CONTATO_FEITO)


def resolve_hubspot_ids(rec):
    contact_id = rec.get('contact_id') or rec.get('contactId')
    deal_id = rec.get('deal_id') or rec.get('dealId')
    if not contact_id:
        c = find_contact_by_email(rec.get('email'))
        if c:
            contact_id = str(c.get('id'))
    if contact_id and not deal_id:
        deals = deals_for_contact(contact_id)
        preferred = None
        for did in deals:
            if str(deal_owner(did)) == str(rec.get('owner_id') or ''):
                preferred = did
                break
        deal_id = preferred or (deals[0] if deals else None)
    return contact_id, deal_id


def next_sdr_sla_due(interaction_dt):
    """Rafael 29/06: resposta efetiva sem agenda vira Retorno Contato com SLA por período útil.

    Interação pela manhã => tarefa 14h do mesmo dia.
    Interação pela tarde/noite => tarefa 9h do próximo dia útil.
    """
    dt = interaction_dt or datetime.now(timezone.utc)
    brt = dt.astimezone(BRT)
    if brt.hour < 12:
        due_brt = brt.replace(hour=14, minute=0, second=0, microsecond=0)
    else:
        due_brt = (brt + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        while due_brt.weekday() >= 5:
            due_brt += timedelta(days=1)
    return due_brt.astimezone(timezone.utc)


def create_return_task(rec, incoming, stage_resp=None):
    contact_id, deal_id = resolve_hubspot_ids(rec)
    if not deal_id or not contact_id:
        return None
    interaction_dt = None
    try:
        if incoming:
            interaction_dt = incoming[-1].get('dt')
    except Exception:
        interaction_dt = None
    due_dt = next_sdr_sla_due(interaction_dt)
    texts = []
    for m in (incoming or [])[-3:]:
        txt = (m.get('text') or '').strip()
        if txt:
            texts.append(re.sub(r'\s+', ' ', txt)[:500])
    resumo = ' | '.join(texts) if texts else 'Lead respondeu/interagiu no WhatsApp; abrir conversa antes de seguir.'
    current_stage = deal_stage(deal_id)
    if is_protected_stage(current_stage):
        # Rafael 30/06: fora das primeiras 6 etapas não criar atividade nem regredir.
        return None
    stage_note = 'Se o negócio ainda estiver em etapa inicial, pode ser movido para Retorno Contato; SDR precisa assumir.'
    body_txt = [
        'Lead interagiu de forma efetiva com as informações enviadas na cadência inicial. Não enviar follow-up automático por cima.',
        stage_note,
        f"Lead: {first_name(rec)} / {company(rec)}",
        f"Destino: {rec.get('to')}",
        f"Deal: {deal_id}",
        f"Contato: {contact_id}",
        f"SLA SDR: tarefa aberta para {due_dt.astimezone(BRT).strftime('%d/%m/%Y %H:%M BRT')}",
        '',
        'Resposta(s) capturada(s):',
        resumo,
        '',
        'Próxima ação SDR: abrir o histórico, considerar todo o contexto do que foi falado e conduzir para agenda se fizer sentido. Não mandar follow-up automático por cima.'
    ]
    body = {
        'properties': {
            'hs_timestamp': due_dt.isoformat().replace('+00:00', 'Z'),
            'hs_task_subject': 'Entrar em contato — lead interagiu com a cadência inicial',
            'hs_task_body': '\n'.join(body_txt),
            'hs_task_status': 'NOT_STARTED',
            'hs_task_priority': 'HIGH',
            'hubspot_owner_id': str(rec.get('owner_id') or ''),
        },
        'associations': [
            {'to': {'id': int(contact_id)}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 204}]},
            {'to': {'id': int(deal_id)}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 216}]},
        ],
    }
    res = d.hs_request('https://api.hubapi.com/crm/v3/objects/tasks', 'POST', body)
    return res.get('id') if res else None


def create_task(rec, text, sender, send_resp):
    contact_id, deal_id = resolve_hubspot_ids(rec)
    if not deal_id or not contact_id:
        return None
    current_stage = deal_stage(deal_id)
    if is_protected_stage(current_stage):
        # Rafael 30/06: atividades automáticas só nas primeiras 6 etapas.
        return None
    body_txt = [
        'Follow-up 1 SDR após diagnóstico MQL enviado ao lead.',
        f"Lead: {first_name(rec)} / {company(rec)}",
        f"Destino: {rec.get('to')}",
        f"Deal: {deal_id}",
        f"Contato: {contact_id}",
        f"Remetente: {sender.get('sender_name')} (porta {sender.get('port')})",
        f"Resposta bridge: {json.dumps(send_resp, ensure_ascii=False)[:1000]}",
        '',
        'Texto enviado:',
        text,
    ]
    body = {
        'properties': {
            'hs_timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'hs_task_subject': f"WhatsApp — Follow-up 1 diagnóstico MQL enviado por {sender.get('sender_name')}",
            'hs_task_body': '\n'.join(body_txt),
            'hs_task_status': 'COMPLETED',
            'hs_task_priority': 'MEDIUM',
            'hubspot_owner_id': str(rec.get('owner_id') or sender.get('owner_id') or ''),
        },
        'associations': [
            {'to': {'id': int(contact_id)}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 204}]},
            {'to': {'id': int(deal_id)}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 216}]},
        ],
    }
    res = d.hs_request('https://api.hubapi.com/crm/v3/objects/tasks', 'POST', body)
    return res.get('id') if res else None


def outgoing_messages_after(jid, after_dt):
    """Fail-safe anti-duplicidade: se já existe qualquer mensagem nossa no
    histórico real depois do diagnóstico, não mandar Follow 1 de novo mesmo que
    o ledger não tenha sido gravado. Incidente 30/06: wrapper matou o processo
    após a primeira bolha e repetiu saudação porque o ledger só era escrito no
    fim da sequência.
    """
    if not after_dt:
        return []
    vars_ = jid_variants(jid)
    out = []
    for path in WA_DATA.glob('history_*.json'):
        try:
            rows = json.loads(path.read_text())
        except Exception:
            continue
        if not isinstance(rows, list):
            continue
        for m in rows:
            if not isinstance(m, dict) or m.get('fromMe') is not True:
                continue
            vals = [m.get('chat'), m.get('sender'), m.get('participant'), m.get('jid'), m.get('remoteJidAlt'), m.get('jidAlt')]
            raw = m.get('rawKey') or {}
            if isinstance(raw, dict):
                vals += [raw.get('remoteJid'), raw.get('remoteJidAlt'), raw.get('participant')]
            if not any(phone_key(str(v or '')) in vars_ or str(v or '') in vars_ for v in vals):
                continue
            ts = m.get('timestamp') or m.get('messageTimestamp') or 0
            try:
                ts = float(ts)
                if ts > 10**12:
                    ts /= 1000
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            except Exception:
                continue
            if dt > after_dt + timedelta(seconds=30):
                out.append(m)
    return out


def already_followed(envios, rec):
    did = str(rec.get('deal_id') or rec.get('dealId') or '')
    pk = phone_key(rec.get('to'))
    for r in envios:
        if not isinstance(r, dict):
            continue
        if str(r.get('msg_type') or '').lower() not in LEGACY_MSG_TYPES:
            continue
        if did and str(r.get('deal_id') or r.get('dealId') or '') == did:
            return True
        if pk and phone_key(r.get('to')) == pk:
            return True
    source_dt = parse_dt(rec.get('date_tz') or rec.get('date'))
    if pk and source_dt and outgoing_messages_after(rec.get('to'), source_dt):
        return True
    return False


def sent_count(envios, owner_name, hours=None, today_only=False):
    """Conta follows MQL enviados por SDR em janela segura.

    `hours` protege o limite horário. Para limite diário, usar
    `today_only=True`; contar o histórico inteiro travava a escala depois que o
    SDR acumulava 12 envios em vários dias.
    """
    now = datetime.now(timezone.utc)
    today_brt = now.astimezone(BRT).date()
    n = 0
    for r in envios:
        if not isinstance(r, dict):
            continue
        if str(r.get('msg_type') or '').lower() not in LEGACY_MSG_TYPES:
            continue
        if str(r.get('sdr') or '') != owner_name:
            continue
        dt = parse_dt(r.get('date_tz') or r.get('date'))
        if not dt:
            continue
        if today_only and dt.astimezone(BRT).date() != today_brt:
            continue
        if hours is None or (now - dt).total_seconds() <= hours * 3600:
            n += 1
    return n


def collect(envios, max_age_hours):
    now = datetime.now(timezone.utc)
    out = []
    for rec in envios:
        if not isinstance(rec, dict):
            continue
        if str(rec.get('campaign_id') or '') == 'diagnostico_agendado' or str(rec.get('msg_type') or '').lower().startswith('diagnostico_agenda'):
            # Confirmação/lembrete de agenda não é diagnóstico comercial e resposta a isso
            # NÃO pode mover negócio de Diagnóstico SDR para Retorno Contato.
            continue
        if str(rec.get('status') or '').lower() not in DIRECT_STATUSES:
            continue
        if str(rec.get('to') or '').endswith('@g.us'):
            continue
        owner_id = str(rec.get('owner_id') or '')
        if owner_id not in OWNER_TO_KEY:
            continue
        if not rec.get('to') or not phone_key(rec.get('to')):
            continue
        if already_followed(envios, rec):
            continue
        dt = parse_dt(rec.get('date_tz') or rec.get('date'))
        if not dt:
            continue
        incoming = incoming_messages_after(rec.get('to'), dt)
        incoming_last_dt = incoming[-1]['dt'] if incoming else None
        incoming_age_h = (now - incoming_last_dt).total_seconds() / 3600 if incoming_last_dt else None
        age_h = (now - dt).total_seconds() / 3600
        # Follow-up automático só para lead sem resposta e com respiro mínimo desde
        # o diagnóstico. Se respondeu ao diagnóstico, não mandar nova
        # automação: mover para Retorno Contato e deixar SDR humano continuar.
        # Incidente King Talhas 26/06.
        if age_h < MIN_HOURS_AFTER_DIAG_FOR_SDR_FOLLOW:
            continue
        if age_h > max_age_hours and not incoming:
            continue
        rec['_dt'] = dt
        rec['_age_h'] = age_h
        rec['_incoming_after'] = incoming
        rec['_incoming_last_dt'] = incoming_last_dt
        rec['_incoming_age_h'] = incoming_age_h
        rec['_priority_bucket'] = 0 if incoming else 1
        out.append(rec)
    out.sort(key=lambda r: (r.get('_priority_bucket', 1), r.get('_incoming_last_dt') or r['_dt']))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=3)
    ap.add_argument('--max-age-hours', type=float, default=8)
    ap.add_argument('--max-per-hour', type=int, default=2)
    ap.add_argument('--max-per-day', type=int, default=12)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--owner', choices=['all','breno','sarah','lucas'], default='all')
    args = ap.parse_args()

    envios = d.load_envios()
    candidates = collect(envios, args.max_age_hours)
    if args.owner != 'all':
        oid = d.BRIDGES[args.owner]['owner_id']
        candidates = [c for c in candidates if str(c.get('owner_id')) == oid]

    print(f"MQL SDR follow-up — candidatos={len(candidates)} limit={args.limit} dry_run={args.dry_run}")
    sent = 0
    for rec in candidates:
        if sent >= args.limit:
            break
        owner_id = str(rec.get('owner_id'))
        owner_key = OWNER_TO_KEY[owner_id]
        bridge = d.BRIDGES[owner_key]
        owner_name = bridge['owner_name']
        if rec.get('_incoming_after'):
            resolved_contact_id, resolved_deal_id = resolve_hubspot_ids(rec)
            last = rec.get('_incoming_after')[-1]
            if args.dry_run:
                print(f"DRY SKIP respondeu diagnóstico -> Retorno Contato: {company(rec)} deal={resolved_deal_id} resp={(last.get('text') or '')[:120]}")
                continue
            moved_stage = move_deal_stage(resolved_deal_id, STAGE_RETORNO_CONTATO)
            task_id = create_return_task(rec, rec.get('_incoming_after') or [])
            print(f"SKIP respondeu diagnóstico -> Retorno Contato: {company(rec)} deal={resolved_deal_id} stage={moved_stage} task={task_id} resp={(last.get('text') or '')[:120]}")
            continue
        if sent_count(envios, owner_name, 1) >= args.max_per_hour:
            print(f"SKIP {owner_name}: limite horário follow-up")
            continue
        if sent_count(envios, owner_name, None, today_only=True) >= args.max_per_day:
            print(f"SKIP {owner_name}: limite diário follow-up")
            continue
        port, status, errs = d.escolher_porta_online(bridge, envios)
        if not port:
            print(f"ERRO {owner_name}: sem bridge online {errs}")
            continue
        sender_phone = ''
        sender_label = owner_name
        try:
            with urllib.request.urlopen(urllib.request.Request(f'http://localhost:{port}/me'), timeout=5) as resp:
                me = json.loads(resp.read().decode())
            sender_phone = str(me.get('phone') or me.get('id') or '')
            sender_label = str(me.get('name') or owner_name)
        except Exception:
            pass
        text = compose(rec, owner_name)
        marker = 'RESPONDEU_DIAG ' if rec.get('_incoming_after') else ''
        print(f"SEND {marker}{owner_name}/porta {port} -> {company(rec)} {rec.get('to')} | {text[:120].replace(chr(10),' ')}")
        if args.dry_run:
            sent += 1
            continue
        ok, resp = d.send_whatsapp_sequence(
            port,
            rec.get('to'),
            text,
            final_pause_seconds=240.0,
            max_parts=3,
            delay_schedule=[12.0, 240.0],
        )
        if not ok:
            print(f"FALHA {company(rec)}: {resp}")
            continue
        sender = {'sender_name': sender_label, 'sender_phone': sender_phone, 'port': port, 'owner_id': owner_id}
        resolved_contact_id, resolved_deal_id = resolve_hubspot_ids(rec)
        moved_stage = move_deal_to_primeiro_contato_feito(resolved_deal_id)
        task_id = create_task(rec, text, sender, resp)
        now_brt = datetime.now(BRT)
        registro = {
            'date': now_brt.strftime('%Y-%m-%d %H:%M'),
            'date_tz': now_brt.isoformat(),
            'to': rec.get('to'),
            'slug': rec.get('slug') or d.slugify(company(rec)),
            'email': rec.get('email'),
            'nome': first_name(rec),
            'sdr': owner_name,
            'sender_name': sender_label,
            'sender_phone': sender_phone,
            'bridge_port': port,
            'text': text,
            'text_status': 'ok',
            'messageId': (resp or {}).get('messageId'),
            'send_response': resp,
            'empresa': company(rec),
            'msg_type': MSG_TYPE,
            'status': 'enviado_followup_mql',
            'deal_id': resolved_deal_id or rec.get('deal_id'),
            'contact_id': resolved_contact_id or rec.get('contact_id'),
            'owner_id': owner_id,
            'source_status': rec.get('status'),
            'source_date': rec.get('date'),
            'task_id': task_id,
            'dealstage_after_followup': moved_stage,
        }
        envios = d.registrar_envio(registro)
        sent += 1
        print(f"OK {company(rec)} messageId={(resp or {}).get('messageId')} task={task_id} stage={moved_stage}")
        if sent < args.limit:
            time.sleep(2)
    print(f"RESUMO enviados={sent}")

if __name__ == '__main__':
    main()
