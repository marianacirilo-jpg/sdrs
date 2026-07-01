#!/usr/bin/env python3
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path('/root/.hermes/zydon-prospeccao')
WPP = ROOT / 'controle' / 'wpp_envios.json'
CID = '232058907307'
DEAL_ID = '61763057572'
EMAIL = 'giuliano@greenix.com.br'
SLUG = 'greenix-industria-de-cosmeticos-giuliano'
COMPANY = 'Greenix industria de cosmeticos'
PHONE = '11933264081'
JID = '5511933264081@c.us'
PORT = 4601
OWNER = '88063842'
OWNER_NAME = 'Sarah'
GROUP = '120363408131718880@g.us'
PDF = ROOT / 'pdfs' / 'Greenix industria de cosmeticos - Potencial de Digitalizacao B2B.pdf'
TEXT = 'Boa tarde, Giuliano, tudo bem? Aqui é a Sarah, da Zydon.\n\nFiz uma análise prévia do potencial da digitalização B2B do seu negócio.'
QUESTION = 'Como você imagina que a Zydon poderia te apoiar?'
AGENDA = 'Se quiser garantir o melhor horário para um diagnóstico completo, pode marcar direto aqui: https://meetings.hubspot.com/sarah-bento'
GROUP_SUMMARY = '''✅ Lead qualificado\nEmpresa: Greenix industria de cosmeticos\nContato: Giuliano\nEmail: giuliano@greenix.com.br\nERP informado: Outro\nEntrada: 29/06/2026 09:40 BRT\nCriativo/origem: PAID_SOCIAL / Facebook | [mql] - escala - 1/3/1 - 25/06 - gus top 5 vender\n\nPor que qualificou:\n• Indústria e terceirização de cosméticos com site institucional validado.\n• Fabricação para clientes/empresas, produção flexível, atendimento Brasil e exterior e regularização ANVISA.\n• Formulário: R$1M a R$5M/ano, 11 a 25 pessoas, 2 a 5 vendedores, sem loja virtual e cliente compraria sozinho 24h.\n\nResponsável: Sarah\nDiagnóstico enviado por: Sarah\nCadência: texto curto, PDF após 1 min, pergunta após 30s, agenda após 20 min'''

def load_env():
    env = Path('/root/.hermes/credentials/hubspot.env')
    if env.exists():
        for line in env.read_text(errors='ignore').splitlines():
            if '=' in line and not line.strip().startswith('#'):
                k,v=line.split('=',1)
                if k.strip() in ('HUBSPOT_ACCESS_TOKEN','HUBSPOT_PRIVATE_APP_TOKEN','HUBSPOT_TOKEN','PRIVATE_APP_TOKEN','HUBSPOT_API_KEY'):
                    return v.strip().strip('"\'')
    return ''
TOKEN = load_env()

def hub(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request('https://api.hubapi.com'+path, data=data, method=method, headers={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        txt=resp.read().decode()
        return json.loads(txt) if txt else {}

def bridge(path, payload, port=PORT, retries=3):
    from whatsapp_safe_send import safe_post_bridge
    last = None
    for i in range(retries):
        try:
            out=safe_post_bridge(port, path, payload, uid='manual_greenix_diagnostico_cadence', timeout=45)
            if out.get('success') or out.get('messageId') or out.get('status') == 1:
                return out
            last=out
        except Exception as e:
            last={'error':str(e)}
        time.sleep(10)
    return last or {'error':'unknown'}

def load_wpp():
    try:
        return json.loads(WPP.read_text(encoding='utf-8'))
    except Exception:
        return []

def save_wpp(rows):
    WPP.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')

def now_brt():
    return datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%Y-%m-%d %H:%M')

def now_brt_iso():
    return datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat()

def lead_replied_after(after_ts):
    hist = Path('/root/.hermes/whatsapp-extra/channel_data/history_4601.json')
    try:
        rows=json.loads(hist.read_text(encoding='utf-8'))
    except Exception:
        return False, []
    targets={JID, JID.replace('@c.us','@s.whatsapp.net')}
    replies=[]
    for m in rows if isinstance(rows,list) else []:
        if not isinstance(m,dict) or m.get('fromMe') is True:
            continue
        chat=str(m.get('chat') or m.get('remoteJid') or (m.get('rawKey') or {}).get('remoteJid') or '')
        if chat not in targets:
            continue
        ts=m.get('timestamp') or 0
        try:
            ts=float(ts); ts=ts/1000 if ts>10000000000 else ts
        except Exception:
            continue
        if ts <= after_ts:
            continue
        txt=''
        for k in ('text','body','caption','content'):
            if isinstance(m.get(k),str) and m.get(k).strip():
                txt=m.get(k).strip(); break
        replies.append({'ts':ts,'text':txt[:300]})
    return bool(replies), replies

# fail-safe: ensure MQL/owner/deal still correct
hub('PATCH', f'/crm/v3/objects/contacts/{CID}', {'properties': {'lifecyclestage':'marketingqualifiedlead','hubspot_owner_id':OWNER}})
if DEAL_ID:
    hub('PATCH', f'/crm/v3/objects/deals/{DEAL_ID}', {'properties': {'hubspot_owner_id':OWNER, 'dealstage':'984052829', 'pipeline':'671008549'}})

wpp=load_wpp()
if any(isinstance(r, dict) and r.get('email')==EMAIL and r.get('status')=='enviado_lead' for r in wpp):
    print('SKIP: Greenix já tem enviado_lead no ledger')
    raise SystemExit(0)

resp1=bridge('/send', {'to':JID,'text':TEXT})
if not (resp1 and (resp1.get('success') or resp1.get('messageId') or resp1.get('status')==1)):
    print(json.dumps({'error':'texto falhou','resp':resp1}, ensure_ascii=False))
    raise SystemExit(1)
text_sent_ts=time.time()
print(json.dumps({'step':'text_sent','resp':resp1}, ensure_ascii=False), flush=True)
time.sleep(60)
resp2=bridge('/send-file', {'to':JID,'filePath':str(PDF),'fileName':f'{COMPANY} - Potencial de Digitalizacao B2B.pdf'})
if not (resp2 and (resp2.get('success') or resp2.get('messageId') or resp2.get('status')==1)):
    print(json.dumps({'error':'pdf falhou','resp':resp2}, ensure_ascii=False))
    raise SystemExit(1)
pdf_sent_ts=time.time()
print(json.dumps({'step':'pdf_sent','resp':resp2}, ensure_ascii=False), flush=True)
time.sleep(30)
replied, replies = lead_replied_after(pdf_sent_ts)
if replied:
    respq={'skipped':True,'reason':'lead_replied_before_question','replies':replies}
    question_ts=pdf_sent_ts
else:
    respq=bridge('/send', {'to':JID,'text':QUESTION})
    question_ts=time.time()
print(json.dumps({'step':'question','resp':respq}, ensure_ascii=False), flush=True)
time.sleep(20*60)
replied2, replies2 = lead_replied_after(question_ts)
if replied or replied2:
    respa={'skipped':True,'reason':'lead_replied_before_agenda','replies':replies or replies2}
else:
    respa=bridge('/send', {'to':JID,'text':AGENDA})
print(json.dumps({'step':'agenda','resp':respa}, ensure_ascii=False), flush=True)
# grupo após envio do fluxo
respg=bridge('/send', {'to':GROUP,'text':GROUP_SUMMARY}, port=4609, retries=2)
# task hubspot
body='Diagnóstico Greenix enviado via WhatsApp pela Sarah. Cadência: texto curto, PDF após 1 min, pergunta após 30s e agenda após 20 min.'
if isinstance(respa,dict) and respa.get('skipped'):
    body += '\nAgenda não enviada porque o lead respondeu antes.'
task=hub('POST','/crm/v3/objects/tasks', {'properties': {'hs_task_subject': "WhatsApp — Diagnóstico 'Potencial de Digitalização B2B' enviado ao lead.", 'hs_task_body': body, 'hs_task_status':'COMPLETED', 'hs_task_priority':'MEDIUM', 'hubspot_owner_id':OWNER}, 'associations':[{'to':{'id':CID},'types':[{'associationCategory':'HUBSPOT_DEFINED','associationTypeId':204}]},{'to':{'id':DEAL_ID},'types':[{'associationCategory':'HUBSPOT_DEFINED','associationTypeId':216}]}]})
wpp=load_wpp()
wpp.append({'date':now_brt(),'date_tz':now_brt_iso(),'email':EMAIL,'contact_id':CID,'slug':SLUG,'status':'enviado_lead','to':JID,'group':GROUP,'bridge_port':PORT,'group_bridge_port':4609,'owner_id':OWNER,'phone':PHONE,'empresa':COMPANY,'fallback_note':'correção manual Rafael: Greenix MQL, owner Sarah; envio pelo SDR dono','text':TEXT,'question_text':QUESTION,'agenda_text':AGENDA,'cadence':{'text_to_pdf_seconds':60,'pdf_to_question_seconds':30,'question_to_agenda_seconds':1200},'group_summary':GROUP_SUMMARY,'pdf_path':str(PDF),'text_response':resp1,'file_response':resp2,'question_response':respq,'agenda_response':respa,'group_summary_response':respg,'task_id':task.get('id')})
save_wpp(wpp)
# processed
proc=ROOT/'controle'/'processed_emails.txt'
with proc.open('a', encoding='utf-8') as f:
    f.write(f"{EMAIL}|{SLUG}|{now_brt()}|enviado_lead|{PHONE}|{COMPANY}\n")
print(json.dumps({'done':True,'task_id':task.get('id'),'group':respg}, ensure_ascii=False), flush=True)