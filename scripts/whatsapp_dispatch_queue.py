#!/usr/bin/env python3
"""Fila unificada de intenção de disparo WhatsApp Zydon.

Camada READ/WRITE local que concentra a INTENÇÃO de disparo de todas as
origens (diagnóstico, follow-up, agenda, proatividade, conversa automática,
Não-MQL e envio manual operacional) em uma única fila com lock atômico.

Este módulo NÃO envia WhatsApp, NÃO chama bridge/chip e NÃO altera volume.
Ele só padroniza como um disparo é enfileirado, deduplicado, priorizado e
acompanhado, para que os senders existentes possam, no futuro, consumir uma
fila única capaz de comportar centenas/milhares de disparos por dia sem
duplicidade e sem lentidão.

Compatibilidade: reaproveita o lock central de `zydon_operational_queues`
(mesmo mecanismo `fcntl` usado pelo ledger histórico) e expõe um helper para
o `whatsapp_send_orchestrator` transformar um intent preparado em linha de fila
sem mudar o envio atual.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterable
import sys

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

try:
    from .zydon_operational_queues import locked_path, load_json, save_json, update_json_locked
except Exception:  # import por spec/file path nos testes e scripts legados
    from zydon_operational_queues import locked_path, load_json, save_json, update_json_locked

try:
    from .whatsapp_message_nature import quota_class_for
except Exception:
    try:
        from whatsapp_message_nature import quota_class_for
    except Exception:  # nature opcional; fila não depende dela para funcionar
        quota_class_for = None  # type: ignore

try:
    from .whatsapp_routing import active_contact_port
except Exception:
    try:
        from whatsapp_routing import active_contact_port  # type: ignore
    except Exception:
        active_contact_port = None  # type: ignore

ROOT = Path('/root/.hermes/zydon-prospeccao')
CONTROL = ROOT / 'controle'
DISPATCH_QUEUE = CONTROL / 'whatsapp_dispatch_queue.json'

SCHEMA_VERSION = 1

# Origens de negócio suportadas pela fila unificada.
ORIGINS = (
    'diagnostico',
    'followup',
    'agenda',
    'proatividade',
    'conversa_automatica',
    'nao_mql',
    'manual_operacional',
    'reentry',
)

# Estados possíveis de um disparo na fila.
STATUSES = (
    'queued',     # aguardando janela/worker
    'locked',     # reservado por um worker (em processamento)
    'sent',       # confirmado como enviado pelo sistema
    'skipped',    # descartado por regra (ex.: já respondido, fora de janela)
    'failed',     # tentativa falhou (pode reprocessar)
    'blocked',    # bloqueado por quota/privacidade/guardrail
    'cancelled',  # cancelado antes de sair
)

# Estados que ainda ocupam a fila para efeito de dedupe (um disparo já
# cancelado/pulado/falho não deve impedir uma nova intenção legítima).
_ACTIVE_FOR_DEDUPE = {'queued', 'locked', 'sent', 'blocked'}

# Prioridade padrão por origem (número menor = sai antes).
_DEFAULT_PRIORITY = {
    'agenda': 10,
    'conversa_automatica': 20,
    'diagnostico': 30,
    'reentry': 32,
    'followup': 40,
    'proatividade': 50,
    'nao_mql': 60,
    'manual_operacional': 15,
}

# Janela padrão de dedupe (6h). Configurável por chamada.
DEFAULT_DEDUPE_WINDOW_SECONDS = 6 * 3600

_BRT = timezone(timedelta(hours=-3))
_WS_RE = re.compile(r'\s+')


def _now(now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def now_utc_iso() -> str:
    return _iso(_now())


def _parse_iso(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        s = str(raw).replace('Z', '+00:00')
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _norm_text(value: Any) -> str:
    return _WS_RE.sub(' ', str(value or '').strip())


def _jid_and_phone(to: str) -> tuple[str, str]:
    raw = str(to or '').strip()
    if raw.endswith('@s.whatsapp.net') or raw.endswith('@c.us') or raw.endswith('@g.us'):
        jid = raw.replace('@c.us', '@s.whatsapp.net')
    else:
        digits = ''.join(ch for ch in raw if ch.isdigit())
        if digits and not digits.startswith('55') and len(digits) in (10, 11):
            digits = '55' + digits
        jid = (digits or raw) + '@s.whatsapp.net'
    phone = ''.join(ch for ch in jid.split('@', 1)[0] if ch.isdigit())
    return jid, phone


def compute_message_hash(*, text: str | None = None, parts: list[dict[str, Any]] | None = None,
                         logical_message_id: str | None = None) -> str:
    """Hash estável do conteúdo da mensagem LÓGICA (não de cada parte solta).

    Junta o texto de todas as partes na ordem em que saem, para que uma
    mensagem com múltiplas partes gere um único hash de dedupe — e não um hash
    diferente por parte.
    """
    pieces: list[str] = []
    if parts:
        for p in parts:
            if not isinstance(p, dict):
                continue
            piece = p.get('text')
            if piece is None and str(p.get('kind') or '') not in ('', 'text'):
                # partes de mídia entram pela referência estável, não pelo texto
                piece = p.get('url') or p.get('media') or p.get('caption') or p.get('kind')
            pieces.append(_norm_text(piece))
    if text is not None:
        pieces.append(_norm_text(text))
    body = '\n'.join(x for x in pieces if x != '')
    if not body and logical_message_id:
        body = str(logical_message_id)
    return hashlib.sha256(body.encode('utf-8')).hexdigest()[:24]


def compute_dedupe_key(*, lead_key: str, origin: str, nature: str, message_hash: str) -> str:
    """Chave de dedupe por lead + origem + natureza + conteúdo lógico."""
    raw = '|'.join([
        _norm_text(lead_key).lower(),
        _norm_text(origin).lower(),
        _norm_text(nature).lower(),
        _norm_text(message_hash).lower(),
    ])
    return 'ddk_' + hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]


def _dispatch_id(dedupe_key: str, anchor: str) -> str:
    raw = f'{dedupe_key}|{anchor}'
    return 'dsp_' + hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]


def _quota_class_for(nature: str, thread_state: str, explicit: str | None) -> str:
    if explicit:
        return str(explicit)
    if quota_class_for is not None:
        try:
            return quota_class_for(nature, thread_state or 'cold_outreach')
        except Exception:
            pass
    return 'cold_automation'


def _normalize_queue(data: Any) -> dict:
    if isinstance(data, dict):
        arr = data.get('dispatches')
        if isinstance(arr, list):
            data.setdefault('version', SCHEMA_VERSION)
            return data
        return {'version': SCHEMA_VERSION, 'dispatches': [v for v in data.values() if isinstance(v, dict)]}
    if isinstance(data, list):
        return {'version': SCHEMA_VERSION, 'dispatches': data}
    return {'version': SCHEMA_VERSION, 'dispatches': []}


def load_dispatches(path: str | Path = DISPATCH_QUEUE) -> list[dict[str, Any]]:
    return list(_normalize_queue(load_json(path, {'dispatches': []})).get('dispatches') or [])


def _validate_origin(origin: str) -> str:
    o = str(origin or '').strip()
    if o not in ORIGINS:
        raise ValueError(f'origin desconhecida: {origin!r} (esperado uma de {ORIGINS})')
    return o


def _validate_status(status: str) -> str:
    s = str(status or '').strip()
    if s not in STATUSES:
        raise ValueError(f'status desconhecido: {status!r} (esperado um de {STATUSES})')
    return s


def build_dispatch_row(*, origin: str, to: str, nature: str, owner_uid: str | None = None,
                       lead_key: str | None = None, text: str | None = None,
                       parts: list[dict[str, Any]] | None = None, port: int | str | None = None,
                       sender_role: str | None = None, thread_state: str = 'cold_outreach',
                       quota_class: str | None = None, priority: int | None = None,
                       logical_message_id: str | None = None, scheduled_at: str | None = None,
                       message_hash: str | None = None, dedupe_window_seconds: int = DEFAULT_DEDUPE_WINDOW_SECONDS,
                       now: datetime | None = None, **extra) -> dict[str, Any]:
    """Monta uma linha de fila padronizada SEM tocar em disparo real."""
    origin = _validate_origin(origin)
    nature = str(nature or '').strip()
    jid, phone = _jid_and_phone(to)
    lead = _norm_text(lead_key) or jid
    mhash = message_hash or compute_message_hash(text=text, parts=parts, logical_message_id=logical_message_id)
    dedupe_key = compute_dedupe_key(lead_key=lead, origin=origin, nature=nature, message_hash=mhash)
    ts = _now(now)
    window = int(dedupe_window_seconds or DEFAULT_DEDUPE_WINDOW_SECONDS)
    # Âncora determinística: mesmo lead/origem/natureza/conteúdo dentro do mesmo
    # bucket de janela produz o mesmo dispatch_id (idempotência natural).
    anchor = str(int(ts.timestamp() // max(1, window)))
    did = _dispatch_id(dedupe_key, anchor)
    row = {
        'dispatch_id': did,
        'origin': origin,
        'nature': nature,
        'quota_class': _quota_class_for(nature, thread_state, quota_class),
        'priority': int(priority) if priority is not None else _DEFAULT_PRIORITY.get(origin, 100),
        'owner_uid': (str(owner_uid).strip() or None) if owner_uid is not None else None,
        'lead_key': lead,
        'jid': jid,
        'phone': phone,
        'port': int(port) if str(port or '').isdigit() else port,
        'sender_role': str(sender_role).strip() if sender_role else None,
        'message_hash': mhash,
        'logical_message_id': logical_message_id,
        'dedupe_key': dedupe_key,
        'dedupe_window_seconds': window,
        'thread_state': str(thread_state or 'cold_outreach'),
        'scheduled_at': scheduled_at,
        'status': 'queued',
        'execution_mode': str(extra.pop('execution_mode', 'shadow') or 'shadow'),
        'locked_at': None,
        'locked_by': None,
        'attempts': 0,
        'last_error': None,
        'created_at': _iso(ts),
        'updated_at': _iso(ts),
    }
    if text is not None:
        row['text'] = text
    if parts:
        row['parts'] = parts
    row.update(extra)
    return row


def _is_dupe(existing: dict[str, Any], candidate: dict[str, Any], *, now: datetime) -> bool:
    if str(existing.get('dedupe_key') or '') != str(candidate.get('dedupe_key') or ''):
        return False
    if str(existing.get('status') or '') not in _ACTIVE_FOR_DEDUPE:
        return False
    window = int(candidate.get('dedupe_window_seconds') or DEFAULT_DEDUPE_WINDOW_SECONDS)
    created = _parse_iso(existing.get('created_at')) or _parse_iso(existing.get('updated_at'))
    if not created:
        return True
    return (now - created) <= timedelta(seconds=window)


def enqueue_dispatch(intent: dict[str, Any] | None = None, *, path: str | Path = DISPATCH_QUEUE,
                     now: datetime | None = None, **kwargs) -> dict[str, Any]:
    """Enfileira uma intenção de disparo de forma idempotente.

    Aceita tanto um dict pronto (`intent`) quanto os campos soltos por kwargs.
    Se um disparo equivalente (mesmo lead/origem/natureza/conteúdo) já existir
    dentro da janela de dedupe, retorna o existente sem duplicar.

    Retorna: {'ok', 'deduped', 'dispatch_id', 'row'}.
    """
    payload = dict(intent or {})
    payload.update(kwargs)
    if 'to' not in payload:
        payload['to'] = payload.get('jid') or payload.get('phone') or payload.get('conversation_id') or ''
    ts = _now(now)
    candidate = build_dispatch_row(now=ts, **{k: v for k, v in payload.items() if k not in ('status', 'created_at', 'updated_at')})

    result: dict[str, Any] = {}

    def upd(data):
        data = _normalize_queue(data)
        rows = data.setdefault('dispatches', [])
        for existing in rows:
            if not isinstance(existing, dict):
                continue
            if str(existing.get('dispatch_id') or '') == candidate['dispatch_id'] or _is_dupe(existing, candidate, now=ts):
                result.update({'ok': True, 'deduped': True, 'dispatch_id': existing.get('dispatch_id'), 'row': dict(existing)})
                return data
        if active_contact_port is not None and candidate.get('port'):
            existing_port = active_contact_port(candidate.get('jid') or candidate.get('phone'), dispatches=rows)
            if existing_port is not None:
                try:
                    different_port = int(existing_port) != int(candidate.get('port'))
                except Exception:
                    different_port = str(existing_port) != str(candidate.get('port'))
                if different_port:
                    result.update({
                        'ok': False,
                        'blocked': True,
                        'deduped': False,
                        'reason': 'active_contact_other_port',
                        'existing_port': existing_port,
                        'candidate_port': candidate.get('port'),
                        'dispatch_id': None,
                        'row': dict(candidate),
                    })
                    return data
        rows.append(candidate)
        result.update({'ok': True, 'deduped': False, 'dispatch_id': candidate['dispatch_id'], 'row': dict(candidate)})
        return data

    update_json_locked(path, {'version': SCHEMA_VERSION, 'dispatches': []}, upd)
    return result


def acquire_next_dispatch(*, owner_uid: str | None = None, port: int | str | None = None,
                          origins: Iterable[str] | None = None, locked_by: str | None = None,
                          path: str | Path = DISPATCH_QUEUE, now: datetime | None = None) -> dict[str, Any] | None:
    """Reserva atomicamente o próximo disparo elegível e o marca como `locked`.

    Filtra por owner/porta/origem, respeita `scheduled_at` (só pega o que já
    está no horário) e ordena por prioridade e antiguidade. Retorna a linha
    reservada ou None se não houver nada elegível.
    """
    ts = _now(now)
    origin_set = {str(o) for o in origins} if origins else None
    picked: dict[str, Any] = {}

    def _eligible(row: dict[str, Any]) -> bool:
        if not isinstance(row, dict) or row.get('status') != 'queued':
            return False
        if owner_uid is not None and str(row.get('owner_uid') or '') != str(owner_uid):
            return False
        if port is not None:
            try:
                if int(row.get('port') or 0) != int(port):
                    return False
            except Exception:
                return False
        if origin_set is not None and str(row.get('origin') or '') not in origin_set:
            return False
        sched = _parse_iso(row.get('scheduled_at'))
        if sched and sched > ts:
            return False
        return True

    def upd(data):
        data = _normalize_queue(data)
        rows = data.get('dispatches') or []
        candidates = [r for r in rows if _eligible(r)]
        if not candidates:
            return data
        candidates.sort(key=lambda r: (
            int(r.get('priority') if r.get('priority') is not None else 100),
            str(r.get('scheduled_at') or r.get('created_at') or ''),
        ))
        row = candidates[0]
        row['status'] = 'locked'
        row['locked_at'] = _iso(ts)
        row['locked_by'] = str(locked_by) if locked_by else None
        row['attempts'] = int(row.get('attempts') or 0) + 1
        row['updated_at'] = _iso(ts)
        picked.update(dict(row))
        return data

    update_json_locked(path, {'version': SCHEMA_VERSION, 'dispatches': []}, upd)
    return dict(picked) if picked else None


def mark_dispatch_status(dispatch_id: str, status: str, *, last_error: str | None = None,
                         path: str | Path = DISPATCH_QUEUE, now: datetime | None = None,
                         **fields) -> dict[str, Any] | None:
    """Atualiza o estado de um disparo sob lock e devolve a linha resultante."""
    status = _validate_status(status)
    ts = _now(now)
    updated: dict[str, Any] = {}

    def upd(data):
        data = _normalize_queue(data)
        for row in data.get('dispatches') or []:
            if isinstance(row, dict) and str(row.get('dispatch_id') or '') == str(dispatch_id):
                row['status'] = status
                row['updated_at'] = _iso(ts)
                if last_error is not None:
                    row['last_error'] = last_error
                if status == 'sent':
                    row.setdefault('sent_at', _iso(ts))
                for k, v in fields.items():
                    row[k] = v
                updated.update(dict(row))
                break
        return data

    update_json_locked(path, {'version': SCHEMA_VERSION, 'dispatches': []}, upd)
    return dict(updated) if updated else None


def _brt_date(raw: Any) -> str:
    dt = _parse_iso(raw)
    if not dt:
        return ''
    return dt.astimezone(_BRT).strftime('%Y-%m-%d')


def queue_metrics(rows: Iterable[dict[str, Any]] | None = None, *, path: str | Path = DISPATCH_QUEUE,
                  now: datetime | None = None) -> dict[str, Any]:
    """Métricas executivas por estado, origem, owner e porta.

    Não envia nada; só lê a fila e agrega. `sentToday` usa o fuso BRT e
    `throughputLastHour` é uma dica de vazão (sent na última hora).
    """
    if rows is None:
        rows = load_dispatches(path)
    rows = [r for r in rows if isinstance(r, dict)]
    ts = _now(now)
    today = ts.astimezone(_BRT).strftime('%Y-%m-%d')
    by_status: dict[str, int] = {}
    by_origin: dict[str, int] = {}
    by_owner: dict[str, int] = {}
    by_port: dict[str, int] = {}
    sent_today = 0
    throughput_last_hour = 0
    for r in rows:
        st = str(r.get('status') or 'queued')
        by_status[st] = by_status.get(st, 0) + 1
        by_origin[str(r.get('origin') or '—')] = by_origin.get(str(r.get('origin') or '—'), 0) + 1
        by_owner[str(r.get('owner_uid') or '—')] = by_owner.get(str(r.get('owner_uid') or '—'), 0) + 1
        by_port[str(r.get('port') or '—')] = by_port.get(str(r.get('port') or '—'), 0) + 1
        if st == 'sent':
            when = r.get('sent_at') or r.get('updated_at')
            if _brt_date(when) == today:
                sent_today += 1
            sdt = _parse_iso(when)
            if sdt and (ts - sdt) <= timedelta(hours=1):
                throughput_last_hour += 1
    return {
        'total': len(rows),
        'byStatus': by_status,
        'byOrigin': by_origin,
        'byOwner': by_owner,
        'byPort': by_port,
        'queued': by_status.get('queued', 0),
        'locked': by_status.get('locked', 0),
        'sent': by_status.get('sent', 0),
        'skipped': by_status.get('skipped', 0),
        'failed': by_status.get('failed', 0),
        'blocked': by_status.get('blocked', 0),
        'cancelled': by_status.get('cancelled', 0),
        'sentToday': sent_today,
        'throughputLastHour': throughput_last_hour,
        'origins': sorted(by_origin.keys()),
    }


def dispatch_capacity_policy(*, daily_unique_target: int = 1000, max_simultaneous: int = 10,
                             target_sdr_chips: int = 6) -> dict[str, Any]:
    """Política executiva de capacidade do motor WhatsApp.

    Não envia nada. Define os limites que o worker deve respeitar para suportar
    1000+ novas conversas únicas/dia e até 10 conversas simultâneas sem
    sobrecarregar chip, destino ou bridge.
    """
    target = max(1, int(daily_unique_target or 1000))
    chips = max(1, int(target_sdr_chips or 6))
    simultaneous = max(1, int(max_simultaneous or 10))
    per_chip_day = int((target + chips - 1) // chips)
    # Janela útil conservadora de 10h comerciais para dimensionamento.
    per_hour = int((target + 9) // 10)
    return {
        'dailyUniqueConversationTarget': target,
        'maxSimultaneousConversations': simultaneous,
        'requiredSdrChips': chips,
        'perChipDailyTarget': per_chip_day,
        'globalHourlyTarget': per_hour,
        'perChipHourlyTarget': max(1, int((per_hour + chips - 1) // chips)),
        'locks': ['lock_by_port', 'lock_by_destination', 'lock_by_dedupe_key'],
        'mode': 'shadow_until_all_senders_dual_write',
        'notes': [
            'cron produz intenção; worker executa',
            f'máximo {max_simultaneous} conversas simultâneas no lote quando o worker estiver em modo assíncrono/por item',
            'um envio ativo por chip e por destino em cada lote',
        ],
    }


def acquire_dispatch_batch(*, max_items: int = 10, owner_uid: str | None = None,
                           origins: Iterable[str] | None = None, execution_modes: Iterable[str] | None = None,
                           locked_by: str | None = None,
                           path: str | Path = DISPATCH_QUEUE, now: datetime | None = None) -> list[dict[str, Any]]:
    """Reserva um lote seguro para worker, sem duplicar chip/destino/dedupe.

    A unidade de concorrência é conversa única: no mesmo lote não entram dois
    disparos para o mesmo destino, nem dois usando o mesmo chip/porta. Isso dá a
    base para falar com até 10 pessoas simultaneamente sem empilhar envios no
    mesmo WhatsApp.
    """
    ts = _now(now)
    limit = max(1, min(10, int(max_items or 10)))
    origin_set = {str(o) for o in origins} if origins else None
    mode_set = {str(m) for m in execution_modes} if execution_modes else None
    picked: list[dict[str, Any]] = []

    def _eligible(row: dict[str, Any]) -> bool:
        if not isinstance(row, dict) or row.get('status') != 'queued':
            return False
        if owner_uid is not None and str(row.get('owner_uid') or '') != str(owner_uid):
            return False
        if origin_set is not None and str(row.get('origin') or '') not in origin_set:
            return False
        if mode_set is not None and str(row.get('execution_mode') or 'shadow') not in mode_set:
            return False
        sched = _parse_iso(row.get('scheduled_at'))
        if sched and sched > ts:
            return False
        return True

    def upd(data):
        data = _normalize_queue(data)
        rows = data.get('dispatches') or []
        candidates = [r for r in rows if _eligible(r)]
        candidates.sort(key=lambda r: (
            int(r.get('priority') if r.get('priority') is not None else 100),
            str(r.get('scheduled_at') or r.get('created_at') or ''),
        ))
        used_ports: set[str] = set()
        used_destinations: set[str] = set()
        used_dedupes: set[str] = set()
        for row in candidates:
            if len(picked) >= limit:
                break
            port_key = str(row.get('port') or '')
            dest_key = str(row.get('jid') or row.get('phone') or row.get('lead_key') or '')
            dedupe_key = str(row.get('dedupe_key') or '')
            if port_key and port_key in used_ports:
                continue
            if dest_key and dest_key in used_destinations:
                continue
            if dedupe_key and dedupe_key in used_dedupes:
                continue
            row['status'] = 'locked'
            row['locked_at'] = _iso(ts)
            row['locked_by'] = str(locked_by) if locked_by else None
            row['attempts'] = int(row.get('attempts') or 0) + 1
            row['updated_at'] = _iso(ts)
            if port_key:
                used_ports.add(port_key)
            if dest_key:
                used_destinations.add(dest_key)
            if dedupe_key:
                used_dedupes.add(dedupe_key)
            picked.append(dict(row))
        return data

    update_json_locked(path, {'version': SCHEMA_VERSION, 'dispatches': []}, upd)
    return list(picked)


def dispatch_queue_snapshot(*, limit: int = 50, path: str | Path = DISPATCH_QUEUE,
                            now: datetime | None = None) -> dict[str, Any]:
    """Snapshot rápido para painel: resumo + linhas mais recentes.

    Read-only. Ordena por `updated_at` desc e devolve no máximo `limit` linhas
    já com os campos executivos que a UI precisa.
    """
    rows = load_dispatches(path)
    summary = queue_metrics(rows, now=now)
    ordered = sorted(rows, key=lambda r: str(r.get('updated_at') or r.get('created_at') or ''), reverse=True)
    recent = []
    for r in ordered[: max(0, int(limit))]:
        recent.append({
            'dispatchId': r.get('dispatch_id'),
            'origin': r.get('origin'),
            'nature': r.get('nature'),
            'quotaClass': r.get('quota_class'),
            'priority': r.get('priority'),
            'owner': r.get('owner_uid'),
            'leadKey': r.get('lead_key'),
            'jid': r.get('jid'),
            'phone': r.get('phone'),
            'port': r.get('port'),
            'senderRole': r.get('sender_role'),
            'status': r.get('status'),
            'scheduledAt': r.get('scheduled_at'),
            'lockedAt': r.get('locked_at'),
            'attempts': r.get('attempts'),
            'lastError': r.get('last_error'),
            'dedupeKey': r.get('dedupe_key'),
            'createdAt': r.get('created_at'),
            'updatedAt': r.get('updated_at'),
        })
    return {'summary': summary, 'rows': recent, 'generatedAt': now_utc_iso()}


def dispatch_row_from_intent(intent: dict[str, Any], *, origin: str | None = None,
                             scheduled_at: str | None = None) -> dict[str, Any]:
    """Helper de compatibilidade para o orquestrador.

    Converte um `intent` já preparado por `whatsapp_send_orchestrator.prepare_intent`
    em uma linha de fila unificada, SEM enviar. Permite que o orquestrador, no
    futuro, enfileire em vez de disparar direto, sem mudar o transporte agora.
    """
    to = intent.get('to') or intent.get('conversation_id') or intent.get('jid') or ''
    text = intent.get('text')
    parts = intent.get('parts')
    return build_dispatch_row(
        origin=str(origin or intent.get('origin') or 'manual_operacional'),
        to=to,
        nature=str(intent.get('nature') or ''),
        owner_uid=intent.get('owner_sdr') or intent.get('owner_uid'),
        lead_key=intent.get('lead_key') or intent.get('conversation_id') or to,
        text=text,
        parts=parts if isinstance(parts, list) else None,
        port=intent.get('selected_port') or intent.get('bridge_port') or intent.get('port'),
        sender_role=intent.get('sender_role'),
        thread_state=str(intent.get('thread_state') or 'cold_outreach'),
        quota_class=intent.get('quota_class'),
        logical_message_id=intent.get('logical_message_id'),
        scheduled_at=scheduled_at,
    )


def enqueue_intent(intent: dict[str, Any], *, origin: str | None = None, scheduled_at: str | None = None,
                   path: str | Path = DISPATCH_QUEUE, now: datetime | None = None) -> dict[str, Any]:
    """Enfileira um intent do orquestrador na fila unificada (sem enviar)."""
    row = dispatch_row_from_intent(intent, origin=origin, scheduled_at=scheduled_at)
    return enqueue_dispatch(row, path=path, now=now)


# ---------------------------------------------------------------------------
# Escala por chip (INFRAESTRUTURA — flag mestra DESLIGADA por padrão).
#
# Nada aqui envia WhatsApp nem muda o comportamento conservador atual. São
# funções puras/atômicas que o worker pode usar SOMENTE quando a flag
# `per_chip_async_enabled` estiver ligada em `controle/dispatch_scale_config.json`.
# Enquanto o arquivo não existir (ou a flag estiver False), tudo fica no modo
# conservador de hoje: 1 item por chip por execução, sem retry automático.
# ---------------------------------------------------------------------------

SCALE_CONFIG_PATH = CONTROL / 'dispatch_scale_config.json'

# Defaults deliberadamente conservadores: mesmo se alguém ligar a flag mestra
# sem ajustar mais nada, começa em dry_run e 1 envio por chip por execução.
_DEFAULT_SCALE_CONFIG: dict[str, Any] = {
    'per_chip_async_enabled': False,  # flag mestra — DESLIGADA por padrão
    'dry_run': True,                  # trava extra: mesmo ligada, começa em shadow
    'per_chip_batch_size': 1,         # itens por chip por execução (1 = conservador)
    'per_chip_hourly_limit': 100,     # teto de envios por chip por hora
    'max_chips': None,                # None = todos os chips elegíveis
    'max_attempts': 3,                # tentativas antes de falha definitiva
    'retry_backoff_seconds': 300,     # espera entre tentativas (segundos)
}


def dispatch_scale_config(overrides: dict[str, Any] | None = None, *,
                          path: str | Path = SCALE_CONFIG_PATH) -> dict[str, Any]:
    """Resolve a config de escala por chip com defaults conservadores.

    Ordem de precedência: defaults < arquivo `dispatch_scale_config.json` <
    `overrides` (usado em teste/console). A flag mestra continua False a menos
    que seja explicitamente ligada. Nunca levanta exceção: config inválida cai
    nos defaults seguros.
    """
    cfg = dict(_DEFAULT_SCALE_CONFIG)
    file_cfg = load_json(path, {})
    if isinstance(file_cfg, dict):
        for k in cfg:
            if k in file_cfg:
                cfg[k] = file_cfg[k]
    if overrides:
        for k, v in overrides.items():
            if k in cfg:
                cfg[k] = v
    cfg['per_chip_async_enabled'] = bool(cfg.get('per_chip_async_enabled'))
    cfg['dry_run'] = bool(cfg.get('dry_run', True))
    cfg['per_chip_batch_size'] = max(1, int(cfg.get('per_chip_batch_size') or 1))
    cfg['per_chip_hourly_limit'] = max(1, int(cfg.get('per_chip_hourly_limit') or 1))
    cfg['max_attempts'] = max(1, int(cfg.get('max_attempts') or 1))
    cfg['retry_backoff_seconds'] = max(0, int(cfg.get('retry_backoff_seconds') or 0))
    if cfg['max_chips'] is not None:
        try:
            cfg['max_chips'] = max(1, int(cfg['max_chips']))
        except Exception:
            cfg['max_chips'] = None
    return cfg


def per_chip_hourly_sent_count(rows: Iterable[dict[str, Any]], *, now: datetime | None = None,
                               window_seconds: int = 3600) -> dict[str, int]:
    """Quantos disparos `sent` cada chip teve na última janela (default 1h).

    Base para respeitar limite por chip/hora sem estourar o WhatsApp. Read-only.
    """
    ts = _now(now)
    counts: dict[str, int] = {}
    for r in rows or []:
        if not isinstance(r, dict) or r.get('status') != 'sent':
            continue
        when = _parse_iso(r.get('sent_at') or r.get('updated_at'))
        if not when or (ts - when) > timedelta(seconds=max(1, int(window_seconds))):
            continue
        key = str(r.get('port') or '')
        if key:
            counts[key] = counts.get(key, 0) + 1
    return counts


def chip_lock_metrics(rows: Iterable[dict[str, Any]] | None = None, *, path: str | Path = DISPATCH_QUEUE,
                      now: datetime | None = None, hourly_window_seconds: int = 3600) -> dict[str, Any]:
    """Monitor por chip: locked/sent/cancelled/... e envios na última hora.

    Serve para acompanhar `locked` empoçado por chip (worker travado) e o
    throughput por chip sem enviar nada. Read-only.
    """
    if rows is None:
        rows = load_dispatches(path)
    rows = [r for r in rows if isinstance(r, dict)]
    ts = _now(now)
    by_chip: dict[str, dict[str, Any]] = {}
    for r in rows:
        port_key = str(r.get('port') or '—')
        d = by_chip.setdefault(port_key, {
            'port': port_key, 'queued': 0, 'locked': 0, 'sent': 0,
            'skipped': 0, 'failed': 0, 'blocked': 0, 'cancelled': 0, 'sentLastHour': 0,
        })
        st = str(r.get('status') or 'queued')
        if st in d:
            d[st] += 1
        if st == 'sent':
            when = _parse_iso(r.get('sent_at') or r.get('updated_at'))
            if when and (ts - when) <= timedelta(seconds=max(1, int(hourly_window_seconds))):
                d['sentLastHour'] += 1
    return {
        'generatedAt': _iso(ts),
        'byChip': by_chip,
        'lockedTotal': sum(d['locked'] for d in by_chip.values()),
        'sentTotal': sum(d['sent'] for d in by_chip.values()),
        'cancelledTotal': sum(d['cancelled'] for d in by_chip.values()),
    }


def acquire_chip_batch(*, port: int | str | None = None, max_per_chip: int = 1,
                       max_chips: int | None = None, per_chip_hourly_limit: int | None = None,
                       owner_uid: str | None = None, origins: Iterable[str] | None = None,
                       execution_modes: Iterable[str] | None = None, locked_by: str | None = None,
                       max_attempts: int | None = None, hourly_window_seconds: int = 3600,
                       allowed_ports: Iterable[int | str] | None = None,
                       path: str | Path = DISPATCH_QUEUE, now: datetime | None = None) -> list[dict[str, Any]]:
    """Reserva um lote AGRUPADO POR CHIP, sem que um chip bloqueie os outros.

    Diferença para `acquire_dispatch_batch` (que pega no máximo 1 item por
    porta): aqui um mesmo chip pode receber vários itens no mesmo lote
    (`max_per_chip`), sem duplicar destino/dedupe, respeitando o limite por
    chip/hora (`per_chip_hourly_limit` menos o que já saiu na última hora e o
    que está em voo). Se um chip está saturado, ele é pulado e os demais chips
    seguem — a saturação de um não trava o outro.

    `port` definido reserva só desse chip. `port=None` percorre todos os chips
    elegíveis. Só reserva itens `queued` cujo `attempts < max_attempts` e cujo
    `scheduled_at` já venceu. Atômico via lock da fila.
    """
    ts = _now(now)
    origin_set = {str(o) for o in origins} if origins else None
    mode_set = {str(m) for m in execution_modes} if execution_modes else None
    allowed_port_set = {str(p) for p in allowed_ports} if allowed_ports else None
    per_chip_cap = max(1, int(max_per_chip or 1))
    picked: list[dict[str, Any]] = []

    def _eligible(row: dict[str, Any]) -> bool:
        if not isinstance(row, dict) or row.get('status') != 'queued':
            return False
        if owner_uid is not None and str(row.get('owner_uid') or '') != str(owner_uid):
            return False
        if origin_set is not None and str(row.get('origin') or '') not in origin_set:
            return False
        if mode_set is not None and str(row.get('execution_mode') or 'shadow') not in mode_set:
            return False
        if port is not None and str(row.get('port') or '') != str(port):
            return False
        if allowed_port_set is not None and str(row.get('port') or '') not in allowed_port_set:
            return False
        if max_attempts is not None and int(row.get('attempts') or 0) >= int(max_attempts):
            return False
        sched = _parse_iso(row.get('scheduled_at'))
        if sched and sched > ts:
            return False
        return True

    def upd(data):
        data = _normalize_queue(data)
        rows = data.get('dispatches') or []
        # Capacidade já usada por chip: enviados na última hora + em voo (locked).
        sent_last_hour = per_chip_hourly_sent_count(rows, now=ts, window_seconds=hourly_window_seconds)
        in_flight: dict[str, int] = {}
        for r in rows:
            if isinstance(r, dict) and r.get('status') == 'locked':
                k = str(r.get('port') or '')
                if k:
                    in_flight[k] = in_flight.get(k, 0) + 1
        candidates = [r for r in rows if _eligible(r)]
        candidates.sort(key=lambda r: (
            int(r.get('priority') if r.get('priority') is not None else 100),
            str(r.get('scheduled_at') or r.get('created_at') or ''),
        ))
        taken_per_chip: dict[str, int] = {}
        chips_served: set[str] = set()
        used_destinations: set[str] = set()
        used_dedupes: set[str] = set()
        for row in candidates:
            port_key = str(row.get('port') or '')
            if not port_key:
                continue  # chip desconhecido não entra no lote por-chip
            if max_chips is not None and port_key not in chips_served and len(chips_served) >= int(max_chips):
                continue
            already = taken_per_chip.get(port_key, 0)
            if already >= per_chip_cap:
                continue
            if per_chip_hourly_limit is not None:
                headroom = int(per_chip_hourly_limit) - sent_last_hour.get(port_key, 0) - in_flight.get(port_key, 0) - already
                if headroom <= 0:
                    continue  # chip saturado: pula sem bloquear os demais
            dest_key = str(row.get('jid') or row.get('phone') or row.get('lead_key') or '')
            dedupe_key = str(row.get('dedupe_key') or '')
            if dest_key and dest_key in used_destinations:
                continue
            if dedupe_key and dedupe_key in used_dedupes:
                continue
            row['status'] = 'locked'
            row['locked_at'] = _iso(ts)
            row['locked_by'] = str(locked_by) if locked_by else None
            row['attempts'] = int(row.get('attempts') or 0) + 1
            row['updated_at'] = _iso(ts)
            taken_per_chip[port_key] = already + 1
            chips_served.add(port_key)
            if dest_key:
                used_destinations.add(dest_key)
            if dedupe_key:
                used_dedupes.add(dedupe_key)
            picked.append(dict(row))
        return data

    update_json_locked(path, {'version': SCHEMA_VERSION, 'dispatches': []}, upd)
    return list(picked)


def schedule_retry(dispatch_id: str, *, path: str | Path = DISPATCH_QUEUE, now: datetime | None = None,
                   backoff_seconds: int = 300, max_attempts: int = 3,
                   last_error: str | None = None) -> dict[str, Any]:
    """Retry controlado sem duplicar mensagem.

    Regras de segurança:
    - Nunca mexe em um disparo já `sent` (não reenvia nada).
    - Se ainda há tentativa (`attempts < max_attempts`), volta para `queued`
      com `scheduled_at` no futuro (backoff) e limpa o lock; assim o mesmo item
      não sai duas vezes na mesma execução.
    - Se esgotou as tentativas, marca `failed` definitivo (`retry_exhausted`).

    O `attempts` é incrementado no acquire; aqui só decidimos requeue x falha.
    Retorna {'retried': bool, 'status': str, ...}.
    """
    ts = _now(now)
    out: dict[str, Any] = {'retried': False, 'status': None, 'reason': 'not_found'}

    def upd(data):
        data = _normalize_queue(data)
        for row in data.get('dispatches') or []:
            if not isinstance(row, dict) or str(row.get('dispatch_id') or '') != str(dispatch_id):
                continue
            if row.get('status') == 'sent':
                out.update({'retried': False, 'status': 'sent', 'reason': 'already_sent'})
                break
            attempts = int(row.get('attempts') or 0)
            if last_error is not None:
                row['last_error'] = last_error
            if attempts >= int(max_attempts):
                row['status'] = 'failed'
                row['retry_exhausted'] = True
                row['updated_at'] = _iso(ts)
                out.update({'retried': False, 'status': 'failed', 'reason': 'exhausted', 'attempts': attempts})
            else:
                nxt = _iso(ts + timedelta(seconds=max(0, int(backoff_seconds))))
                row['status'] = 'queued'
                row['locked_at'] = None
                row['locked_by'] = None
                row['scheduled_at'] = nxt
                row['updated_at'] = _iso(ts)
                out.update({'retried': True, 'status': 'queued', 'attempts': attempts, 'next_at': nxt})
            break
        return data

    update_json_locked(path, {'version': SCHEMA_VERSION, 'dispatches': []}, upd)
    return out
