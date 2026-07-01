#!/usr/bin/env python3
"""Cadência automática para negócios em Primeiro Contato sem resposta.

Objetivo: depois do 1º contato SDR (Dia 0), enviar 2º/3º/4º contatos em
cadência diária se o lead NÃO respondeu/interagiu e o negócio continua em
Primeiro Contato. Após 4 tentativas sem resposta, sinalizar nutrição/material
rico em vez de continuar priorizando SDR.

Seguro por padrão: rode com --dry-run para prévia. Envio real exige --send.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import sys
import time
import urllib.request
import fcntl
import atexit
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path('/root/.hermes/zydon-prospeccao')
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DISPARO = ROOT / 'disparo_dinamico.py'
WA_DATA = Path('/root/.hermes/whatsapp-extra/channel_data')
METRICS_JSONL = ROOT / 'controle' / 'cadencia_primeiro_contato_metrics.jsonl'
APPROVED_FOLLOWUP_MANIFEST = ROOT / 'controle' / 'followup_textos_aprovados_rafael_20260630.json'

spec = importlib.util.spec_from_file_location('disparo_dinamico', str(DISPARO))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
from scripts.whatsapp_send_orchestrator import enrich_legacy_row  # noqa: E402
from scripts.whatsapp_routing import choose_outbound_port  # noqa: E402
from scripts.whatsapp_dispatch_flow import record_dispatch_shadow_from_row, record_dispatch_worker_owned  # noqa: E402

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
BLOCKING_MSG_TYPES = INITIAL_MSG_TYPES | {
    CADENCE_MSG_TYPE,
    NURTURE_MSG_TYPE,
    # Correções/incidentes e nomes históricos também contam como tentativa real.
    # Sem isso, a fila paralela pode não enxergar um envio manual corrigido e repetir.
    'cadencia_primeiro_contato',
    'followup_mql_f1_corrigido',
    'mql_sdr_followup',
    'primeiro_contato_cadencia_corrigido',
}

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
    {'name': 'Sarah', 'port': 4601},
    {'name': 'Lucas Batista', 'port': 4603},
    {'name': 'Breno', 'port': 4605},
    {'name': 'Lucas Resende', 'port': 4606},
    {'name': 'Rafael', 'port': 4607},
    {'name': 'João Pedro', 'port': 4609},
    {'name': 'Gustavo', 'port': 4610},
]
COMMUNICATOR_PORTS = {int(s['port']) for s in COMMUNICATOR_SENDERS}

# Rafael 27/06: follow-ups 2+ podem enviar 1 portal público parecido
# com o segmento do lead para deixar a Zydon concreta/visual. Rafael reforçou:
# primeiro pesquisar quem compra do lead (restaurante, padaria, pet shop,
# material de construção, oficina, revenda etc.) e só então escolher uma loja
# parecida quando existir. Rafael 29/06: o follow-up não é cobrança; precisa
# explicar rápido e dar exemplo claro. Se não houver exemplo do mesmo segmento,
# pode usar um portal demonstrativo como exemplo visual de funcionamento, sem
# dizer que é caso parecido nem inventar aderência.
PORTAL_PUBLIC_EXAMPLES = [
    {'keywords': ['alimento', 'bebida', 'hortifruti', 'ceasa', 'mercado', 'supermercado', 'restaurante', 'padaria', 'lanchonete', 'food service', 'doce', 'chocolate', 'embare'], 'name': 'Ceasa Mais', 'url': 'https://portal.ceasamais.com.br/', 'buyer_context': 'Esse cliente vende para restaurantes, mercados e compradores de food service.'},
    {'keywords': ['autopeça', 'auto pecas', 'automot', 'lubrificante', 'lavador', 'oficina', 'mecânica', 'mecanica', 'auto center', 'frota', 'peça', 'peca'], 'name': 'Siga / Knakasaki', 'url': 'https://siga.knakasaki.com/', 'buyer_context': 'Esse cliente vende para oficinas, auto centers e compradores de reposição automotiva.'},
    {'keywords': ['maquina', 'máquina', 'hyundai', 'etork', 'equipamento', 'trator', 'locadora', 'obra', 'construtora', 'manutenção pesada', 'manutencao pesada'], 'name': 'Etork', 'url': 'https://etork.com.br/', 'buyer_context': 'Esse cliente atende compradores de máquinas, obras, manutenção e reposição técnica.'},
    {'keywords': ['automação', 'automacao', 'industrial', 'mro', 'técnico', 'tecnico', 'borracha', 'insumo industrial', 'manutenção industrial', 'manutencao industrial', 'fábrica', 'fabrica'], 'name': 'Akme Automação', 'url': 'https://portal.akmeautomacao.com.br/', 'buyer_context': 'Esse cliente atende indústrias, manutenção e compradores técnicos de insumos.'},
    {'keywords': ['pet', 'veterin', 'saúde animal', 'saude animal', 'agro', 'ração', 'racao', 'nutrição animal', 'nutricao animal', 'pet shop', 'clínica veterinária', 'clinica veterinaria'], 'name': 'Mouragro', 'url': 'https://loja.mouragro.com.br/', 'buyer_context': 'Esse cliente vende para pet shops, clínicas e compradores do agro/pet.'},
    {'keywords': ['cosmético', 'cosmetico', 'beleza', 'salão', 'salao', 'perfumaria', 'revenda', 'lojista de beleza', 'clínica estética', 'clinica estetica'], 'name': 'Provanza', 'url': 'https://lojista.provanza.com.br/', 'buyer_context': 'Esse cliente vende para revendas, salões e lojistas de beleza.'},
    {'keywords': ['impressão 3d', 'impressao 3d', 'filamento', '3d', 'tecnologia', 'maker', 'revenda de tecnologia'], 'name': 'Voolt3D Atacado', 'url': 'https://voolt3datacado.com.br/', 'buyer_context': 'Esse cliente vende para revendas e compradores técnicos de impressão 3D.'},
    {'keywords': ['telecom', 'fibra', 'provedor', 'infra', 'instalador', 'integrador'], 'name': 'Fibratech', 'url': 'https://lojafibratech.net.br/', 'buyer_context': 'Esse cliente vende para provedores, instaladores e integradores de telecom.'},
    {'keywords': ['limpeza', 'higiene', 'descartável', 'descartavel', 'saneante', 'zeladoria', 'condomínio', 'condominio', 'facilities'], 'name': 'Superlimp', 'url': 'https://loja.superlimp.com.br/', 'buyer_context': 'Esse cliente vende para empresas, condomínios e compradores de limpeza/facilities.'},
    {'keywords': ['plástico', 'plastico', 'embalagem', 'loja de embalagem', 'food service'], 'name': 'Lar Plásticos', 'url': 'https://parceiros.larplasticos.com.br/', 'buyer_context': 'Esse cliente atende lojistas, food service e compradores de embalagens.'},
    {'keywords': ['têxtil', 'textil', 'fiação', 'fiacao', 'confecção', 'confeccao', 'moda', 'camiseta', 'uniforme', 'facção', 'faccao', 'lojista de moda'], 'name': 'Fiação Itabaiana', 'url': 'https://compreonline.fiacaoitabaiana.com.br/', 'buyer_context': 'Esse cliente vende para confecções, lojistas e compradores do setor têxtil.'},
    {'keywords': ['esporte', 'padel', 'bullpadel', 'loja esportiva', 'artigo esportivo', 'artigos esportivos'], 'name': 'Bullpadel B2B', 'url': 'https://b2b.bullpadelbr.com/', 'buyer_context': 'Esse cliente vende para lojas, academias e pontos ligados a artigos esportivos.'},
    {'keywords': ['distribuidora', 'distribuição', 'distribuicao', 'atacado', 'atacadista', 'suprimento', 'revenda', 'lojista'], 'name': 'Stoky Distribuidora', 'url': 'https://stoky.com.br/', 'buyer_context': 'Esse cliente vende para lojistas, revendas e compradores recorrentes do atacado.'},
]
# Fallback autorizado pelo Rafael (28/06): se não souber o segmento, ainda usar
# um dos três portais abaixo para concretizar a experiência no Follow 1+.
FALLBACK_PORTAL_EXAMPLES = [
    {'name': 'Voolt3D Atacado', 'url': 'https://voolt3datacado.com.br/'},
    {'name': 'Stoky', 'url': 'https://stoky.com.br/'},
    {'name': 'Ceasa Mais', 'url': 'https://portal.ceasamais.com.br/'},
]

BUYER_PROFILE_TERMS = [
    'quem compra', 'comprador típico', 'comprador tipico', 'cliente comprador',
    'clientes compradores', 'vende para', 'atende ', 'abastece', 'fornece para',
    'restaurante', 'padaria', 'mercado', 'supermercado', 'pet shop', 'clínica',
    'clinica', 'oficina', 'auto center', 'revenda', 'lojista', 'loja de material',
    'material de construção', 'material de construcao', 'construtora', 'indústria',
    'industria', 'fábrica', 'fabrica', 'salão', 'salao', 'condomínio', 'condominio',
    'instalador', 'integrador', 'provedor', 'academia', 'clube', 'restaurantes',
    'padarias', 'pet shops', 'oficinas', 'revendas', 'lojistas', 'construtoras',
]


def now_brt():
    return datetime.now(BRT)


def next_sdr_sla_due(interaction_dt=None):
    """Rafael 29/06: Retorno Contato sem agenda tem SLA pelo próximo período útil."""
    dt = interaction_dt or datetime.now(timezone.utc)
    brt = dt.astimezone(BRT)
    if brt.hour < 12:
        due_brt = brt.replace(hour=14, minute=0, second=0, microsecond=0)
    else:
        due_brt = (brt + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        while due_brt.weekday() >= 5:
            due_brt += timedelta(days=1)
    return due_brt.astimezone(timezone.utc)


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


def phone_key_variants(phone_key):
    """Variações estáveis para dedupe WhatsApp BR com/sem 9º dígito.

    Incidente 30/06: o mesmo contato apareceu como 55+DDD+8 dígitos e depois
    55+DDD+9+8 dígitos. Sem essa equivalência, a lane achava que era lead novo.
    """
    k = ''.join(ch for ch in str(phone_key or '') if ch.isdigit())
    if k.startswith('55') and len(k) in (12, 13):
        k = k[2:]
    vals = {k} if k else set()
    if len(k) == 11 and k[2] == '9':
        vals.add(k[:2] + k[3:])
    elif len(k) == 10 and k[2] in '6789':
        vals.add(k[:2] + '9' + k[2:])
    return {v for v in vals if v}


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
            keys.update(phone_key_variants(key))
    raw = m.get('rawKey') or {}
    if isinstance(raw, dict):
        for field in ('remoteJid', 'remoteJidAlt', 'participant'):
            key = normalize_jid_phone(raw.get(field))
            if key:
                keys.update(phone_key_variants(key))
    return keys


def history_outgoing_for(phone_key, ports):
    out = []
    target_keys = phone_key_variants(phone_key)
    for m in load_history_messages(ports):
        if m.get('fromMe') is not True:
            continue
        if not (target_keys & message_phone_keys(m)):
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
    target_keys = phone_key_variants(phone_key)
    incoming = []
    for m in load_history_messages(ports):
        if m.get('fromMe') is True:
            continue
        if not (target_keys & message_phone_keys(m)):
            continue
        try:
            ts = float(m.get('timestamp') or 0)
        except Exception:
            ts = 0
        if ts and ts > cutoff + 60:
            incoming.append(m)
    incoming.sort(key=lambda x: float(x.get('timestamp') or 0))
    return incoming


def message_text(m):
    for key in ('text', 'body', 'caption'):
        val = m.get(key)
        if isinstance(val, str) and val.strip():
            return re.sub(r'\s+', ' ', val).strip()
    raw = m.get('raw') or m.get('message') or {}
    if isinstance(raw, dict):
        for key in ('conversation', 'extendedTextMessage', 'imageMessage', 'videoMessage'):
            val = raw.get(key)
            if isinstance(val, str) and val.strip():
                return re.sub(r'\s+', ' ', val).strip()
            if isinstance(val, dict):
                txt = val.get('text') or val.get('caption')
                if isinstance(txt, str) and txt.strip():
                    return re.sub(r'\s+', ' ', txt).strip()
    return ''


WEAK_RESPONSES = {'oi','olá','ola','bom dia','boa tarde','boa noite','ok','okk','obrigado','obrigada','sim','whatsapp','wpp','zap'}
EFFECTIVE_TERMS = (
    'faz sentido','quanto custa','preço','preco','valor','plano','ligar','ligação','ligacao',
    'agenda','agendar','reunião','reuniao','demonstração','demonstracao','proposta',
    'erp','bling','omie','tiny','sankhya','portal','pedido','vendedor','cliente','tabela',
    'restaurante','revenda','distribuidor','atacado','pode falar','contato dele','contato dela'
)


def is_effective_interaction(m):
    """Só evolui para Retorno Contato quando há interação efetiva com a cadência inicial."""
    text = message_text(m)
    low = re.sub(r'\s+', ' ', (text or '').lower()).strip()
    cleaned = re.sub(r'[^a-z0-9áàâãéêíóôõúç ]+', '', low).strip()
    if not cleaned:
        return False
    if cleaned in WEAK_RESPONSES or len(cleaned.split()) <= 2:
        return any(t in low for t in EFFECTIVE_TERMS)
    return True


def summarize_incoming_for_sdr(incoming):
    texts = []
    for m in (incoming or [])[-3:]:
        txt = message_text(m)
        if txt:
            texts.append(txt[:500])
    if not texts:
        return 'O lead respondeu/interagiu no WhatsApp, mas não consegui extrair texto. Abrir conversa antes de seguir.'
    return ('Resposta(s) do lead capturada(s) para o SDR começar pelo objetivo/expectativa dele: '
            + ' | '.join(texts)
            + '\nPróxima ação: não mandar novo follow automático; responder partindo do motivo do cadastro, expectativa com a Zydon e processo comercial atual.')


def envios_for_phone(envios, phone_key):
    out = []
    for r in envios:
        if not isinstance(r, dict):
            continue
        if str(r.get('msg_type') or '').lower() not in BLOCKING_MSG_TYPES:
            continue
        keys = set()
        for k in d.PHONE_FIELDS:
            keys.update(phone_key_variants(normalize_jid_phone(r.get(k))))
        if phone_key_variants(phone_key) & keys:
            ts = envio_ts(r)
            if ts:
                rr = dict(r)
                rr['_ts'] = ts
                out.append(rr)
    out.sort(key=lambda r: r['_ts'])
    return out


def prior_communicator_port_for_phone(envios, phone_key):
    """Mantém no máximo 1 comunicador por lead.

    Se qualquer contato anterior registrado para o telefone saiu por comunicador
    (diagnóstico, D0 ou cadência), reutilizar a mesma porta. Isso evita misturar
    Mariana + Gustavo + SDR no mesmo lead.
    """
    last = None
    for r in envios:
        if not isinstance(r, dict):
            continue
        keys = set()
        for k in d.PHONE_FIELDS:
            keys.update(phone_key_variants(normalize_jid_phone(r.get(k))))
        if not (phone_key_variants(phone_key) & keys):
            continue
        try:
            port = int(r.get('bridge_port') or 0)
        except Exception:
            continue
        if port not in COMMUNICATOR_PORTS:
            continue
        ts = envio_ts(r)
        if ts:
            last = (ts, port)
    return last[1] if last else None


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


def buscar_deals_primeiro_contato(owner_id, max_results=None):
    url = 'https://api.hubapi.com/crm/v3/objects/deals/search'
    page_limit = min(100, int(max_results or 100))
    body = {
        'filterGroups': [{'filters': [
            {'propertyName': 'pipeline', 'operator': 'EQ', 'value': PIPELINE},
            {'propertyName': 'dealstage', 'operator': 'EQ', 'value': STAGE_PRIMEIRO_CONTATO},
            {'propertyName': 'hubspot_owner_id', 'operator': 'EQ', 'value': owner_id},
        ]}],
        'properties': ['dealname', 'dealstage', 'hubspot_owner_id', 'createdate', 'notes_last_updated', 'notes_last_contacted', 'hs_latest_meeting_activity'],
        'limit': page_limit,
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
        if max_results and len(out) >= max_results:
            return out[:max_results]
        after = (res.get('paging') or {}).get('next', {}).get('after')
        if not after:
            break
    return out


# NOTE (Rafael 30/06): caminhos antigos removidos de propósito.
# As funções que adicionavam/removiam ponte com SDR responsável, telefone do
# consultor ou texto de "você já está falando com X da Zydon"
# (consultant_addendum, owner_phone_for_addendum, remove_sdr_bridge_mentions,
# prior_diagnostic_sent_by_owner_sdr, apply_diagnostic_sdr_context_bridge) foram
# eliminadas. O follow-up agora é EXCLUSIVAMENTE um dos 4 textos fixos do
# manifesto aprovado, sem addendum, sem ponte e sem CTA oculto. Não reintroduzir.


_RESEARCH_FOLLOWUPS = None
_RESEARCH_MATCH_MATRIX = None

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


GENERIC_COMPANY_TOKENS = {
    'distribuidora', 'distribuidor', 'industria', 'comercio', 'comercial', 'ltda',
    'eireli', 'me', 'epp', 'atacado', 'atacarejo', 'loja', 'shop', 'company',
    'brasil', 'grupo', 'na', 'de', 'da', 'do', 'das', 'dos', 'com'
}


def company_key_tokens(key):
    return {t for t in norm_key(key).split() if len(t) >= 3 and t not in GENERIC_COMPANY_TOKENS}


def research_key_matches(lead_key, research_key):
    """Match conservador para não puxar rascunho de outra empresa homônima/genérica.

    O bug de 29/06 veio de match por substring: "Na distribuidora" acabou
    reaproveitando rascunho de "Santana distribuidor" porque compartilhavam o
    termo genérico distribuidor/distribuidora. Agora só aceita exato ou interseção
    de token distintivo.
    """
    if not lead_key or not research_key:
        return False
    if lead_key == research_key:
        return True
    lt = company_key_tokens(lead_key)
    rt = company_key_tokens(research_key)
    if not lt or not rt:
        return False
    return bool(lt & rt) and (lead_key in research_key or research_key in lead_key or len(lt & rt) >= 2)


def researched_message_for(lead, attempt_number):
    empresa = lead.get('empresa') or ''
    key = norm_key(empresa)
    if not key:
        return ''
    research = load_researched_followups()
    if key in research and attempt_number in research[key]:
        return research[key][attempt_number]
    for rk, attempts in research.items():
        if attempt_number in attempts and research_key_matches(key, rk):
            return attempts[attempt_number]
    return ''


def all_researched_text_for_lead(lead):
    empresa = lead.get('empresa') or ''
    key = norm_key(empresa)
    if not key:
        return ''
    research = load_researched_followups()
    matches = []
    if key in research:
        matches.extend(research[key].values())
    for rk, attempts in research.items():
        if key != rk and research_key_matches(key, rk):
            matches.extend(attempts.values())
    matrix_txt = research_matrix_text(research_matrix_entry_for(lead))
    if matrix_txt:
        matches.append(matrix_txt)
    return '\n'.join(str(x) for x in matches if x)


def has_buyer_profile_evidence(text):
    haystack = norm_key(text)
    return bool(haystack and any(norm_key(term) in haystack for term in BUYER_PROFILE_TERMS))


def load_research_match_matrix():
    """Carrega a matriz machine-readable da pesquisa Claude.

    A partir de 30/06 os textos são fixos, então o markdown não traz mais um
    rascunho por lead em formato `Follow N ```...````. A evidência de estudo
    confiável vem do JSON `lead-match-matrix.json`, que lista deal_id, comprador,
    fontes, fit e bloqueios. Sem esse JSON ou com block_reason, o envio fica
    bloqueado por `--require-research`.
    """
    global _RESEARCH_MATCH_MATRIX
    if _RESEARCH_MATCH_MATRIX is not None:
        return _RESEARCH_MATCH_MATRIX
    out = {}
    base = ROOT / 'docs' / 'followup-research'
    matrices = sorted(base.glob('*/lead-match-matrix.json'), reverse=True)
    for matrix in matrices:
        try:
            data = json.loads(matrix.read_text(encoding='utf-8'))
        except Exception:
            continue
        for item in data.get('leads') or []:
            deal_id = str(item.get('deal_id') or '').strip()
            empresa_key = norm_key(item.get('empresa') or '')
            if deal_id:
                out.setdefault(('deal', deal_id), item)
            if empresa_key:
                out.setdefault(('empresa', empresa_key), item)
        if out:
            break
    _RESEARCH_MATCH_MATRIX = out
    return out


def research_matrix_entry_for(lead):
    matrix = load_research_match_matrix()
    deal_id = str((lead or {}).get('deal_id') or '').strip()
    if deal_id and ('deal', deal_id) in matrix:
        return matrix[('deal', deal_id)]
    key = norm_key((lead or {}).get('empresa') or '')
    if key and ('empresa', key) in matrix:
        return matrix[('empresa', key)]
    return None


def research_matrix_text(entry):
    if not entry:
        return ''
    parts = [
        entry.get('empresa'),
        entry.get('segment_match'),
        entry.get('buyer_profile'),
        ' '.join(entry.get('buyer_evidence') or []),
        entry.get('zydon_fit_reason'),
        entry.get('message_angle'),
        entry.get('portal_recommendation'),
    ]
    return '\n'.join(str(p) for p in parts if p)


def matrix_entry_has_usable_study(entry):
    if not entry or entry.get('block_reason'):
        return False
    q = entry.get('quality_gate') or {}
    return bool(q.get('has_source') and q.get('has_buyer') and q.get('not_generic') and q.get('no_sdr_bridge', True))


def lead_has_study(lead, attempt_number=None):
    """Exige estudo/contexto real antes de follow-up automático.

    Rafael 29/06: estudar a empresa antes do follow-up. Considera válido quando
    há rascunho pesquisado para a tentativa ou texto pesquisado com evidência de
    comprador/segmento; nome da empresa sozinho não basta.
    """
    attempt_number = int(attempt_number or lead.get('next_attempt') or 1)
    entry = research_matrix_entry_for(lead)
    if entry is not None:
        return matrix_entry_has_usable_study(entry)
    researched = researched_message_for(lead, attempt_number)
    if researched and has_buyer_profile_evidence(researched):
        return True
    all_text = all_researched_text_for_lead(lead)
    return bool(all_text and has_buyer_profile_evidence(all_text))


def portal_example_for(lead, researched_text=''):
    # Prioridade máxima: matriz pesquisada lead × portais Zydon permitidos.
    # Ela NÃO define texto de WhatsApp; só alimenta variáveis do manifesto aprovado
    # (portal_segmento, portal_url, portal_buyer_context) para Follow 1.
    entry = research_matrix_entry_for(lead)
    rec = (entry or {}).get('portal_recommendation') or {}
    if isinstance(rec, dict) and rec.get('url'):
        buyer_context = rec.get('buyer_context') or rec.get('portal_buyer_context')
        if not buyer_context:
            buyer_context = 'Esse cliente vende para compradores recorrentes no B2B.'
        return {
            'name': rec.get('name') or rec.get('portal_name') or 'Portal referência Zydon',
            'url': rec.get('url'),
            'buyer_context': buyer_context,
        }
    # Primeiro tenta portal parecido pelo contexto pesquisado. Rafael pediu
    # pesquisa de quem compra do lead antes de mandar link específico.
    # A empresa/nome do negócio também entra no contexto: ex. "Avena sports"
    # não pode cair em cosmético só porque a pesquisa falou genericamente em
    # revenda/lojista.
    research_context = '\n'.join([
        lead.get('empresa') or '',
        researched_text or '',
        all_researched_text_for_lead(lead),
    ])
    haystack = norm_key(research_context)
    if haystack and has_buyer_profile_evidence(research_context):
        # Overrides de segmento evitam falso positivo por palavra genérica como
        # revenda/lojista. Para roupa/moda/sports, nunca usar Provanza.
        apparel_terms = [
            'roupa', 'roupas', 'moda', 'vestuario', 'vestuario esportivo',
            'confecao', 'confeccao', 'textil', 'enxoval', 'uniforme',
            'camiseta', 'sports', 'sport', 'fitness wear', 'activewear'
        ]
        sports_terms = ['padel', 'tenis', 'artigo esportivo', 'artigos esportivos', 'sports', 'sport']
        # Se é roupa/sports, o exemplo aprovado é Bullpadel: portal B2B de
        # marca esportiva, mais próximo que Provanza/Fiação.
        if any(t in haystack for t in apparel_terms + sports_terms):
            for ex in PORTAL_PUBLIC_EXAMPLES:
                if ex['name'] == 'Bullpadel B2B':
                    return ex
        best = None
        best_score = 0
        for ex in PORTAL_PUBLIC_EXAMPLES:
            score = sum(1 for kw in ex['keywords'] if norm_key(kw) in haystack)
            # Evita escolher case especializado por termo genérico isolado.
            if ex['name'] == 'Provanza' and score == 1 and any(t in haystack for t in apparel_terms):
                score = 0
            if score > best_score:
                best = ex
                best_score = score
        if best:
            return best
    # Fallback controlado: se há estudo com evidência de comprador, mas nenhum
    # portal especializado pontuou, ainda usa link base real da carteira para
    # explicar visualmente a experiência. O texto de follow-up deve enquadrar como
    # exemplo de funcionamento, não como caso parecido do segmento.
    key = f"{lead.get('deal_id') or ''}|{lead.get('empresa') or ''}|{lead.get('jid') or ''}"
    idx = int(__import__('hashlib').sha256(key.encode()).hexdigest()[:8], 16) % len(FALLBACK_PORTAL_EXAMPLES)
    return FALLBACK_PORTAL_EXAMPLES[idx]


def text_has_url(text):
    return bool(re.search(r'https?://', str(text or ''), re.I))


def company_name_for_message(raw):
    empresa = str(raw or '').strip()
    low = norm_key(empresa)
    bad_exact = {'', 'sua', 'sem nome', 'none', 'null', 'nao usar', 'uso interno', 'uso iterno', 'verificar', 'empresa', 'teste', 'lead'}
    if low in bad_exact or len(low) <= 2:
        return ''
    if any(term in low for term in ('nao usar', 'uso interno', 'uso iterno', 'verificar telefone', 'teste ')):
        return ''
    alnum = ''.join(ch for ch in empresa if ch.isalnum())
    if len(alnum) <= 2 or set(empresa) <= {'.', '-', '_', ' '}:
        return ''
    return empresa


def _approval_norm(text):
    text = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode('ascii')
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# Tentativas válidas da régua fixa. Não existe Follow 0 nem Follow 5+.
APPROVED_FOLLOWUP_ATTEMPTS = (1, 2, 3, 4)

# Únicas variáveis que o código pode substituir nos textos do manifesto.
# Qualquer outro placeholder no manifesto é tratado como adulteração e bloqueia.
APPROVED_FOLLOWUP_VARS = ('nome', 'empresa', 'portal_segmento', 'portal_url', 'portal_buyer_context')

# Saudação fixa que abre os 4 textos aprovados. Usada só para classificar texto
# claramente antigo/fora do padrão na mensagem de bloqueio do gate.
APPROVED_FOLLOWUP_GREETING_MARKERS = ('boa tarde', 'tudo bem')


def _approved_manifest_texts():
    """Carrega o manifesto imutável dos 4 follow-ups aprovados por Rafael (30/06)
    e verifica a integridade contra o sha256 declarado no próprio arquivo.

    Fail-closed: qualquer problema (arquivo ausente, JSON quebrado, texto sem
    hash declarado ou texto divergente do hash) levanta exceção. Os chamadores no
    caminho de envio capturam e BLOQUEIAM. Nunca cair em texto antigo/alternativo.
    """
    data = json.loads(APPROVED_FOLLOWUP_MANIFEST.read_text(encoding='utf-8'))
    texts = data.get('texts') or {}
    declared = data.get('sha256') or {}
    if not texts:
        raise ValueError('manifesto sem textos aprovados')
    for attempt in APPROVED_FOLLOWUP_ATTEMPTS:
        key = f'follow{attempt}'
        tmpl = texts.get(key)
        if not tmpl or not str(tmpl).strip():
            raise ValueError(f'manifesto sem texto para {key}')
        want = declared.get(key)
        if not want:
            raise ValueError(f'manifesto sem sha256 declarado para {key}')
        got = hashlib.sha256(str(tmpl).encode('utf-8')).hexdigest()
        if got != want:
            raise ValueError(f'{key} diverge do sha256 aprovado (manifesto adulterado)')
    return texts


def portal_segmento_label(portal):
    name = (portal or {}).get('name') or ''
    buyer = (portal or {}).get('buyer_context') or ''
    if name == 'Bullpadel B2B' or 'artigos esportivos' in buyer.lower():
        return 'artigos esportivos'
    if name == 'Ceasa Mais' or 'food service' in buyer.lower():
        return 'food service / distribuição de alimentos'
    if 'auto' in buyer.lower() or 'automotiva' in buyer.lower():
        return 'autopeças e reposição automotiva'
    if 'beleza' in buyer.lower():
        return 'beleza e revenda'
    if 'pet' in buyer.lower() or 'agro' in buyer.lower():
        return 'pet/agro'
    if 'têxtil' in buyer.lower() or 'textil' in buyer.lower():
        return 'têxtil/moda'
    if 'atacado' in buyer.lower() or 'revendas' in buyer.lower():
        return 'atacado e revenda'
    return 'B2B parecida'


def _render_approved_template(attempt, lead=None):
    """Renderiza UM dos 4 follow-ups fixos substituindo SOMENTE as variáveis do
    manifesto (APPROVED_FOLLOWUP_VARS): nome, empresa, portal_segmento,
    portal_url, portal_buyer_context.

    Não gera variação, não anexa parágrafo, não muda ordem, não injeta CTA. Se a
    tentativa for inválida ou o manifesto estiver ausente/quebrado/adulterado,
    levanta exceção (fail-closed) — quem está no caminho de envio bloqueia.
    """
    attempt = int(attempt)
    if attempt not in APPROVED_FOLLOWUP_ATTEMPTS:
        raise ValueError(f'tentativa inválida para follow-up fixo: {attempt}')
    texts = _approved_manifest_texts()
    tmpl = texts[f'follow{attempt}']
    lead = lead or {}
    nome = (lead.get('nome') or 'André').strip().split()[0] or 'André'
    nome = nome[:1].upper() + nome[1:].lower()
    empresa = company_name_for_message(lead.get('empresa')) or 'sua empresa'
    portal = portal_example_for(lead) if attempt == 1 else {}
    portal_url = (portal or {}).get('url') or ''
    portal_buyer_context = (portal or {}).get('buyer_context') or 'Esse cliente vende para compradores recorrentes no B2B.'
    portal_segmento = portal_segmento_label(portal)
    variables = {
        'nome': nome,
        'empresa': empresa,
        'portal_url': portal_url,
        'portal_buyer_context': portal_buyer_context,
        'portal_segmento': portal_segmento,
    }
    # Trava de variáveis: só os campos permitidos podem aparecer no manifesto.
    # Qualquer placeholder estranho gera KeyError no format e bloqueia o envio.
    rendered = tmpl.format(**variables)
    if '{' in rendered or '}' in rendered:
        raise ValueError(f'follow{attempt} ainda tem placeholder não substituído após render')
    return rendered


def sender_first_name(sender_name):
    name = str(sender_name or '').strip()
    if not name:
        return 'Rafael'
    return name.split()[0]


def presentation_line_for_sender(sender_name):
    return f"{sender_first_name(sender_name)} da Zydon aqui, plataforma de ecommerce B2B."


def add_presentation_if_needed(text, sender_name):
    """Se o remetente/chip não tem histórico com o lead, apresenta antes do follow.

    Rafael 30/06: seja qual follow for, se a pessoa não tiver histórico com o lead,
    precisa se apresentar: "Rafael da Zydon aqui, plataforma de ecommerce B2B".
    Mantém a saudação como 1ª bolha e coloca a apresentação no começo da 2ª.
    """
    line = presentation_line_for_sender(sender_name)
    raw = str(text or '').strip()
    if not raw or 'plataforma de ecommerce b2b' in _approval_norm(raw):
        return raw
    paras = [p.strip() for p in re.split(r'\n\s*\n+', raw) if p.strip()]
    if not paras:
        return line
    if len(paras) == 1:
        return paras[0] + '\n\n' + line
    return '\n\n'.join([paras[0], line] + paras[1:])


def _strip_optional_presentation_for_gate(text):
    paras = [p.strip() for p in re.split(r'\n\s*\n+', str(text or '').strip()) if p.strip()]
    out = []
    for p in paras:
        n = _approval_norm(p)
        n_clean = re.sub(r'[^a-z0-9áàâãéêíóôõúç ]+', ' ', n)
        n_clean = ' '.join(n_clean.split())
        if 'da zydon aqui plataforma de ecommerce b2b' in n_clean:
            continue
        out.append(p)
    return '\n\n'.join(out)


def sender_has_outgoing_history_with_lead(lead, sender):
    try:
        port = int((sender or {}).get('port') or 0)
    except Exception:
        port = 0
    if not port:
        return False
    phone_key = normalize_jid_phone((lead or {}).get('jid'))
    if not phone_key:
        return False
    return bool(history_outgoing_for(phone_key, [port]))


def approved_followup_template_gate(text, attempt_number, lead=None):
    """Gate fail-closed: só os 4 textos fixos do manifesto aprovado por Rafael
    (30/06) podem ser enviados. Chamado imediatamente antes de cada envio.

    Bloqueia (envia (False, motivo)) se:
      - tentativa for inválida (fora de 1-4);
      - manifesto estiver ausente/quebrado/adulterado (sha256 não confere);
      - o texto renderizar vazio;
      - Follow 3 vier com estrofe duplicada;
      - o texto divergir, em qualquer caractere, do manifesto após substituir
        apenas as variáveis permitidas.

    O único texto que passa é exatamente o render do manifesto. Não há lista de
    "modelos antigos" porque qualquer coisa que não seja o manifesto é rejeitada.
    """
    attempt = int(attempt_number or 0)
    if attempt not in APPROVED_FOLLOWUP_ATTEMPTS:
        return False, f'tentativa inválida: {attempt_number}'
    try:
        expected = _render_approved_template(attempt, lead)
    except Exception as exc:
        return False, f'manifesto de textos aprovados indisponível/inválido (fail-closed): {exc}'
    if not (expected or '').strip():
        return False, 'manifesto retornou texto vazio (fail-closed)'
    norm_text = _approval_norm(_strip_optional_presentation_for_gate(text))
    norm_expected = _approval_norm(expected)
    if not norm_text:
        return False, 'texto vazio'
    # Trava específica do Follow 3: estrofe da pergunta principal não pode repetir.
    if attempt == 3 and norm_text.count('quando o seu cliente vai fazer um pedido') != 1:
        return False, 'Follow 3 com estrofe duplicada'
    if norm_text == norm_expected:
        return True, 'ok'
    # Texto que nem começa com a saudação fixa é claramente antigo/fora do padrão.
    if any(marker not in norm_text for marker in APPROVED_FOLLOWUP_GREETING_MARKERS):
        return False, f'texto antigo/não aprovado: Follow {attempt} não segue o manifesto'
    return False, f'Follow {attempt} não bate exatamente com o manifesto aprovado por Rafael'


def extract_message_variation(lead, attempt_number, sender=None):
    """Retorna SOMENTE o follow-up fixo do manifesto aprovado por Rafael (30/06).

    Sem variações, sem modelos antigos, sem anexos/CTAs extras. As únicas
    substituições são as variáveis do manifesto (nome, empresa, portal_segmento,
    portal_url, portal_buyer_context). O parâmetro `sender` é mantido apenas por
    compatibilidade de assinatura — ele NÃO altera o texto (o remetente não muda
    nem uma vírgula da mensagem). É um único caminho de geração de texto.
    """
    return _render_approved_template(attempt_number, lead)


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


def current_deal_stage(deal_id):
    if not deal_id:
        return ''
    try:
        res = d.hs_request(
            f'https://api.hubapi.com/crm/v3/objects/deals/{deal_id}?properties=dealstage',
            'GET',
        )
        return str(((res or {}).get('properties') or {}).get('dealstage') or '')
    except Exception:
        return ''


def current_deal_operational_state(deal_id):
    """Lê a etapa ao vivo antes de qualquer envio externo.

    Regra Rafael: se o SDR/HubSpot mandou o negócio para Perdido, a automação
    não pode retomar pelo WhatsApp em sequência. Fail-closed se não conseguir
    consultar, para evitar mandar por cima de uma decisão humana recente.
    """
    if not deal_id:
        return {'ok': False, 'stage': '', 'pipeline': '', 'reason': 'deal_id ausente'}
    try:
        res = d.hs_request(
            f'https://api.hubapi.com/crm/v3/objects/deals/{deal_id}?properties=dealstage,pipeline,closedate,closed_lost_reason',
            'GET',
        )
        props = (res or {}).get('properties') or {}
        return {
            'ok': True,
            'stage': str(props.get('dealstage') or ''),
            'pipeline': str(props.get('pipeline') or ''),
            'closedate': str(props.get('closedate') or ''),
            'closed_lost_reason': str(props.get('closed_lost_reason') or ''),
        }
    except Exception as e:
        return {'ok': False, 'stage': '', 'pipeline': '', 'reason': str(e)[:180]}


def should_block_automation_for_deal_state(state, *, allowed_stages=None):
    allowed = set(str(x) for x in (allowed_stages or [STAGE_PRIMEIRO_CONTATO]))
    if not state.get('ok'):
        return True, f"bloqueado fail-closed: não consegui confirmar etapa ao vivo ({state.get('reason') or 'sem motivo'})"
    stage = str(state.get('stage') or '')
    if stage == STAGE_PERDIDO:
        return True, 'bloqueado: negócio está em Perdido no HubSpot'
    if stage not in allowed:
        label = STAGE_LABELS.get(stage, stage or 'sem etapa')
        return True, f'bloqueado: negócio não está mais na etapa permitida ({label})'
    return False, ''


def deal_still_in_primeiro_contato(deal_id):
    return current_deal_stage(deal_id) == STAGE_PRIMEIRO_CONTATO


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


def mark_return_contact(lead, reasons=None, incoming=None):
    effective_incoming = [m for m in (incoming or []) if is_effective_interaction(m)]
    if not effective_incoming:
        return None
    last_ts = None
    try:
        ts = float(effective_incoming[-1].get('timestamp') or 0)
        if ts > 10_000_000_000:
            ts = ts / 1000.0
        if ts:
            last_ts = datetime.fromtimestamp(ts, timezone.utc)
    except Exception:
        last_ts = None
    due_dt = next_sdr_sla_due(last_ts)
    move_deal_stage(lead['deal_id'], STAGE_RETORNO_CONTATO)
    body_txt = [
        'Lead interagiu de forma efetiva com as informações enviadas na cadência inicial. Movido para Retorno Contato.',
        f"Lead: {lead.get('nome') or ''} / {lead.get('empresa') or ''}",
        f"Deal: {lead.get('deal_id')}",
        f"Contato: {lead.get('contact_id')}",
        f"SLA SDR: tarefa aberta para {due_dt.astimezone(BRT).strftime('%d/%m/%Y %H:%M BRT')}",
    ]
    if reasons:
        body_txt.append('Motivos: ' + '; '.join(reasons[:5]))
    body_txt.extend(['', summarize_incoming_for_sdr(effective_incoming)])
    body_txt.append('Próxima ação SDR: abrir o histórico, considerar todo o contexto do que foi falado e conduzir para agenda se fizer sentido.')
    body = {
        'properties': {
            'hs_timestamp': due_dt.isoformat().replace('+00:00', 'Z'),
            'hs_task_subject': 'Entrar em contato — lead interagiu com a cadência inicial',
            'hs_task_body': '\n'.join(body_txt),
            'hs_task_status': 'NOT_STARTED',
            'hs_task_priority': 'HIGH',
            'hubspot_owner_id': str(lead.get('owner_id') or ''),
        },
        'associations': [
            {'to': {'id': int(lead['contact_id'])}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 204}]},
            {'to': {'id': int(lead['deal_id'])}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 216}]},
        ],
    }
    try:
        res = d.hs_request('https://api.hubapi.com/crm/v3/objects/tasks', 'POST', body)
        task_id = res.get('id') if res else None
    except Exception:
        task_id = None
    append_metric({**lead, 'event': 'moved_retorno_contato', 'task_id': task_id, 'reasons': reasons or [], 'sla_due': due_dt.astimezone(BRT).isoformat(), 'date_tz': now_brt().isoformat()})
    return task_id



def mark_lost_after_4(lead):
    if not deal_still_in_primeiro_contato(lead.get('deal_id')):
        append_metric({**lead, 'event': 'skip_lost_stage_changed', 'date_tz': now_brt().isoformat()})
        return None
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
        routing_decision = None
        try:
            from scripts.whatsapp_dispatch_queue import load_dispatches  # import local evita ciclo em testes
            dispatches = load_dispatches()
        except Exception:
            dispatches = None
        try:
            routing_decision = choose_outbound_port(
                lead.get('owner_key') or lead.get('owner_name'),
                lead.get('jid'),
                lead_key=lead.get('deal_id') or lead.get('contact_id') or lead.get('jid'),
                rows=envios,
                dispatches=dispatches,
            )
        except Exception:
            routing_decision = None
        if routing_decision and routing_decision.get('mode') in {'blocked_private_target', 'active_contact_conflict'}:
            return None, [routing_decision.get('reason') or routing_decision.get('mode')]
        routed_port = routing_decision.get('port') if routing_decision else None
        if routed_port and int(routed_port) not in disabled_ports:
            sender_phone = ''
            sender_label = lead['owner_name']
            try:
                with urllib.request.urlopen(urllib.request.Request(f'http://localhost:{int(routed_port)}/me'), timeout=5) as resp:
                    me = json.loads(resp.read().decode())
                sender_phone = str(me.get('phone') or me.get('id') or '')
                sender_label = str(me.get('name') or lead['owner_name'])
            except Exception:
                pass
            sender = bridge_sender_for_lead(lead, int(routed_port), sender_label, sender_phone)
            if isinstance(sender, dict):
                sender['routing_mode'] = routing_decision.get('mode')
                sender['routing_reason'] = routing_decision.get('reason')
            return sender, None
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

    # Rafael: usar comunicadores para expandir limite, principalmente nos follow-ups.
    # Regra dura 28/06: por lead, no máximo 1 comunicador + o SDR dono.
    # Se já houve diagnóstico/D0/follow por comunicador, reutilizar o mesmo comunicador.
    # Se ainda não houve comunicador, distribuir em round-robin pelos comunicadores ativos.
    # Follow-up por comunicador NÃO inclui ponte com SDR responsável; ponte fica só no diagnóstico.
    if use_communicators:
        prior_comm = lead.get('prior_communicator_port')
        # Regra Rafael: aproveitar todos os chips, mas manter APENAS 1 comunicador por lead.
        # Se o lead já tem comunicador anterior, só essa porta pode continuar.
        # Se a lane atual é outra porta, pula o lead e procura outro candidato.
        if prior_comm:
            try:
                prior_port = int(prior_comm)
            except Exception:
                prior_port = 0
            if communicator_ports and prior_port not in set(int(p) for p in communicator_ports):
                return None, [f'lead já tem comunicador {prior_port}; mantendo um único comunicador por lead']
            effective_ports = [prior_port]
        else:
            effective_ports = communicator_ports
        pool = [s for s in active_communicator_senders(effective_ports) if s['port'] not in disabled_ports]
        if pool:
            s = pool[rr_index % len(pool)]
            return bridge_sender_for_lead(lead, s['port'], s['sender_name'], s.get('sender_phone') or ''), None

    return owner_sender()


def collect_candidates(move_interacted=False, owner_keys=None, max_deals_per_owner=None, require_research=False):
    envios = d.load_envios()
    now_utc = datetime.now(timezone.utc)
    stats = {}
    candidates = []
    nurture_due = []
    blocked_examples = []
    owners_to_scan = tuple(owner_keys or OWNER_KEYS)

    for owner_key in owners_to_scan:
        bridge = d.BRIDGES[owner_key]
        owner_id = bridge['owner_id']
        owner_name = bridge['owner_name']
        ports = bridge.get('ports') or [bridge['port']]
        deals = buscar_deals_primeiro_contato(owner_id, max_results=max_deals_per_owner)
        s = {'deals_primeiro_contato': len(deals), 'sem_contato': 0, 'sem_tel': 0, 'sem_d0': 0,
             'respondidos_interagidos': 0, 'nao_venceu_janela': 0, 'prontos_cadencia': 0, 'prontos_nutricao': 0}
        for deal in deals:
            deal_id = str(deal.get('id'))
            props = deal.get('properties') or {}
            if require_research and not matrix_entry_has_usable_study(research_matrix_entry_for({'deal_id': deal_id, 'empresa': props.get('dealname') or ''})):
                continue
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
            prior_communicator_port = prior_communicator_port_for_phone(envios, phone_key)
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
                    'vende_em_loja_virtual': cprops.get('vende_em_loja_virtual_') or '',
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
                    'prior_communicator_port': prior_communicator_port,
                    'prior_had_link': False,
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
            incoming_all = history_incoming_after(phone_key, first_ts, sorted(related_ports))
            incoming = [m for m in incoming_all if is_effective_interaction(m)]
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
                    mark_return_contact(lead_for_move, reasons, incoming=incoming)
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
                'vende_em_loja_virtual': cprops.get('vende_em_loja_virtual_') or '',
                'tel': tel_raw,
                'jid': jid,
                'tel_fmt': tel_fmt,
                'attempt_count': attempt_count,
                'prior_communicator_port': prior_communicator_port,
                'first_ts': first_ts.isoformat(),
                'last_ts': last_ts.isoformat(),
                'days_since_first': round(days_since_first, 2),
                'hours_since_last': round(hours_since_last, 2),
                'agenda': owner_agenda(owner_key),
                'prior_had_link': any(text_has_url(r.get('text') or r.get('body') or r.get('message_text') or r.get('message') or '') for r in related),
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


LEAD_LOCK_DIR = Path('/tmp/zydon_followup_lead_locks')
_HELD_LEAD_LOCKS = []


def acquire_lead_send_lock(jid: str, deal_id: str = ''):
    """Lock por lead/telefone para permitir lanes paralelas por chip sem duplicar.

    O lock global serializa tudo e é seguro, mas lento demais para F2/F3 splitado.
    Em modo paralelo, cada chip roda uma lane; este lock impede que duas lanes
    escolham e enviem para o mesmo telefone ao mesmo tempo.
    """
    LEAD_LOCK_DIR.mkdir(parents=True, exist_ok=True)
    key = normalize_jid_phone(jid) or str(deal_id or '')
    if not key:
        return None
    lock_path = LEAD_LOCK_DIR / (hashlib.sha256(key.encode()).hexdigest() + '.lock')
    fh = open(lock_path, 'w')
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fh.close()
        return None
    fh.write(f"pid={os.getpid()} jid={jid} deal={deal_id} at={datetime.now(timezone.utc).isoformat()}\n")
    fh.flush()
    _HELD_LEAD_LOCKS.append(fh)
    return fh


def release_lead_send_lock(fh):
    if not fh:
        return
    try:
        fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()
    except Exception:
        pass
    try:
        _HELD_LEAD_LOCKS.remove(fh)
    except ValueError:
        pass


def cadence_send_window(dt=None):
    """Janela dura de envio da cadência.

    Mesmo em execução manual, não enviar fim de semana nem fora da janela operacional.
    Cron também bloqueia, mas a trava no script evita bypass acidental.
    """
    dt = dt or now_brt()
    dow = dt.weekday()  # segunda=0
    if dow >= 5:
        return False
    # Regra firme Rafael 30/06: follows podem rodar até 20:00 BRT.
    # Implementação: janela inclusiva até 19:59; a partir de 20:00 bloqueia.
    if dt.hour < 6 or dt.hour >= 20:
        return False
    return True


def cadence_sequence_options(attempt_no):
    attempt_no = int(attempt_no or 1)
    final_pause = 480.0 if attempt_no == 2 else (240.0 if attempt_no in (1, 3) else 60.0)
    max_parts = 4 if attempt_no == 3 else 3
    if attempt_no == 3:
        delay_schedule = [12.0, 240.0, 240.0]
    elif attempt_no == 4:
        delay_schedule = [12.0, 360.0]
    else:
        delay_schedule = None
    return max_parts, final_pause, delay_schedule


def enqueue_worker_owned_cadence(lead, sender, text):
    attempt_no = int((lead or {}).get('next_attempt') or 1)
    max_parts, final_pause, custom_delay = cadence_sequence_options(attempt_no)
    parts = d.split_whatsapp_text(text, max_parts=max_parts)
    if custom_delay is not None:
        delay_schedule = custom_delay[:max(0, len(parts) - 1)]
        if len(delay_schedule) < max(0, len(parts) - 1):
            delay_schedule.extend([60.0] * (len(parts) - 1 - len(delay_schedule)))
    else:
        delay_schedule = [d.delay_before_next_part(i, len(parts), pause_seconds=12.0, final_pause_seconds=final_pause) for i in range(1, len(parts))]
    sender = sender or {}
    res = record_dispatch_worker_owned(
        origin='followup',
        nature=f'followup_f{attempt_no}',
        thread_state='cold_outreach',
        to=lead['jid'],
        text=text,
        owner_uid=sender.get('owner_uid') or lead.get('owner_key') or lead.get('owner_name'),
        lead_key=lead.get('deal_id') or lead.get('contact_id') or lead['jid'],
        port=sender.get('port'),
        sender_role=sender.get('sender_name') or sender.get('name') or lead.get('owner_name'),
        completion_type='followup_cadence',
        parts=parts,
        delay_schedule=delay_schedule,
        deal_id=lead.get('deal_id'),
        contact_id=lead.get('contact_id'),
        owner_id=lead.get('owner_id'),
        owner_name=lead.get('owner_name'),
        owner_key=lead.get('owner_key'),
        lead_name=lead.get('nome'),
        nome=lead.get('nome'),
        empresa=lead.get('empresa'),
        slug=d.slugify(lead.get('empresa') or ''),
        phone=lead.get('tel'),
        tel_fmt=lead.get('tel_fmt'),
        sender_name=sender.get('sender_name') or sender.get('name') or lead.get('owner_name'),
        sender_phone=sender.get('sender_phone'),
        sender_is_communicator=bool(sender.get('is_communicator')),
        campaign_id='cadencia_primeiro_contato_sem_resposta',
        msg_type=CADENCE_MSG_TYPE,
        attempt_number=attempt_no,
    )
    return {'ok': bool(res.get('ok')), 'deduped': bool(res.get('deduped')), 'dispatch_id': res.get('dispatch_id'), 'skipped': res.get('skipped'), 'reason': res.get('reason')}


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
    ap.add_argument('--scan-max-deals', type=int, default=25, help='limite de deals por owner escaneados por tick; evita timeout e mantém cron incremental')
    ap.add_argument('--stop-after-sent', type=int, default=0, help='em lanes paralelas, varre até --limit candidatos mas encerra após N envios confirmados')
    args = ap.parse_args()

    if args.send and not args.require_research:
        print('BLOQUEADO: --send exige --require-research. Follow-up automático só roda com estudo/pesquisa prévia para evitar portal genérico.')
        return 2
    if args.send and not cadence_send_window():
        print('BLOQUEADO: fora da janela operacional da cadência (seg-sex 06:00-19:59 BRT; para às 20:00).')
        return 2

    worker_owned = str(os.environ.get('ZYDON_CADENCIA_WORKER_OWNED') or '').lower() in {'1', 'true', 'yes', 'on'}
    if args.send and not worker_owned and not os.environ.get('ZYDON_PARALLEL_FOLLOWUP_LANES') and not acquire_global_send_lock(blocking=False):
        print('Lock global de envio ocupado; pulando cadência para evitar sobreposição de mensagens/chips.')
        return 0
    owner_keys_filter = None if args.owner == 'all' else [args.owner]
    if args.json:
        noise = io.StringIO()
        with contextlib.redirect_stdout(noise):
            candidates, nurture_due, stats, blocked_examples = collect_candidates(move_interacted=bool(args.send or args.mark_nurture), owner_keys=owner_keys_filter, max_deals_per_owner=args.scan_max_deals, require_research=args.require_research)
    else:
        candidates, nurture_due, stats, blocked_examples = collect_candidates(move_interacted=bool(args.send or args.mark_nurture), owner_keys=owner_keys_filter, max_deals_per_owner=args.scan_max_deals, require_research=args.require_research)
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
        candidates = [c for c in candidates if lead_has_study(c, int(c.get('next_attempt') or 1))]

    def candidate_gate_preview(c, preview_sender=None):
        try:
            text = extract_message_variation(c, c['next_attempt'], preview_sender)
        except Exception as exc:
            return {'gate_ok': False, 'gate_reason': f'manifesto indisponível/inválido (fail-closed): {exc}', 'text': ''}
        gate_ok, gate_reason = approved_followup_template_gate(text, c['next_attempt'], c)
        return {'gate_ok': bool(gate_ok), 'gate_reason': gate_reason, 'text': text if gate_ok else ''}

    cadence_preview = []
    for i, c in enumerate(candidates[:args.limit], 1):
        preview_sender = None
        if args.use_comunicadores:
            pool = active_communicator_senders(args.comunicador_port or None)
            if pool:
                preview_sender = pool[(i - 1) % len(pool)]
        row = dict(c)
        row['preview_index'] = i
        row.update(candidate_gate_preview(c, preview_sender))
        cadence_preview.append(row)

    summary = {
        'generated_at_brt': now_brt().isoformat(),
        'stats': stats,
        'cadence_ready': len(candidates),
        'nurture_ready': len(nurture_due),
        'blocked_examples': blocked_examples,
        'cadence_preview': cadence_preview,
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
        for row in cadence_preview:
            print(f"\n[{row.get('preview_index')}] {row['owner_name']} tentativa {row['next_attempt']}/{MAX_ATTEMPTS} | {row['nome']} | {row['empresa']} | {row['tel_fmt']} | D+{row['days_since_first']} | última {row['hours_since_last']}h")
            if not row.get('gate_ok'):
                print(f"BLOQUEADO gate texto aprovado F{row['next_attempt']}: {row.get('gate_reason')}")
                continue
            print(row.get('text') or '')
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
    # Em lanes paralelas por chip, --limit é limite de varredura padrão, mas quando
    # --stop-after-sent=1 cada lane precisa conseguir pular candidatos de outros
    # comunicadores até achar um lead do próprio chip. Se cortar nos primeiros 12,
    # as lanes ficam vivas mas não enviam nada.
    send_candidates = candidates if args.stop_after_sent else candidates[:args.limit]
    for idx, lead in enumerate(send_candidates, 1):
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
        # Geração protegida: se o manifesto sumir/adulterar, isto vira um bloqueio
        # por lead (fail-closed) em vez de derrubar o lote inteiro com traceback.
        try:
            text = extract_message_variation(lead, lead['next_attempt'], sender)
        except Exception as exc:
            print(f"BLOQUEADO gate texto aprovado F{lead['next_attempt']}: {lead['empresa']} {lead['tel_fmt']} | manifesto indisponível/inválido (fail-closed): {exc}")
            continue
        if not sender_has_outgoing_history_with_lead(lead, sender):
            text = add_presentation_if_needed(text, sender_label)
        gate_ok, gate_reason = approved_followup_template_gate(text, lead['next_attempt'], lead)
        if not gate_ok:
            print(f"BLOQUEADO gate texto aprovado F{lead['next_attempt']}: {lead['empresa']} {lead['tel_fmt']} | {gate_reason}")
            continue
        # Trava final simples: a lista foi montada a partir de Primeiro Contato,
        # mas o card pode ter mudado enquanto o cron preparava envio. Se saiu da
        # etapa, não manda follow-up nem marca perdido.
        if not deal_still_in_primeiro_contato(lead.get('deal_id')):
            print(f"PULADO etapa mudou antes do envio: {lead['empresa']} deal={lead['deal_id']}")
            continue
        # Lock por lead/telefone antes da última checagem. Em lanes paralelas,
        # outra porta pode ter selecionado o mesmo candidato no mesmo segundo;
        # quem não pegar o lock pula para o próximo sem enviar.
        lead_lock = acquire_lead_send_lock(lead['jid'], lead.get('deal_id') or '')
        if not lead_lock:
            print(f"PULADO lock paralelo ativo para lead: {lead['empresa']} {lead['tel_fmt']}")
            continue
        # Recheca o ledger compartilhado imediatamente antes de enviar. Se outro
        # cron acabou de mandar diagnóstico/primeiro contato/follow-up para o mesmo
        # telefone enquanto esta lista era montada, pula sem enviar.
        fresh_envios = d.load_envios()
        phone_key = normalize_jid_phone(lead['jid'])
        # Fail-safe real: ledger só grava no final da sequência splitada. Em paralelo,
        # outra lane pode já ter mandado saudação/parte 2 no WhatsApp e ainda não ter
        # ledger. Se houver qualquer follow ativo/recente hoje no histórico real, pula.
        today_start = now_brt().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        recent_real_follow = []
        for hm in history_outgoing_for(phone_key, COMMUNICATOR_PORTS):
            try:
                hts = float(hm.get('timestamp') or 0)
            except Exception:
                hts = 0
            if hts < today_start:
                continue
            htxt = (message_text(hm) or '').lower()
            if any(marker in htxt for marker in (
                'bom dia', 'boa tarde', 'boa noite',
                'a maioria das indústrias que chegam aqui trava',
                'faz sentido bater um papo rápido',
                'cada cliente seu enxerga a tabela comercial',
                'separei um portal real',
            )):
                recent_real_follow.append(hm)
        if recent_real_follow:
            print(f"PULADO histórico real WhatsApp hoje antes do ledger: {lead['empresa']} {lead['tel_fmt']} ({len(recent_real_follow)} msgs)")
            release_lead_send_lock(lead_lock)
            continue
        fresh_related = envios_for_phone(fresh_envios, phone_key)
        fresh_attempt_count = len([r for r in fresh_related if str(r.get('msg_type') or '').lower() != NURTURE_MSG_TYPE])
        if fresh_attempt_count >= int(lead['next_attempt']):
            print(f"PULADO ledger recente antes do envio: {lead['empresa']} {lead['tel_fmt']} tentativa já registrada ({fresh_attempt_count})")
            release_lead_send_lock(lead_lock)
            continue
        live_state = current_deal_operational_state(lead.get('deal_id'))
        blocked_state, blocked_reason = should_block_automation_for_deal_state(live_state)
        if blocked_state:
            print(f"PULADO etapa HubSpot ao vivo antes do envio: {lead['empresa']} {lead['tel_fmt']} | {blocked_reason}")
            append_metric({**lead, 'event': 'skip_live_deal_stage_block', 'stage': live_state.get('stage'), 'reason': blocked_reason, 'date_tz': now_brt().isoformat()})
            release_lead_send_lock(lead_lock)
            continue
        port_ok, port_reason = d.port_within_external_limits(fresh_envios, port, max_per_hour=args.max_per_port_hour, max_per_day=args.max_per_port_day)
        if not port_ok:
            # Rafael liberou em 29/06 ultrapassar o teto diário nos comunicadores
            # Mariana (4600), Lucas Resende (4606) e Rafael (4607) para não travar
            # a régua 1/2/3/4. Mantemos o teto por hora para não empilhar mensagens.
            override_daily_ports = {4600, 4606, 4607}
            hour_count = d.envios_porta_periodo(fresh_envios, port, seconds=3600)
            if port in override_daily_ports and hour_count < args.max_per_port_hour:
                print(f"AVISO limite diário liberado por Rafael: {port_reason} | seguindo no chip {port}")
            else:
                print(f"PULADO limite global do chip: {port_reason} | {lead['empresa']} {lead['tel_fmt']}")
                release_lead_send_lock(lead_lock)
                continue
        print(f"ENVIANDO [{idx}] {lead['owner_name']} via {sender_label} porta {port} tentativa {lead['next_attempt']} -> {lead['empresa']} {lead['tel_fmt']}")
        attempt_no = int(lead.get('next_attempt') or 0)
        if worker_owned:
            res = enqueue_worker_owned_cadence(lead, sender, text)
            release_lead_send_lock(lead_lock)
            if not res.get('ok') and not res.get('deduped'):
                failed += 1
                print(f"FALHA fila worker_owned porta {port}: {res}. Porta mantida para próxima rodada.")
                continue
            append_metric({**lead, 'event': 'cadence_queued_worker_owned', 'attempt_number': lead['next_attempt'], 'dispatch_id': res.get('dispatch_id'), 'deduped': res.get('deduped'), 'bridge_port': port, 'date_tz': now_brt().isoformat()})
            sent += 1
            print(f"OK enfileirado worker_owned | dispatch={res.get('dispatch_id')} | deduped={res.get('deduped')}")
            if args.stop_after_sent and sent >= args.stop_after_sent:
                break
            if idx < min(args.limit, len(candidates)):
                time.sleep(args.sleep_seconds)
            continue
        max_parts, final_pause, delay_schedule = cadence_sequence_options(attempt_no)
        ok, resp = d.send_whatsapp_sequence(
            port,
            lead['jid'],
            text,
            final_pause_seconds=final_pause,
            max_parts=max_parts,
            delay_schedule=delay_schedule,
        )
        if not ok:
            failed += 1
            disabled_ports.add(port)
            print(f"FALHA porta {port}: {resp}. Porta removida da rodada.")
            release_lead_send_lock(lead_lock)
            continue
        task_id = create_cadence_task(lead, text, lead['next_attempt'], {'sender_name': sender_label, 'port': port}, send_resp=resp)
        if int(lead['next_attempt']) == 1:
            # Garantia Rafael: fez Follow 1/primeiro contato, card fica em Primeiro Contato.
            move_deal_stage(lead['deal_id'], STAGE_PRIMEIRO_CONTATO)
        sent_at = now_brt()
        registro = enrich_legacy_row({
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
        }, nature=f"followup_f{int(lead.get('next_attempt') or 1)}", origin='cron_cadencia_primeiro_contato', thread_state='cold_outreach', owner_uid=(sender.get('owner_uid') or lead.get('owner_key') or lead.get('owner_name')))
        record_dispatch_shadow_from_row(registro, origin='followup', nature=f"followup_f{int(lead.get('next_attempt') or 1)}", thread_state='cold_outreach')
        envios = d.registrar_envio(registro)
        release_lead_send_lock(lead_lock)
        append_metric({**lead, 'event': 'cadence_sent', 'attempt_number': lead['next_attempt'], 'task_id': task_id, 'bridge_port': port, 'date_tz': sent_at.isoformat()})
        sent += 1
        print(f"OK enviado | task={task_id} | resp={resp}")
        if args.stop_after_sent and sent >= args.stop_after_sent:
            break
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
