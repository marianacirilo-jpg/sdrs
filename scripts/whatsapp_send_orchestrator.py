#!/usr/bin/env python3
"""Orquestrador central de dispatch WhatsApp Zydon.

Camada de negócio acima do transporte seguro:
- prepara MessageIntent com natureza/origem/thread/quota;
- escolhe chip via whatsapp_routing;
- consulta quota em shadow/enforce;
- registra ledger central com lock;
- opcionalmente envia por whatsapp_safe_send.

Por padrão, funções de preparação/registro não mudam volume nem disparam WhatsApp.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
import sys

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

try:
    from .whatsapp_message_nature import build_logical_message
    from .whatsapp_quota_manager import check_quota
    from .whatsapp_routing import choose_outbound_port
    from .zydon_operational_queues import append_wpp_envio_locked
    from .whatsapp_safe_send import safe_send_text
except Exception:  # import por spec/file path nos testes e scripts legados
    from whatsapp_message_nature import build_logical_message
    from whatsapp_quota_manager import check_quota
    from whatsapp_routing import choose_outbound_port
    from zydon_operational_queues import append_wpp_envio_locked
    from whatsapp_safe_send import safe_send_text

ROOT = Path('/root/.hermes/zydon-prospeccao')
WPP_ENVIOS = ROOT / 'controle' / 'wpp_envios.json'

OWNER_LABELS = {
    'sarah': 'Sarah',
    'lucas_batista': 'Lucas Batista',
    'breno': 'Breno',
}


def now_brt_iso() -> str:
    return datetime.now(timezone(timedelta(hours=-3))).isoformat()


def _jid(to: str) -> str:
    raw = str(to or '').strip()
    if raw.endswith('@s.whatsapp.net') or raw.endswith('@c.us') or raw.endswith('@g.us'):
        return raw.replace('@c.us', '@s.whatsapp.net')
    digits = ''.join(ch for ch in raw if ch.isdigit())
    if digits and not digits.startswith('55') and len(digits) in (10, 11):
        digits = '55' + digits
    return (digits or raw) + '@s.whatsapp.net'


def prepare_intent(*, owner_uid: str, to: str, nature: str, origin: str, text: str | None = None,
                   thread_state: str = 'cold_outreach', lead_key: str | None = None,
                   rows: list[dict[str, Any]] | None = None,
                   users: dict[str, dict[str, Any]] | None = None,
                   ports: dict[int, dict[str, Any]] | None = None,
                   health: dict[int, dict[str, Any]] | None = None,
                   selected_port: int | str | None = None,
                   parts: list[dict[str, Any]] | None = None,
                   enforce_quota: bool = False,
                   **extra) -> dict[str, Any]:
    jid = _jid(to)
    routing = {'port': selected_port, 'mode': 'provided', 'reason': 'Porta fornecida pelo caller legado.'}
    if not selected_port:
        routing = choose_outbound_port(owner_uid, jid, lead_key=lead_key or jid, rows=rows or [], users=users, ports=ports, health=health)
        selected_port = routing.get('port')
    if not selected_port:
        raise RuntimeError(f'no_outbound_port: {routing.get("reason")}')
    normalized_parts = parts or [{'kind': 'text', 'text': text or '', 'part_nature': nature}]
    intent = build_logical_message(
        nature=nature,
        thread_state=thread_state,
        origin=origin,
        conversation_id=jid,
        selected_port=int(selected_port),
        owner_sdr=owner_uid,
        parts=normalized_parts,
        text=text,
        to=jid,
        **extra,
    )
    intent['status'] = 'prepared'
    intent['bridge_port'] = int(selected_port)
    intent['routing'] = routing
    intent['quota'] = check_quota(intent, rows=rows or [], enforce=enforce_quota)
    return intent


def ledger_row_from_intent(intent: dict[str, Any], send_result: dict[str, Any] | None = None, *, status: str | None = None) -> dict[str, Any]:
    send_result = send_result or {}
    row = dict(intent)
    legacy_status = row.pop('legacy_status', None)
    legacy_msg_type = row.pop('legacy_msg_type', None)
    row['status'] = status or legacy_status or row.get('status') or 'enviado_lead'
    row['msg_type'] = legacy_msg_type or row.get('msg_type') or row.get('nature')
    row['to'] = row.get('to') or row.get('conversation_id') or row.get('jid')
    row['jid'] = row.get('jid') or row['to']
    row['bridge_port'] = int(row.get('bridge_port') or row.get('selected_port'))
    row['date_tz'] = row.get('date_tz') or now_brt_iso()
    row['date'] = row.get('date') or row['date_tz'][:16].replace('T', ' ')
    row['sdr'] = row.get('sdr') or OWNER_LABELS.get(str(row.get('owner_sdr') or ''), row.get('owner_sdr'))
    row['sender_name'] = row.get('sender_name') or row.get('sdr')
    row['response'] = send_result
    mid = send_result.get('messageId') or send_result.get('id')
    if mid:
        row['messageId'] = mid
    if send_result.get('messageIds'):
        row['messageIds'] = send_result.get('messageIds')
    if send_result.get('parts'):
        row['sent_parts'] = send_result.get('parts')
    return row


def enrich_legacy_row(row: dict[str, Any], *, nature: str, origin: str, thread_state: str = 'cold_outreach',
                      owner_uid: str | None = None, parts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Adiciona envelope central a uma linha legada sem alterar semântica antiga.

    Usado na migração gradual: mantém `status`, `msg_type`, `bridge_port`, etc.
    do caller, mas acrescenta `nature`, `origin`, `quota_class`,
    `logical_message_id`, `quota_counted` e `parts` para quota/painel.
    """
    base = dict(row or {})
    selected_port = base.get('selected_port') or base.get('bridge_port') or base.get('port')
    to = base.get('to') or base.get('jid') or base.get('conversation_id') or ''
    intent = build_logical_message(
        nature=nature,
        thread_state=thread_state,
        origin=origin,
        conversation_id=_jid(to) if to else '',
        selected_port=selected_port,
        owner_sdr=owner_uid or base.get('owner_sdr') or base.get('sdr') or base.get('owner_id'),
        parts=parts or [{'kind': 'text', 'text': base.get('text') or '', 'part_nature': nature}],
        text=base.get('text') or '',
        to=_jid(to) if to else to,
    )
    for key in ('logical_message_id', 'conversation_id', 'selected_port', 'owner_sdr', 'nature', 'origin',
                'thread_state', 'quota_class', 'quota_counted', 'parts'):
        base.setdefault(key, intent.get(key))
    base.setdefault('jid', intent.get('jid'))
    base.setdefault('to', intent.get('to'))
    base.setdefault('legacy_status', intent.get('legacy_status'))
    base.setdefault('legacy_msg_type', intent.get('legacy_msg_type'))
    return base


def record_dispatch(intent: dict[str, Any], send_result: dict[str, Any] | None = None, *, path: str | Path = WPP_ENVIOS, status: str | None = None):
    row = ledger_row_from_intent(intent, send_result, status=status)
    return append_wpp_envio_locked(row, path=path)


def send_text_intent(intent: dict[str, Any], *, timeout: int = 30, record: bool = True, path: str | Path = WPP_ENVIOS) -> tuple[bool, dict[str, Any]]:
    quota = intent.get('quota') or {}
    if quota and quota.get('allowed') is False:
        return False, {'success': False, 'error': 'quota_blocked', 'quota': quota}
    port = int(intent.get('selected_port') or intent.get('bridge_port'))
    to = intent.get('to') or intent.get('conversation_id') or intent.get('jid')
    text = intent.get('text') or ''
    ok, resp = safe_send_text(port, to, text, uid=f"{intent.get('origin')}:{intent.get('logical_message_id')}", timeout=timeout)
    result = dict(resp or {}) if isinstance(resp, dict) else {'raw': resp}
    result.setdefault('success', bool(ok))
    if record:
        record_dispatch(intent, result, path=path)
    return ok, result
