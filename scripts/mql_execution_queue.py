#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fila auditável de execução MQL → diagnóstico.

V1 propositalmente simples: JSON atômico + lock + helpers puros. Não envia
WhatsApp, não chama HubSpot e não muda o fluxo sozinho; só oferece uma camada de
garantia/idempotência para os scripts existentes.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path('/root/.hermes/zydon-prospeccao')
DEFAULT_QUEUE = ROOT / 'controle' / 'mql_execution_queue.json'
DEFAULT_LOCK = ROOT / 'controle' / 'mql_execution_queue.lock'
STEP_NAMES = ('pdf_generated', 'whatsapp_sent', 'hubspot_attached', 'group_notified')
ACTIVE_STATUSES = {'mql_confirmed', 'executing', 'blocked'}


def now_brt_iso() -> str:
    return datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat(timespec='seconds')


def only_digits(value: str | None) -> str:
    return re.sub(r'\D+', '', value or '')


def default_step_state() -> dict:
    return {'status': 'pending', 'at': None, 'error': None}


def default_steps() -> dict:
    return {name: default_step_state() for name in STEP_NAMES}


def load_queue(path: str | Path = DEFAULT_QUEUE) -> dict:
    path = Path(path)
    if not path.exists():
        return {'version': 1, 'items': []}
    try:
        data = json.loads(path.read_text(encoding='utf-8') or '{}')
    except Exception:
        return {'version': 1, 'items': []}
    if not isinstance(data, dict):
        return {'version': 1, 'items': []}
    data.setdefault('version', 1)
    if not isinstance(data.get('items'), list):
        data['items'] = []
    return data


def save_queue(data: dict, path: str | Path = DEFAULT_QUEUE) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    os.replace(tmp, path)


@contextlib.contextmanager
def with_queue_lock(lock_path: str | Path = DEFAULT_LOCK):
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('w') as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def dedupe_keys(contact_id: str | None = None, deal_id: str | None = None, phone: str | None = None, email: str | None = None) -> list[str]:
    keys: list[str] = []
    contact_id = str(contact_id or '').strip()
    deal_id = str(deal_id or '').strip()
    phone_norm = only_digits(phone)
    email_norm = str(email or '').strip().lower()
    if contact_id:
        keys.append(f'contact:{contact_id}')
    if deal_id:
        keys.append(f'deal:{deal_id}')
    if phone_norm:
        keys.append(f'phone:{phone_norm}')
    if email_norm:
        keys.append(f'email:{email_norm}')
    return list(dict.fromkeys(keys))


def execution_id(keys: list[str]) -> str:
    canonical = '|'.join(sorted(dict.fromkeys(k for k in keys if k)))
    digest = hashlib.sha1(canonical.encode('utf-8')).hexdigest()[:16]
    return f'mql:{digest}'


def _ensure_item_shape(item: dict) -> dict:
    keys = list(dict.fromkeys(item.get('dedupe_keys') or dedupe_keys(item.get('contact_id'), item.get('deal_id'), item.get('phone_norm') or item.get('phone'), item.get('email'))))
    item['dedupe_keys'] = keys
    item.setdefault('execution_id', execution_id(keys))
    item.setdefault('version', 1)
    item.setdefault('status', 'mql_confirmed')
    item.setdefault('created_at', now_brt_iso())
    item['updated_at'] = now_brt_iso()
    steps = item.setdefault('steps', {})
    for name in STEP_NAMES:
        base = default_step_state()
        base.update(steps.get(name) or {})
        steps[name] = base
    item.setdefault('retry', {'count': 0, 'next_retry_at': None, 'last_error': None})
    return item


def find_existing_item(queue: dict, keys: list[str]) -> dict | None:
    keyset = set(keys or [])
    if not keyset:
        return None
    for item in queue.get('items', []):
        if keyset & set(item.get('dedupe_keys') or []):
            return item
    return None


def upsert_mql_item(queue: dict, item: dict) -> tuple[dict, bool]:
    queue.setdefault('version', 1)
    queue.setdefault('items', [])
    shaped = _ensure_item_shape(dict(item))
    existing = find_existing_item(queue, shaped['dedupe_keys'])
    if existing:
        created_at = existing.get('created_at')
        old_steps = existing.get('steps') or {}
        old_retry = existing.get('retry') or {}
        existing.update({k: v for k, v in shaped.items() if v not in (None, '', [])})
        existing['created_at'] = created_at or shaped['created_at']
        existing['steps'] = old_steps or shaped['steps']
        for name in STEP_NAMES:
            existing['steps'].setdefault(name, default_step_state())
        existing['retry'] = old_retry or shaped['retry']
        existing['dedupe_keys'] = list(dict.fromkeys((existing.get('dedupe_keys') or []) + shaped['dedupe_keys']))
        existing['updated_at'] = now_brt_iso()
        return existing, False
    queue['items'].append(shaped)
    return shaped, True


def mark_step(queue: dict, execution_id_value: str, step: str, status: str, **fields) -> dict:
    if step not in STEP_NAMES:
        raise ValueError(f'etapa inválida: {step}')
    for item in queue.get('items', []):
        if item.get('execution_id') != execution_id_value:
            continue
        steps = item.setdefault('steps', {})
        state = steps.setdefault(step, default_step_state())
        state.update(fields)
        state['status'] = status
        state['at'] = fields.get('at') or now_brt_iso()
        if status == 'done':
            state['error'] = None
        item['updated_at'] = now_brt_iso()
        if all((item.get('steps') or {}).get(name, {}).get('status') in ('done', 'skipped_duplicate') for name in STEP_NAMES):
            item['status'] = 'completed'
        elif status in ('failed', 'blocked'):
            item['status'] = 'blocked'
        else:
            item.setdefault('status', 'executing')
        return item
    raise KeyError(f'execution_id não encontrado: {execution_id_value}')


def upsert_and_save(item: dict, path: str | Path = DEFAULT_QUEUE) -> tuple[dict, bool]:
    with with_queue_lock():
        queue = load_queue(path)
        saved, created = upsert_mql_item(queue, item)
        save_queue(queue, path)
        return saved, created
