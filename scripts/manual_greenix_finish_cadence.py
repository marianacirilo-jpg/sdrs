#!/usr/bin/env python3
import json, time, urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path('/root/.hermes/zydon-prospeccao')
WPP=ROOT/'controle'/'wpp_envios.json'
CID='232058907307'; DEAL_ID='61763057572'; EMAIL='giuliano@greenix.com.br'; SLUG='greenix-industria-de-cosmeticos-giuliano'; COMPANY='Greenix industria de cosmeticos'; PHONE='11933264081'; JID='5511933264081@c.us'; PORT=4601; OWNER='88063842'; GROUP='120363408131718880@g.us'
PDF=ROOT/'pdfs'/'Greenix industria de cosmeticos - Potencial de Digitalizacao B2B.pdf'
TEXT='Boa tarde, Giuliano, tudo bem? Aqui é a Sarah, da Zydon.\n\nFiz uma análise prévia do potencial da digitalização B2B do seu negócio.'
TEXT_RESP={'success':True,'messageId':'3EB0A07FE79EFCC87DD140','status':1}
QUESTION='Como você imagina que a Zydon poderia te apoiar?'
AGENDA='Se quiser garantir o melhor horário para um diagnóstico completo, pode marcar direto aqui: https://meetings.hubspot.com/sarah-bento'
GROUP_SUMMARY='''✅ Lead qualificado\nEmpresa: Greenix industria de cosmeticos\nContato: Giuliano\nEmail: giuliano@greenix.com.br\nERP informado: Outro\nEntrada: 29/06/2026 09:40 BRT\nCriativo/origem: PAID_SOCIAL / Facebook | [mql] - escala - 1/3/1 - 25/06 - gus top 5 vender\n\nPor que qualificou:\n• Indústria e terceirização de cosméticos com site institucional validado.\n• Fabricação para clientes/empresas, produção flexível, atendimento Brasil e exterior e regularização ANVISA.\n• Formulário: R$1M a R$5M/ano, 11 a 25 pessoas, 2 a 5 vendedores, sem loja virtual e cliente compraria sozinho 24h.\n\nResponsável: Sarah\nDiagnóstico enviado por: Sarah\nCadência: texto curto, PDF após 1 min, pergunta após 30s, agenda após 20 min'''

def env_token():
    for line in Path('/root/.hermes/credentials/hubspot.env').read_text(errors='ignore').splitlines():
        if '=' in line and not line.strip().startswith('#'):
            k,v=line.split('=',1)
            if k.strip() in ('HUBSPOT_ACCESS_TOKEN','HUBSPOT_PRIVATE_APP_TOKEN','HUBSPOT_TOKEN','PRIVATE_APP_TOKEN','HUBSPOT_API_KEY'):
                return v.strip().strip('"\'')
    return ''
TOKEN=env_token()
def hub(method,path,payload=None):
    data=json.dumps(payload).encode() if payload is not None else None
    req=urllib.request.Request('https://api.hubapi.com'+path,data=data,method=method,headers={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=40) as r:
        txt=r.read().decode(); return json.loads(txt) if txt else {}
def bridge(port,path,payload,timeout=90):
    from whatsapp_safe_send import safe_post_bridge
    return safe_post_bridge(port, path, payload, uid='manual_greenix_finish_cadence', timeout=timeout)
def load_wpp():
    try: return json.loads(WPP.read_text(encoding='utf-8'))
    except Exception: return []
def save_wpp(x): WPP.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def now(): return datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%Y-%m-%d %H:%M')
def nowiso(): return datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat()
def replied_after(after_ts):
    hist=Path('/root/.hermes/whatsapp-extra/channel_data/history_4601.json')
    try: rows=json.loads(hist.read_text(encoding='utf-8'))
    except Exception: return False, []
    targets={JID,JID.replace('@c.us','@s.whatsapp.net')}; out=[]
    for m in rows if isinstance(rows,list) else []:
        if not isinstance(m,dict) or m.get('fromMe') is True: continue
        chat=str(m.get('chat') or m.get('remoteJid') or (m.get('rawKey') or {}).get('remoteJid') or '')
        if chat not in targets: continue
        try:
            ts=float(m.get('timestamp') or 0); ts=ts/1000 if ts>10000000000 else ts
        except Exception: continue
        if ts<=after_ts: continue
        txt=''
        for k in ('text','body','caption','content'):
            if isinstance(m.get(k),str) and m.get(k).strip(): txt=m.get(k).strip(); break
        out.append({'ts':ts,'text':txt[:300]})
    return bool(out), out
# espera restante do texto -> PDF
time.sleep(60)
resp_pdf=bridge(PORT,'/send-file',{'to':JID,'filePath':str(PDF),'fileName':f'{COMPANY} - Potencial de Digitalizacao B2B.pdf'},timeout=120)
pdf_ts=time.time(); print(json.dumps({'pdf':resp_pdf},ensure_ascii=False),flush=True)
time.sleep(30)
rep, reps = replied_after(pdf_ts)
if rep:
    resp_q={'skipped':True,'reason':'lead_replied_before_question','replies':reps}; q_ts=pdf_ts
else:
    resp_q=bridge(PORT,'/send',{'to':JID,'text':QUESTION}); q_ts=time.time()
print(json.dumps({'question':resp_q},ensure_ascii=False),flush=True)
time.sleep(1200)
rep2, reps2 = replied_after(q_ts)
if rep or rep2:
    resp_a={'skipped':True,'reason':'lead_replied_before_agenda','replies':reps or reps2}
else:
    resp_a=bridge(PORT,'/send',{'to':JID,'text':AGENDA})
print(json.dumps({'agenda':resp_a},ensure_ascii=False),flush=True)
resp_g=bridge(4609,'/send',{'to':GROUP,'text':GROUP_SUMMARY})
task=hub('POST','/crm/v3/objects/tasks',{'properties':{'hs_task_subject':"WhatsApp — Diagnóstico 'Potencial de Digitalização B2B' enviado ao lead.",'hs_task_body':'Diagnóstico Greenix enviado via WhatsApp pela Sarah. Cadência: texto, PDF após 1 min, pergunta após 30s e agenda após 20 min.','hs_task_status':'COMPLETED','hs_task_priority':'MEDIUM','hubspot_owner_id':OWNER},'associations':[{'to':{'id':CID},'types':[{'associationCategory':'HUBSPOT_DEFINED','associationTypeId':204}]},{'to':{'id':DEAL_ID},'types':[{'associationCategory':'HUBSPOT_DEFINED','associationTypeId':216}]}]})
wpp=load_wpp(); wpp.append({'date':now(),'date_tz':nowiso(),'email':EMAIL,'contact_id':CID,'deal_id':DEAL_ID,'slug':SLUG,'status':'enviado_lead','to':JID,'group':GROUP,'bridge_port':PORT,'group_bridge_port':4609,'owner_id':OWNER,'phone':PHONE,'empresa':COMPANY,'fallback_note':'correção manual Rafael: Greenix MQL, owner Sarah; envio pelo SDR dono','text':TEXT,'question_text':QUESTION,'agenda_text':AGENDA,'cadence':{'text_to_pdf_seconds':60,'pdf_to_question_seconds':30,'question_to_agenda_seconds':1200},'group_summary':GROUP_SUMMARY,'pdf_path':str(PDF),'text_response':TEXT_RESP,'file_response':resp_pdf,'question_response':resp_q,'agenda_response':resp_a,'group_summary_response':resp_g,'task_id':task.get('id')}); save_wpp(wpp)
with (ROOT/'controle'/'processed_emails.txt').open('a',encoding='utf-8') as f: f.write(f'{EMAIL}|{SLUG}|{now()}|enviado_lead|{PHONE}|{COMPANY}\n')
print(json.dumps({'done':True,'task_id':task.get('id'),'group':resp_g},ensure_ascii=False),flush=True)
