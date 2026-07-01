#!/usr/bin/env python3
"""Camada única de envio WhatsApp Zydon.

Uso por crons/scripts: importa este módulo e chama safe_send_text/safe_send_file
em vez de postar direto na bridge. A camada:
- normaliza telefone/JID para PN (@s.whatsapp.net) quando possível;
- bloqueia @lid sem telefone real mapeado;
- grava auditoria interna com messageId;
- reconcilia depois contra history_<port>.json.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT = Path('/root/.hermes/zydon-prospeccao')
WA_EXTRA = Path('/root/.hermes/whatsapp-extra')
DATA_DIR = WA_EXTRA / 'channel_data'
OUTBOUND_AUDIT_FILE = PROJECT / 'controle' / 'channel_outbound_audit.jsonl'
ENVIO_LEDGER_FILE = PROJECT / 'controle' / 'wpp_envios.json'
SEND_LOCK_DIR = PROJECT / 'controle' / 'runtime' / 'whatsapp_send_locks'
HOMOLOGATED_TEAM_PHONES = {
    '553496698718', '553484255965', '553484095632', '553484295409',
    '553484325076', '553484428888', '553484222311', '553484178698',
}
MANUAL_REPLY_UID_PREFIXES = (
    'manual_', 'incoming_auto_reply:', 'reply_', 'lead_reply_', 'operator_reply_'
)
# Semáforo global de transporte: todos os envios externos que entram pela camada
# segura passam por aqui antes da bridge. Isso centraliza a proteção contra
# corrida entre crons/disparos únicos; a trava fina por destino+payload continua
# abaixo para idempotência da regra 9.
GLOBAL_TRANSPORT_LOCK = PROJECT / 'controle' / 'runtime' / 'whatsapp_global_transport.lock'
_AUDIT_LOCK = threading.Lock()


def only_digits(value):
    return ''.join(ch for ch in str(value or '') if ch.isdigit())


def is_lid(jid):
    return str(jid or '').strip().endswith('@lid')


def canonical_chat_id(jid):
    s = str(jid or '').strip()
    if not s:
        return ''
    if s.endswith('@g.us') or s == 'status@broadcast' or s.endswith('@broadcast'):
        return s
    if s.endswith('@lid'):
        return s
    if '@' in s:
        local = s.split('@', 1)[0]
    else:
        local = s
    digits = only_digits(local)
    if not digits:
        return s
    if len(digits) in (10, 11):
        digits = '55' + digits
    return f'{digits}@s.whatsapp.net'


def _real_phone_jid(jid):
    s = canonical_chat_id(jid)
    if s.endswith('@s.whatsapp.net') and only_digits(s):
        return s
    return ''


def _history_rows(port):
    p = DATA_DIR / f'history_{int(port)}.json'
    try:
        data = json.loads(p.read_text(encoding='utf-8')) if p.exists() else []
    except Exception:
        data = []
    return data if isinstance(data, list) else []


def _jid_alt_from_msg(m):
    if not isinstance(m, dict):
        return ''
    candidates = [m.get('jidAlt'), m.get('remoteJidAlt')]
    raw = m.get('rawKey') or m.get('key') or {}
    if isinstance(raw, dict):
        candidates.extend([raw.get('remoteJidAlt'), raw.get('participantAlt')])
    for c in candidates:
        pn = _real_phone_jid(c)
        if pn:
            return pn
    return ''


def _message_matches_chat(m, chat, canon):
    vals = [m.get('chat'), m.get('jid'), m.get('remoteJid')]
    raw = m.get('rawKey') or m.get('key') or {}
    if isinstance(raw, dict):
        vals.extend([raw.get('remoteJid'), raw.get('participant')])
    return any(str(v or '') == chat or canonical_chat_id(v) == canon for v in vals)


def resolve_target_jid(port, chat):
    """Retorna (target_jid, erro). Nunca devolve @lid sem PN mapeado."""
    chat = str(chat or '').strip()
    if not chat:
        return '', 'chat vazio'
    if chat.endswith('@g.us') or chat == 'status@broadcast' or chat.endswith('@broadcast'):
        return chat, ''
    pn = _real_phone_jid(chat)
    if pn:
        return pn, ''
    canon = canonical_chat_id(chat)
    try:
        for m in reversed(_history_rows(int(port))):
            if not isinstance(m, dict):
                continue
            if not _message_matches_chat(m, chat, canon):
                continue
            alt = _jid_alt_from_msg(m)
            if alt:
                return alt, ''
    except Exception:
        pass
    if is_lid(chat):
        return '', 'Conversa está só como LID; sem telefone real/PN para enviar com segurança.'
    return '', 'chat não é um telefone WhatsApp válido'


def _normalize_message_id(value):
    v = str(value or '').strip()
    if not v:
        return ''
    return re.sub(r'_(text|pdf|media|file|caption)$', '', v, flags=re.I)


def bridge_message_ids(resp):
    ids, seen = [], set()
    def add(v):
        mid = _normalize_message_id(v)
        if mid and mid not in seen:
            seen.add(mid); ids.append(mid)
    def walk(obj):
        if isinstance(obj, dict):
            add(obj.get('messageId')); add(obj.get('id'))
            for mid in obj.get('messageIds') or []:
                add(mid)
            for key in ('response', 'responses', 'result', 'results', 'bridge'):
                if key in obj:
                    walk(obj.get(key))
        elif isinstance(obj, list):
            for item in obj:
                walk(item)
    walk(resp)
    return ids


def message_ok(resp):
    if isinstance(resp, dict):
        return bool(resp.get('success') or resp.get('messageId') or resp.get('id') or resp.get('status') in (1, 2, '1', '2', 'success'))
    txt = str(resp or '')
    return 'messageId' in txt or '"status": 1' in txt or '"status":2' in txt or 'success' in txt.lower()


def _payload_sha256(payload):
    raw = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _send_lock_path(port, target_jid, send_type, payload):
    key = json.dumps({
        # A chave é global por destino+payload, não por porta: o mesmo lead não
        # deve receber texto idêntico por outro chip só porque houve troca de rota.
        'target': canonical_chat_id(target_jid),
        'sendType': str(send_type or ''),
        'payloadSha256': _payload_sha256(payload),
    }, ensure_ascii=False, sort_keys=True).encode('utf-8')
    return SEND_LOCK_DIR / (hashlib.sha256(key).hexdigest() + '.lock')


def _with_send_lock(port, target_jid, send_type, payload):
    SEND_LOCK_DIR.mkdir(parents=True, exist_ok=True)
    path = _send_lock_path(port, target_jid, send_type, payload)
    fh = path.open('a+')
    fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
    return fh


def _with_global_transport_lock():
    """Lock central para qualquer transporte externo WhatsApp.

    A regra 9 bloqueia duplicidade por destino+payload antes do transporte. Este
    lock complementa a regra centralizando a janela crítica entre crons diferentes
    (diagnóstico, agenda, follow, disparo manual) sem cada script reimplementar
    semáforo próprio. Ele só existe na camada segura: quem não usa esta camada deve
    falhar nos testes de padronização.
    """
    GLOBAL_TRANSPORT_LOCK.parent.mkdir(parents=True, exist_ok=True)
    fh = GLOBAL_TRANSPORT_LOCK.open('a+')
    fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
    return fh


def _phone_variants(jid):
    canon = canonical_chat_id(jid)
    d = only_digits(canon)
    if d.startswith('55'):
        national = d[2:]
    else:
        national = d
    vals = set()
    if d:
        vals.add(d)
    if len(national) in (10, 11):
        vals.add('55' + national)
        if len(national) == 10:
            vals.add('55' + national[:2] + '9' + national[2:])
        elif len(national) == 11 and national[2] == '9':
            vals.add('55' + national[:2] + national[3:])
    return vals


def _load_ledger_rows():
    try:
        obj = json.loads(ENVIO_LEDGER_FILE.read_text(encoding='utf-8'))
    except Exception:
        return []
    if isinstance(obj, dict):
        obj = obj.get('envios', [])
    return obj if isinstance(obj, list) else []


def _has_operational_ledger_for_chat(port, target_jid):
    target_variants = _phone_variants(target_jid)
    if not target_variants:
        return False
    for r in _load_ledger_rows():
        if not isinstance(r, dict):
            continue
        try:
            if int(r.get('bridge_port') or 0) != int(port):
                continue
        except Exception:
            continue
        if not (r.get('contact_id') or r.get('email')):
            continue
        vals = [r.get(k) for k in ('to', 'jid', 'lead_jid', 'phone', 'telefone')]
        for v in vals:
            if _phone_variants(v) & target_variants:
                return True
    return False


def _is_homologated_team_chat(target_jid):
    return bool(_phone_variants(target_jid) & HOMOLOGATED_TEAM_PHONES)


def _manual_reply_requires_ledger(uid):
    u = str(uid or '')
    return any(u.startswith(p) for p in MANUAL_REPLY_UID_PREFIXES)


def _manual_reply_guard(uid, port, target_jid, path):
    """Bloqueia resposta manual em conversa 1:1 sem vínculo operacional.

    Rafael 30/06: conversa privativa de comunicador/SDR não pode ser lida nem
    respondida só porque parece comercial. Manual reply só passa se o chat já tem
    envio operacional auditado no ledger do MESMO chip/porta.
    """
    if path not in ('/send', '/send-file'):
        return None
    if str(target_jid or '').endswith('@g.us') or str(target_jid or '').endswith('@broadcast'):
        return None
    if not _manual_reply_requires_ledger(uid):
        return None
    if _is_homologated_team_chat(target_jid):
        return {
            'success': False, 'blocked': True, 'reason': 'private_homologated_team_chat',
            'error': 'Conversa interna/privativa de chip homologado; não responder.'
        }
    if not _has_operational_ledger_for_chat(port, target_jid):
        return {
            'success': False, 'blocked': True, 'reason': 'manual_reply_without_operational_ledger',
            'error': 'Sem envio operacional/ledger neste chip+chat; não responder conversa privativa.'
        }
    return None


def _release_lock(fh):
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        fh.close()
    except Exception:
        pass


def _text_preview(text, limit=240):
    return ' '.join(str(text or '').split())[:limit]


def _append_audit(row):
    try:
        OUTBOUND_AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _AUDIT_LOCK:
            with OUTBOUND_AUDIT_FILE.open('a', encoding='utf-8') as f:
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
    except Exception:
        pass


def _parse_iso_ts(value):
    try:
        return datetime.fromisoformat(str(value or '').replace('Z', '+00:00'))
    except Exception:
        return None


def _recent_duplicate_send(port, target_jid, send_type, payload, window_seconds=3600):
    """Retorna auditoria recente para mesmo destino+payload, antes de postar na bridge.

    Isso protege todos os crons contra corrida/retry: se dois workers tentarem
    mandar exatamente a mesma mensagem para o mesmo lead dentro da janela, só a
    primeira chega no WhatsApp. A segunda vira bloqueio auditável.
    """
    if os.environ.get('ZYDON_DISABLE_SEND_IDEMPOTENCY') == '1':
        return None
    target = canonical_chat_id(target_jid)
    payload_hash = _payload_sha256(payload)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=window_seconds)
    try:
        lines = OUTBOUND_AUDIT_FILE.read_text(encoding='utf-8').splitlines()
    except Exception:
        return None
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except Exception:
            continue
        ts = _parse_iso_ts(row.get('ts'))
        if ts and ts < cutoff:
            # JSONL está em ordem cronológica; ao andar de trás para frente,
            # eventos mais antigos que o corte podem encerrar a busca.
            break
        if row.get('event') != 'send':
            continue
        if str(row.get('sendType') or '') != str(send_type or ''):
            continue
        if str(row.get('payloadSha256') or '') != payload_hash:
            continue
        row_target = canonical_chat_id(((row.get('bridge') or {}).get('to')) or row.get('targetJid') or row.get('chatOriginal') or '')
        if row_target != target:
            continue
        if not ts or now - ts <= timedelta(seconds=window_seconds):
            return row
    return None


def _record_duplicate_block(uid, port, chat, target_jid, send_type, payload, duplicate_of):
    rec = {
        'event': 'blocked_duplicate_recent',
        'auditId': f"dup_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{secrets.token_hex(5)}",
        'ts': datetime.now(timezone.utc).isoformat(),
        'uid': str(uid or ''),
        'port': int(port),
        'chatOriginal': str(chat or ''),
        'targetJid': canonical_chat_id(target_jid),
        'sendType': str(send_type or ''),
        'payloadSha256': _payload_sha256(payload),
        'textPreview': _text_preview((payload or {}).get('text') or (payload or {}).get('caption') or ''),
        'duplicateOfAuditId': (duplicate_of or {}).get('auditId'),
        'duplicateOfTs': (duplicate_of or {}).get('ts'),
        'duplicateOfMessageIds': (duplicate_of or {}).get('messageIds') or [],
        'blocked': True,
    }
    _append_audit(rec)
    return rec


def record_outbound_audit(uid, port, chat, target_jid, send_type, payload, bridge_resp, normalized_to_pn=False):
    rec = {
        'event': 'send',
        'auditId': f"out_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{secrets.token_hex(5)}",
        'ts': datetime.now(timezone.utc).isoformat(),
        'uid': str(uid or ''),
        'port': int(port),
        'chatOriginal': str(chat or ''),
        'targetJid': canonical_chat_id(target_jid),
        'targetKind': 'group' if str(target_jid).endswith('@g.us') else ('pn' if str(target_jid).endswith('@s.whatsapp.net') else ('lid' if is_lid(target_jid) else 'unknown')),
        'normalizedToPN': bool(normalized_to_pn),
        'sendType': str(send_type or ''),
        'messageIds': bridge_message_ids(bridge_resp),
        'payloadSha256': _payload_sha256(payload),
        'textPreview': _text_preview((payload or {}).get('text') or (payload or {}).get('caption') or ''),
        'fileName': os.path.basename(str((payload or {}).get('fileName') or '')),
        'bridge': bridge_resp if isinstance(bridge_resp, dict) else {'raw': str(bridge_resp)},
        'reconciliationStatus': 'pending',
    }
    _append_audit(rec)
    return rec


def _event_message_id(m):
    for key in ('messageId', 'id'):
        mid = _normalize_message_id((m or {}).get(key))
        if mid and not mid.startswith('wpp_') and not mid.startswith('wpp_envios:'):
            return mid
    for key in ('send_response', 'response', 'bridge'):
        ids = bridge_message_ids((m or {}).get(key))
        if ids:
            return ids[0]
    return ''


def reconcile_outbound_record(rec):
    try:
        port = int(rec.get('port'))
    except Exception:
        return {'status': 'missing', 'matchedBy': '', 'reason': 'port_invalid'}
    target = canonical_chat_id(rec.get('targetJid') or rec.get('chatOriginal') or '')
    ids = {_normalize_message_id(x) for x in (rec.get('messageIds') or []) if _normalize_message_id(x)}
    text = _text_preview(rec.get('textPreview') or '')
    file_name = os.path.basename(str(rec.get('fileName') or '')).lower()
    for m in _history_rows(port):
        if not isinstance(m, dict) or not m.get('fromMe'):
            continue
        if target and canonical_chat_id(m.get('chat') or (m.get('rawKey') or {}).get('remoteJid') or '') != target:
            continue
        mid = _event_message_id(m)
        if mid and mid in ids:
            return {'status': 'found', 'matchedBy': 'messageId', 'messageId': mid, 'historyTimestamp': m.get('timestamp') or m.get('ts')}
        if text and _text_preview(m.get('text') or m.get('caption') or '') == text:
            return {'status': 'found', 'matchedBy': 'text', 'messageId': mid, 'historyTimestamp': m.get('timestamp') or m.get('ts')}
        if file_name and os.path.basename(str(m.get('mediaName') or m.get('fileName') or '')).lower() == file_name:
            return {'status': 'found', 'matchedBy': 'fileName', 'messageId': mid, 'historyTimestamp': m.get('timestamp') or m.get('ts')}
    return {'status': 'missing', 'matchedBy': '', 'reason': 'not_in_history'}


def schedule_reconciliation(rec, delay=8):
    def run():
        try:
            time.sleep(max(0, float(delay)))
            result = reconcile_outbound_record(rec)
            _append_audit({'event': 'reconcile', 'auditId': rec.get('auditId'), 'ts': datetime.now(timezone.utc).isoformat(), **result})
        except Exception as e:
            _append_audit({'event': 'reconcile', 'auditId': rec.get('auditId'), 'ts': datetime.now(timezone.utc).isoformat(), 'status': 'error', 'error': str(e)[:500]})
    threading.Thread(target=run, name='zydon-whatsapp-reconcile', daemon=True).start()


def _post_json(url, payload, timeout=30):
    req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        txt = resp.read().decode('utf-8', errors='replace')
        try:
            return json.loads(txt or '{}')
        except Exception:
            return {'raw': txt}


def safe_post_bridge(port, path, payload, uid='dexter', timeout=30, reconcile=True):
    path = str(path or '')
    payload = dict(payload or {})
    if path not in ('/send', '/send-file'):
        return _post_json(f'http://127.0.0.1:{int(port)}{path}', payload, timeout=timeout)
    original_to = str(payload.get('to') or '')
    target, err = resolve_target_jid(int(port), original_to)
    if err:
        return {'success': False, 'error': err, 'blocked': True, 'to': original_to}
    payload['to'] = target
    guard = _manual_reply_guard(uid, int(port), target, path)
    if guard:
        guard.update({'to': target, 'requestedTo': original_to})
        _append_audit({
            'event': 'blocked_privacy_guard',
            'auditId': f"privacy_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{secrets.token_hex(5)}",
            'ts': datetime.now(timezone.utc).isoformat(),
            'uid': str(uid or ''),
            'port': int(port),
            'chatOriginal': original_to,
            'targetJid': target,
            'reason': guard.get('reason'),
            'textPreview': _text_preview(payload.get('text') or payload.get('caption') or ''),
            'blocked': True,
        })
        return guard
    send_type = 'file' if path == '/send-file' else 'text'

    # Lock cross-process por porta+destino+payload. O lock cobre checar dedupe,
    # postar na bridge e gravar audit; sem isso dois crons podem ler o audit antes
    # de qualquer um gravar e ambos enviam o mesmo payload.
    transport_fh = _with_global_transport_lock()
    lock_fh = _with_send_lock(int(port), target, send_type, payload)
    try:
        dup = _recent_duplicate_send(int(port), target, send_type, payload)
        if dup:
            block = _record_duplicate_block(uid, int(port), original_to, target, send_type, payload, dup)
            return {
                'success': False,
                'blocked': True,
                'duplicate_recent': True,
                'reason': 'duplicate_recent_payload',
                'duplicateOfAuditId': block.get('duplicateOfAuditId'),
                'duplicateOfMessageIds': block.get('duplicateOfMessageIds'),
                'to': target,
            }
        try:
            resp = _post_json(f'http://127.0.0.1:{int(port)}{path}', payload, timeout=timeout)
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            try:
                resp = json.loads(body)
            except Exception:
                resp = {'raw': body}
            resp['http_error'] = e.code
            return resp
        except Exception as e:
            return {'success': False, 'error': str(e), 'timeout_seconds': timeout}
        audit = record_outbound_audit(uid, int(port), original_to, target, send_type, payload, resp, normalized_to_pn=(target != original_to))
    finally:
        _release_lock(lock_fh)
        _release_lock(transport_fh)
    if reconcile:
        schedule_reconciliation(audit)
    return resp


def safe_send_text(port, jid, text, uid='dexter', timeout=30, reconcile=True):
    resp = safe_post_bridge(port, '/send', {'to': jid, 'text': text}, uid=uid, timeout=timeout, reconcile=reconcile)
    return message_ok(resp), resp


def safe_send_file(port, jid, file_path, file_name=None, uid='dexter', timeout=90, reconcile=True, **extra):
    payload = {'to': jid, 'filePath': str(file_path)}
    if file_name:
        payload['fileName'] = file_name
    payload.update({k: v for k, v in extra.items() if v is not None})
    resp = safe_post_bridge(port, '/send-file', payload, uid=uid, timeout=timeout, reconcile=reconcile)
    return message_ok(resp), resp
