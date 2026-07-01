#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regra Rafael 2026-07-01: em dúvida inicial/pending_review, considerar MQL.
Casos do print HubSpot: Saboratto e Coruja Brindes.
"""
import json, os, re, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJ=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJ/'scripts'))
import process_gate_once as p  # noqa

PROPS=[
 'firstname','lastname','email','company','phone','mobilephone','hs_whatsapp_phone_number','hs_searchable_calculated_phone_number',
 'lifecyclestage','hs_lead_status','hubspot_owner_id','createdate','lastmodifieddate','recent_conversion_date','recent_conversion_event_name',
 'num_conversion_events','num_unique_conversion_events','hs_object_source','hs_object_source_label','hs_analytics_source','hs_latest_source',
 'hs_analytics_source_data_1','hs_latest_source_data_2','qual_erp_utiliza_','selecione_o_sistema_de_gesto_erp',
 'qual_o_faturamento_anual_da_sua_empresa_','e_qual_faturamento_anual_da_sua_empresa',
 'qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados','de_qual_forma_mais_vende_hoje_em_dia',
 'quantas_pessoas_atuam_na_sua_empresa','quantos_vendedores_internos_sua_empresa_possui','vende_em_loja_virtual_',
 'voc_acredita_que_o_seu_cliente_compraria_sozinho_na_sua_loja_24h_por_dia_sem_precisar_de_vendedor',
 'qual_seria_o_maior_problema_que_voc_enfrenta_em_sua_operao_atualmente'
]

CASES={
 'saboratto@saboratto.com.br': {
  'slug':'saboratto-alimentos-pedro-zanella',
  'empresa_real':'Saboratto — loja/indústria/comércio de temperos e alimentos, lead Facebook com ERP Bling; aprovado como MQL pela regra Rafael de dúvida inicial.',
  'dominio_site':'saboratto.com.br — site/loja virtual identificado no ciclo automático; havia dúvida entre varejo/D2C e possível operação B2B de alimentos/temperos.',
  'redes':'O automático reprovou por fail-closed por faturamento baixo e comunicação de varejo. Rafael definiu que, neste primeiro momento, quando houver dúvida/pending_review deve considerar MQL para diagnóstico comercial.',
  'segmento':'Alimentos/temperos com loja virtual e potencial de venda recorrente B2B para food service, revendas, empórios ou pequenos varejos a validar.',
  'motivo':'MQL por regra Rafael: caso dúbio/pending_review deve seguir como MQL. Há empresa real, ERP Bling, produto físico e loja virtual; o diagnóstico vai validar se existe canal B2B/recorrência além do D2C.',
  'insight':'empórios, restaurantes ou revendas acessarem catálogo de temperos, condições comerciais e reposição por portal 24h sem depender de atendimento manual',
  'telefone_publico':'Telefone recebido no HubSpot/formulário: +55 55 99728-2808.',
  'whatsapp_publico':'Usar telefone informado no HubSpot/formulário: +55 55 99728-2808.'
 },
 'jean@corujabrindes.com.br': {
  'slug':'coruja-brindes-jean-souza',
  'empresa_real':'Coruja Brindes — empresa real B2B de brindes; aprovada como MQL pela regra Rafael de dúvida inicial.',
  'dominio_site':'corujabrindes.com.br — operação de brindes/produtos personalizados; havia dúvida sobre recorrência/abastecimento para revendas, mas empresa é B2B e tem produto físico.',
  'redes':'O automático deixou pendente por falta de prova clara de reposição/abastecimento recorrente. Rafael definiu que, em dúvida inicial, considerar MQL para diagnóstico.',
  'segmento':'Brindes corporativos/produtos personalizados para empresas, com potencial de catálogo, orçamento, recorrência de campanhas e pedidos por portal B2B.',
  'motivo':'MQL por regra Rafael: em caso pendente/dúbio, considerar MQL. Coruja Brindes é empresa real B2B de produto físico; diagnóstico vai validar recorrência e canal de pedidos.',
  'insight':'clientes corporativos consultarem catálogo de brindes, personalizações, prazos e pedidos recorrentes por um portal, reduzindo orçamento manual por WhatsApp',
  'telefone_publico':'Telefone recebido no HubSpot/formulário: +55 11 99254-7634.',
  'whatsapp_publico':'Usar telefone informado no HubSpot/formulário: +55 11 99254-7634.'
 }
}

def token():
 env=Path('/root/.hermes/credentials/hubspot.env')
 if os.environ.get('HUBSPOT_PRIVATE_APP_TOKEN'): return os.environ['HUBSPOT_PRIVATE_APP_TOKEN']
 if env.exists():
  for line in env.read_text(encoding='utf-8',errors='ignore').splitlines():
   m=re.match(r'\s*(?:export\s+)?(?:HUBSPOT_PRIVATE_APP_TOKEN|HUBSPOT_TOKEN|HUBSPOT_API_KEY)=["\']?([^"\'\s]+)',line)
   if m: return m.group(1)
 return ''

def hs_search(email):
 body={'filterGroups':[{'filters':[{'propertyName':'email','operator':'EQ','value':email}]}],'properties':PROPS,'limit':10}
 req=urllib.request.Request('https://api.hubapi.com/crm/v3/objects/contacts/search',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+token(),'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=30) as resp: data=json.loads(resp.read().decode())
 rows=data.get('results') or []
 if not rows: raise SystemExit(f'contato não encontrado: {email}')
 return rows[0]

def lead_for(email):
 c=hs_search(email); props=c.get('properties') or {}
 phone=props.get('hs_searchable_calculated_phone_number') or props.get('hs_whatsapp_phone_number') or props.get('mobilephone') or props.get('phone') or ''
 return {'id':c.get('id'),'email':email,'firstname':props.get('firstname') or '','lastname':props.get('lastname') or '',
  'company':props.get('company') or '','phone':phone,'phone_valid':bool(p.phone_variants_with_optional_9(phone)),
  'phone_invalid_reason':'' if p.phone_variants_with_optional_9(phone) else 'sem telefone BR normalizável',
  'createdate':props.get('createdate') or '','gate_trigger':'manual_hubspot_mql','hs_lastmodifieddate':props.get('lastmodifieddate') or '',
  'properties':props,'manual_override_by':'Rafael Calixto','manual_override_reason':'Rafael definiu: em dúvida inicial/pending_review, considerar MQL.'}

def update_jsons(email, cid):
 now=datetime.now(timezone.utc).isoformat()
 # pipeline
 path=PROJ/'controle/mql_pipeline_queue.json'
 try: data=json.loads(path.read_text(encoding='utf-8'))
 except Exception: data={'items':[]}
 items=data.get('items') if isinstance(data,dict) else (data if isinstance(data,list) else [])
 matched=False
 for it in items:
  if isinstance(it,dict) and (str(it.get('email','')).lower()==email or str(it.get('contact_id',''))==str(cid)):
   it['state']='mql_confirmado_regra_duvida_rafael'; it['mql_confirmed']=True; it['diagnostic_allowed']=True; it['updated_at']=now; it['previous_auto_state']=it.get('state')
   it.setdefault('events',[]).append({'at':now,'state':'mql_confirmado_regra_duvida_rafael','reason':'Rafael: em dúvida inicial/pending_review, considerar MQL.'}); matched=True
 if not matched:
  items.append({'key':email+'|manual_regra_duvida','events':[{'at':now,'state':'mql_confirmado_regra_duvida_rafael','reason':'Rafael: em dúvida inicial/pending_review, considerar MQL.'}], 'updated_at':now,'state':'mql_confirmado_regra_duvida_rafael','email':email,'contact_id':cid,'mql_confirmed':True,'diagnostic_allowed':True})
 if isinstance(data,dict): data['items']=items; out=data
 else: out=items
 path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 # pending alerts
 path=PROJ/'controle/pending_lead_alerts.json'
 try: alerts=json.loads(path.read_text(encoding='utf-8'))
 except Exception: alerts={}
 row=alerts.get(email) or next((v for k,v in alerts.items() if isinstance(v,dict) and str(v.get('email','')).lower()==email), None)
 if isinstance(row,dict):
  row['channel']='final_analysis_completed'; row['final_status']='mql_confirmado_regra_duvida_rafael'; row['finalized_at']=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'); row['final_reason']='Rafael: em dúvida inicial/pending_review, considerar MQL; reclassificado para diagnóstico.'
 path.write_text(json.dumps(alerts,ensure_ascii=False,indent=2),encoding='utf-8')
 # supersede old ledger statuses
 path=PROJ/'controle/wpp_envios.json'
 try: w=json.loads(path.read_text(encoding='utf-8'))
 except Exception: return
 rows=w.get('envios') if isinstance(w,dict) else (w if isinstance(w,list) else [])
 for r in rows:
  if isinstance(r,dict) and str(r.get('email','')).lower()==email and str(r.get('status','')).lower() in {'nao_mql_grupo','pendente_revisao_mql'}:
   r['status']='superseded_by_regra_duvida_mql'; r['superseded_at']=now; r['superseded_reason']='Rafael: em dúvida inicial/pending_review, considerar MQL.'
 if isinstance(w,dict): w['envios']=rows; out=w
 else: out=rows
 path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
 leads=[]
 for email,research in CASES.items():
  r=dict(research); r['mql']=True; p.RESEARCH[email]=r
  lead=lead_for(email); update_jsons(email, lead['id']); leads.append(lead)
 payload={'generated_at':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),'count':len(leads),'cutoff_window_h':24,'manual_reclassification':True,'leads':leads,'duplicates':[]}
 Path('/tmp/gate_qualified.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
 print('gate manual escrito:', ', '.join([x['email'] for x in leads]), flush=True)
 p.main()

if __name__=='__main__': main()
