#!/usr/bin/env python3
"""Disparo institucional para limpar backlog SDR (>72h) Sarah/Lucas.

Envia pelos chips institucionais Rafael (4607), Mariana (4600) e Lucas Resende
(4606), marca wpp_envios.json e cria task COMPLETED no HubSpot.
"""
import argparse
import importlib.util
import json
import random
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta

ROOT = '/root/.hermes/zydon-prospeccao'
DISPARO = f'{ROOT}/disparo_dinamico.py'

spec = importlib.util.spec_from_file_location('disparo_dinamico', DISPARO)
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

CAMPAIGN_DEFAULT = 'backlog_sarah_lucas_72h_2026_06_24'
BACKLOG_MSG_TYPES = {'primeiro_contato', 'primeiro_contato_backlog_institucional'}

SENDERS = [
    {'port': 4607, 'sender_name': 'Rafael', 'remetente': 'o Rafael', 'expected': 'Rafael Calixto'},
    {'port': 4600, 'sender_name': 'Mariana', 'remetente': 'a Mariana', 'expected': 'Mariana | Zydon'},
    {'port': 4606, 'sender_name': 'Lucas Resende', 'remetente': 'o Lucas Resende', 'expected': 'Lucas Resende'},
    # Lucas Batista autorizado por Rafael para acelerar backlog; mantém mensagem própria.
    {'port': 4603, 'sender_name': 'Lucas Batista', 'remetente': 'Lucas Batista', 'expected': 'Lucas Batista'},
]

OWNER_KEYS = ['sarah', 'lucas']


def now_brt():
    return datetime.now(timezone(timedelta(hours=-3)))


def normalize_envios_block_set(envios):
    out = set()
    for r in envios:
        if not isinstance(r, dict):
            continue
        if str(r.get('msg_type', '')).lower() not in BACKLOG_MSG_TYPES:
            continue
        for field in d.PHONE_FIELDS:
            key = d.normalize_phone(r.get(field, ''))
            if key:
                out.add(key)
    return out


def get_json(port, path, timeout=5):
    with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}', timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def healthy_senders():
    ok = []
    errors = []
    for s in SENDERS:
        port = s['port']
        try:
            st = get_json(port, '/status')
            me = get_json(port, '/me')
            name = me.get('name') or ''
            if st.get('connected') is True and st.get('needsQR') is False and me.get('id') and s['expected'].lower() in name.lower():
                ss = dict(s)
                ss['status'] = st
                ss['me'] = me
                ok.append(ss)
            else:
                errors.append(f"{port}: inválida status={st} me={me}")
        except Exception as e:
            errors.append(f"{port}: {e}")
    return ok, errors


def sent_count_recent(envios, port, campaign_id, hours=24):
    cutoff = datetime.now() - timedelta(hours=hours)
    total = 0
    for r in envios:
        if not isinstance(r, dict):
            continue
        if r.get('bridge_port') != port:
            continue
        if r.get('campaign_id') != campaign_id:
            continue
        raw = str(r.get('date', ''))[:19]
        dt = None
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
            try:
                dt = datetime.strptime(raw, fmt)
                break
            except Exception:
                pass
        if dt and dt >= cutoff:
            total += 1
    return total


def sender_weight(sender):
    return max(1, int(sender.get('weight', 1)))


def choose_sender(senders, envios, campaign_id, disabled_ports, planned_counts=None, lead=None):
    candidates = [s for s in senders if s['port'] not in disabled_ports]
    if not candidates:
        return None
    lead = lead or {}
    # Regra Rafael 24/06: em horário comercial, se o lead tem SDR dono,
    # usar o telefone do SDR dono — não Mariana/Rafael/Lucas Resende institucional.
    hour = now_brt().hour
    if now_brt().weekday() < 5 and 7 <= hour < 18:
        owner = (lead.get('sdr_original') or '').strip().lower()
        preferred = None
        if owner == 'lucas':
            preferred = 'Lucas Batista'
        elif owner == 'sarah':
            preferred = 'Sarah 2'
        elif owner == 'breno':
            preferred = 'Breno'
        if preferred:
            for s in candidates:
                if s.get('sender_name') == preferred:
                    return s
            return None
    planned_counts = planned_counts or {}
    # Rotação por lote atual, não pelo histórico da campanha: evita jogar muitos
    # seguidos no chip novo (ex.: Lucas Batista entrou depois com contagem menor).
    candidates.sort(key=lambda s: (planned_counts.get(s['port'], 0), s['port']))
    return candidates[0]


def clean_name(name):
    name = (name or '').strip().split()[0]
    if not name:
        return 'tudo bem'
    return name[:1].upper() + name[1:].lower()


def empresa_valida(empresa):
    e = (empresa or '').strip()
    low = e.lower()
    if (not e or low in ('sem nome', 'none', 'null') or 'não usar' in low or 'nao usar' in low
            or 'uso iterno' in low or 'uso interno' in low or set(e) <= {'.', '-', '_', ' '} or e.startswith('@')):
        return ''
    return e


def variant_index(lead, total):
    import hashlib
    key = f"{lead.get('deal_id')}|{lead.get('jid')}|{lead.get('empresa')}"
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % total


def owner_agenda(lead):
    owner = (lead.get('sdr_original') or '').strip().lower()
    if owner == 'sarah':
        return 'Sarah', 'https://meetings.hubspot.com/sarah-bento'
    if owner == 'lucas':
        return 'Lucas Batista', 'https://meetings.hubspot.com/lucas-alcantara-nogueira-batista'
    return '', ''


def segmento_contexto(empresa, erp):
    """Personalização leve por segmento/nome; evita mensagem genérica de massa."""
    txt = (empresa or '').lower()
    if any(k in txt for k in ['embalag', 'papel', 'papyrus', 'graf', 'cartucho']):
        base = 'como vocês organizam pedidos recorrentes, prazos e recompra dos clientes B2B'
    elif any(k in txt for k in ['pneu', 'mangueira', 'peça', 'peca', 'auto', 'carbura', 'filtro']):
        base = 'como vocês recebem pedidos de reposição e atendem clientes recorrentes sem depender só do WhatsApp'
    elif any(k in txt for k in ['cosmet', 'colch', 'vinicola', 'adega', 'alimento', 'supplement']):
        base = 'como vocês controlam carteira de clientes, recompra e pedidos recorrentes no digital'
    elif any(k in txt for k in ['constr', 'madeira', 'steel', 'design', 'obra']):
        base = 'como vocês organizam orçamento, pedido e acompanhamento dos clientes B2B'
    else:
        base = 'como vocês recebem pedidos B2B, recorrência e atendimento'
    erp = (erp or '').strip()
    if erp and erp.lower() not in ('outro', 'outros'):
        return f'{base}, principalmente considerando que vocês usam {erp}'
    return base


def build_message(lead, sender):
    nome = clean_name(lead.get('nome'))
    emp = empresa_valida(lead.get('empresa'))
    erp = (lead.get('erp') or '').strip()
    remetente = sender['remetente']
    empresa_txt = f"a empresa {emp}" if emp else "a sua empresa"
    empresa_da = f"da empresa {emp}" if emp else "da sua empresa"
    contexto = segmento_contexto(emp, erp)
    agenda_nome, agenda_url = owner_agenda(lead)
    agenda_txt = f"\n\nSe preferir já adiantar, a agenda do responsável ({agenda_nome}) é: {agenda_url}" if agenda_url else ''
    if sender.get('sender_name') == 'Lucas Batista':
        empresa_lucas = emp or 'sua empresa'
        return (
            f"Olá {nome}! Tudo bem?\n"
            f"Lucas aqui da Zydon.\n\n"
            f"Você solicitou um contato para fazer o *Diagnóstico Comercial B2B* da {empresa_lucas}.\n\n"
            f"Dei uma olhada rápida no cadastro e queria entender {contexto}. "
            f"Com isso eu consigo te direcionar para a conversa certa e executar o diagnóstico com você."
        )
    variants = [
        f"Oi, {nome}. Aqui é {remetente}, da Zydon. Vi o cadastro {empresa_da} e queria entender {contexto}. Dependendo do cenário, dá para organizar pedidos, atendimento e recompra em um canal B2B mais simples. Faz sentido eu te direcionar para uma conversa rápida?",
        f"Oi, {nome}. Aqui é {remetente}, da Zydon. Passei pelo interesse {empresa_da} e queria entender melhor: {contexto}. Se isso ainda fica espalhado em WhatsApp, ligação ou vendedor, consigo te mostrar um caminho mais organizado.",
        f"Oi, {nome}. Aqui é {remetente}, da Zydon. Vi que {empresa_txt} buscou a Zydon e achei que fazia sentido falar contigo por um ponto específico: {contexto}. Quer que eu te direcione para uma análise rápida?",
        f"Oi, {nome}. Aqui é {remetente}, da Zydon. Estou retomando alguns contatos que ficaram pendentes e o caso {empresa_da} chamou atenção. Queria entender {contexto}. Pode ser por aqui?",
        f"Oi, {nome}. Aqui é {remetente}, da Zydon. Pelo cadastro {empresa_da}, parece ter espaço para melhorar venda B2B digital. A pergunta principal é {contexto}. Se fizer sentido, já te passo para o responsável olhar contigo.",
    ]
    return variants[variant_index(lead, len(variants))] + agenda_txt


def create_task(lead, sender, text, campaign_id, send_resp):
    url = 'https://api.hubapi.com/crm/v3/objects/tasks'
    subject = f"WhatsApp — primeiro contato backlog enviado por {sender['sender_name']}"
    body_txt = (
        f"Primeiro contato de backlog enviado via WhatsApp institucional.\n\n"
        f"Campanha: {campaign_id}\n"
        f"Remetente: {sender['sender_name']} (porta {sender['port']})\n"
        f"Owner original: {lead['sdr_original']}\n"
        f"Lead: {lead.get('nome')} / {lead.get('empresa')}\n"
        f"Destino: {lead['jid']}\n"
        f"Resposta bridge: {json.dumps(send_resp, ensure_ascii=False)[:1000]}\n\n"
        f"Texto enviado:\n{text}"
    )
    body = {
        'properties': {
            'hs_timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'hs_task_subject': subject,
            'hs_task_body': body_txt,
            'hs_task_status': 'COMPLETED',
            'hs_task_priority': 'MEDIUM',
            'hubspot_owner_id': lead['owner_id'],
        },
        'associations': [
            {'to': {'id': int(lead['contact_id'])}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 204}]},
            {'to': {'id': int(lead['deal_id'])}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 216}]},
        ]
    }
    res = d.hs_request(url, 'POST', body)
    return res.get('id') if res else None


def collect_leads(min_age_hours=72):
    envios = d.load_envios()
    blocked = normalize_envios_block_set(envios)
    seen_batch = set(blocked)
    now = datetime.now(timezone.utc)
    leads = []
    stats = {}
    for key in OWNER_KEYS:
        bridge = d.BRIDGES[key]
        owner_id = bridge['owner_id']
        owner_name = bridge['owner_name']
        all_deals = d.buscar_deals_sem_tarefa(owner_id)
        ids = d.filtrar_deals_sem_atividade_valida(all_deals)
        s = {'elegiveis': 0, 'under_age': 0, 'sem_contato': 0, 'sem_tel': 0, 'ja_enviado': 0, 'prontos': 0}
        for deal in all_deals:
            if str(deal['id']) not in ids:
                continue
            s['elegiveis'] += 1
            props = deal.get('properties') or {}
            created = d.parse_hubspot_datetime(props.get('createdate'))
            if not created:
                s['under_age'] += 1
                continue
            age_h = (now - created).total_seconds() / 3600
            if age_h <= min_age_hours:
                s['under_age'] += 1
                continue
            res = d.get_contact_for_deal(deal['id'])
            if not res:
                s['sem_contato'] += 1
                continue
            contact_id, cprops = res
            tel = d.extrair_telefone(cprops)
            if not tel:
                s['sem_tel'] += 1
                continue
            tel_raw, jid, fmt = tel
            phone_key = d.normalize_phone(jid)
            if phone_key in seen_batch:
                s['ja_enviado'] += 1
                continue
            seen_batch.add(phone_key)
            s['prontos'] += 1
            leads.append({
                'sdr_original': owner_name,
                'owner_id': owner_id,
                'deal_id': str(deal['id']),
                'contact_id': str(contact_id),
                'empresa': (props.get('dealname') or '').strip(),
                'nome': (cprops.get('firstname') or '').strip(),
                'erp': d.extrair_erp(cprops) or '',
                'tel_fmt': fmt,
                'jid': jid,
                'idade_h': age_h,
                'createdate': props.get('createdate'),
            })
        stats[owner_name] = s
    # Mais novo primeiro dentro do backlog velho.
    leads.sort(key=lambda x: x['idade_h'])
    return leads, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--send', action='store_true')
    ap.add_argument('--limit', type=int, default=9)
    ap.add_argument('--min-age-hours', type=float, default=72)
    ap.add_argument('--campaign-id', default=CAMPAIGN_DEFAULT)
    ap.add_argument('--sleep-seconds', type=float, default=35)
    ap.add_argument('--only-ports', default='', help='CSV de portas autorizadas para este lote, ex: 4600,4606,4607')
    args = ap.parse_args()
    if args.send == args.dry_run:
        print('Use exatamente um: --dry-run ou --send')
        return 2

    senders, sender_errors = healthy_senders()
    if args.only_ports.strip():
        allowed = {int(x.strip()) for x in args.only_ports.split(',') if x.strip()}
        senders = [s for s in senders if s['port'] in allowed]
    print('Remetentes saudáveis:', [(s['port'], s['sender_name']) for s in senders])
    if sender_errors:
        print('Remetentes fora:', sender_errors)
    if not senders:
        print('Nenhum chip institucional saudável. Abortando.')
        return 1

    leads, stats = collect_leads(args.min_age_hours)
    print('Stats:', json.dumps(stats, ensure_ascii=False))
    print(f'Prontos coletados: {len(leads)} | limite={args.limit}')
    batch = leads[:args.limit]
    envios = d.load_envios()
    disabled_ports = set()
    sent = 0
    fail = 0
    planned_counts = {}
    for idx, lead in enumerate(batch, 1):
        envios = d.load_envios()
        lead_sdr = str(lead.get('sdr_original') or '').strip().lower()
        candidate_senders = [s for s in senders if not (lead_sdr == 'sarah' and s.get('sender_name') == 'Lucas Batista')]
        sender = choose_sender(candidate_senders, envios, args.campaign_id, disabled_ports, planned_counts, lead=lead)
        if not sender:
            print('Sem remetentes disponíveis após falhas. Abortando lote.')
            break
        planned_counts[sender['port']] = planned_counts.get(sender['port'], 0) + 1
        text = build_message(lead, sender)
        print(f"\n[{idx}] {lead['sdr_original']} -> {sender['sender_name']}:{sender['port']} | {lead['nome']} | {lead['empresa']} | {lead['tel_fmt']} | {lead['idade_h']/24:.1f}d")
        print(text)
        if args.dry_run:
            continue
        ok, resp = d.send_whatsapp(sender['port'], lead['jid'], text)
        if not ok:
            fail += 1
            disabled_ports.add(sender['port'])
            print(f"FALHA porta {sender['port']}: {resp}. Porta removida da rodada.")
            continue
        task_id = create_task(lead, sender, text, args.campaign_id, resp)
        registro = {
            'date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'to': lead['jid'],
            'nome': lead['nome'],
            'empresa': lead['empresa'],
            'slug': d.slugify(lead['empresa']),
            'sdr_original': lead['sdr_original'],
            'sdr': lead['sdr_original'],
            'sender_name': sender['sender_name'],
            'bridge_port': sender['port'],
            'text': text,
            'text_status': 'ok',
            'msg_type': 'primeiro_contato_backlog_institucional',
            'campaign_id': args.campaign_id,
            'deal_id': lead['deal_id'],
            'contact_id': lead['contact_id'],
            'task_id': task_id,
            'send_response': resp,
        }
        d.registrar_envio(registro)
        sent += 1
        print(f"ENVIADO ok | task={task_id} | resp={resp}")
        if idx < len(batch):
            time.sleep(args.sleep_seconds + random.uniform(0, 10))
    print(f"\nRESUMO: enviados={sent} falhas={fail} dry_run={args.dry_run}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
