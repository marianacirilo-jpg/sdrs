#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dedupe forte antes de qualquer diagnóstico MQL externo.

Consulta ledger histórico e fila de garantia. É deliberadamente conservador:
quando encontra envio concluído ou execução ativa para qualquer chave do lead,
bloqueia o envio e devolve motivo auditável.
"""
from __future__ import annotations

import json
from pathlib import Path

from mql_execution_queue import DEFAULT_QUEUE, dedupe_keys, load_queue, only_digits

ROOT = Path('/root/.hermes/zydon-prospeccao')
DEFAULT_LEDGER = ROOT / 'controle' / 'wpp_envios.json'
LEDGER_BLOCK_STATUSES = {
    'enviado_lead',
    'enviado_mql',
    'mql_diagnostico_em_andamento',
    'mql_diagnostico_rafael_texto',
    'mql_diagnostico_rafael_pdf',
    'mql_agenda_sdr_apos_diagnostico',
}
QUEUE_BLOCK_STATUSES = {'mql_confirmed', 'executing', 'blocked'}


def _load_ledger(path: str | Path = DEFAULT_LEDGER) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding='utf-8') or '{}')
    except Exception:
        return []
    rows = data.get('envios', data) if isinstance(data, dict) else data
    return [x for x in rows if isinstance(x, dict)] if isinstance(rows, list) else []


def phone_variants(phone: str) -> set[str]:
    k = only_digits(phone)
    if k.startswith('55') and len(k) in (12, 13):
        k = k[2:]
    vals = {k} if k else set()
    if len(k) == 11 and k[2] == '9':
        vals.add(k[:2] + k[3:])
    elif len(k) == 10 and k[2] in '6789':
        vals.add(k[:2] + '9' + k[2:])
    return {v for v in vals if v}


def _row_phone_values(row: dict) -> set[str]:
    vals = set()
    for field in ('phone', 'telefone', 'to', 'jid', 'lead_jid'):
        raw = str(row.get(field) or '')
        vals.update(phone_variants(raw))
    return vals


def _matches_ledger(row: dict, *, contact_id='', deal_id='', phone='', email='') -> tuple[bool, str]:
    email = str(email or '').strip().lower()
    contact_id = str(contact_id or '').strip()
    deal_id = str(deal_id or '').strip()
    phone_norms = phone_variants(phone)
    if email and str(row.get('email') or '').strip().lower() == email:
        return True, 'email'
    if contact_id and str(row.get('contact_id') or '').strip() == contact_id:
        return True, 'contact_id'
    if deal_id and str(row.get('deal_id') or '').strip() == deal_id:
        return True, 'deal_id'
    if phone_norms and (phone_norms & _row_phone_values(row)):
        return True, 'telefone'
    return False, ''


def _queue_block_reason(queue_path, keys: list[str]) -> str:
    queue = load_queue(queue_path)
    keyset = set(keys)
    for item in queue.get('items', []):
        if not (keyset & set(item.get('dedupe_keys') or [])):
            continue
        steps = item.get('steps') or {}
        if (steps.get('whatsapp_sent') or {}).get('status') == 'done':
            return f"fila {item.get('execution_id')} whatsapp_sent.done"
        status = str(item.get('status') or '').lower()
        if status in QUEUE_BLOCK_STATUSES:
            return f"fila {item.get('execution_id')} status {status}"
    return ''


def can_send_diagnostic(contact_id='', deal_id='', phone='', email='', company='', ledger_path: str | Path = DEFAULT_LEDGER, queue_path: str | Path = DEFAULT_QUEUE) -> tuple[bool, str]:
    keys = dedupe_keys(contact_id=contact_id, deal_id=deal_id, phone=phone, email=email)
    for row in reversed(_load_ledger(ledger_path)):
        status = str(row.get('status') or row.get('msg_type') or '').strip().lower()
        if status not in LEDGER_BLOCK_STATUSES:
            continue
        matched, field = _matches_ledger(row, contact_id=contact_id, deal_id=deal_id, phone=phone, email=email)
        if matched:
            return False, f'já enviado/em andamento: ledger status {status} por {field}'
    queue_reason = _queue_block_reason(queue_path, keys)
    if queue_reason:
        return False, f'já enviado/em andamento: {queue_reason}'
    return True, 'sem envio anterior encontrado'
