#!/usr/bin/env python3
"""Taxonomia central de mensagens WhatsApp Zydon.

Este módulo não envia WhatsApp. Ele só transforma uma intenção de negócio
(`nature` + `thread_state` + `origin`) em campos padronizados para quota,
ledger e compatibilidade com os campos legados (`status`/`msg_type`).
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

COLD_AUTOMATION = 'cold_automation'
PIPELINE_FOLLOWTHROUGH = 'pipeline_followthrough'
ACTIVE_CONVERSATION = 'active_conversation'
INTERNAL = 'internal'
WARMUP = 'warmup'

COLD_OUTREACH = 'cold_outreach'
POST_DIAGNOSTIC = 'post_diagnostic'
SCHEDULED_MEETING = 'scheduled_meeting'
NO_SHOW = 'no_show'
OPT_OUT = 'opt_out'
INTERNAL_ONLY = 'internal_only'

_NATURES = {
    'first_contact': {
        'quota_class': COLD_AUTOMATION,
        'legacy_status': 'primeiro_contato',
        'legacy_msg_type': 'primeiro_contato',
    },
    'followup_f1': {
        'quota_class': COLD_AUTOMATION,
        'legacy_status': 'followup_f1',
        'legacy_msg_type': 'primeiro_contato_cadencia',
    },
    'followup_f2': {
        'quota_class': COLD_AUTOMATION,
        'legacy_status': 'followup_f2',
        'legacy_msg_type': 'primeiro_contato_cadencia',
    },
    'followup_f3': {
        'quota_class': COLD_AUTOMATION,
        'legacy_status': 'followup_f3',
        'legacy_msg_type': 'primeiro_contato_cadencia',
    },
    'followup_f4': {
        'quota_class': COLD_AUTOMATION,
        'legacy_status': 'followup_f4',
        'legacy_msg_type': 'primeiro_contato_cadencia',
    },
    'non_mql_outreach': {
        'quota_class': COLD_AUTOMATION,
        'legacy_status': 'nao_mql_legitimo_tratativa',
        'legacy_msg_type': 'nao_mql_legitimo_tratativa',
    },
    'reentry_diagnostic': {
        # Reabordagem fria de lead recuperado de reinscrição: conta na quota de
        # automação fria como qualquer primeiro contato. Mantém o mesmo
        # quota_class que a fila central já atribuía por fallback, para não mudar
        # o volume observado dos disparos reentry já enfileirados.
        'quota_class': COLD_AUTOMATION,
        'legacy_status': 'enviado_lead',
        'legacy_msg_type': 'reentry_diagnostic',
    },
    'diagnostic_bundle': {
        'quota_class': PIPELINE_FOLLOWTHROUGH,
        'legacy_status': 'enviado_lead',
        'legacy_msg_type': 'diagnostic_bundle',
    },
    'diagnostic_initial': {
        'quota_class': PIPELINE_FOLLOWTHROUGH,
        'legacy_status': 'mql_diagnostico_em_andamento',
        'legacy_msg_type': 'diagnostic_initial',
    },
    'diagnostic_pdf': {
        'quota_class': PIPELINE_FOLLOWTHROUGH,
        'legacy_status': 'enviado_lead',
        'legacy_msg_type': 'diagnostic_pdf',
    },
    'diagnostic_question': {
        'quota_class': PIPELINE_FOLLOWTHROUGH,
        'legacy_status': 'enviado_lead',
        'legacy_msg_type': 'diagnostic_question',
    },
    'diagnostic_agenda_invite': {
        'quota_class': PIPELINE_FOLLOWTHROUGH,
        'legacy_status': 'enviado_lead',
        'legacy_msg_type': 'diagnostic_agenda_invite',
    },
    'agenda_confirmation': {
        'quota_class': PIPELINE_FOLLOWTHROUGH,
        'legacy_status': 'enviado_lead',
        'legacy_msg_type': 'diagnostico_agenda_confirmacao',
    },
    'agenda_reminder': {
        'quota_class': PIPELINE_FOLLOWTHROUGH,
        'legacy_status': 'enviado_lead',
        'legacy_msg_type': 'diagnostico_agenda_lembrete',
    },
    'followup_f1_postdiag': {
        'quota_class': PIPELINE_FOLLOWTHROUGH,
        'legacy_status': 'mql_followup1_deterministico',
        'legacy_msg_type': 'mql_followup1_deterministico',
    },
    'no_show_recovery': {
        'quota_class': PIPELINE_FOLLOWTHROUGH,
        'legacy_status': 'no_show_recovery',
        'legacy_msg_type': 'no_show_recovery',
    },
    'manual_reply': {
        'quota_class': ACTIVE_CONVERSATION,
        'legacy_status': 'manual_reply',
        'legacy_msg_type': 'manual_reply',
    },
    'internal_group_alert': {
        'quota_class': INTERNAL,
        'legacy_status': 'enviado_grupo',
        'legacy_msg_type': 'internal_group_alert',
    },
    'system_monitor': {
        'quota_class': INTERNAL,
        'legacy_status': 'system_monitor',
        'legacy_msg_type': 'system_monitor',
    },
    'premeeting_summary': {
        'quota_class': INTERNAL,
        'legacy_status': 'premeeting_summary',
        'legacy_msg_type': 'premeeting_summary',
    },
    'warmup': {
        'quota_class': WARMUP,
        'legacy_status': 'warmup',
        'legacy_msg_type': 'warmup',
    },
}

_ACTIVE_THREAD_STATES = {ACTIVE_CONVERSATION}
_NON_COUNTED_CLASSES = {ACTIVE_CONVERSATION, INTERNAL, WARMUP}


def known_natures() -> tuple[str, ...]:
    return tuple(sorted(_NATURES))


def _require_known_nature(nature: str) -> dict:
    key = str(nature or '').strip()
    try:
        return _NATURES[key]
    except KeyError as exc:
        raise ValueError(f'nature desconhecida: {nature!r}') from exc


def quota_class_for(nature: str, thread_state: str = COLD_OUTREACH) -> str:
    base = _require_known_nature(nature)['quota_class']
    if str(thread_state or '') in _ACTIVE_THREAD_STATES and base == COLD_AUTOMATION:
        return ACTIVE_CONVERSATION
    return base


def quota_counted_for(nature: str, thread_state: str = COLD_OUTREACH) -> bool:
    return quota_class_for(nature, thread_state) not in _NON_COUNTED_CLASSES


def describe_nature(nature: str, thread_state: str = COLD_OUTREACH) -> dict:
    spec = dict(_require_known_nature(nature))
    qc = quota_class_for(nature, thread_state)
    return {
        'nature': str(nature),
        'thread_state': str(thread_state or COLD_OUTREACH),
        'quota_class': qc,
        'quota_counted': qc not in _NON_COUNTED_CLASSES,
        'legacy_status': spec['legacy_status'],
        'legacy_msg_type': spec['legacy_msg_type'],
    }


def build_logical_message(*, nature: str, thread_state: str, origin: str, conversation_id: str,
                          selected_port: int | str | None = None, owner_sdr: str | None = None,
                          parts: list[dict] | None = None, logical_message_id: str | None = None,
                          **extra) -> dict:
    intent = describe_nature(nature, thread_state)
    lm_id = logical_message_id or f"lm_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid4().hex[:8]}"
    normalized_parts = []
    for i, part in enumerate(parts or [{'kind': 'text', 'part_nature': nature}], start=1):
        p = dict(part or {})
        p.setdefault('seq', i)
        p.setdefault('part_nature', nature)
        p['logical_message_id'] = lm_id
        normalized_parts.append(p)
    record = {
        'logical_message_id': lm_id,
        'conversation_id': conversation_id,
        'jid': conversation_id,
        'selected_port': int(selected_port) if str(selected_port or '').isdigit() else selected_port,
        'owner_sdr': owner_sdr,
        'nature': nature,
        'origin': origin,
        'thread_state': intent['thread_state'],
        'quota_class': intent['quota_class'],
        'quota_counted': intent['quota_counted'],
        'legacy_status': intent['legacy_status'],
        'legacy_msg_type': intent['legacy_msg_type'],
        'status': 'pending',
        'parts': normalized_parts,
        'ts': datetime.now(timezone.utc).isoformat(),
    }
    record.update(extra)
    return record
