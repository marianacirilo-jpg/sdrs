#!/usr/bin/env python3
"""Quota central WhatsApp Zydon.

Shadow por padrão: calcula se bloquearia, mas não bloqueia envio até todos os
senders estarem migrados e Rafael autorizar enforcement.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Iterable

DEFAULT_LIMITS = {
    'cold_automation': {'per_port_hour': 8},
    'pipeline_followthrough': {'per_port_hour': 999},
    'active_conversation': {'per_port_hour': 999999},
    'internal': {'per_port_hour': 999999},
    'warmup': {'per_port_hour': 999999},
}

NON_COUNTED = {'active_conversation', 'internal', 'warmup'}


def _parse_dt(row: dict[str, Any]) -> datetime | None:
    for key in ('date_tz', 'ts', 'created_at', 'date'):
        raw = row.get(key)
        if not raw:
            continue
        try:
            s = str(raw).replace('Z', '+00:00')
            if key == 'date' and 'T' not in s:
                try:
                    return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=-3))).astimezone(timezone.utc)
                except Exception:
                    return datetime.strptime(s[:16], '%Y-%m-%d %H:%M').replace(tzinfo=timezone(timedelta(hours=-3))).astimezone(timezone.utc)
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def _logical_id(row: dict[str, Any]) -> str:
    return str(row.get('logical_message_id') or row.get('messageId') or row.get('id') or f"legacy:{id(row)}")


def _quota_class(row: dict[str, Any]) -> str:
    return str(row.get('quota_class') or ('internal' if str(row.get('to') or '').endswith('@g.us') else 'cold_automation'))


def _quota_counted(row: dict[str, Any]) -> bool:
    if row.get('quota_counted') is False:
        return False
    return _quota_class(row) not in NON_COUNTED


def rows_in_window(rows: Iterable[dict[str, Any]], *, now: datetime | None = None, seconds: int = 3600) -> list[dict[str, Any]]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = now - timedelta(seconds=seconds)
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        dt = _parse_dt(row)
        if not dt or start <= dt <= now:
            out.append(row)
    return out


def count_logical_sends(rows: Iterable[dict[str, Any]], *, quota_class: str | None = None, port: int | str | None = None, now: datetime | None = None, seconds: int = 3600) -> int:
    seen = set()
    for row in rows_in_window(rows, now=now, seconds=seconds):
        if quota_class and _quota_class(row) != quota_class:
            continue
        if port is not None:
            try:
                if int(row.get('bridge_port') or row.get('selected_port') or row.get('port') or 0) != int(port):
                    continue
            except Exception:
                continue
        if not _quota_counted(row):
            continue
        seen.add(_logical_id(row))
    return len(seen)


def check_quota(intent: dict[str, Any], *, rows: Iterable[dict[str, Any]] | None = None, limits: dict[str, dict[str, int]] | None = None, enforce: bool = False, now: datetime | None = None) -> dict[str, Any]:
    qc = str(intent.get('quota_class') or 'cold_automation')
    counted = intent.get('quota_counted') is not False and qc not in NON_COUNTED
    port = intent.get('selected_port') or intent.get('bridge_port') or intent.get('port')
    limits = limits or DEFAULT_LIMITS
    limit = int((limits.get(qc) or {}).get('per_port_hour', 999999))
    used = count_logical_sends(rows or [], quota_class=qc, port=port, now=now, seconds=3600) if counted else 0
    would_allow = (not counted) or used < limit
    return {
        'quota_class': qc,
        'quota_counted': bool(counted),
        'selected_port': port,
        'window_seconds': 3600,
        'used': used,
        'limit': limit,
        'allowed_if_enforced': would_allow,
        'allowed': would_allow if enforce else True,
        'shadow': not enforce,
        'reason': 'ok' if would_allow else 'quota_would_block',
    }
