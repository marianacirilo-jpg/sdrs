#!/usr/bin/env python3
"""Fundação de aprendizado contínuo por chip (porta) e operador (owner) — Zydon.

Camada READ-ONLY que deriva métricas agregadas de saúde/reputação de cada chip
WhatsApp e de cada operador a partir de duas fontes já existentes:

- o ledger histórico `controle/wpp_envios.json` (envios reais registrados);
- a fila unificada `controle/whatsapp_dispatch_queue.json` (estados de disparo:
  queued/locked/sent/failed/blocked).

Este módulo **não envia WhatsApp**, **não chama bridge/chip**, **não altera
volume** e **não liga nenhuma decisão live de roteamento**. Ele apenas lê,
agrega e calcula um score simples de saúde, para que, no futuro, o roteador
possa *consultar* (via `prefer_healthy_chip` / `rank_healthy_chips`) e preferir
chips saudáveis — mas essa ligação ainda não está feita de propósito.

A derivação é determinística e idempotente: dadas as mesmas linhas de entrada e o
mesmo `now`, o snapshot gerado é byte-a-byte igual. A persistência em
`controle/chip_operator_learning.json` é uma reconstrução completa (não um
acúmulo incremental), então rodar duas vezes seguidas não duplica nada.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterable, Iterator

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

try:
    from .zydon_operational_queues import load_json, update_json_locked
except Exception:  # import por spec/file path nos testes e scripts legados
    from zydon_operational_queues import load_json, update_json_locked

try:
    from .whatsapp_dispatch_queue import load_dispatches, DISPATCH_QUEUE
except Exception:
    from whatsapp_dispatch_queue import load_dispatches, DISPATCH_QUEUE  # type: ignore

ROOT = Path('/root/.hermes/zydon-prospeccao')
CONTROL = ROOT / 'controle'
WPP_ENVIOS = CONTROL / 'wpp_envios.json'
LEARNING_SNAPSHOT = CONTROL / 'chip_operator_learning.json'

SCHEMA_VERSION = 1

# Janela padrão para considerar um lock "preso" (stale). Um disparo reservado há
# mais tempo que isso sem terminar sinaliza chip/worker travado.
DEFAULT_STALE_SECONDS = 15 * 60

# Score >= este piso => chip/operador considerado saudável.
DEFAULT_HEALTH_FLOOR = 60.0

# Score neutro quando ainda não há histórico suficiente (chip novo/desconhecido).
NEUTRAL_SCORE = 50.0

_BRT = timezone(timedelta(hours=-3))

# Contadores canônicos de cada bucket de métricas.
_COUNT_KEYS = ('sent', 'failed', 'blocked', 'replies', 'locked', 'stale')

# Statuses de ledger que NÃO representam nem envio bom nem falha de chip
# (duplicata apagada, mensagem substituída por regra, em andamento).
_LEDGER_NEUTRAL_MARKERS = ('deleted', 'duplicate', 'superseded', 'em_andamento')

# Marcadores de falha em status textual do ledger.
_LEDGER_FAIL_MARKERS = ('failed', 'erro', 'error', 'falha', 'invalid', 'invalido',
                        'nao_enviado', 'not_sent', 'bloqueado', 'blocked')

# Campos que, se truthy, indicam evidência de resposta do lead no ledger.
_REPLY_FLAG_FIELDS = ('lead_reply', 'lead_replied', 'replied', 'reply', 'answered',
                      'lead_response', 'resposta_lead')
_REPLY_TS_FIELDS = ('reply_at', 'lead_reply_at', 'replied_at', 'answered_at', 'last_reply_at')


# --------------------------------------------------------------------------- #
# Helpers de tempo / parsing (tolerantes ao ledger real)
# --------------------------------------------------------------------------- #
def _now(now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def now_utc_iso() -> str:
    return _iso(_now())


def _parse_ts(raw: Any) -> datetime | None:
    """Parseia timestamps do ledger/fila. Naive => assume BRT (fuso do ledger)."""
    if not raw:
        return None
    try:
        s = str(raw).replace('Z', '+00:00')
        dt = datetime.fromisoformat(s)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_BRT)
    return dt.astimezone(timezone.utc)


def _first(row: dict[str, Any], keys: Iterable[str]) -> Any:
    for k in keys:
        v = row.get(k)
        if v:
            return v
    return None


def _port_key(port: Any) -> str:
    s = str(port if port is not None else '').strip()
    if s.isdigit():
        return str(int(s))
    return s or 'unknown'


def _port_display(pk: str) -> Any:
    return int(pk) if pk.isdigit() else pk


def _owner_key(owner: Any) -> str:
    s = str(owner if owner is not None else '').strip().lower()
    return s or 'unknown'


def _response_ok(resp: Any) -> bool:
    """Mesma heurística de sucesso usada pelo worker (messageId/status 1|2)."""
    if not isinstance(resp, dict):
        return False
    if resp.get('messageId') or resp.get('id'):
        return True
    if resp.get('success') is True:
        return True
    if str(resp.get('status')) in ('1', '2'):
        return True
    if isinstance(resp.get('messageIds'), list) and resp.get('messageIds'):
        return True
    return False


# --------------------------------------------------------------------------- #
# Classificação de eventos (ledger + fila)
# --------------------------------------------------------------------------- #
def classify_ledger_outcome(row: dict[str, Any]) -> str | None:
    """Classifica uma linha do ledger em 'sent' | 'failed' | None (neutro)."""
    err = _first(row, ('send_error', 'error', 'last_error', 'bridge_error', 'text_error'))
    status = str(row.get('status') or '').strip().lower()
    if err:
        return 'failed'
    if status:
        if any(m in status for m in _LEDGER_NEUTRAL_MARKERS):
            return None
        if any(m in status for m in _LEDGER_FAIL_MARKERS):
            return 'failed'
        if status.startswith('enviado') or status.endswith('_done') or status in ('done', 'sent'):
            return 'sent'
    resp = (row.get('send_response') or row.get('response')
            or row.get('question_response') or row.get('bridge_response'))
    if _response_ok(resp):
        return 'sent'
    return None


def has_reply_evidence(row: dict[str, Any]) -> bool:
    """True quando há sinal de que o lead respondeu naquele envio."""
    if _first(row, _REPLY_FLAG_FIELDS) or _first(row, _REPLY_TS_FIELDS):
        return True
    status = str(row.get('status') or '').lower()
    nature = str(row.get('nature') or '').lower()
    if 'resposta' in status or 'reply' in status:
        return True
    if 'reply' in nature:
        return True
    return False


def _ledger_dims(row: dict[str, Any]) -> tuple[str, str, Any, str, str]:
    port = _port_key(row.get('bridge_port') or row.get('selected_port') or row.get('port'))
    owner_display = (row.get('owner_sdr') or row.get('owner_id') or row.get('sdr')
                     or row.get('owner_uid') or row.get('sender_name'))
    origin = str(row.get('origin') or 'unknown')
    nature = str(row.get('nature') or 'unknown')
    return port, _owner_key(owner_display), owner_display, origin, nature


def _queue_dims(row: dict[str, Any]) -> tuple[str, str, Any, str, str]:
    port = _port_key(row.get('port'))
    owner_display = row.get('owner_uid')
    origin = str(row.get('origin') or 'unknown')
    nature = str(row.get('nature') or 'unknown')
    return port, _owner_key(owner_display), owner_display, origin, nature


def _event(outcome: str, dims, ts: datetime | None, *, error: str | None, dedupe: str | None) -> dict[str, Any]:
    port, owner_key, owner_display, origin, nature = dims
    return {
        'outcome': outcome,
        'port': port,
        'owner_key': owner_key,
        'owner_display': (str(owner_display).strip() if owner_display else None),
        'origin': origin,
        'nature': nature,
        'ts': ts,
        'error': error,
        'dedupe': dedupe,
    }


def _iter_ledger_events(rows: Iterable[dict[str, Any]], *, since: datetime | None) -> Iterator[dict[str, Any]]:
    for row in rows:
        if not isinstance(row, dict):
            continue
        ts = _parse_ts(row.get('date_tz') or row.get('date'))
        if since and ts and ts < since:
            continue
        dims = _ledger_dims(row)
        outcome = classify_ledger_outcome(row)
        lmid = row.get('logical_message_id')
        if outcome == 'sent':
            key = f'sent:{lmid}' if lmid else None
            yield _event('sent', dims, ts, error=None, dedupe=key)
            if has_reply_evidence(row):
                rts = _parse_ts(_first(row, _REPLY_TS_FIELDS)) or ts
                rkey = f'reply:{lmid}' if lmid else None
                yield _event('reply', dims, rts, error=None, dedupe=rkey)
        elif outcome == 'failed':
            err = _first(row, ('send_error', 'error', 'last_error', 'bridge_error', 'text_error'))
            yield _event('failed', dims, ts, error=(str(err)[:300] if err else str(row.get('status') or '')[:300]), dedupe=None)


def _iter_queue_events(rows: Iterable[dict[str, Any]], *, since: datetime | None,
                       now: datetime, stale_seconds: int) -> Iterator[dict[str, Any]]:
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = str(row.get('status') or '').strip().lower()
        ts = _parse_ts(row.get('sent_at') or row.get('updated_at') or row.get('created_at'))
        if since and ts and ts < since:
            continue
        dims = _queue_dims(row)
        lmid = row.get('logical_message_id') or row.get('dispatch_id')
        if status == 'sent':
            yield _event('sent', dims, _parse_ts(row.get('sent_at')) or ts, error=None,
                         dedupe=f'sent:{lmid}' if lmid else None)
        elif status == 'failed':
            yield _event('failed', dims, ts, error=str(row.get('last_error') or '')[:300], dedupe=None)
        elif status == 'blocked':
            yield _event('blocked', dims, ts, error=str(row.get('last_error') or '')[:300], dedupe=None)
        elif status == 'locked':
            yield _event('locked', dims, ts, error=None, dedupe=None)
            locked_at = _parse_ts(row.get('locked_at'))
            if locked_at and (now - locked_at) > timedelta(seconds=max(1, stale_seconds)):
                yield _event('stale', dims, locked_at, error='stale_lock', dedupe=None)


# --------------------------------------------------------------------------- #
# Agregação em buckets
# --------------------------------------------------------------------------- #
def _empty_bucket() -> dict[str, Any]:
    b: dict[str, Any] = {k: 0 for k in _COUNT_KEYS}
    b['lastSentAt'] = None
    b['lastErrorAt'] = None
    b['lastError'] = None
    return b


def _bump(bucket: dict[str, Any], ev: dict[str, Any]) -> None:
    outcome = ev['outcome']
    count_key = 'replies' if outcome == 'reply' else outcome
    bucket[count_key] = bucket.get(count_key, 0) + 1
    ts_iso = _iso(ev['ts']) if ev['ts'] else None
    if outcome == 'sent' and ts_iso:
        if not bucket['lastSentAt'] or ts_iso > bucket['lastSentAt']:
            bucket['lastSentAt'] = ts_iso
    if outcome in ('failed', 'blocked', 'stale'):
        if ts_iso and (not bucket['lastErrorAt'] or ts_iso > bucket['lastErrorAt']):
            bucket['lastErrorAt'] = ts_iso
            bucket['lastError'] = ev.get('error') or bucket['lastError']
        elif ev.get('error') and not bucket['lastError']:
            bucket['lastError'] = ev.get('error')


def _sub_bump(store: dict[str, dict[str, Any]], key: str, ev: dict[str, Any]) -> None:
    b = store.setdefault(key, {k: 0 for k in _COUNT_KEYS})
    count_key = 'replies' if ev['outcome'] == 'reply' else ev['outcome']
    b[count_key] = b.get(count_key, 0) + 1


def chip_health_score(bucket: dict[str, Any], *, health_floor: float = DEFAULT_HEALTH_FLOOR) -> float:
    """Score simples de saúde/reputação (0..100) de um chip/operador.

    Determinístico e puro. Base = taxa de sucesso; bônus por resposta do lead;
    penalidade por locks presos (stale) e por bloqueios de guardrail. Sem
    histórico terminal (nenhum enviado/falha/bloqueio), devolve neutro.
    """
    sent = int(bucket.get('sent', 0))
    failed = int(bucket.get('failed', 0))
    blocked = int(bucket.get('blocked', 0))
    replies = int(bucket.get('replies', 0))
    stale = int(bucket.get('stale', 0))
    attempts = sent + failed + blocked
    if attempts == 0:
        return NEUTRAL_SCORE
    score = (sent / attempts) * 100.0
    if sent > 0:
        score += min(10.0, (replies / sent) * 10.0)
    score -= min(25.0, stale * 8.0)
    score -= min(15.0, blocked * 3.0)
    score = max(0.0, min(100.0, score))
    return round(score, 2)


def _finalize_bucket(bucket: dict[str, Any], *, health_floor: float,
                     by_origin: dict[str, dict[str, Any]] | None = None,
                     by_nature: dict[str, dict[str, Any]] | None = None,
                     extra: dict[str, Any] | None = None) -> dict[str, Any]:
    sent = int(bucket.get('sent', 0))
    failed = int(bucket.get('failed', 0))
    blocked = int(bucket.get('blocked', 0))
    replies = int(bucket.get('replies', 0))
    attempts = sent + failed + blocked
    out: dict[str, Any] = {k: int(bucket.get(k, 0)) for k in _COUNT_KEYS}
    out['attempts'] = attempts
    out['successRate'] = round(sent / attempts, 4) if attempts else None
    out['replyRate'] = round(replies / sent, 4) if sent else None
    out['lastSentAt'] = bucket.get('lastSentAt')
    out['lastErrorAt'] = bucket.get('lastErrorAt')
    out['lastError'] = bucket.get('lastError')
    score = chip_health_score(bucket, health_floor=health_floor)
    out['healthScore'] = score
    out['healthy'] = bool(score >= health_floor) if attempts else None
    if by_origin is not None:
        out['byOrigin'] = {k: _finalize_sub(v) for k, v in sorted(by_origin.items())}
    if by_nature is not None:
        out['byNature'] = {k: _finalize_sub(v) for k, v in sorted(by_nature.items())}
    if extra:
        out.update(extra)
    return out


def _finalize_sub(sub: dict[str, Any]) -> dict[str, Any]:
    sent = int(sub.get('sent', 0))
    failed = int(sub.get('failed', 0))
    blocked = int(sub.get('blocked', 0))
    attempts = sent + failed + blocked
    out = {k: int(sub.get(k, 0)) for k in _COUNT_KEYS}
    out['attempts'] = attempts
    out['successRate'] = round(sent / attempts, 4) if attempts else None
    return out


# --------------------------------------------------------------------------- #
# Snapshot determinístico
# --------------------------------------------------------------------------- #
def build_learning_snapshot(*, ledger_rows: Iterable[dict[str, Any]] | None = None,
                            dispatch_rows: Iterable[dict[str, Any]] | None = None,
                            ledger_path: str | Path = WPP_ENVIOS,
                            queue_path: str | Path = DISPATCH_QUEUE,
                            now: datetime | None = None, since_days: int | None = None,
                            stale_seconds: int = DEFAULT_STALE_SECONDS,
                            health_floor: float = DEFAULT_HEALTH_FLOOR,
                            generated_at: str | None = None) -> dict[str, Any]:
    """Deriva o snapshot de aprendizado por chip e operador (read-only, puro).

    Se `ledger_rows`/`dispatch_rows` não forem passados, lê os arquivos vivos.
    Nos testes passamos linhas sintéticas e não tocamos a operação.
    """
    ts = _now(now)
    since = ts - timedelta(days=since_days) if since_days else None

    if ledger_rows is None:
        raw = load_json(ledger_path, {'envios': []})
        ledger_rows = raw.get('envios', []) if isinstance(raw, dict) else (raw or [])
    if dispatch_rows is None:
        try:
            dispatch_rows = load_dispatches(queue_path)
        except Exception:
            dispatch_rows = []

    events = list(_iter_ledger_events(ledger_rows, since=since))
    events += list(_iter_queue_events(dispatch_rows, since=since, now=ts, stale_seconds=stale_seconds))

    # Dedupe idempotente entre fontes: um mesmo envio lógico registrado no ledger
    # e na fila conta uma vez só (chave outcome:logical_message_id).
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for ev in events:
        key = ev.get('dedupe')
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        deduped.append(ev)

    chips: dict[str, dict[str, Any]] = {}
    chip_origin: dict[str, dict[str, dict[str, Any]]] = {}
    chip_nature: dict[str, dict[str, dict[str, Any]]] = {}
    chip_owners: dict[str, set[str]] = {}
    operators: dict[str, dict[str, Any]] = {}
    op_origin: dict[str, dict[str, dict[str, Any]]] = {}
    op_nature: dict[str, dict[str, dict[str, Any]]] = {}
    op_ports: dict[str, set[str]] = {}
    op_display: dict[str, Any] = {}
    totals = _empty_bucket()

    for ev in deduped:
        pk = ev['port']
        ok = ev['owner_key']
        chips.setdefault(pk, _empty_bucket())
        operators.setdefault(ok, _empty_bucket())
        _bump(chips[pk], ev)
        _bump(operators[ok], ev)
        _bump(totals, ev)
        _sub_bump(chip_origin.setdefault(pk, {}), ev['origin'], ev)
        _sub_bump(chip_nature.setdefault(pk, {}), ev['nature'], ev)
        _sub_bump(op_origin.setdefault(ok, {}), ev['origin'], ev)
        _sub_bump(op_nature.setdefault(ok, {}), ev['nature'], ev)
        chip_owners.setdefault(pk, set()).add(ok)
        op_ports.setdefault(ok, set()).add(pk)
        if ev.get('owner_display') and ok not in op_display:
            op_display[ok] = ev['owner_display']

    chips_out = {
        pk: _finalize_bucket(chips[pk], health_floor=health_floor,
                             by_origin=chip_origin.get(pk, {}), by_nature=chip_nature.get(pk, {}),
                             extra={'port': _port_display(pk), 'owners': sorted(chip_owners.get(pk, set()))})
        for pk in sorted(chips)
    }
    operators_out = {
        ok: _finalize_bucket(operators[ok], health_floor=health_floor,
                             by_origin=op_origin.get(ok, {}), by_nature=op_nature.get(ok, {}),
                             extra={'operator': ok, 'displayName': op_display.get(ok),
                                    'ports': sorted(op_ports.get(ok, set()), key=lambda p: (not p.isdigit(), p))})
        for ok in sorted(operators)
    }

    return {
        'version': SCHEMA_VERSION,
        'generatedAt': generated_at if generated_at is not None else _iso(ts),
        'window': {'sinceDays': since_days, 'since': _iso(since) if since else None},
        'healthFloor': health_floor,
        'staleSeconds': stale_seconds,
        'totals': _finalize_bucket(totals, health_floor=health_floor),
        'chips': chips_out,
        'operators': operators_out,
    }


def write_learning_snapshot(*, path: str | Path = LEARNING_SNAPSHOT, **kwargs) -> dict[str, Any]:
    """Reconstrói e persiste o snapshot sob lock (idempotente: reescreve tudo)."""
    snapshot = build_learning_snapshot(**kwargs)
    update_json_locked(path, {'version': SCHEMA_VERSION}, lambda _old: snapshot)
    return snapshot


def load_learning_snapshot(path: str | Path = LEARNING_SNAPSHOT) -> dict[str, Any]:
    data = load_json(path, {})
    return data if isinstance(data, dict) else {}


# --------------------------------------------------------------------------- #
# Consulta para o roteador (ainda NÃO ligada ao envio live)
# --------------------------------------------------------------------------- #
def _rank_flag(healthy: Any) -> int:
    if healthy is True:
        return 2
    if healthy is None:
        return 1
    return 0


def rank_healthy_chips(snapshot: dict[str, Any], candidate_ports: Iterable[Any] | None = None,
                       *, floor: float | None = None) -> list[dict[str, Any]]:
    """Ordena chips por saúde (saudável > desconhecido > insalubre), score desc.

    Consulta pura: o roteador poderá chamar isto para *preferir* chips saudáveis
    sem que este módulo dispare nada. Portas candidatas sem histórico entram como
    neutras (healthy=None) para não deixar chip novo morrer à míngua.
    """
    chips = snapshot.get('chips', {}) if isinstance(snapshot, dict) else {}
    cand = None if candidate_ports is None else {_port_key(p) for p in candidate_ports}
    keys = set(chips.keys())
    if cand is not None:
        keys |= cand
    result: list[dict[str, Any]] = []
    for pk in sorted(keys):
        if cand is not None and pk not in cand:
            continue
        b = chips.get(pk)
        if b is None:
            result.append({'port': _port_display(pk), 'healthScore': NEUTRAL_SCORE,
                           'healthy': None, 'sent': 0, 'successRate': None, 'known': False})
        else:
            result.append({'port': b.get('port', _port_display(pk)), 'healthScore': b.get('healthScore', NEUTRAL_SCORE),
                           'healthy': b.get('healthy'), 'sent': int(b.get('sent', 0)),
                           'successRate': b.get('successRate'), 'known': True})
    result.sort(key=lambda e: (_rank_flag(e['healthy']), e['healthScore'], e['sent']), reverse=True)
    return result


def prefer_healthy_chip(snapshot: dict[str, Any], candidate_ports: Iterable[Any] | None = None,
                        *, floor: float | None = None) -> Any:
    """Devolve a melhor porta candidata por saúde, ou None. Só sugere, não envia."""
    ranked = rank_healthy_chips(snapshot, candidate_ports, floor=floor)
    return ranked[0]['port'] if ranked else None


def rank_healthy_operators(snapshot: dict[str, Any], candidate_operators: Iterable[Any] | None = None,
                           *, floor: float | None = None) -> list[dict[str, Any]]:
    """Mesma lógica de ranking, aplicada a operadores/owners."""
    ops = snapshot.get('operators', {}) if isinstance(snapshot, dict) else {}
    cand = None if candidate_operators is None else {_owner_key(o) for o in candidate_operators}
    keys = set(ops.keys())
    if cand is not None:
        keys |= cand
    result: list[dict[str, Any]] = []
    for ok in sorted(keys):
        if cand is not None and ok not in cand:
            continue
        b = ops.get(ok)
        if b is None:
            result.append({'operator': ok, 'displayName': None, 'healthScore': NEUTRAL_SCORE,
                           'healthy': None, 'sent': 0, 'known': False})
        else:
            result.append({'operator': ok, 'displayName': b.get('displayName'),
                           'healthScore': b.get('healthScore', NEUTRAL_SCORE), 'healthy': b.get('healthy'),
                           'sent': int(b.get('sent', 0)), 'known': True})
    result.sort(key=lambda e: (_rank_flag(e['healthy']), e['healthScore'], e['sent']), reverse=True)
    return result


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description='Zydon chip/operator continuous-learning snapshot (read-only)')
    ap.add_argument('--since-days', type=int, default=None)
    ap.add_argument('--stale-seconds', type=int, default=DEFAULT_STALE_SECONDS)
    ap.add_argument('--write', action='store_true', help='persistir em controle/chip_operator_learning.json')
    ap.add_argument('--out', default=str(LEARNING_SNAPSHOT))
    args = ap.parse_args(argv)
    if args.write:
        snap = write_learning_snapshot(path=args.out, since_days=args.since_days, stale_seconds=args.stale_seconds)
    else:
        snap = build_learning_snapshot(since_days=args.since_days, stale_seconds=args.stale_seconds)
    print(json.dumps({'generatedAt': snap['generatedAt'], 'totals': snap['totals'],
                      'chips': {k: {'healthScore': v['healthScore'], 'sent': v['sent'],
                                    'failed': v['failed'], 'healthy': v['healthy']}
                                for k, v in snap['chips'].items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
