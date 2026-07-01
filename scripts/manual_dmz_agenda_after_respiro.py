#!/usr/bin/env python3
import json, time, importlib.util
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path('/root/.hermes/zydon-prospeccao')
spec = importlib.util.spec_from_file_location('pg', ROOT / 'scripts/process_gate_once.py')
pg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pg)
PORT=4603; JID='5516992919340@c.us'; EMAIL='dmz@dmz.com.br'; CID='232068683571'; DEAL_ID='61770586497'; OWNER='85778446'
QUESTION_ID='3EB0F6B89CCB676C62489B'
AGENDA='Se quiser garantir o melhor horário para um diagnóstico completo, pode marcar direto aqui: https://meetings.hubspot.com/lucas-alcantara-nogueira-batista'

def bridge(path,payload,timeout=90):
    # Faxina segura 2026-06-30: usa camada segura e auditável.
    return pg.post_bridge(PORT, path, payload)

def history():
    p=Path('/root/.hermes/whatsapp-extra/channel_data/history_4603.json')
    try: return json.loads(p.read_text(encoding='utf-8'))
    except Exception: return []

def question_ts():
    for m in history():
        if isinstance(m,dict) and (m.get('id')==QUESTION_ID or (m.get('rawKey') or {}).get('id')==QUESTION_ID):
            ts=float(m.get('timestamp') or 0); return ts/1000 if ts>10000000000 else ts
    return time.time()

def replied_after(ts0):
    targets={JID,JID.replace('@c.us','@s.whatsapp.net')}; out=[]
    for m in history():
        if not isinstance(m,dict) or m.get('fromMe') is True: continue
        chat=str(m.get('chat') or m.get('remoteJid') or (m.get('rawKey') or {}).get('remoteJid') or '')
        if chat not in targets: continue
        try: ts=float(m.get('timestamp') or 0); ts=ts/1000 if ts>10000000000 else ts
        except Exception: continue
        if ts<=ts0: continue
        txt=''
        for k in ('text','body','caption','content'):
            if isinstance(m.get(k),str) and m.get(k).strip(): txt=m.get(k).strip(); break
        out.append({'ts':ts,'text':txt[:300]})
    return out
qt=question_ts(); wait=max(0, 20*60 - (time.time()-qt)); time.sleep(wait)
replies=replied_after(qt)
if replies:
    result={'skipped':True,'reason':'lead_replied_before_agenda','replies':replies}
else:
    result=bridge('/send', {'to':JID,'text':AGENDA})
# ledger
p=ROOT/'controle/wpp_envios.json'
try: data=json.loads(p.read_text(encoding='utf-8'))
except Exception: data={'envios':[]}
rows=data.get('envios',[]) if isinstance(data,dict) else data
rows.append({'date':datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%Y-%m-%d %H:%M'),'date_tz':datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat(),'email':EMAIL,'contact_id':CID,'deal_id':DEAL_ID,'slug':'dmz-vitor-feriza','status':'mql_agenda_sdr_apos_diagnostico','to':JID,'bridge_port':PORT,'owner_id':OWNER,'text':AGENDA,'response':result})
p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'agenda_result':result},ensure_ascii=False))
