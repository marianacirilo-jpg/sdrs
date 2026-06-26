#!/usr/bin/env python3
"""Cadência automática para negócios em Primeiro Contato sem resposta.

Objetivo: depois do 1º contato SDR (Dia 0), enviar 2º/3º/4º contatos em
cadência diária se o lead NÃO respondeu/interagiu e o negócio continua em
Primeiro Contato. Após 4 tentativas sem resposta, sinalizar nutrição/material
rico em vez de continuar priorizando SDR.

Seguro por padrão: rode com --dry-run para prévia. Envio real exige --send.
"""
import argparse
import importlib.util
import json
import os
import sys
import time
import urllib.request
import fcntl
import atexit
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path('/root/.hermes/zydon-prospeccao')
DISPARO = ROOT / 'disparo_dinamico.py'
WA_DATA = Path('/root/.hermes/whatsapp-extra/channel_data')
METRICS_JSONL = ROOT / 'controle' / 'cadencia_primeiro_contato_metrics.jsonl'

spec = importlib.util.spec_from_file_location('disparo_dinamico', str(DISPARO))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

PIPELINE = d.PIPELINE
STAGE_PRIMEIRO_CONTATO = '1214320997'
STAGE_RETORNO_CONTATO = '998099482'
STAGE_PERDIDO = '984052835'
CLOSED_LOST_REASON = 'Falta de retorno - Início do funil'
STAGE_LABELS = {
    '984052829': 'Lead Sem Contato',
    '1214320997': 'Primeiro Contato',
    '998099482': 'Retorno Contato',
    '1151853491': 'Diagnóstico SDR',
    '1376131958': 'No Show',
    '1269308723': 'Introdução',
}
BRT = timezone(timedelta(hours=-3))

INITIAL_MSG_TYPES = {'primeiro_contato', 'primeiro_contato_backlog_institucional'}
CADENCE_MSG_TYPE = 'primeiro_contato_cadencia'
NURTURE_MSG_TYPE = 'primeiro_contato_nutricao'
BLOCKING_MSG_TYPES = INITIAL_MSG_TYPES | {CADENCE_MSG_TYPE, NURTURE_MSG_TYPE}

# Conservador: no máximo 4 tentativas totais contando Dia 0.
MAX_ATTEMPTS = 4
# Rafael: nunca fazer dois follows para a mesma pessoa no mesmo dia BRT.
# A próxima tentativa só fica elegível no próximo dia útil de execução.
MIN_HOURS_BETWEEN_ATTEMPTS = 20

OWNER_KEYS = ('breno', 'sarah', 'lucas')

# Comunicadores institucionais liberados para ajudar no volume. Quando usados,
# a mensagem precisa deixar claro que o SDR/consultor responsável vai seguir.
COMMUNICATOR_SENDERS = [
    {'name': 'Mariana', 'port': 4600},
    {'name': 'Lucas Resende', 'port': 4606},
    {'name': 'Rafael', 'port': 4607},
    {'name': 'João Pedro', 'port': 4609},
    {'name': 'Gustavo', 'port': 4610},
]


def now_brt():
    return datetime.now(BRT)


def parse_dt(raw):
    if not raw:
        return None
    txt = str(raw).strip()
    for suffix in ('Z', '+00:00'):
        pass
    try:
        if txt.endswith('Z'):
            return datetime.fromisoformat(txt[:-1] + '+00:00').astimezone(timezone.utc)
        dt = datetime.fromisoformat(txt)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=BRT)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(txt[:19], fmt).replace(tzinfo=BRT).astimezone(timezone.utc)
        except Exception:
            continue
    return None


def normalize_jid_phone(value):
    return d.normalize_phone(str(value or ''))


def envio_ts(reg):
    return parse_dt(reg.get('date_tz') or reg.get('date') or reg.get('created_at'))


def load_history_messages(ports):
    items = []
    for port in sorted(set(int(p) for p in ports)):
        p = WA_DATA / f'history_{port}.json'
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for m in data:
            if not isinstance(m, dict):
                continue
            mm = dict(m)
            mm['port'] = int(mm.get('port') or port)
            items.append(mm)
    return items


def message_phone_keys(m):
    keys = set()
    for field in ('chat', 'sender', 'participant', 'jid', 'remoteJidAlt', 'jidAlt'):
        val = m.get(field)
        key = normalize_jid_phone(val)
        if key:
            keys.add(key)
    raw = m.get('rawKey') or {}
    if isinstance(raw, dict):
        for field in ('remoteJid', 'remoteJidAlt', 'participant'):
            key = normalize_jid_phone(raw.get(field))
            if key:
                keys.add(key)
    return keys


def history_outgoing_for(phone_key, ports):
    out = []
    for m in load_history_messages(ports):
        if m.get('fromMe') is not True:
            continue
        if phone_key not in message_phone_keys(m):
            continue
        try:
            ts = float(m.get('timestamp') or 0)
        except Exception:
            ts = 0
        if ts:
            out.append(m)
    out.sort(key=lambda x: float(x.get('timestamp') or 0))
    return out


def history_incoming_after(phone_key, after_dt, ports):
    if not after_dt:
        return []
    cutoff = after_dt.timestamp()
    incoming = []
    for m in load_history_messages(ports):
        if m.get('fromMe') is True:
            continue
        if phone_key not in message_phone_keys(m):
            continue
        try:
            ts = float(m.get('timestamp') or 0)
        except Exception:
            ts = 0
        if ts and ts > cutoff + 60:
            incoming.append(m)
    incoming.sort(key=lambda x: float(x.get('timestamp') or 0))
    return incoming


def envios_for_phone(envios, phone_key):
    out = []
    for r in envios:
        if not isinstance(r, dict):
            continue
        if str(r.get('msg_type') or '').lower() not in BLOCKING_MSG_TYPES:
            continue
        keys = {normalize_jid_phone(r.get(k)) for k in d.PHONE_FIELDS}
        keys.discard('')
        if phone_key in keys:
            ts = envio_ts(r)
            if ts:
                rr = dict(r)
                rr['_ts'] = ts
                out.append(rr)
    out.sort(key=lambda r: r['_ts'])
    return out


def is_automation_task(props):
    txt = ' '.join(str(props.get(k) or '') for k in ('hs_task_subject', 'hs_task_body')).lower()
    markers = (
        'diagnóstico', 'diagnostico', 'potencial de digitalização', 'potencial de digitalizacao',
        'primeiro contato whatsapp', 'primeiro contato backlog',
        'cadência primeiro contato', 'cadencia primeiro contato',
        'nutrição/material rico', 'nutricao/material rico',
    )
    return any(m in txt for m in markers)


def has_interaction_after_first(deal_id, first_ts):
    """Retorna (blocked, reasons). Fail-closed em erro de leitura."""
    reasons = []
    deal_ids = [str(deal_id)]
    task_map = d.ler_assoc_deals_objetos(deal_ids, 'tasks')
    call_map = d.ler_assoc_deals_objetos(deal_ids, 'calls')
    meeting_map = d.ler_assoc_deals_objetos(deal_ids, 'meetings')
    if any(x is None for x in (task_map, call_map, meeting_map)):
        return True, ['erro ao ler associações HubSpot (fail-closed)']

    task_ids = task_map.get(str(deal_id), [])
    call_ids = call_map.get(str(deal_id), [])
    meeting_ids = meeting_map.get(str(deal_id), [])

    task_props = d.buscar_objetos_props('tasks', task_ids, ['hs_task_subject', 'hs_task_body', 'hs_timestamp'])
    call_props = d.buscar_objetos_props('calls', call_ids, ['hs_call_status', 'hs_call_disposition', 'hs_call_title', 'hs_call_body', 'hs_call_duration', 'hs_timestamp'])
    meeting_props = d.buscar_objetos_props('meetings', meeting_ids, ['hs_meeting_outcome', 'hs_meeting_title', 'hs_meeting_body', 'hs_timestamp', 'hs_meeting_start_time'])
    if task_props is None or call_props is None or meeting_props is None:
        return True, ['erro ao ler detalhes de atividades HubSpot (fail-closed)']

    for tid, props in task_props.items():
        ts = parse_dt(props.get('hs_timestamp'))
        if first_ts and ts and ts <= first_ts:
            continue
        if not is_automation_task(props):
            reasons.append(f"task comercial/manual após D0: {props.get('hs_task_subject') or tid}")

    for cid, props in call_props.items():
        if d.call_efetuada(props):
            reasons.append(f"ligação efetuada/atendida: {props.get('hs_call_title') or cid}")

    for mid, props in meeting_props.items():
        txt = ' '.join(str(props.get(k) or '') for k in ('hs_meeting_outcome', 'hs_meeting_title', 'hs_meeting_body')).lower()
        if 'canceled' in txt or 'cancelad' in txt:
            continue
        # Reunião associada (futura/agendada ou efetuada) tira da cadência automática.
        reasons.append(f"reunião associada/agendada/efetuada: {props.get('hs_meeting_title') or mid}")

    return bool(reasons), reasons


def buscar_deals_primeiro_contato(owner_id):
    url = 'https://api.hubapi.com/crm/v3/objects/deals/search'
    body = {
        'filterGroups': [{'filters': [
            {'propertyName': 'pipeline', 'operator': 'EQ', 'value': PIPELINE},
            {'propertyName': 'dealstage', 'operator': 'EQ', 'value': STAGE_PRIMEIRO_CONTATO},
            {'propertyName': 'hubspot_owner_id', 'operator': 'EQ', 'value': owner_id},
        ]}],
        'properties': ['dealname', 'dealstage', 'hubspot_owner_id', 'createdate', 'notes_last_updated', 'notes_last_contacted', 'hs_latest_meeting_activity'],
        'limit': 100,
        'sorts': [{'propertyName': 'createdate', 'direction': 'DESCENDING'}],
    }
    out = []
    after = None
    while True:
        if after:
            body['after'] = after
        elif 'after' in body:
            del body['after']
        res = d.hs_request(url, 'POST', body)
        if not res:
            break
        out.extend(res.get('results', []))
        after = (res.get('paging') or {}).get('next', {}).get('after')
        if not after:
            break
    return out


def article_for_name(name):
    first = (name or '').strip().split()[0].lower()
    return 'a' if first in {'sarah', 'mariana'} else 'o'


def owner_phone_for_addendum(owner_name):
    first = (owner_name or '').strip().split()[0].lower()
    # Telefones dos chips SDR. Remover sufixo de device do Baileys (:4, :13 etc.).
    phones = {
        'sarah': '55 34 8429-1640',
        'lucas': '55 34 8429-5409',
        'breno': '55 34 8432-5076',
    }
    return phones.get(first, '')


def consultant_addendum(lead, sender):
    sender_name = (sender or {}).get('sender_name') or (sender or {}).get('name') or lead.get('owner_name') or ''
    owner = lead.get('owner_name') or 'consultor'
    # Se o próprio SDR dono está enviando, não faz sentido dizer
    # "O Breno/Lucas/Sarah é quem vai seguir contigo". O nome do chip pode vir
    # como "Breno Mendonça" enquanto o owner vem só "Breno", então compara pelo
    # primeiro nome normalizado, não por string exata.
    sender_norm = ' '.join((sender_name or '').strip().lower().split())
    owner_norm = ' '.join((owner or '').strip().lower().split())
    sender_first = sender_norm.split()[0] if sender_norm else ''
    owner_first = owner_norm.split()[0] if owner_norm else ''
    same_person = bool(sender_norm and owner_norm and sender_norm == owner_norm)
    # Para Sarah/Breno, primeiro nome basta. Para Lucas, não basta porque existem
    # Lucas Batista (SDR) e Lucas Resende (comunicador).
    if not same_person and sender_first == owner_first and owner_first in {'sarah', 'breno'}:
        same_person = True
    if not sender_name or same_person:
        return ''

    artigo = article_for_name(owner).capitalize()
    phone = owner_phone_for_addendum(owner)
    if phone:
        return f"\n\n{artigo} {owner} segue contigo se fizer sentido avançar. WhatsApp: +{phone}."
    return f"\n\n{artigo} {owner} segue contigo se fizer sentido avançar."


_RESEARCH_FOLLOWUPS = None

def norm_key(text):
    text = (text or '').lower()
    text = re.sub(r'[^a-z0-9áàâãéêíóôõúç]+', ' ', text)
    return ' '.join(text.split())


def load_researched_followups():
    """Carrega rascunhos hipersegmentados gerados pelo Claude Code.

    Rafael: não repetir mensagem genérica quando já existe estudo por segmento,
    formulário/ERP ou pesquisa. Este parser usa o relatório mais recente em
    docs/followup-research e cai no template apenas quando não há rascunho.
    """
    global _RESEARCH_FOLLOWUPS
    if _RESEARCH_FOLLOWUPS is not None:
        return _RESEARCH_FOLLOWUPS
    out = {}
    base = ROOT / 'docs' / 'followup-research'
    reports = sorted(base.glob('*/preparo-followups-*.md'), reverse=True)
    for report in reports:
        try:
            md = report.read_text(encoding='utf-8')
        except Exception:
            continue
        headings = list(re.finditer(r'^##\s+\d+\.\s+(.+?)\s*$', md, re.M))
        for i, h in enumerate(headings):
            title = h.group(1).strip()
            section = md[h.end(): headings[i + 1].start() if i + 1 < len(headings) else len(md)]
            if ',' in title:
                company = title.split(',', 1)[1].strip()
            else:
                company = title.strip()
            company = re.sub(r'\s*\([^)]*\)\s*$', '', company).strip()
            key = norm_key(company)
            if not key:
                continue
            out.setdefault(key, {})
            for m in re.finditer(r'Follow\s+(\d+)\s*\n```\s*\n(.*?)\n```', section, re.S | re.I):
                try:
                    attempt = int(m.group(1))
                except Exception:
                    continue
                txt = m.group(2).strip()
                if txt:
                    out[key][attempt] = txt
    _RESEARCH_FOLLOWUPS = out
    return out


def researched_message_for(lead, attempt_number):
    empresa = lead.get('empresa') or ''
    key = norm_key(empresa)
    if not key:
        return ''
    research = load_researched_followups()
    # match exato ou contém, para lidar com razão social abreviada no HubSpot.
    if key in research and attempt_number in research[key]:
        return research[key][attempt_number]
    for rk, attempts in research.items():
        if attempt_number in attempts and (key in rk or rk in key):
            return attempts[attempt_number]
    return ''


def extract_message_variation(lead, attempt_number, sender=None):
    nome = (lead.get('nome') or 'tudo bem').strip().split()[0]
    if nome.lower() in ('', 'lead', 'cliente'):
        nome = 'tudo bem'
    else:
        nome = nome[:1].upper() + nome[1:].lower()
    empresa = (lead.get('empresa') or '').strip()
    empresa_low = empresa.lower()
    if (not empresa or empresa_low in ('sua', 'sem nome', 'none', 'null') or 'não usar' in empresa_low
            or 'nao usar' in empresa_low or 'uso interno' in empresa_low or 'uso iterno' in empresa_low
            or set(empresa) <= {'.', '-', '_', ' '}):
        empresa = ''
    empresa_txt = f" da {empresa}" if empresa else ''
    owner = (sender or {}).get('sender_name') or (sender or {}).get('name') or lead.get('owner_name') or 'Zydon'
    if owner == 'Lucas Batista':
        owner_short = 'Lucas Batista'
    elif owner == 'Lucas Resende':
        owner_short = 'Lucas Resende'
    elif owner == 'João Pedro':
        owner_short = 'João Pedro'
    else:
        owner_short = str(owner).split()[0]
    erp = (lead.get('erp') or '').strip()
    erp_line = f"Já integra nativo com o {erp}." if erp else "Quando o ERP está dentro das integrações nativas, dá para conectar direto."
    agenda = lead.get('agenda') or ''
    agenda_txt = f"\n\nSe preferir, pode escolher um horário direto aqui: {agenda}" if agenda else ''
    dor_default = 'o desafio aí parece ser digitalizar a operação comercial sem complicar o que já funciona'
    first_variants = [
        f"Oi {nome}, tudo bem?\n\nAqui é {owner_short}, da Zydon. Vi seu cadastro{empresa_txt} sobre venda B2B e queria entender se hoje os pedidos ainda passam por WhatsApp, vendedor ou pedido manual.\n\nPode me responder por aqui?",
        f"Oi {nome}, tudo bem?\n\nAqui é {owner_short}, da Zydon. Vi o interesse{empresa_txt} e queria entender se o desafio aí é organizar pedido recorrente, tabela por cliente ou recompra.\n\nPode ser por aqui?",
        f"Oi {nome}, tudo bem?\n\nAqui é {owner_short}, da Zydon. A Zydon ajuda operações B2B a deixar o cliente consultando preço e fazendo pedido sozinho. Queria entender se isso faz sentido para vocês hoje.\n\nPode me responder por aqui?",
    ]
    if attempt_number == 1 and float(lead.get('days_since_first') or 0) > 2:
        agenda_part = f" Se fizer sentido, a agenda do consultor responsável fica aqui: {agenda}" if agenda else ""
        first_variants = [
            f"Oi {nome}, tudo bem?\n\nAqui é {owner_short}, da Zydon. Vi um cadastro anterior{empresa_txt} sobre venda B2B e queria entender se isso ainda faz sentido hoje.\n\nPode me responder por aqui?{agenda_part}",
            f"Oi {nome}, tudo bem?\n\nAqui é {owner_short}, da Zydon. Seu cadastro{empresa_txt} ficou pendente por aqui. A conversa costuma fazer sentido quando pedido, recompra ou tabela por cliente ainda ficam no manual.\n\nSe for o caso de vocês, pode me responder por aqui.{agenda_part}",
            f"Oi {nome}, tudo bem?\n\nAqui é {owner_short}, da Zydon. Estou retomando alguns cadastros antigos e queria entender se venda B2B digital ainda é um tema para {empresa or 'vocês'}.\n\nPode ser por aqui?{agenda_part}",
        ]
    variants = {
        1: first_variants,
        2: [
            f"Fala {nome}!\n\nQueria deixar um número que pode fazer sentido pra vocês.\nDistribuidoras que colocaram o portal no ar viram em torno de 60% dos pedidos recorrentes migrarem pro autosserviço em menos de 3 meses. O time parou de tirar pedido e voltou a prospectar.\nAinda faz sentido conversar essa semana?",
            f"Fala {nome}!\n\nUm ponto que pode fazer sentido: quando o cliente recorrente compra sozinho pelo portal, o vendedor para de ficar só tirando pedido e volta a abrir conta nova.\nAinda faz sentido conversarmos essa semana?",
        ],
        3: [
            f"Fala {nome}, tudo certo?\n\nFiz uma conta rápida com base no perfil de vocês.\nCom 2 a 5 vendedores, cada pedido processado na mão custa entre R$15 e R$25 em tempo de equipe. Em 500 pedidos por mês, isso é até R$12 mil por mês só em retrabalho. Fora o tempo que o vendedor poderia estar prospectando.\nQuer ver como isso fica com os números reais da {empresa or 'empresa'}? zydon.com.br/calculadora-roi",
            f"Fala {nome}, tudo certo?\n\nFiz uma conta rápida com base no perfil de vocês.\nSe parte do time fica conferindo pedido, preço e condição no WhatsApp, esse tempo vira custo operacional todo mês. O portal tira esse peso do vendedor e deixa ele focar em conta nova.\nQuer ver como isso fica com os números reais da {empresa or 'empresa'}? zydon.com.br/calculadora-roi",
        ],
        4: [
            f"Fala {nome}, tudo tranquilo por aí?\n\nImagino que a correria tenha enrolado sua agenda.\nVou pausar por aqui pra não ficar lotando o seu WhatsApp. Sei que o plano era resolver a questão dos vendedores travados tirando pedido. Quando tiver fôlego pra tirar isso do papel, as portas da Zydon continuam abertas.\nAbraço e sucesso!",
            f"Fala {nome}, tudo tranquilo por aí?\n\nImagino que a rotina tenha corrido por aí.\nVou pausar as tentativas para não ficar lotando seu WhatsApp. Se voltar a fazer sentido olhar pedido B2B, recompra e cliente comprando sozinho, as portas da Zydon continuam abertas.\nAbraço e sucesso!",
        ],
    }
    key = f"{lead.get('deal_id')}|{lead.get('jid')}|{attempt_number}"
    idx = int(__import__('hashlib').sha256(key.encode()).hexdigest()[:8], 16) % len(variants[attempt_number])
    researched = researched_message_for(lead, attempt_number)
    text = researched or variants[attempt_number][idx]
    # Rafael 26/06: quando houver estudo do Claude Code, ele tem precedência sobre
    # template genérico. A mensagem deve usar segmento, formulário/ERP e dor provável.
    if researched:
        lead['_research_used'] = True
    # Rafael 26/06: quando o disparo for pelo próprio SDR, sempre tentar ligação.
    # Comunicador mantém CTA por WhatsApp/ponte para o SDR dono.
    if not (sender or {}).get('is_communicator'):
        call_cta = 'Você tem um tempo agora? Posso te ligar rapidinho?'
        replacements = [
            'Pode me responder por aqui?', 'Pode ser por aqui?', 'Ainda faz sentido conversar essa semana?',
            'Ainda faz sentido conversarmos essa semana?', 'Quer ver como isso fica com os números reais da empresa? zydon.com.br/calculadora-roi',
            f"Quer ver como isso fica com os números reais da {empresa or 'empresa'}? zydon.com.br/calculadora-roi",
        ]
        for r in replacements:
            text = text.replace(r, call_cta)
        if call_cta not in text:
            text = text.rstrip() + '\n\n' + call_cta
    text = text + consultant_addendum(lead, sender)
    if now_brt().hour >= 18:
        # Rafael: depois das 18h não usar "ligação" nem pedir chamada.
        replacements = {
            'ligação': 'conversa por aqui',
            'te ligo rapidinho e te direciono melhor': 'te respondo por aqui e te direciono melhor',
            'te ligo rápido': 'te respondo por aqui',
            'eu te ligo': 'eu te respondo por aqui',
            'Faz sentido eu te ligar para confirmar isso?': 'Faz sentido me responder por aqui para eu confirmar isso?',
            'Posso te ligar rápido?': 'Pode me responder por aqui?',
            'Podemos falar por aqui ou prefere por conversa por aqui?': 'Podemos falar por aqui?',
            'ou prefere por conversa por aqui?': 'podemos seguir por aqui?',
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
    return text


def owner_agenda(owner_key):
    if owner_key == 'breno':
        return 'https://meetings.hubspot.com/breno-mendonca'
    if owner_key == 'sarah':
        return 'https://meetings.hubspot.com/sarah-bento'
    if owner_key == 'lucas':
        return 'https://meetings.hubspot.com/lucas-alcantara-nogueira-batista'
    return ''


def create_cadence_task(lead, text, attempt_number, sender, send_resp=None, nurture=False):
    subject = (f"WhatsApp — cadência Primeiro Contato D{attempt_number-1} enviado por {sender.get('sender_name')}"
               if not nurture else "WhatsApp — sem resposta após 4 tentativas; encaminhar nutrição/material rico")
    body_txt = [
        f"Cadência automática Primeiro Contato sem resposta.",
        f"Tentativa: {attempt_number}/{MAX_ATTEMPTS}",
        f"Lead: {lead.get('nome')} / {lead.get('empresa')}",
        f"Destino: {lead.get('jid')}",
        f"Deal: {lead.get('deal_id')}",
        f"Contato: {lead.get('contact_id')}",
        f"Remetente: {sender.get('sender_name')} (porta {sender.get('port')})",
        f"SDR responsável: {lead.get('owner_name')} ({lead.get('owner_id')})",
    ]
    if send_resp is not None:
        body_txt.append(f"Resposta bridge: {json.dumps(send_resp, ensure_ascii=False)[:1000]}")
    if text:
        body_txt.extend(['', 'Texto enviado:', text])
    body = {
        'properties': {
            'hs_timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'hs_task_subject': subject,
            'hs_task_body': '\n'.join(body_txt),
            'hs_task_status': 'COMPLETED',
            'hs_task_priority': 'MEDIUM',
            'hubspot_owner_id': lead['owner_id'],
        },
        'associations': [
            {'to': {'id': int(lead['contact_id'])}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 204}]},
            {'to': {'id': int(lead['deal_id'])}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 216}]},
        ],
    }
    res = d.hs_request('https://api.hubapi.com/crm/v3/objects/tasks', 'POST', body)
    return res.get('id') if res else None


def move_deal_stage(deal_id, stage_id, extra_props=None):
    props = {'dealstage': str(stage_id)}
    if extra_props:
        props.update(extra_props)
    try:
        return d.hs_request(
            f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}",
            'PATCH',
            {'properties': props},
        )
    except Exception as e:
        print(f"⚠️  Falha ao mover deal {deal_id} para etapa {stage_id}: {e}")
        return None


def mark_return_contact(lead, reasons=None):
    move_deal_stage(lead['deal_id'], STAGE_RETORNO_CONTATO)
    body = 'Movido automaticamente para Retorno Contato porque houve resposta/interação após follow-up.\n'
    if reasons:
        body += 'Motivos: ' + '; '.join(reasons[:5])
    try:
        task_id = create_cadence_task(lead, body, int(lead.get('attempt_count') or 0), {'sender_name': 'Automação', 'port': None}, send_resp={'stage_move': 'Retorno Contato'}, nurture=True)
    except Exception:
        task_id = None
    append_metric({**lead, 'event': 'moved_retorno_contato', 'task_id': task_id, 'reasons': reasons or [], 'date_tz': now_brt().isoformat()})
    return task_id


def mark_lost_after_4(lead):
    move_deal_stage(lead['deal_id'], STAGE_PERDIDO, {'closed_lost_reason': CLOSED_LOST_REASON})
    body = f"4 follow-ups enviados sem resposta. Negócio ainda estava em Primeiro Contato. Movido para Perdido. Motivo: {CLOSED_LOST_REASON}."
    task_id = create_cadence_task(lead, body, MAX_ATTEMPTS, {'sender_name': 'Automação', 'port': None}, send_resp={'stage_move': 'Perdido', 'closed_lost_reason': CLOSED_LOST_REASON}, nurture=True)
    append_metric({**lead, 'event': 'moved_lost_after_4', 'task_id': task_id, 'closed_lost_reason': CLOSED_LOST_REASON, 'date_tz': now_brt().isoformat()})
    return task_id


def append_metric(row):
    METRICS_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with METRICS_JSONL.open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')


def bridge_sender_for_lead(lead, port, sender_label, sender_phone=''):
    return {
        'sender_name': sender_label,
        'name': sender_label,
        'port': port,
        'sender_phone': sender_phone,
        'is_communicator': sender_label != lead.get('owner_name'),
    }


def active_communicator_senders(include_ports=None):
    include = set(int(p) for p in include_ports) if include_ports else None
    out = []
    for s in COMMUNICATOR_SENDERS:
        port = int(s['port'])
        if include and port not in include:
            continue
        try:
            with urllib.request.urlopen(urllib.request.Request(f'http://localhost:{port}/status'), timeout=4) as resp:
                st = json.loads(resp.read().decode())
            with urllib.request.urlopen(urllib.request.Request(f'http://localhost:{port}/me'), timeout=4) as resp:
                me = json.loads(resp.read().decode())
            if st.get('needsQR') is True or not me.get('id'):
                continue
            out.append(bridge_sender_for_lead({'owner_name': ''}, port, s['name'], str(me.get('phone') or me.get('id') or '')))
        except Exception:
            continue
    return out


def choose_sender_for_lead(lead, envios, use_communicators=False, communicator_ports=None, rr_index=0, disabled_ports=None):
    disabled_ports = disabled_ports or set()

    def owner_sender():
        bridge = d.BRIDGES[lead['owner_key']]
        port, status, errors = d.escolher_porta_online(bridge, envios)
        if not port or port in disabled_ports:
            return None, errors
        sender_phone = ''
        sender_label = lead['owner_name']
        try:
            with urllib.request.urlopen(urllib.request.Request(f'http://localhost:{port}/me'), timeout=5) as resp:
                me = json.loads(resp.read().decode())
            sender_phone = str(me.get('phone') or me.get('id') or '')
            sender_label = str(me.get('name') or lead['owner_name'])
        except Exception:
            pass
        return bridge_sender_for_lead(lead, port, sender_label, sender_phone), None

    # Rafael: comunicadores limpam backlog/Follow 1 antigo. SDRs ficam com Lead Sem Contato,
    # primeiros contatos recentes e follows seguintes (tentativas 2+).
    attempt = int(lead.get('next_attempt') or 1)
    days = float(lead.get('days_since_first') or 0)
    if use_communicators and attempt == 1 and days > 2:
        pool = [s for s in active_communicator_senders(communicator_ports) if s['port'] not in disabled_ports]
        if pool:
            s = pool[rr_index % len(pool)]
            return bridge_sender_for_lead(lead, s['port'], s['sender_name'], s.get('sender_phone') or ''), None

    return owner_sender()


def collect_candidates(move_interacted=False):
    envios = d.load_envios()
    now_utc = datetime.now(timezone.utc)
    stats = {}
    candidates = []
    nurture_due = []
    blocked_examples = []

    for owner_key in OWNER_KEYS:
        bridge = d.BRIDGES[owner_key]
        owner_id = bridge['owner_id']
        owner_name = bridge['owner_name']
        ports = bridge.get('ports') or [bridge['port']]
        deals = buscar_deals_primeiro_contato(owner_id)
        s = {'deals_primeiro_contato': len(deals), 'sem_contato': 0, 'sem_tel': 0, 'sem_d0': 0,
             'respondidos_interagidos': 0, 'nao_venceu_janela': 0, 'prontos_cadencia': 0, 'prontos_nutricao': 0}
        for deal in deals:
            deal_id = str(deal.get('id'))
            props = deal.get('properties') or {}
            res = d.get_contact_for_deal(deal_id)
            if not res:
                s['sem_contato'] += 1
                continue
            contact_id, cprops = res
            tel = d.extrair_telefone(cprops)
            if not tel:
                s['sem_tel'] += 1
                continue
            tel_raw, jid, tel_fmt = tel
            phone_key = normalize_jid_phone(jid)
            related = envios_for_phone(envios, phone_key)
            if not related:
                # Anti-repetição: o ledger pode não ter capturado mensagens antigas
                # exibidas no Channel/WhatsApp. Se já existe saída no histórico do
                # chip para este telefone, tratar como D0 e continuar a cadência,
                # nunca mandar outro "1º contato".
                hist_out = history_outgoing_for(phone_key, ports)
                if hist_out:
                    h = hist_out[-1]
                    hts = datetime.fromtimestamp(float(h.get('timestamp')), tz=timezone.utc)
                    related = [{'_ts': hts, 'msg_type': 'primeiro_contato_history', 'date_tz': hts.isoformat(), 'text': h.get('text') or h.get('body') or ''}]
            if not related:
                created_ts = parse_dt(props.get('createdate'))
                activity_candidates = [parse_dt(props.get(k)) for k in ('notes_last_updated','notes_last_contacted','hs_latest_meeting_activity')]
                recent_anchor = max([x for x in activity_candidates + [created_ts] if x], default=None)
                if not recent_anchor or (now_utc - recent_anchor).total_seconds() > 21 * 86400:
                    s['sem_d0'] += 1
                    continue
                age_days = (now_utc - recent_anchor).total_seconds() / 86400
                if age_days < 0:
                    s['nao_venceu_janela'] += 1
                    continue
                dup = d.company_recently_touched(envios, props.get('dealname') or '', current_deal_id=deal_id)
                if dup:
                    s['sem_d0'] += 1
                    if len(blocked_examples) < 8:
                        blocked_examples.append({'deal_id': deal_id, 'empresa': props.get('dealname'), 'motivos': [f"duplicado empresa com envio recente ({dup.get('deal_id') or dup.get('email') or dup.get('slug')})"]})
                    continue
                # Limpeza do passado aprovada pelo Rafael: negócios em Primeiro Contato
                # sem D0 no ledger, mas criados/ativos nas últimas 3 semanas, recebem Follow 1.
                lead = {
                    'owner_key': owner_key,
                    'owner_id': owner_id,
                    'owner_name': owner_name,
                    'ports': ports,
                    'deal_id': deal_id,
                    'contact_id': str(contact_id),
                    'nome': (cprops.get('firstname') or '').strip(),
                    'empresa': (props.get('dealname') or '').strip(),
                    'erp': d.extrair_erp(cprops) or '',
                    'tel': tel_raw,
                    'jid': jid,
                    'tel_fmt': tel_fmt,
                    'attempt_count': 0,
                    'next_attempt': 1,
                    'first_ts': '',
                    'last_ts': '',
                    'days_since_first': round((now_utc - recent_anchor).total_seconds() / 86400, 2),
                    'hours_since_last': 9999,
                    'agenda': owner_agenda(owner_key),
                    'recent_anchor': recent_anchor.isoformat(),
                }
                candidates.append(lead)
                s['prontos_cadencia'] += 1
                continue
            first_ts = related[0]['_ts']
            last_ts = related[-1]['_ts']
            attempt_count = len([r for r in related if str(r.get('msg_type') or '').lower() != NURTURE_MSG_TYPE])
            days_since_first = (now_utc - first_ts).total_seconds() / 86400
            hours_since_last = (now_utc - last_ts).total_seconds() / 3600
            if days_since_first < 0 or hours_since_last < 0:
                s['nao_venceu_janela'] += 1
                continue
            now_brt_dt = now_utc.astimezone(BRT)
            last_brt_dt = last_ts.astimezone(BRT)
            next_brt_day_ok = now_brt_dt.date() > last_brt_dt.date()

            # Regra Rafael (25/06): a cadência já é restrita à etapa Primeiro Contato.
            # Não bloquear por task manual, ligação ou reunião associada. Enquanto o negócio
            # continuar em Primeiro Contato, só uma resposta do lead no WhatsApp após D0
            # tira o lead da cadência automática.
            # Se o D0/follow saiu por comunicador, a resposta cai no histórico da porta
            # do comunicador, não no chip do SDR dono. Olhar ambos.
            related_ports = {int(p) for p in ports}
            for rr in related:
                try:
                    if rr.get('bridge_port'):
                        related_ports.add(int(rr.get('bridge_port')))
                except Exception:
                    pass
            incoming = history_incoming_after(phone_key, first_ts, sorted(related_ports))
            if incoming:
                reasons = [f"resposta WhatsApp após D0 ({len(incoming)} msg)"]
                s['respondidos_interagidos'] += 1
                if len(blocked_examples) < 8:
                    blocked_examples.append({
                        'deal_id': deal_id,
                        'empresa': props.get('dealname'),
                        'motivos': reasons,
                    })
                if move_interacted:
                    lead_for_move = {
                        'deal_id': deal_id,
                        'contact_id': str(contact_id),
                        'nome': (cprops.get('firstname') or '').strip(),
                        'empresa': (props.get('dealname') or '').strip(),
                        'owner_id': owner_id,
                    }
                    mark_return_contact(lead_for_move, reasons)
                continue

            lead = {
                'owner_key': owner_key,
                'owner_id': owner_id,
                'owner_name': owner_name,
                'ports': ports,
                'deal_id': deal_id,
                'contact_id': str(contact_id),
                'nome': (cprops.get('firstname') or '').strip(),
                'empresa': (props.get('dealname') or '').strip(),
                'erp': d.extrair_erp(cprops) or '',
                'tel': tel_raw,
                'jid': jid,
                'tel_fmt': tel_fmt,
                'attempt_count': attempt_count,
                'first_ts': first_ts.isoformat(),
                'last_ts': last_ts.isoformat(),
                'days_since_first': round(days_since_first, 2),
                'hours_since_last': round(hours_since_last, 2),
                'agenda': owner_agenda(owner_key),
            }
            if attempt_count >= MAX_ATTEMPTS:
                if days_since_first >= 4 and next_brt_day_ok:
                    nurture_due.append(lead)
                    s['prontos_nutricao'] += 1
                else:
                    s['nao_venceu_janela'] += 1
                continue
            next_attempt = attempt_count + 1
            min_days = next_attempt - 1
            if days_since_first >= min_days and next_brt_day_ok:
                lead['next_attempt'] = next_attempt
                candidates.append(lead)
                s['prontos_cadencia'] += 1
            else:
                s['nao_venceu_janela'] += 1
        stats[owner_name] = s

    def candidate_priority(x):
        attempt = int(x.get('next_attempt') or 1)
        age_days = float(x.get('days_since_first') or 0)
        if attempt == 1 and age_days <= 2:
            bucket = 0  # Rafael: lead novo/recente é prioridade acima de Follow 2/3/4
        elif attempt >= 2:
            bucket = 1  # continuar cadência já iniciada depois dos novos
        else:
            bucket = 2  # backlog antigo por último, com agenda/contexto
        return (bucket, attempt, -age_days)

    candidates.sort(key=candidate_priority)
    nurture_due.sort(key=lambda x: -x['days_since_first'])
    return candidates, nurture_due, stats, blocked_examples


GLOBAL_SEND_LOCK = '/tmp/zydon_external_whatsapp_send.lock'
_GLOBAL_LOCK_FH = None


def acquire_global_send_lock(blocking=False):
    """Semáforo global para qualquer envio externo Zydon.

    Compartilhado por diagnóstico/PDF, primeiro contato e cadência/follow-up.
    Se estiver ocupado, este cron pula o tick para não empilhar mensagens/chips.
    """
    global _GLOBAL_LOCK_FH
    _GLOBAL_LOCK_FH = open(GLOBAL_SEND_LOCK, 'w')
    flags = 0 if blocking else fcntl.LOCK_NB
    try:
        fcntl.flock(_GLOBAL_LOCK_FH, fcntl.LOCK_EX | flags)
    except BlockingIOError:
        return False
    _GLOBAL_LOCK_FH.write(f"cadencia_primeiro_contato pid={os.getpid()} at={datetime.now(timezone.utc).isoformat()}\n")
    _GLOBAL_LOCK_FH.flush()
    def _release():
        try:
            fcntl.flock(_GLOBAL_LOCK_FH, fcntl.LOCK_UN)
            _GLOBAL_LOCK_FH.close()
        except Exception:
            pass
    atexit.register(_release)
    return True


def main():
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true', help='prévia sem enviar nem criar task')
    mode.add_argument('--send', action='store_true', help='envia WhatsApp e cria task de cadência')
    mode.add_argument('--mark-nurture', action='store_true', help='cria task de nutrição para casos com 4 tentativas sem resposta; não envia WhatsApp')
    ap.add_argument('--limit', type=int, default=3)
    ap.add_argument('--max-per-hour', type=int, default=3)
    ap.add_argument('--max-per-port-hour', type=int, default=d.MAX_EXTERNAL_PER_PORT_HOUR, help='teto global por chip/porta na última hora; usar override só em disparo manual autorizado')
    ap.add_argument('--max-per-port-day', type=int, default=d.MAX_EXTERNAL_PER_PORT_DAY, help='teto global por chip/porta no dia BRT; usar override só em disparo manual autorizado')
    ap.add_argument('--skip-company-regex', action='append', default=[], help='pula leads cuja empresa bata no regex, repetível')
    ap.add_argument('--sleep-seconds', type=float, default=300)
    ap.add_argument('--owner', choices=['all', 'breno', 'sarah', 'lucas'], default='all')
    ap.add_argument('--use-comunicadores', action='store_true', help='usa chips comunicadores institucionais com gancho para o SDR responsável')
    ap.add_argument('--comunicador-port', action='append', type=int, default=[], help='limita comunicadores a portas específicas, repetível')
    ap.add_argument('--first-attempt-max-age-hours', type=float, default=0, help='se >0, só envia Follow 1 para leads com anchor/criação recente; follows 2+ continuam normalmente')
    ap.add_argument('--require-research', action='store_true', help='só envia/mostra leads com rascunho hipersegmentado do Claude Code/base setorial; evita fallback genérico')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    if args.send and not acquire_global_send_lock(blocking=False):
        print('Lock global de envio ocupado; pulando cadência para evitar sobreposição de mensagens/chips.')
        return 0

    candidates, nurture_due, stats, blocked_examples = collect_candidates(move_interacted=bool(args.send or args.mark_nurture))
    if args.owner != 'all':
        candidates = [c for c in candidates if c['owner_key'] == args.owner]
        nurture_due = [c for c in nurture_due if c['owner_key'] == args.owner]
    if args.skip_company_regex:
        import re
        patterns = [re.compile(p, re.I) for p in args.skip_company_regex]
        candidates = [c for c in candidates if not any(p.search(c.get('empresa') or '') for p in patterns)]
        nurture_due = [c for c in nurture_due if not any(p.search(c.get('empresa') or '') for p in patterns)]
    if args.first_attempt_max_age_hours and args.first_attempt_max_age_hours > 0:
        # Rafael: Follow 1 automático só para lead novo. Backlog antigo sem D0
        # não deve ser disparado no cron; follows 2+ continuam normalmente.
        candidates = [
            c for c in candidates
            if c.get('next_attempt') != 1 or (float(c.get('days_since_first') or 9999) * 24) <= args.first_attempt_max_age_hours
        ]
    if args.require_research:
        candidates = [c for c in candidates if researched_message_for(c, int(c.get('next_attempt') or 1))]

    summary = {
        'generated_at_brt': now_brt().isoformat(),
        'stats': stats,
        'cadence_ready': len(candidates),
        'nurture_ready': len(nurture_due),
        'blocked_examples': blocked_examples,
        'cadence_preview': candidates[:args.limit],
        'nurture_preview': nurture_due[:args.limit],
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"CADÊNCIA PRIMEIRO CONTATO — {summary['generated_at_brt']}")
        print('Stats:', json.dumps(stats, ensure_ascii=False))
        print(f"Prontos cadência: {len(candidates)} | prontos nutrição: {len(nurture_due)} | limite={args.limit}")
        if blocked_examples:
            print('Exemplos bloqueados por resposta/interação:', json.dumps(blocked_examples, ensure_ascii=False))
        for i, c in enumerate(candidates[:args.limit], 1):
            preview_sender = None
            if args.use_comunicadores:
                pool = active_communicator_senders(args.comunicador_port or None)
                if pool:
                    preview_sender = pool[(i - 1) % len(pool)]
            text = extract_message_variation(c, c['next_attempt'], preview_sender)
            print(f"\n[{i}] {c['owner_name']} tentativa {c['next_attempt']}/{MAX_ATTEMPTS} | {c['nome']} | {c['empresa']} | {c['tel_fmt']} | D+{c['days_since_first']} | última {c['hours_since_last']}h")
            print(text)
        if nurture_due:
            print('\nNutrição/material rico (sem envio):')
            for i, c in enumerate(nurture_due[:args.limit], 1):
                print(f"[{i}] {c['owner_name']} | {c['nome']} | {c['empresa']} | {c['tel_fmt']} | tentativas={c['attempt_count']} | D+{c['days_since_first']}")

    if args.dry_run:
        return 0

    if args.mark_nurture:
        marked = 0
        for lead in nurture_due[:args.limit]:
            task_id = mark_lost_after_4(lead)
            marked += 1
            print(f"PERDIDO após 4 follows sem retorno: {lead['empresa']} task={task_id}")
        print(f"RESUMO: perdidos_marcados={marked}")
        return 0

    sent = 0
    failed = 0
    disabled_ports = set()
    envios = d.load_envios()
    for idx, lead in enumerate(candidates[:args.limit], 1):
        used_hour = d.envios_sdr_ultima_hora(envios, lead['owner_name'])
        if used_hour >= args.max_per_hour:
            print(f"Limite horário atingido para {lead['owner_name']}: {used_hour}/{args.max_per_hour}. Pulando.")
            continue
        sender, errors = choose_sender_for_lead(
            lead,
            envios,
            use_communicators=args.use_comunicadores,
            communicator_ports=args.comunicador_port or None,
            rr_index=idx - 1,
            disabled_ports=disabled_ports,
        )
        if not sender:
            print(f"Sem porta saudável para {lead['owner_name']}. Erros: {errors}")
            continue
        port = sender['port']
        sender_label = sender['sender_name']
        sender_phone = sender.get('sender_phone') or ''
        text = extract_message_variation(lead, lead['next_attempt'], sender)
        # Recheca o ledger compartilhado imediatamente antes de enviar. Se outro
        # cron acabou de mandar diagnóstico/primeiro contato/follow-up para o mesmo
        # telefone enquanto esta lista era montada, pula sem enviar.
        fresh_envios = d.load_envios()
        fresh_related = envios_for_phone(fresh_envios, normalize_jid_phone(lead['jid']))
        fresh_attempt_count = len([r for r in fresh_related if str(r.get('msg_type') or '').lower() != NURTURE_MSG_TYPE])
        if fresh_attempt_count >= int(lead['next_attempt']):
            print(f"PULADO ledger recente antes do envio: {lead['empresa']} {lead['tel_fmt']} tentativa já registrada ({fresh_attempt_count})")
            continue
        port_ok, port_reason = d.port_within_external_limits(fresh_envios, port, max_per_hour=args.max_per_port_hour, max_per_day=args.max_per_port_day)
        if not port_ok:
            print(f"PULADO limite global do chip: {port_reason} | {lead['empresa']} {lead['tel_fmt']}")
            continue
        print(f"ENVIANDO [{idx}] {lead['owner_name']} via {sender_label} porta {port} tentativa {lead['next_attempt']} -> {lead['empresa']} {lead['tel_fmt']}")
        ok, resp = d.send_whatsapp(port, lead['jid'], text)
        if not ok:
            failed += 1
            disabled_ports.add(port)
            print(f"FALHA porta {port}: {resp}. Porta removida da rodada.")
            continue
        task_id = create_cadence_task(lead, text, lead['next_attempt'], {'sender_name': sender_label, 'port': port}, send_resp=resp)
        if int(lead['next_attempt']) == 1:
            # Garantia Rafael: fez Follow 1/primeiro contato, card fica em Primeiro Contato.
            move_deal_stage(lead['deal_id'], STAGE_PRIMEIRO_CONTATO)
        sent_at = now_brt()
        registro = {
            'date': sent_at.strftime('%Y-%m-%d %H:%M:%S'),
            'date_tz': sent_at.isoformat(),
            'to': lead['jid'],
            'nome': lead['nome'],
            'empresa': lead['empresa'],
            'slug': d.slugify(lead['empresa']),
            'sdr': lead['owner_name'],
            'sender_name': sender_label,
            'sender_phone': sender_phone,
            'sender_is_communicator': bool(sender.get('is_communicator')),
            'bridge_port': port,
            'text': text,
            'text_status': 'ok',
            'msg_type': CADENCE_MSG_TYPE,
            'attempt_number': lead['next_attempt'],
            'campaign_id': 'cadencia_primeiro_contato_sem_resposta',
            'deal_id': lead['deal_id'],
            'contact_id': lead['contact_id'],
            'task_id': task_id,
            'send_response': resp,
        }
        envios = d.registrar_envio(registro)
        append_metric({**lead, 'event': 'cadence_sent', 'attempt_number': lead['next_attempt'], 'task_id': task_id, 'bridge_port': port, 'date_tz': sent_at.isoformat()})
        sent += 1
        print(f"OK enviado | task={task_id} | resp={resp}")
        if idx < min(args.limit, len(candidates)):
            time.sleep(args.sleep_seconds)
    lost_marked = 0
    for lead in nurture_due[:args.limit]:
        task_id = mark_lost_after_4(lead)
        lost_marked += 1
        print(f"PERDIDO após 4 follows sem retorno: {lead['empresa']} task={task_id}")
    print(f"RESUMO: enviados={sent} falhas={failed} perdidos_marcados={lost_marked}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
