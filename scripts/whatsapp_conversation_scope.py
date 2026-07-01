#!/usr/bin/env python3
"""Escopo central de escuta/condução de conversas WhatsApp Zydon.

Regra Rafael:
- Não escutar WhatsApp inteiro.
- Só escutar conversa iniciada por automação/disparo ativo/manual operacional.
- Nunca escutar conversa entre chips Zydon/comunicadores/SDRs.
- Se entrou no escopo, o agente é protagonista do relacionamento e mantém como
  pendente de follow-through até resolver ou escalar dúvida real.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Any

ROOT = Path('/root/.hermes/zydon-prospeccao')
CHANNEL_USERS_FILE = ROOT / 'controle' / 'channel_users.json'
CHANNEL_PORTS_FILE = ROOT / 'controle' / 'channel_ports.json'

SYSTEM_HISTORY_TYPES = {
    'cron-sdr-primeiro-contato',
    'primeiro_contato',
    'primeiro_contato_cadencia',
    'diagnostic_initial',
    'diagnostic_pdf',
    'diagnostic_question',
    'diagnostic_agenda_invite',
    'diagnostico_agenda_confirmacao',
    'diagnostico_agenda_lembrete',
    'nao_mql_legitimo_tratativa',
    'mql_followup1_deterministico',
}

SYSTEM_NATURES = {
    'first_contact',
    'followup_f1', 'followup_f2', 'followup_f3', 'followup_f4',
    'followup_f1_postdiag',
    'diagnostic_bundle', 'diagnostic_initial', 'diagnostic_pdf', 'diagnostic_question',
    'diagnostic_agenda_invite', 'agenda_confirmation', 'agenda_reminder',
    'non_mql_outreach', 'no_show_recovery', 'manual_reply',
}

SYSTEM_ORIGINS = {
    'manual_channel',
    'cron_active_mql', 'cron_diagnostic_pipeline', 'cron_followup_unificado',
    'cron_followup_postdiag', 'cron_agenda_queue', 'cron_agenda_monitor',
    'cron_non_mql', 'user_manual_script',
}

ESCALATION_MARKERS = (
    '(sem texto extraído)',
    'áudio',
    'imagem',
    'boleto',
    'contrato',
    'jurídico',
    'cancelar',
    'não quero',
    'pare de mandar',
    'remover',
    'humano',
)


def _load_json(path: Path, default: Any):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def digits(value: str | None) -> str:
    return ''.join(re.findall(r'\d+', str(value or '')))


def canonical_phone(value: str | None) -> str:
    d = digits(value)
    if d.startswith('55') and len(d) in (12, 13):
        return d
    if len(d) in (10, 11):
        return '55' + d
    return d


def jid_phone(jid: str | None) -> str:
    return canonical_phone(str(jid or '').split('@', 1)[0])


def zydon_chip_phones(users: dict | None = None, ports: dict | None = None) -> set[str]:
    """Retorna telefones/JIDs conhecidos dos chips Zydon.

    Além de dados explícitos futuros, mantém os comunicadores/SDRs conhecidos em
    memória operacional para bloquear escuta chip↔chip desde já.
    """
    known = {
        '553496698718',  # Rafael
        '553484255965',  # Mariana
        '553484095632',  # Sarah
        '553484295409',  # Lucas Batista
        '553484325076',  # Breno
    }
    users = users if users is not None else _load_json(CHANNEL_USERS_FILE, {})
    ports = ports if ports is not None else _load_json(CHANNEL_PORTS_FILE, {})
    for collection in (users or {}).values():
        for key in ('phone', 'jid', 'whatsapp', 'number'):
            if collection.get(key):
                known.add(jid_phone(collection.get(key)))
    for collection in (ports or {}).values():
        for key in ('phone', 'jid', 'whatsapp', 'number'):
            if collection.get(key):
                known.add(jid_phone(collection.get(key)))
    return {x for x in known if x}


def is_internal_chip_thread(chat_jid: str, *, users: dict | None = None, ports: dict | None = None) -> bool:
    phone = jid_phone(chat_jid)
    return bool(phone and phone in zydon_chip_phones(users, ports))


def _same_chat(row: dict, chat_jid: str, port: int | str | None = None) -> bool:
    target = jid_phone(chat_jid)
    candidates = [row.get('to'), row.get('jid'), row.get('conversation_id'), row.get('chat')]
    if target and any(jid_phone(c) == target for c in candidates if c):
        if port is None:
            return True
        row_port = row.get('bridge_port', row.get('port', row.get('selected_port')))
        return not row_port or str(row_port) == str(port)
    return False


def _ledger_initialized(ledger_rows: Iterable[dict], chat_jid: str, port: int | str | None) -> tuple[bool, str | None]:
    for row in ledger_rows or []:
        if not isinstance(row, dict) or not _same_chat(row, chat_jid, port):
            continue
        nature = str(row.get('nature') or row.get('msg_type') or row.get('campaign_id') or row.get('status') or '')
        if nature in SYSTEM_NATURES or nature in SYSTEM_HISTORY_TYPES or row.get('status') in ('enviado_lead', 'primeiro_contato'):
            return True, row.get('owner_sdr') or row.get('owner') or row.get('sdr')
    return False, None


def _audit_initialized(audit_rows: Iterable[dict], chat_jid: str, port: int | str | None) -> bool:
    for row in audit_rows or []:
        if not isinstance(row, dict) or not _same_chat(row, chat_jid, port):
            continue
        origin = str(row.get('origin') or row.get('source') or '')
        nature = str(row.get('nature') or row.get('msg_type') or '')
        if origin in SYSTEM_ORIGINS or nature in SYSTEM_NATURES:
            return True
    return False


def _history_initialized(history: Iterable[dict]) -> bool:
    for msg in history or []:
        if not isinstance(msg, dict) or not msg.get('fromMe'):
            continue
        typ = str(msg.get('type') or msg.get('msg_type') or msg.get('kind') or '')
        if typ in SYSTEM_HISTORY_TYPES or typ.startswith('cron-'):
            return True
    return False


def should_listen_to_incoming(*, port: int | str, chat_jid: str, history: list[dict] | None = None,
                              ledger_rows: list[dict] | None = None, audit_rows: list[dict] | None = None,
                              users: dict | None = None, ports: dict | None = None) -> dict:
    """Decide se uma resposta pode entrar no agente operacional.

    Política Rafael/Zydon 01/07:
    - comunicadores: apenas leads/contatos iniciados pela automação/Channel;
    - SDRs: todas as conversas 1:1 externas, mesmo sem origem de automação;
    - todos: nunca grupos e nunca conversas entre chips Zydon.

    Retorna sempre razão explícita para painel/log. Não envia mensagem.
    """
    if str(chat_jid or '').endswith('@g.us'):
        return {'listen': False, 'reason': 'group_thread', 'mode': 'blocked'}

    users = users if users is not None else _load_json(CHANNEL_USERS_FILE, {})
    ports = ports if ports is not None else _load_json(CHANNEL_PORTS_FILE, {})

    if is_internal_chip_thread(chat_jid, users=users, ports=ports):
        return {'listen': False, 'reason': 'internal_chip_thread', 'mode': 'blocked'}

    port_cfg = (ports or {}).get(str(port), {}) or {}
    role = str(port_cfg.get('role') or '').lower()

    ledger_ok, owner_sdr = _ledger_initialized(ledger_rows or [], chat_jid, port)
    initialized = ledger_ok or _audit_initialized(audit_rows or [], chat_jid, port) or _history_initialized(history or [])
    if initialized:
        return {
            'listen': True,
            'reason': 'system_initialized',
            'mode': 'agent_owns_relationship',
            'state': 'pending_agent_followthrough',
            'owner_sdr': owner_sdr,
        }

    if role == 'sdr':
        return {
            'listen': True,
            'reason': 'sdr_external_direct_thread',
            'mode': 'sdr_external_capture',
            'state': 'pending_agent_followthrough',
            'owner_sdr': port_cfg.get('owner'),
        }

    return {'listen': False, 'reason': 'not_system_initialized', 'mode': 'blocked'}


def classify_followthrough(text: str | None) -> dict:
    """Classificação mínima de condução: agente segue; só escala dúvida real.

    Preço é tratável pelo agente (regra Rafael: planos a partir de R$597/mês),
    portanto não escala só por preço.
    """
    raw = str(text or '').strip()
    low = raw.lower()
    if not raw or any(marker in low for marker in ESCALATION_MARKERS):
        return {
            'escalate': True,
            'next_state': 'pending_human_review',
            'reason': 'ambiguous_or_human_required',
        }
    return {
        'escalate': False,
        'next_state': 'pending_agent_followthrough',
        'reason': 'agent_can_continue',
    }
