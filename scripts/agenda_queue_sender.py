#!/usr/bin/env python3
"""Send queued agenda messages after the 20-minute diagnosis respiro."""
from __future__ import annotations
import fcntl, json, time, os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import importlib.util
import sys

ROOT = Path('/root/.hermes/zydon-prospeccao')
if str(ROOT / 'scripts') not in sys.path:
    sys.path.insert(0, str(ROOT / 'scripts'))
from zydon_operational_queues import append_wpp_envio, update_json_locked, normalize_envios  # noqa: E402
from whatsapp_send_orchestrator import enrich_legacy_row  # noqa: E402
from whatsapp_dispatch_flow import record_dispatch_shadow_from_row, record_dispatch_worker_owned  # noqa: E402

QUEUE = ROOT / 'controle/agenda_queue.json'
WPP = ROOT / 'controle/wpp_envios.json'
DISPATCH_QUEUE = ROOT / 'controle/whatsapp_dispatch_queue.json'
LOCK = Path('/tmp/zydon_agenda_queue.lock')

spec = importlib.util.spec_from_file_location('pg', ROOT / 'scripts/process_gate_once.py')
pg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pg)

def load(path, default):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception: return default

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def now_brt(): return datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%Y-%m-%d %H:%M')
def now_iso(): return datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat()

def append_wpp(row):
    row = enrich_legacy_row(
        row,
        nature='diagnostic_agenda_invite',
        origin='cron_agenda_queue',
        thread_state='scheduled_meeting',
        owner_uid=row.get('owner_sdr') or row.get('sdr') or row.get('owner_id'),
    )
    record_dispatch_shadow_from_row(row, origin='agenda', nature='diagnostic_agenda_invite', thread_state='scheduled_meeting')
    append_wpp_envio(row, WPP)


def mark_wpp_agenda_done(it, res):
    def upd(raw):
        data = normalize_envios(raw)
        envios=data.setdefault('envios', [])
        email=it.get('email'); slug=it.get('slug'); jid=it.get('jid'); port=it.get('port')
        for row in reversed(envios):
            if not isinstance(row, dict) or row.get('status') != 'enviado_lead':
                continue
            if email and row.get('email') != email:
                continue
            if slug and row.get('slug') != slug:
                continue
            if jid and row.get('to') != jid:
                continue
            if port and str(row.get('bridge_port')) != str(port):
                continue
            row['agenda_pending'] = False
            row['agenda_response'] = res
            row['agenda_done_at'] = now_iso()
            break
        envios.append(enrich_legacy_row({'date': now_brt(), 'email': email, 'slug': slug, 'status': 'agenda_followup_done', 'to': jid, 'bridge_port': port, 'agenda_queue_key': it.get('key'), 'agenda_response': res}, nature='diagnostic_agenda_invite', origin='cron_agenda_queue', thread_state='scheduled_meeting', owner_uid=it.get('owner_id')))
        return data
    update_json_locked(WPP, {'envios': []}, upd)

def history_path(port): return Path(f'/root/.hermes/whatsapp-extra/channel_data/history_{port}.json')

def lead_replied_after(port, jid, ts0):
    rows=load(history_path(port), [])
    targets={jid, jid.replace('@c.us','@s.whatsapp.net')}; out=[]
    for m in rows if isinstance(rows,list) else []:
        if not isinstance(m,dict) or m.get('fromMe') is True: continue
        chat=str(m.get('chat') or m.get('remoteJid') or (m.get('rawKey') or {}).get('remoteJid') or '')
        if chat not in targets: continue
        try:
            ts=float(m.get('timestamp') or 0); ts=ts/1000 if ts>10000000000 else ts
        except Exception: continue
        if ts<=ts0: continue
        txt=''
        for k in ('text','body','caption','content'):
            if isinstance(m.get(k),str) and m.get(k).strip(): txt=m.get(k).strip(); break
        out.append({'ts':ts,'text':txt[:300]})
    return out

def message_ts(port, mid):
    if not mid: return time.time()
    for m in load(history_path(port), []):
        if not isinstance(m,dict): continue
        if m.get('id')==mid or (m.get('rawKey') or {}).get('id')==mid:
            try:
                ts=float(m.get('timestamp') or 0); return ts/1000 if ts>10000000000 else ts
            except Exception: return time.time()
    return time.time()


def enqueue_worker_owned_agenda(it, port, jid):
    text = str(it.get('text') or '').strip()
    if not text:
        # Nunca criar worker_owned vazio: o worker bloquearia como
        # missing_port_or_text_or_jid e o item ficaria em queued_worker_owned sem
        # ação comercial real. Marcar para revisão preserva o processo sem
        # inventar link/frase de agenda.
        res = {'ok': False, 'blocked': True, 'reason': 'missing_agenda_text'}
        it['status'] = 'needs_review'
        it['result'] = res
        it['done_at'] = now_iso()
        it['worker_queue_result'] = res
        return res
    res = record_dispatch_worker_owned(
        origin='agenda',
        nature='diagnostic_agenda_invite',
        thread_state='scheduled_meeting',
        to=jid,
        text=text,
        owner_uid=it.get('owner_id') or it.get('owner_sdr') or it.get('sdr'),
        lead_key=it.get('deal_id') or it.get('contact_id') or it.get('email') or it.get('slug') or jid,
        port=port,
        path=DISPATCH_QUEUE,
        completion_type='agenda_queue',
        agenda_queue_key=it.get('key'),
        email=it.get('email'),
        contact_id=it.get('contact_id'),
        deal_id=it.get('deal_id'),
        slug=it.get('slug'),
    )
    if not res.get('ok') and not res.get('deduped'):
        return res
    it['status'] = 'queued_worker_owned'
    it['worker_dispatch_id'] = res.get('dispatch_id')
    it['worker_queued_at'] = now_iso()
    it['worker_queue_result'] = res
    return res


def main(worker_owned=None):
    if worker_owned is None:
        worker_owned = str(os.environ.get('ZYDON_AGENDA_WORKER_OWNED') or '').lower() in {'1', 'true', 'yes', 'on'}
    with LOCK.open('w') as lf:
        try: fcntl.flock(lf, fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return
        data=load(QUEUE, {'items':[]})
        items=data.get('items',[]) if isinstance(data,dict) else []
        now=time.time(); changed=False; out=[]
        for it in items:
            if it.get('status') != 'pending' or float(it.get('due_at') or 0) > now: continue
            port=int(it['port']); jid=it['jid']; qts=message_ts(port, it.get('question_message_id'))
            replies=lead_replied_after(port, jid, qts)
            if replies:
                res={'skipped': True, 'reason': 'lead_replied_before_agenda', 'replies': replies}
                it['status']='done'; it['result']=res; it['done_at']=now_iso(); changed=True
                mark_wpp_agenda_done(it, res)
                out.append(f"agenda_queue_done: {it.get('email') or it.get('slug') or jid} via {port}")
                save(QUEUE, {'items': items})
                append_wpp({'date':now_brt(),'date_tz':now_iso(),'email':it.get('email'),'contact_id':it.get('contact_id'),'deal_id':it.get('deal_id'),'status':'mql_agenda_sdr_apos_diagnostico','to':jid,'bridge_port':port,'owner_id':it.get('owner_id'),'text':it['text'],'response':res})
                out.append(f"agenda {it.get('email')}: {res}")
                continue
            if worker_owned:
                res = enqueue_worker_owned_agenda(it, port, jid)
                changed=True
                save(QUEUE, {'items': items})
                out.append(f"agenda_worker_owned_queued: {it.get('email') or it.get('slug') or jid} via {port} dispatch={res.get('dispatch_id')}")
                continue
            res, attempts = pg.post_bridge_with_retries_locked(port, '/send', {'to': jid, 'text': it['text']}, attempts=3, delay=12)
            res = {'response': res, 'attempts': attempts} if attempts else res
            it['status']='done'; it['result']=res; it['done_at']=now_iso(); changed=True
            mark_wpp_agenda_done(it, res)
            out.append(f"agenda_queue_done: {it.get('email') or it.get('slug') or jid} via {port}")
            # Persistir a fila imediatamente depois do /send ou skip. Se o cron cair
            # antes do save final, a próxima rodada não pode reenviar o mesmo link.
            save(QUEUE, {'items': items})
            append_wpp({'date':now_brt(),'date_tz':now_iso(),'email':it.get('email'),'contact_id':it.get('contact_id'),'deal_id':it.get('deal_id'),'status':'mql_agenda_sdr_apos_diagnostico','to':jid,'bridge_port':port,'owner_id':it.get('owner_id'),'text':it['text'],'response':res})
            out.append(f"agenda {it.get('email')}: {res}")
        if changed: save(QUEUE, {'items': items})
        if out: print('\n'.join(out))
if __name__ == '__main__': main()
