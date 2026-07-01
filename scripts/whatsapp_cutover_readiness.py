#!/usr/bin/env python3
"""Auditoria de prontidão para trocar disparos WhatsApp para worker_owned.

Não envia nada. Mapeia quem chama envio direto, qual cron/wrapper aciona e se o
fluxo já tem payload suficiente para virar produtor do worker.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

DIRECT_SEND_TOKENS = (
    'safe_send_text(',
    'safe_post_bridge(',
    'post_bridge_with_retries_locked(',
    'post_bridge_with_retries(',
    'post_bridge_locked(',
    "'/send'",
    '"/send"',
)

FLOW_DEFS = [
    {
        'id': 'agenda_queue',
        'name': 'Agenda pós-diagnóstico',
        'script': 'scripts/agenda_queue_sender.py',
        'cron_name': 'zydon-agenda-queue-sender-1min',
        'wrapper': '~/.hermes/scripts/zydon_agenda_queue_sender.sh',
        'risk': 'baixo',
        'expected_tokens': ['post_bridge_with_retries_locked(', 'lead_replied_after(', 'record_dispatch_shadow_from_row(', "it['text']", "it['jid']", "it['port']"],
        'candidate_checks': ['has_complete_payload', 'lead_reply_guard', 'single_queue_item_mark_done', 'already_dualwrites_shadow'],
        'cutover_status': 'candidate',
        'reason': 'Tem fila própria, guarda resposta do lead antes de enviar, payload contém jid/port/text e marca item done; é o melhor primeiro corte.',
    },
    {
        'id': 'non_mql',
        'name': 'Tratativa Não-MQL legítima',
        'script': 'scripts/non_mql_legit_outreach.py',
        'cron_name': 'zydon-nao-mql-tratativa-legitima-10min',
        'wrapper': '~/.hermes/scripts/zydon_non_mql_legit_backfill.sh',
        'risk': 'médio',
        'expected_tokens': ['post_bridge_with_retries(', 'record_dispatch_shadow_from_row(', 'save_envios(', 'phone_variants'],
        'candidate_checks': ['has_complete_payload', 'has_alt_phone_retry', 'already_dualwrites_shadow'],
        'cutover_status': 'needs_adapter',
        'reason': 'Tem retry por telefone alternativo dentro do sender; worker precisa adapter para tentativa alternativa antes de cortar legado.',
    },
    {
        'id': 'diagnostic_mql',
        'name': 'Diagnóstico MQL / PDF / primeiro envio',
        'script': 'scripts/process_gate_once.py',
        'cron_name': 'zydon-active-mql-qualifier-1min',
        'wrapper': '~/.hermes/scripts/zydon_active_mql_qualifier.sh',
        'risk': 'alto',
        'expected_tokens': ['post_bridge_with_retries_locked(', 'record_dispatch_shadow', 'send-file', 'message_ok('],
        'candidate_checks': ['has_complete_payload', 'handles_media_or_pdf', 'already_dualwrites_shadow'],
        'cutover_status': 'needs_adapter',
        'reason': 'Fluxo amplo com PDF/mídia, grupo e HubSpot; precisa adapter de mídia e separação lead vs interno antes do corte.',
    },
    {
        'id': 'followup_parallel',
        'name': 'Follow-up SDR / lanes paralelas',
        'script': 'scripts/cadencia_primeiro_contato.py',
        'cron_name': 'zydon-followup-parallel-lanes-5min',
        'wrapper': '~/.hermes/scripts/zydon_followup_parallel_lanes_launcher.sh',
        'risk': 'alto',
        'expected_tokens': ['record_dispatch_shadow_from_row(', 'd.registrar_envio(', 'send_whatsapp_sequence', 'choose_outbound_port'],
        'candidate_checks': ['already_dualwrites_shadow', 'has_routing', 'has_sequence_state'],
        'cutover_status': 'needs_adapter',
        'reason': 'Maior volume; precisa preservar lane/estado de sequência e trocar primeiro em lote limitado.',
    },
    {
        'id': 'agenda_monitor',
        'name': 'Monitor diagnóstico agendado / lembretes',
        'script': 'scripts/monitor_diagnostico_agendado.py',
        'cron_name': 'zydon-diagnostico-agendado-monitor',
        'wrapper': '~/.hermes/scripts/zydon_monitor_diagnostico_agendado.sh',
        'risk': 'médio',
        'expected_tokens': ['record_dispatch_shadow_from_row(', 'append_wpp_envio_locked', 'enrich_legacy_row'],
        'candidate_checks': ['already_dualwrites_shadow', 'must_split_internal_vs_lead_notifications'],
        'cutover_status': 'needs_adapter',
        'reason': 'Mistura acompanhamento/avisos e registros; precisa separar notificações internas de envio ao lead antes do corte.',
    },
    {
        'id': 'reentry_drip',
        'name': 'Reentrada diagnóstico drip',
        'script': '/root/.hermes/scripts/zydon_reentry_diagnostic_drip_20260701.py',
        'cron_name': 'zydon-reentry-diagnostic-drip-10min',
        'wrapper': '/root/.hermes/scripts/zydon_reentry_diagnostic_drip_20260701.py',
        'risk': 'médio',
        'expected_tokens': ['safe_send_text', 'record_dispatch', 'drip'],
        'candidate_checks': ['must_verify_current_script_exists'],
        'cutover_status': 'needs_adapter',
        'reason': 'Fluxo de reentrada sensível; precisa verificar script atual e ledger antes de corte.',
    },
    {
        'id': 'dynamic_sender',
        'name': 'Disparo dinâmico central',
        'script': 'disparo_dinamico.py',
        'cron_name': 'biblioteca usada por cadência/backlogs/outros',
        'wrapper': 'importado por scripts diversos',
        'risk': 'alto',
        'expected_tokens': ['safe_send_text(', 'registrar_envio(', 'record_dispatch_shadow_from_row('],
        'candidate_checks': ['already_dualwrites_shadow', 'central_ledger'],
        'cutover_status': 'needs_adapter',
        'reason': 'É função/base compartilhada; trocar aqui muda vários fluxos de uma vez. Melhor trocar chamadores específicos primeiro.',
    },
]

IGNORE_UNKNOWN_PARTS = (
    '/tests/', '/backups/', '/controle/releases/', '/references/',
    'manual_', 'manual_dmz_',
    'disparo_primeiro_contato.py',  # legado/manual ou pausado
    'process_pending_cycle_', 'sumico_inicio_funil.py',
    'channel_panel.py', 'channel_panel_v2.py',
    'send_lead.py',
    'whatsapp_safe_send.py', 'whatsapp_dispatch_worker.py', 'whatsapp_send_orchestrator.py',
    'whatsapp_cutover_readiness.py',
)


def read(root: Path, rel: str) -> str:
    p = Path(rel) if str(rel).startswith('/') else root / rel
    try:
        return p.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return ''


def _contains_any(src: str, tokens= DIRECT_SEND_TOKENS) -> bool:
    return any(t in src for t in tokens)


def classify_flow(root: Path, flow: dict[str, Any]) -> dict[str, Any]:
    src = read(root, flow['script'])
    present = bool(src)
    found = [t for t in flow.get('expected_tokens', []) if t in src]
    missing = [t for t in flow.get('expected_tokens', []) if t not in src]
    direct = _contains_any(src)
    shadow = 'record_dispatch_shadow' in src or 'enqueue_dispatch' in src or 'enqueue_intent' in src
    checks = list(flow.get('candidate_checks', []))
    status = flow['cutover_status']
    blockers = []
    if not present:
        status = 'missing_script'
        blockers.append('script_not_found')
    if direct and not shadow and flow['id'] not in {'reentry_drip'}:
        status = 'needs_dualwrite'
        blockers.append('direct_send_without_shadow')
    if flow['id'] == 'agenda_queue' and missing:
        status = 'needs_adapter'
        blockers.append('agenda_expected_tokens_missing')
    if flow['id'] != 'agenda_queue' and flow['cutover_status'] != 'candidate':
        blockers.append(flow['reason'])
    return {
        'id': flow['id'],
        'name': flow['name'],
        'script': flow['script'],
        'cron_name': flow['cron_name'],
        'wrapper': flow['wrapper'],
        'risk': flow['risk'],
        'direct_send': direct,
        'shadow_dualwrite': shadow,
        'checks': checks,
        'found_tokens': found,
        'missing_tokens': missing,
        'cutover_status': status,
        'blockers': blockers,
        'reason': flow['reason'],
    }


def find_unknown_direct_senders(root: Path, known_scripts: set[str]) -> list[str]:
    out = []
    for p in list(root.glob('*.py')) + list((root / 'scripts').glob('*.py')):
        rel = str(p.relative_to(root))
        marker = '/' + rel
        if rel in known_scripts:
            continue
        if any(part in marker for part in IGNORE_UNKNOWN_PARTS) or any(part in rel for part in IGNORE_UNKNOWN_PARTS):
            continue
        src = p.read_text(encoding='utf-8', errors='ignore')
        if _contains_any(src):
            out.append(rel)
    return sorted(out)


def build_cutover_report(root: str | Path = Path('/root/.hermes/zydon-prospeccao')) -> dict[str, Any]:
    root = Path(root)
    flows = [classify_flow(root, f) for f in FLOW_DEFS]
    known = {f['script'] for f in FLOW_DEFS}
    unknown = find_unknown_direct_senders(root, known)
    recommended = [
        {'order': 1, 'flow_id': 'agenda_queue', 'action': 'trocar primeiro para worker_owned com lote pequeno; manter lead_replied_after e marcar done antes de worker'},
        {'order': 2, 'flow_id': 'non_mql', 'action': 'criar adapter para retry de telefone alternativo; depois corte limitado'},
        {'order': 3, 'flow_id': 'followup_parallel', 'action': 'migrar uma lane/SDR por vez; limitar volume; preservar sequência'},
        {'order': 4, 'flow_id': 'reentry_drip', 'action': 'validar script atual e dedupe por reconversão antes de corte'},
        {'order': 5, 'flow_id': 'diagnostic_mql', 'action': 'separar mídia/PDF e envio interno antes de worker'},
        {'order': 6, 'flow_id': 'dynamic_sender', 'action': 'não trocar central direto; trocar chamadores primeiro'},
    ]
    return {
        'ok': not unknown,
        'flows': flows,
        'unknown_direct_senders': unknown,
        'recommended_cutover_order': recommended,
        'summary': {
            'total_flows': len(flows),
            'candidates': sum(1 for f in flows if f['cutover_status'] == 'candidate'),
            'needs_adapter': sum(1 for f in flows if f['cutover_status'] == 'needs_adapter'),
            'missing_script': sum(1 for f in flows if f['cutover_status'] == 'missing_script'),
            'unknown_direct_senders': len(unknown),
        },
    }


if __name__ == '__main__':
    print(json.dumps(build_cutover_report(), ensure_ascii=False, indent=2, sort_keys=True))
