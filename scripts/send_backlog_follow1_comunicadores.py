#!/usr/bin/env python3
"""One-off/manual: limpa backlog antigo de Primeiro Contato usando comunicadores.

Filtro intencional Rafael 26/06:
- somente tentativa 1 sem D0 real já vencida há >2 dias;
- comunicadores 4600/4606/4607/4609/4610 em round-robin;
- inclui telefone do SDR dono;
- SDRs ficam para Lead Sem Contato e follows 2+.
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path('/root/.hermes/zydon-prospeccao')
sys.path.insert(0, str(ROOT / 'scripts'))
import cadencia_primeiro_contato as c  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--send', action='store_true')
    ap.add_argument('--limit', type=int, default=75)
    ap.add_argument('--sleep-seconds', type=float, default=10)
    ap.add_argument('--min-age-days', type=float, default=2.0)
    ap.add_argument('--max-per-port-day', type=int, default=25)
    ap.add_argument('--max-per-port-hour', type=int, default=25)
    args = ap.parse_args()

    if args.send and not c.acquire_global_send_lock(blocking=False):
        print('Lock global ocupado; abortando para não sobrepor envios.')
        return 0

    candidates, _, stats, blocked = c.collect_candidates(move_interacted=bool(args.send))
    backlog = [
        x for x in candidates
        if int(x.get('next_attempt') or 1) == 1 and float(x.get('days_since_first') or 0) > args.min_age_days
    ]
    # Mais antigos primeiro para limpar backlog real.
    backlog.sort(key=lambda x: float(x.get('days_since_first') or 0), reverse=True)

    print('BACKLOG FOLLOW1 COMUNICADORES', datetime.now().isoformat())
    print('Stats:', json.dumps(stats, ensure_ascii=False))
    print(f'Backlog elegível >{args.min_age_days}d: {len(backlog)} | limite={args.limit}')
    if blocked:
        print('Bloqueados/interagidos:', json.dumps(blocked[:5], ensure_ascii=False))

    if not args.send:
        pool = c.active_communicator_senders(None)
        for i, lead in enumerate(backlog[:args.limit], 1):
            sender = pool[(i - 1) % len(pool)] if pool else None
            text = c.extract_message_variation(lead, 1, sender)
            print(f"\n[{i}] {lead['owner_name']} D+{lead['days_since_first']} via {(sender or {}).get('sender_name')} -> {lead['empresa']} {lead['tel_fmt']}")
            print(text)
        return 0

    sent = failed = skipped = 0
    disabled_ports = set()
    envios = c.d.load_envios()
    rr = 0
    for lead in backlog[:args.limit]:
        sender, errors = c.choose_sender_for_lead(
            lead,
            envios,
            use_communicators=True,
            communicator_ports=[4600, 4606, 4607, 4609, 4610],
            rr_index=rr,
            disabled_ports=disabled_ports,
        )
        rr += 1
        if not sender or not sender.get('is_communicator'):
            skipped += 1
            print(f"PULADO sem comunicador saudável: {lead['empresa']} errors={errors}")
            continue
        port = sender['port']
        fresh_envios = c.d.load_envios()
        fresh_related = c.envios_for_phone(fresh_envios, c.normalize_jid_phone(lead['jid']))
        fresh_attempt_count = len([r for r in fresh_related if str(r.get('msg_type') or '').lower() != c.NURTURE_MSG_TYPE])
        if fresh_attempt_count >= 1:
            skipped += 1
            print(f"PULADO ledger recente: {lead['empresa']} {lead['tel_fmt']} já tem tentativa registrada")
            continue
        port_ok, port_reason = c.d.port_within_external_limits(
            fresh_envios, port, max_per_hour=args.max_per_port_hour, max_per_day=args.max_per_port_day
        )
        if not port_ok:
            skipped += 1
            print(f"PULADO limite chip {port}: {port_reason} | {lead['empresa']}")
            continue
        text = c.extract_message_variation(lead, 1, sender)
        print(f"ENVIANDO backlog [{sent+1}] {lead['owner_name']} via {sender['sender_name']} porta {port} -> {lead['empresa']} {lead['tel_fmt']}")
        ok, resp = c.d.send_whatsapp(port, lead['jid'], text)
        if not ok:
            failed += 1
            disabled_ports.add(port)
            print(f"FALHA porta {port}: {resp}")
            continue
        task_id = c.create_cadence_task(lead, text, 1, {'sender_name': sender['sender_name'], 'port': port}, send_resp=resp)
        c.move_deal_stage(lead['deal_id'], c.STAGE_PRIMEIRO_CONTATO)
        sent_at = c.now_brt()
        registro = {
            'date': sent_at.strftime('%Y-%m-%d %H:%M:%S'),
            'date_tz': sent_at.isoformat(),
            'to': lead['jid'],
            'nome': lead['nome'],
            'empresa': lead['empresa'],
            'slug': c.d.slugify(lead['empresa']),
            'sdr': lead['owner_name'],
            'sender_name': sender['sender_name'],
            'sender_phone': sender.get('sender_phone') or '',
            'sender_is_communicator': True,
            'bridge_port': port,
            'text': text,
            'text_status': 'ok',
            'msg_type': c.CADENCE_MSG_TYPE,
            'attempt_number': 1,
            'campaign_id': 'backlog_follow1_comunicadores_2026_06_26',
            'deal_id': lead['deal_id'],
            'contact_id': lead['contact_id'],
            'task_id': task_id,
            'send_response': resp,
        }
        envios = c.d.registrar_envio(registro)
        c.append_metric({**lead, 'event': 'backlog_follow1_comunicador_sent', 'attempt_number': 1, 'task_id': task_id, 'bridge_port': port, 'date_tz': sent_at.isoformat()})
        sent += 1
        print(f"OK enviado | task={task_id} | resp={resp}")
        if args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)
    print(f"RESUMO backlog_comunicadores enviados={sent} falhas={failed} pulados={skipped}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
