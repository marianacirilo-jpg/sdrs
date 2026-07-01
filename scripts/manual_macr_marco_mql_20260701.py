#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Override Rafael 2026-07-01: Macr desenvolvimento / Marco Aurélio é MQL.
Form de demonstração com atacadista/lojista, Olist/Tiny, faturamento 500k-1M, 2-5 vendedores, loja virtual.
"""
import json, os, re, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJ=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJ/'scripts'))
import process_gate_once as p  # noqa

EMAIL='macr@mcstorefornecedor.com'
RESEARCH={
 'slug':'macr-desenvolvimento-marco-aurelio',
 'mql': True,
 'empresa_real':'Macr desenvolvimento / MC Store Fornecedor — lead de formulário de demonstração; Marco Aurélio informa atuação atacadista/lojista, ERP Olist/Tiny, faturamento R$500 mil a R$1 milhão/ano, 2 a 5 vendedores internos, loja virtual e venda por ads/grupos de WhatsApp.',
 'dominio_site':'mcstorefornecedor.com — domínio profissional informado no formulário; contexto do anúncio/landing indica loja online/fornecedor para varejo.',
 'redes':'Rafael confirmou explicitamente: “Esse é também”. Regra vigente: leads recentes dos anúncios com dúvida comercial mínima devem seguir como MQL; follow-ups qualificam mais.',
 'segmento':'Atacadista/lojista/fornecedor com loja online e venda via Ads/grupos de WhatsApp; potencial B2B para portal de pedidos, catálogo, tabela e compra autônoma 24h.',
 'motivo':'MQL confirmado por Rafael. O formulário traz sinais fortes: atacadista/lojista, Olist/Tiny, faturamento 500k-1M, 2-5 vendedores, loja virtual e dor de vendedor digitar pedido manualmente para loja online de varejo.',
 'insight':'permitir que lojistas/atacadistas consultem catálogo, condições, disponibilidade e façam pedidos 24h sem depender do vendedor digitar manualmente pedidos vindos de ads e grupos de WhatsApp',
 'telefone_publico':'Telefone informado no HubSpot/formulário: +55 62 98583-7695.',
 'whatsapp_publico':'Usar WhatsApp informado no HubSpot/formulário: +55 62 98583-7695.'
}
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

def token():
 env=Path('/root/.hermes/credentials/hubspot.env')
 if os.environ.get('HUBSPOT_PRIVATE_APP_TOKEN'): return os.environ['HUBSPOT_PRIVATE_APP_TOKEN']
 if env.exists():
  for line in env.read_text(encoding='utf-8',errors='ignore').splitlines():
   m=re.match(r'\s*(?:export\s+)?(?:HUBSPOT_PRIVATE_APP_TOKEN|HUBSPOT_TOKEN|HUBSPOT_API_KEY)=["\']?([^"\'\s]+)',line)
   if m: return m.group(1)
 return ''

def hs_search(email):
 body={'filterGroups':[{'filters':[{'propertyName':'email','operator':'EQ','value':email}]}],'properties':PROPS,'limit':1}
 req=urllib.request.Request('https://api.hubapi.com/crm/v3/objects/contacts/search',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+token(),'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=30) as resp: data=json.loads(resp.read().decode())
 rows=data.get('results') or []
 if not rows: raise SystemExit(f'contato não encontrado: {email}')
 return rows[0]

def update_controls(email, cid):
 now=datetime.now(timezone.utc).isoformat()
 path=PROJ/'controle/mql_pipeline_queue.json'
 try: data=json.loads(path.read_text(encoding='utf-8'))
 except Exception: data={'items':[]}
 items=data.get('items') if isinstance(data,dict) else []
 matched=False
 for it in items:
  if isinstance(it,dict) and (str(it.get('email','')).lower()==email or str(it.get('contact_id',''))==str(cid)):
   it['state']='mql_confirmado_rafael_manual'; it['mql_confirmed']=True; it['diagnostic_allowed']=True; it['updated_at']=now
   it.setdefault('events',[]).append({'at':now,'state':'mql_confirmado_rafael_manual','reason':'Rafael confirmou: “Esse é também”.'})
   matched=True
 if not matched:
  items.append({'key':email+'|manual_rafael_mql_20260701','events':[{'at':now,'state':'mql_confirmado_rafael_manual','reason':'Rafael confirmou: “Esse é também”.'}],'updated_at':now,'state':'mql_confirmado_rafael_manual','email':email,'contact_id':cid,'mql_confirmed':True,'diagnostic_allowed':True})
 if isinstance(data,dict): data['items']=items; out=data
 else: out=items
 path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 path=PROJ/'controle/pending_lead_alerts.json'
 try: alerts=json.loads(path.read_text(encoding='utf-8'))
 except Exception: alerts={}
 row=alerts.get(email)
 if isinstance(row,dict):
  row['channel']='final_analysis_completed'; row['final_status']='mql_confirmado_rafael_manual'; row['finalized_at']=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'); row['final_reason']='Rafael confirmou MQL no Discord; diagnóstico autorizado.'
 path.write_text(json.dumps(alerts,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
 c=hs_search(EMAIL); props=c.get('properties') or {}
 phone=props.get('hs_searchable_calculated_phone_number') or props.get('hs_whatsapp_phone_number') or props.get('mobilephone') or props.get('phone') or ''
 p.RESEARCH[EMAIL]=dict(RESEARCH)
 lead={'id':c.get('id'),'email':EMAIL,'firstname':props.get('firstname') or '','lastname':props.get('lastname') or '',
       'company':props.get('company') or '','phone':phone,'phone_valid':bool(p.phone_variants_with_optional_9(phone)),
       'phone_invalid_reason':'' if p.phone_variants_with_optional_9(phone) else 'sem telefone BR normalizável',
       'createdate':props.get('createdate') or '','gate_trigger':'manual_hubspot_mql','hs_lastmodifieddate':props.get('lastmodifieddate') or '',
       'properties':props,'manual_override_by':'Rafael Calixto','manual_override_reason':'Rafael confirmou: Esse é também.'}
 update_controls(EMAIL, lead['id'])
 payload={'generated_at':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),'count':1,'cutoff_window_h':24,'manual_reclassification':True,'leads':[lead],'duplicates':[]}
 Path('/tmp/gate_qualified.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
 print('gate manual escrito:', EMAIL, flush=True)
 p.main()

if __name__=='__main__': main()
