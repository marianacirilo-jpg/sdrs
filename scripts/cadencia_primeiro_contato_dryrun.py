#!/usr/bin/env python3
"""Dry-run da cadência automática para deals travados em Primeiro Contato.

NÃO envia WhatsApp e NÃO escreve no HubSpot.

Objetivo: identificar leads que receberam 1º contato, não responderam/interagiram,
e estão aptos para 2º/3º/4º contato automático com janela mínima de 24h.
Após 4 tentativas sem resposta, recomenda tirar da prioridade SDR e mandar para
nutrição/marketing.
"""
import argparse
import json
import os
import re
import unicodedata
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path('/root/.hermes/zydon-prospeccao')
WPP_ENVIOS = ROOT / 'controle' / 'wpp_envios.json'
HISTORY_DIR = Path('/root/.hermes/whatsapp-extra/channel_data')
HUBSPOT_ENV = Path('/root/.hermes/credentials/hubspot.env')
HUBSPOT_API = 'https://api.hubapi.com'
PIPELINE = '671008549'
STAGE_PRIMEIRO_CONTATO = '1214320997'
STAGE_LABELS = {
    '984052829': 'Lead Sem Contato',
    '1214320997': 'Primeiro Contato',
    '998099482': 'Retorno Contato',
    '1151853491': 'Diagnóstico SDR',
    '1269308723': 'Introdução',
    '984278846': 'Introdução',
}
OWNERS = {
    '86265630': 'Breno',
    '88063842': 'Sarah',
    '85778446': 'Lucas Batista',
}
ATTEMPT_TYPES = ('primeiro_contato','segundo_contato','terceiro_contato','quarto_contato')
CONTACT_PROPS = [
    'firstname','lastname','email','phone','mobilephone','hs_whatsapp_phone_number',
    'hs_searchable_calculated_phone_number','company','createdate','recent_conversion_date',
    'recent_conversion_event_name'
]
# Props read-only de atividades HubSpot associadas ao deal (tasks/notes).
TASK_PROPS = ['hs_task_subject','hs_task_body','hs_task_status','hs_timestamp','hs_task_type','hubspot_owner_id']
NOTE_PROPS = ['hs_note_body','hs_timestamp','hubspot_owner_id']
# Termos comerciais que caracterizam evidência de PRIMEIRO CONTATO numa atividade.
# Conservador: uma task/nota genérica sem termo comercial NÃO conta como contato.
# (texto é normalizado sem acento e em minúsculas antes da comparação)
FIRST_CONTACT_TERMS = [
    'whatsapp', 'primeiro contato', 'contato inicial', 'follow-up', 'follow up',
    'followup', 'channel', 'diagnostico enviado', 'mensagem enviada',
    'abordagem inicial', 'primeira abordagem',
]
BRT = timezone(timedelta(hours=-3))
UTC = timezone.utc


def _norm(s):
    """Minúsculas + sem acento, para casar termos de forma robusta."""
    s = unicodedata.normalize('NFKD', str(s or ''))
    return ''.join(c for c in s if not unicodedata.combining(c)).lower()


def _strip_html(s):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', str(s or ''))).strip()


def has_first_contact_term(*texts):
    blob = ' '.join(_norm(t) for t in texts if t)
    return any(term in blob for term in FIRST_CONTACT_TERMS)


def load_hubspot_token():
    token = os.environ.get('HUBSPOT_ACCESS_TOKEN') or os.environ.get('HUBSPOT_TOKEN') or ''
    if token:
        return token.strip()
    if HUBSPOT_ENV.exists():
        for line in HUBSPOT_ENV.read_text().splitlines():
            line=line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k,v=line.split('=',1)
            if k.strip() in ('HUBSPOT_ACCESS_TOKEN','HUBSPOT_TOKEN','PRIVATE_APP_TOKEN','HUBSPOT_API_KEY'):
                return v.strip().strip('"\'')
    raise SystemExit('HubSpot token não encontrado em ~/.hermes/credentials/hubspot.env')

TOKEN = load_hubspot_token()


def hs_request(method, path, payload=None, timeout=25):
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(
        HUBSPOT_API + path,
        data=data,
        headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8') or '{}')


def normalize_phone(value):
    if not value: return ''
    digits=''.join(ch for ch in str(value) if ch.isdigit())
    if digits.startswith('55') and len(digits) in (12,13):
        digits=digits[2:]
    return digits if len(digits) >= 10 else ''


def jid_variants(phone):
    p=normalize_phone(phone)
    if not p: return set()
    return {p, '55'+p, f'55{p}@s.whatsapp.net', f'55{p}@c.us'}


def parse_dt(raw):
    if not raw: return None
    if isinstance(raw, (int,float)):
        try: return datetime.fromtimestamp(float(raw), UTC)
        except Exception: return None
    s=str(raw).strip()
    # ISO com timezone explícito
    try:
        txt=s[:-1] + '+00:00' if s.endswith('Z') else s
        dt=datetime.fromisoformat(txt)
        if dt.tzinfo is None:
            dt=dt.replace(tzinfo=BRT)
        return dt.astimezone(UTC)
    except Exception:
        pass
    for fmt in ('%Y-%m-%d %H:%M:%S','%Y-%m-%d %H:%M'):
        try:
            # wpp_envios antigo de primeiro contato era UTC em alguns casos, mas registros novos têm date_tz.
            return datetime.strptime(s[:19], fmt).replace(tzinfo=BRT).astimezone(UTC)
        except Exception:
            pass
    return None


def load_envios():
    try:
        data=json.loads(WPP_ENVIOS.read_text())
    except Exception:
        return []
    if isinstance(data, dict) and isinstance(data.get('envios'), list): return data['envios']
    if isinstance(data, list): return data
    if isinstance(data, dict): return [v for v in data.values() if isinstance(v, dict)]
    return []


def envio_attempt_records(envios):
    by_deal=defaultdict(list); by_phone=defaultdict(list)
    for r in envios:
        if not isinstance(r, dict): continue
        mt=str(r.get('msg_type') or '').lower()
        if mt not in ATTEMPT_TYPES: continue
        dt=parse_dt(r.get('date_tz') or r.get('sent_at') or r.get('date') or r.get('timestamp'))
        if not dt: continue
        rec={**r, '_dt':dt, '_type':mt}
        did=str(r.get('deal_id') or r.get('dealId') or '').strip()
        if did: by_deal[did].append(rec)
        for field in ('to','jid','lead_jid','tel','telefone','phone'):
            p=normalize_phone(r.get(field))
            if p: by_phone[p].append(rec)
    for d in (by_deal, by_phone):
        for k in list(d): d[k].sort(key=lambda x:x['_dt'])
    return by_deal, by_phone


def search_deals_first_contact(limit=500):
    body={
        'filterGroups':[{'filters':[
            {'propertyName':'pipeline','operator':'EQ','value':PIPELINE},
            {'propertyName':'dealstage','operator':'EQ','value':STAGE_PRIMEIRO_CONTATO},
        ]}],
        'properties':['dealname','dealstage','hubspot_owner_id','createdate','hs_lastmodifieddate'],
        'limit':100,
        'sorts':[{'propertyName':'createdate','direction':'DESCENDING'}],
    }
    out=[]; after=None
    while True:
        if after: body['after']=after
        data=hs_request('POST','/crm/v3/objects/deals/search',body)
        out.extend(data.get('results') or [])
        if len(out)>=limit: return out[:limit]
        after=((data.get('paging') or {}).get('next') or {}).get('after')
        if not after: return out


def associated_contact(deal_id):
    try:
        assoc=hs_request('GET', f'/crm/v3/objects/deals/{deal_id}/associations/contacts')
        rows=assoc.get('results') or []
        cids=[str((r or {}).get('id') or (r or {}).get('toObjectId') or '') for r in rows]
        cids=[c for c in cids if c]
        if not cids: return '', {}
        q=''.join('&properties='+p for p in CONTACT_PROPS)
        if len(cids) == 1:
            cid=cids[0]
            c=hs_request('GET', f'/crm/v3/objects/contacts/{cid}?{q.lstrip("&")}')
            return cid, c.get('properties') or {}
        body={'properties': CONTACT_PROPS, 'inputs': [{'id': cid} for cid in cids]}
        batch=hs_request('POST', '/crm/v3/objects/contacts/batch/read', body)
        candidates=[]
        for item in batch.get('results') or []:
            cid=str(item.get('id') or '')
            p=item.get('properties') or {}
            dt=parse_dt(p.get('recent_conversion_date') or p.get('createdate'))
            candidates.append((dt.timestamp() if dt else 0, cid, p))
        if not candidates: return '', {}
        _, cid, props=max(candidates, key=lambda x: x[0])
        return cid, props
    except Exception:
        return '', {}


def contact_phone(props):
    for k in ('hs_searchable_calculated_phone_number','hs_whatsapp_phone_number','mobilephone','phone'):
        p=normalize_phone(props.get(k))
        if len(p)==11 and p[2]=='9': return p
    return ''


def incoming_after(phone, after_dt):
    if not phone or not after_dt or not HISTORY_DIR.exists(): return False
    variants=jid_variants(phone)
    for path in HISTORY_DIR.glob('history_*.json'):
        try: rows=json.loads(path.read_text())
        except Exception: continue
        if not isinstance(rows, list): continue
        for m in rows:
            if not isinstance(m, dict) or m.get('fromMe'): continue
            chat=str(m.get('chat') or m.get('remoteJid') or '')
            if not any(v and v in chat for v in variants): continue
            dt=parse_dt(m.get('timestamp'))
            if dt and dt > after_dt:
                return True
    return False


def history_messages(phone):
    """Mensagens do histórico WhatsApp local para o telefone, como (dt, fromMe).

    Lê os arquivos uma única vez por deal para derivar 'tem mensagem enviada' e
    'respondeu depois de X' sem varrer o histórico duas vezes. Read-only.
    """
    out=[]
    if not phone or not HISTORY_DIR.exists(): return out
    variants=jid_variants(phone)
    for path in HISTORY_DIR.glob('history_*.json'):
        try: rows=json.loads(path.read_text())
        except Exception: continue
        if not isinstance(rows, list): continue
        for m in rows:
            if not isinstance(m, dict): continue
            chat=str(m.get('chat') or m.get('remoteJid') or '')
            if not any(v and v in chat for v in variants): continue
            dt=parse_dt(m.get('timestamp'))
            if dt: out.append((dt, bool(m.get('fromMe'))))
    out.sort(key=lambda x:x[0])
    return out


def deal_assoc_ids(deal_id, to_obj, limit=100, timeout=25):
    """IDs de objetos (tasks/notes) associados ao deal via API v4. Read-only."""
    data=hs_request('GET', f'/crm/v4/objects/deals/{deal_id}/associations/{to_obj}?limit={limit}', timeout=timeout)
    ids=[]
    for r in (data.get('results') or []):
        tid=str(r.get('toObjectId') or r.get('id') or '')
        if tid: ids.append(tid)
    return ids


def batch_assoc_ids(from_obj, to_obj, ids, timeout=60):
    """Mapa {from_id: [to_id,...]} via batch association read v4. Read-only.

    Substitui N chamadas GET (uma por deal) por ~N/100 POSTs em lote contra
    POST /crm/v4/associations/{from}/{to}/batch/read.
    """
    result=defaultdict(list)
    for i in range(0, len(ids), 100):
        chunk=ids[i:i+100]
        body={'inputs':[{'id':x} for x in chunk]}
        data=hs_request('POST', f'/crm/v4/associations/{from_obj}/{to_obj}/batch/read', body, timeout=timeout)
        for r in (data.get('results') or []):
            fid=str((r.get('from') or {}).get('id') or '')
            if not fid: continue
            for t in (r.get('to') or []):
                tid=str(t.get('toObjectId') or t.get('id') or '')
                if tid: result[fid].append(tid)
    return result


def batch_read(obj, ids, props, timeout=25):
    """Lê em lote objetos HubSpot (tasks/notes) com props úteis. Read-only."""
    out=[]
    for i in range(0, len(ids), 100):
        chunk=ids[i:i+100]
        body={'properties':props, 'inputs':[{'id':x} for x in chunk]}
        data=hs_request('POST', f'/crm/v3/objects/{obj}/batch/read', body, timeout=timeout)
        out.extend(data.get('results') or [])
    return out


def _activity_from_task(t):
    """Normaliza um objeto task do HubSpot para o dict de atividade."""
    p=t.get('properties') or {}
    subject=p.get('hs_task_subject') or ''
    return {
        'kind':'task',
        'subject':subject,
        'body':p.get('hs_task_body') or '',
        'status':p.get('hs_task_status') or '',
        'type':p.get('hs_task_type') or 'TASK',
        'ownerId':str(p.get('hubspot_owner_id') or ''),
        'dt':parse_dt(p.get('hs_timestamp')),
        'label':subject.strip() or '(tarefa sem assunto)',
    }


def _activity_from_note(nh):
    """Normaliza um objeto note do HubSpot para o dict de atividade."""
    p=nh.get('properties') or {}
    snippet=_strip_html(p.get('hs_note_body'))[:120]
    return {
        'kind':'note',
        'subject':'',
        'body':p.get('hs_note_body') or '',
        'status':'',
        'type':'NOTE',
        'ownerId':str(p.get('hubspot_owner_id') or ''),
        'dt':parse_dt(p.get('hs_timestamp')),
        'label':snippet or '(nota sem texto)',
    }


def deal_activities(deal_id, timeout=15):
    """Atividades HubSpot (tasks + notes) de UM deal — fallback deal a deal.

    Cada item: {kind, subject, body, status, type, ownerId, dt, label}. Não
    escreve nada no HubSpot. Pode levantar exceção (tratada por deal no main).
    """
    activities=[]
    task_ids=deal_assoc_ids(deal_id, 'tasks', timeout=timeout)
    for t in batch_read('tasks', task_ids, TASK_PROPS, timeout=timeout):
        activities.append(_activity_from_task(t))
    note_ids=deal_assoc_ids(deal_id, 'notes', timeout=timeout)
    for nh in batch_read('notes', note_ids, NOTE_PROPS, timeout=timeout):
        activities.append(_activity_from_note(nh))
    return activities


def activities_by_deal(deal_ids):
    """Mapa {deal_id: [activities...]} para muitos deals de uma vez. Read-only.

    Estratégia rápida (evita ir deal a deal):
      1) batch association v4 deals->tasks e deals->notes (chunks de 100);
      2) batch read v3 de TODAS as tasks/notes únicas (chunks de 100);
      3) reconstrói por deal a partir dos mapas em memória.

    Se a associação em lote falhar, cai para o fallback deal a deal com timeout
    baixo — sem derrubar o dry-run (deals que falharem ficam sem atividades).
    """
    deal_ids=[str(d) for d in deal_ids if d]
    result={did:[] for did in deal_ids}
    if not deal_ids:
        return result
    try:
        task_map=batch_assoc_ids('deals','tasks',deal_ids)
        note_map=batch_assoc_ids('deals','notes',deal_ids)
    except Exception:
        for did in deal_ids:
            try:
                result[did]=deal_activities(did, timeout=10)
            except Exception:
                pass
        return result

    all_task_ids=sorted({tid for ids in task_map.values() for tid in ids})
    all_note_ids=sorted({nid for ids in note_map.values() for nid in ids})
    tasks_by_id={}
    for t in batch_read('tasks', all_task_ids, TASK_PROPS):
        tid=str(t.get('id') or '')
        if tid: tasks_by_id[tid]=_activity_from_task(t)
    notes_by_id={}
    for nh in batch_read('notes', all_note_ids, NOTE_PROPS):
        nid=str(nh.get('id') or '')
        if nid: notes_by_id[nid]=_activity_from_note(nh)

    for did in deal_ids:
        acts=[]
        for tid in task_map.get(did, []):
            a=tasks_by_id.get(tid)
            if a: acts.append(a)
        for nid in note_map.get(did, []):
            a=notes_by_id.get(nid)
            if a: acts.append(a)
        result[did]=acts
    return result


def bucket_for(attempts, hours_since_last):
    if attempts >= 4:
        return 'nutricao_marketing'
    if attempts <= 0:
        return 'sem_primeiro_contato_registrado'
    if hours_since_last < 24:
        return 'aguardar_24h'
    return f'dia_{attempts}_proximo_{attempts+1}contato'


# --- Saneamento do limbo de Primeiro Contato: 5 destinos operacionais ----------
# Classificação ORTOGONAL ao bucket de cadência (não substitui nem altera ele).
# Aponta o destino operacional de cada deal para sanear o limbo. Read-only:
# não envia WhatsApp, não escreve no HubSpot, não muda owner/stage.
# Os 6 buckets granulares se agrupam nos 5 destinos do mapa operacional:
#   d0_real                -> D0 real
#   reconciliar_hubspot    -> Reconciliar ledger/evidência
#   reconciliar_whatsapp   -> Reconciliar ledger/evidência
#   d0_confiavel_cadencia  -> Cadência 2º/3º/4º
#   nao_tocar_respondeu    -> Não tocar — respondeu
#   nutricao_liberar_pipe  -> Nutrição/liberar pipe
SANITATION_LABELS = {
    'd0_real': 'D0 real',
    'reconciliar_hubspot': 'D0 inferido por HubSpot',
    'reconciliar_whatsapp': 'WhatsApp no histórico sem ledger',
    'd0_confiavel_cadencia': 'D0 confiável — cadência',
    'nao_tocar_respondeu': 'Não tocar — respondeu',
    'nutricao_liberar_pipe': 'Nutrição / liberar pipe',
}
SANITATION_ACTIONS = {
    'd0_real': 'Tratar como primeiro contato, não como 2º contato',
    'reconciliar_hubspot': 'Validar/reconciliar ledger; pode entrar em cadência se evidência estiver ok',
    'reconciliar_whatsapp': 'Reconciliar histórico/ledger antes de cadência',
    'd0_confiavel_cadencia': 'Apto para próximo contato quando janela permitir',
    'nao_tocar_respondeu': 'SDR assumir conversa/Retorno Contato',
    'nutricao_liberar_pipe': 'Encerrar prioridade SDR e mandar para nutrição/material rico',
}
# Buckets que exigem checagem humana antes de qualquer cadência.
SANITATION_NEEDS_REVIEW = {'reconciliar_hubspot', 'reconciliar_whatsapp'}


def sanitation_for_row(bucket, attempt_source, evidence, responded):
    """Destino de saneamento (1 de 5) para um deal do limbo. Read-only.

    Prioridade: respondeu > nutrição > ledger confiável > inferido HubSpot >
    WhatsApp sem ledger > D0 real. Devolve sanitationBucket/Label/Action e o
    flag needsReview, sem tocar no bucket de cadência.
    """
    evidence = evidence or []
    if responded:
        sb = 'nao_tocar_respondeu'
    elif bucket == 'nutricao_marketing':
        sb = 'nutricao_liberar_pipe'
    elif attempt_source == 'ledger':
        sb = 'd0_confiavel_cadencia'
    elif attempt_source == 'hubspot_activity':
        sb = 'reconciliar_hubspot'
    elif attempt_source == 'none' and 'whatsapp_history' in evidence:
        sb = 'reconciliar_whatsapp'
    else:
        sb = 'd0_real'
    return {
        'sanitationBucket': sb,
        'sanitationLabel': SANITATION_LABELS[sb],
        'recommendedAction': SANITATION_ACTIONS[sb],
        'needsReview': sb in SANITATION_NEEDS_REVIEW,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=500)
    ap.add_argument('--json-out', default=str(ROOT/'controle'/'cadencia_primeiro_contato_dryrun.json'))
    ap.add_argument('--sample', type=int, default=8)
    args=ap.parse_args()
    now=datetime.now(UTC)
    envios=load_envios()
    by_deal, by_phone=envio_attempt_records(envios)
    deals=search_deals_first_contact(args.limit)
    # Atividades HubSpot de TODOS os deals em lote, antes do loop (read-only).
    # Evita ir deal a deal (que estourava o tempo com 1 GET de associação/deal).
    activities_map=activities_by_deal([str(d.get('id') or '') for d in deals if d.get('id')])
    rows=[]; counts=defaultdict(int); sanit_counts=defaultdict(int)
    for d in deals:
        did=str(d.get('id') or '')
        props=d.get('properties') or {}
        owner_id=str(props.get('hubspot_owner_id') or '')
        owner=OWNERS.get(owner_id, owner_id or 'Sem owner')
        cid,cprops=associated_contact(did)
        phone=contact_phone(cprops)
        recs=list(by_deal.get(did, []))
        if phone:
            recs += [r for r in by_phone.get(phone, []) if r not in recs]
        recs=sorted(recs, key=lambda x:x['_dt'])
        ledger_attempts=len(recs)

        # Atividades HubSpot do deal (read-only), já lidas em lote antes do loop.
        # Robusto: falha na leitura em lote vira lista vazia, não derruba o run.
        activities=activities_map.get(did, [])
        activity_error=False
        acts_dt=sorted([a for a in activities if a['dt']], key=lambda a:a['dt'])
        last_act=acts_dt[-1] if acts_dt else None
        # Evidência de PRIMEIRO CONTATO inferida via termo comercial (conservador).
        fc_acts=[a for a in acts_dt if has_first_contact_term(a['subject'], a['body'])]
        fc_last=fc_acts[-1]['dt'] if fc_acts else None

        # Histórico WhatsApp local: lido uma vez para resposta + evidência de envio.
        hist=history_messages(phone)
        has_outbound=any(fromMe for _, fromMe in hist)

        # Fonte principal de tentativas: ledger > atividade HubSpot > nenhuma.
        evidence=[]
        if ledger_attempts > 0:
            attempt_source='ledger'
            attempts=ledger_attempts
            last_dt=recs[-1]['_dt']
            evidence.append('ledger')
            if fc_last: evidence.append('hubspot_activity')
        elif fc_last:
            # Sem ledger, mas há atividade HubSpot confiável de 1º contato.
            attempt_source='hubspot_activity'
            attempts=1
            last_dt=fc_last
            evidence.append('hubspot_activity')
        else:
            attempt_source='none'
            attempts=0
            last_dt=None
        if has_outbound: evidence.append('whatsapp_history')

        hours=((now-last_dt).total_seconds()/3600) if last_dt else None
        responded=False
        if last_dt:
            responded=any((not fromMe) and dt > last_dt for dt, fromMe in hist)
        if responded:
            bucket='respondeu_nao_tocar'
        else:
            bucket=bucket_for(attempts, hours or 0)
        counts[bucket]+=1
        # Saneamento (ortogonal ao bucket de cadência): aponta 1 dos 5 destinos.
        sanit=sanitation_for_row(bucket, attempt_source, evidence, responded)
        sanit_counts[sanit['sanitationBucket']]+=1
        rows.append({
            'dealId': did,
            'dealName': props.get('dealname') or '',
            'ownerId': owner_id,
            'owner': owner,
            'contactId': cid,
            'phone': phone,
            'attempts': attempts,
            'attemptSource': attempt_source,
            'evidence': evidence,
            'lastAttemptAt': last_dt.astimezone(BRT).isoformat() if last_dt else '',
            'hoursSinceLast': round(hours,1) if hours is not None else None,
            'respondedAfterLast': responded,
            'hubspotActivityCount': len(activities),
            'lastHubspotActivityAt': last_act['dt'].astimezone(BRT).isoformat() if last_act else '',
            'lastHubspotActivityType': last_act['type'] if last_act else '',
            'lastHubspotActivitySubject': last_act['label'] if last_act else '',
            'hubspotActivityError': activity_error,
            'bucket': bucket,
            'nextContactNumber': attempts+1 if bucket.startswith('dia_') else None,
            # CH: destino de saneamento (read-only, não altera o bucket acima).
            'sanitationBucket': sanit['sanitationBucket'],
            'sanitationLabel': sanit['sanitationLabel'],
            'recommendedAction': sanit['recommendedAction'],
            'needsReview': sanit['needsReview'],
        })
    out={'generatedAt': datetime.now(BRT).isoformat(), 'stage':'Primeiro Contato', 'totalDeals':len(deals), 'counts':dict(counts), 'sanitationCounts':dict(sanit_counts), 'rows':rows}
    Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json_out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print('CADENCIA_PRIMEIRO_CONTATO_DRYRUN')
    print('generatedAt:', out['generatedAt'])
    print('totalDeals:', len(deals))
    for k,v in sorted(counts.items()): print(f'{k}: {v}')
    # Mapa de saneamento: os 5 destinos operacionais (agrupa os 6 buckets).
    print('\nMapa de saneamento (5 destinos):')
    sanit_groups=[
        ('D0 real', ['d0_real']),
        ('Reconciliar ledger/evidência', ['reconciliar_hubspot','reconciliar_whatsapp']),
        ('Cadência 2º/3º/4º', ['d0_confiavel_cadencia']),
        ('Não tocar — respondeu', ['nao_tocar_respondeu']),
        ('Nutrição/liberar pipe', ['nutricao_liberar_pipe']),
    ]
    for label, keys in sanit_groups:
        total=sum(sanit_counts.get(k,0) for k in keys)
        detail=' '.join(f'{k}={sanit_counts.get(k,0)}' for k in keys) if len(keys)>1 else ''
        print(f'- {label}: {total}{("  ("+detail+")") if detail else ""}')
    eligible=[r for r in rows if str(r['bucket']).startswith('dia_')]
    print('\nElegíveis próximos contatos:', len(eligible))
    for r in eligible[:args.sample]:
        print(f"- {r['owner']} | {r['dealName']} | tentativas={r['attempts']} | fonte={r['attemptSource']} | {r['hoursSinceLast']}h | prox={r['nextContactNumber']}º")
    inferred=[r for r in rows if r['attemptSource']=='hubspot_activity']
    print('\nInferidos por atividade HubSpot (sem ledger):', len(inferred))
    for r in inferred[:args.sample]:
        print(f"- {r['owner']} | {r['dealName']} | bucket={r['bucket']} | últ.atividade={r['lastHubspotActivitySubject'][:50]}")
    errs=[r for r in rows if r.get('hubspotActivityError')]
    if errs:
        print(f'\nAtenção: {len(errs)} deal(s) com erro ao buscar atividades HubSpot (hubspotActivityError=true).')
    print('\nJSON:', args.json_out)

if __name__ == '__main__':
    main()
