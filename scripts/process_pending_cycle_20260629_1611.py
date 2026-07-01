#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One autonomous cron cycle for pending Discord-only alerts after gate empty."""
from __future__ import annotations
import importlib.util, json, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path('/root/.hermes/zydon-prospeccao')
sys.path.insert(0, str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('pg', ROOT/'scripts/process_gate_once.py')
pg=importlib.util.module_from_spec(spec); spec.loader.exec_module(pg)
spec2=importlib.util.spec_from_file_location('aq', ROOT/'scripts/active_mql_qualifier.py')
aq=importlib.util.module_from_spec(spec2); spec2.loader.exec_module(aq)

GROUP='120363408131718880@g.us'
CONTROL=ROOT/'controle'
PROCESSED=CONTROL/'processed_emails.txt'
WPP=CONTROL/'wpp_envios.json'
QUEUE=CONTROL/'agenda_queue.json'
BRT=ZoneInfo('America/Sao_Paulo')
PIPELINE='671008549'; LEAD_SEM_CONTATO='984052829'

def now_brt(): return datetime.now(BRT).strftime('%Y-%m-%d %H:%M')
def now_iso_brt(): return datetime.now(BRT).isoformat()
def only_digits(s): return re.sub(r'\D+','',s or '')
def load_json(p, default):
    try: return json.loads(p.read_text(encoding='utf-8'))
    except Exception: return default

def save_json(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def append_wpp(row):
    data=load_json(WPP, {'envios':[]})
    if not isinstance(data, dict): data={'envios': data if isinstance(data,list) else []}
    data.setdefault('envios',[]).append(row)
    save_json(WPP, data)

def append_processed(email, slug, status, phone, company):
    with PROCESSED.open('a', encoding='utf-8') as f:
        f.write(f'{email}|{slug}|{now_brt()}|{status}|{phone}|{company}\n')

def final_emails():
    out=set()
    if PROCESSED.exists():
        for line in PROCESSED.read_text(errors='ignore').splitlines():
            if line.strip(): out.add(line.split('|',1)[0].strip().lower())
    data=load_json(WPP, {'envios':[]}); rows=data.get('envios',[]) if isinstance(data,dict) else data
    for r in rows:
        if isinstance(r,dict) and str(r.get('status','')).lower() in {'enviado_lead','enviado_mql','nao_mql_grupo','mql_telefone_invalido_grupo','mql_diagnostico_em_andamento','mql_manual_reclassificado'}:
            e=str(r.get('email') or '').lower()
            if e: out.add(e)
    return out

def fetch_contact(cid):
    qs='&'.join('properties='+p for p in aq.CONTACT_PROPS)
    return aq.hs('GET', f'/crm/v3/objects/contacts/{cid}?{qs}')

def source_line(p):
    vals=[]
    for k in ('hs_analytics_source','hs_analytics_source_data_1','hs_analytics_source_data_2','hs_latest_source','hs_latest_source_data_1','hs_latest_source_data_2','recent_conversion_event_name'):
        v=(p.get(k) or '').strip()
        if v and v not in vals: vals.append(v)
    return ' / '.join(vals[:3]) if vals else 'não informado'

def created_brt(p):
    s=p.get('recent_conversion_date') or p.get('createdate') or ''
    try:
        dt=datetime.fromisoformat(s.replace('Z','+00:00'))
        return dt.astimezone(BRT).strftime('%d/%m/%Y %H:%M')+' BRT'
    except Exception: return s or 'não informado'

def company_slug(company): return re.sub(r'[^a-z0-9]+','-', (company or '').lower()).strip('-')[:70] or 'lead'

def notify_group(text):
    data=load_json(WPP, {'envios':[]}); envios=data.get('envios',[]) if isinstance(data,dict) else []
    port, resp, attempts = pg.post_group_with_rotation(text, envios)
    return port, resp, attempts

def non_mql(cid, reason, bullets):
    c=fetch_contact(cid); p=c.get('properties') or {}
    email=(p.get('email') or '').lower(); company=(p.get('company') or email).strip(); first=(p.get('firstname') or 'não informado').strip()
    if email in final_emails(): return f'PULADO finalizado: {email}'
    text=(f'❌ Lead não qualificado\nEmpresa: {company}\nContato: {first}\nEmail: {email}\nEntrada: {created_brt(p)}\nCriativo/origem: {source_line(p)}\n\nPor que não qualificou:\n' + ''.join(f'• {b}\n' for b in bullets).rstrip())
    port, resp, attempts=notify_group(text)
    deals=pg.contact_deals(cid)
    task_id=None
    try:
        task_id=pg.create_task(cid, deals, 'Qualificação inbound — lead não qualificado', reason, None)
    except Exception as e:
        task_id=f'erro: {e}'
    phone=only_digits(p.get('hs_searchable_calculated_phone_number') or p.get('hs_whatsapp_phone_number') or p.get('phone') or '')
    append_wpp({'date':now_brt(),'date_tz':now_iso_brt(),'email':email,'contact_id':cid,'status':'nao_mql_grupo','empresa':company,'reason':reason,'group_bridge_port':port,'group_response':resp,'group_attempts':attempts,'task_id':task_id})
    append_processed(email, company_slug(company), 'nao_mql_grupo', phone, company)
    return f'❌ Não-MQL registrado: {company} ({email})'

def enqueue_agenda(row):
    data=load_json(QUEUE, {'items':[]}); data.setdefault('items',[]).append(row); save_json(QUEUE,data)

def send_discra():
    cid='232055776166'
    c=fetch_contact(cid); p=c.get('properties') or {}
    email=(p.get('email') or '').lower(); company=(p.get('company') or 'Discra Distribuidora').strip(); first=(p.get('firstname') or 'Dantielia').strip()
    if email in final_emails(): return f'PULADO finalizado: {email}'
    # WhatsApp público real encontrado no site oficial discra.com.br (wa.me/551146054694).
    phone='551146054694'; jid=phone+'@c.us'
    append_wpp({'date':now_brt(),'date_tz':now_iso_brt(),'email':email,'contact_id':cid,'status':'mql_diagnostico_em_andamento','empresa':company,'to':jid,'phone_source':'site oficial discra.com.br wa.me/551146054694'})
    pg.patch_contact(cid, {'lifecyclestage':'marketingqualifiedlead'})
    owner, deals, notes = pg.wait_for_business_owner(cid, timeout_sec=300, interval_sec=10)
    if owner in pg.OWNER_MAP:
        om=pg.OWNER_MAP[owner]
        try:
            for did in deals:
                pg.patch_deal(did, {'pipeline':PIPELINE,'dealstage':LEAD_SEM_CONTATO,'hubspot_owner_id':owner})
        except Exception: pass
        port=om['porta']; sender=om['nome']; sig=om['assinatura']; agenda=om['agenda']; fallback_note=''
    else:
        om=pg.DEFAULT_OWNER
        port=4600; sender='Mariana'; sig='Aqui é a Mariana, da Zydon'; agenda=''; fallback_note='fallback institucional: owner/deal não resolvido após espera; ' + '; '.join(notes[-3:])
    research={
      'slug':'discra-distribuidora-dantielia',
      'mql': True,
      'empresa_real':'Discra Distribuidora — empresa validada pelo domínio oficial discra.com.br e formulário HubSpot.',
      'dominio_site':'discra.com.br — site oficial ativo com título “Discra Distribuidora” e botão WhatsApp público wa.me/551146054694.',
      'redes':'Pesquisa pública disponível neste ciclo: web_search/Firecrawl falhou por billing, então foi usado acesso direto ao site oficial. O HTML confirmou Discra Distribuidora e link WhatsApp público; formulário informa venda para supermercados, mercados, padarias e restaurantes.',
      'segmento':'Distribuidora B2B para supermercados, mercados, padarias e restaurantes, com equipe comercial grande, venda por vendedores externos e sem loja virtual.',
      'motivo':'Passa no crivo MQL: o formulário informa distribuidora atendendo supermercados, mercados, padarias e restaurantes, +151 pessoas, 21 a 100 vendedores internos/externos, sem loja virtual e dúvida sobre autosserviço. O site oficial confirma a Discra Distribuidora e WhatsApp comercial público.',
      'insight':'mercados, padarias e restaurantes consultarem catálogo, preço e disponibilidade para recomprar sem depender de cada vendedor externo ou atendimento manual',
      'telefone_publico':'WhatsApp público no site oficial: +55 11 4605-4694; telefone do formulário veio incompleto, por isso foi usado o número público oficial.',
      'whatsapp_publico':'wa.me/551146054694 no site oficial discra.com.br',
    }
    lead={'email':email,'phone':phone,'firstname':first,'company':company,'createdate':p.get('createdate'),'phone_valid':True,'properties':p}
    slug,pdf,pretty=pg.generate_pdf(lead, research, sender)
    thumb=pg.gen_thumb(pdf, slug)
    text=f'Boa tarde, {first}, tudo bem? {sig}.\n\nFiz uma análise prévia do potencial da digitalização B2B do seu negócio.'
    question='Como você imagina que a Zydon poderia te apoiar?'
    r1, attempts1=pg.post_bridge_with_retries(port, '/send', {'to':jid,'text':text}, attempts=3, delay=12)
    if not pg.message_ok(r1): raise RuntimeError(f'falha texto Discra: {r1}')
    time.sleep(60)
    r2, attempts2=pg.post_bridge_with_retries(port, '/send-file', {'to':jid,'filePath':str(pretty),'fileName':f'{company} - Potencial de Digitalizacao B2B.pdf','thumbnailPath':thumb}, attempts=3, delay=12)
    if not pg.message_ok(r2): raise RuntimeError(f'falha PDF Discra: {r2}')
    time.sleep(30)
    r3, attempts3=pg.post_bridge_with_retries(port, '/send', {'to':jid,'text':question}, attempts=3, delay=12)
    if not pg.message_ok(r3): raise RuntimeError(f'falha pergunta Discra: {r3}')
    group_text=(f'✅ Lead qualificado\nEmpresa: {company}\nContato: {first}\nEmail: {email}\nERP informado: {p.get("qual_erp_utiliza_") or p.get("selecione_o_sistema_de_gesto_erp") or "não informado"}\nEntrada: {created_brt(p)}\nCriativo/origem: {source_line(p)}\n\nPor que qualificou:\n• Distribuidora B2B para supermercados, mercados, padarias e restaurantes.\n• Formulário indica +151 pessoas, 21 a 100 vendedores e venda externa/manual.\n• Site oficial confirmou Discra Distribuidora e WhatsApp comercial público.\n\nResponsável: {sender if owner in pg.OWNER_MAP else "sem SDR definido"}\nDiagnóstico enviado por: {sender}')
    gport, gresp, gattempts=notify_group(group_text)
    task_id=None
    try:
        task_id=pg.create_task(cid, deals, "WhatsApp — Diagnóstico 'Potencial de Digitalização B2B' enviado ao lead.", 'Diagnóstico enviado. '+research['motivo'], owner if owner in pg.OWNER_MAP else None)
    except Exception as e: task_id=f'erro: {e}'
    agenda_text=f'Se quiser garantir o melhor horário para um diagnóstico completo, pode marcar direto aqui: {agenda}' if agenda else ''
    if agenda_text:
        enqueue_agenda({'due_at':time.time()+20*60,'email':email,'contact_id':cid,'deal_id':deals[0] if deals else '', 'jid':jid,'port':port,'owner_id':owner,'text':agenda_text,'question_message_id':(r3 or {}).get('messageId'),'status':'pending'})
    append_wpp({'date':now_brt(),'date_tz':now_iso_brt(),'email':email,'contact_id':cid,'deal_id':','.join(deals),'slug':slug,'status':'enviado_lead','to':jid,'bridge_port':port,'owner_id':owner,'empresa':company,'phone':phone,'phone_source':'site oficial discra.com.br','fallback_note':fallback_note,'text':text,'question_text':question,'agenda_text':agenda_text,'pdf_path':str(pretty),'text_response':r1,'file_response':r2,'question_response':r3,'group_summary_response':gresp,'group_bridge_port':gport,'task_id':task_id,'owner_wait_notes':notes})
    append_processed(email, slug, 'enviado_lead', phone, company)
    return f'✅ MQL enviado: {company} ({email}) por {sender}; PDF {Path(pretty).name}'

def main():
    results=[]
    results.append(non_mql('232056473513','Sem evidência confiável de ICP B2B recorrente; formulário veio com campos essenciais inconsistentes/garbled e o domínio informado não abriu.',[
        'Campos do formulário vieram inconsistentes para segmento e forma de venda.',
        'Domínio informado não abriu no ciclo e não confirmou operação pública.',
        'Mesmo com faturamento alto informado, faltou evidência clara de distribuidor/atacado/indústria B2B recorrente.'
    ]))
    results.append(non_mql('231173178447','Pendente/Não-MQL fail-closed: domínio tankforce.com está estacionado/à venda e formulário indica operação pequena sem ICP claro de distribuição/atacado.',[
        'Domínio público direciona para página de venda de domínio, não para site da empresa.',
        'Porte informado é pequeno e venda atual “Marketing”, com loja virtual já existente.',
        'Não houve confirmação de distribuidora/atacado/indústria com pedido recorrente.'
    ]))
    results.append(send_discra())
    results.append(non_mql('232023613298','Formulário interno/sem dados comerciais suficientes; e-mail Gmail, sem domínio corporativo e sem telefone válido.',[
        'Entrada identificada como formulário interno.',
        'Sem domínio corporativo/site público validável.',
        'Telefone veio inválido/incompleto e não há dados de ICP B2B.'
    ]))
    print('\n'.join(results))

if __name__=='__main__':
    main()
