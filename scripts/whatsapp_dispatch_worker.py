#!/usr/bin/env python3
"""Worker seguro da fila unificada de disparos WhatsApp Zydon.

Fase atual: shadow/dry-run por padrão. O worker prova a capacidade de reservar
até 10 conversas simultâneas, respeitando lock por chip/destino/dedupe, mas NÃO
envia WhatsApp e NÃO chama bridge enquanto `dry_run=True`.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

try:
    from .whatsapp_dispatch_queue import (
        DISPATCH_QUEUE,
        acquire_dispatch_batch,
        acquire_chip_batch,
        chip_lock_metrics,
        dispatch_capacity_policy,
        dispatch_scale_config,
        mark_dispatch_status,
        schedule_retry,
        _iso,  # módulo interno, usado só para timestamp consistente
        _now,
    )
    from .whatsapp_safe_send import safe_post_bridge
    from .whatsapp_worker_completions import complete_after_send
    from .whatsapp_jid_utils import is_blocked_operational_target
except Exception:
    from whatsapp_dispatch_queue import (  # type: ignore
        DISPATCH_QUEUE,
        acquire_dispatch_batch,
        acquire_chip_batch,
        chip_lock_metrics,
        dispatch_capacity_policy,
        dispatch_scale_config,
        mark_dispatch_status,
        schedule_retry,
        _iso,
        _now,
    )
    from whatsapp_safe_send import safe_post_bridge  # type: ignore
    from whatsapp_worker_completions import complete_after_send  # type: ignore
    from whatsapp_jid_utils import is_blocked_operational_target  # type: ignore


def _worker_id() -> str:
    return f"dispatch-worker-shadow-{socket.gethostname()}"


def _requeue_shadow(dispatch_id: str, *, path: str | Path, now: datetime, reason: str = 'shadow_checked') -> dict[str, Any] | None:
    return mark_dispatch_status(
        dispatch_id,
        'queued',
        path=path,
        now=now,
        shadow_checked_at=_iso(now),
        worker_mode='dry_run',
        last_shadow_result=reason,
    )


def _bridge_message_ok(resp: Any) -> bool:
    txt = json.dumps(resp or {}, ensure_ascii=False)
    return bool(isinstance(resp, dict) and (resp.get('messageId') or resp.get('id') or resp.get('status') in (1, 2, '1', '2') or 'messageId' in txt or '"status": 1' in txt or '"status":2' in txt or '"status": 2' in txt))


def _default_transport(row: dict[str, Any]) -> dict[str, Any]:
    kind = str(row.get('kind') or 'text').lower()
    if kind in {'file', 'document', 'pdf'}:
        payload = {'to': row['jid']}
        for key in ('filePath', 'fileName', 'thumbnailPath', 'caption'):
            if row.get(key):
                payload[key] = row.get(key)
        return safe_post_bridge(int(row['port']), '/send-file', payload, uid='whatsapp_dispatch_worker', timeout=120)
    return safe_post_bridge(int(row['port']), '/send', {'to': row['jid'], 'text': row.get('text') or ''}, uid='whatsapp_dispatch_worker', timeout=90)


def _part_to_candidate(row: dict[str, Any], part: Any) -> dict[str, Any]:
    candidate = dict(row)
    if isinstance(part, dict):
        candidate.update(part)
        kind = str(candidate.get('kind') or 'text').lower()
        candidate['kind'] = kind
        if kind in {'file', 'document', 'pdf'}:
            candidate['text'] = candidate.get('caption') or candidate.get('fileName') or row.get('text') or ''
        else:
            candidate['text'] = str(candidate.get('text') or '').strip()
        return candidate
    candidate['kind'] = 'text'
    candidate['text'] = str(part or '').strip()
    return candidate


def _part_is_present(part: Any) -> bool:
    if isinstance(part, dict):
        kind = str(part.get('kind') or 'text').lower()
        if kind in {'file', 'document', 'pdf'}:
            return bool(part.get('filePath') or part.get('url') or part.get('media'))
        return bool(str(part.get('text') or '').strip())
    return bool(str(part or '').strip())


def _part_preview(candidate: dict[str, Any]) -> str:
    if str(candidate.get('kind') or 'text').lower() in {'file', 'document', 'pdf'}:
        return str(candidate.get('fileName') or candidate.get('filePath') or '').strip()
    return str(candidate.get('text') or '').strip()


def _send_parts_sequence(row: dict[str, Any], send) -> dict[str, Any] | None:
    raw_parts = [p for p in (row.get('parts') or []) if _part_is_present(p)]
    if not raw_parts:
        return None
    responses = []
    ids = []
    schedule = row.get('delay_schedule') or []
    for idx, part in enumerate(raw_parts, 1):
        candidate = _part_to_candidate(row, part)
        resp = send(candidate)
        resp = resp if isinstance(resp, dict) else {'response': resp}
        responses.append({'part': idx, 'text': part, 'ok': _bridge_message_ok(resp), 'response': dict(resp)})
        if not _bridge_message_ok(resp):
            return {'ok': False, 'error': 'partial_sequence_failed', 'failed_part': idx, 'responses': responses}
        mid = resp.get('messageId') or resp.get('id')
        if mid:
            ids.append(mid)
        if idx < len(raw_parts):
            try:
                wait = float(schedule[idx - 1]) if idx - 1 < len(schedule) else 0.0
            except Exception:
                wait = 0.0
            if wait > 0:
                time.sleep(wait)
    return {'success': True, 'messageId': ids[-1] if ids else None, 'messageIds': ids, 'parts': len(raw_parts), 'responses': responses, 'to': row.get('jid')}


def _send_with_alternates(row: dict[str, Any], send) -> dict[str, Any]:
    attempts = []
    jids = [row.get('jid')]
    for alt in row.get('alternate_jids') or []:
        if alt and alt not in jids:
            jids.append(alt)
    last_resp: dict[str, Any] | None = None
    for jid in jids:
        candidate = dict(row)
        candidate['jid'] = jid
        seq_resp = _send_parts_sequence(candidate, send)
        resp = seq_resp if seq_resp is not None else send(candidate)
        last_resp = resp if isinstance(resp, dict) else {'response': resp}
        attempts.append({'jid': jid, 'response': dict(last_resp)})
        if _bridge_message_ok(last_resp):
            last_resp.setdefault('to', jid)
            last_resp['worker_attempts'] = attempts
            return last_resp
    out = last_resp or {'ok': False, 'error': 'no_attempts'}
    out['worker_attempts'] = attempts
    return out


def _validate_live_row(row: dict[str, Any]) -> str | None:
    if str(row.get('execution_mode') or 'shadow') != 'worker_owned':
        return 'not_worker_owned'
    if not row.get('port') or not row.get('jid') or not str(row.get('text') or '').strip():
        return 'missing_port_or_text_or_jid'
    if is_blocked_operational_target(row.get('jid')):
        return 'internal_or_group_target_blocked'
    return None


def _handle_live_failure(row: dict[str, Any], last_error: str, *, path: str | Path, ts: datetime,
                         result: dict[str, Any], retry=None, bridge_response: Any = None) -> None:
    """Falha de envio: retry controlado (se houver) ou falha terminal.

    `retry=None` reproduz o comportamento conservador atual (marca `failed`).
    Quando um callback de retry é passado (caminho por-chip com flag ligada),
    ele decide requeue com backoff x falha definitiva — sem reenviar nada já
    confirmado.
    """
    if retry is not None:
        outcome = retry(row, last_error) or {}
        if outcome.get('retried'):
            result['retried'] = result.get('retried', 0) + 1
            return
    extra = {}
    if bridge_response is not None:
        extra['bridge_response'] = bridge_response
    mark_dispatch_status(row['dispatch_id'], 'failed', path=path, now=ts, last_error=last_error,
                         worker_mode='live', **extra)
    result['failed'] += 1


def _process_live_row(row: dict[str, Any], *, send, completion_callback, path: str | Path,
                      ts: datetime, result: dict[str, Any], retry=None) -> None:
    """Executa um disparo worker_owned e registra o resultado no `result`.

    Mesma lógica usada pelo `run_once` live; extraída para ser reaproveitada
    pelo caminho por-chip sem duplicar código nem alterar o comportamento atual.
    """
    reason = _validate_live_row(row)
    if reason:
        mark_dispatch_status(row['dispatch_id'], 'blocked', path=path, now=ts, last_error=reason, worker_mode='live')
        result['blocked'] += 1
        return
    try:
        resp = _send_with_alternates(row, send)
    except Exception as exc:
        _handle_live_failure(row, str(exc)[:500], path=path, ts=ts, result=result, retry=retry)
        return
    if _bridge_message_ok(resp):
        completion_result = {}
        try:
            completion_result = (completion_callback or complete_after_send)(row, resp) or {}
            if completion_result.get('ok') is False:
                result['completion_failed'] += 1
            else:
                result['completed'] += 1
        except Exception as exc:
            completion_result = {'ok': False, 'error': str(exc)[:500]}
            result['completion_failed'] += 1
        mark_dispatch_status(row['dispatch_id'], 'sent', path=path, now=ts, worker_mode='live', bridge_response=resp, completion_result=completion_result, messageId=(resp or {}).get('messageId') or (resp or {}).get('id'))
        result['sent'] += 1
    else:
        _handle_live_failure(row, json.dumps(resp, ensure_ascii=False)[:500], path=path, ts=ts,
                             result=result, retry=retry, bridge_response=resp)


def run_once(*, path: str | Path = DISPATCH_QUEUE, dry_run: bool = True,
             max_simultaneous: int | None = None, now: datetime | None = None,
             transport=None, completion_callback=None) -> dict[str, Any]:
    """Processa um lote da fila.

    `dry_run=True` é o modo seguro atual: reserva lote, mede capacidade e devolve
    tudo para `queued`. `dry_run=False` fica bloqueado propositalmente até os
    senders fazerem dual-write e o transporte por worker ser validado.
    """
    ts = _now(now)
    policy = dispatch_capacity_policy(max_simultaneous=max_simultaneous or 10)
    limit = min(int(max_simultaneous or policy['maxSimultaneousConversations']), policy['maxSimultaneousConversations'])
    worker = _worker_id()
    batch = acquire_dispatch_batch(
        path=path,
        max_items=limit,
        locked_by=worker,
        now=ts,
        execution_modes=None if dry_run else ['worker_owned'],
    )
    result = {
        'ok': True,
        'mode': 'dry_run' if dry_run else 'live',
        'worker': worker,
        'capacity': policy,
        'locked': len(batch),
        'sent': 0,
        'failed': 0,
        'blocked': 0,
        'completed': 0,
        'completion_failed': 0,
        'requeued': 0,
        'dispatchIds': [r.get('dispatch_id') for r in batch],
        'generatedAt': _iso(ts),
    }
    if not dry_run:
        send = transport or _default_transport
        for row in batch:
            _process_live_row(row, send=send, completion_callback=completion_callback,
                              path=path, ts=ts, result=result)
        return result
    for row in batch:
        if _requeue_shadow(row['dispatch_id'], path=path, now=ts):
            result['requeued'] += 1
    return result


def run_per_chip_once(*, path: str | Path = DISPATCH_QUEUE, config: dict[str, Any] | None = None,
                      now: datetime | None = None, transport=None, completion_callback=None) -> dict[str, Any]:
    """Caminho de escala por chip — SÓ atua com a flag mestra ligada.

    Enquanto `per_chip_async_enabled` estiver False (padrão), cai no worker
    conservador atual em modo shadow (`run_once` dry-run), sem qualquer envio.
    Ligada, reserva um lote AGRUPADO POR CHIP (`acquire_chip_batch`), respeita
    limite por chip/hora e faz retry controlado sem duplicar mensagens. Mesmo
    ligada, começa em `dry_run` até que a config explicite `dry_run=False`.
    """
    cfg = config if isinstance(config, dict) else dispatch_scale_config()
    ts = _now(now)
    if not cfg.get('per_chip_async_enabled'):
        # Flag desligada => comportamento conservador de hoje, sem risco.
        out = run_once(path=path, dry_run=True, now=ts, transport=transport, completion_callback=completion_callback)
        out['perChip'] = {'enabled': False, 'note': 'flag desligada; worker conservador (shadow)'}
        return out

    dry_run = bool(cfg.get('dry_run', True))
    worker = _worker_id()
    batch = acquire_chip_batch(
        path=path,
        max_per_chip=int(cfg.get('per_chip_batch_size', 1)),
        max_chips=cfg.get('max_chips'),
        per_chip_hourly_limit=int(cfg.get('per_chip_hourly_limit', 100)),
        max_attempts=int(cfg.get('max_attempts', 3)),
        allowed_ports=cfg.get('allowed_ports'),
        execution_modes=None if dry_run else ['worker_owned'],
        locked_by=worker,
        now=ts,
    )
    result: dict[str, Any] = {
        'ok': True,
        'mode': 'per_chip_dry_run' if dry_run else 'per_chip_live',
        'worker': worker,
        'config': {k: cfg.get(k) for k in ('per_chip_batch_size', 'per_chip_hourly_limit', 'max_chips', 'max_attempts', 'retry_backoff_seconds', 'allowed_ports')},
        'locked': len(batch),
        'sent': 0,
        'failed': 0,
        'blocked': 0,
        'completed': 0,
        'completion_failed': 0,
        'requeued': 0,
        'retried': 0,
        'dispatchIds': [r.get('dispatch_id') for r in batch],
        'generatedAt': _iso(ts),
    }
    if dry_run:
        for row in batch:
            if _requeue_shadow(row['dispatch_id'], path=path, now=ts):
                result['requeued'] += 1
        result['byChip'] = chip_lock_metrics(path=path, now=ts)['byChip']
        return result

    send = transport or _default_transport

    def _retry(row: dict[str, Any], last_error: str) -> dict[str, Any]:
        return schedule_retry(row['dispatch_id'], path=path, now=ts,
                              backoff_seconds=int(cfg.get('retry_backoff_seconds', 300)),
                              max_attempts=int(cfg.get('max_attempts', 3)), last_error=last_error)

    for row in batch:
        _process_live_row(row, send=send, completion_callback=completion_callback,
                          path=path, ts=ts, result=result, retry=_retry)
    result['byChip'] = chip_lock_metrics(path=path, now=ts)['byChip']
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='Zydon WhatsApp dispatch worker shadow/dry-run')
    ap.add_argument('--queue', default=str(DISPATCH_QUEUE))
    ap.add_argument('--max-simultaneous', type=int, default=10)
    ap.add_argument('--live', action='store_true', help='bloqueado por segurança nesta fase')
    ap.add_argument('--per-chip', action='store_true',
                    help='usa o caminho por-chip (só atua se a flag da config estiver ligada)')
    args = ap.parse_args(argv)
    if args.per_chip:
        # A flag mestra ainda mora na config; sem ela, run_per_chip_once cai no shadow.
        out = run_per_chip_once(path=args.queue)
    else:
        out = run_once(path=args.queue, dry_run=not args.live, max_simultaneous=args.max_simultaneous)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get('ok') else 2


if __name__ == '__main__':
    raise SystemExit(main())
