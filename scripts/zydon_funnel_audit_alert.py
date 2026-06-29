#!/usr/bin/env python3
"""Zydon: auditoria silenciosa das primeiras etapas do funil.
Imprime alerta apenas quando há furo operacional relevante.
"""
import json, os, re, sys, hashlib, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, '/root/.hermes/zydon-prospeccao/scripts')
from whatsapp_safe_send import safe_post_bridge

MENTION = '<@1445899458666696829> <@551035817129148419>'
BASE = 'https://api.hubapi.com'
PIPE = '671008549'
BRT = timezone(timedelta(hours=-3))
STAGES = {
    '984052829': 'Lead Sem Contato',
    '1214320997': 'Primeiro Contato',
    '998099482': 'Retorno Contato',
    '1151853491': 'Diagnóstico SDR',
    '1376131958': 'No Show',
}
SDR_PORTS = [4600, 4601, 4603, 4605, 4606, 4607, 4609, 4610]
GROUP_JID = '120363408131718880@g.us'
GROUP_BRIDGE = 'http://127.0.0.1:4607'
WA_ALERT_STATE = Path('/root/.hermes/zydon-prospeccao/controle/funnel_audit_whatsapp_alerts.json')
WA_MENTIONS = ['553484428888@s.whatsapp.net', '553496698718@s.whatsapp.net']
OWNER_NAMES = {'86265630': 'Breno', '88063842': 'Sarah', '85778446': 'Lucas Batista', '76764091': 'Lucas Batista'}
OWNER_WA = {'86265630': '553484325076@s.whatsapp.net', '88063842': '553484095632@s.whatsapp.net', '85778446': '553484295409@s.whatsapp.net', '76764091': '553484295409@s.whatsapp.net'}

def load_token():
    for k in ('HUBSPOT_ACCESS_TOKEN','HUBSPOT_TOKEN','PRIVATE_APP_TOKEN','HUBSPOT_API_KEY'):
        if os.environ.get(k): return os.environ[k].strip()
    env = Path('/root/.hermes/credentials/hubspot.env')
    if env.exists():
        for line in env.read_text().splitlines():
            if '=' not in line or line.strip().startswith('#'): continue
            k,v=line.split('=',1)
            if k.strip() in ('HUBSPOT_ACCESS_TOKEN','HUBSPOT_TOKEN','PRIVATE_APP_TOKEN','HUBSPOT_API_KEY'):
                return v.strip().strip('"\'')
    raise SystemExit('Sem token HubSpot')
TOKEN = load_token()

def hs(method,path,body=None):
    import time
    data=json.dumps(body).encode() if body is not None else None
    headers={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json'}
    for attempt in range(5):
        req=urllib.request.Request(BASE+path,data=data,method=method,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=40) as r:
                raw=r.read().decode(); return json.loads(raw or '{}') if raw else {}
        except urllib.error.HTTPError as e:
            if e.code in (429,500,502,503,504) and attempt < 4:
                time.sleep(2 ** attempt)
                continue
            raise

def search(stage):
    out=[]; after=None
    while True:
        body={'filterGroups':[{'filters':[{'propertyName':'pipeline','operator':'EQ','value':PIPE},{'propertyName':'dealstage','operator':'EQ','value':stage}]}], 'properties':['dealname','hubspot_owner_id'], 'limit':100}
        if after: body['after']=after
        d=hs('POST','/crm/v3/objects/deals/search',body); out += d.get('results',[])
        after=((d.get('paging') or {}).get('next') or {}).get('after')
        if not after: break
    return out

def assoc(obj, oid, to):
    out=[]; after=None
    while True:
        p=f'/crm/v4/objects/{obj}/{oid}/associations/{to}?limit=500'
        if after: p+='&after='+str(after)
        d=hs('GET',p)
        out += [str(x.get('toObjectId') or x.get('id')) for x in d.get('results',[]) if (x.get('toObjectId') or x.get('id'))]
        after=((d.get('paging') or {}).get('next') or {}).get('after')
        if not after: break
    return out

def batch(obj,ids,props):
    ids=list(dict.fromkeys(ids)); out={}
    for i in range(0,len(ids),100):
        if not ids[i:i+100]: continue
        d=hs('POST',f'/crm/v3/objects/{obj}/batch/read',{'properties':props,'inputs':[{'id':x} for x in ids[i:i+100]]})
        for r in d.get('results',[]): out[str(r['id'])]=r.get('properties',{})
    return out

def parse_dt(s):
    if not s: return None
    try:
        if str(s).isdigit(): return datetime.fromtimestamp(int(s)/1000,tz=timezone.utc)
        return datetime.fromisoformat(str(s).replace('Z','+00:00'))
    except Exception: return None

def next_period_sla_due(anchor=None):
    """Rafael 29/06: touchpoint futuro por próximo período útil.

    Manhã -> tarefa 14h do mesmo dia.
    Tarde/noite -> tarefa 9h do próximo dia útil.
    Usado quando auditoria encontra Retorno Contato/No Show sem atividade futura.
    """
    now = (anchor or datetime.now(timezone.utc)).astimezone(BRT)
    if now.weekday() < 5 and now.hour < 12:
        due = now.replace(hour=14, minute=0, second=0, microsecond=0)
    else:
        due = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        while due.weekday() >= 5:
            due += timedelta(days=1)
    return due

def create_contact_task(deal, contact_ids, label):
    props = deal.get('properties') or {}
    owner = props.get('hubspot_owner_id')
    name = props.get('dealname') or deal['id']
    if not owner:
        return None
    associations = [
        {'to': {'id': str(deal['id'])}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 216}]},
    ]
    for cid in contact_ids[:5]:
        associations.append({'to': {'id': str(cid)}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 204}]})
    if label == 'No Show':
        subject = 'Revisar No Show e definir próximo contato'
        action_hint = 'Revisar se é caso de remarcar diagnóstico, tentar novo contato ou encerrar corretamente.'
    else:
        subject = 'Entrar em contato — Retorno Contato'
        action_hint = 'Retomar pelo contexto da última interação efetiva e conduzir para agenda se fizer sentido.'
    due_brt = next_period_sla_due()
    body = {
        'properties': {
            'hs_task_subject': subject,
            'hs_task_body': (
                f'Tarefa criada automaticamente pela auditoria do funil: o negócio está em {label} '
                'e não tinha nenhum touchpoint/atividade futura agendada para o SDR. '
                f'Aplicado SLA do próximo período útil: {due_brt.strftime("%d/%m/%Y %H:%M BRT")}. '
                f'{action_hint} '
                'Abrir o histórico do WhatsApp/HubSpot antes de responder.'
            ),
            'hs_task_status': 'NOT_STARTED',
            'hs_task_priority': 'HIGH',
            'hs_timestamp': due_brt.astimezone(timezone.utc).isoformat().replace('+00:00','Z'),
            'hubspot_owner_id': str(owner),
        },
        'associations': associations,
    }
    created = hs('POST','/crm/v3/objects/tasks',body)
    return {'deal': name, 'task_id': str(created.get('id') or ''), 'owner': str(owner)}

def check_stage(stage_id, label):
    deals=search(stage_id)
    # Performance guard: Lead Sem Contato e Primeiro Contato só entram na contagem.
    # O cron no Hermes tem timeout script-only de ~120s. Retorno Contato/No Show
    # têm centenas de deals e a auditoria antiga fazia N chamadas por deal
    # (associações/tarefas/contatos), estourando timeout antes de entregar o alerta
    # realmente crítico. Este watchdog fica rápido e determinístico: contagem para
    # etapas grandes; checagem detalhada só em Diagnóstico SDR, onde a ausência de
    # reunião futura é furo operacional relevante.
    if label != 'Diagnóstico SDR':
        return {'count':len(deals),'no_open':[],'no_future':[],'auto_created':[]}

    all_tasks=[]; all_meet=[]; maps={}
    for d in deals:
        did=d['id']
        tids=assoc('deals',did,'tasks')
        mids=assoc('deals',did,'meetings') if label=='Diagnóstico SDR' else []
        cids=assoc('deals',did,'contacts') if label in ('Retorno Contato','No Show','Diagnóstico SDR') else []
        contact_mids=[]
        # HubSpot às vezes deixa a reunião futura ligada ao contato antes de
        # aparecer/ser persistida diretamente no deal. Para Diagnóstico SDR,
        # agenda no contato também conta como agenda real; se não olharmos aqui
        # a auditoria dá falso "sem reunião futura".
        if label=='Diagnóstico SDR':
            for cid in cids:
                contact_mids += assoc('contacts',cid,'meetings')
        mids_all=list(dict.fromkeys(mids + contact_mids))
        maps[did]={'tasks':tids,'meetings':mids_all,'direct_meetings':mids,'contact_meetings':contact_mids,'contacts':cids}
        all_tasks += tids
        all_meet += mids_all
    tasks=batch('tasks',all_tasks,['hs_task_status','hs_task_subject','hs_timestamp'])
    meetings=batch('meetings',all_meet,['hs_meeting_start_time','hs_timestamp','hs_meeting_title']) if all_meet else {}
    no_open=[]; no_future=[]; auto_created=[]
    now=datetime.now(timezone.utc)
    for d in deals:
        name=(d.get('properties') or {}).get('dealname') or d['id']
        has_touchpoint=False
        for tid in maps[d['id']]['tasks']:
            tp = tasks.get(tid,{})
            st=(tp.get('hs_task_status') or '').upper()
            dt=parse_dt(tp.get('hs_timestamp'))
            if st not in ('COMPLETED','DONE'):
                # Retorno Contato e No Show exigem atividade futura agendada.
                # Para Diagnóstico SDR mantemos a regra anterior de tarefa aberta,
                # porque a reunião futura é verificada separadamente.
                if label in ('Retorno Contato','No Show'):
                    if dt and dt > now:
                        has_touchpoint=True; break
                else:
                    has_touchpoint=True; break
        if not has_touchpoint:
            if label in ('Retorno Contato','No Show'):
                created = create_contact_task(d, maps[d['id']].get('contacts') or [], label)
                if created:
                    auto_created.append(created)
                else:
                    no_open.append(name)
            elif label == 'Diagnóstico SDR':
                # Rafael 29/06: Diagnóstico SDR sem agenda não deve virar tarefa genérica.
                # É melhor coordenar no grupo e marcar o SDR dono para decidir se remarca,
                # move etapa ou faz próxima ação. Tarefa aberta para SDR precisa ser sniper.
                pass
            else:
                no_open.append(name)
        if label=='Diagnóstico SDR':
            future=False
            for mid in maps[d['id']]['meetings']:
                dt=parse_dt(meetings.get(mid,{}).get('hs_meeting_start_time') or meetings.get(mid,{}).get('hs_timestamp'))
                if dt and dt>now: future=True; break
            if not future:
                owner = (d.get('properties') or {}).get('hubspot_owner_id') or ''
                owner_name = OWNER_NAMES.get(str(owner), str(owner) or 'sem owner')
                no_future.append(f'{name} (SDR {owner_name})')
    return {'count':len(deals),'no_open':no_open,'no_future':no_future,'auto_created':auto_created}

def chip_status():
    bad=[]
    for port in SDR_PORTS:
        ok=False; detail='sem resposta'
        for endpoint in ('status','me'):
            try:
                with urllib.request.urlopen(f'http://localhost:{port}/{endpoint}',timeout=3) as r:
                    raw=r.read().decode(); data=json.loads(raw or '{}') if raw else {}
                if endpoint=='status' and data.get('connected') and not data.get('needsQR'):
                    ok=True; break
                if endpoint=='me' and (data.get('phone') or data.get('id')):
                    ok=True; break
                detail=str(data)[:120] or detail
            except Exception as e:
                detail=str(e)[:120]
        if not ok: bad.append(f'{port}: {detail}')
    return bad

def load_state(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}

def save_state(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)

def wa_alert_line(a):
    line = a
    for oid, name in OWNER_NAMES.items():
        jid = OWNER_WA.get(oid)
        if jid and f'SDR {name}' in line:
            line = line.replace(f'SDR {name}', f'SDR @{jid.split("@",1)[0]} {name}')
    return line

def send_whatsapp_pipe_alert(alerts):
    state = load_state(WA_ALERT_STATE)
    new = []
    for a in alerts:
        key = hashlib.sha1(a.encode()).hexdigest()
        if key not in state:
            new.append(a)
            state[key] = datetime.now(timezone.utc).isoformat()
    if not new:
        save_state(WA_ALERT_STATE, state)
        return None
    wa_lines = [wa_alert_line(x) for x in new[:6]]
    mentions = list(dict.fromkeys(WA_MENTIONS + [jid for oid, jid in OWNER_WA.items() if OWNER_NAMES.get(oid) and f'SDR {OWNER_NAMES[oid]}' in '\n'.join(new)]))
    text = 'Dexter: @553484428888 @553496698718 alerta de incoerência no funil Zydon:\n' + '\n'.join('- ' + x for x in wa_lines)
    payload = {'to': GROUP_JID, 'text': text, 'mentions': mentions}
    resp = safe_post_bridge(4607, '/send', payload, uid='funnel_audit_alert', timeout=15)
    save_state(WA_ALERT_STATE, state)
    return resp

def main():
    alerts=[]; summary={}
    for sid,label in STAGES.items():
        info=check_stage(sid,label); summary[label]=info['count']
        if info.get('auto_created'):
            alerts.append(f"{label}: criei {len(info['auto_created'])} tarefa(s) automática(s) 'Entrar em contato' para o próximo período útil. Ex.: " + '; '.join(f"{x['deal']} (task {x['task_id']})" for x in info['auto_created'][:5]))
        if info['no_open']:
            alerts.append(f"{label}: {len(info['no_open'])} negócio(s) sem atividade futura/tarefa aberta. Ex.: " + '; '.join(info['no_open'][:5]))
        if info['no_future']:
            alerts.append(f"{label}: {len(info['no_future'])} negócio(s) sem reunião futura. Ex.: " + '; '.join(info['no_future'][:5]))
    bad_chips=chip_status()
    if bad_chips:
        alerts.append('Chips sem resposta no bridge: ' + ' | '.join(bad_chips))
    if alerts:
        wa = send_whatsapp_pipe_alert(alerts)
        print(f"{MENTION} auditoria do funil Zydon encontrou furo(s):")
        print('Contagem: ' + ', '.join(f'{k}={v}' for k,v in summary.items()))
        for a in alerts:
            print('- ' + a)
        if wa:
            if wa.get('success'):
                print(f"WhatsApp grupo: avisado (ID {wa.get('messageId')}).")
            else:
                print(f"WhatsApp grupo: falha ao avisar ({wa.get('error') or wa}).")

if __name__ == '__main__':
    main()
