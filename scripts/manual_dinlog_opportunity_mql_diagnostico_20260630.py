#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rafael 2026-06-30: lifecycle=opportunity deve seguir diagnóstico/follow-up.
Dinlog estava como Não-MQL no crivo, mas HubSpot já está opportunity; tratar como nova oportunidade e enviar diagnóstico.
"""
import json, os, re, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJ=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ/'scripts'))
import process_gate_once as p  # noqa

EMAIL='gru.vcp.santos@grupodin.com.br'

PROPS=['firstname','lastname','email','company','phone','hs_whatsapp_phone_number','hs_searchable_calculated_phone_number','lifecyclestage','hs_lead_status','hubspot_owner_id','createdate','lastmodifieddate','recent_conversion_date','recent_conversion_event_name','num_conversion_events','num_unique_conversion_events','hs_object_source','hs_object_source_label','hs_analytics_source','hs_latest_source','hs_analytics_source_data_1','hs_latest_source_data_2','qual_erp_utiliza_','selecione_o_sistema_de_gesto_erp','qual_o_faturamento_anual_da_sua_empresa_','qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados','de_qual_forma_mais_vende_hoje_em_dia','quantas_pessoas_atuam_na_sua_empresa','quantos_vendedores_internos_sua_empresa_possui','vende_em_loja_virtual_','voc_acredita_que_o_seu_cliente_compraria_sozinho_na_sua_loja_24h_por_dia_sem_precisar_de_vendedor']

RESEARCH={
 'slug':'dinlog-logistica-aduaneira-luiz-guimaraes',
 'mql':True,
 'empresa_real':'Dinlog Armazém e Logística Aduaneira Integrada LTDA — empresa B2B real de logística retroportuária/aduaneira com operação em Santos, GRU/VCP e atendimento nacional.',
 'dominio_site':'grupodin.com.br — site oficial ativo confirmado no ciclo anterior, com serviços de carga geral fracionada, carga solta, container, aéreo nacional, armazém, pesados/indivisíveis, embalagem/exportação, telefones e e-mail corporativo.',
 'redes':'Pesquisa pública anterior validou site oficial do Grupo Din/Dinlog. Rafael definiu nova regra: lead em lifecycle opportunity deve ser tratado como oportunidade comercial para diagnóstico/follow-up, não como régua Não-MQL.',
 'segmento':'Serviços logísticos/aduaneiros B2B para empresas de importação/exportação e cargas; oportunidade comercial já aberta no HubSpot.',
 'motivo':'Override por regra operacional Rafael: como o contato está em lifecycle opportunity no HubSpot, considerar como nova oportunidade para follow-up e diagnóstico. Não disparar régua Não-MQL; seguir diagnóstico para aproveitar a oportunidade comercial já aberta.',
 'insight':'clientes de importação/exportação acompanharem solicitações, condições e histórico operacional em um portal B2B, reduzindo dependência de telefone/planilhas e centralizando pedidos/consultas comerciais',
 'telefone_publico':'Telefone celular válido recebido no HubSpot/formulário: +55 13 98127-2139.',
 'whatsapp_publico':'Usar o celular válido recebido no HubSpot/formulário: +55 13 98127-2139.',
}

def token():
 env=Path('/root/.hermes/credentials/hubspot.env')
 txt=env.read_text(encoding='utf-8', errors='ignore') if env.exists() else ''
 m=re.search(r'(pat-[A-Za-z0-9_\-]+|[A-Za-z0-9_\-.]{80,})', txt)
 return os.environ.get('HUBSPOT_PRIVATE_APP_TOKEN') or (m.group(1) if m else '')

def hs_search(email):
 body={'filterGroups':[{'filters':[{'propertyName':'email','operator':'EQ','value':email}]}],'properties':PROPS,'limit':1}
 req=urllib.request.Request('https://api.hubapi.com/crm/v3/objects/contacts/search',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+token(),'Content-Type':'application/json'},method='POST')
 data=json.loads(urllib.request.urlopen(req,timeout=30).read().decode())
 if not data.get('results'): raise SystemExit('contato não encontrado')
 return data['results'][0]

def lead_for(email):
 c=hs_search(email); props=c.get('properties') or {}
 phone=props.get('hs_searchable_calculated_phone_number') or props.get('hs_whatsapp_phone_number') or props.get('phone') or ''
 return {'id':c['id'],'email':email,'firstname':props.get('firstname') or '','lastname':props.get('lastname') or '','company':props.get('company') or '','phone':phone,'phone_valid':bool(p.phone_variants_with_optional_9(phone)),'phone_invalid_reason':'' if p.phone_variants_with_optional_9(phone) else 'sem telefone BR normalizável','createdate':props.get('createdate') or '','gate_trigger':'manual_hubspot_mql','hs_lastmodifieddate':props.get('lastmodifieddate') or '','properties':props,'manual_override_by':'Rafael Calixto','manual_override_reason':'Lifecycle opportunity deve seguir diagnóstico/follow-up; não tratar como Não-MQL.'}

def mark_controls(email, cid):
 now=datetime.now(timezone.utc).isoformat()
 for rel in ['controle/mql_pipeline_queue.json','controle/pending_lead_alerts.json']:
  path=PROJ/rel
  try: data=json.loads(path.read_text(encoding='utf-8'))
  except Exception: continue
  if rel.endswith('mql_pipeline_queue.json'):
   items=data.get('items') if isinstance(data,dict) else []
   for it in items:
    if isinstance(it,dict) and (str(it.get('email','')).lower()==email or str(it.get('contact_id',''))==str(cid)):
     it['state']='mql_opportunity_diagnostico_autorizado'; it['mql_confirmed']=True; it['diagnostic_allowed']=True; it['updated_at']=now
     it.setdefault('events',[]).append({'at':now,'state':'mql_opportunity_diagnostico_autorizado','reason':'Rafael: opportunity também segue diagnóstico/follow-up.'})
  else:
   row=data.get(email) if isinstance(data,dict) else None
   if isinstance(row,dict):
    row['channel']='final_analysis_completed'; row['final_status']='mql_opportunity_diagnostico_autorizado'; row['finalized_at']=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'); row['final_reason']='Lifecycle opportunity: Rafael autorizou seguir diagnóstico/follow-up.'
  path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
 p.RESEARCH[EMAIL]=RESEARCH
 lead=lead_for(EMAIL)
 mark_controls(EMAIL, lead['id'])
 payload={'generated_at':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),'count':1,'cutoff_window_h':24,'manual_reclassification':True,'leads':[lead],'duplicates':[]}
 Path('/tmp/gate_qualified.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
 print('gate manual opportunity escrito:', EMAIL, flush=True)
 p.main()

if __name__=='__main__': main()
