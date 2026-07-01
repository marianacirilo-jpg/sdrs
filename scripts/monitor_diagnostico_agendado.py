#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Monitora agendamentos de diagnóstico nas agendas dos SDRs.

Quando um lead agenda diagnóstico com Sarah, Breno ou Lucas Batista pelo HubSpot
Meetings/Google sync, a automação:
- identifica reunião de diagnóstico associada a deal+contato;
- envia pelo WhatsApp do SDR a confirmação com link da reunião;
- lembra no dia da reunião para entrar pelo computador quando possível;
- move o negócio para Diagnóstico SDR;
- cria uma task de preparação para o SDR com contexto objetivo;
- grava estado local para não duplicar.

Por padrão roda em dry-run. Use --apply para escrever no HubSpot.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from whatsapp_safe_send import safe_send_text

ROOT = Path('/root/.hermes/zydon-prospeccao')
if str(ROOT / 'scripts') not in sys.path:
    sys.path.insert(0, str(ROOT / 'scripts'))
from zydon_operational_queues import append_wpp_envio_locked  # noqa: E402
from whatsapp_send_orchestrator import enrich_legacy_row  # noqa: E402
from whatsapp_dispatch_flow import record_dispatch_shadow_from_row  # noqa: E402
STATE_FILE = ROOT / 'controle' / 'diagnostico_agendado_processed.json'
WPP_FILE = ROOT / 'controle' / 'wpp_envios.json'
LOCK_FILE = ROOT / 'controle' / 'runtime' / 'diagnostico_agendado_monitor.lock'
OUTBOUND_AUDIT_FILE = ROOT / 'controle' / 'channel_outbound_audit.jsonl'
HUBSPOT_ENV = Path('/root/.hermes/credentials/hubspot.env')
HS = 'https://api.hubapi.com'
BRT = ZoneInfo('America/Sao_Paulo')

PIPELINE = '671008549'
STAGE_LABELS = {
    '984052829': 'Lead Sem Contato',
    '1388724005': 'Leads Inválidos',
    '1214320997': 'Primeiro Contato',
    '998099482': 'Retorno Contato',
    '1151853491': 'Diagnóstico SDR',
    '1269308723': 'Introdução',
    '984278846': 'Introdução',
    '984278847': 'Apresentação Comercial',
    '984278848': 'Apresentação Técnica',
    '984278849': 'Proposta/Negociação',
    '984278850': 'Negócio fechado',
    '984278851': 'Negócio perdido',
}
STAGE_DIAGNOSTICO_SDR = '1151853491'
EARLY_STAGES_CAN_MOVE = {'984052829', '1214320997', '998099482', '1151853491', '1388724005'}
CLOSED_DEAL_STAGES = {'984278850', '984278851'}  # Negócio fechado / Negócio perdido
CLOSED_STAGES = CLOSED_DEAL_STAGES  # compatibilidade com helpers de negócio aberto

SDRS = {
    '88063842': {'nome': 'Sarah', 'agenda': 'https://meetings.hubspot.com/sarah-bento', 'porta': 4601},
    '86265630': {'nome': 'Breno', 'agenda': 'https://meetings.hubspot.com/breno-mendonca', 'porta': 4605},
    '85778446': {'nome': 'Lucas Batista', 'agenda': 'https://meetings.hubspot.com/lucas-alcantara-nogueira-batista', 'porta': 4603},
}
GROUP_JID = '120363408131718880@g.us'
COMMUNICATOR_PORTS = [4600, 4606, 4607, 4609, 4610]
MEETING_PROPS = [
    'hs_meeting_title', 'hs_meeting_start_time', 'hs_meeting_end_time',
    'hs_meeting_body', 'hs_meeting_location', 'hs_meeting_source', 'hs_meeting_created_from_link_id',
    'hs_meeting_external_url', 'hubspot_owner_id', 'hs_timestamp', 'hs_createdate',
]
DEAL_PROPS = [
    'dealname', 'dealstage', 'pipeline', 'hubspot_owner_id', 'createdate',
    'qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados',
    'qual_erp_utiliza_', 'selecione_o_sistema_de_gesto_erp',
    'qual_o_faturamento_mensal_da_sua_empresa_', 'quantos_vendedores_sua_empresa_tem_',
    'como_voc_vende_hoje_', 'voc_possui_loja_virtual_',
]
CONTACT_PROPS = ['firstname', 'lastname', 'email', 'phone', 'mobilephone', 'hs_whatsapp_phone_number']

# === CONTRATOS FIXOS DE TEXTO/PROCESSO ===
# Rafael 29/06: estes modelos não devem ser reescritos ad hoc. Qualquer mudança
# precisa alterar constantes + testes snapshot em tests/test_monitor_diagnostico_agendado.py.
CONFIRMATION_LINK_LINE_TEMPLATE = 'Link para acessar: {link}'
CONFIRMATION_NO_LINK_LINE = 'O convite também ficou no seu e-mail/calendário.'
CONFIRMATION_COMPUTER_LINE = 'Se puder, entra pelo computador para a gente conseguir te mostrar melhor na prática.'
CONFIRMATION_RESCHEDULE_LINE = 'Caso queira alterar sua data ou horário do diagnóstico, pode me chamar por aqui que alinhamos o novo momento.'
CONFIRMATION_TEMPLATE = (
    '{nome}, aqui é {sdr_nome} da Zydon. Diagnóstico confirmado para {horario}.\n\n'
    '{link_line}\n\n'
    f'{CONFIRMATION_COMPUTER_LINE}\n\n'
    f'{CONFIRMATION_RESCHEDULE_LINE}'
)

REMINDER_LINK_LINE_TEMPLATE = 'Link: {link}'
REMINDER_NO_LINK_LINE = 'O link está no convite do calendário/e-mail.'
REMINDER_COMPUTER_LINE = 'Se conseguir entrar pelo computador, a experiência fica melhor para vermos o processo com calma.'
REMINDER_TEMPLATE = (
    '{nome}, passando para lembrar do nosso diagnóstico hoje às {horario}.\n\n'
    '{link_line}\n\n'
    f'{REMINDER_COMPUTER_LINE}'
)

GROUP_NO_LINK_LINE = 'Link: não localizado direto no HubSpot'
GROUP_TEMPLATE = (
    '📅 Diagnóstico agendado\n\n'
    '{empresa} marcou diagnóstico com {sdr_nome} para {horario}.\n'
    'Lead: {lead_nome}\n'
    '{link_line}'
)

LINK_DIRECT_HOSTS = ('meet.google.com', 'zoom.us', 'teams.microsoft.com')
BIDIRECTIONAL_SYNC_SOURCE = 'BIDIRECTIONAL_SYNC'
REMINDER_WINDOW_START_HOUR_BRT = 7
REMINDER_WINDOW_END_HOUR_BRT = 11
REMINDER_MIN_LEAD_TIME_MINUTES = 30
CONFIRMATION_REMINDER_MIN_GAP_HOURS = 2
PREP_TASK_LEAD_HOURS = 2


def load_token() -> str:
    for k in ('HUBSPOT_ACCESS_TOKEN', 'HUBSPOT_TOKEN', 'PRIVATE_APP_TOKEN', 'HUBSPOT_API_KEY'):
        v = os.environ.get(k)
        if v:
            return v.strip()
    if HUBSPOT_ENV.exists():
        for line in HUBSPOT_ENV.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            if k.strip() in ('HUBSPOT_ACCESS_TOKEN', 'HUBSPOT_TOKEN', 'PRIVATE_APP_TOKEN', 'HUBSPOT_API_KEY'):
                return v.strip().strip('"\'')
    raise SystemExit('HubSpot token não encontrado')

TOKEN = load_token()


def hs(method: str, path: str, payload=None):
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    last_error = None
    for attempt in range(4):
        req = urllib.request.Request(
            HS + path,
            data=data,
            headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'},
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read().decode('utf-8')
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            msg = e.read().decode('utf-8', 'ignore')[:1000]
            last_error = RuntimeError(f'HubSpot {method} {path} -> {e.code}: {msg}')
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise last_error
        except (urllib.error.URLError, TimeoutError) as e:
            last_error = RuntimeError(f'HubSpot {method} {path} -> network: {e}')
            if attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise last_error
    raise last_error or RuntimeError(f'HubSpot {method} {path} failed')


def parse_dt(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value) / 1000, timezone.utc)
    s = str(value).replace('Z', '+00:00')
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def brt_fmt(value):
    dt = parse_dt(value)
    if not dt:
        return str(value or '')
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BRT).strftime('%d/%m/%Y %H:%M')


def clean(v, limit=220):
    s = re.sub(r'\s+', ' ', str(v or '')).strip()
    return s[:limit]


def is_open_pipeline_deal(deal) -> bool:
    """True somente para negócios abertos no pipeline Zydon.

    Rafael 01/07: confirmação/lembrete de reunião e resumo do dia não podem sair
    para negócio ganho ou perdido, nem para objeto fora do pipeline principal.
    """
    props = (deal or {}).get('properties') or {}
    pipeline = str(props.get('pipeline') or '')
    stage = str(props.get('dealstage') or '')
    if pipeline != PIPELINE:
        return False
    if stage in CLOSED_STAGES:
        return False
    label = STAGE_LABELS.get(stage, '').lower()
    if 'ganho' in label or 'fechado' in label or 'perdido' in label:
        return False
    return True


def open_deal_skip_reason(deal) -> str:
    props = (deal or {}).get('properties') or {}
    pipeline = str(props.get('pipeline') or '') or 'sem pipeline'
    stage = str(props.get('dealstage') or '')
    label = STAGE_LABELS.get(stage, stage or 'sem etapa')
    if pipeline != PIPELINE:
        return f'fora do pipeline Zydon ({pipeline})'
    if stage in CLOSED_STAGES or 'ganho' in label.lower() or 'fechado' in label.lower() or 'perdido' in label.lower():
        return f'negócio fechado ({label})'
    return f'não aberto ({label})'


def first_name_from_contact(props):
    first = clean(props.get('firstname'))
    if first:
        return first.split()[0].capitalize()
    full = first_contact_name(props)
    return full.split()[0].capitalize() if full else 'Tudo bem'


def normalize_phone(value):
    digits = re.sub(r'\D+', '', str(value or ''))
    if not digits:
        return ''
    # HubSpot às vezes salva DDD+número sem 55. Só aceita formatos BR claros.
    if not digits.startswith('55'):
        if len(digits) in (10, 11):
            digits = '55' + digits
        else:
            return ''
    # Corrige celular BR legado sem o nono dígito quando possível.
    if digits.startswith('55') and len(digits) == 12 and digits[4] in '6789':
        digits = digits[:4] + '9' + digits[4:]
    if not (12 <= len(digits) <= 13):
        return ''
    return digits


def contact_phone(contact):
    cp = contact.get('properties') or {}
    for k in ('hs_whatsapp_phone_number', 'mobilephone', 'phone'):
        digits = normalize_phone(cp.get(k))
        if digits:
            return digits
    return ''


def phone_to_jid(phone):
    digits = normalize_phone(phone)
    return f'{digits}@c.us' if digits else ''


ENGAGEMENT_METADATA_ERRORS = {}


def engagement_metadata(meeting_id: str):
    """Lê metadados legados de meeting quando o CRM v3 omite o link Meet.

    Em reuniões vindas do Google Calendar (`BIDIRECTIONAL_SYNC`), o objeto v3 pode
    trazer só `hs_meeting_external_url` como link do evento do calendário, enquanto
    o link real da sala fica em `/engagements/v1/engagements/{id}.metadata.videoConferenceUrl`.
    Se essa consulta falhar, o monitor segura o envio em reuniões Google em vez
    de mandar texto incompleto dizendo que o link está no e-mail/calendário.
    """
    if not meeting_id:
        return {}
    try:
        data = hs('GET', f'/engagements/v1/engagements/{meeting_id}')
        ENGAGEMENT_METADATA_ERRORS.pop(str(meeting_id), None)
        meta = data.get('metadata') or {}
        return meta if isinstance(meta, dict) else {}
    except Exception as e:
        ENGAGEMENT_METADATA_ERRORS[str(meeting_id)] = str(e)[:500]
        return {}


def meeting_join_link(meeting):
    p = meeting.get('properties') or {}
    candidates = [p.get('hs_meeting_location'), p.get('hs_meeting_body'), p.get('hs_meeting_external_url')]
    meta = engagement_metadata(str(meeting.get('id') or p.get('hs_object_id') or ''))
    candidates.extend([
        meta.get('videoConferenceUrl'),
        meta.get('meetingLocation'),
        meta.get('location'),
        meta.get('body'),
    ])
    for c in candidates:
        text = str(c or '').replace('&amp;', '&')
        for m in re.finditer(r'https?://[^\s<>"]+', text):
            url = m.group(0).rstrip(').,;')
            # Link de acesso direto. Não mandar evento Google Calendar como se fosse sala da reunião.
            if any(host in url for host in LINK_DIRECT_HOSTS):
                return url
    return ''


def link_lookup_error(meeting):
    """Erro bloqueante ao consumir link legado em agenda Google.

    Para `BIDIRECTIONAL_SYNC`, não é seguro assumir "link no e-mail" se o endpoint
    legado falhou, porque o Meet costuma existir só em `metadata.videoConferenceUrl`.
    """
    p = meeting.get('properties') or {}
    mid = str(meeting.get('id') or p.get('hs_object_id') or '')
    if str(p.get('hs_meeting_source') or '') == BIDIRECTIONAL_SYNC_SOURCE:
        return ENGAGEMENT_METADATA_ERRORS.get(mid)
    return None


def should_block_for_missing_link(meeting, link):
    """Fail-closed só quando NÃO há link e o lookup legado falhou.

    Se já encontramos um link direto (Meet/Zoom/Teams) — venha ele do CRM v3 ou
    do metadata legado — a falha transitória do endpoint `/engagements` não deve
    segurar o envio: o link bom já está em mãos. O bloqueio existe apenas para o
    caso `BIDIRECTIONAL_SYNC` em que o link real não foi localizado e o legado,
    onde o Meet costuma morar, ficou indisponível — aí não mandamos texto
    incompleto dizendo "link no e-mail". Retorna a mensagem de erro a registrar
    quando deve bloquear, ou None quando pode seguir.
    """
    if link:
        return None
    return link_lookup_error(meeting)


def confirmation_message(meeting, deal, contact, sdr):
    mp = meeting.get('properties') or {}
    cp = contact.get('properties') or {}
    nome = first_name_from_contact(cp)
    horario = brt_fmt(mp.get('hs_meeting_start_time') or mp.get('hs_timestamp'))
    link = meeting_join_link(meeting)
    link_line = CONFIRMATION_LINK_LINE_TEMPLATE.format(link=link) if link else CONFIRMATION_NO_LINK_LINE
    return CONFIRMATION_TEMPLATE.format(
        nome=nome,
        sdr_nome=sdr['nome'],
        horario=horario,
        link_line=link_line,
    )


def reminder_message(meeting, deal, contact, sdr):
    mp = meeting.get('properties') or {}
    cp = contact.get('properties') or {}
    nome = first_name_from_contact(cp)
    horario = brt_fmt(mp.get('hs_meeting_start_time') or mp.get('hs_timestamp'))
    link = meeting_join_link(meeting)
    link_line = REMINDER_LINK_LINE_TEMPLATE.format(link=link) if link else REMINDER_NO_LINK_LINE
    return REMINDER_TEMPLATE.format(nome=nome, horario=horario, link_line=link_line)


def group_notification_message(meeting, deal, contact, sdr):
    mp = meeting.get('properties') or {}
    cp = contact.get('properties') or {}
    empresa = clean((deal.get('properties') or {}).get('dealname')) or clean(mp.get('hs_meeting_title')) or 'Lead sem empresa'
    nome = first_contact_name(cp)
    horario = brt_fmt(mp.get('hs_meeting_start_time') or mp.get('hs_timestamp'))
    link = meeting_join_link(meeting)
    link_line = REMINDER_LINK_LINE_TEMPLATE.format(link=link) if link else GROUP_NO_LINK_LINE
    return GROUP_TEMPLATE.format(
        empresa=empresa,
        sdr_nome=sdr.get('nome'),
        horario=horario,
        lead_nome=nome,
        link_line=link_line,
    )


def group_notification_batch_line(meeting, deal, contact, sdr):
    mp = meeting.get('properties') or {}
    cp = contact.get('properties') or {}
    empresa = clean((deal.get('properties') or {}).get('dealname')) or clean(mp.get('hs_meeting_title')) or 'Lead sem empresa'
    nome = first_contact_name(cp)
    horario = brt_fmt(mp.get('hs_meeting_start_time') or mp.get('hs_timestamp'))
    link = meeting_join_link(meeting) or 'link não localizado direto no HubSpot'
    return f"• {empresa} — {sdr.get('nome')} — {horario}. Lead: {nome}. Link: {link}"


def group_notification_batch_message(items):
    """Consolida 2+ reuniões no grupo para não perder avisos nem spammar.

    Quando várias agendas entram no mesmo tick, confirmação para lead continua
    individual, mas o grupo recebe um resumo único. Isso evita que `max_sends`
    bloqueie o aviso interno e deixe SDR/Rafael sem contexto.
    """
    if len(items) == 1:
        return items[0]['text']
    lines = [group_notification_batch_line(it['meeting'], it['deal'], it['contact'], it['sdr']) for it in items]
    return '📅 Diagnósticos agendados\n\n' + '\n'.join(lines)


def choose_communicator_port():
    for port in COMMUNICATOR_PORTS:
        try:
            urllib.request.urlopen(urllib.request.Request(f'http://localhost:{int(port)}/status'), timeout=5).read()
            return port
        except Exception:
            continue
    return None


def send_whatsapp(port, jid, text):
    # status fail-closed: se a bridge do SDR não estiver online, não improvisa outro chip.
    urllib.request.urlopen(urllib.request.Request(f'http://localhost:{int(port)}/status'), timeout=8).read()
    ok, resp = safe_send_text(port, jid, text, uid='monitor_diagnostico_agendado', timeout=30)
    return resp


def _norm_msg_text(text):
    return re.sub(r'\s+', ' ', str(text or '')).strip()


def _history_path(port):
    return Path(f'/root/.hermes/whatsapp-extra/channel_data/history_{int(port)}.json')


def recently_sent_same_text(port, jid, text, hours=36):
    """Fail-closed dedupe contra loop: audit/history real vencem estado local.

    Se o cron morrer antes de gravar `diagnostico_agendado_processed.json`, o
    próximo tick ainda precisa enxergar que a bridge já mandou a mensagem.
    """
    wanted = _norm_msg_text(text)
    if not wanted:
        return False
    targets = {str(jid or ''), str(jid or '').replace('@c.us', '@s.whatsapp.net'), str(jid or '').replace('@s.whatsapp.net', '@c.us')}
    cutoff = time.time() - hours * 3600
    if OUTBOUND_AUDIT_FILE.exists():
        try:
            for line in OUTBOUND_AUDIT_FILE.read_text(encoding='utf-8', errors='ignore').splitlines()[-3000:]:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get('event') != 'send' or int(r.get('port') or 0) != int(port):
                    continue
                ts = parse_dt(r.get('ts'))
                if ts and ts.timestamp() < cutoff:
                    continue
                if str(r.get('targetJid') or '') in targets and _norm_msg_text(r.get('textPreview')) == wanted:
                    return True
        except Exception:
            pass
    hp = _history_path(port)
    if hp.exists():
        try:
            rows = json.loads(hp.read_text(encoding='utf-8'))
            for m in rows if isinstance(rows, list) else []:
                if not isinstance(m, dict) or not m.get('fromMe'):
                    continue
                chat = str(m.get('chat') or (m.get('rawKey') or {}).get('remoteJid') or '')
                if chat not in targets:
                    continue
                try:
                    ts = float(m.get('timestamp') or 0)
                    ts = ts / 1000 if ts > 10000000000 else ts
                except Exception:
                    ts = 0
                if ts and ts < cutoff:
                    continue
                if _norm_msg_text(m.get('text') or m.get('caption')) == wanted:
                    return True
        except Exception:
            pass
    return False


def reserve_state(kind, mid, state, processed, confirmations, reminders, group_notified, sent_at):
    if kind == 'confirmation':
        confirmations.add(mid)
        sent_at[mid] = datetime.now(timezone.utc).isoformat()
    elif kind == 'reminder':
        reminders.add(mid)
    elif kind == 'group':
        group_notified.add(mid)
    elif kind == 'processed':
        processed.add(mid)
    persist_state_progress(state, processed, confirmations, reminders, group_notified, sent_at)


def append_wpp_envio(row):
    kind = str((row or {}).get('msg_type') or '')
    if str((row or {}).get('to') or '').endswith('@g.us') or (row or {}).get('status') == 'enviado_grupo':
        nature, thread_state = 'internal_group_alert', 'internal_only'
    elif 'lembrete' in kind:
        nature, thread_state = 'agenda_reminder', 'scheduled_meeting'
    elif 'confirmacao' in kind or 'confirmação' in kind:
        nature, thread_state = 'agenda_confirmation', 'scheduled_meeting'
    else:
        nature, thread_state = 'diagnostic_agenda_invite', 'scheduled_meeting'
    enriched = enrich_legacy_row(row, nature=nature, origin='cron_diagnostic_agenda_monitor', thread_state=thread_state)
    record_dispatch_shadow_from_row(enriched, origin='agenda', nature=nature, thread_state=thread_state)
    append_wpp_envio_locked(enriched, WPP_FILE)


def create_completed_task(subject, body_text, deal, contact, owner_id):
    body = {
        'properties': {
            'hs_timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'hs_task_subject': subject,
            'hs_task_body': body_text,
            'hs_task_status': 'COMPLETED',
            'hs_task_priority': 'MEDIUM',
            'hubspot_owner_id': str(owner_id or ''),
        },
        'associations': [
            {'to': {'id': int(contact['id'])}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 204}]},
            {'to': {'id': int(deal['id'])}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 216}]},
        ],
    }
    return hs('POST', '/crm/v3/objects/tasks', body).get('id')


def log_group_message(kind, text, send_resp, meeting, deal, contact, port):
    mp = meeting.get('properties') or {}
    row = {
        'date_tz': datetime.now(BRT).isoformat(),
        'status': 'enviado_grupo',
        'campaign_id': 'diagnostico_agendado_grupo',
        'msg_type': kind,
        'to': GROUP_JID,
        'bridge_port': port,
        'sender_name': f'Comunicador {port}',
        'deal_id': str(deal.get('id')),
        'contact_id': str(contact.get('id')),
        'empresa': clean((deal.get('properties') or {}).get('dealname')),
        'meeting_id': str(meeting.get('id')),
        'meeting_start': mp.get('hs_meeting_start_time') or mp.get('hs_timestamp'),
        'text': text,
        'bridge_response': send_resp,
    }
    append_wpp_envio(row)


def log_sent_message(kind, text, send_resp, meeting, deal, contact, sdr):
    mp = meeting.get('properties') or {}
    owner_id = str(mp.get('hubspot_owner_id') or '')
    jid = phone_to_jid(contact_phone(contact))
    row = {
        'date_tz': datetime.now(BRT).isoformat(),
        'status': 'enviado_lead',
        'campaign_id': 'diagnostico_agendado',
        'msg_type': kind,
        'to': jid,
        'bridge_port': sdr.get('porta'),
        'sender_name': sdr.get('nome'),
        'owner_id': owner_id,
        'sdr': sdr.get('nome'),
        'deal_id': str(deal.get('id')),
        'contact_id': str(contact.get('id')),
        'empresa': clean((deal.get('properties') or {}).get('dealname')),
        'meeting_id': str(meeting.get('id')),
        'meeting_start': mp.get('hs_meeting_start_time') or mp.get('hs_timestamp'),
        'text': text,
        'bridge_response': send_resp,
    }
    append_wpp_envio(row)
    subject = 'WhatsApp — confirmação de diagnóstico enviada' if kind == 'diagnostico_agenda_confirmacao' else 'WhatsApp — lembrete de diagnóstico enviado'
    body = '\n'.join([
        subject,
        f"Meeting ID: {meeting.get('id')}",
        f"Remetente: {sdr.get('nome')} (porta {sdr.get('porta')})",
        f"Destino: {jid}",
        f"Resposta bridge: {json.dumps(send_resp, ensure_ascii=False)[:1000]}",
        '',
        'Texto enviado:',
        text,
    ])
    return create_completed_task(subject, body, deal, contact, owner_id)


def should_send_day_reminder(meeting, state, now=None):
    """Lembrete único na manhã do dia da reunião.

    Regra Rafael: confirmação no ato do agendamento; outro momento é no dia da reunião,
    preferencialmente de manhã. Não lembrar colado na confirmação nem após a reunião.
    """
    now = now or datetime.now(timezone.utc)
    sent = set(str(x) for x in state.get('reminder_sent_meeting_ids', []))
    mid = str(meeting.get('id'))
    if mid in sent:
        return False
    mp = meeting.get('properties') or {}
    start = parse_dt(mp.get('hs_meeting_start_time') or mp.get('hs_timestamp'))
    if not start:
        return False
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    now_brt = now.astimezone(BRT)
    start_brt = start.astimezone(BRT)
    if now_brt.date() != start_brt.date() or start <= now:
        return False
    # Janela de manhã: manda a partir de 07:00 até 10:59 BRT. Para reunião cedo,
    # permite mandar se ainda faltam pelo menos 30min. Se a agenda for criada
    # depois das 11h para o mesmo dia, a confirmação com link já é suficiente;
    # não mandar segundo lembrete para não repetir.
    if not (REMINDER_WINDOW_START_HOUR_BRT <= now_brt.hour < REMINDER_WINDOW_END_HOUR_BRT):
        return False
    if start - now < timedelta(minutes=REMINDER_MIN_LEAD_TIME_MINUTES):
        return False
    # Evita confirmar e lembrar colado quando a reunião foi marcada no mesmo dia.
    confirmed_at = (state.get('confirmation_sent_at') or {}).get(mid)
    if confirmed_at:
        cdt = parse_dt(confirmed_at)
        if cdt and now - cdt < timedelta(hours=CONFIRMATION_REMINDER_MIN_GAP_HOURS):
            return False
    return True


def should_send_confirmation(meeting, now=None):
    """Confirmação só para reunião futura. Nunca confirma reunião já passada."""
    now = now or datetime.now(timezone.utc)
    mp = meeting.get('properties') or {}
    start = parse_dt(mp.get('hs_meeting_start_time') or mp.get('hs_timestamp'))
    if not start:
        return True
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return start > now


def load_state():
    base = {
        'processed_meeting_ids': [],
        'confirmation_sent_meeting_ids': [],
        'reminder_sent_meeting_ids': [],
        'group_notified_meeting_ids': [],
        'confirmation_sent_at': {},
    }
    if not STATE_FILE.exists():
        return base
    try:
        data = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        if isinstance(data, dict):
            for k, v in base.items():
                data.setdefault(k, v.copy() if isinstance(v, dict) else list(v))
            return data
    except Exception:
        pass
    return base


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state['processed_meeting_ids'] = list(dict.fromkeys(str(x) for x in state.get('processed_meeting_ids', [])))[-1000:]
    state['confirmation_sent_meeting_ids'] = list(dict.fromkeys(str(x) for x in state.get('confirmation_sent_meeting_ids', [])))[-1000:]
    state['reminder_sent_meeting_ids'] = list(dict.fromkeys(str(x) for x in state.get('reminder_sent_meeting_ids', [])))[-1000:]
    state['group_notified_meeting_ids'] = list(dict.fromkeys(str(x) for x in state.get('group_notified_meeting_ids', [])))[-1000:]
    state['confirmation_sent_at'] = dict(state.get('confirmation_sent_at') or {})
    tmp = STATE_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(STATE_FILE)


def persist_state_progress(state, processed, confirmations, reminders, group_notified, sent_at):
    """Persist dedupe immediately after a successful external send.

    The monitor can send WhatsApp and then spend time creating HubSpot task logs
    for many meetings. If cron times out before the final save_state(), the next
    run does not know the WhatsApp was already sent and repeats it. After the
    bridge confirms success, record the dedupe state before any slower logging.
    """
    state['processed_meeting_ids'] = sorted(processed)
    state['confirmation_sent_meeting_ids'] = sorted(confirmations)
    state['reminder_sent_meeting_ids'] = sorted(reminders)
    state['group_notified_meeting_ids'] = sorted(group_notified)
    state['confirmation_sent_at'] = sent_at
    state['last_run_at'] = datetime.now(timezone.utc).isoformat()
    save_state(state)


def search_recent_meetings(lookback_hours=240, limit=100):
    """Busca reuniões por dois caminhos:
    1) criadas recentemente (para confirmação imediata);
    2) agendas futuras/próximas (para lembrete no dia e lote autorizado da semana).
    """
    out = {}
    since_ms = int((time.time() - lookback_hours * 3600) * 1000)
    bodies = [
        {
            'filterGroups': [{'filters': [{'propertyName': 'hs_createdate', 'operator': 'GTE', 'value': str(since_ms)}]}],
            'properties': MEETING_PROPS,
            'sorts': [{'propertyName': 'hs_createdate', 'direction': 'DESCENDING'}],
            'limit': min(limit, 100),
        }
    ]
    now = datetime.now(timezone.utc)
    start_ms = int(now.timestamp() * 1000)
    end_ms = int((now + timedelta(days=14)).timestamp() * 1000)
    bodies.append({
        'filterGroups': [{'filters': [
            {'propertyName': 'hs_meeting_start_time', 'operator': 'GTE', 'value': str(start_ms)},
            {'propertyName': 'hs_meeting_start_time', 'operator': 'LTE', 'value': str(end_ms)},
        ]}],
        'properties': MEETING_PROPS,
        'sorts': [{'propertyName': 'hs_meeting_start_time', 'direction': 'ASCENDING'}],
        'limit': min(limit, 100),
    })
    for body in bodies:
        for m in hs('POST', '/crm/v3/objects/meetings/search', body).get('results', []):
            out[str(m.get('id'))] = m
    return list(out.values())


def assoc_ids(meeting_id: str, to_type: str):
    data = hs('GET', f'/crm/v3/objects/meetings/{meeting_id}/associations/{to_type}')
    return [str(x.get('id')) for x in data.get('results', []) if x.get('id')]


def assoc_ids_from(obj_type: str, obj_id: str, to_type: str):
    data = hs('GET', f'/crm/v3/objects/{obj_type}/{obj_id}/associations/{to_type}')
    return [str(x.get('id')) for x in data.get('results', []) if x.get('id')]


def associate_meeting_to_deal(meeting_id: str, deal_id: str):
    # TypeId 212 = meeting -> deal (HUBSPOT_DEFINED). Sem isso a auditoria
    # do funil enxerga Diagnóstico SDR sem reunião futura, mesmo quando a
    # reunião existe associada ao contato e o monitor usou fallback pelo contato.
    return hs('PUT', f'/crm/v4/objects/meetings/{meeting_id}/associations/deals/{deal_id}', [
        {'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 212}
    ])


def read_obj(obj_type: str, obj_id: str, props):
    return hs('GET', f'/crm/v3/objects/{obj_type}/{obj_id}?properties=' + ','.join(props))


def is_diagnostico_meeting(m):
    p = m.get('properties') or {}
    owner = str(p.get('hubspot_owner_id') or '')
    title = clean(p.get('hs_meeting_title'), 500).lower()
    source = str(p.get('hs_meeting_source') or '')
    # Agenda pública do SDR ou sync do calendário, mas apenas para reuniões com título de diagnóstico.
    if owner not in SDRS:
        return False
    if not re.search(r'diagn[oó]stic', title):
        return False
    # Evita capturar reuniões manuais antigas sem contexto se não houver título; título já obrigatório acima.
    return source in ('MEETINGS_PUBLIC', BIDIRECTIONAL_SYNC_SOURCE, 'CRM_UI', '')


def first_contact_name(props):
    return clean(((props.get('firstname') or '') + ' ' + (props.get('lastname') or '')).strip()) or clean(props.get('email')) or 'Lead'


def build_task_body(meeting, deal, contact, sdr_name):
    mp = meeting.get('properties') or {}
    dp = deal.get('properties') or {}
    cp = contact.get('properties') or {}
    area = dp.get('qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados')
    erp = dp.get('qual_erp_utiliza_') or dp.get('selecione_o_sistema_de_gesto_erp')
    fat = dp.get('qual_o_faturamento_mensal_da_sua_empresa_')
    vend = dp.get('quantos_vendedores_sua_empresa_tem_')
    venda = dp.get('como_voc_vende_hoje_')
    loja = dp.get('voc_possui_loja_virtual_')
    phone = cp.get('hs_whatsapp_phone_number') or cp.get('mobilephone') or cp.get('phone')
    body = [
        'Lead marcou diagnóstico com SDR pela agenda. Preparar conversa antes da reunião.',
        '',
        f"SDR: {sdr_name}",
        f"Reunião: {clean(mp.get('hs_meeting_title'))}",
        f"Horário: {brt_fmt(mp.get('hs_meeting_start_time') or mp.get('hs_timestamp'))} BRT",
        f"Lead: {first_contact_name(cp)}",
        f"Empresa/deal: {clean(dp.get('dealname'))}",
        f"E-mail: {clean(cp.get('email'))}",
        f"Telefone/WhatsApp: {clean(phone)}",
        f"Deal ID: {deal.get('id')}",
        f"Contato ID: {contact.get('id')}",
        '',
        'Contexto do formulário/HubSpot:',
        f"- Segmento/área: {clean(area) or 'não informado'}",
        f"- ERP: {clean(erp) or 'não informado'}",
        f"- Faturamento: {clean(fat) or 'não informado'}",
        f"- Vendedores: {clean(vend) or 'não informado'}",
        f"- Venda hoje: {clean(venda) or 'não informado'}",
        f"- Loja virtual: {clean(loja) or 'não informado'}",
        '',
        'Próxima ação na reunião:',
        '- Começar pelo objetivo/expectativa do lead: por que se cadastrou e o que chamou atenção na Zydon.',
        '- Mapear processo B2B antes de apresentar: cliente comprador, tabela/condição por cliente, recorrência, giro, pedido via vendedor/televendas/campo.',
        '- Não repetir pergunta se ela já foi feita e respondida no WhatsApp/diagnóstico; olhar histórico antes.',
    ]
    return '\n'.join(body)


def create_task(meeting, deal, contact, sdr_name):
    mp = meeting.get('properties') or {}
    start = parse_dt(mp.get('hs_meeting_start_time') or mp.get('hs_timestamp')) or datetime.now(timezone.utc)
    task_time = start - timedelta(hours=PREP_TASK_LEAD_HOURS)
    if task_time < datetime.now(timezone.utc):
        task_time = datetime.now(timezone.utc)
    body = {
        'properties': {
            'hs_timestamp': task_time.isoformat().replace('+00:00', 'Z'),
            'hs_task_subject': f"Preparar diagnóstico — {clean((deal.get('properties') or {}).get('dealname'))}",
            'hs_task_body': build_task_body(meeting, deal, contact, sdr_name),
            'hs_task_status': 'NOT_STARTED',
            'hs_task_priority': 'HIGH',
            'hubspot_owner_id': str((meeting.get('properties') or {}).get('hubspot_owner_id') or ''),
        },
        'associations': [
            {'to': {'id': int(contact['id'])}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 204}]},
            {'to': {'id': int(deal['id'])}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 216}]},
        ],
    }
    return hs('POST', '/crm/v3/objects/tasks', body).get('id')


def update_deal_stage(deal_id: str):
    return hs('PATCH', f'/crm/v3/objects/deals/{deal_id}', {'properties': {'dealstage': STAGE_DIAGNOSTICO_SDR}})


def process(args):
    state = load_state()
    processed = set(str(x) for x in state.get('processed_meeting_ids', []))
    confirmations = set(str(x) for x in state.get('confirmation_sent_meeting_ids', []))
    reminders = set(str(x) for x in state.get('reminder_sent_meeting_ids', []))
    group_notified = set(str(x) for x in state.get('group_notified_meeting_ids', []))
    sent_at = dict(state.get('confirmation_sent_at') or {})
    actions = []
    pending_group_notifications = []
    meetings = search_recent_meetings(args.lookback_hours, args.limit)
    if args.mark_existing:
        newly = 0
        for m in meetings:
            mid = str(m.get('id'))
            if not is_diagnostico_meeting(m):
                continue
            if mid not in processed:
                processed.add(mid)
                newly += 1
            confirmations.add(mid)  # não confirma reuniões antigas como se fossem novas
            group_notified.add(mid)  # não avisa no grupo reunião antiga como se fosse nova
        state['last_run_at'] = datetime.now(timezone.utc).isoformat()
        state['processed_meeting_ids'] = sorted(processed)
        state['confirmation_sent_meeting_ids'] = sorted(confirmations)
        state['group_notified_meeting_ids'] = sorted(group_notified)
        save_state(state)
        return [f'✅ Baseline criado: {newly} reuniões de diagnóstico existentes marcadas como já vistas; próximas novas terão confirmação automática.']

    for m in meetings:
        mid = str(m.get('id'))
        if not is_diagnostico_meeting(m):
            continue
        mp = m.get('properties') or {}
        owner = str(mp.get('hubspot_owner_id') or '')
        sdr = SDRS.get(owner) or {'nome': owner, 'porta': None}
        sdr_name = sdr.get('nome') or owner
        need_new_processing = mid not in processed
        need_confirmation = (mid not in confirmations) and should_send_confirmation(m)
        # Nunca mandar confirmação e lembrete do dia no mesmo ciclo. Se a reunião
        # apareceu agora, a confirmação já cumpre o papel; lembrete só em ciclo
        # posterior, respeitando `confirmation_sent_at`.
        need_reminder = (not need_confirmation) and should_send_day_reminder(m, state)
        need_group_notify = (mid not in group_notified) and should_send_confirmation(m)
        if not (need_new_processing or need_confirmation or need_reminder or need_group_notify):
            continue

        deal_ids = assoc_ids(mid, 'deals')
        contact_ids = assoc_ids(mid, 'contacts')
        # HubSpot Meetings pode criar a reunião antes de associar diretamente o deal.
        # Quando já há contato, usar o deal associado ao contato como fallback
        # evita perder confirmação/task por corrida de sincronização (ex.: ALLKIT).
        if not deal_ids and contact_ids:
            for cid in contact_ids:
                try:
                    deal_ids = assoc_ids_from('contacts', cid, 'deals')
                except Exception:
                    deal_ids = []
                if deal_ids:
                    actions.append(f"ℹ️ reunião {mid}: sem deal direto na reunião; usando deal associado ao contato {cid}")
                    break
        if not contact_ids:
            actions.append(f"⚠️ reunião {mid} ({clean(mp.get('hs_meeting_title'))}) sem associação de contato; não processei")
            if args.apply and need_new_processing:
                processed.add(mid)
            continue
        if not deal_ids:
            actions.append(f"⚠️ reunião {mid} ({clean(mp.get('hs_meeting_title'))}) sem deal associado; não processei")
            # Não marcar como processada: o HubSpot pode associar o deal minutos depois.
            continue
        deal = read_obj('deals', deal_ids[0], DEAL_PROPS)
        if not is_open_pipeline_deal(deal):
            actions.append(
                f"↩️ reunião {mid} / {clean((deal.get('properties') or {}).get('dealname'))}: "
                f"não processei confirmação/lembrete/grupo/task porque {open_deal_skip_reason(deal)}"
            )
            if args.apply:
                processed.add(mid)
                confirmations.add(mid)
                reminders.add(mid)
                group_notified.add(mid)
                persist_state_progress(state, processed, confirmations, reminders, group_notified, sent_at)
            continue
        if args.apply and deal_ids and mid:
            try:
                # Se chegamos ao deal por fallback via contato, persistir a associação
                # direta reunião->deal. Isso mantém a auditoria do funil e o HubSpot
                # coerentes e evita alerta repetido de Diagnóstico SDR sem reunião.
                direct_deals = assoc_ids(mid, 'deals')
                if str(deal['id']) not in direct_deals:
                    associate_meeting_to_deal(mid, str(deal['id']))
                    actions.append(f"🔗 reunião {mid}: associada diretamente ao deal {deal['id']}")
            except Exception as e:
                actions.append(f"⚠️ reunião {mid}: falha ao associar ao deal {deal_ids[0]}: {e}")
        contact = read_obj('contacts', contact_ids[0], CONTACT_PROPS)
        dp = deal.get('properties') or {}
        stage = str(dp.get('dealstage') or '')
        stage_label = STAGE_LABELS.get(stage, stage or 'sem etapa')
        if stage in CLOSED_DEAL_STAGES:
            actions.append(f"↩️ reunião {mid} / {clean(dp.get('dealname'))}: etapa {stage_label}; não enviei lembrete/confirmação/resumo nem aviso interno")
            if args.apply and need_new_processing:
                processed.add(mid)
            continue
        phone = contact_phone(contact)
        jid = phone_to_jid(phone)

        task_id = None
        if need_new_processing:
            if stage not in EARLY_STAGES_CAN_MOVE:
                actions.append(f"⚠️ reunião {mid} / {clean(dp.get('dealname'))}: etapa atual {stage_label}; não movi automaticamente")
            elif args.apply:
                if stage != STAGE_DIAGNOSTICO_SDR:
                    update_deal_stage(deal['id'])
                task_id = create_task(m, deal, contact, sdr_name)
            if args.apply:
                processed.add(mid)
            actions.append(
                f"✅ {'APLICADO' if args.apply else 'DRY-RUN'}: {clean(dp.get('dealname'))} marcou diagnóstico com {sdr_name} "
                f"({brt_fmt(mp.get('hs_meeting_start_time') or mp.get('hs_timestamp'))} BRT). "
                f"Etapa: {stage_label} -> Diagnóstico SDR. Task: {task_id or 'seria criada'}. Meeting: {mid}"
            )

        if need_confirmation:
            link = meeting_join_link(m)
            lookup_error = should_block_for_missing_link(m, link)
            if lookup_error:
                actions.append(f"⚠️ reunião {mid} / {clean(dp.get('dealname'))}: não enviei confirmação; falha ao consultar link legado do calendário ({lookup_error})")
                continue
            text = confirmation_message(m, deal, contact, sdr)
            if not link:
                actions.append(f"⚠️ <@551035817129148419> reunião {mid} / {clean(dp.get('dealname'))}: sem link direto Meet/Zoom/Teams no HubSpot após CRM v3 + engagement legado; confirmei dizendo que o link está no e-mail/calendário")
            if not jid:
                actions.append(f"⚠️ reunião {mid} / {clean(dp.get('dealname'))}: sem telefone para confirmar por WhatsApp")
                if args.apply:
                    confirmations.add(mid)
            elif not sdr.get('porta'):
                actions.append(f"⚠️ reunião {mid} / {clean(dp.get('dealname'))}: SDR sem porta configurada")
            elif args.apply:
                try:
                    if recently_sent_same_text(sdr['porta'], jid, text):
                        reserve_state('confirmation', mid, state, processed, confirmations, reminders, group_notified, sent_at)
                        actions.append(f"↩️ confirmação {mid} já encontrada no histórico/audit; não reenviei para {jid}")
                    elif args.max_sends is not None and args._sends_this_run >= args.max_sends:
                        actions.append(f"⏸️ limite seguro de envios por tick atingido; confirmação {mid} fica para o próximo ciclo")
                    else:
                        reserve_state('confirmation', mid, state, processed, confirmations, reminders, group_notified, sent_at)
                        resp = send_whatsapp(sdr['porta'], jid, text)
                        args._sends_this_run += 1
                        persist_state_progress(state, processed, confirmations, reminders, group_notified, sent_at)
                        log_task_id = log_sent_message('diagnostico_agenda_confirmacao', text, resp, m, deal, contact, sdr)
                        actions.append(f"📩 confirmação enviada por {sdr_name} para {jid}. Task log: {log_task_id}. Meeting: {mid}")
                except Exception as e:
                    actions.append(f"⚠️ falha ao enviar confirmação {mid} por {sdr_name}: {e}")
            else:
                actions.append(f"📩 DRY-RUN confirmação por {sdr_name} para {jid}: {text}")

        if need_group_notify:
            _group_link = meeting_join_link(m)
            lookup_error = should_block_for_missing_link(m, _group_link)
            if lookup_error:
                actions.append(f"⚠️ grupo {mid} / {clean(dp.get('dealname'))}: não avisei; falha ao consultar link legado do calendário ({lookup_error})")
                continue
            text = group_notification_message(m, deal, contact, sdr)
            if args.apply:
                # Não consumir o limite de envios para lead com avisos internos.
                # Agrupamos no fim do tick; assim 2-3 agendas viram um único aviso
                # no grupo e nenhuma reunião fica sem contexto por causa do max_sends.
                pending_group_notifications.append({
                    'mid': mid,
                    'text': text,
                    'meeting': m,
                    'deal': deal,
                    'contact': contact,
                    'sdr': sdr,
                    'sdr_name': sdr_name,
                })
                actions.append(f"📌 aviso de grupo {mid} enfileirado para lote seguro")
            else:
                actions.append(f"📣 DRY-RUN grupo: {text}")

        if need_reminder:
            link = meeting_join_link(m)
            lookup_error = should_block_for_missing_link(m, link)
            if lookup_error:
                actions.append(f"⚠️ lembrete {mid} / {clean(dp.get('dealname'))}: não enviei; falha ao consultar link legado do calendário ({lookup_error})")
                continue
            text = reminder_message(m, deal, contact, sdr)
            if not link:
                actions.append(f"⚠️ <@551035817129148419> lembrete {mid} / {clean(dp.get('dealname'))}: sem link direto Meet/Zoom/Teams após CRM v3 + engagement legado; enviei dizendo que o link está no convite do e-mail/calendário")
            if not jid:
                actions.append(f"⚠️ lembrete {mid} / {clean(dp.get('dealname'))}: sem telefone")
                if args.apply:
                    reminders.add(mid)
            elif not sdr.get('porta'):
                actions.append(f"⚠️ lembrete {mid} / {clean(dp.get('dealname'))}: SDR sem porta")
            elif args.apply:
                try:
                    if recently_sent_same_text(sdr['porta'], jid, text):
                        reserve_state('reminder', mid, state, processed, confirmations, reminders, group_notified, sent_at)
                        actions.append(f"↩️ lembrete {mid} já encontrado no histórico/audit; não reenviei para {jid}")
                    elif args.max_sends is not None and args._sends_this_run >= args.max_sends:
                        actions.append(f"⏸️ limite seguro de envios por tick atingido; lembrete {mid} fica para o próximo ciclo")
                    else:
                        reserve_state('reminder', mid, state, processed, confirmations, reminders, group_notified, sent_at)
                        resp = send_whatsapp(sdr['porta'], jid, text)
                        args._sends_this_run += 1
                        persist_state_progress(state, processed, confirmations, reminders, group_notified, sent_at)
                        log_task_id = log_sent_message('diagnostico_agenda_lembrete_dia', text, resp, m, deal, contact, sdr)
                        actions.append(f"⏰ lembrete do dia enviado por {sdr_name} para {jid}. Task log: {log_task_id}. Meeting: {mid}")
                except Exception as e:
                    actions.append(f"⚠️ falha ao enviar lembrete {mid} por {sdr_name}: {e}")
            else:
                actions.append(f"⏰ DRY-RUN lembrete por {sdr_name} para {jid}: {text}")

    if args.apply and pending_group_notifications:
        port = choose_communicator_port()
        if not port:
            mids = ', '.join(it['mid'] for it in pending_group_notifications)
            actions.append(f"⚠️ grupo: nenhum comunicador online para avisar reuniões {mids}; ficará pendente para o próximo ciclo")
        else:
            batch_text = group_notification_batch_message(pending_group_notifications)
            try:
                if recently_sent_same_text(port, GROUP_JID, batch_text):
                    for it in pending_group_notifications:
                        group_notified.add(it['mid'])
                    persist_state_progress(state, processed, confirmations, reminders, group_notified, sent_at)
                    actions.append(f"↩️ lote de grupo já encontrado no histórico/audit; não reenviei ({len(pending_group_notifications)} reuniões)")
                else:
                    resp = send_whatsapp(port, GROUP_JID, batch_text)
                    for it in pending_group_notifications:
                        group_notified.add(it['mid'])
                    persist_state_progress(state, processed, confirmations, reminders, group_notified, sent_at)
                    for it in pending_group_notifications:
                        log_group_message('diagnostico_agenda_aviso_grupo_lote' if len(pending_group_notifications) > 1 else 'diagnostico_agenda_aviso_grupo', batch_text, resp, it['meeting'], it['deal'], it['contact'], port)
                    if len(pending_group_notifications) == 1:
                        it = pending_group_notifications[0]
                        actions.append(f"📣 grupo avisado pela porta {port}: {clean((it['deal'].get('properties') or {}).get('dealname'))} / {it['sdr_name']}. Meeting: {it['mid']}")
                    else:
                        mids = ', '.join(it['mid'] for it in pending_group_notifications)
                        actions.append(f"📣 grupo avisado em lote pela porta {port}: {len(pending_group_notifications)} diagnósticos. Meetings: {mids}")
            except Exception as e:
                mids = ', '.join(it['mid'] for it in pending_group_notifications)
                actions.append(f"⚠️ falha ao avisar grupo em lote ({mids}): {e}")

    if args.apply:
        state['last_run_at'] = datetime.now(timezone.utc).isoformat()
        state['processed_meeting_ids'] = sorted(processed)
        state['confirmation_sent_meeting_ids'] = sorted(confirmations)
        state['reminder_sent_meeting_ids'] = sorted(reminders)
        state['group_notified_meeting_ids'] = sorted(group_notified)
        state['confirmation_sent_at'] = sent_at
        save_state(state)
    return actions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='escreve no HubSpot')
    ap.add_argument('--lookback-hours', type=int, default=240)
    ap.add_argument('--limit', type=int, default=100)
    ap.add_argument('--mark-existing', action='store_true', help='cria baseline sem processar reuniões já existentes')
    ap.add_argument('--max-sends', type=int, default=2, help='limite fail-safe de envios WhatsApp por tick')
    args = ap.parse_args()
    args._sends_this_run = 0
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open('w') as lf:
        try:
            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('monitor já em execução; skip seguro')
            return
        actions = process(args)
    if actions:
        print('\n'.join(actions))

if __name__ == '__main__':
    main()
