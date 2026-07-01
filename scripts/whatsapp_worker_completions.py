#!/usr/bin/env python3
"""Completion hooks para disparos executados pelo worker WhatsApp.

Mantém o processo de origem consistente somente depois do envio real confirmado.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path('/root/.hermes/zydon-prospeccao')
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / 'scripts') not in sys.path:
    sys.path.insert(0, str(ROOT / 'scripts'))

from zydon_operational_queues import normalize_envios, update_json_locked  # noqa: E402
from whatsapp_send_orchestrator import enrich_legacy_row  # noqa: E402
import process_gate_once as p  # noqa: E402

AGENDA_QUEUE = ROOT / 'controle/agenda_queue.json'
WPP = ROOT / 'controle/wpp_envios.json'


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def _save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def _now_iso() -> str:
    return datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat()


def _now_brt() -> str:
    return datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%Y-%m-%d %H:%M')


def _complete_agenda_queue(row: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    key = row.get('agenda_queue_key')
    if not key:
        return {'ok': False, 'reason': 'missing_agenda_queue_key'}
    data = _load(AGENDA_QUEUE, {'items': []})
    items = data.get('items', []) if isinstance(data, dict) else []
    target = None
    for it in items:
        if isinstance(it, dict) and it.get('key') == key:
            target = it
            break
    if target is None:
        return {'ok': False, 'reason': 'agenda_item_not_found', 'agenda_queue_key': key}
    if target.get('status') == 'done':
        return {'ok': True, 'already_done': True, 'agenda_queue_key': key}

    res = {'response': response, 'attempts': [{'response': response, 'via': 'dispatch_worker'}]}
    target['status'] = 'done'
    target['result'] = res
    target['done_at'] = _now_iso()
    target['worker_completed_at'] = target['done_at']
    target['worker_response'] = response
    _save(AGENDA_QUEUE, {'items': items})

    email = target.get('email')
    slug = target.get('slug')
    jid = target.get('jid') or row.get('jid')
    port = target.get('port') or row.get('port')

    def upd(raw):
        data = normalize_envios(raw)
        envios = data.setdefault('envios', [])
        for existing in reversed(envios):
            if not isinstance(existing, dict) or existing.get('status') != 'enviado_lead':
                continue
            if email and existing.get('email') != email:
                continue
            if slug and existing.get('slug') != slug:
                continue
            if jid and existing.get('to') != jid:
                continue
            if port and str(existing.get('bridge_port')) != str(port):
                continue
            existing['agenda_pending'] = False
            existing['agenda_response'] = res
            existing['agenda_done_at'] = target['done_at']
            break
        envios.append(enrich_legacy_row({
            'date': _now_brt(),
            'email': email,
            'slug': slug,
            'status': 'agenda_followup_done',
            'to': jid,
            'bridge_port': port,
            'agenda_queue_key': key,
            'agenda_response': res,
        }, nature='diagnostic_agenda_invite', origin='cron_agenda_queue', thread_state='scheduled_meeting', owner_uid=target.get('owner_id') or row.get('owner_uid')))
        return data

    update_json_locked(WPP, {'envios': []}, upd)
    return {'ok': True, 'agenda_queue_key': key, 'status': 'done'}


def create_non_mql_task(row: dict[str, Any], msg: str, response: dict[str, Any]) -> str | None:
    task_body = (
        f"Tratativa Não-MQL legítimo enviada para {row.get('jid')} pela porta {row.get('port')} ({row.get('sender_name') or row.get('sender_role') or ''}).\n\n"
        f"Mensagem:\n{msg}\n\n"
        f"Motivo interno da não qualificação:\n{row.get('reason') or ''}"
    )
    return p.create_task(row.get('contact_id'), row.get('deals') or [], 'WhatsApp — tratativa lead legítimo, mas não-MQL', task_body, None)


def _complete_non_mql(row: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    msg = row.get('text') or ''
    task_id = None
    task_error = None
    try:
        task_id = create_non_mql_task(row, msg, response)
    except Exception as exc:
        task_error = str(exc)[:500]

    entry = enrich_legacy_row({
        'date': _now_brt(),
        'date_tz': _now_iso(),
        'email': row.get('email'),
        'contact_id': row.get('contact_id'),
        'slug': row.get('slug'),
        'empresa': row.get('empresa'),
        'phone': row.get('phone'),
        'to': response.get('to') or response.get('jid') or row.get('jid'),
        'bridge_port': row.get('port'),
        'sender_name': row.get('sender_name') or row.get('sender_role'),
        'campaign_id': row.get('campaign_id') or 'nao_mql_legitimo_tratativa',
        'msg_type': row.get('msg_type') or row.get('campaign_id') or 'nao_mql_legitimo_tratativa',
        'status': 'enviado_nao_mql_legitimo',
        'text': msg,
        'messageId': response.get('messageId') or response.get('id'),
        'send_status': response.get('status'),
        'response': response,
        'task_id': task_id,
        'task_error': task_error,
        'note': 'Ledger salvo por completion do whatsapp_dispatch_worker após envio worker_owned.',
    }, nature='non_mql_outreach', origin='cron_non_mql_legit_outreach', thread_state='cold_outreach', owner_uid=row.get('owner_uid') or row.get('sender_name'))

    def upd(raw):
        data = normalize_envios(raw)
        envios = data.setdefault('envios', [])
        envios.append(entry)
        return data

    update_json_locked(WPP, {'envios': []}, upd)
    return {'ok': True, 'status': 'done', 'task_id': task_id, 'task_error': task_error}


def _complete_first_contact(row: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    msg = row.get('text') or ''
    task_id = None
    task_error = None
    move_stage = None
    move_error = None
    try:
        import disparo_dinamico as dd  # noqa: WPS433 - completion reutiliza contrato legado
        task_id = dd.create_hubspot_task(
            row.get('deal_id'), row.get('contact_id'), row.get('owner_id'), row.get('owner_name') or row.get('owner_uid') or '',
            row.get('lead_name') or row.get('nome') or 'lead', row.get('tel_fmt') or row.get('phone') or row.get('jid'),
            bridge_port=row.get('port'), sender_phone=row.get('sender_phone'), sender_label=row.get('sender_name') or row.get('sender_role'),
            message_id=response.get('messageId') or response.get('id'),
        )
    except Exception as exc:
        task_error = str(exc)[:500]
    try:
        import disparo_dinamico as dd  # noqa: WPS433
        if row.get('deal_id'):
            moved = dd.hs_request(
                f"https://api.hubapi.com/crm/v3/objects/deals/{row.get('deal_id')}",
                'PATCH',
                {'properties': {'dealstage': dd.STAGE_PRIMEIRO_CONTATO}},
            )
            move_stage = ((moved or {}).get('properties') or {}).get('dealstage')
    except Exception as exc:
        move_error = str(exc)[:500]

    sent_at = _now_iso()
    entry = enrich_legacy_row({
        'date': _now_brt(),
        'date_tz': sent_at,
        'to': response.get('to') or row.get('jid'),
        'slug': row.get('slug'),
        'nome': row.get('lead_name') or row.get('nome'),
        'sdr': row.get('owner_name') or row.get('owner_uid'),
        'sender_name': row.get('sender_name') or row.get('sender_role'),
        'sender_phone': row.get('sender_phone'),
        'bridge_port': row.get('port'),
        'text': msg,
        'text_status': 'ok',
        'messageId': response.get('messageId') or response.get('id'),
        'send_response': response,
        'empresa': row.get('empresa'),
        'msg_type': row.get('msg_type') or 'primeiro_contato',
        'attempt_number': row.get('attempt_number') or 1,
        'campaign_id': row.get('campaign_id') or 'lead_sem_contato_follow1',
        'deal_id': row.get('deal_id'),
        'contact_id': row.get('contact_id'),
        'task_id': task_id,
        'task_error': task_error,
        'moved_stage': move_stage,
        'move_error': move_error,
        'note': 'Ledger salvo por completion do whatsapp_dispatch_worker após envio worker_owned.',
    }, nature='first_contact', origin='lead_sem_contato_follow1', thread_state='cold_outreach', owner_uid=row.get('owner_uid') or row.get('owner_name'))

    def upd(raw):
        data = normalize_envios(raw)
        data.setdefault('envios', []).append(entry)
        return data

    update_json_locked(WPP, {'envios': []}, upd)
    return {'ok': True, 'status': 'done', 'task_id': task_id, 'task_error': task_error, 'moved_stage': move_stage, 'move_error': move_error}


def create_cadence_task(row: dict[str, Any], msg: str, response: dict[str, Any]) -> str | None:
    import cadencia_primeiro_contato as cad  # noqa: WPS433
    lead = {
        'deal_id': row.get('deal_id'),
        'contact_id': row.get('contact_id'),
        'nome': row.get('lead_name') or row.get('nome'),
        'empresa': row.get('empresa'),
        'jid': row.get('jid'),
        'owner_id': row.get('owner_id'),
        'owner_name': row.get('owner_name') or row.get('owner_uid'),
    }
    sender = {'sender_name': row.get('sender_name') or row.get('sender_role'), 'port': row.get('port')}
    return cad.create_cadence_task(lead, msg, int(row.get('attempt_number') or 1), sender, send_resp=response)


def move_cadence_deal_if_needed(row: dict[str, Any]) -> str | None:
    if int(row.get('attempt_number') or 0) != 1:
        return None
    import cadencia_primeiro_contato as cad  # noqa: WPS433
    moved = cad.move_deal_stage(row.get('deal_id'), cad.STAGE_PRIMEIRO_CONTATO)
    return ((moved or {}).get('properties') or {}).get('dealstage')


def _complete_followup_cadence(row: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    msg = row.get('text') or ''
    task_id = None
    task_error = None
    move_stage = None
    move_error = None
    try:
        task_id = create_cadence_task(row, msg, response)
    except Exception as exc:
        task_error = str(exc)[:500]
    try:
        move_stage = move_cadence_deal_if_needed(row)
    except Exception as exc:
        move_error = str(exc)[:500]

    sent_at = _now_iso()
    attempt = int(row.get('attempt_number') or 1)
    entry = enrich_legacy_row({
        'date': _now_brt(),
        'date_tz': sent_at,
        'to': response.get('to') or response.get('jid') or row.get('jid'),
        'nome': row.get('lead_name') or row.get('nome'),
        'empresa': row.get('empresa'),
        'slug': row.get('slug'),
        'sdr': row.get('owner_name') or row.get('owner_uid'),
        'sender_name': row.get('sender_name') or row.get('sender_role'),
        'sender_phone': row.get('sender_phone'),
        'sender_is_communicator': bool(row.get('sender_is_communicator')),
        'bridge_port': row.get('port'),
        'text': msg,
        'text_status': 'ok',
        'msg_type': row.get('msg_type') or 'primeiro_contato_cadencia',
        'attempt_number': attempt,
        'campaign_id': row.get('campaign_id') or 'cadencia_primeiro_contato_sem_resposta',
        'deal_id': row.get('deal_id'),
        'contact_id': row.get('contact_id'),
        'task_id': task_id,
        'task_error': task_error,
        'messageId': response.get('messageId') or response.get('id'),
        'send_response': response,
        'moved_stage': move_stage,
        'move_error': move_error,
        'note': 'Ledger salvo por completion do whatsapp_dispatch_worker após envio worker_owned.',
    }, nature=f'followup_f{attempt}', origin='cron_cadencia_primeiro_contato', thread_state='cold_outreach', owner_uid=row.get('owner_uid') or row.get('owner_key') or row.get('owner_name'))

    def upd(raw):
        data = normalize_envios(raw)
        data.setdefault('envios', []).append(entry)
        return data

    update_json_locked(WPP, {'envios': []}, upd)
    return {'ok': True, 'status': 'done', 'task_id': task_id, 'task_error': task_error, 'moved_stage': move_stage, 'move_error': move_error}


def _response_for_part(response: dict[str, Any], index: int, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    responses = response.get('responses') or []
    if isinstance(responses, list) and len(responses) >= index:
        item = responses[index - 1]
        if isinstance(item, dict):
            nested = item.get('response')
            if isinstance(nested, dict):
                return nested
            return item
    mids = response.get('messageIds') or []
    if isinstance(mids, list) and len(mids) >= index:
        return {'messageId': mids[index - 1]}
    return dict(fallback or response or {})


def _complete_diagnostic_bundle(row: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    text_resp = row.get('text_response') if isinstance(row.get('text_response'), dict) else _response_for_part(response, 1)
    file_resp = row.get('file_response') if isinstance(row.get('file_response'), dict) else _response_for_part(response, 2)
    question_resp = row.get('question_response') if isinstance(row.get('question_response'), dict) else _response_for_part(response, 3, response)
    sent_at = _now_iso()
    agenda_key = row.get('agenda_queue_key') or f"agenda:{row.get('email')}:{row.get('slug')}:{row.get('port')}:{row.get('jid')}"
    entry = enrich_legacy_row({
        'date': _now_brt(),
        'date_tz': sent_at,
        'email': row.get('email'),
        'contact_id': row.get('contact_id'),
        'deal_id': row.get('deal_id'),
        'slug': row.get('slug'),
        'empresa': row.get('empresa') or row.get('company'),
        'phone': row.get('phone'),
        'status': 'enviado_lead',
        'to': response.get('to') or row.get('jid'),
        'bridge_port': row.get('port'),
        'owner_id': row.get('owner_id'),
        'sender_name': row.get('sender_name') or row.get('sender_role') or row.get('owner_name'),
        'text': row.get('text') or '',
        'question_text': row.get('question_text') or p.MQL_INTENT_QUESTION_FIXED,
        'agenda_text': row.get('agenda_text'),
        'cadence': row.get('cadence') or {
            'text_to_pdf_seconds': p.TEXT_TO_PDF_DELAY_SECONDS,
            'pdf_to_question_seconds': p.PDF_TO_QUESTION_DELAY_SECONDS,
            'question_to_agenda_seconds': p.QUESTION_TO_AGENDA_DELAY_SECONDS,
        },
        'pdf_path': row.get('pdf_path'),
        'hubspot_file_id': row.get('hubspot_file_id'),
        'hubspot_file_error': row.get('hubspot_file_error'),
        'text_response': text_resp,
        'file_response': file_resp,
        'question_response': question_resp,
        'messageId': question_resp.get('messageId') or question_resp.get('id') or response.get('messageId'),
        'send_response': response,
        'agenda_pending': True,
        'agenda_response': None,
        'question_sent_at': row.get('question_sent_at') or sent_at,
        'group_summary': row.get('group_summary'),
        'group_summary_response': row.get('group_summary_response'),
        'task_id': row.get('task_id'),
        'completion_type': 'diagnostic_bundle',
        'note': 'Ledger salvo por completion do whatsapp_dispatch_worker após envio worker_owned.',
    }, nature='diagnostic_bundle', origin='cron_mql_diagnostic_pipeline', thread_state='post_diagnostic', owner_uid=row.get('owner_id') or row.get('owner_uid') or row.get('owner_name'))

    def upd(raw):
        data = normalize_envios(raw)
        data.setdefault('envios', []).append(entry)
        return data

    update_json_locked(WPP, {'envios': []}, upd)

    reentry_updated = False
    if row.get('reentry_queue_path'):
        path = Path(str(row.get('reentry_queue_path')))
        data = _load(path, None)
        items = data.get('items', []) if isinstance(data, dict) else []
        target = next((it for it in items if _reentry_item_matches(it, row)), None)
        if target and target.get('status') != 'sent':
            target['status'] = 'sent'
            target['worker_owned_dispatch_id'] = row.get('dispatch_id')
            target['worker_completed_at'] = sent_at
            target['worker_message_id'] = question_resp.get('messageId') or question_resp.get('id') or response.get('messageId')
            target['worker_bridge_port'] = row.get('port')
            target['result'] = {
                'status': 'sent',
                'via': 'whatsapp_dispatch_worker',
                'completion_type': 'diagnostic_bundle',
                'text_message_id': text_resp.get('messageId') or text_resp.get('id'),
                'file_message_id': file_resp.get('messageId') or file_resp.get('id'),
                'question_message_id': question_resp.get('messageId') or question_resp.get('id'),
                'bridge_port': row.get('port'),
            }
            _save(path, data if isinstance(data, dict) else {'items': items})
            reentry_updated = True

    due_at = row.get('agenda_due_at_epoch')
    try:
        due_at = float(due_at) if due_at is not None else None
    except Exception:
        due_at = None
    if due_at is None:
        import time
        due_at = time.time() + p.QUESTION_TO_AGENDA_DELAY_SECONDS
    agenda_item = {
        'key': agenda_key,
        'email': row.get('email'),
        'slug': row.get('slug'),
        'company': row.get('empresa') or row.get('company'),
        'contact_id': row.get('contact_id'),
        'port': row.get('port'),
        'jid': row.get('jid'),
        'text': row.get('agenda_text'),
        'due_at': due_at,
        'due_at_iso': row.get('agenda_due_at_iso'),
        'question_sent_at': row.get('question_sent_at') or sent_at,
        'question_message_id': question_resp.get('messageId') or question_resp.get('id'),
        'source': 'whatsapp_dispatch_worker',
        'status': 'pending',
        'created_at': sent_at,
    }
    data = _load(AGENDA_QUEUE, {'items': []})
    if not isinstance(data, dict):
        data = {'items': []}
    items = data.setdefault('items', [])
    existing = next((it for it in items if isinstance(it, dict) and it.get('key') == agenda_key and it.get('status') == 'pending'), None)
    if existing:
        existing.update({k: v for k, v in agenda_item.items() if v not in (None, '')})
    else:
        items.append(agenda_item)
    _save(AGENDA_QUEUE, data)
    return {'ok': True, 'status': 'done', 'agenda_queue_key': agenda_key, 'task_id': row.get('task_id'), 'reentry_item_updated': reentry_updated}


def _reentry_item_matches(item: dict[str, Any], row: dict[str, Any]) -> bool:
    """Casa a linha de disparo com o item da fila reentry sem depender de e-mail sozinho.

    Prioriza o dispatch_id gravado no item no momento do enfileiramento; cai para
    deal/contact/email só quando o item ainda não conhece o dispatch (compat).
    """
    if not isinstance(item, dict):
        return False
    did = str(row.get('dispatch_id') or '')
    if did and str(item.get('worker_owned_dispatch_id') or '') == did:
        return True
    if str(item.get('worker_owned_dispatch_id') or ''):
        # item já amarrado a outro dispatch; não sequestrar por e-mail
        return False
    deal = str(row.get('deal_id') or '')
    contact = str(row.get('contact_id') or '')
    email = str(row.get('email') or '').lower()
    if deal and str(item.get('deal_id') or '') == deal:
        return True
    if contact and str(item.get('contact_id') or '') == contact:
        return True
    if email and str(item.get('email') or '').lower() == email:
        return True
    return False


def _complete_reentry_diagnostic(row: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    """Fecha o item da fila reentry depois do envio real worker_owned.

    Idempotente: se o item já está `sent`, não reescreve. Além de atualizar a
    fila de reinscrição (origem operacional), grava uma linha real no ledger para
    que dedupe/histórico enxerguem o disparo como mensagem real do lead.
    """
    queue_path = row.get('reentry_queue_path')
    updated_item = False
    already = False
    reason = None
    if queue_path:
        path = Path(str(queue_path))
        data = _load(path, None)
        items = data.get('items', []) if isinstance(data, dict) else []
        target = next((it for it in items if _reentry_item_matches(it, row)), None)
        if target is None:
            reason = 'reentry_item_not_found'
        elif target.get('status') == 'sent':
            already = True
        else:
            target['status'] = 'sent'
            target['worker_owned_dispatch_id'] = row.get('dispatch_id')
            target['worker_completed_at'] = _now_iso()
            target['worker_message_id'] = response.get('messageId') or response.get('id')
            target['worker_bridge_port'] = row.get('port')
            target.setdefault('result', {})
            if isinstance(target['result'], dict):
                target['result'].update({'status': 'sent', 'via': 'whatsapp_dispatch_worker',
                                         'bridge_port': row.get('port'),
                                         'messageId': target['worker_message_id']})
            _save(path, data if isinstance(data, dict) else {'items': items})
            updated_item = True
    else:
        reason = 'missing_reentry_queue_path'

    entry = enrich_legacy_row({
        'date': _now_brt(),
        'date_tz': _now_iso(),
        'email': row.get('email'),
        'contact_id': row.get('contact_id'),
        'deal_id': row.get('deal_id'),
        'slug': row.get('slug'),
        'empresa': row.get('empresa') or row.get('company'),
        'phone': row.get('phone'),
        'status': 'enviado_lead',
        'to': response.get('to') or row.get('jid'),
        'bridge_port': row.get('port'),
        'sender_name': row.get('sender_name') or row.get('sender_role'),
        'text': row.get('text') or '',
        'messageId': response.get('messageId') or response.get('id'),
        'send_response': response,
        'campaign_id': row.get('campaign_id') or 'reentry_diagnostic_drip',
        'msg_type': row.get('msg_type') or 'reentry_diagnostic',
        'completion_type': 'reentry_diagnostic',
        'note': 'Ledger salvo por completion do whatsapp_dispatch_worker após envio worker_owned.',
    }, nature='reentry_diagnostic', origin='cron_reentry_diagnostic_drip', thread_state='cold_outreach',
       owner_uid=row.get('owner_uid') or row.get('owner_id') or row.get('owner_name'))

    def upd(raw):
        data = normalize_envios(raw)
        data.setdefault('envios', []).append(entry)
        return data

    update_json_locked(WPP, {'envios': []}, upd)
    return {'ok': True, 'status': 'done', 'reentry_item_updated': updated_item,
            'already_done': already, 'reason': reason}


def complete_after_send(row: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    row = row or {}
    if row.get('completion_type') == 'agenda_queue':
        return _complete_agenda_queue(row, response or {})
    if row.get('completion_type') == 'non_mql':
        return _complete_non_mql(row, response or {})
    if row.get('completion_type') == 'first_contact':
        return _complete_first_contact(row, response or {})
    if row.get('completion_type') == 'followup_cadence':
        return _complete_followup_cadence(row, response or {})
    if row.get('completion_type') == 'diagnostic_bundle':
        return _complete_diagnostic_bundle(row, response or {})
    if row.get('completion_type') == 'reentry_diagnostic':
        return _complete_reentry_diagnostic(row, response or {})
    return {'ok': True, 'skipped': True, 'reason': 'no_completion_hook'}
