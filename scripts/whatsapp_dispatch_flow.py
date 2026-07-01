#!/usr/bin/env python3
"""Dual-write seguro para o fluxo unificado de disparos WhatsApp.

Esta camada é intencionalmente fail_open: se a fila falhar, o envio legado segue
funcionando. Ela NÃO envia WhatsApp; apenas registra a intenção na fila unificada
para que todos os crons/disparos passem a seguir o mesmo fluxo de observabilidade,
dedupe e futura execução por worker.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

try:
    from .whatsapp_dispatch_queue import enqueue_dispatch
    from .whatsapp_jid_utils import is_blocked_operational_target
except Exception:
    from whatsapp_dispatch_queue import enqueue_dispatch  # type: ignore
    from whatsapp_jid_utils import is_blocked_operational_target  # type: ignore


def _norm(value: Any) -> str:
    return str(value or '').strip()


def _logical_message_id(origin: str, nature: str, to: str, text: str, lead_key: str | None = None) -> str:
    raw = '|'.join([_norm(origin), _norm(nature), _norm(lead_key or to), _norm(text)])
    return 'lm_' + hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]


def record_dispatch_shadow(*, origin: str, to: str, text: str | None = None, nature: str,
                           owner_uid: str | None = None, lead_key: str | None = None,
                           port: int | str | None = None, sender_role: str | None = None,
                           thread_state: str = 'cold_outreach', quota_class: str | None = None,
                           logical_message_id: str | None = None, **extra) -> dict[str, Any]:
    """Registra intenção de disparo na fila unificada sem enviar WhatsApp.

    Retorna sempre um dict e nunca levanta exceção para o caller legado
    (fail_open=True), porque a prioridade desta fase é não interromper produção.
    Dedupe é feito dentro de `enqueue_dispatch` por lead/origin/nature/hash.
    """
    try:
        if is_blocked_operational_target(to):
            return {'ok': False, 'skipped': True, 'reason': 'internal_or_group_target'}
        body = text or ''
        logical_id = logical_message_id or _logical_message_id(origin, nature, to, body, lead_key)
        res = enqueue_dispatch(
            origin=origin,
            to=to,
            text=body,
            nature=nature,
            owner_uid=owner_uid,
            lead_key=lead_key or to,
            port=port,
            sender_role=sender_role,
            thread_state=thread_state,
            quota_class=quota_class,
            logical_message_id=logical_id,
            **extra,
        )
        return {'ok': bool(res.get('ok')), 'fail_open': False, 'deduped': bool(res.get('deduped')), 'dispatch_id': res.get('dispatch_id')}
    except Exception as exc:
        return {'ok': False, 'fail_open': True, 'error': str(exc)[:500]}


def record_dispatch_worker_owned(**kwargs) -> dict[str, Any]:
    """Registra intenção que PODE ser executada pelo worker live.

    Use somente em produtores que NÃO chamaram o envio legado. O worker live
    ignora tudo que não estiver com `execution_mode=worker_owned`.
    """
    kwargs['execution_mode'] = 'worker_owned'
    return record_dispatch_shadow(**kwargs)


def record_dispatch_shadow_from_row(row: dict[str, Any], *, origin: str, nature: str,
                                    thread_state: str = 'cold_outreach', text_field: str = 'text',
                                    owner_uid: str | None = None) -> dict[str, Any]:
    row = row or {}
    to = row.get('to') or row.get('jid') or row.get('lead_jid') or row.get('phone') or ''
    if not _norm(to) or is_blocked_operational_target(to):
        return {'ok': False, 'skipped': True, 'reason': 'internal_or_group_target'}
    return record_dispatch_shadow(
        origin=origin,
        nature=nature,
        thread_state=thread_state,
        to=to,
        text=row.get(text_field) or row.get('message_text') or row.get('texto') or '',
        owner_uid=owner_uid or row.get('owner_sdr') or row.get('sdr') or row.get('owner_uid') or row.get('owner_id'),
        lead_key=row.get('deal_id') or row.get('contact_id') or row.get('email') or row.get('slug') or row.get('to'),
        port=row.get('bridge_port') or row.get('port') or row.get('sender_port'),
        sender_role=row.get('sender_role') or row.get('sender_name') or row.get('sender'),
        legacy_status=row.get('status'),
        legacy_msg_type=row.get('msg_type'),
    )
