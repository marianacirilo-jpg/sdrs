#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tratativa WhatsApp para leads legítimos, mas Não-MQL.

- Usa os comunicadores Lucas Resende (4606), Mariana (4600) e Rafael (4607).
- Fail-closed: só envia quando há e-mail corporativo/domínio não-gratuito, empresa real,
  telefone BR normalizável e nenhuma evidência local de envio anterior da campanha.
- Registra wpp_envios.json e task COMPLETED no HubSpot.

Uso:
  python3 scripts/non_mql_legit_outreach.py --dry-run --limit 9
  python3 scripts/non_mql_legit_outreach.py --send --limit 9
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

CAMPAIGN = 'nao_mql_legitimo_tratativa'
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
    return datetime.now(ZoneInfo('America/Sao_Paulo'))


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
            if st in {'enviado_lead','primeiro_contato','primeiro_contato_backlog_institucional','primeiro_contato_cadencia'}:
                return True, f'bloqueado por envio posterior existente: {st}'
    return False, ''


def search_contact_by_email(email):
    payload = {
        'filterGroups': [{'filters': [{'propertyName': 'email', 'operator': 'EQ', 'value': email}]}],
        'properties': CONTACT_PROPS,
        'limit': 10,
    }
    data = p.hs('POST', '/crm/v3/objects/contacts/search', payload)[1]
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
    company = safe_company(props, research)
    greeting = f"Oi {nome}, tudo bem?" if nome else "Oi, tudo bem?"
    empresa_line = f"Pelo que entendemos da {company}, talvez a gente não conseguiria ajudar agora." if company else "Pelo que entendemos, talvez a gente não conseguiria ajudar agora."
    # Variação determinística por remetente, sem travessão/emoji/reticências.
    if sender['name'] == 'Mariana':
        return (
            f"{greeting}\n\n"
            f"{sender['intro']}\n\n"
            "Obrigado pelo interesse de vocês na Zydon. Talvez a gente não tenha conseguido deixar claro o nosso foco.\n\n"
            "A Zydon atende principalmente indústrias, distribuidores e atacadistas que vendem para outras empresas e querem transformar esse processo em um portal B2B próprio.\n\n"
            f"{empresa_line}\n\n"
            "Se nossa leitura estiver errada, me responde aqui que a gente entende melhor o negócio de vocês."
        )
    if sender['name'] == 'Rafael':
        return (
            f"{greeting}\n\n"
            f"{sender['intro']}\n\n"
            "Analisamos o interesse de vocês e acho importante te dar um retorno transparente.\n\n"
            "Nosso foco é ajudar empresas que vendem para outras empresas, como indústrias, distribuidores e atacadistas, a digitalizar pedidos recorrentes em um portal próprio.\n\n"
            f"{empresa_line}\n\n"
            "Se entendemos errado, me chama aqui que a gente conversa melhor."
        )
    return (
        f"{greeting}\n\n"
        f"{sender['intro']}\n\n"
        "Poxa, talvez a gente não tenha conseguido explicar tão bem o foco da Zydon.\n\n"
        "Hoje ajudamos principalmente indústrias, distribuidores e atacadistas que vendem para outras empresas e querem digitalizar pedidos recorrentes em um portal próprio.\n\n"
        f"{empresa_line}\n\n"
        "Se nossa leitura estiver errada, me responde aqui que a gente entende melhor o negócio de vocês."
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
        if day + pd >= p.MAX_EXTERNAL_PER_PORT_DAY:
            continue
        candidates.append((s, hour + ph, day + pd))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[1], item[2], item[0]['port']))
    return candidates[0][0]


def candidate_from_research(email, research, envios):
    if research.get('mql') is not False:
        return None, 'não é Não-MQL na pesquisa'
    dom = corporate_domain(email, research)
    if not dom:
        return None, 'sem domínio corporativo seguro'
    contact = search_contact_by_email(email)
    if not contact:
        return None, 'contato não encontrado no HubSpot'
    cid = str(contact.get('id'))
    props = contact.get('properties') or {}
    lifecycle = (props.get('lifecyclestage') or '').strip().lower()
    # Regra Rafael: só tratar Não-MQL legítimo se o ciclo de vida atual no HubSpot ainda for exatamente LEAD.
    # Não enviar para subscriber/vazio nem para MQL/SQL/Oportunidade/Cliente, porque pode ter revisão manual ou estágio diferente.
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


def all_backfill_candidates(limit, envios):
    rows, skips = [], []
    for email, research in sorted(p.RESEARCH.items(), key=lambda kv: kv[1].get('slug') or kv[0]):
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
    if len(d) == 11:
        d = '55' + d
    return d + '@s.whatsapp.net'


def post_bridge_short(port, payload, timeout=35):
    req = urllib.request.Request(
        f'http://127.0.0.1:{port}/send',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            txt = resp.read().decode('utf-8', errors='replace')
            try:
                return json.loads(txt)
            except Exception:
                return {'raw': txt}
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='replace')
        try:
            data = json.loads(body)
        except Exception:
            data = {'raw': body}
        data['http_error'] = e.code
        return data
    except Exception as e:
        return {'error': str(e), 'timeout_seconds': timeout}


def send_one(cand, sender, envios, dry_run=False):
    msg = build_message(cand['props'], cand['research'], sender)
    jid = lead_jid(cand['phone'])
    if dry_run:
        return {'dry_run': True, 'to': jid, 'text': msg}
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
    task_body = (
        f"Tratativa Não-MQL legítimo enviada para {jid} pela porta {sender['port']} ({sender['name']}).\n\n"
        f"Mensagem:\n{msg}\n\n"
        f"Motivo interno da não qualificação:\n{cand['reason']}"
    )
    task_id = p.create_task(cand['contact_id'], cand['deals'], 'WhatsApp — tratativa lead legítimo, mas não-MQL', task_body, None)
    entry = {
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
        'response': resp,
        'task_id': task_id,
    }
    envios.append(entry)
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
    ap.add_argument('--limit', type=int, default=9)
    ap.add_argument('--sleep', type=int, default=20)
    args = ap.parse_args()

    if not args.dry_run and not os.environ.get('ZYDON_SKIP_SEND_LOCK') and not p.acquire_global_send_lock(blocking=False):
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
        result = send_one(cand, sender, envios, dry_run=args.dry_run)
        results.append({
            'email': cand['email'], 'contact_id': cand['contact_id'], 'empresa': cand['company'],
            'slug': cand['slug'], 'sender': sender['name'], 'port': sender['port'], 'result': result,
        })
        if not args.dry_run and cand is not candidates[-1]:
            time.sleep(args.sleep)

    print(json.dumps({
        'ok': True,
        'mode': 'dry-run' if args.dry_run else 'send-current' if args.send_current else 'send',
        'eligible_count': len(candidates),
        'sender_errors': sender_errors,
        'results': results,
        'skip_sample': skips[:25],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
