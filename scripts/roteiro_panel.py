#!/usr/bin/env python3
"""Roteiro Comercial Zydon — app standalone para roteiro.zydon.com.br.

Não é Channel. Porta padrão: 8290.
Wizard Next > Next para demonstração conforme diagnóstico HubSpot.
"""
from __future__ import annotations
import argparse, base64, hashlib, hmac, html, http.cookies, json, os, re, secrets, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PROJECT=Path('/root/.hermes/zydon-prospeccao')
USERS_FILE=PROJECT/'controle'/'channel_users.json'
ROTEIRO_FILE=PROJECT/'controle'/'roteiro_comercial.json'
ROTEIRO_AUDIT_FILE=PROJECT/'controle'/'roteiro_comercial_audit.jsonl'
RUNS_FILE=PROJECT/'controle'/'roteiro_presentation_runs.jsonl'
SECRET_FILE=PROJECT/'controle'/'roteiro_session_secret.txt'
BEST_FILE=PROJECT/'controle'/'roteiro_best_practices.json'
GOOGLE_ENV=Path('/root/.hermes/credentials/google_oauth.env')
HUBSPOT_ENV=Path('/root/.hermes/credentials/hubspot.env')
LOGO_PATH=PROJECT/'motor'/'logo'/'zydon_full_black.png'
HUBSPOT_API='https://api.hubapi.com'; HUBSPOT_PORTAL_ID='48590774'; HUBSPOT_PIPELINE_ID='671008549'
INTRODUCTION_STAGE_ID='1269308723'; DIAGNOSTICO_EC_STAGE_ID='1269710168'; PRESENTATION_STAGE_ID='990617426'; TECHNICAL_STAGE_ID='1269308724'
PROPOSAL_STAGE_ID='984052831'; TERMS_STAGE_ID='1213797817'; CLOSED_WON_STAGE_ID='984052834'
ROTEIRO_STAGES={INTRODUCTION_STAGE_ID:'Introdução',DIAGNOSTICO_EC_STAGE_ID:'Diagnóstico EC',PRESENTATION_STAGE_ID:'Apresentação Comercial 🎯',TECHNICAL_STAGE_ID:'Apresentação Técnica 💻',PROPOSAL_STAGE_ID:'Proposta / Negociação',TERMS_STAGE_ID:'Termos e condições',CLOSED_WON_STAGE_ID:'Negócio fechado'}
PRESENTATION_STAGES={PRESENTATION_STAGE_ID:'Apresentação Comercial 🎯',TECHNICAL_STAGE_ID:'Apresentação Técnica 💻'}
ROTEIRO_EXECUTIVE_OWNER_LABELS={'86020066':'João Vitor','89412201':'Samara','82229596':'Edimilson','89459433':'Ítalo'}
ROTEIRO_EXECUTIVE_OWNER_IDS=set(ROTEIRO_EXECUTIVE_OWNER_LABELS.keys())
# Roteiro owner scope: João Vitor, Samara, Edimilson ou Ítalo.
HUBSPOT_OWNER_LABELS={'86265630':'Breno','88063842':'Sarah','85778446':'Lucas Batista','76764091':'Lucas Batista',**ROTEIRO_EXECUTIVE_OWNER_LABELS}
SESSION_COOKIE='zydon_roteiro_session'; OAUTH_STATE_COOKIE='zydon_roteiro_oauth_state'; SESSION_TTL=7*24*3600; OAUTH_STATE_TTL=3600
ROTEIRO_VIEW_ALL_UIDS={'rafael','lucas_resende'}; GROWTH_ROLES={'growth','growth_leader','leader_growth','lider_growth','líder_growth','head_growth','growth_head'}

FORM_FIELD_LABELS={
 'qual_erp_utiliza_':'ERP utilizado','selecione_o_sistema_de_gesto_erp':'ERP utilizado','vende_em_loja_virtual_':'Vende em loja virtual',
 'voc_acredita_que_o_seu_cliente_compraria_sozinho_na_sua_loja_24h_por_dia_sem_precisar_de_vendedor':'Cliente compraria sozinho 24h?',
 'qual_o_faturamento_anual_da_sua_empresa_':'Faturamento anual','e_qual_faturamento_anual_da_sua_empresa':'Faturamento anual','selecione_a_faixa_de_faturamento':'Faturamento anual',
 'principais_dores':'Principais dores','qual_seria_o_maior_problema_que_voc_enfrenta_em_sua_operao_atualmente':'Maior problema operacional',
 'quantas_pessoas_atuam_na_sua_empresa':'Pessoas na empresa','quantos_vendedores_internos_sua_empresa_possui':'Vendedores internos','de_qual_forma_mais_vende_hoje_em_dia':'Forma de venda predominante'}
CONTACT_BASIC=['firstname','lastname','email','company','phone','mobilephone','hs_whatsapp_phone_number','hubspot_owner_id']
CONTACT_FORM_KEYS=list(FORM_FIELD_LABELS.keys()); CONTACT_PROPS=CONTACT_BASIC+CONTACT_FORM_KEYS
COMPANY_PROPS=['name','domain','website','industry','city','state','description']
ERP_KEYS=['qual_erp_utiliza_','selecione_o_sistema_de_gesto_erp']; FAT_KEYS=['selecione_a_faixa_de_faturamento','qual_o_faturamento_anual_da_sua_empresa_','e_qual_faturamento_anual_da_sua_empresa']
DOR_KEYS=['principais_dores','qual_seria_o_maior_problema_que_voc_enfrenta_em_sua_operao_atualmente']
# Engajamentos HubSpot associados ao negócio (notas, tarefas, atividades) para enriquecer o roteiro.
ENGAGEMENT_PROPS={
 'notes':['hs_note_body','hs_timestamp','hs_createdate'],
 'tasks':['hs_task_subject','hs_task_body','hs_task_status','hs_task_type','hs_timestamp'],
 'calls':['hs_call_title','hs_call_body','hs_timestamp'],
 'meetings':['hs_meeting_title','hs_meeting_body','hs_meeting_start_time','hs_timestamp'],
 'emails':['hs_email_subject','hs_email_text','hs_email_html','hs_timestamp'],
}
ENGAGEMENT_LABELS={'notes':'Nota','tasks':'Tarefa','calls':'Ligação','meetings':'Reunião','emails':'E-mail'}
DIAGNOSTIC_PAT=re.compile(r'diagn[oó]stico|diagnostico|\bmql\b|resumo|diagn[oó]stico\s+ec|diagn[oó]stico\s+sdr',re.I)
FOLLOWUP_PAT=re.compile(r'pr[oó]ximo\s+passo|follow|retorno|proposta|no[\s-]?show|reuni[ãa]o|apresenta[çc][ãa]o',re.I)

BASE_PHASES=[
 {'id':'diagnostico','title':'Diagnóstico antes da tela','screen':'Estratégia','when':'Sempre','preQuestions':['Qual gargalo mais atrapalha venda recorrente hoje?','Pedido nasce em WhatsApp, planilha, ligação, vendedor ou portal?','Que regra comercial não pode quebrar: tabela, pagamento, limite ou estoque?'],'show':'Não abrir produto ainda. Confirmar diagnóstico e critério de valor da reunião.','value':'A demo deixa de ser tour e vira prova da hipótese de valor.','successCheck':'Diagnóstico e prioridade de valor confirmados.'},
 {'id':'erp','title':'Condicional ERP e dados conectados','screen':'Estratégia','when':'Quando usa Bling, Omie, Olist/Tiny ou Sankhya','preQuestions':['O ERP concentra pedido, tabela, estoque e financeiro?','Quais dados precisam aparecer iguais na plataforma?'],'show':'Abrir explicando integração, histórico e regras que vêm do ERP.','value':'Reduz retrabalho e aproxima a demo da operação real.','successCheck':'ERP e regras críticas mapeados.'},
 {'id':'cliente_vitrine','title':'Portal do Cliente: vitrine B2B','screen':'Cliente','when':'Sempre','preQuestions':['Seu cliente compra por catálogo, recompra ou indicação do vendedor?','Ele precisa ver preço antes do login ou só catálogo público?'],'show':'Vitrine, categorias, banners, busca, produtos mais comprados, últimos pedidos e detalhes.','value':'Cliente compra sozinho sem depender do vendedor para pedido repetido.','successCheck':'Cliente entendeu como encontra e compra produtos.'},
 {'id':'cliente_acesso','title':'Acesso, CNPJ e acordos comerciais','screen':'Cliente','when':'Sempre','preQuestions':['Um comprador representa várias empresas/CNPJs?','Cada cliente tem tabela, desconto e pagamento diferente?'],'show':'Solicitação de acesso, login, múltiplos CNPJs, mudança de acordo comercial, preço e desconto.','value':'Mostra personalização B2B real por cliente, não e-commerce genérico.','successCheck':'Regras de cliente/CNPJ validadas.'},
 {'id':'pedido_checkout','title':'Pedido rápido e checkout','screen':'Cliente','when':'Sempre','preQuestions':['Pedido recorrente vem em planilha, foto, texto ou lista?','Qual regra impede pedido errado: estoque, unidade, operação, pagamento ou crédito?'],'show':'Pedido rápido com IA/planilha, carrinho, frete, pagamento, limite de crédito e conclusão.','value':'Menos erro, menos digitação e pedido completo dentro das regras.','successCheck':'Checkout conectado às regras comerciais.'},
 {'id':'pos_compra','title':'Pós-compra e financeiro','screen':'Cliente','when':'Sempre','preQuestions':['Quanto o time gasta respondendo status, boleto, NF e rastreio?','Cliente pede segunda via por WhatsApp?'],'show':'Meus pedidos, rastreio/status ERP, repetir pedido, boleto, XML/NF e financeiro.','value':'Autoatendimento reduz demanda operacional do comercial/financeiro.','successCheck':'Valor de autoatendimento validado.'},
 {'id':'whatsapp','title':'Zoe no WhatsApp','screen':'WhatsApp','when':'Quando WhatsApp é canal relevante ou dor envolve pedido manual','preQuestions':['Quanto do pedido hoje chega em áudio, foto ou texto?','O cliente quer consultar produto, status e financeiro pelo WhatsApp?'],'show':'Pedido via foto/áudio/texto; IA monta carrinho com preço e condição do cliente.','value':'Aproveita canal atual sem sacrificar regra comercial e rastreabilidade.','successCheck':'Uso do WhatsApp como canal validado.'},
 {'id':'vendedor','title':'Tela do Vendedor','screen':'Vendedor','when':'Quando há vendedores internos/força de vendas','preQuestions':['Os vendedores têm carteiras separadas?','Eles precisam dar desconto, montar proposta e acompanhar risco de cliente?'],'show':'Cadastro de clientes, acesso restrito à carteira, desconto/acréscimo, exportar proposta e análises.','value':'Aumenta produtividade do vendedor e gestão da carteira sem expor toda a base.','successCheck':'Necessidade da tela do vendedor confirmada.'},
 {'id':'admin','title':'Painel Admin e gestão','screen':'Admin','when':'Sempre','preQuestions':['Quem configura vitrine, banners, regras e acessos hoje?','Gestão precisa ver vendas, carrinhos, projeção e agente de IA?'],'show':'Construtor, Zydon Pay, relatórios, transações, projeção, carrinho abandonado, dashboards e solicitações.','value':'Admin controla operação e mede resultado sem depender de agência ou ticket.','successCheck':'Admin conectado ao controle da operação.'},
 {'id':'fechamento','title':'Fechamento e próximo passo','screen':'Estratégia','when':'Sempre','preQuestions':['Quais critérios definem sucesso para avançar?','Quem precisa participar da próxima validação?','Próximo passo é proposta, técnica ou decisores?'],'show':'Não demonstrar nova tela; resumir valor, gaps e próximo passo.','value':'Controla a reunião e transforma demo em avanço comercial.','successCheck':'Próximo passo objetivo combinado.'},
]

B2B_DIGITAL_CHALLENGES=[
 'Resistência do time comercial: medo de perder controle, carteira ou relacionamento.',
 'Condições personalizadas que não cabem em e-commerce genérico: tabela, desconto, prazo e política por cliente.',
 'Pedidos manuais que impedem escala: WhatsApp, ligação, planilha, foto e retrabalho no ERP.',
 'Integração com ERP: catálogo, preço, estoque, financeiro e status precisam bater com a operação.',
 'Gestão de crédito e aprovação por CNPJ: limite, bloqueio, múltiplas empresas e regras de aprovação.'
]
CHALLENGER_INTRO_PHASES=[
 {'id':'challenger_aquecimento','title':'1 · Aquecimento','screen':'Introdução','when':'Etapa Introdução','preQuestions':['Onde a digitalização B2B já travou na prática: time comercial, regra comercial, ERP, pedido manual ou crédito?','Qual parte da venda ainda depende demais de uma pessoa específica?'],'show':'Abrir com os 5 gargalos do mercado de distribuidoras e indústrias: resistência comercial; condições personalizadas; pedidos manuais; integração ERP; crédito/aprovação por CNPJ. Pedir concordância antes de avançar.','value':'Gerar reconhecimento: o executivo percebe que a Zydon entende o problema antes de falar de plataforma.','successCheck':'Cliente concordou com pelo menos 2 gargalos reais.'},
 {'id':'challenger_reestruturacao','title':'2 · Reestruturação','screen':'Introdução','when':'Etapa Introdução','preQuestions':['E se o problema não for “colocar loja no ar”, mas digitalizar as regras comerciais sem quebrar o vendedor?','Qual regra comercial hoje impede o cliente de comprar sozinho?'],'show':'Reestruturar a visão: e-commerce B2B não é vitrine bonita; é uma camada de execução comercial conectada ao ERP, carteira, condição, crédito e recorrência.','value':'Mudar o critério de compra: sair de “site/app” e ir para “escala comercial com regra e controle”.','successCheck':'Cliente aceitou olhar o problema por regra/escala, não por layout de loja.'},
 {'id':'challenger_angustia','title':'3 · Angústia controlada','screen':'Introdução','when':'Etapa Introdução','preQuestions':['Quanto pedido ainda precisa ser digitado duas vezes?','Quantos clientes deixam de comprar porque dependem do vendedor responder?','Quanto erro nasce de preço, estoque, CNPJ ou condição divergente?'],'show':'Quantificar com perguntas: tempo perdido em pedido manual, erro de digitação, vendedor virando tirador de pedido, cliente sem autoatendimento e aprovação travando faturamento.','value':'Criar tensão racional sem exagero: mostrar custo de manter a operação manual.','successCheck':'Cliente verbalizou custo, risco ou perda de escala.'},
 {'id':'challenger_impacto_emocional','title':'4 · Impacto emocional','screen':'Introdução','when':'Etapa Introdução','preQuestions':['O que acontece quando o melhor vendedor está ausente e o cliente precisa comprar?','Como fica a percepção do cliente quando preço/estoque/limite mudam no meio do pedido?'],'show':'Contar o cenário típico: vendedor sobrecarregado, cliente esperando no WhatsApp, financeiro bloqueando pedido no fim, gestor sem previsibilidade e concorrente digital ficando mais fácil de comprar.','value':'Transformar problema operacional em urgência executiva: perda de confiança, margem, recorrência e controle.','successCheck':'Cliente reconheceu impacto em cliente, vendedor ou gestão.'},
 {'id':'challenger_novo_caminho','title':'5 · Um novo caminho','screen':'Introdução','when':'Etapa Introdução','preQuestions':['Se o cliente comprasse sozinho sem perder tabela, crédito e regra comercial, o que mudaria no time?','Qual seria a primeira operação que deveria sair do manual?'],'show':'Apresentar o novo caminho sem demo profunda: portal B2B + vendedor + WhatsApp/IA + admin, todos respeitando ERP, CNPJ, tabela, pagamento e crédito. Encaminhar para diagnóstico/apresentação conforme maturidade.','value':'Criar ponte para a solução Zydon: primeiro concordamos com a tese; depois demonstramos a plataforma na etapa certa.','successCheck':'Próximo passo combinado: diagnóstico EC, apresentação comercial ou técnica.'},
]
def challenger_intro_context():
 return {'methodology':'A Venda Desafiadora / Challenger Sale','sourceSummary':'Modelo teach-tailor-take control com coreografia: Aquecimento, Reestruturação, Angústia Controlada, Impacto Emocional, Novo Caminho e Nossa Solução.','challenges':B2B_DIGITAL_CHALLENGES}

def _parse_env(path):
 out={}
 try:
  if path.exists():
   for line in path.read_text().splitlines():
    line=line.strip()
    if line and not line.startswith('#') and '=' in line:
     k,v=line.split('=',1); out[k.strip()]=v.strip().strip('"').strip("'")
 except Exception: pass
 return out

def google_config():
 cfg=_parse_env(GOOGLE_ENV); get=lambda k:(os.environ.get(k) or cfg.get(k) or '').strip()
 return {'client_id':get('ROTEIRO_GOOGLE_CLIENT_ID') or get('GOOGLE_CLIENT_ID'),'client_secret':get('ROTEIRO_GOOGLE_CLIENT_SECRET') or get('GOOGLE_CLIENT_SECRET')}
def google_configured():
 c=google_config(); return bool(c['client_id'] and c['client_secret'] and 'COLE_AQUI' not in c['client_id'])
def load_users():
 try: return json.loads(USERS_FILE.read_text())
 except Exception: return {}
def uid_from_email(email):
 email=str(email or '').strip().lower()
 if '@' not in email or not email.endswith('@zydon.com.br'): return None
 local=email.split('@',1)[0].split('+',1)[0]; users=load_users()
 for uid,cfg in users.items():
  if email in [str(e).lower() for e in (cfg.get('emails') or [])]: return uid
 aliases={'rafael':'rafael','rafael.calixto':'rafael','lucas.resende':'lucas_resende','lucas_resende':'lucas_resende','breno':'breno','sarah':'sarah','lucas.batista':'lucas_batista','lucas':'lucas_batista'}
 uid=aliases.get(local) or local
 return uid if uid in users else None
_OWNER_LABEL_CACHE={}
def hubspot_owner_labels(token):
 """Resolve owner id -> nome via HubSpot Owners API. Cache em memória por token. Nunca quebra."""
 token=str(token or '').strip()
 if not token: return {}
 if token in _OWNER_LABEL_CACHE: return _OWNER_LABEL_CACHE[token]
 labels={}; after=None
 try:
  while True:
   path='/crm/v3/owners?limit=100'+(f'&after={urllib.parse.quote(after)}' if after else '')
   data=hs_request('GET',path,token)
   for o in data.get('results') or []:
    oid=str(o.get('id') or '').strip()
    name=' '.join(x for x in [str(o.get('firstName') or '').strip(),str(o.get('lastName') or '').strip()] if x).strip() or str(o.get('email') or '').strip()
    if oid and name: labels[oid]=name
   after=((data.get('paging') or {}).get('next') or {}).get('after')
   if not after: break
 except Exception: pass
 _OWNER_LABEL_CACHE[token]=labels
 return labels
def owner_label(oid,labels=None):
 """Preferir cadastro local, depois HubSpot Owners, depois fallback 'Owner <id>'."""
 oid=str(oid or '').strip()
 if not oid: return 'Sem proprietário'
 for uid,cfg in load_users().items():
  if str((cfg or {}).get('hubspot_owner_id') or '')==oid: return str((cfg or {}).get('name') or uid)
 if oid in HUBSPOT_OWNER_LABELS: return HUBSPOT_OWNER_LABELS[oid]
 if labels and oid in labels: return labels[oid]
 return 'Owner '+oid
def roteiro_is_growth_leader(uid,cfg):
 role=str((cfg or {}).get('role') or '').lower().replace(' ','_').replace('-','_'); title=str((cfg or {}).get('title') or (cfg or {}).get('cargo') or '').lower()
 extra={x.strip() for x in os.environ.get('ROTEIRO_GROWTH_VIEW_ALL_UIDS','').split(',') if x.strip()}
 return uid in extra or role in GROWTH_ROLES or ('growth' in title and any(w in title for w in ['lider','líder','leader','head']))
def roteiro_can_view_all(uid):
 cfg=load_users().get(uid,{})
 return uid in ROTEIRO_VIEW_ALL_UIDS or roteiro_is_growth_leader(uid,cfg)
def roteiro_owner_id_for_user(uid): return '' if roteiro_can_view_all(uid) else str((load_users().get(uid,{}) or {}).get('hubspot_owner_id') or '')

def _secret():
 if SECRET_FILE.exists():
  s=SECRET_FILE.read_text().strip()
  if s: return s.encode()
 sec=secrets.token_urlsafe(48); SECRET_FILE.parent.mkdir(parents=True,exist_ok=True); SECRET_FILE.write_text(sec); os.chmod(SECRET_FILE,0o600); return sec.encode()
SECRET=_secret(); _b64u=lambda b: base64.urlsafe_b64encode(b).decode().rstrip('=')
def _b64d(s): return base64.urlsafe_b64decode(s+'='*(-len(s)%4))
def make_session(uid,ttl=SESSION_TTL):
 exp=str(int(time.time()+ttl)); sig=hmac.new(SECRET,(uid+'|'+exp).encode(),hashlib.sha256).digest(); return _b64u(uid.encode())+'.'+exp+'.'+_b64u(sig)
def verify_session(v):
 try:
  ub,exp,sb=str(v or '').split('.'); uid=_b64d(ub).decode(); sig=_b64d(sb); ok=hmac.compare_digest(sig,hmac.new(SECRET,(uid+'|'+exp).encode(),hashlib.sha256).digest())
  return uid if ok and int(exp)>time.time() and uid in load_users() else None
 except Exception: return None
def make_state():
 n=secrets.token_urlsafe(16); ts=str(int(time.time())); sig=hmac.new(SECRET,(n+'|'+ts).encode(),hashlib.sha256).hexdigest()[:32]; return n+'.'+ts+'.'+sig
def verify_state(v):
 try:
  n,ts,sig=str(v or '').split('.'); return hmac.compare_digest(sig,hmac.new(SECRET,(n+'|'+ts).encode(),hashlib.sha256).hexdigest()[:32]) and int(ts)>=time.time()-OAUTH_STATE_TTL
 except Exception: return False
def build_cookie(name,value,max_age,secure=False,http_only=True,same_site='Lax'):
 parts=[f'{name}={value}','Path=/',f'Max-Age={int(max_age)}',f'SameSite={same_site}']
 if http_only: parts.append('HttpOnly')
 if secure: parts.append('Secure')
 return '; '.join(parts)
def request_is_https(h): return 'https' in (h.headers.get('X-Forwarded-Proto') or '').lower() or h.headers.get('Host','').split(':',1)[0]=='roteiro.zydon.com.br'
def cookies(h):
 jar=http.cookies.SimpleCookie(); raw=h.headers.get('Cookie')
 if raw:
  try: jar.load(raw)
  except Exception: pass
 return jar
def identity(h):
 email=h.headers.get('Cf-Access-Authenticated-User-Email') or h.headers.get('CF-Access-Authenticated-User-Email') or ''
 uid=uid_from_email(email) if email else None
 if uid: return uid
 jar=cookies(h); return verify_session(jar[SESSION_COOKIE].value) if SESSION_COOKIE in jar else None
def oauth_redirect_uri(h=None): return 'https://roteiro.zydon.com.br/oauth/callback'
def google_exchange_code(code, redirect_uri, cfg):
 data=urllib.parse.urlencode({'code':code,'client_id':cfg['client_id'],'client_secret':cfg['client_secret'],'redirect_uri':redirect_uri,'grant_type':'authorization_code'}).encode()
 req=urllib.request.Request('https://oauth2.googleapis.com/token',data=data,headers={'Content-Type':'application/x-www-form-urlencoded'},method='POST')
 with urllib.request.urlopen(req,timeout=30) as r: return json.loads(r.read().decode() or '{}')
def google_userinfo(tok):
 req=urllib.request.Request('https://openidconnect.googleapis.com/v1/userinfo',headers={'Authorization':'Bearer '+tok})
 with urllib.request.urlopen(req,timeout=30) as r: return json.loads(r.read().decode() or '{}')

def _human(v):
 s=str(v or '').strip()
 if not s: return ''
 if '_' in s and not re.search(r'https?://|www\.|@',s,re.I): s=s.strip('_').replace('_',' ')
 s=re.sub(r'\s+',' ',s).strip(); low=s.lower(); simple={'sim':'Sim','nao':'Não','não':'Não','outro':'Outro','outros':'Outros'}
 if low in simple: return simple[low]
 return s[:1].upper()+s[1:] if s==s.lower() else s
def _prop(props,k): return _human((props or {}).get(k) or '')
def _first(props,keys):
 for k in keys:
  v=_prop(props,k)
  if v: return v
 return ''
def _short(v,n=90):
 v=str(v or '').strip(); return v if len(v)<=n else v[:n-1].rstrip()+'…'
def build_form_data(props):
 out=[]; seen=set()
 for k,label in FORM_FIELD_LABELS.items():
  if label in seen: continue
  v=_prop(props,k)
  if v: seen.add(label); out.append({'key':k,'label':label,'value':v})
 return out
def build_lead_chips(props):
 specs=[('ERP',ERP_KEYS),('Vende online',['vende_em_loja_virtual_']),('Faturamento',FAT_KEYS),('Vendedores',['quantos_vendedores_internos_sua_empresa_possui']),('Forma de venda',['de_qual_forma_mais_vende_hoje_em_dia']),('Dor principal',DOR_KEYS)]
 return [{'label':label,'value':_short(v)} for label,keys in specs for v in [_first(props,keys)] if v][:6]
def has_sales_team(props):
 v=_prop(props,'quantos_vendedores_internos_sua_empresa_possui').lower()
 return bool(v and not re.fullmatch(r'0|zero|nenhum|não tenho|nao tenho',v))
def uses_big_four(props): return bool(re.search(r'bling|omie|olist|tiny|sankhya',_first(props,ERP_KEYS),re.I))
def whatsapp_relevant(props): return bool(re.search(r'whats|áudio|audio|foto|texto|pedido manual',(_prop(props,'de_qual_forma_mais_vende_hoje_em_dia')+' '+_first(props,DOR_KEYS)),re.I))
def build_company_context(cp):
 c=cp or {}; out={}
 for key,label in [('name','name'),('website','site'),('domain','site'),('industry','industry')]:
  if label not in out and _prop(c,key): out[label]=_prop(c,key)
 loc=', '.join(x for x in [_prop(c,'city'),_prop(c,'state')] if x)
 if loc: out['location']=loc
 if _prop(c,'description'): out['description']=_short(_prop(c,'description'),350)
 return out
def build_meeting_insights(props):
 out=[]; erp=_first(props,ERP_KEYS); online=_prop(props,'vende_em_loja_virtual_'); vend=_prop(props,'quantos_vendedores_internos_sua_empresa_possui'); forma=_prop(props,'de_qual_forma_mais_vende_hoje_em_dia'); dor=_first(props,DOR_KEYS); fat=_first(props,FAT_KEYS)
 if erp: out.append(f'ERP atual: {erp}.')
 if online: out.append(f'Vende online hoje: {online}.')
 if fat: out.append(f'Faixa de faturamento: {fat}.')
 if vend: out.append(f'Vendedores internos: {vend}.')
 if forma: out.append(f'Canal predominante: {forma}.')
 if dor: out.append(f'Dor declarada: {_short(dor,120)}.')
 return out[:6]
def build_guide_focus(props):
 out=[]; erp=_first(props,ERP_KEYS); online=_prop(props,'vende_em_loja_virtual_'); dor=_first(props,DOR_KEYS)
 if uses_big_four(props): out.append(f'{erp} é Big Four: abra com dados/integração e não com tour genérico.')
 elif erp: out.append(f'ERP {erp}: valide integração, catálogo, preço, estoque e financeiro.')
 if online and re.search(r'n[ãa]o',online,re.I): out.append('Não vende online: enfatize vitrine B2B, acesso do cliente e checkout guiado.')
 elif online: out.append('Já vende online: compare B2C genérico com e-commerce B2B por regra comercial.')
 if has_sales_team(props): out.append('Tem vendedores: incluir tela do Vendedor, carteira, proposta e análises.')
 else: out.append('Sem vendedores internos declarados: focar Cliente/e-commerce B2B + Admin.')
 if whatsapp_relevant(props): out.append('WhatsApp é relevante: mostrar Zoe/IA para pedido via texto, áudio ou foto.')
 if dor: out.append(f'Conectar cada tela à dor declarada: {_short(dor,110)}.')
 return out[:6]
def build_discovery_questions(props):
 qs=[]
 if not _first(props,ERP_KEYS): qs.append('Qual ERP concentra pedido, estoque, financeiro e tabela?')
 if not _prop(props,'de_qual_forma_mais_vende_hoje_em_dia'): qs.append('Como o pedido nasce hoje: WhatsApp, planilha, ligação, vendedor ou portal?')
 if not _prop(props,'quantos_vendedores_internos_sua_empresa_possui'): qs.append('Existe equipe de vendedores internos ou representantes usando carteira?')
 if not _first(props,DOR_KEYS): qs.append('Qual dor operacional mais trava pedido recorrente?')
 qs.append('Há tabela por cliente, condição de pagamento e limite de crédito?')
 return qs[:6]
def load_best_practices():
 try: return json.loads(BEST_FILE.read_text())
 except Exception: return []
def coaching_tips(props):
 bp=load_best_practices(); tips=[b.get('principle') for b in bp[:4] if b.get('principle')]
 tips += build_guide_focus(props)[:2]
 return tips[:6]
def dynamic_phases(props,stage_id=''):
 if str(stage_id or '')==INTRODUCTION_STAGE_ID:
  return [dict(p) for p in CHALLENGER_INTRO_PHASES]
 phases=[]
 for p in BASE_PHASES:
  if p['id']=='erp' and not uses_big_four(props): continue
  if p['id']=='whatsapp' and not whatsapp_relevant(props): continue
  if p['id']=='vendedor' and not has_sales_team(props): continue
  phases.append(dict(p))
 return phases

def strip_html(v):
 s=str(v or '')
 s=re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>',' ',s)
 s=re.sub(r'(?s)<[^>]+>',' ',s)
 s=html.unescape(s)
 return re.sub(r'\s+',' ',s).strip()
def _fmt_date(ts):
 s=str(ts or '').strip()
 m=re.match(r'(\d{4})-(\d{2})-(\d{2})',s)
 if m: return f'{m.group(3)}/{m.group(2)}/{m.group(1)}'
 if s.isdigit() and len(s)>=10:
  try: return datetime.fromtimestamp(int(s[:13])/1000 if len(s)>=13 else int(s),timezone.utc).strftime('%d/%m/%Y')
  except Exception: return ''
 return s[:10]
def _engagement_record(obj,props):
 p=props or {}; g=lambda k: strip_html(p.get(k) or '')
 if obj=='notes': title='Nota'; text=g('hs_note_body'); ts=p.get('hs_timestamp') or p.get('hs_createdate') or ''
 elif obj=='tasks':
  title=g('hs_task_subject') or 'Tarefa'; text=g('hs_task_body'); st=g('hs_task_status')
  if st: text=(text+f' [status: {st}]').strip()
  ts=p.get('hs_timestamp') or ''
 elif obj=='calls': title=g('hs_call_title') or 'Ligação'; text=g('hs_call_body'); ts=p.get('hs_timestamp') or ''
 elif obj=='meetings': title=g('hs_meeting_title') or 'Reunião'; text=g('hs_meeting_body'); ts=p.get('hs_meeting_start_time') or p.get('hs_timestamp') or ''
 elif obj=='emails': title=g('hs_email_subject') or 'E-mail'; text=g('hs_email_text') or g('hs_email_html'); ts=p.get('hs_timestamp') or ''
 else: title=''; text=''; ts=''
 return {'type':obj,'title':title,'text':text,'ts':str(ts or '')}
def build_engagement_intel(records):
 recs=sorted([r for r in (records or []) if (r.get('title') or r.get('text'))],key=lambda r:str(r.get('ts') or ''),reverse=True)
 diag=[]; foll=[]; timeline=[]
 for r in recs:
  blob=((r.get('title') or '')+' '+(r.get('text') or '')).strip()
  if not blob: continue
  label=ENGAGEMENT_LABELS.get(r.get('type'),str(r.get('type') or '').title())
  item={'type':r.get('type'),'label':label,'title':r.get('title') or label,'text':_short(r.get('text'),240),'ts':_fmt_date(r.get('ts'))}
  if DIAGNOSTIC_PAT.search(blob) and len(diag)<6: diag.append(item)
  if FOLLOWUP_PAT.search(blob) and len(foll)<6: foll.append(item)
  if len(timeline)<8: timeline.append(item)
 return {'diagnosticSummary':diag,'followUps':foll,'hubspotTimeline':timeline}
def collect_deal_engagements(token,deal_id):
 records=[]
 for obj,props in ENGAGEMENT_PROPS.items():
  ids=hs_deal_associations(token,deal_id,obj)
  for row in hs_batch_read(token,obj,ids[:25],props):
   rec=_engagement_record(obj,row.get('properties'))
   if rec.get('title') or rec.get('text'): records.append(rec)
 return records
def _company_url(cp):
 for k in ['website','domain']:
  v=str((cp or {}).get(k) or '').strip()
  if v:
   if not re.match(r'https?://',v,re.I): v='https://'+v.lstrip('/')
   return v.split()[0]
 return ''
def parse_homepage(html_text,url):
 t=str(html_text or ''); title=''; desc=''
 m=re.search(r'(?is)<title[^>]*>(.*?)</title>',t)
 if m: title=strip_html(m.group(1))
 m=re.search(r'(?is)<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',t) or re.search(r'(?is)<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',t)
 if not m: m=re.search(r'(?is)<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']',t)
 if m: desc=strip_html(m.group(1))
 if not (title or desc): return {}
 return {'source':url,'url':url,'title':_short(title,160),'description':_short(desc,320)}
def build_web_search_queries(cp):
 """Sem website/domain: gerar buscas com nome da empresa + termos B2B, LinkedIn/site/CNPJ."""
 c=cp or {}; name=_prop(c,'name'); ind=_prop(c,'industry'); out=[]
 if not name: return out
 loc=', '.join(x for x in [_prop(c,'city'),_prop(c,'state')] if x)
 out.append(f'{name} {ind} B2B atacado distribuidor' if ind else f'{name} empresa B2B atacado distribuidor')
 out.append(f'{name} site oficial catálogo produtos')
 out.append(f'{name} LinkedIn empresa funcionários')
 out.append(f'{name} CNPJ razão social atividade')
 if loc: out.append(f'{name} {loc}')
 return out[:6]
def build_web_research_hints(cp):
 """Instruções de pesquisa pré-reunião para o executivo/Claude."""
 c=cp or {}; name=_prop(c,'name'); hints=[]
 if name: hints.append(f'Pesquisar "{name}" + termos do segmento para entender o modelo de venda.')
 hints += [
  'Confirmar segmento, porte e se é indústria, distribuidor ou varejo B2B.',
  'Procurar catálogo/e-commerce atual, canais de venda e se já vende online.',
  'Checar LinkedIn para porte (nº de funcionários) e estrutura comercial.',
  'Buscar CNPJ/razão social para validar faturamento e atividade principal.']
 return hints[:6]
def build_research_angles(cp,ctx):
 """Derivar ângulos de pesquisa a partir da homepage + cadastro: segmento, canais, catálogo, distribuição/indústria."""
 c=cp or {}; ctx=ctx or {}
 blob=' '.join([str(ctx.get('title') or ''),str(ctx.get('description') or ''),_prop(c,'industry'),_prop(c,'name')]).lower()
 angles=[]
 if re.search(r'distribu|atacad',blob): angles.append('Provável distribuição/atacado: validar carteira, tabela por cliente e pedido recorrente.')
 if re.search(r'ind[uú]stria|f[áa]brica|fabricante|manufatur',blob): angles.append('Provável indústria/fabricante: validar representantes, política comercial e B2B para revenda.')
 if re.search(r'e-?commerce|loja|shop|varejo|store|marketplace',blob): angles.append('Já tem presença e-commerce: comparar B2C atual com e-commerce B2B por regra comercial.')
 if re.search(r'cat[áa]logo|produtos|cole[çc][ãa]o|linha',blob): angles.append('Catálogo/produtos visível: explorar mix, recompra e vitrine B2B.')
 if not angles: angles.append('Segmento ainda incerto: usar a reunião para confirmar modelo de venda e canais.')
 return angles[:5]
def fetch_internet_context(cp):
 url=_company_url(cp)
 if not url:
  return {'source':'','url':'','title':'','description':'','note':'Sem site/domínio no HubSpot. Pesquisar antes da reunião.','webSearchQueries':build_web_search_queries(cp),'webResearchHints':build_web_research_hints(cp)}
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; ZydonRoteiro/1.0)'})
  with urllib.request.urlopen(req,timeout=6) as r:
   raw=r.read(300000).decode('utf-8','replace')
  ctx=parse_homepage(raw,url) or {'source':url,'url':url,'title':'','description':'','note':'Página sem título/descrição legível.'}
  ctx['researchAngles']=build_research_angles(cp,ctx); ctx['webResearchHints']=build_web_research_hints(cp)
  if not (ctx.get('title') or ctx.get('description')): ctx['webSearchQueries']=build_web_search_queries(cp)
  return ctx
 except Exception:
  return {'source':url,'url':url,'title':'','description':'','note':'Não foi possível carregar o site agora.','webSearchQueries':build_web_search_queries(cp),'webResearchHints':build_web_research_hints(cp)}

def hubspot_token():
 if os.environ.get('HUBSPOT_API_KEY'): return os.environ['HUBSPOT_API_KEY'].strip()
 cfg=_parse_env(HUBSPOT_ENV); return (cfg.get('HUBSPOT_API_KEY') or '').strip()
def hs_request(method,path,token,payload=None,timeout=30):
 data=json.dumps(payload).encode() if payload is not None else None
 req=urllib.request.Request(HUBSPOT_API+path,data=data,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method=method)
 with urllib.request.urlopen(req,timeout=timeout) as r: return json.loads(r.read().decode() or '{}')
def hs_deal_associations(token,deal_id,to_object):
 try:
  d=hs_request('GET',f'/crm/v4/objects/deals/{deal_id}/associations/{to_object}',token)
  return [str(r.get('toObjectId')) for r in d.get('results') or [] if r.get('toObjectId')]
 except Exception: return []
def hs_batch_read(token,obj,ids,props):
 ids=[str(i) for i in ids or [] if str(i)]
 if not ids: return []
 try: return (hs_request('POST',f'/crm/v3/objects/{obj}/batch/read',token,{'properties':props,'inputs':[{'id':i} for i in ids]}) .get('results') or [])
 except Exception: return []
def context_hint(name):
 b=str(name or '').lower()
 if re.search(r'farma|medicament|cosm|beleza',b): return 'Investigar mix, recorrência, televendas, tabela por cliente e reposição.'
 if re.search(r'café|alimento|bebida|distrib|atacado',b): return 'Investigar giro, pedido mínimo, prazo, condição e clientes por carteira.'
 return 'Confirmar segmento, comprador, recorrência, ERP, tabela e forma atual de pedido.'
def presentation_deals(uid='rafael'):
 tok=hubspot_token()
 if not tok: return {'configured':False,'error':'HubSpot não configurado','total':0,'deals':[],'owners':[],'stages':ROTEIRO_STAGES}
 filters=[{'propertyName':'pipeline','operator':'EQ','value':HUBSPOT_PIPELINE_ID},{'propertyName':'dealstage','operator':'IN','values':list(ROTEIRO_STAGES.keys())},{'propertyName':'hubspot_owner_id','operator':'IN','values':sorted(ROTEIRO_EXECUTIVE_OWNER_IDS)}]
 scope='Executivos: João Vitor, Samara, Edimilson e Ítalo · Introdução em diante' if roteiro_can_view_all(uid) else 'somente sua carteira executiva em Introdução+'
 if not roteiro_can_view_all(uid):
  oid=roteiro_owner_id_for_user(uid)
  if not oid: return {'configured':True,'total':0,'deals':[],'owners':[],'scope':scope,'permission':'no_hubspot_owner','stages':ROTEIRO_STAGES}
  if oid not in ROTEIRO_EXECUTIVE_OWNER_IDS: return {'configured':True,'total':0,'deals':[],'owners':[],'scope':scope,'permission':'owner_outside_roteiro_executives','stages':ROTEIRO_STAGES}
  filters=[f for f in filters if f.get('propertyName')!='hubspot_owner_id']
  filters.append({'propertyName':'hubspot_owner_id','operator':'EQ','value':oid})
 payload={'filterGroups':[{'filters':filters}],'properties':['dealname','dealstage','pipeline','hubspot_owner_id','createdate','hs_lastmodifieddate','amount'],'limit':100,'sorts':[{'propertyName':'hs_lastmodifieddate','direction':'DESCENDING'}]}
 owner_labels=hubspot_owner_labels(tok); rows=[]; after=None
 while True:
  if after: payload['after']=after
  else: payload.pop('after',None)
  data=hs_request('POST','/crm/v3/objects/deals/search',tok,payload)
  for d in data.get('results') or []:
   pr=d.get('properties') or {}; did=str(d.get('id') or ''); oid=str(pr.get('hubspot_owner_id') or ''); stage=str(pr.get('dealstage') or '')
   name=pr.get('dealname') or '(negócio sem nome)'
   rows.append({'dealId':did,'dealName':name,'ownerId':oid,'owner':owner_label(oid,owner_labels),'stageId':stage,'stageLabel':ROTEIRO_STAGES.get(stage,stage),'updatedAt':pr.get('hs_lastmodifieddate') or '', 'amount':pr.get('amount') or '', 'url':f'https://app.hubspot.com/contacts/{HUBSPOT_PORTAL_ID}/deal/{did}','contextHints':[context_hint(name)]})
  after=((data.get('paging') or {}).get('next') or {}).get('after')
  if not after or len(rows)>=300: break
 owners=[]
 for r in rows:
  o=next((x for x in owners if x['ownerId']==r['ownerId']),None)
  if o: o['count']+=1
  else: owners.append({'ownerId':r['ownerId'],'owner':r['owner'],'count':1})
 return {'configured':True,'total':len(rows),'deals':rows[:300],'owners':owners,'scope':scope,'stages':ROTEIRO_STAGES}
def deal_intelligence(uid,deal_id,stage_id=''):
 empty={'hasForm':False,'formData':[],'leadChips':[],'companyContext':{},'meetingInsights':[],'guideFocus':[],'discoveryQuestions':build_discovery_questions({}),'coachingTips':load_best_practices()[:3],'note':'Sem formulário associado no HubSpot para este negócio.','phases':dynamic_phases({},stage_id),'diagnosticSummary':[],'followUps':[],'hubspotTimeline':[],'internetContext':{},'challenger':challenger_intro_context() if str(stage_id or '')==INTRODUCTION_STAGE_ID else {}}
 tok=hubspot_token()
 if not tok: empty['note']='HubSpot não configurado.'; return empty
 cids=hs_deal_associations(tok,deal_id,'contacts'); coids=hs_deal_associations(tok,deal_id,'companies')
 contacts=hs_batch_read(tok,'contacts',cids[:5],CONTACT_PROPS); companies=hs_batch_read(tok,'companies',coids[:3],COMPANY_PROPS)
 cp=(companies[0].get('properties') if companies else {}) or {}
 eng=build_engagement_intel(collect_deal_engagements(tok,deal_id)); internet=fetch_internet_context(cp)
 if not contacts and not companies:
  out=dict(empty); out.update(eng); out['internetContext']=internet; return out
 props={}; best=-1
 for c in contacts:
  p=c.get('properties') or {}; score=sum(1 for k in CONTACT_FORM_KEYS if _prop(p,k))
  if score>best: best=score; props=p
 phases=dynamic_phases(props,stage_id)
 fd=build_form_data(props)
 return {'hasForm':bool(fd),'formData':fd,'leadChips':build_lead_chips(props),'companyContext':build_company_context(cp),'meetingInsights':build_meeting_insights(props),'guideFocus':build_guide_focus(props),'discoveryQuestions':build_discovery_questions(props),'coachingTips':coaching_tips(props),'note':'' if fd else 'Sem formulário associado no HubSpot para este negócio.','phases':phases,'diagnosticSummary':eng['diagnosticSummary'],'followUps':eng['followUps'],'hubspotTimeline':eng['hubspotTimeline'],'internetContext':internet,'challenger':challenger_intro_context() if str(stage_id or '')==INTRODUCTION_STAGE_ID else {}}
def default_roteiro(): return {'ok':True,'title':'Roteiro de Demonstração Zydon','subtitle':'Wizard dinâmico conforme fase comercial e diagnóstico do cliente.','phases':BASE_PHASES,'introPhases':CHALLENGER_INTRO_PHASES,'challenger':challenger_intro_context(),'bestPractices':load_best_practices()}
def roteiro_load():
 data=default_roteiro()
 try:
  if ROTEIRO_FILE.exists(): data.update(json.loads(ROTEIRO_FILE.read_text() or '{}')); data['ok']=True
 except Exception as e: data['error']=str(e)
 return data
def roteiro_save(uid,body):
 payload={'ok':True,'title':str((body or {}).get('title') or 'Roteiro de Demonstração Zydon')[:180],'subtitle':str((body or {}).get('subtitle') or '')[:320],'phases':(body or {}).get('phases') or BASE_PHASES,'updatedAt':datetime.now(timezone.utc).isoformat(),'updatedBy':uid}
 ROTEIRO_FILE.parent.mkdir(parents=True,exist_ok=True); ROTEIRO_FILE.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
 with open(ROTEIRO_AUDIT_FILE,'a') as f: f.write(json.dumps({'ts':payload['updatedAt'],'uid':uid},ensure_ascii=False)+'\n')
 return payload
def post_meeting_template(deal=None,intel=None):
 """Resumo estruturado pós-reunião. Rascunho local: ainda não escreve no HubSpot."""
 fields=[
  {'key':'diagnostico_confirmado','label':'Diagnóstico confirmado','value':'','hint':'O que foi confirmado sobre dor, ERP, canal e regras comerciais.'},
  {'key':'telas_demonstradas','label':'Telas demonstradas','value':'','hint':'Quais fases/telas foram realmente mostradas.'},
  {'key':'valor_percebido','label':'Valor percebido','value':'','hint':'O que o cliente reconheceu como ganho.'},
  {'key':'objecoes_riscos','label':'Objeções / riscos','value':'','hint':'Dúvidas, bloqueios e riscos para avançar.'},
  {'key':'proximo_passo','label':'Próximo passo','value':'','hint':'Proposta, técnica, decisores ou validação.'},
  {'key':'quem_participa','label':'Quem precisa participar','value':'','hint':'Pessoas/áreas da próxima etapa.'}]
 return {'title':'Resumo pós-reunião','fields':fields,'note':'Rascunho local. Ainda não escreve no HubSpot.'}
def start_presentation(uid,deal_id):
 deal=next((d for d in presentation_deals(uid).get('deals',[]) if str(d.get('dealId'))==str(deal_id)),None)
 if not deal: raise ValueError('negócio não encontrado nesta etapa/escopo')
 intel=deal_intelligence(uid,deal_id,deal.get('stageId')); run={'runId':secrets.token_urlsafe(10),'ts':datetime.now(timezone.utc).isoformat(),'uid':uid,'dealId':deal_id,'dealName':deal['dealName'],'stageLabel':deal.get('stageLabel'),'status':'started','phaseCount':len(intel.get('phases') or [])}
 RUNS_FILE.parent.mkdir(parents=True,exist_ok=True)
 with open(RUNS_FILE,'a') as f: f.write(json.dumps(run,ensure_ascii=False)+'\n')
 return {'ok':True,'run':run,'deal':deal,'intel':intel,'roteiro':roteiro_load(),'postMeetingTemplate':post_meeting_template(deal,intel)}

CSS=r'''
:root{--bg:#08090b;--panel:#15161a;--panel2:#101114;--card:#0b0c0f;--line:#2a2c33;--line2:#343742;--txt:#f5f7fb;--muted:#a9afbd;--soft:#747b8b;--lime:#cdeb00;--lime2:#aeda00;--orange:#ff9f2f;--orange2:#7a421b;--pink:#ed6ab0;--cyan:#52d6ff;--violet:#9b7cff;--shadow:0 22px 80px rgba(0,0,0,.34)}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font-family:Inter,system-ui,-apple-system,Segoe UI,Arial,sans-serif;font-size:14px}a{color:inherit;text-decoration:none}button,input,select,textarea{font:inherit}.top{min-height:94px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:18px;padding:24px 16px;background:#08090b}.brand{display:flex;gap:14px;align-items:center}.brand-mark{width:48px;height:48px;border-radius:14px;background:var(--lime);display:grid;place-items:center;box-shadow:0 0 34px rgba(205,235,0,.22)}.brand-mark img{max-width:29px;max-height:29px}.brand h1{font-size:24px;line-height:1.05;margin:0;letter-spacing:-.035em}.brand p{margin:4px 0 0;color:var(--muted)}.brand p b{color:#fff}.actions{display:flex;align-items:center;gap:10px}.theme{width:40px;height:40px;border-radius:9px;background:#15161a;border:1px solid var(--line);color:var(--muted);display:grid;place-items:center}.app{min-height:100vh;background:radial-gradient(circle at 20% 0%,rgba(205,235,0,.07),transparent 25%),#08090b}.main{padding:0 16px 32px;max-width:1280px;margin:0 auto}.panel{background:var(--panel);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow)}.finder{padding:16px;margin-bottom:16px}.eyebrow{font-size:12px;letter-spacing:.055em;text-transform:uppercase;color:var(--muted);font-weight:850;display:flex;align-items:center;gap:8px}.eyebrow .dot{color:var(--lime)}.filters{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}.selectish,.search{width:100%;height:40px;border:1px solid var(--line);background:#0d0e12;color:var(--muted);border-radius:9px;padding:0 12px}.search{color:var(--txt)}.selectish{display:flex;align-items:center;justify-content:space-between;cursor:pointer}.selectish.on{border-color:rgba(205,235,0,.55);color:var(--lime)}.filterbar{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.pill{border:1px solid var(--line);background:#0d0e12;color:var(--muted);border-radius:999px;padding:7px 10px;font-size:12px;cursor:pointer}.pill.on{background:var(--lime);border-color:var(--lime);color:#111;font-weight:850}.deals-panel{padding:16px;margin-bottom:16px;max-height:46vh;overflow:auto}.panel-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:14px;position:sticky;top:0;background:var(--panel);z-index:2;padding-bottom:8px}.count-badge{border-radius:999px;background:#2a2d37;color:#d7dbea;font-size:12px;font-weight:850;padding:5px 10px}.deal-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px}.deal{width:100%;min-height:64px;text-align:left;border:1px solid var(--line);background:#0b0c0f;color:var(--txt);border-radius:10px;padding:12px;cursor:pointer;display:flex;align-items:flex-start;justify-content:space-between;gap:10px;transition:.16s ease}.deal:hover{border-color:#454956;transform:translateY(-1px)}.deal.on{border-color:var(--lime);box-shadow:0 0 0 1px rgba(205,235,0,.45),0 0 30px rgba(205,235,0,.08)}.deal b{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:14px}.deal span:first-child{min-width:0}.deal small{display:block;color:#aeb5c4;margin-top:7px;font-size:11px}.tag{align-self:center;flex:0 0 auto;border-radius:999px;background:#30333d;color:#c9cfdf;font-size:10px;font-weight:850;padding:4px 8px;white-space:nowrap}.tag.solution,.tag.Solução{color:var(--lime)}.tag.intro,.tag.Introdução{color:#d9e1f0}.empty{border:1px dashed var(--line2);border-radius:14px;padding:22px;text-align:center;color:var(--muted)}.game-card{padding:20px;margin-bottom:16px}.game-top{display:flex;justify-content:space-between;align-items:flex-start;gap:18px}.tabs{display:flex;gap:8px;flex-wrap:wrap}.tab{border:1px solid var(--line);background:#0b0c0f;color:var(--muted);border-radius:9px;padding:12px 16px;font-weight:850;cursor:pointer}.tab.on{background:var(--lime);border-color:var(--lime);color:#111}.client-meta{color:var(--muted);font-size:13px;text-align:right}.client-meta b{color:#fff}.xp-row{display:grid;grid-template-columns:auto auto 1fr auto;align-items:center;gap:12px;margin-top:18px}.rank{border:1px solid #70727b;border-radius:999px;color:#c4c9d5;padding:8px 12px;font-weight:850}.xp{color:var(--lime);font-weight:900}.progress{height:12px;border-radius:999px;background:#303037;overflow:hidden}.progress>span{display:block;height:100%;background:linear-gradient(90deg,var(--lime),#f2ff62);width:0}.hint{color:#aeb5c4;font-size:12px;margin-top:9px}.hint b{color:var(--lime)}.start-wrap{display:flex;justify-content:flex-end;margin-top:16px}.btn{border:1px solid var(--line2);background:#0b0c0f;color:var(--txt);border-radius:10px;padding:12px 16px;font-weight:850;cursor:pointer}.btn:hover{border-color:#555a68}.btn.lime{background:var(--lime);border-color:var(--lime);color:#101010}.btn.orange{background:transparent;color:#ffad4d;border-color:#ff9f2f}.btn.ghost{background:transparent;color:var(--muted)}.btn.sm{font-size:12px;padding:8px 10px}.stagebar{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:14px}.stage-tabs{display:flex;gap:8px;flex-wrap:wrap}.stage-tab{border:1px solid var(--line);background:#0b0c0f;color:var(--muted);border-radius:999px;padding:9px 13px;font-size:12px;font-weight:850;cursor:pointer}.stage-tab.on{background:#fff;color:#101114;border-color:#fff}.chips{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}.chip{border:1px solid var(--line);background:#0b0c0f;border-radius:999px;padding:7px 11px;color:#d8dce8;font-size:12px}.chip b{color:var(--lime);text-transform:uppercase;font-size:10px;margin-right:6px}.road{padding:16px;margin-bottom:16px;display:grid;grid-template-columns:repeat(5,minmax(120px,1fr));gap:24px;align-items:start}.road-step{position:relative;text-align:center;color:var(--muted);background:transparent;border:0;cursor:pointer}.road-step:after{content:'';position:absolute;left:72%;right:-40%;top:29px;height:3px;background:#32333a;border-radius:8px}.road-step:last-child:after,.road-step:nth-child(5n):after{display:none}.road-icon{width:58px;height:58px;border-radius:16px;border:2px solid #333744;background:#101114;margin:0 auto 8px;display:grid;place-items:center;color:#c7cedd;font-size:24px;position:relative}.road-step.on .road-icon{border-color:var(--orange);box-shadow:0 0 0 3px rgba(255,159,47,.22),0 0 26px rgba(255,159,47,.2);color:var(--orange);background:#27180f}.road-step.done .road-icon{border-color:var(--lime);color:#111;background:var(--lime)}.bubble{position:absolute;right:-9px;top:-8px;min-width:18px;height:18px;border-radius:999px;background:var(--lime);color:#111;font-size:11px;font-weight:900;display:grid;place-items:center}.road-step:nth-child(3) .bubble{background:var(--cyan)}.road-step:nth-child(4) .bubble{background:var(--pink)}.road-step:nth-child(5) .bubble{background:var(--violet);color:#fff}.road-title{font-size:12px;color:#e8ebf5;font-weight:850}.road-sub{font-size:11px;color:var(--muted)}.phase-card{padding:0;overflow:hidden;margin-bottom:16px}.phase-hero{display:grid;grid-template-columns:auto 1fr auto;gap:16px;align-items:center;padding:24px;background:linear-gradient(90deg,rgba(255,159,47,.14),rgba(255,159,47,.04),transparent)}.phase-symbol{width:64px;height:64px;border-radius:18px;border:2px solid var(--orange);background:#2a1a10;color:var(--orange);display:grid;place-items:center;font-size:30px}.kicker{font-size:12px;letter-spacing:.075em;text-transform:uppercase;color:var(--orange);font-weight:900}.phase-hero h2{font-size:30px;line-height:1.05;margin:5px 0 8px;letter-spacing:-.035em}.phase-hero p{margin:0;color:#e8ebf5}.donut{width:72px;height:72px;border-radius:50%;display:grid;place-items:center;background:conic-gradient(var(--lime) var(--pct),#2a2c35 0);font-weight:900}.donut:before{content:attr(data-label);width:58px;height:58px;border-radius:50%;background:#111217;display:grid;place-items:center}.phase-body{padding:24px}.section{border-top:1px solid var(--line);padding-top:18px;margin-top:18px}.section:first-child{border-top:0;margin-top:0;padding-top:0}.section h3{font-size:12px;text-transform:uppercase;letter-spacing:.07em;color:#aeb5c4;margin:0 0 12px;display:flex;gap:7px;align-items:center}.objective-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.objective{border:1px solid var(--line);background:#0b0c0f;color:#fff;border-radius:10px;min-height:72px;padding:14px 14px 14px 58px;text-align:left;position:relative;font-weight:800;line-height:1.35;cursor:pointer}.objective .n{position:absolute;left:16px;top:16px;width:30px;height:30px;border:2px solid #343744;border-radius:8px;display:grid;place-items:center;color:#b9bfcc}.objective.done{border-color:rgba(205,235,0,.65);background:rgba(205,235,0,.06)}.objective.done .n{background:var(--lime);border-color:var(--lime);color:#111}.gargalos{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.gargalo{border:1px solid var(--line);background:#111217;border-radius:12px;padding:16px;min-height:92px}.gargalo b{display:block;margin-bottom:6px}.gargalo .n{display:inline-grid;place-items:center;width:28px;height:28px;border-radius:8px;background:#3b2515;color:#ffad4d;font-weight:900;margin-right:8px}.gargalo p{color:#b4bbc9;margin:0;line-height:1.35;font-size:12px}.showbox{border:1px solid var(--line);background:#0d0e12;border-radius:12px;padding:16px;color:#e9edf6;line-height:1.55}.nav{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:22px}.center-note{color:#bec4d1;font-size:12px;text-align:center;flex:1}.prep-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.enr ul{margin:0;padding-left:18px;line-height:1.55}.enr li{margin-bottom:8px}.enr li span,.enr-empty{color:var(--muted)}.enr-ts{color:var(--lime);font-weight:850}.enr-web p{color:var(--muted);line-height:1.45}.post-fld{width:100%;padding:12px;border:1px solid var(--line);background:#0d0e12;color:#fff;border-radius:10px;resize:vertical}.post-hint{color:var(--muted);font-size:12px;margin:5px 0 0}.present .finder,.present .deals-panel,.present .game-card{display:none}.present .main{max-width:1180px}.login{min-height:100vh;display:grid;place-items:center;background:#08090b}.login-card{background:#15161a;border:1px solid var(--line);border-radius:18px;padding:36px;text-align:center;box-shadow:var(--shadow)}.theme-light{--bg:#f7f8f0;--panel:#ffffff;--panel2:#f0f2e7;--card:#ffffff;--line:rgba(17,24,14,.13);--line2:rgba(17,24,14,.20);--txt:#10150d;--muted:#667060;--soft:#7c8476;--shadow:0 18px 54px rgba(17,24,14,.10)}.theme-light.app{background:radial-gradient(circle at 20% 0%,rgba(205,235,0,.22),transparent 24%),#f7f8f0}.theme-light .top{background:#fff}.theme-light .panel{background:var(--panel)}.theme-light .selectish,.theme-light .search,.theme-light .pill,.theme-light .deal,.theme-light .btn,.theme-light .stage-tab,.theme-light .chip,.theme-light .objective,.theme-light .showbox,.theme-light .post-fld{background:#fff;color:var(--txt)}.theme-light .deal small,.theme-light .client-meta,.theme-light .hint,.theme-light .enr-empty{color:var(--muted)}.theme-light .theme{background:#fff;color:#111}.theme-light .road-icon{background:#fff}.theme-light .phase-hero{background:linear-gradient(90deg,rgba(255,159,47,.18),rgba(205,235,0,.10),transparent)}.theme-light .donut:before{background:#fff}.theme-light .gargalo{background:#fff}.theme-light .panel-head{background:var(--panel)}@media(max-width:1050px){.deal-grid{grid-template-columns:repeat(2,1fr)}.road{grid-template-columns:repeat(3,1fr)}.gargalos{grid-template-columns:1fr 1fr}.objective-grid,.prep-grid{grid-template-columns:1fr}}@media(max-width:680px){.top,.game-top,.phase-hero{grid-template-columns:1fr;display:block}.filters,.deal-grid,.road,.gargalos{grid-template-columns:1fr}.road-step:after{display:none}.client-meta{text-align:left;margin-top:12px}.xp-row{grid-template-columns:1fr}.main{padding:0 10px 24px}}
'''
HTML=r'''<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Roteiro Comercial</title><style>__CSS__</style></head><body><div id="root"></div><script>
let deals=null,roteiro=null,active='',owner='all',stage='all',levelFilter='all',q='',run=null,phase=0,done={},loading=false,editor=false,presentMode=false,meetingStage='meeting',postVals={},theme=localStorage.getItem('roteiroTheme')||'dark';
const esc=s=>(s??'').toString().replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
const clean=s=>(s||'').replace(/[🎯💻]/g,'').trim();
const introStages=()=>['1269308723','1269710168'];
function setLevelFilter(l){levelFilter=l;stage='all';draw()}
function toggleTheme(){theme=theme==='dark'?'light':'dark';localStorage.setItem('roteiroTheme',theme);draw()}
async function api(p,o={}){let r=await fetch(p,o); if(!r.ok)throw new Error(await r.text()); return r.json()}
async function load(){[deals,roteiro]=await Promise.all([api('/api/presentation-deals'),api('/api/roteiro')]); let a=all(); if(a.length&&!active)active=a[0].dealId; draw()}
function all(){return (deals&&deals.deals)||[]} function cur(){return all().find(d=>d.dealId===active)||null}
function filtered(){let a=all(); if(owner!=='all')a=a.filter(d=>d.ownerId===owner); if(stage!=='all')a=a.filter(d=>d.stageId===stage); if(levelFilter==='intro')a=a.filter(d=>introStages().includes(d.stageId)); if(levelFilter==='solution')a=a.filter(d=>!introStages().includes(d.stageId)); if(q.trim()){let t=q.toLowerCase(); a=a.filter(d=>(d.dealName||'').toLowerCase().includes(t)||(d.owner||'').toLowerCase().includes(t))} return a}
function phases(){return (run&&run.intel&&run.intel.phases)||[]} function intel(){return (run&&run.intel)||{}}
function level(d=cur()){let label=(d&&d.stageLabel)||''; return /Introdução|Diagnóstico/i.test(label)?'Introdução':'Solução'}
function select(id){active=id;run=null;phase=0;done={};presentMode=false;meetingStage='meeting';postVals={};draw()} function setPhase(i){phase=Math.max(0,Math.min(i,phases().length-1));draw()}
function objKey(i=phase,j){let p=phases()[i]||{};return (p.id||i)+':obj:'+j} function objCount(i=phase){return ((phases()[i]||{}).preQuestions||[]).length} function objDone(i=phase){let n=objCount(i),c=0;for(let j=0;j<n;j++)if(done[objKey(i,j)])c++;return c} function phaseComplete(i=phase){let n=objCount(i);return n?objDone(i)>=n:!!done[(phases()[i]||{}).id]} function completeCount(){return phases().filter((_,i)=>phaseComplete(i)).length} function toggleObj(j){done[objKey(phase,j)]=!done[objKey(phase,j)];draw()} function mark(){let n=objCount(); if(n){for(let j=0;j<n;j++)done[objKey(phase,j)]=true}else{let p=phases()[phase]; if(p)done[p.id]=!done[p.id]} draw()}
function setStage(s){meetingStage=s;draw()} function togglePresent(){presentMode=!presentMode;draw()}
async function start(){if(!active)return;loading=true;draw();try{run=await api('/api/start-presentation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dealId:active})});phase=0;done={};meetingStage='meeting';postVals={}}catch(e){alert(e.message)}loading=false;draw()}
function headerHTML(){return `<div class="top"><div class="brand"><div class="brand-mark"><img src="/logo.png" alt="Zydon"></div><div><h1>Roteiro de Apresentação Comercial</h1><p>⚡ Metodologia <b>A Venda Desafiadora</b> — jornada gamificada por fases</p></div></div><div class="actions"><button class="theme" onclick="toggleTheme()">${theme==='dark'?'Tema claro':'Tema escuro'}</button><a class="btn ghost sm" href="/logout">Sair</a></div></div>`}
function finder(){let os=(deals&&deals.owners)||[], st=(deals&&deals.stages)||{};let own=os.find(o=>o.ownerId===owner);let stLabel=stage==='all'?'Todas as etapas':clean(st[stage]||stage);return `<section class="panel finder"><div class="eyebrow"><span class="dot">♙</span> Clientes ${own?'de '+esc(own.owner):'dos executivos'}</div><div class="filters"><button class="selectish ${stage!=='all'?'on':''}" onclick="stage=stage==='all'?'${Object.keys(st)[0]||'all'}':'all';draw()"><span>◎ ${esc(stLabel)}</span><span>⌄</span></button><input class="search" placeholder="Selecione ou busque um cliente para sugerir o nível" value="${esc(q)}" oninput="q=this.value;draw()"></div><div class="filterbar"><button class="pill ${owner==='all'?'on':''}" onclick="owner='all';draw()">Todos</button>${os.map(o=>`<button class="pill ${owner===o.ownerId?'on':''}" onclick="owner='${esc(o.ownerId)}';draw()">${esc(o.owner)} ${o.count}</button>`).join('')}<button class="pill ${stage==='all'?'on':''}" onclick="stage='all';levelFilter='all';draw()">Todas as etapas</button>${Object.entries(st).map(([id,lb])=>`<button class="pill ${stage===id?'on':''}" onclick="stage='${id}';levelFilter='all';draw()">${esc(clean(lb))}</button>`).join('')}</div></section>`}
function dealGrid(){let rows=filtered();return `<section class="panel deals-panel"><div class="panel-head"><div class="eyebrow"><span class="dot">◎</span> Negócios do seu funil</div><span class="count-badge">${rows.length} negócios</span></div>${rows.length?`<div class="deal-grid">${rows.map(d=>`<button class="deal ${active===d.dealId?'on':''}" onclick="select('${esc(d.dealId)}')"><span><b>${esc(d.dealName)}</b><small>${esc(clean(d.stageLabel))}</small></span><span class="tag ${level(d)==='Solução'?'solution':'intro'}">${level(d)}</span></button>`).join('')}</div>`:'<div class="empty">Nenhuma conta nesta etapa/escopo.</div>'}</section>`}
function gameCard(){let d=cur(), ps=phases(), count=completeCount(), total=run?ps.length:(level(d)==='Introdução'?5:6), xp=count*20, pct=total?Math.round(count/total*100):0;return `<section class="panel game-card"><div class="game-top"><div><div class="tabs"><button class="tab ${(levelFilter==='intro'||(levelFilter==='all'&&level(d)==='Introdução'))?'on':''}" onclick="setLevelFilter('intro')">♨ Introdução</button><button class="tab ${(levelFilter==='solution'||(levelFilter==='all'&&level(d)==='Solução'))?'on':''}" onclick="setLevelFilter('solution')">🚀 Nossa Solução</button></div></div><div class="client-meta"><b>◎ ${esc(d?d.dealName:'Cliente não informado')}</b> · ${esc(d?d.owner:'')}</div></div><div class="xp-row"><span class="rank">♕ ${xp>=100?'Desafiador Mestre':xp>=60?'Intermediário':'Iniciante'}</span><span class="xp">⚡ ${xp}/${total*20} XP</span><div class="progress"><span style="width:${pct}%"></span></div><span class="client-meta">⚐ ${count}/${total} fases concluídas</span></div><div class="hint">Conclua os objetivos de cada fase para avançar e virar <b>Desafiador Mestre.</b></div>${d&&!run?`<div class="start-wrap"><button class="btn lime" onclick="start()">${loading?'Montando roteiro…':'Iniciar roteiro gamificado →'}</button></div>`:''}</section>`}
function chips(){let cs=(intel().leadChips)||[]; if(!cs.length)return `<span class="chip">${esc(intel().note||'Sem formulário associado no HubSpot')}</span>`; return cs.map(c=>`<span class="chip"><b>${esc(c.label)}</b>${esc(c.value)}</span>`).join('')}
function engItem(x){return `<li><b>${esc(x.label||'')}${x.title&&x.title!==x.label?' · '+esc(x.title):''}</b>${x.ts?` <small class="enr-ts">${esc(x.ts)}</small>`:''}${x.text?`<br><span>${esc(x.text)}</span>`:''}</li>`}
function diagBlock(){let a=(intel().diagnosticSummary)||[]; if(!a.length)return `<div class="enr-empty">Sem diagnóstico registrado no HubSpot.</div>`; return `<ul>${a.map(engItem).join('')}</ul>`}
function followBlock(){let a=(intel().followUps)||[]; if(!a.length)return `<div class="enr-empty">Sem follow-ups marcados no HubSpot.</div>`; return `<ul>${a.map(engItem).join('')}</ul>`}
function challengeBlock(){let c=(intel().challenger)||{}, a=c.challenges||[]; if(!a.length)return ''; return `<div class="section"><h3>⚠ Os 5 gargalos da digitalização B2B — distribuidora e indústria</h3><div class="gargalos">${a.map((x,i)=>`<div class="gargalo"><b><span class="n">${i+1}</span>${esc((x||'').split(':')[0])}</b><p>${esc((x||'').split(':').slice(1).join(':')||x)}</p></div>`).join('')}</div></div>`}
function webBlock(){let w=(intel().internetContext)||{};let h='';if(w.title||w.description){h+=`<div class="enr-web">${w.title?`<b>${esc(w.title)}</b>`:''}${w.description?`<p>${esc(w.description)}</p>`:''}${w.url?`<a href="${esc(w.url)}" target="_blank">${esc(w.source||w.url)} ↗</a>`:''}</div>`}else{h+=`<div class="enr-empty">${esc(w.note||'Sem contexto web disponível.')}</div>`}if((w.researchAngles||[]).length)h+=`<ul>${w.researchAngles.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`;if((w.webSearchQueries||[]).length)h+=`<div class="enr-empty">Buscar antes da reunião:</div><ul>${w.webSearchQueries.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`;if((w.webResearchHints||[]).length)h+=`<ul>${w.webResearchHints.map(x=>`<li><span>${esc(x)}</span></li>`).join('')}</ul>`;return h}
function stageTabs(){return `<div class="stagebar"><div class="stage-tabs"><button class="stage-tab ${meetingStage==='prep'?'on':''}" onclick="setStage('prep')">1 · Preparação</button><button class="stage-tab ${meetingStage==='meeting'?'on':''}" onclick="setStage('meeting')">2 · Reunião</button><button class="stage-tab ${meetingStage==='post'?'on':''}" onclick="setStage('post')">3 · Pós-reunião</button></div><button class="btn sm ${presentMode?'lime':'ghost'}" onclick="togglePresent()">${presentMode?'Sair do modo apresentação':'Modo apresentação'}</button></div>`}
function postFields(){let f=((run&&run.postMeetingTemplate)||{}).fields||[];return f.map(x=>`<div class="section"><h3>${esc(x.label)}</h3><textarea class="post-fld" rows="2" oninput="postVals['${esc(x.key)}']=this.value" placeholder="${esc(x.hint||'Anotar...')}">${esc(postVals[x.key]||x.value||'')}</textarea>${x.hint?`<p class="post-hint">${esc(x.hint)}</p>`:''}</div>`).join('')}
function prepView(){let d=cur();return `<section class="panel game-card">${stageTabs()}<div class="client-meta" style="text-align:left"><b>${esc(d.dealName)}</b> · ${esc(clean(d.stageLabel))} · ${esc(d.owner)} · <a href="${esc(d.url)}" target="_blank">HubSpot ↗</a></div><div class="chips">${chips()}</div><div class="prep-grid"><div class="section enr"><h3>Diagnóstico já enviado</h3>${diagBlock()}</div><div class="section enr"><h3>Follow-ups importantes</h3>${followBlock()}</div><div class="section"><h3>Insights do diagnóstico</h3><ul>${(intel().meetingInsights||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div><div class="section"><h3>Perguntas faltantes</h3><ul>${(intel().discoveryQuestions||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div></div>${challengeBlock()}<div class="section enr"><h3>Contexto web</h3>${webBlock()}</div><div class="nav"><span></span><button class="btn lime" onclick="setStage('meeting')">Iniciar reunião →</button></div></section>`}
function road(){let icons=['♨','⇄','☟','♡','◉','▣','✦','✓'];let ps=phases();return `<section class="panel road">${ps.map((p,i)=>`<button class="road-step ${i===phase?'on':''} ${phaseComplete(i)?'done':''}" onclick="setPhase(${i})"><span class="road-icon">${icons[i%icons.length]}<span class="bubble">${i+1}</span></span><span class="road-title">${esc(p.title)}</span><span class="road-sub">${esc(p.screen||'')}</span></button>`).join('')}</section>`}
function objectiveCards(p){let a=p.preQuestions||[]; if(!a.length)return '<div class="empty">Sem objetivos configurados nesta fase.</div>';return `<div class="objective-grid">${a.map((x,i)=>`<button class="objective ${done[objKey(phase,i)]?'done':''}" onclick="toggleObj(${i})"><span class="n">${i+1}</span>${esc(x)}</button>`).join('')}</div>`}
function wizard(){let d=cur(), ps=phases(), p=ps[phase]||{}, c=objDone(), n=objCount(), pct=n?Math.round(c/n*100):0;return `${stageTabs()}<div class="chips">${chips()}</div>${road()}<section class="panel phase-card"><div class="phase-hero"><div class="phase-symbol">♨</div><div><div class="kicker">Fase ${phase+1} de ${ps.length} · ${esc(p.screen||'')}</div><h2>${esc(p.title)}</h2><p>${esc(p.value||'Conduza a conversa com clareza antes de demonstrar produto.')}</p></div><div class="donut" style="--pct:${pct}%" data-label="${pct}%"></div></div><div class="phase-body"><div class="section"><h3>☷ Objetivos da fase — ${c}/${n}</h3>${objectiveCards(p)}</div>${challengeBlock()}<div class="section"><h3>Perguntas antes de demonstrar</h3><div class="showbox">Use os objetivos acima como checklist de descoberta antes de abrir a tela.</div></div><div class="section"><h3>Agora mostre</h3><div class="showbox">${esc(p.show)}</div></div><div class="section"><h3>Valor para conectar</h3><p>${esc(p.value)}</p></div><div class="section"><h3>Como adaptar essa fase</h3><ul>${[...(intel().guideFocus||[]),...(intel().coachingTips||[])].slice(0,5).map(x=>`<li>${esc(x.principle||x)}</li>`).join('')}</ul></div>${p.id==='fechamento'?`<div class="section"><h3>Resumo pós-reunião (rascunho local)</h3>${postFields()}<div class="nav"><span></span><button class="btn ghost sm" onclick="setStage('post')">Abrir pós-reunião →</button></div></div>`:''}<div class="nav"><button class="btn ghost" onclick="setPhase(${phase-1})">‹ Fase anterior</button><span class="center-note">${c} de ${n} objetivos concluídos nesta fase</span><button class="btn orange" onclick="${phase<ps.length-1?`setPhase(${phase+1})`:`setStage('post')`}">${phase<ps.length-1?'Próxima fase: '+esc((ps[phase+1]||{}).title):'Ir para pós-reunião'} ›</button></div><div class="nav"><span></span><button class="btn lime" onclick="mark()">Marcar fase concluída</button></div></div></section>`}
function postView(){let d=cur(),t=(run&&run.postMeetingTemplate)||{};return `<section class="panel game-card">${stageTabs()}<h2>Pós-reunião · ${esc(d.dealName)}</h2><p class="client-meta" style="text-align:left">${esc(t.note||'Resumo estruturado da reunião.')}</p>${postFields()}<div class="nav"><button class="btn ghost" onclick="setStage('meeting')">← Voltar à reunião</button><span></span></div></section>`}
function stageView(){if(meetingStage==='prep')return prepView();if(meetingStage==='post')return postView();return wizard()}
function briefing(){let d=cur();return `${finder()}${dealGrid()}${d?gameCard():`<section class="panel game-card"><h2>Linha de produção de demonstração</h2><p class="hint">Selecione uma conta. O Roteiro monta um wizard Next > Next com perguntas antes da tela, adaptação por diagnóstico e boas práticas comerciais.</p></section>`}`}
function draw(){let cls=((run&&presentMode)?'app present':'app')+' theme-'+theme;document.getElementById('root').innerHTML=`<div class="${cls}">${headerHTML()}<main class="main">${run?(presentMode?stageView():finder()+dealGrid()+gameCard()+stageView()):briefing()}</main></div>`}
load().catch(e=>{document.getElementById('root').innerHTML='<pre>'+esc(e.message)+'</pre>'})
</script></body></html>'''
def page(): return HTML.replace('__CSS__',CSS)
def auth_page(): return '<!doctype html><title>Roteiro Comercial</title><div class="login"><div class="login-card"><h1>Roteiro Comercial</h1><p>Entrar com conta @zydon.com.br</p><a class="btn" href="/login?go=1">Entrar com Google</a></div></div><style>'+CSS+'</style>'
def send_json(h,obj,status=200):
 b=json.dumps(obj,ensure_ascii=False).encode(); h.send_response(status); h.send_header('Content-Type','application/json; charset=utf-8'); h.send_header('Content-Length',str(len(b))); h.end_headers(); h.wfile.write(b)
def send_html(h,txt,status=200):
 b=txt.encode(); h.send_response(status); h.send_header('Content-Type','text/html; charset=utf-8'); h.send_header('Content-Length',str(len(b))); h.end_headers(); h.wfile.write(b)
class H(BaseHTTPRequestHandler):
 def log_message(self,*a): pass
 def do_GET(self):
  path=urlparse(self.path).path; uid=identity(self)
  if path=='/health': return send_json(self,{'ok':True,'app':'roteiro','googleConfigured':google_configured(),'stages':ROTEIRO_STAGES,'time':datetime.now().isoformat()})
  if path=='/logo.png' and LOGO_PATH.exists():
   b=LOGO_PATH.read_bytes(); self.send_response(200); self.send_header('Content-Type','image/png'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b); return
  if path=='/logout':
   self.send_response(302); self.send_header('Set-Cookie',build_cookie(SESSION_COOKIE,'',0,secure=request_is_https(self))); self.send_header('Location','/login'); self.end_headers(); return
  if path=='/login':
   if 'go=1' in self.path and google_configured():
    st=make_state(); cfg=google_config(); url='https://accounts.google.com/o/oauth2/v2/auth?'+urllib.parse.urlencode({'client_id':cfg['client_id'],'redirect_uri':oauth_redirect_uri(self),'response_type':'code','scope':'openid email profile','state':st,'hd':'zydon.com.br','prompt':'select_account'})
    self.send_response(302); self.send_header('Set-Cookie',build_cookie(OAUTH_STATE_COOKIE,st,OAUTH_STATE_TTL,secure=request_is_https(self))); self.send_header('Location',url); self.end_headers(); return
   return send_html(self,auth_page())
  if path=='/oauth/callback':
   qs=parse_qs(urlparse(self.path).query); jar=cookies(self); st=qs.get('state',[''])[0]
   if OAUTH_STATE_COOKIE not in jar or not verify_state(st) or st!=jar[OAUTH_STATE_COOKIE].value: return send_html(self,'OAuth inválido',400)
   try:
    tok=google_exchange_code(qs.get('code',[''])[0],oauth_redirect_uri(self),google_config()); info=google_userinfo(tok.get('access_token','')); uid=uid_from_email(info.get('email',''))
    if not uid: return send_html(self,'Usuário não autorizado',403)
    self.send_response(302); self.send_header('Set-Cookie',build_cookie(SESSION_COOKIE,make_session(uid),SESSION_TTL,secure=request_is_https(self))); self.send_header('Location','/'); self.end_headers(); return
   except Exception as e: return send_html(self,'Erro OAuth: '+html.escape(str(e)),500)
  if not uid: self.send_response(302); self.send_header('Location','/login'); self.end_headers(); return
  if path=='/api/roteiro': return send_json(self,roteiro_load())
  if path=='/api/presentation-deals': return send_json(self,presentation_deals(uid))
  return send_html(self,page())
 def do_POST(self):
  uid=identity(self); path=urlparse(self.path).path
  if not uid: return send_json(self,{'ok':False,'error':'auth'},401)
  try:
   n=int(self.headers.get('Content-Length','0') or '0'); body=json.loads(self.rfile.read(n).decode() or '{}')
   if path=='/api/roteiro': return send_json(self,roteiro_save(uid,body))
   if path=='/api/start-presentation': return send_json(self,start_presentation(uid,body.get('dealId')))
   return send_json(self,{'ok':False,'error':'not found'},404)
  except Exception as e: return send_json(self,{'ok':False,'error':str(e)},500)

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--host',default='0.0.0.0'); ap.add_argument('--port',type=int,default=8290); a=ap.parse_args()
 httpd=ThreadingHTTPServer((a.host,a.port),H); print(f'Roteiro rodando em {a.host}:{a.port}',flush=True); httpd.serve_forever()
if __name__=='__main__': main()
