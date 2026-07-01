#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tratativa WhatsApp para leads legítimos, mas Não-MQL.

Processo rígido aprovado por Rafael (30/06): texto, comunicadores, janela e
defaults ficam fixos em constantes no código, sem LLM/modelo variável.

- Comunicadores fixos: Lucas Resende (4606), Mariana (4600) e Rafael (4607).
- Texto WhatsApp 100% fixo nas constantes APPROVED_* (build_message só varia
  primeiro nome, comunicador e a linha de contexto padrão/mismatch).
- Janela rígida de envio externo: todos os dias, 07h-22h BRT (fail-closed).
  Fora da janela, --send sai [SILENT] sem enviar; --dry-run continua liberado
  para auditoria.
- Gating fail-closed por envio (e-mail gratuito NÃO bloqueia mais): lifecycle
  atual no HubSpot exatamente "lead", telefone BR normalizável, empresa segura,
  dedupe local e nenhum envio MQL posterior.
- Defaults fixos: --limit 999, --sleep 10.
- Registra wpp_envios.json e cria task no HubSpot.

Uso:
  python3 scripts/non_mql_legit_outreach.py --dry-run
  python3 scripts/non_mql_legit_outreach.py --send
  python3 scripts/non_mql_legit_outreach.py --send-current /tmp/non_mql_current.json
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p  # noqa: E402
from whatsapp_safe_send import safe_post_bridge  # noqa: E402
from whatsapp_send_orchestrator import enrich_legacy_row  # noqa: E402
from whatsapp_dispatch_flow import record_dispatch_shadow_from_row, record_dispatch_worker_owned  # noqa: E402

DISPATCH_QUEUE = PROJ / 'controle' / 'whatsapp_dispatch_queue.json'

PROCESS_ID = 'zydon-nao-mql-tratativa-legitima'
PROCESS_VERSION = 'rafael-approved-2026-06-30-v1'
CAMPAIGN = 'nao_mql_legitimo_tratativa'
MIN_NON_MQL_LEDGER_AGE_HOURS = 0
FIXED_BRT_TIMEZONE = 'America/Sao_Paulo'
FIXED_SEND_WEEKDAYS_BRT = (0, 1, 2, 3, 4, 5, 6)  # todos os dias
FIXED_SEND_START_HOUR_BRT = 7
FIXED_SEND_END_HOUR_BRT = 22  # exclusivo: 22:00 já bloqueia envio
DEFAULT_SEND_LIMIT = 999
DEFAULT_SLEEP_SECONDS = 10

APPROVED_CONTEXT_LINE_STANDARD = (
    "Vi que vocês demonstraram interesse na Zydon e quis te chamar por aqui para entender melhor."
)
APPROVED_CONTEXT_LINE_MISMATCH = (
    "Vi que vocês demonstraram interesse na Zydon, mas alguns dados do cadastro ficaram desencontrados, "
    "principalmente nome da empresa e domínio do e-mail. Quis te chamar por aqui para confirmar melhor o contexto."
)
APPROVED_PRODUCT_LINE = (
    "A Zydon é voltada para indústrias, distribuidores e atacadistas que vendem para outras empresas "
    "e querem organizar pedidos recorrentes em um portal B2B próprio."
)
APPROVED_FIT_LINE = (
    "Pelo que conseguimos entender até aqui, não ficou tão claro se esse é o momento ou o tipo de operação de vocês."
)
APPROVED_CTA_LINE = "Como você imagina que a Zydon poderia te ajudar hoje?"
SENDER_LABELS = {
    'Rafael': 'o Rafael',
    'Mariana': 'a Mariana',
    'Lucas Resende': 'o Lucas Resende',
}
SENDERS = [
    {'port': 4606, 'name': 'Lucas Resende', 'intro': 'Aqui é o Lucas Resende, da Zydon, plataforma de eCommerce B2B.'},
    {'port': 4600, 'name': 'Mariana', 'intro': 'Aqui é a Mariana, da Zydon, plataforma de eCommerce B2B.'},
    {'port': 4607, 'name': 'Rafael', 'intro': 'Aqui é o Rafael, da Zydon, plataforma de eCommerce B2B.'},
]
FREE_DOMAINS = set(getattr(p, 'FREE_EMAIL_DOMAINS', set())) | {'gmail.com.br', 'hotmail.com.br'}

CONTACT_PROPS = [
    'firstname','lastname','email','company','phone','mobilephone','hs_whatsapp_phone_number',
    'hs_searchable_calculated_phone_number','lifecyclestage','hubspot_owner_id',
    'createdate','recent_conversion_date','recent_conversion_event_name',
]


def now_brt():
    return datetime.now(ZoneInfo(FIXED_BRT_TIMEZONE))


def within_fixed_send_window(dt=None):
    """Janela rígida aprovada para envio externo Não-MQL.

    O agendador pode acordar mais vezes, mas o próprio código fica fail-closed:
    nenhum WhatsApp externo sai fora de 07:00-21:59 BRT, todos os dias.
    """
    dt = dt or now_brt()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(FIXED_BRT_TIMEZONE))
    dt = dt.astimezone(ZoneInfo(FIXED_BRT_TIMEZONE))
    return (
        dt.weekday() in FIXED_SEND_WEEKDAYS_BRT
        and FIXED_SEND_START_HOUR_BRT <= dt.hour < FIXED_SEND_END_HOUR_BRT
    )


def load_envios():
    return p.load_wpp()


def save_envios(envios):
    p.save_wpp(envios)


def email_domain(email):
    return (email or '').split('@')[-1].lower().strip() if '@' in (email or '') else ''


def corporate_domain(email, research):
    dom = email_domain(email)
    # Se a pesquisa diz que o domínio do e-mail não pertence ao negócio, não é seguro chamar como lead legítimo por domínio.
    dom_text = (research.get('dominio_site') or '').lower()
    if dom and dom not in FREE_DOMAINS and 'não pertence' not in dom_text and 'nao pertence' not in dom_text:
        return dom
    cand = p.candidate_domain(email, research)
    if cand and cand not in FREE_DOMAINS:
        return cand
    return ''


def already_sent(envios, email=None, cid=None, phone=None):
    phone_keys = {p.normalize_br_phone(phone or ''), p.only_digits(phone or '')}
    phone_keys.discard('')
    for e in envios:
        if not isinstance(e, dict):
            continue
        if e.get('campaign_id') == CAMPAIGN or e.get('msg_type') == CAMPAIGN:
            if email and str(e.get('email','')).lower() == email.lower():
                return True, 'email já consta na campanha'
            if cid and str(e.get('contact_id','')) == str(cid):
                return True, 'contact_id já consta na campanha'
            for field in ('phone','telefone','to','jid','lead_jid'):
                val = str(e.get(field) or '')
                vals = {p.normalize_br_phone(val), p.only_digits(val)}
                if phone_keys & vals:
                    return True, 'telefone já consta na campanha'
        # Qualquer diagnóstico/MQL posterior ao não-MQL bloqueia para não mandar mensagem contraditória.
        if email and str(e.get('email','')).lower() == email.lower():
            st = str(e.get('status') or e.get('msg_type') or '').lower()
            if st in {
                'enviado_lead', 'enviado_mql',
                'mql_diagnostico_rafael_texto', 'mql_diagnostico_rafael_pdf', 'mql_agenda_sdr_apos_diagnostico',
                'primeiro_contato', 'primeiro_contato_backlog_institucional', 'primeiro_contato_cadencia',
            }:
                return True, f'bloqueado por envio posterior existente: {st}'
    return False, ''


def hs_retry(method, path, payload=None, attempts=5, base_sleep=1.8):
    """HubSpot wrapper local para evitar gargalo 429 SECONDLY derrubando o cron.

    O process_gate_once.hs levanta RuntimeError em 429. Para esta régua de
    backfill, é melhor esperar poucos segundos e seguir do que quebrar a rodada
    inteira e repetir o mesmo lote no próximo tick.
    """
    last = None
    for i in range(attempts):
        try:
            if i:
                time.sleep(base_sleep * i)
            return p.hs(method, path, payload)
        except RuntimeError as e:
            last = e
            msg = str(e)
            if '-> 429:' not in msg and 'RATE_LIMIT' not in msg and 'SECONDLY' not in msg:
                raise
            if i == attempts - 1:
                raise
    raise last


def search_contact_by_email(email):
    payload = {
        'filterGroups': [{'filters': [{'propertyName': 'email', 'operator': 'EQ', 'value': email}]}],
        'properties': CONTACT_PROPS,
        'limit': 10,
    }
    data = hs_retry('POST', '/crm/v3/objects/contacts/search', payload)[1]
    results = data.get('results') or []
    if not results:
        return None
    # Preferir contato com telefone e conversão recente.
    def score(c):
        props = c.get('properties') or {}
        phone = props.get('hs_searchable_calculated_phone_number') or props.get('hs_whatsapp_phone_number') or props.get('phone') or props.get('mobilephone') or ''
        return (1 if p.phone_variants_with_optional_9(phone) else 0, props.get('recent_conversion_date') or props.get('createdate') or '')
    return sorted(results, key=score, reverse=True)[0]


def safe_company(props, research):
    company = (props.get('company') or '').strip()
    if company and company.lower() not in {'none','null','sem nome'}:
        return company
    er = (research.get('empresa_real') or '').strip()
    if er:
        return re.split(r' — | - |\|', er)[0].strip()[:80]
    return ''


def first_name(props):
    raw = (props.get('firstname') or '').strip().split()
    if not raw:
        return ''
    token = raw[0]
    # Evita mandar saudação com emoji, nick decorado ou caracteres estranhos.
    if not re.search(r'[A-Za-zÀ-ÿ]', token):
        return ''
    token = re.sub(r'[^A-Za-zÀ-ÿ\'-]', '', token)
    return token[:1].upper() + token[1:].lower() if token else ''


def build_message(props, research, sender):
    nome = first_name(props)
    greeting = f"Oi {nome}, tudo bem?" if nome else "Oi, tudo bem?"
    sender_label = SENDER_LABELS.get(sender['name'], sender['name'])
    reason_blob = ' '.join(str(research.get(k) or '') for k in ('motivo', 'dominio_site', 'redes', 'segmento')).lower()
    domain_or_name_mismatch = any(term in reason_blob for term in (
        'domínio do e-mail', 'dominio do e-mail', 'domínio não bate', 'dominio não bate',
        'domínio nao bate', 'dominio nao bate', 'nome não bate', 'nome nao bate',
        'não pertence', 'nao pertence', 'não corresponde', 'nao corresponde',
    ))
    context_line = APPROVED_CONTEXT_LINE_MISMATCH if domain_or_name_mismatch else APPROVED_CONTEXT_LINE_STANDARD
    return (
        f"{greeting}\n\n"
        f"Aqui é {sender_label}, da Zydon, plataforma de eCommerce B2B.\n\n"
        f"{context_line}\n\n"
        f"{APPROVED_PRODUCT_LINE}\n\n"
        f"{APPROVED_FIT_LINE}\n\n"
        f"{APPROVED_CTA_LINE}"
    )


def healthy_senders(envios):
    out, errors = [], []
    for s in SENDERS:
        ok, detail = p.bridge_me(s['port'])
        if not ok:
            errors.append(f"{s['port']} {s['name']}: {detail}")
            continue
        limit_ok, limit_reason = p.port_within_external_limits(envios, s['port'])
        if not limit_ok and not os.environ.get('ZYDON_NON_MQL_IGNORE_HOURLY'):
            errors.append(f"{s['port']} {s['name']}: limite {limit_reason}")
            continue
        ss = dict(s)
        ss['me'] = detail
        out.append(ss)
    return out, errors


def recent_counts(envios, port):
    now = now_brt()
    hour = day = 0
    for e in envios:
        if not p.is_direct_external_envio(e):
            continue
        try:
            if int(e.get('bridge_port')) != int(port):
                continue
        except Exception:
            continue
        dt = p.envio_datetime_brt(e)
        if not dt:
            continue
        delta = (now - dt).total_seconds()
        if 0 <= delta < 3600:
            hour += 1
        if dt.date() == now.date():
            day += 1
    return hour, day


def choose_sender(senders, envios, planned):
    candidates = []
    for s in senders:
        hour, day = recent_counts(envios, s['port'])
        ph = planned.get((s['port'], 'hour'), 0)
        pd = planned.get((s['port'], 'day'), 0)
        if hour + ph >= p.MAX_EXTERNAL_PER_PORT_HOUR and not os.environ.get('ZYDON_NON_MQL_IGNORE_HOURLY'):
            continue
        if day + pd >= p.MAX_EXTERNAL_PER_PORT_DAY and not os.environ.get('ZYDON_NON_MQL_IGNORE_DAILY'):
            continue
        candidates.append((s, hour + ph, day + pd))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[1], item[2], item[0]['port']))
    return candidates[0][0]


def is_test_or_dummy_lead(email, props, research):
    blob = ' '.join(str(x or '') for x in (
        email,
        props.get('firstname') if isinstance(props, dict) else '',
        props.get('company') if isinstance(props, dict) else '',
        props.get('phone') if isinstance(props, dict) else '',
        props.get('hs_searchable_calculated_phone_number') if isinstance(props, dict) else '',
        research.get('empresa_real') if isinstance(research, dict) else '',
        research.get('slug') if isinstance(research, dict) else '',
    )).lower()
    digits = p.only_digits(blob)
    return any(tok in blob for tok in ('joao@empresa.com.br', 'empresa ltda', 'leo testes', 'leonardo tester')) or '11999999999' in digits or '5511999999999' in digits


def candidate_from_research(email, research, envios):
    if research.get('mql') is not False:
        return None, 'não é Não-MQL na pesquisa'
    dom = corporate_domain(email, research)
    if not dom:
        # Correção Rafael 29/06: a tratativa Não-MQL é retorno para TODO lead
        # que não é MQL real. E-mail gratuito/sem domínio corporativo não bloqueia
        # mais; continua bloqueando apenas lifecycle diferente de lead, telefone
        # ausente/inválido, dedupe ou envio MQL posterior.
        dom = email_domain(email) or 'sem-dominio-corporativo'
    contact = search_contact_by_email(email)
    if not contact:
        return None, 'contato não encontrado no HubSpot'
    cid = str(contact.get('id'))
    props = contact.get('properties') or {}
    if is_test_or_dummy_lead(email, props, research):
        return None, 'base teste/dummy bloqueada'
    lifecycle = (props.get('lifecyclestage') or '').strip().lower()
    # Regra Rafael: só tratar Não-MQL legítimo se o ciclo de vida atual no HubSpot ainda for exatamente LEAD.
    # Opportunity é oportunidade comercial: NÃO recebe régua Não-MQL; deve seguir/reativar fluxo de diagnóstico/follow-up.
    # Não enviar para subscriber/vazio nem para MQL/SQL/Oportunidade/Cliente, porque pode ter revisão manual ou estágio diferente.
    if lifecycle == 'opportunity':
        return None, 'lifecycle opportunity: tratar como nova oportunidade de diagnóstico/follow-up, não como Não-MQL'
    if lifecycle != 'lead':
        return None, f'lifecycle atual bloqueia: {lifecycle or "vazio"}'
    phone = props.get('hs_searchable_calculated_phone_number') or props.get('hs_whatsapp_phone_number') or props.get('phone') or props.get('mobilephone') or ''
    variants = p.phone_variants_with_optional_9(phone)
    if not variants:
        return None, 'sem telefone BR normalizável'
    sent, why = already_sent(envios, email=email, cid=cid, phone=phone)
    if sent:
        return None, why
    company = safe_company(props, research)
    if not company:
        return None, 'sem empresa segura'
    return {
        'email': email,
        'contact_id': cid,
        'props': props,
        'research': research,
        'slug': research.get('slug') or email.split('@')[0],
        'company': company,
        'phone': variants[0],
        'phone_variants': variants,
        'domain': dom,
        'deals': p.contact_deals(cid),
        'reason': (research.get('motivo') or '')[:500],
    }, ''


def _ledger_dt_key(e):
    dt = p.envio_datetime_brt(e)
    return dt.isoformat() if dt else str(e.get('date') or '')


def ledger_non_mql_research_items(envios):
    """Puxa Não-MQLs recentes registrados pelo cron de definição mesmo quando não estão no RESEARCH estático.

    Rafael pediu que esta régua olhe a base que o outro cron pontuou como Não-MQL,
    sempre conferindo o lifecycle atual no HubSpot antes de enviar.
    """
    items = []
    seen = set(p.RESEARCH.keys())
    cutoff_ts = now_brt().timestamp() - (MIN_NON_MQL_LEDGER_AGE_HOURS * 3600)
    for e in sorted([x for x in envios if isinstance(x, dict)], key=_ledger_dt_key, reverse=True):
        email = str(e.get('email') or '').lower().strip()
        if not email or email in seen:
            continue
        status = str(e.get('status') or '').lower()
        if status != 'nao_mql_grupo':
            continue
        dt = p.envio_datetime_brt(e)
        if dt and dt.timestamp() > cutoff_ts:
            # Com MIN_NON_MQL_LEDGER_AGE_HOURS=0, só ignora registros com horário futuro
            # por relógio/log inconsistente. O controle de madrugada/noite fica no cron.
            continue
        empresa = str(e.get('empresa') or '').strip()
        slug = str(e.get('slug') or email.split('@')[0]).strip()
        domain = email_domain(email)
        research = {
            'slug': slug,
            'mql': False,
            'empresa_real': empresa or email,
            'dominio_site': domain,
            'redes': 'Lead registrado como Não-MQL pelo cron de definição MQL; validar HubSpot em tempo real antes do envio.',
            'segmento': 'Não-MQL registrado pelo cron de definição MQL',
            'motivo': 'Lead avaliado como Não-MQL pelo cron de definição. Entrou na régua de tratativa respeitosa somente se o lifecycle atual no HubSpot ainda for lead.',
            'insight': '',
        }
        seen.add(email)
        items.append((email, research))
    return items


def all_backfill_candidates(limit, envios):
    rows, skips = [], []
    items = ledger_non_mql_research_items(envios) + sorted(p.RESEARCH.items(), key=lambda kv: kv[1].get('slug') or kv[0])
    seen = set()
    for email, research in items:
        if email in seen:
            continue
        seen.add(email)
        cand, why = candidate_from_research(email, research, envios)
        if cand:
            rows.append(cand)
            if limit and len(rows) >= limit:
                break
        else:
            skips.append({'email': email, 'slug': research.get('slug'), 'skip': why})
    return rows, skips


def lead_jid(phone):
    d = p.only_digits(phone)
    if len(d) in (10, 11):
        d = '55' + d
    return d + '@s.whatsapp.net'


def post_bridge_short(port, payload, timeout=35):
    return safe_post_bridge(port, '/send', payload, uid='non_mql_legit_outreach', timeout=timeout)


def enqueue_worker_owned_non_mql(cand, sender, msg, jid):
    alternate_jids = [lead_jid(v) for v in cand.get('phone_variants', [])[1:] if lead_jid(v) != jid]
    res = record_dispatch_worker_owned(
        origin='nao_mql',
        nature='non_mql_outreach',
        thread_state='cold_outreach',
        to=jid,
        text=msg,
        owner_uid=sender.get('owner') or sender.get('name'),
        lead_key=cand.get('contact_id') or cand.get('email') or jid,
        port=sender['port'],
        sender_role=sender.get('name'),
        path=DISPATCH_QUEUE,
        completion_type='non_mql',
        alternate_jids=alternate_jids,
        email=cand.get('email'),
        contact_id=cand.get('contact_id'),
        slug=cand.get('slug'),
        empresa=cand.get('company'),
        phone=cand.get('phone'),
        sender_name=sender.get('name'),
        campaign_id=CAMPAIGN,
        msg_type=CAMPAIGN,
        reason=cand.get('reason'),
        deals=cand.get('deals') or [],
    )
    return res


def send_one(cand, sender, envios, dry_run=False, worker_owned=False):
    msg = build_message(cand['props'], cand['research'], sender)
    jid = lead_jid(cand['phone'])
    if dry_run:
        return {'dry_run': True, 'to': jid, 'text': msg}
    if worker_owned:
        res = enqueue_worker_owned_non_mql(cand, sender, msg, jid)
        return {'ok': bool(res.get('ok')), 'mode': 'worker_owned', 'to': jid, 'dispatch_id': res.get('dispatch_id'), 'deduped': bool(res.get('deduped')), 'text': msg}
    # Uma tentativa curta: se a bridge/Baileys travar para número sem WhatsApp,
    # não prender o cron de MQL por 5+ minutos nem repetir mensagem incerta.
    resp = post_bridge_short(sender['port'], {'to': jid, 'text': msg}, timeout=35)
    attempts = [{'attempt': 1, 'response': resp}]
    if not p.message_ok(resp) and len(cand['phone_variants']) > 1:
        alt = cand['phone_variants'][1]
        alt_jid = lead_jid(alt)
        alt_resp = post_bridge_short(sender['port'], {'to': alt_jid, 'text': msg}, timeout=25)
        attempts.append({'attempt': 'alt', 'response': alt_resp})
        if p.message_ok(alt_resp):
            cand['phone'] = alt
            jid = alt_jid
            resp = alt_resp
    if not p.message_ok(resp):
        return {'ok': False, 'to': jid, 'response': resp, 'attempts': attempts, 'text': msg}
    entry = enrich_legacy_row({
        'date': now_brt().strftime('%Y-%m-%d %H:%M:%S'),
        'date_tz': now_brt().isoformat(),
        'email': cand['email'],
        'contact_id': cand['contact_id'],
        'slug': cand['slug'],
        'empresa': cand['company'],
        'phone': cand['phone'],
        'to': jid,
        'bridge_port': sender['port'],
        'sender_name': sender['name'],
        'campaign_id': CAMPAIGN,
        'msg_type': CAMPAIGN,
        'status': 'enviado_nao_mql_legitimo',
        'text': msg,
        'messageId': resp.get('messageId') or resp.get('id'),
        'send_status': resp.get('status'),
        'response': resp,
        'task_id': None,
        'note': 'Ledger salvo imediatamente após /send para impedir reenvio se HubSpot task demorar/falhar.',
    }, nature='non_mql_outreach', origin='cron_non_mql_legit_outreach', thread_state='cold_outreach', owner_uid=sender.get('owner') or sender.get('name'))
    record_dispatch_shadow_from_row(entry, origin='nao_mql', nature='non_mql_outreach', thread_state='cold_outreach')
    envios.append(entry)
    save_envios(envios)
    task_id = None
    try:
        task_body = (
            f"Tratativa Não-MQL legítimo enviada para {jid} pela porta {sender['port']} ({sender['name']}).\n\n"
            f"Mensagem:\n{msg}\n\n"
            f"Motivo interno da não qualificação:\n{cand['reason']}"
        )
        task_id = p.create_task(cand['contact_id'], cand['deals'], 'WhatsApp — tratativa lead legítimo, mas não-MQL', task_body, None)
        entry['task_id'] = task_id
        save_envios(envios)
    except Exception as e:
        entry['task_error'] = str(e)[:500]
        save_envios(envios)
    return {'ok': True, 'to': jid, 'messageId': resp.get('messageId'), 'response': resp, 'task_id': task_id, 'text': msg}


def load_current(path, envios):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    email = (data.get('email') or '').lower()
    research = data.get('research') or {}
    # Permite receber props/id direto do process_gate_once no futuro.
    if data.get('contact_id') and data.get('props'):
        props = data['props']
        lifecycle = (props.get('lifecyclestage') or '').strip().lower()
        if lifecycle == 'opportunity':
            return None, 'lifecycle opportunity: tratar como nova oportunidade de diagnóstico/follow-up, não como Não-MQL'
        if lifecycle != 'lead':
            return None, f'lifecycle atual bloqueia: {lifecycle or "vazio"}'
        phone = props.get('hs_searchable_calculated_phone_number') or props.get('hs_whatsapp_phone_number') or props.get('phone') or props.get('mobilephone') or data.get('phone') or ''
        variants = p.phone_variants_with_optional_9(phone)
        if not variants:
            return None, 'sem telefone BR normalizável'
        sent, why = already_sent(envios, email=email, cid=data['contact_id'], phone=phone)
        if sent:
            return None, why
        return {
            'email': email,
            'contact_id': str(data['contact_id']),
            'props': props,
            'research': research,
            'slug': research.get('slug') or data.get('slug') or email.split('@')[0],
            'company': safe_company(props, research),
            'phone': variants[0],
            'phone_variants': variants,
            'domain': corporate_domain(email, research),
            'deals': data.get('deals') or [],
            'reason': (research.get('motivo') or '')[:500],
        }, ''
    return candidate_from_research(email, research, envios)


def main():
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--send', action='store_true')
    mode.add_argument('--send-current', metavar='JSON')
    ap.add_argument('--limit', type=int, default=DEFAULT_SEND_LIMIT)
    ap.add_argument('--sleep', type=int, default=DEFAULT_SLEEP_SECONDS)
    args = ap.parse_args()
    worker_owned = str(os.environ.get('ZYDON_NON_MQL_WORKER_OWNED') or '').lower() in {'1', 'true', 'yes', 'on'}

    if not args.dry_run and not within_fixed_send_window():
        print('[SILENT] fora da janela fixa Não-MQL 07h-22h BRT todos os dias')
        return

    if not args.dry_run and not worker_owned and not os.environ.get('ZYDON_SKIP_SEND_LOCK') and not p.acquire_global_send_lock(blocking=False):
        print('[SILENT] lock ocupado')
        return
    envios = load_envios()
    senders, sender_errors = healthy_senders(envios)
    if not senders:
        print(json.dumps({'ok': False, 'error': 'nenhum comunicador elegível', 'sender_errors': sender_errors}, ensure_ascii=False, indent=2))
        return

    if args.send_current:
        cand, why = load_current(args.send_current, envios)
        candidates = [cand] if cand else []
        skips = [{'current': args.send_current, 'skip': why}] if not cand else []
    else:
        candidates, skips = all_backfill_candidates(args.limit, envios)

    planned = {}
    results = []
    for cand in candidates:
        sender = choose_sender(senders, envios, planned)
        if not sender:
            results.append({
                'email': cand['email'], 'contact_id': cand['contact_id'], 'empresa': cand['company'],
                'slug': cand['slug'], 'result': {'ok': False, 'skipped': 'sem capacidade por limite hora/dia dos comunicadores'}
            })
            continue
        planned[(sender['port'], 'hour')] = planned.get((sender['port'], 'hour'), 0) + 1
        planned[(sender['port'], 'day')] = planned.get((sender['port'], 'day'), 0) + 1
        result = send_one(cand, sender, envios, dry_run=args.dry_run, worker_owned=worker_owned)
        results.append({
            'email': cand['email'], 'contact_id': cand['contact_id'], 'empresa': cand['company'],
            'slug': cand['slug'], 'sender': sender['name'], 'port': sender['port'], 'result': result,
        })
        if not args.dry_run and cand is not candidates[-1]:
            time.sleep(args.sleep)

    print(json.dumps({
        'ok': True,
        'process_id': PROCESS_ID,
        'process_version': PROCESS_VERSION,
        'mode': 'dry-run' if args.dry_run else 'send-current' if args.send_current else 'send',
        'eligible_count': len(candidates),
        'sender_errors': sender_errors,
        'results': results,
        'skip_sample': skips[:25],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
