#!/usr/bin/env python3
import contextlib
import io
import importlib.util
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path('/root/.hermes/zydon-prospeccao')
spec = importlib.util.spec_from_file_location('d', ROOT / 'disparo_dinamico.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
bspec = importlib.util.spec_from_file_location('backlog', ROOT / 'scripts/disparo_backlog_institucional.py')
backlog = importlib.util.module_from_spec(bspec)
bspec.loader.exec_module(backlog)

AUTHORIZED_SENDERS = [
    {'port': 4607, 'sender_name': 'Rafael', 'remetente': 'o Rafael', 'expected': 'Rafael Calixto'},
    {'port': 4600, 'sender_name': 'Mariana', 'remetente': 'a Mariana', 'expected': 'Mariana | Zydon'},
    {'port': 4606, 'sender_name': 'Lucas Resende', 'remetente': 'o Lucas Resende', 'expected': 'Lucas Resende'},
    {'port': 4609, 'sender_name': 'João Pedro', 'remetente': 'o João Pedro', 'expected': 'João Pedro'},
    {'port': 4610, 'sender_name': 'Gustavo', 'remetente': 'o Gustavo', 'expected': 'Gustavo'},
]
OWNER_NAMES = {v['owner_id']: v['owner_name'] for v in d.BRIDGES.values()}
OWNER_NAMES.update({'76764091': 'Owner antigo 76764091', '88063746': 'Owner antigo 88063746', 'SEM_OWNER': 'Sem owner'})


def all_initial_deals():
    url = 'https://api.hubapi.com/crm/v3/objects/deals/search'
    body = {
        'filterGroups': [{'filters': [
            {'propertyName': 'pipeline', 'operator': 'EQ', 'value': d.PIPELINE},
            {'propertyName': 'dealstage', 'operator': 'IN', 'values': d.FIRST_5_STAGES},
        ]}],
        'properties': ['dealname', 'dealstage', 'hubspot_owner_id', 'createdate'],
        'limit': 100,
        'sorts': [{'propertyName': 'createdate', 'direction': 'DESCENDING'}],
    }
    out, after = [], None
    while True:
        if after:
            body['after'] = after
        else:
            body.pop('after', None)
        res = d.hs_request(url, 'POST', body)
        if not res:
            raise SystemExit('erro ao buscar deals')
        out.extend(res.get('results', []))
        after = (res.get('paging') or {}).get('next', {}).get('after')
        if not after:
            return out


def sent_records_by_phone():
    arr = d.load_envios()
    by = {}
    for r in arr:
        if not isinstance(r, dict):
            continue
        for f in ('to', 'jid', 'lead_jid', 'tel', 'telefone'):
            val = r.get(f)
            if not val or str(val).lower() == 'grupo' or '@g.us' in str(val):
                continue
            k = d.normalize_phone(val)
            if k:
                by.setdefault(k, []).append(r)
    return by


def existing_task_subjects(deal_id):
    assoc = d.ler_assoc_deals_objetos([str(deal_id)], 'tasks')
    if not assoc:
        return []
    tids = assoc.get(str(deal_id), [])
    props = d.buscar_tasks_props(tids)
    if props is None:
        return None
    return [str((props.get(str(tid), {}) or {}).get('hs_task_subject') or '') for tid in tids]


def create_activity_task(lead, records):
    subjects = existing_task_subjects(lead['deal_id'])
    if subjects is None:
        return None, 'erro_ler_tasks'
    if any('WhatsApp — atividade relevante registrada' in s for s in subjects):
        return None, 'ja_existia'
    last = records[-1] if records else {}
    sender = last.get('sender_name') or last.get('sdr') or last.get('owner_id') or 'automação Zydon'
    subject = f"WhatsApp — atividade relevante registrada ({sender})"
    body_txt = (
        "Registro criado para refletir no HubSpot que o lead já recebeu WhatsApp direto por automação/Zydon.\n\n"
        f"Deal: {lead['empresa']} ({lead['deal_id']})\n"
        f"Contato: {lead['nome']} ({lead['contact_id']})\n"
        f"Destino: {lead['jid']}\n"
        f"Último remetente/porta: {sender} / {last.get('bridge_port')}\n"
        f"Último tipo: {last.get('msg_type') or last.get('status')}\n"
        f"Última data: {last.get('date') or last.get('date_tz') or last.get('ts')}\n\n"
        "Motivo: negócio aparecia como sem atividade relevante, mas já havia envio WhatsApp registrado no controle wpp_envios."
    )
    body = {
        'properties': {
            'hs_timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'hs_task_subject': subject,
            'hs_task_body': body_txt,
            'hs_task_status': 'COMPLETED',
            'hs_task_priority': 'MEDIUM',
            'hubspot_owner_id': lead['owner_id'] if lead['owner_id'] != 'SEM_OWNER' else None,
        },
        'associations': [
            {'to': {'id': int(lead['contact_id'])}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 204}]},
            {'to': {'id': int(lead['deal_id'])}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 216}]},
        ],
    }
    # remove None owner if needed
    if body['properties']['hubspot_owner_id'] is None:
        del body['properties']['hubspot_owner_id']
    res = d.hs_request('https://api.hubapi.com/crm/v3/objects/tasks', 'POST', body)
    return (res.get('id') if res else None), ('ok' if res else 'erro_criar')


def collect_targets():
    deals = all_initial_deals()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ids = d.filtrar_deals_sem_atividade_valida(deals)
    sent_by_phone = sent_records_by_phone()
    sent_targets, pending_targets = [], []
    now = datetime.now(timezone.utc)
    for deal in deals:
        did = str(deal['id'])
        props = deal.get('properties') or {}
        if did not in ids:
            continue
        res = d.get_contact_for_deal(did)
        if not res:
            continue
        cid, cprops = res
        tel = d.extrair_telefone(cprops)
        if not tel:
            continue
        tel_raw, jid, fmt = tel
        k = d.normalize_phone(jid)
        owner_id = str(props.get('hubspot_owner_id') or 'SEM_OWNER')
        created = d.parse_hubspot_datetime(props.get('createdate'))
        age_h = (now - created).total_seconds() / 3600 if created else 99999
        lead = {
            'deal_id': did,
            'contact_id': str(cid),
            'owner_id': owner_id,
            'sdr_original': OWNER_NAMES.get(owner_id, owner_id),
            'nome': cprops.get('firstname') or cprops.get('name') or 'tudo bem',
            'empresa': props.get('dealname') or cprops.get('company') or 'sua empresa',
            'jid': jid,
            'tel_fmt': fmt,
            'idade_h': age_h,
            'erp': cprops.get('qual_erp_utiliza_') or cprops.get('selecione_o_sistema_de_gesto') or cprops.get('selecione_o_sistema_de_gesto_erp') or '',
        }
        if k in sent_by_phone:
            sent_targets.append((lead, sent_by_phone[k]))
        else:
            pending_targets.append(lead)
    pending_targets.sort(key=lambda x: x['idade_h'])
    return sent_targets, pending_targets


def choose_sender(i, lead=None):
    lead = lead or {}
    hour = datetime.now(timezone(timedelta(hours=-3))).hour
    dow = datetime.now(timezone(timedelta(hours=-3))).weekday()
    if dow < 5 and 7 <= hour < 18:
        owner = (lead.get('sdr_original') or '').strip().lower()
        if owner == 'lucas':
            return {'port': 4603, 'sender_name': 'Lucas Batista', 'remetente': 'Lucas Batista', 'expected': 'Lucas Batista'}
        # Sarah principal/extra varia; este script não deve improvisar institucional para Sarah em horário comercial.
        if owner == 'sarah':
            return {'port': 4601, 'sender_name': 'Sarah', 'remetente': 'a Sarah', 'expected': 'Sarah da Zydon'}
    return AUTHORIZED_SENDERS[i % len(AUTHORIZED_SENDERS)]


def main():
    sent_targets, pending_targets = collect_targets()
    print(f'Já tinham WhatsApp e precisam atividade: {len(sent_targets)}')
    created = skipped = errors = 0
    for lead, records in sent_targets:
        tid, status = create_activity_task(lead, records)
        if status == 'ok':
            created += 1
            print(f"TASK_OK {tid} | {lead['empresa']} | {lead['nome']}")
        elif status == 'ja_existia':
            skipped += 1
        else:
            errors += 1
            print(f"TASK_ERRO {status} | {lead['empresa']} | {lead['deal_id']}")
    print(f'Atividades: criadas={created} ja_existiam={skipped} erros={errors}')

    print(f'Pendentes sem WhatsApp: {len(pending_targets)}')
    sent = fail = 0
    for i, lead in enumerate(pending_targets):
        sender = choose_sender(i, lead=lead)
        text = backlog.build_message(lead, sender)
        print(f"SEND [{i+1}] {lead['empresa']} -> {sender['sender_name']}:{sender['port']} | {lead['tel_fmt']}")
        ok, resp = d.send_whatsapp(sender['port'], lead['jid'], text)
        if not ok:
            fail += 1
            print(f'  FALHA {resp}')
            continue
        tid = backlog.create_task(lead, sender, text, 'acao_pendentes_sem_atividade_2026_06_24', resp)
        registro = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'to': lead['jid'],
            'nome': lead['nome'],
            'empresa': lead['empresa'],
            'slug': d.slugify(lead['empresa']),
            'sdr_original': lead['sdr_original'],
            'sdr': lead['sdr_original'],
            'sender_name': sender['sender_name'],
            'bridge_port': sender['port'],
            'text': text,
            'text_status': 'ok',
            'msg_type': 'primeiro_contato_backlog_institucional',
            'campaign_id': 'acao_pendentes_sem_atividade_2026_06_24',
            'deal_id': lead['deal_id'],
            'contact_id': lead['contact_id'],
            'task_id': tid,
            'send_response': resp,
        }
        d.registrar_envio(registro)
        sent += 1
        print(f"  OK task={tid} resp={resp}")
    print(f'RESUMO atividades_criadas={created} atividades_existiam={skipped} atividades_erros={errors} disparos_ok={sent} disparos_falha={fail}')


if __name__ == '__main__':
    main()
