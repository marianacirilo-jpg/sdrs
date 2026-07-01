#!/usr/bin/env python3
"""Utilitários centrais de JID/telefone WhatsApp para Zydon.

Regra de produto:
- Preferir PN (`@s.whatsapp.net`) quando o device expõe `remoteJidAlt`/`jidAlt`.
- Nunca derivar telefone de `@lid` puro.
- Canonicalizar celular BR com/sem nono dígito para uma única thread.
"""
from __future__ import annotations

import re
from typing import Any


def is_lid(value: Any) -> bool:
    return str(value or '').strip().endswith('@lid')


def is_group_or_broadcast(value: Any) -> bool:
    s = str(value or '').strip()
    return s.endswith('@g.us') or s.endswith('@broadcast') or s == 'status@broadcast'


# Números internos Zydon/SDR/institucionais. Nunca são lead/destino comercial
# para o worker/painel; conversas entre eles são coordenação/aquecimento/privadas.
INTERNAL_WPP_DIGITS = {
    '553484255965',  # Mariana institucional
    '553484477245',  # Sarah antigo
    '553484291640',  # Sarah novo/canônico
    '553484325076',  # Breno
    '553484295409',  # Lucas Batista
    '553484428888',  # Lucas Resende institucional
    '553496698718',  # Rafael
}


def is_internal_contact(value: Any) -> bool:
    d = only_digits(value)
    return any(d.startswith(n) for n in INTERNAL_WPP_DIGITS)


def is_blocked_operational_target(value: Any) -> bool:
    """True para destinos que jamais devem virar envio/conversa operacional.

    Usado por producers, fila/flow, worker e Channel para manter uma única
    fronteira: grupo/broadcast e chips internos não são leads.
    """
    return is_group_or_broadcast(value) or is_internal_contact(value)


def only_digits(value: Any) -> str:
    return ''.join(ch for ch in str(value or '') if ch.isdigit())


def _candidate_jids_from_message(msg: dict[str, Any] | None) -> list[str]:
    m = msg or {}
    vals = []
    for key in ('remoteJidAlt', 'jidAlt', 'jid', 'chat', 'sender', 'participant'):
        vals.append(str(m.get(key) or '').strip())
    raw = m.get('rawKey') or {}
    if isinstance(raw, dict):
        for key in ('remoteJidAlt', 'jidAlt', 'remoteJid', 'participant'):
            vals.append(str(raw.get(key) or '').strip())
    out = []
    seen = set()
    for v in vals:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def real_phone_digits(value: Any) -> str:
    """Retorna telefone BR canônico com DDI 55 ou vazio.

    Aceita JID PN/c.us e número formatado. Não aceita `@lid` puro, grupos ou
    broadcast. Para celular BR antigo `55 + DDD + 8 dígitos` começando em 6/7/8/9,
    insere o nono dígito depois do DDD.
    """
    s = str(value or '').strip()
    if not s or is_lid(s) or is_group_or_broadcast(s):
        return ''
    d = only_digits(s)
    if len(d) in (10, 11):
        d = '55' + d
    if not d.startswith('55') or len(d) not in (12, 13):
        return ''
    if len(d) == 12 and d[4:5] in {'6', '7', '8', '9'}:
        d = d[:4] + '9' + d[4:]
    return d


def canonical_chat_id(value: Any) -> str:
    d = real_phone_digits(value)
    return f'{d}@s.whatsapp.net' if d else str(value or '').strip()


def canonical_chat_for_message(msg: dict[str, Any] | None) -> str:
    for v in _candidate_jids_from_message(msg):
        d = real_phone_digits(v)
        if d:
            return f'{d}@s.whatsapp.net'
    return str((msg or {}).get('chat') or '').strip()


def jid_from_phone(value: Any) -> str:
    d = real_phone_digits(value)
    return f'{d}@s.whatsapp.net' if d else ''


def phone_aliases(value: Any) -> set[str]:
    d = real_phone_digits(value)
    if not d:
        return set()
    out = {d}
    local = d[2:]
    if len(local) == 11 and local[2] == '9':
        out.add('55' + local[:2] + local[3:])
    elif len(local) == 10 and local[2:3] in {'6', '7', '8', '9'}:
        out.add('55' + local[:2] + '9' + local[2:])
    return out
