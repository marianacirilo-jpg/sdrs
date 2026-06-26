#!/usr/bin/env python3
"""Follow-up SDR para leads MQL que já receberam diagnóstico/PDF.

Consulta o ledger compartilhado controle/wpp_envios.json, encontra envios diretos
`status=enviado_lead` cujo owner é Sarah/Breno/Lucas Batista e envia uma segunda
mensagem curta pelo SDR dono, fazendo uma pergunta operacional específica.

Seguro por padrão:
- não envia para grupo;
- não duplica se já houver msg_type=mql_sdr_followup para o mesmo deal/telefone;
- não envia se já houver follow-up SDR registrado para o mesmo deal/telefone;
- se o lead respondeu ao diagnóstico, não envia follow-up automático; move para Retorno Contato;
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
DISPARO = ROOT / 'disparo_dinamico.py'
WA_DATA = Path('/root/.hermes/whatsapp-extra/channel_data')

spec = importlib.util.spec_from_file_location('disparo_dinamico', str(DISPARO))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

BRT = timezone(timedelta(hours=-3))
OWNER_TO_KEY = {v['owner_id']: k for k, v in d.BRIDGES.items()}
OWNER_TO_NAME = {v['owner_id']: v['owner_name'] for v in d.BRIDGES.values()}
MSG_TYPE = 'mql_sdr_followup'
DIRECT_STATUSES = {'enviado_lead', 'enviado_mql'}
STAGE_PRIMEIRO_CONTATO_FEITO = '1214320997'  # Pipeline Principal: Primeiro Contato
STAGE_RETORNO_CONTATO = '998099482'  # Lead respondeu depois do diagnóstico


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
            if dt and dt > after_dt:
                out.append({'dt': dt, 'text': message_text(m), 'source': path.name})
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


def insight_from_text(rec):
    text = str(rec.get('text') or '')
    m = re.search(r'Em resumo,\s*(.+?)(?:\n| A Sarah| O Breno| O Lucas Batista| A consultora| O consultor|$)', text, re.S)
    if m:
        val = re.sub(r'\s+', ' ', m.group(1)).strip()
        if val:
            return val[:260]
    summary = str(rec.get('group_summary') or '')
    m = re.search(r'• Oportunidade:\s*(.+)', summary)
    if m:
        return re.sub(r'\s+', ' ', m.group(1)).strip()[:260]
    return ''


def question_for(rec):
    blob = (str(rec.get('text') or '') + ' ' + str(rec.get('group_summary') or '') + ' ' + company(rec)).lower()
    if any(x in blob for x in ('instagram', 'lead', 'essência', 'essencias', 'aromas', 'lojista', 'revenda')):
        return 'Hoje a reposição dos lojistas chega mais pelo WhatsApp/Instagram ou vocês já têm algum catálogo com pedido recorrente?'
    if any(x in blob for x in ('academia', 'suplement', 'mercado', 'atacado')):
        return 'Hoje o pedido de atacado entra mais pelo site, por vendedor ou fecha no WhatsApp?'
    if any(x in blob for x in ('agro', 'produtor', 'insumo', 'máquina', 'maquina', 'implemento', 'fertilizante')):
        return 'Hoje esses pedidos de produtores e clientes recorrentes chegam mais por WhatsApp, ligação ou vendedor?'
    if any(x in blob for x in ('estoque', 'preço', 'preco', 'tabela')):
        return 'Hoje o cliente consulta preço e disponibilidade com vendedor ou vocês já têm algum canal para isso?'
    if any(x in blob for x in ('erp', 'bling', 'omie', 'olist', 'sankhya')):
        return 'Hoje o pedido B2B entra em algum canal integrado ao ERP ou ainda depende de conversa manual?'
    return 'Hoje os pedidos B2B chegam mais por WhatsApp, ligação, e-mail ou vendedor?'


def compose(rec, sender_name):
    nome = first_name(rec)
    empresa = company(rec)
    insight = insight_from_text(rec)
    sent_by_owner = str(rec.get('fallback_note') or '').lower().find('sdr dono') >= 0
    if sent_by_owner:
        # Quando o próprio SDR já enviou o diagnóstico, o follow-up não pode soar
        # como uma reapresentação ou repetir a mesma abertura. Ele deve continuar
        # a conversa a partir do material anterior.
        opener = f"{nome}, {'aqui é a' if sender_name == 'Sarah' else 'aqui é o'} {sender_name} da Zydon. Passando para continuar o ponto que te enviei sobre a {empresa}, sem recomeçar a conversa do zero."
    else:
        opener = f"{nome}, {'aqui é a' if sender_name == 'Sarah' else 'aqui é o'} {sender_name} da Zydon. Vi o diagnóstico que a gente te enviou da {empresa}."
    parts = [opener]
    incoming = rec.get('_incoming_after') or incoming_messages_after(rec.get('to'), rec.get('_dt'))
    if incoming:
        last = incoming[-1]
        resposta = (last.get('text') or '').strip()
        if resposta:
            parts.append(f"Vi sua resposta sobre o diagnóstico: \"{resposta[:220]}\". Vou seguir exatamente a partir disso, sem começar do zero.")
        else:
            parts.append('Vi que você respondeu depois do diagnóstico, então vou continuar a partir desse contexto e não começar do zero.')
    if insight:
        parts.append(f"Puxei um ponto dele: {insight}")
    parts.append(question_for(rec))
    parts.append('Pode me responder por aqui mesmo.')
    return '\n\n'.join(parts)


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


def move_deal_stage(deal_id, stage):
    if not deal_id:
        return None
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


def create_task(rec, text, sender, send_resp):
    contact_id, deal_id = resolve_hubspot_ids(rec)
    if not deal_id or not contact_id:
        return None
    body_txt = [
        'Follow-up SDR após diagnóstico MQL enviado ao lead.',
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
            'hs_task_subject': f"WhatsApp — follow-up diagnóstico MQL enviado por {sender.get('sender_name')}",
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


def already_followed(envios, rec):
    did = str(rec.get('deal_id') or rec.get('dealId') or '')
    pk = phone_key(rec.get('to'))
    for r in envios:
        if not isinstance(r, dict):
            continue
        if str(r.get('msg_type') or '').lower() != MSG_TYPE:
            continue
        if did and str(r.get('deal_id') or r.get('dealId') or '') == did:
            return True
        if pk and phone_key(r.get('to')) == pk:
            return True
    return False


def sent_count(envios, owner_name, hours=None):
    now = datetime.now(timezone.utc)
    n = 0
    for r in envios:
        if not isinstance(r, dict):
            continue
        if str(r.get('msg_type') or '').lower() != MSG_TYPE:
            continue
        if str(r.get('sdr') or '') != owner_name:
            continue
        dt = parse_dt(r.get('date_tz') or r.get('date'))
        if not dt:
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
        # Follow-up automático só para lead sem resposta e com pelo menos 60min
        # desde o diagnóstico. Se respondeu ao diagnóstico, não mandar nova
        # automação: mover para Retorno Contato e deixar SDR humano continuar.
        # Incidente King Talhas 26/06.
        if age_h < 1.0:
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
            print(f"SKIP respondeu diagnóstico -> Retorno Contato: {company(rec)} deal={resolved_deal_id} stage={moved_stage} resp={(last.get('text') or '')[:120]}")
            continue
        if sent_count(envios, owner_name, 1) >= args.max_per_hour:
            print(f"SKIP {owner_name}: limite horário follow-up")
            continue
        if sent_count(envios, owner_name, None) >= args.max_per_day:
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
            continue
        ok, resp = d.send_whatsapp(port, rec.get('to'), text)
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
