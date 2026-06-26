#!/usr/bin/env python3
"""Campanha SUMIÇO INÍCIO DE FUNIL.

Seleciona deals no stage Primeiro Contato sem atividade há >21 dias, envia
WhatsApp de encerramento por comunicadores institucionais em round-robin e,
após envio confirmado, move o deal para perdido com motivo Sumiço - Início do funil.

Seguro por padrão: sem --send apenas gera prévia.
"""
import argparse
import csv
import importlib.util
import json
import random
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path('/root/.hermes/zydon-prospeccao')
DISPARO = ROOT / 'disparo_dinamico.py'
OUTDIR = ROOT / 'controle' / 'sumico_inicio_funil'
LOG_JSONL = OUTDIR / 'envios_sumico_inicio_funil.jsonl'
SEGMENTACAO_CLAUDE = OUTDIR / 'segmentacao_claude_20260625_161840.json'
CAMPAIGN_ID = 'sumico_inicio_funil_2026_06_25'
PIPELINE = '671008549'
STAGE_PRIMEIRO_CONTATO = '1214320997'
STAGE_PERDIDO = '984052835'
LOST_REASON_VALUE = 'Falta de retorno - Início do funil'
BRT = timezone(timedelta(hours=-3))
CUTOFF_DAYS = 21

spec = importlib.util.spec_from_file_location('disparo_dinamico', str(DISPARO))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

SENDERS = [
    {'key': 'mariana', 'name': 'Mariana', 'port': 4600, 'expected': 'Mariana | Zydon'},
    {'key': 'lucas_resende', 'name': 'Lucas Resende', 'port': 4606, 'expected': 'Lucas Resende'},
    {'key': 'rafael', 'name': 'Rafael', 'port': 4607, 'expected': 'Rafael Calixto'},
    {'key': 'joao_pedro', 'name': 'João Pedro', 'port': 4609, 'expected': 'João'},
    {'key': 'gustavo', 'name': 'Gustavo', 'port': 4610, 'expected': 'Gustavo'},
]

OWNER_MAP = {
    '86265630': {'key': 'breno', 'name': 'Breno', 'phone_digits': '5534984472414', 'phone_display': '34 98447-2414'},
    '88063842': {'key': 'sarah', 'name': 'Sarah', 'phone_digits': '5534984095632', 'phone_display': '34 98409-5632'},
    '85778446': {'key': 'lucas', 'name': 'Lucas Batista', 'phone_digits': '5534984295409', 'phone_display': '34 98429-5409'},
}

NATIVE_ERPS = {'bling', 'omie', 'olist', 'tiny', 'olist/tiny', 'sankhya'}
PHONE_FIELDS = ('to', 'jid', 'lead_jid', 'tel', 'telefone')


def parse_dt(raw):
    if not raw:
        return None
    s = str(raw).strip()
    try:
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def now_brt():
    return datetime.now(BRT)


def clean_first_name(name):
    name = (name or '').strip()
    if not name:
        return 'tudo bem'
    name = re.sub(r'[^A-Za-zÀ-ÿ\s\-]', '', name).strip()
    if not name:
        return 'tudo bem'
    first = name.split()[0]
    if first.lower() in {'lead', 'cliente', 'contato', 'teste'}:
        return 'tudo bem'
    return first[:1].upper() + first[1:].lower()


def erp_allowed(erp):
    e = (erp or '').strip()
    if not e:
        return ''
    low = e.lower().replace('tiny/olist', 'olist/tiny')
    if any(x in low for x in NATIVE_ERPS):
        if 'tiny' in low or 'olist' in low:
            return 'Olist/Tiny'
        if 'bling' in low:
            return 'Bling'
        if 'omie' in low:
            return 'Omie'
        if 'sankhya' in low:
            return 'Sankhya'
    return ''


def stable_index(*parts, mod):
    import hashlib
    raw = '|'.join(str(p or '') for p in parts)
    return int(hashlib.sha256(raw.encode()).hexdigest()[:8], 16) % mod


def choose_template(lead):
    return stable_index(lead.get('deal_id'), lead.get('jid'), lead.get('sdr_name'), mod=10) + 1


def render_message(lead, sender=None):
    nome = clean_first_name(lead.get('firstname'))
    sdr = lead['sdr_name']
    phone = lead['sdr_phone_display']
    artigo = 'a' if sdr.lower().startswith('sarah') else 'o'
    com_sdr = f"com {artigo} {sdr}"
    chama_sdr = f"chama {artigo} {sdr}"
    sender_name = (sender or {}).get('name') or 'Rafael'
    sender_article = 'a' if sender_name.lower().split()[0] in {'mariana'} else 'o'
    intro = f"Aqui é {sender_article} {sender_name}, da Zydon, plataforma de eCommerce B2B."
    hiper = (lead.get('frase_sugerida') or '').strip()
    if hiper:
        # Reescreve a pesquisa do Claude no formato pedido pelo Rafael:
        # apresentação do remetente -> consultor que já estava atendendo -> consciência segmentada -> CTA sem cinismo.
        texto = re.sub(r'\s+', ' ', hiper).strip()
        # remove saudação original do Claude para evitar duas apresentações
        texto = re.sub(r'^(Oi|Olá|Fala)\s+[^.]+\.\s*', '', texto, flags=re.I)
        # remove CTAs que podem soar irônicos/cínicos para lead que já foi chamado antes
        texto = re.sub(r'\s*(Quando quiser|Se quiser|Se em algum momento|Quando fizer sentido|Se fizer sentido)[^.]+(?:no|pelo|por aqui)\s+\d{2}\s+\d{4,5}-\d{4}\.?$', '', texto, flags=re.I).strip()
        texto = re.sub(r'\s*(Quando quiser|Se quiser|Se em algum momento|Quando fizer sentido|Se fizer sentido)[^.]+$', '', texto, flags=re.I).strip()
        abertura = f"Oi {nome}, tudo bem?\n\n{intro}\n\n{artigo.upper() if False else artigo.capitalize()} {sdr} estava falando contigo, mas imagino que a rotina aí tenha corrido e a conversa acabou não evoluindo."
        corpo = texto
        fechamento = f"Por isso vamos pausar as tentativas por aqui para não ficar insistindo no seu WhatsApp.\n\nSe esse tema voltar a fazer sentido, {chama_sdr} no {phone}.\n\nObrigado e sucesso por aí!"
        if corpo:
            return 'claude_segmentado', abertura + "\n\n" + corpo + "\n\n" + fechamento
        return 'claude_segmentado', abertura + "\n\n" + fechamento
    erp = erp_allowed(lead.get('erp'))
    tid = choose_template(lead)
    # ERP templates only when natively confirmed; otherwise transparently fall back.
    templates = {
        1: f"Olá {nome}, tudo bem?\n\n{intro}\n\nVocê estava falando {com_sdr}, mas imagino que a correria aí na empresa tenha atrapalhado a agenda de vocês.\n\nComo acabaram se desencontrando, vamos pausar as tentativas por aqui para não ficar lotando seu WhatsApp.\n\nSe ainda fizer sentido digitalizar as vendas B2B e deixar seus clientes pedindo com mais autonomia, {chama_sdr} no {phone}.\n\nAbraço e sucesso!",
        2: f"Olá {nome}, tudo bem?\n\n{intro}\n\nVocê estava falando {com_sdr}, mas imagino que a rotina aí tenha enrolado a agenda e travado a nossa evolução.\n\nVamos pausar as tentativas por aqui para não ficar insistindo no seu WhatsApp.\n\nSe o plano ainda é digitalizar as vendas B2B e criar uma operação 24h integrada ao {erp}, {chama_sdr} no {phone}.\n\nAbraço e sucesso!" if erp else None,
        3: f"Oi {nome}, tudo bem?\n\n{intro}\n\nPassando só para encerrar por aqui com cuidado.\n\nVocê e {artigo} {sdr} acabaram se desencontrando, então vamos pausar os contatos para não ficar insistindo.\n\nSe ainda fizer sentido conversar sobre vendas B2B, portal para clientes e pedidos com mais autonomia, {chama_sdr} no {phone}.\n\nSucesso aí!",
        4: f"Olá {nome}, tudo certo?\n\n{intro}\n\nComo não conseguimos evoluir a conversa {com_sdr}, vou considerar que esse tema ficou sem prioridade agora.\n\nPara não ficar enchendo seu WhatsApp, vamos pausar as tentativas por aqui.\n\nSe em algum momento vocês quiserem retomar o plano de vender mais no B2B sem depender tanto de pedido manual, {chama_sdr} no {phone}.\n\nUm abraço!",
        5: f"Olá {nome}, tudo bem?\n\n{intro}\n\nVocê estava falando {com_sdr} sobre a Zydon, mas parece que a agenda de vocês acabou correndo.\n\nVamos pausar o contato por aqui para não incomodar.\n\nSe ainda fizer sentido estruturar um canal B2B para seus clientes comprarem com mais autonomia e conectado ao {erp}, {chama_sdr} no {phone}.\n\nAbraço e sucesso!" if erp else None,
        6: f"Oi {nome}, tudo bem?\n\n{intro}\n\nComo não conseguimos seguir a conversa {com_sdr}, vamos pausar as tentativas por aqui.\n\nSe quiser retomar o projeto de vendas B2B mais pra frente, {chama_sdr} no {phone}.\n\nAbraço!",
        7: f"Fala {nome}, tudo bem?\n\n{intro}\n\nComo a conversa {com_sdr} não avançou nas últimas semanas, vou pausar por aqui para não ficar insistindo.\n\nSe a prioridade de digitalizar as vendas B2B voltar para a mesa, {chama_sdr} no {phone} que ele retoma com você.\n\nSucesso por aí!",
        8: f"Olá {nome}, tudo bem?\n\n{intro}\n\nA gente tentou evoluir a conversa por aqui, mas imagino que a agenda tenha ficado corrida.\n\nVou pausar as tentativas para não lotar seu WhatsApp.\n\nQuando fizer sentido retomar a ideia de dar mais autonomia para seus clientes comprarem no B2B, {chama_sdr} no {phone}.\n\nAbraço!",
        9: f"Oi {nome}, tudo certo?\n\n{intro}\n\nComo não conseguimos avançar {com_sdr}, vamos encerrar as tentativas por aqui.\n\nSe mais pra frente vocês quiserem reduzir pedido manual e deixar o cliente B2B comprando com mais autonomia, {chama_sdr} no {phone}.\n\nUm abraço e sucesso!",
        10: f"Olá {nome}, tudo bem?\n\n{intro}\n\nComo vocês acabaram se desencontrando {com_sdr}, vamos pausar esse contato por enquanto.\n\nA ideia é não ficar insistindo no seu WhatsApp sem necessidade.\n\nSe ainda fizer sentido olhar para vendas B2B, portal do cliente e pedidos 24h, {chama_sdr} no {phone}.\n\nAbraço!",
    }
    msg = templates.get(tid)
    if not msg:
        msg = templates[1]
        tid = 1
    return tid, msg


def get_json(port, path, timeout=5):
    with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}', timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def active_senders(include_ports=None):
    include_ports = set(include_ports or []) if include_ports else None
    ok, errors = [], []
    for s in SENDERS:
        if include_ports and s['port'] not in include_ports:
            continue
        try:
            st = get_json(s['port'], '/status')
            me = get_json(s['port'], '/me')
            name = str(me.get('name') or '')
            # Do not require exact expected for João; phone/id is source of truth after QR.
            if me.get('id') and me.get('phone') and st.get('needsQR') is not True:
                ss = dict(s)
                ss['status'] = st
                ss['me'] = me
                ss['phone'] = str(me.get('phone') or '')
                ok.append(ss)
            else:
                errors.append({'port': s['port'], 'name': s['name'], 'status': st, 'me': me})
        except Exception as e:
            errors.append({'port': s['port'], 'name': s['name'], 'error': str(e)})
    return ok, errors


def buscar_deals_primeiro_contato():
    url = 'https://api.hubapi.com/crm/v3/objects/deals/search'
    body = {
        'filterGroups': [{'filters': [
            {'propertyName': 'pipeline', 'operator': 'EQ', 'value': PIPELINE},
            {'propertyName': 'dealstage', 'operator': 'EQ', 'value': STAGE_PRIMEIRO_CONTATO},
        ]}],
        'properties': ['dealname','dealstage','hubspot_owner_id','createdate','notes_last_updated','notes_last_contacted','hs_latest_meeting_activity','closed_lost_reason'],
        'limit': 100,
        'sorts': [{'propertyName': 'notes_last_updated', 'direction': 'ASCENDING'}],
    }
    out, after = [], None
    while True:
        if after:
            body['after'] = after
        else:
            body.pop('after', None)
        res = d.hs_request(url, 'POST', body)
        if not res:
            break
        out.extend(res.get('results') or [])
        after = ((res.get('paging') or {}).get('next') or {}).get('after')
        if not after:
            break
    return out


def local_already_sent_keys():
    keys = set()
    for r in d.load_envios():
        if not isinstance(r, dict):
            continue
        if str(r.get('msg_type') or '') != 'sumico_inicio_funil':
            continue
        for f in PHONE_FIELDS:
            k = d.normalize_phone(str(r.get(f) or ''))
            if k:
                keys.add(k)
    if LOG_JSONL.exists():
        for line in LOG_JSONL.read_text(encoding='utf-8').splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get('send_success'):
                k = d.normalize_phone(str(r.get('jid') or r.get('lead_phone') or ''))
                if k:
                    keys.add(k)
    return keys


def load_segmentacao_claude():
    if not SEGMENTACAO_CLAUDE.exists():
        return {}
    try:
        data = json.loads(SEGMENTACAO_CLAUDE.read_text(encoding='utf-8'))
    except Exception:
        return {}
    out = {}
    for row in data if isinstance(data, list) else []:
        did = str(row.get('deal_id') or '')
        frase = str(row.get('frase_sugerida') or '').strip()
        if did and frase:
            out[did] = row
    return out


def lead_from_deal(deal):
    props = deal.get('properties') or {}
    owner_id = str(props.get('hubspot_owner_id') or '')
    if owner_id not in OWNER_MAP:
        return None, 'owner_fora_escopo'
    cutoff = datetime.now(timezone.utc) - timedelta(days=CUTOFF_DAYS)
    candidates = [parse_dt(props.get(k)) for k in ('notes_last_updated','notes_last_contacted','hs_latest_meeting_activity')]
    last_activity = max([x for x in candidates if x], default=None)
    created = parse_dt(props.get('createdate'))
    effective_last = last_activity or created
    if not effective_last or effective_last >= cutoff:
        return None, 'atividade_recente_ou_sem_data'
    contact = d.get_contact_for_deal(deal['id'])
    if not contact:
        return None, 'sem_contato'
    contact_id, cprops = contact
    tel = d.extrair_telefone(cprops)
    if not tel:
        return None, 'sem_celular_valido'
    tel_raw, jid, tel_fmt = tel
    owner = OWNER_MAP[owner_id]
    erp = d.extrair_erp(cprops)
    return {
        'deal_id': str(deal['id']),
        'contact_id': str(contact_id),
        'dealname': props.get('dealname') or '',
        'owner_id': owner_id,
        'sdr_key': owner['key'],
        'sdr_name': owner['name'],
        'sdr_phone_display': owner['phone_display'],
        'sdr_phone_digits': owner['phone_digits'],
        'firstname': cprops.get('firstname') or '',
        'email': cprops.get('email') or '',
        'lead_phone': tel_raw,
        'jid': jid,
        'tel_fmt': tel_fmt,
        'erp': erp,
        'createdate': props.get('createdate'),
        'last_activity': effective_last.isoformat(),
        'last_activity_days': round((datetime.now(timezone.utc) - effective_last).total_seconds()/86400, 1),
    }, None


def write_preview(leads):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    stamp = now_brt().strftime('%Y%m%d_%H%M%S')
    json_path = OUTDIR / f'preview_{stamp}.json'
    csv_path = OUTDIR / f'preview_{stamp}.csv'
    rows = []
    for lead in leads:
        tid, msg = render_message(lead)
        row = dict(lead)
        row['template_id'] = tid
        row['message_text'] = msg
        rows.append(row)
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    with csv_path.open('w', encoding='utf-8', newline='') as f:
        fields = ['deal_id','contact_id','dealname','firstname','sdr_name','sdr_phone_display','lead_phone','tel_fmt','erp','last_activity_days','template_id','message_text']
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader(); w.writerows(rows)
    return json_path, csv_path, rows


def send_whatsapp(port, jid, text):
    body = json.dumps({'to': jid, 'text': text}).encode()
    req = urllib.request.Request(f'http://127.0.0.1:{port}/send', data=body, headers={'Content-Type':'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            return True, json.loads(resp.read().decode())
    except Exception as e:
        return False, {'error': str(e)}


def create_task(lead, sender, msg, resp):
    body_txt = (
        f"Campanha: {CAMPAIGN_ID}\n"
        f"Ação: encerramento por sumiço início de funil + perdido após envio confirmado.\n"
        f"Remetente: {sender['name']} porta {sender['port']} ({sender.get('phone','')})\n"
        f"Consultor/SDR de retorno: {lead['sdr_name']} {lead['sdr_phone_display']}\n"
        f"Destino: {lead['jid']}\n"
        f"MessageId: {(resp or {}).get('messageId')}\n\n"
        f"Texto enviado:\n{msg}"
    )
    data = {
        'properties': {
            'hs_timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
            'hs_task_subject': f"WhatsApp encerramento — sumiço início de funil — {lead['sdr_name']}",
            'hs_task_body': body_txt,
            'hs_task_status': 'COMPLETED',
            'hs_task_priority': 'MEDIUM',
            'hubspot_owner_id': lead['owner_id'],
        },
        'associations': [
            {'to': {'id': int(lead['contact_id'])}, 'types': [{'associationCategory':'HUBSPOT_DEFINED','associationTypeId':204}]},
            {'to': {'id': int(lead['deal_id'])}, 'types': [{'associationCategory':'HUBSPOT_DEFINED','associationTypeId':216}]},
        ]
    }
    res = d.hs_request('https://api.hubapi.com/crm/v3/objects/tasks', 'POST', data)
    return (res or {}).get('id')


def move_to_lost(lead):
    data = {'properties': {'dealstage': STAGE_PERDIDO, 'closed_lost_reason': LOST_REASON_VALUE}}
    res = d.hs_request(f"https://api.hubapi.com/crm/v3/objects/deals/{lead['deal_id']}", 'PATCH', data)
    props = (res or {}).get('properties') or {}
    return {'ok': props.get('dealstage') == STAGE_PERDIDO, 'dealstage': props.get('dealstage'), 'closed_lost_reason': props.get('closed_lost_reason')}


def append_log(rec):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    with LOG_JSONL.open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def register_envio(lead, sender, msg, resp, task_id, lost_result):
    sent_at = now_brt()
    d.registrar_envio({
        'date': sent_at.strftime('%Y-%m-%d %H:%M'),
        'date_tz': sent_at.isoformat(),
        'campaign_id': CAMPAIGN_ID,
        'to': lead['jid'],
        'jid': lead['jid'],
        'slug': d.slugify(lead.get('dealname') or ''),
        'nome': clean_first_name(lead.get('firstname')),
        'sdr': lead['sdr_name'],
        'sdr_phone': lead['sdr_phone_digits'],
        'sender_name': sender['name'],
        'sender_phone': sender.get('phone'),
        'bridge_port': sender['port'],
        'text': msg,
        'text_status': 'ok',
        'messageId': (resp or {}).get('messageId'),
        'send_response': resp,
        'empresa': lead.get('dealname'),
        'msg_type': 'sumico_inicio_funil',
        'deal_id': lead['deal_id'],
        'contact_id': lead['contact_id'],
        'task_id': task_id,
        'moved_to_lost': bool(lost_result.get('ok')),
        'lost_reason': LOST_REASON_VALUE,
    })


def sender_counts_today():
    today = now_brt().date()
    counts = {}
    for r in d.load_envios():
        if not isinstance(r, dict):
            continue
        try:
            dt = datetime.fromisoformat(str(r.get('date_tz')).replace('Z','+00:00')).astimezone(BRT)
        except Exception:
            continue
        if dt.date() == today and r.get('bridge_port'):
            counts[int(r['bridge_port'])] = counts.get(int(r['bridge_port']), 0) + 1
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--send', action='store_true', help='envia de verdade e move para perdido após sucesso')
    ap.add_argument('--limit', type=int, default=0, help='limite de envios nesta execução; 0 = todos na prévia')
    ap.add_argument('--delay', type=float, default=20.0)
    ap.add_argument('--include-port', action='append', type=int, default=[])
    ap.add_argument('--max-per-chip-day', type=int, default=30)
    args = ap.parse_args()

    print(f"Campanha {CAMPAIGN_ID} | send={args.send} | cutoff>{CUTOFF_DAYS}d")
    senders, sender_errors = active_senders(args.include_port or None)
    print('Chips ativos:')
    for s in senders:
        print(f"  - {s['name']} porta {s['port']} me={s['me']}")
    if sender_errors:
        print('Chips fora/erro:')
        for e in sender_errors:
            print('  - ' + json.dumps(e, ensure_ascii=False))
    if args.send and not senders:
        print('ERRO: nenhum chip ativo')
        sys.exit(2)

    deals = buscar_deals_primeiro_contato()
    print(f"Deals em Primeiro Contato: {len(deals)}")
    sent_keys = local_already_sent_keys()
    segmentacao = load_segmentacao_claude()
    leads, skipped = [], {}
    for deal in deals:
        lead, reason = lead_from_deal(deal)
        if reason:
            skipped[reason] = skipped.get(reason, 0) + 1
            continue
        if d.normalize_phone(lead['jid']) in sent_keys:
            skipped['ja_enviado_sumico'] = skipped.get('ja_enviado_sumico', 0) + 1
            continue
        if lead['deal_id'] in segmentacao:
            lead['frase_sugerida'] = segmentacao[lead['deal_id']].get('frase_sugerida')
            lead['segmento_claude'] = segmentacao[lead['deal_id']].get('segmento')
            lead['fonte_resumo_claude'] = segmentacao[lead['deal_id']].get('fonte_resumo')
        leads.append(lead)
    leads.sort(key=lambda x: (-x['last_activity_days'], x['sdr_name'], x['deal_id']))
    if args.limit and not args.send:
        leads_out = leads[:args.limit]
    else:
        leads_out = leads
    json_path, csv_path, rows = write_preview(leads_out)
    print(f"Elegíveis: {len(leads)} | prévia: {json_path} | {csv_path}")
    print('Pulados: ' + json.dumps(skipped, ensure_ascii=False, sort_keys=True))
    print('Amostra:')
    for r in rows[:10]:
        print(f"  - deal={r['deal_id']} {r['firstname']} | {r['dealname']} | {r['sdr_name']} | {r['tel_fmt']} | {r['last_activity_days']}d | tpl={r['template_id']}")
        print('    ' + r['message_text'].split('\n')[0])

    if not args.send:
        print('DRY-RUN concluído. Use --send --limit N para enviar.')
        return

    to_send = leads[:args.limit] if args.limit else leads
    if not to_send:
        print('Nada para enviar.')
        return
    counts_today = sender_counts_today()
    sent = failed = moved = 0
    sender_idx = 0
    for lead in to_send:
        # escolhe próximo sender ativo respeitando limite diário
        candidates = []
        for _ in range(len(senders)):
            s = senders[sender_idx % len(senders)]
            sender_idx += 1
            if counts_today.get(s['port'], 0) < args.max_per_chip_day:
                candidates.append(s); break
        if not candidates:
            print('Sem chips com limite diário disponível. Parando.')
            break
        sender = candidates[0]
        tid, msg = render_message(lead, sender)
        print(f"\n[{sent+failed+1}/{len(to_send)}] Enviando deal={lead['deal_id']} para {lead['tel_fmt']} via {sender['name']}:{sender['port']} tpl={tid}")
        ok, resp = send_whatsapp(sender['port'], lead['jid'], msg)
        rec = {'ts': now_brt().isoformat(), 'campaign_id': CAMPAIGN_ID, 'deal_id': lead['deal_id'], 'contact_id': lead['contact_id'], 'jid': lead['jid'], 'lead_phone': lead['lead_phone'], 'sender': sender, 'template_id': tid, 'message_text': msg, 'send_success': False, 'send_response': resp}
        if not ok or not resp.get('success'):
            print(f"  FALHA envio: {resp}")
            failed += 1
            append_log(rec)
            print('  Parando no primeiro erro para evitar duplicidade/ban.')
            break
        print(f"  OK WhatsApp messageId={resp.get('messageId')}")
        task_id = create_task(lead, sender, msg, resp)
        lost_result = move_to_lost(lead)
        print(f"  HubSpot task={task_id} lost={lost_result}")
        register_envio(lead, sender, msg, resp, task_id, lost_result)
        rec.update({'send_success': True, 'messageId': resp.get('messageId'), 'task_id': task_id, 'lost_result': lost_result})
        append_log(rec)
        sent += 1
        if lost_result.get('ok'):
            moved += 1
        counts_today[sender['port']] = counts_today.get(sender['port'], 0) + 1
        if sent < len(to_send):
            time.sleep(args.delay)
    print(f"\nResumo: enviados={sent} movidos_perdido={moved} falhas={failed} log={LOG_JSONL}")


if __name__ == '__main__':
    main()
