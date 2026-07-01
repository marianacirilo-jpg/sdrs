#!/usr/bin/env python3
"""Monitor silencioso de qualidade dos envios WhatsApp Dexter/Zydon.

Lê os history_46xx.json das bridges e alerta apenas quando um envio recente
1:1 apresenta risco técnico de entrega/materialização no device do remetente:
- envio sem canonicalização após a blindagem;
- onWhatsApp/canonicalização com erro ou exists=false;
- preflight sem devices;
- privacyToken recusado;
- ownSync não OK.

Sem risco novo => stdout vazio, próprio para cron/script-only.
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterable

DEFAULT_HISTORY_GLOB = '/root/.hermes/whatsapp-extra/channel_data/history_46*.json'
DEFAULT_STATE_PATH = '/root/.hermes/zydon-prospeccao/controle/whatsapp_outbound_quality_monitor_state.json'
DEFAULT_WINDOW_MINUTES = 180
# Marco da implantação da blindagem onWhatsApp/JID canônico. Evita que
# histórico legado gere ruído se o estado do watchdog for recriado.
DEFAULT_SINCE_ISO = '2026-06-29T23:30:00Z'


@dataclass(frozen=True)
class Finding:
    key: str
    severity: str
    port: int | str | None
    message_id: str | None
    chat: str | None
    requested_chat: str | None
    reasons: tuple[str, ...]
    text_preview: str
    iso: str | None


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return None


def is_recent(rec: dict[str, Any], now: datetime, window_minutes: int, since: datetime | None = None) -> bool:
    dt = parse_iso(rec.get('iso'))
    if dt is None:
        # Sem ISO: não alerta por padrão para evitar ruído de histórico legado.
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if since is not None and dt < since:
        return False
    return dt >= now - timedelta(minutes=window_minutes)


def is_1to1_pn_jid(jid: str | None) -> bool:
    return bool(jid and jid.endswith('@s.whatsapp.net'))


def is_deleted(rec: dict[str, Any]) -> bool:
    return bool(rec.get('deleted') or rec.get('revoked') or rec.get('isDeleted'))


def _string_bad_token(value: Any) -> bool:
    if value is None or value is True:
        return False
    s = str(value).lower()
    return 'bad-request' in s or 'error' in s or 'forbidden' in s or 'timed' in s


def analyze_record(rec: dict[str, Any], now: datetime, window_minutes: int, since: datetime | None = None) -> Finding | None:
    if rec.get('type') != 'api-send':
        return None
    if is_deleted(rec):
        return None
    chat = rec.get('chat')
    requested = rec.get('requestedChat')
    if not is_1to1_pn_jid(chat):
        return None
    if not is_recent(rec, now, window_minutes, since):
        return None

    reasons: list[str] = []
    canonical = rec.get('canonicalization')
    preflight = rec.get('preflight')
    own_sync = rec.get('ownSync')

    # Depois da blindagem, todo envio 1:1 novo deveria carregar canonicalization.
    if canonical is None:
        reasons.append('sem_canonicalizacao')
    elif isinstance(canonical, dict):
        if canonical.get('error'):
            reasons.append(f"canonicalizacao_erro:{str(canonical.get('error'))[:80]}")
        if canonical.get('exists') is False:
            reasons.append('onWhatsApp_exists_false')
        if canonical.get('jid') and canonical.get('jid') != chat:
            reasons.append('chat_final_diverge_do_canonical')
    else:
        reasons.append('canonicalizacao_formato_invalido')

    if preflight is None:
        reasons.append('sem_preflight')
    elif isinstance(preflight, dict) and not preflight.get('skipped'):
        devices = preflight.get('devices')
        if isinstance(devices, list) and len(devices) == 0:
            reasons.append('preflight_devices_vazio')
        elif isinstance(devices, str) and devices:
            reasons.append(f"preflight_devices_erro:{devices[:80]}")
        if _string_bad_token(preflight.get('privacyToken')):
            reasons.append(f"privacy_token_ruim:{str(preflight.get('privacyToken'))[:80]}")
    elif not isinstance(preflight, dict):
        reasons.append('preflight_formato_invalido')

    if isinstance(own_sync, dict):
        if own_sync.get('ok') is not True:
            reasons.append(f"ownSync_nao_ok:{str(own_sync)[:100]}")
    elif own_sync is None:
        reasons.append('sem_ownSync')

    if not reasons:
        return None

    mid = rec.get('id')
    port = rec.get('port')
    key = f"{port}|{chat}|{mid}|{','.join(reasons)}"
    text = str(rec.get('text') or '').replace('\n', ' ')
    if len(text) > 140:
        text = text[:137] + '...'
    return Finding(
        key=key,
        severity='ALTA' if any('devices_vazio' in r or 'privacy_token_ruim' in r or 'exists_false' in r for r in reasons) else 'MEDIA',
        port=port,
        message_id=mid,
        chat=chat,
        requested_chat=requested,
        reasons=tuple(reasons),
        text_preview=text,
        iso=rec.get('iso'),
    )


def load_json_array(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def scan_histories(paths: Iterable[Path], now: datetime, window_minutes: int, since: datetime | None = None) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        for rec in load_json_array(path):
            finding = analyze_record(rec, now, window_minutes, since)
            if finding:
                findings.append(finding)
    return findings


def load_state(path: Path) -> set[str]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        keys = data.get('alerted_keys', []) if isinstance(data, dict) else []
        return set(str(x) for x in keys)
    except Exception:
        return set()


def save_state(path: Path, keys: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Mantém estado compacto.
    ordered = sorted(keys)[-5000:]
    path.write_text(json.dumps({'alerted_keys': ordered}, ensure_ascii=False, indent=2), encoding='utf-8')


def format_findings(findings: list[Finding]) -> str:
    if not findings:
        return ''
    lines = ['⚠️ WhatsApp outbound quality: risco técnico em envio recente']
    for f in findings[:20]:
        lines.append(
            f"- severidade={f.severity} port={f.port} id={f.message_id} chat={f.chat}"
            + (f" requested={f.requested_chat}" if f.requested_chat and f.requested_chat != f.chat else '')
        )
        lines.append(f"  motivos: {', '.join(f.reasons)}")
        if f.text_preview:
            lines.append(f"  texto: {f.text_preview}")
        if f.iso:
            lines.append(f"  horário: {f.iso}")
    if len(findings) > 20:
        lines.append(f"- ... mais {len(findings) - 20} achado(s) omitidos")
    return '\n'.join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--history-glob', default=DEFAULT_HISTORY_GLOB)
    ap.add_argument('--state', default=DEFAULT_STATE_PATH)
    ap.add_argument('--window-minutes', type=int, default=DEFAULT_WINDOW_MINUTES)
    ap.add_argument('--since-iso', default=DEFAULT_SINCE_ISO, help='ignora envios anteriores a este ISO; use vazio para desativar')
    ap.add_argument('--dry-run', action='store_true', help='não grava estado; mostra também achados já alertados')
    args = ap.parse_args()

    import glob
    paths = [Path(p) for p in sorted(glob.glob(args.history_glob))]
    now = datetime.now(timezone.utc)
    since = parse_iso(args.since_iso) if args.since_iso else None
    if since is not None and since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    findings = scan_histories(paths, now, args.window_minutes, since)

    state_path = Path(args.state)
    already = load_state(state_path)
    new_findings = findings if args.dry_run else [f for f in findings if f.key not in already]
    output = format_findings(new_findings)
    if output:
        print(output)
    if not args.dry_run and new_findings:
        save_state(state_path, already | {f.key for f in new_findings})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
