#!/usr/bin/env python3
"""Roteiro Comercial Zydon — app standalone para roteiro.zydon.com.br.

Projeto separado do Channel. Porta padrão: 8290.
Regra de visibilidade do Roteiro: Rafael, Lucas Resende e líder de Growth veem tudo; demais usuários veem apenas a própria carteira executiva HubSpot.
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
PRESENTATION_RUNS_FILE=PROJECT/'controle'/'roteiro_presentation_runs.jsonl'
RESEARCH_FILE=PROJECT/'controle'/'roteiro_company_research.json'
SESSION_SECRET_FILE=PROJECT/'controle'/'roteiro_session_secret.txt'
GOOGLE_OAUTH_ENV=Path('/root/.hermes/credentials/google_oauth.env')
HUBSPOT_ENV=Path('/root/.hermes/credentials/hubspot.env')
LOGO_PATH=PROJECT/'motor'/'logo'/'zydon_full_black.png'
HUBSPOT_API='https://api.hubapi.com'
HUBSPOT_PORTAL_ID='48590774'
HUBSPOT_PIPELINE_ID='671008549'
PRESENTATION_STAGE_ID='990617426'
PRESENTATION_STAGE_LABEL='Apresentação Comercial 🎯'
HUBSPOT_OWNER_LABELS={'86265630':'Breno','88063842':'Sarah','85778446':'Lucas Batista'}
SESSION_COOKIE='zydon_roteiro_session'
OAUTH_STATE_COOKIE='zydon_roteiro_oauth_state'
SESSION_TTL=7*24*3600
OAUTH_STATE_TTL=3600
ALLOWED_EMAIL_DOMAINS=('zydon.com.br',)
ROTEIRO_VIEW_ALL_UIDS={'rafael','lucas_resende'}
ROTEIRO_GROWTH_ROLE_KEYS={'growth','growth_leader','leader_growth','lider_growth','líder_growth','head_growth','growth_head'}

PDF_STORY_SECTIONS=[
 {'id':'condicional-erp','title':'0. Condicional Big Four','body':'Se usa Bling, Omie, Olist ou Sankhya, abrir com contexto dos dados dele e uma demo próxima da realidade da empresa.'},
 {'id':'white-label','title':'1. Abertura: solução white label','body':'A solução é dele: marca, cores, banners e experiência comercial própria.'},
 {'id':'vitrine','title':'2. Vitrine de produtos','body':'Mostrar catálogo, categorias, banners, produtos mais comprados, últimos pedidos, recomendados e caminho até o carrinho.'},
 {'id':'login-acesso','title':'3. Login e solicitação de acesso','body':'Explicar login do cliente e login dedicado do vendedor/força de vendas.'},
 {'id':'home-inteligente','title':'4. Página inicial inteligente','body':'Busca inteligente, pedido rápido com IA via planilha, múltiplas tabelas, operações, estoque, unidades e variações.'},
 {'id':'checkout','title':'5. Checkout e conclusão','body':'Mostrar regras reais: pagamento à vista/a prazo, grupo de pagamento, limite de crédito e condições comerciais.'},
 {'id':'meus-pedidos','title':'6. Meus pedidos','body':'Histórico e acompanhamento de pedidos vindos do ERP ou portal, com status/entrega.'},
 {'id':'financeiro','title':'7. Financeiro','body':'Portal financeiro para boleto e nota fiscal, reduzindo dependência do vendedor.'},
 {'id':'app','title':'8. Aplicativo','body':'Citar app Vendas B2B; demonstrar se o prospect pedir ou se fizer sentido.'},
 {'id':'whatsapp','title':'9. Pedido direto no WhatsApp','body':'IA reconhece o cliente pelo telefone, consulta produto/status/financeiro e pode fechar pedido.'},
 {'id':'admin','title':'10. Painel ADMIN','body':'Construtor, Zydon Pay, relatórios, transações, projeção, carrinho abandonado, dashboards e solicitações de acesso.'},
]

def _parse_env_file(path):
    out={}
    try:
        if path.exists():
            for line in path.read_text(encoding='utf-8').splitlines():
                line=line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k,v=line.split('=',1); out[k.strip()]=v.strip().strip('"').strip("'")
    except Exception: pass
    return out

def google_config():
    cfg=_parse_env_file(GOOGLE_OAUTH_ENV)
    def get(k): return (os.environ.get(k) or cfg.get(k) or '').strip()
    return {'client_id':get('ROTEIRO_GOOGLE_CLIENT_ID') or get('GOOGLE_CLIENT_ID'), 'client_secret':get('ROTEIRO_GOOGLE_CLIENT_SECRET') or get('GOOGLE_CLIENT_SECRET')}
def google_configured():
    c=google_config(); return bool(c['client_id'] and c['client_secret'] and 'COLE_AQUI' not in c['client_id'])
def load_users():
    try: return json.loads(USERS_FILE.read_text(encoding='utf-8'))
    except Exception: return {}

def owner_label(oid):
    """Nome do proprietário quando conhecido; nunca devolve número solto."""
    oid=str(oid or '').strip()
    if not oid: return 'Sem proprietário'
    if oid in HUBSPOT_OWNER_LABELS: return HUBSPOT_OWNER_LABELS[oid]
    for uid,cfg in load_users().items():
        if str((cfg or {}).get('hubspot_owner_id') or '').strip()==oid:
            return str((cfg or {}).get('name') or uid)
    return 'Owner '+oid

def roteiro_is_growth_leader(uid,cfg):
    role=str((cfg or {}).get('role') or '').strip().lower().replace(' ','_').replace('-','_')
    title=str((cfg or {}).get('title') or (cfg or {}).get('cargo') or '').strip().lower()
    extra={x.strip() for x in os.environ.get('ROTEIRO_GROWTH_VIEW_ALL_UIDS','').split(',') if x.strip()}
    return uid in extra or role in ROTEIRO_GROWTH_ROLE_KEYS or ('growth' in title and ('lider' in title or 'líder' in title or 'leader' in title or 'head' in title))
def roteiro_can_view_all(uid):
    cfg=load_users().get(uid,{})
    return uid in ROTEIRO_VIEW_ALL_UIDS or roteiro_is_growth_leader(uid,cfg)
def roteiro_owner_id_for_user(uid):
    if roteiro_can_view_all(uid): return ''
    return str((load_users().get(uid,{}) or {}).get('hubspot_owner_id') or '')

def uid_from_email(email):
    email=str(email or '').strip().lower()
    if '@' not in email: return None
    local,domain=email.rsplit('@',1)
    if domain not in ALLOWED_EMAIL_DOMAINS: return None
    users=load_users(); normalized=local.split('+',1)[0]+'@'+domain
    for uid,cfg in users.items():
        if normalized in [str(e).strip().lower() for e in (cfg.get('emails') or [])]: return uid
    aliases={'rafael':'rafael','rafael.calixto':'rafael','calixto':'rafael','lucas.resende':'lucas_resende','lucas_resende':'lucas_resende','breno':'breno','sarah':'sarah','lucas':'lucas_batista','lucas.batista':'lucas_batista'}
    uid=aliases.get(local) or (local if local in users else None)
    return uid if uid in users else None

def _secret():
    try:
        if SESSION_SECRET_FILE.exists():
            s=SESSION_SECRET_FILE.read_text().strip()
            if s: return s.encode()
    except Exception: pass
    sec=secrets.token_urlsafe(48); SESSION_SECRET_FILE.parent.mkdir(parents=True,exist_ok=True); SESSION_SECRET_FILE.write_text(sec); os.chmod(SESSION_SECRET_FILE,0o600); return sec.encode()
SECRET=_secret()
def _b64u(b): return base64.urlsafe_b64encode(b).decode().rstrip('=')
def _b64d(s): return base64.urlsafe_b64decode(s+'='*(-len(s)%4))
def make_session(uid,ttl=SESSION_TTL):
    exp=str(int(time.time()+ttl)); msg=(uid+'|'+exp).encode(); sig=hmac.new(SECRET,msg,hashlib.sha256).digest(); return _b64u(uid.encode())+'.'+exp+'.'+_b64u(sig)
def verify_session(v):
    try:
        ub,exp,sb=str(v or '').split('.'); uid=_b64d(ub).decode(); sig=_b64d(sb); exp_sig=hmac.new(SECRET,(uid+'|'+exp).encode(),hashlib.sha256).digest()
        return uid if hmac.compare_digest(sig,exp_sig) and int(exp)>time.time() and uid in load_users() else None
    except Exception: return None
def make_state():
    nonce=secrets.token_urlsafe(16); ts=str(int(time.time())); sig=hmac.new(SECRET,(nonce+'|'+ts).encode(),hashlib.sha256).hexdigest()[:32]; return nonce+'.'+ts+'.'+sig
def verify_state(v):
    try:
        n,ts,sig=str(v or '').split('.'); exp=hmac.new(SECRET,(n+'|'+ts).encode(),hashlib.sha256).hexdigest()[:32]; return hmac.compare_digest(sig,exp) and int(ts)>=time.time()-OAUTH_STATE_TTL
    except Exception: return False
def build_cookie(name,value,max_age,secure=False,http_only=True,same_site='Lax'):
    if same_site=='None' and not secure: same_site='Lax'
    parts=[f'{name}={value}','Path=/',f'Max-Age={int(max_age)}',f'SameSite={same_site}']
    if http_only: parts.append('HttpOnly')
    if secure: parts.append('Secure')
    return '; '.join(parts)
def request_is_https(h): return 'https' in (h.headers.get('X-Forwarded-Proto') or '').lower() or (h.headers.get('Host','').split(':',1)[0].lower()=='roteiro.zydon.com.br')
def cookies(h):
    jar=http.cookies.SimpleCookie(); raw=h.headers.get('Cookie')
    if raw:
        try: jar.load(raw)
        except Exception: pass
    return jar
def identity(h):
    email=h.headers.get('Cf-Access-Authenticated-User-Email') or h.headers.get('CF-Access-Authenticated-User-Email') or ''
    if email:
        uid=uid_from_email(email)
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

def default_roteiro(): return {'ok':True,'title':'Roteiro de Apresentação Produto','subtitle':'Storytelling em linha do tempo/minhoca para conduzir a apresentação comercial.','style':'worm_timeline','sections':[dict(x) for x in PDF_STORY_SECTIONS]}
def roteiro_load():
    data=default_roteiro()
    try:
        if ROTEIRO_FILE.exists():
            raw=json.loads(ROTEIRO_FILE.read_text(encoding='utf-8') or '{}')
            if isinstance(raw,dict): data.update(raw); data['ok']=True
    except Exception as e: data['error']=str(e)
    return data
def roteiro_save(uid,body):
    if not isinstance(body,dict): raise ValueError('payload inválido')
    secs=[]
    for i,sec in enumerate((body.get('sections') or [])[:40]):
        if isinstance(sec,dict):
            title=str(sec.get('title') or f'Tampa {i+1}').strip()[:180]; text=str(sec.get('body') or '').strip()[:12000]
            if title or text: secs.append({'id':str(sec.get('id') or f'tampa-{i+1}')[:80],'title':title or f'Tampa {i+1}','body':text})
    if not secs: raise ValueError('inclua ao menos uma tampa')
    payload={'ok':True,'title':str(body.get('title') or 'Roteiro de Apresentação Produto')[:180],'subtitle':str(body.get('subtitle') or '')[:320],'style':'worm_timeline','sections':secs,'updatedAt':datetime.now(timezone.utc).isoformat(),'updatedBy':uid}
    ROTEIRO_FILE.parent.mkdir(parents=True,exist_ok=True); tmp=ROTEIRO_FILE.with_suffix('.json.tmp'); tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(ROTEIRO_FILE)
    with open(ROTEIRO_AUDIT_FILE,'a',encoding='utf-8') as f: f.write(json.dumps({'ts':payload['updatedAt'],'uid':uid,'sections':len(secs)},ensure_ascii=False)+'\n')
    return payload

def hubspot_token():
    if os.environ.get('HUBSPOT_API_KEY'): return os.environ['HUBSPOT_API_KEY'].strip()
    try:
        for line in HUBSPOT_ENV.read_text(encoding='utf-8').splitlines():
            if line.startswith('HUBSPOT_API_KEY='): return line.split('=',1)[1].strip().strip('"').strip("'")
    except Exception: pass
    return ''
def hs_request(method,path,token,payload=None,timeout=25):
    data=json.dumps(payload).encode() if payload is not None else None
    req=urllib.request.Request(HUBSPOT_API+path,data=data,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method=method)
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.loads(r.read().decode() or '{}')
def presentation_context(name):
    b=str(name or '').lower(); out=[]
    if re.search(r'farma|medicament|cosm|beauty|hair|beleza',b): out.append('Investigar mix, recorrência, representantes/televendas, tabela por cliente e reposição.')
    if re.search(r'café|alimento|foods|bebida|distrib|atacado',b): out.append('Investigar giro, pedido mínimo, prazo, condição e clientes por carteira.')
    if re.search(r'eco|limpeza|industrial|auto|peça|moto',b): out.append('Investigar catálogo, estoque, tabela, unidade alternativa e retrabalho do vendedor.')
    if not out: out.append('Começar por segmento, comprador, volume/recorrência, ERP, tabela por cliente e forma atual de pedido.')
    return out

def load_research_cache():
    try: return json.loads(RESEARCH_FILE.read_text(encoding='utf-8') or '{}') if RESEARCH_FILE.exists() else {}
    except Exception: return {}
def save_research_cache(c): RESEARCH_FILE.write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8')
def research_prompt_for_deal(deal): return f"Investigue a fundo a empresa {deal.get('dealName') or 'empresa'} para apresentação comercial Zydon B2B: segmento, cliente comprador, canais, recorrência/giro, ERP provável, dores de pedido/tabela/preço e perguntas de diagnóstico. Não invente; se não achar fonte, marque hipótese."
def research_for_deal(deal):
    cache=load_research_cache(); did=str(deal.get('dealId') or '')
    if did and did in cache: return cache[did]
    item={'status':'pendente_claude','company':deal.get('dealName') or '', 'generatedAt':datetime.now(timezone.utc).isoformat(), 'summary':'Investigação profunda pendente; usar hipóteses até preencher com fontes.', 'hypotheses':presentation_context(deal.get('dealName')), 'questions':['Qual ERP está em uso?','Quem compra e com que recorrência?','Pedido nasce no WhatsApp, planilha, ligação, vendedor ou portal?','Há tabela por cliente, condição de pagamento e limite de crédito?'], 'claudePrompt':research_prompt_for_deal(deal), 'sources':[]}
    if did: cache[did]=item; save_research_cache(cache)
    return item

def presentation_deals(uid='rafael'):
    token=hubspot_token()
    if not token: return {'configured':False,'error':'HubSpot não configurado','total':0,'deals':[],'owners':[]}
    filters=[{'propertyName':'pipeline','operator':'EQ','value':HUBSPOT_PIPELINE_ID},{'propertyName':'dealstage','operator':'EQ','value':PRESENTATION_STAGE_ID}]
    scope='consolidado HubSpot' if roteiro_can_view_all(uid) else 'somente sua carteira executiva'
    if not roteiro_can_view_all(uid):
        oid=roteiro_owner_id_for_user(uid)
        if not oid: return {'configured':True,'stageId':PRESENTATION_STAGE_ID,'stageLabel':PRESENTATION_STAGE_LABEL,'total':0,'deals':[],'owners':[],'scope':scope,'permission':'no_hubspot_owner'}
        filters.append({'propertyName':'hubspot_owner_id','operator':'EQ','value':oid})
    payload={'filterGroups':[{'filters':filters}], 'properties':['dealname','dealstage','pipeline','hubspot_owner_id','createdate','hs_lastmodifieddate','amount'], 'limit':100, 'sorts':[{'propertyName':'hs_lastmodifieddate','direction':'DESCENDING'}]}
    rows=[]; after=None
    while True:
        if after: payload['after']=after
        else: payload.pop('after',None)
        data=hs_request('POST','/crm/v3/objects/deals/search',token,payload)
        for d in data.get('results') or []:
            pr=d.get('properties') or {}; did=str(d.get('id') or ''); oid=str(pr.get('hubspot_owner_id') or ''); name=pr.get('dealname') or '(negócio sem nome)'
            rows.append({'dealId':did,'dealName':name,'ownerId':oid,'owner':owner_label(oid),'stageId':PRESENTATION_STAGE_ID,'stageLabel':PRESENTATION_STAGE_LABEL,'updatedAt':pr.get('hs_lastmodifieddate') or '', 'amount':pr.get('amount') or '', 'url':f'https://app.hubspot.com/contacts/{HUBSPOT_PORTAL_ID}/deal/{did}', 'contextHints':presentation_context(name)})
        after=((data.get('paging') or {}).get('next') or {}).get('after')
        if not after or len(rows)>=300: break
    owners=[]
    for r in rows:
        o=next((x for x in owners if x['ownerId']==r['ownerId']),None)
        if o: o['count']+=1
        else: owners.append({'ownerId':r['ownerId'],'owner':r['owner'],'count':1})
    return {'configured':True,'stageId':PRESENTATION_STAGE_ID,'stageLabel':PRESENTATION_STAGE_LABEL,'total':len(rows),'deals':rows[:300],'owners':owners,'scope':scope}
def start_presentation(uid,deal_id):
    deal=next((d for d in presentation_deals(uid).get('deals',[]) if str(d.get('dealId'))==str(deal_id)),None)
    if not deal: raise ValueError('negócio não encontrado nesta etapa/escopo')
    run={'runId':secrets.token_urlsafe(10),'ts':datetime.now(timezone.utc).isoformat(),'uid':uid,'dealId':deal['dealId'],'dealName':deal['dealName'],'owner':deal.get('owner'),'status':'started'}
    PRESENTATION_RUNS_FILE.parent.mkdir(parents=True,exist_ok=True)
    with open(PRESENTATION_RUNS_FILE,'a',encoding='utf-8') as f: f.write(json.dumps(run,ensure_ascii=False)+'\n')
    return {'ok':True,'run':run,'deal':deal,'research':research_for_deal(deal),'roteiro':roteiro_load()}

CSS=r'''
:root{--bg:#FBFCF8;--panel:#fff;--surface:#F4F6EC;--line:rgba(16,22,16,.10);--line2:rgba(16,22,16,.16);--txt:#13190F;--muted:#697065;--lime:#CDEB00;--lime-deep:#9FBE00;--ink:#0C0F0A;--radius:16px;--shadow:0 1px 2px rgba(16,22,16,.04),0 10px 28px rgba(16,22,16,.05)}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--txt);font-family:Inter,system-ui,-apple-system,Segoe UI,Arial,sans-serif;font-size:14px;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}.muted{color:var(--muted)}
.top{height:60px;display:flex;align-items:center;justify-content:space-between;padding:0 22px;border-bottom:1px solid var(--line);background:var(--panel);position:sticky;top:0;z-index:20}
.brand{display:flex;align-items:center;gap:11px;font-weight:800;letter-spacing:-.02em}.brand img{height:22px}.brand small{font-weight:500;color:var(--muted);letter-spacing:0;font-size:12px}
.top-actions{display:flex;align-items:center;gap:12px}.scope{font-size:12px;color:var(--muted)}
.btn{display:inline-flex;align-items:center;gap:8px;border:1px solid var(--ink);background:var(--ink);color:var(--lime);border-radius:999px;padding:10px 16px;font-weight:700;font-size:13px;cursor:pointer;transition:.15s;font-family:inherit}
.btn:hover{transform:translateY(-1px)}.btn.ghost{background:transparent;color:var(--txt);border-color:var(--line2)}.btn.ghost:hover{border-color:var(--ink)}
.btn.lime{background:var(--lime);color:var(--ink);border-color:var(--lime)}.btn.sm{padding:7px 13px;font-size:12px}.btn[disabled]{opacity:.5;pointer-events:none;transform:none}
.shell{display:grid;grid-template-columns:340px minmax(0,1fr);height:calc(100vh - 60px)}
.rail{border-right:1px solid var(--line);background:var(--panel);overflow:auto;padding:16px}
.main{overflow:auto;padding:26px 30px 64px}.main-wrap{max-width:940px;margin:0 auto}
.rail-h{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:12px}
.rail-h h2{margin:0;font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}.rail-h .cnt{font-size:12px;color:var(--muted)}
.search{width:100%;border:1px solid var(--line);background:var(--surface);border-radius:10px;padding:9px 11px;font:inherit;margin-bottom:12px;color:var(--txt)}
.owners{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px}
.opill{border:1px solid var(--line);background:var(--panel);border-radius:999px;padding:5px 11px;font-size:12px;font-weight:600;cursor:pointer;color:var(--muted);font-family:inherit}
.opill:hover{border-color:var(--ink)}.opill.on{background:var(--ink);color:#fff;border-color:var(--ink)}.opill.on b{color:var(--lime);font-weight:700}
.qlist{display:flex;flex-direction:column;gap:6px}
.qitem{text-align:left;border:1px solid var(--line);background:var(--panel);border-radius:12px;padding:11px 13px;cursor:pointer;transition:.12s;font-family:inherit}
.qitem:hover{border-color:var(--line2)}.qitem.on{border-color:var(--ink);box-shadow:inset 3px 0 0 var(--lime-deep)}
.qitem .nm{font-weight:700;font-size:13px;line-height:1.3;color:var(--txt)}
.qitem .mt{display:flex;gap:7px;margin-top:6px;font-size:11px;color:var(--muted);align-items:center}
.dot{width:4px;height:4px;border-radius:50%;background:var(--lime-deep);flex:none}
.empty{color:var(--muted);font-size:13px;padding:16px;border:1px dashed var(--line2);border-radius:12px;text-align:center;line-height:1.5}
.welcome{border:1px solid var(--line);background:var(--panel);border-radius:18px;padding:40px 30px;text-align:center;box-shadow:var(--shadow)}
.welcome h1{margin:0 0 8px;font-size:22px;letter-spacing:-.03em}.welcome p{margin:0 auto;max-width:440px;color:var(--muted);line-height:1.55}
.head{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;border:1px solid var(--line);background:var(--panel);border-radius:18px;padding:22px 24px;box-shadow:var(--shadow)}
.head h1{margin:0 0 8px;font-size:25px;letter-spacing:-.03em;line-height:1.15}
.head .meta{display:flex;flex-wrap:wrap;gap:8px;align-items:center;color:var(--muted);font-size:12px}
.tag{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);background:var(--surface);border-radius:999px;padding:4px 11px;font-size:12px;font-weight:600;color:var(--txt)}
.tag.stage{background:var(--ink);color:var(--lime);border-color:var(--ink)}
.link{color:var(--muted);font-weight:600;font-size:12px}.link:hover{color:var(--ink)}
.sec-title{font-size:12px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);font-weight:700;margin:28px 2px 12px}
.prep{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.pcard{border:1px solid var(--line);background:var(--panel);border-radius:14px;padding:16px;box-shadow:var(--shadow)}
.pcard h4{margin:0 0 12px;font-size:13px;display:flex;align-items:center;gap:9px;font-weight:700}
.pcard h4 .bar{width:16px;height:3px;border-radius:3px;background:var(--lime-deep);flex:none}
.pcard ul{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:9px}
.pcard li{font-size:13px;line-height:1.45;color:#33402f;padding-left:16px;position:relative}
.pcard li:before{content:"";position:absolute;left:0;top:6px;width:6px;height:6px;border-radius:50%;border:1.5px solid var(--lime-deep)}
.pcard p{margin:0;font-size:13px;line-height:1.5;color:#33402f}
.pstatus{font-size:11px;color:var(--muted);margin-top:12px;display:inline-flex;align-items:center;gap:6px}
.pstatus .dot{background:var(--lime-deep)}
.trail{display:flex;flex-direction:column;border:1px solid var(--line);border-radius:14px;overflow:hidden;background:var(--panel);box-shadow:var(--shadow)}
.trow{display:flex;gap:13px;align-items:flex-start;padding:12px 15px;border-bottom:1px solid var(--line)}
.trow:last-child{border-bottom:0}
.tn{flex:none;width:26px;height:26px;border-radius:8px;background:var(--surface);border:1px solid var(--line);display:grid;place-items:center;font-weight:700;font-size:12px;color:var(--muted)}
.trow .tt{font-weight:600;font-size:13px;line-height:1.3}.trow .td{font-size:12px;color:var(--muted);margin-top:2px;line-height:1.4}
.cock-head{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;margin-bottom:6px}
.cock-head h1{margin:0;font-size:20px;letter-spacing:-.02em}.cock-head .meta{display:flex;gap:8px;margin-top:6px;flex-wrap:wrap}
.progress{height:6px;border-radius:999px;background:var(--surface);overflow:hidden;margin:16px 0 22px}.progress>i{display:block;height:100%;background:var(--lime-deep);transition:width .35s}
.step{border:1px solid var(--line);background:var(--panel);border-radius:20px;padding:28px 30px;box-shadow:var(--shadow)}
.step .kicker{font-size:12px;color:var(--muted);font-weight:700;letter-spacing:.05em;text-transform:uppercase}
.step h2{margin:9px 0 16px;font-size:27px;letter-spacing:-.03em;line-height:1.12}
.step p{font-size:15px;line-height:1.65;color:#2c3729;margin:0 0 22px}
.step-foot{display:flex;align-items:center;justify-content:space-between;gap:12px;border-top:1px solid var(--line);padding-top:18px;flex-wrap:wrap}
.check{display:inline-flex;align-items:center;gap:10px;font-weight:600;font-size:13px;cursor:pointer;user-select:none}
.check input{width:18px;height:18px;accent-color:var(--lime-deep)}
.nav{display:flex;gap:8px}
.srail{display:flex;flex-direction:column;gap:2px}
.srow{display:flex;gap:11px;align-items:center;text-align:left;border:0;background:transparent;padding:9px 10px;border-radius:10px;cursor:pointer;width:100%;font-family:inherit}
.srow:hover{background:var(--surface)}.srow.on{background:var(--surface)}
.snum{flex:none;width:22px;height:22px;border-radius:50%;border:1.5px solid var(--line2);display:grid;place-items:center;font-size:11px;font-weight:700;color:var(--muted)}
.srow.on .snum{border-color:var(--ink);background:var(--ink);color:var(--lime)}
.srow.done .snum{border-color:var(--lime-deep);background:var(--lime-deep);color:var(--ink)}
.srow .stt{font-size:12.5px;font-weight:600;line-height:1.3;color:var(--muted)}.srow.on .stt{color:var(--ink)}.srow.done .stt{color:var(--txt)}
.back{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--muted);cursor:pointer;margin-bottom:16px;font-weight:600;background:none;border:0;padding:0;font-family:inherit}
.back:hover{color:var(--ink)}
.accord{border:1px solid var(--line);border-radius:14px;background:var(--panel);margin-top:24px;overflow:hidden;box-shadow:var(--shadow)}
.accord>summary{list-style:none;cursor:pointer;padding:15px 18px;font-weight:700;font-size:13px;display:flex;justify-content:space-between;align-items:center}
.accord>summary::-webkit-details-marker{display:none}.accord[open]>summary{border-bottom:1px solid var(--line)}.accord .abody{padding:18px}
.field{display:grid;gap:6px;margin-bottom:12px}.field label{font-size:12px;font-weight:600;color:var(--muted)}
.field input{width:100%;border:1px solid var(--line);background:var(--surface);border-radius:10px;padding:10px;font:inherit;color:var(--txt)}
.esec{border:1px solid var(--line);background:var(--surface);border-radius:12px;padding:13px;margin:10px 0}
.esec-head{display:flex;gap:8px;margin-bottom:8px;align-items:center}
.esec-head input{flex:1;border:1px solid var(--line);background:var(--panel);border-radius:8px;padding:9px;font:inherit;font-weight:600;color:var(--txt)}
.esec textarea{width:100%;border:1px solid var(--line);background:var(--panel);border-radius:8px;padding:10px;font:inherit;min-height:88px;resize:vertical;color:var(--txt)}
.linkbtn{border:0;background:transparent;color:var(--muted);cursor:pointer;font-size:12px;font-family:inherit}.linkbtn:hover{color:var(--ink);text-decoration:underline}
.editor-bar{display:flex;align-items:center;gap:12px;margin-top:16px;flex-wrap:wrap}
.login{min-height:100vh;display:grid;place-items:center;padding:20px}
.login-card{width:min(100%,440px);text-align:center;border:1px solid var(--line);background:#fff;border-radius:20px;padding:36px;box-shadow:var(--shadow)}
.login-card img{height:30px;margin-bottom:6px}.login-card h1{font-size:22px;margin:8px 0}.login-card p{color:var(--muted);font-size:13px;line-height:1.55}
@media(max-width:860px){.shell{grid-template-columns:1fr;height:auto}.rail{border-right:0;border-bottom:1px solid var(--line)}.prep{grid-template-columns:1fr}.head{flex-direction:column}.main{padding:18px 16px 50px}.step{padding:22px}.step h2{font-size:22px}}
'''
HTML=r'''<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Roteiro Comercial · Zydon</title><style>__CSS__</style></head><body><div id="root"></div><script>
let roteiro=null,deals=null,activeDeal='',ownerFilter='all',q='',run=null,mode='briefing',stepIdx=0,done={},showEditor=false,starting=false,statusMsg='Pronto.';
function esc(s){return (s??'').toString().replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
function cleanStage(s){return (s||'').replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2190}-\u{21FF}\u{FE0F}]/gu,'').trim()}
async function api(path,opts={}){const r=await fetch(path,opts); if(!r.ok) throw new Error((await r.text())||('Erro '+r.status)); return r.json()}
async function load(){try{[roteiro,deals]=await Promise.all([api('/api/roteiro'),api('/api/presentation-deals')]);}catch(e){deals={error:e.message,deals:[]}; roteiro=roteiro||{sections:[]}} draw()}
function sections(){return (roteiro&&roteiro.sections)||[]}
function allDeals(){return (deals&&deals.deals)||[]}
function filteredDeals(){let a=allDeals(); if(ownerFilter!=='all') a=a.filter(d=>String(d.ownerId||'')===String(ownerFilter)); if(q.trim()){let t=q.trim().toLowerCase(); a=a.filter(d=>(d.dealName||'').toLowerCase().includes(t)||(d.owner||'').toLowerCase().includes(t))} return a}
function activeDealObj(){return activeDeal?(allDeals().find(d=>d.dealId===activeDeal)||null):null}
function doneCount(){return Object.keys(done).filter(k=>done[k]).length}

function selectDeal(id){activeDeal=id; run=null; mode='briefing'; stepIdx=0; done={}; showEditor=false; draw()}
function backToQueue(){mode='briefing'; run=null; stepIdx=0; done={}; draw()}
function setStep(i){let n=sections().length; stepIdx=Math.max(0,Math.min(i,n-1)); draw()}
function toggleDone(id){done[id]=!done[id]; draw()}
function toggleEditor(){showEditor=!showEditor; draw()}
async function startPresentation(){let d=activeDealObj(); if(!d)return; starting=true; draw(); try{run=await api('/api/start-presentation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dealId:d.dealId})}); roteiro=run.roteiro||roteiro; mode='cockpit'; stepIdx=0; done={};}catch(e){run={error:e.message}} starting=false; draw()}

function statusLabel(s){return ({'pendente_claude':'Pesquisa aprofundada pendente do Claude'}[s])||s}
function prepPanel(d){
 let r=run&&run.research&&!run.error?run.research:null;
 let summary=r?(r.summary||''):'A pesquisa aprofundada é montada ao iniciar a apresentação. Até lá, conduza pelas hipóteses e perguntas ao lado.';
 let hyp=(r&&r.hypotheses&&r.hypotheses.length?r.hypotheses:(d.contextHints||[]));
 let qs=(r&&r.questions&&r.questions.length?r.questions:['Qual ERP está em uso hoje?','Quem compra e com que recorrência?','Como o pedido nasce: WhatsApp, planilha, ligação, vendedor ou portal?','Há tabela por cliente, condição de pagamento e limite de crédito?']);
 let src=(r&&r.sources)||[];
 return `<div class="prep">
  <div class="pcard"><h4><span class="bar"></span>Pesquisa</h4><p>${esc(summary)}</p>${src.length?`<ul style="margin-top:10px">${src.map(s=>`<li>${esc(s)}</li>`).join('')}</ul>`:''}${r&&r.status?`<div class="pstatus"><span class="dot"></span>${esc(statusLabel(r.status))}</div>`:''}</div>
  <div class="pcard"><h4><span class="bar"></span>Hipóteses</h4><ul>${hyp.length?hyp.map(h=>`<li>${esc(h)}</li>`).join(''):'<li>Defina segmento e dor principal antes de demonstrar.</li>'}</ul></div>
  <div class="pcard"><h4><span class="bar"></span>Perguntas de descoberta</h4><ul>${qs.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>
 </div>`;
}
function trailPreview(){let secs=sections(); if(!secs.length)return '<div class="empty">Roteiro vazio. Use o editor para montar a trilha.</div>'; return `<div class="trail">${secs.map((s,i)=>`<div class="trow"><span class="tn">${i+1}</span><div><div class="tt">${esc(s.title)}</div><div class="td">${esc(s.body)}</div></div></div>`).join('')}</div>`}

function briefing(d){
 let st=cleanStage(d.stageLabel)||'Apresentação Comercial';
 return `<div class="head">
  <div><h1>${esc(d.dealName)}</h1>
   <div class="meta"><span class="tag stage">${esc(st)}</span><span class="tag">${esc(d.owner)}</span>${d.amount?`<span class="tag">R$ ${esc(d.amount)}</span>`:''}<a class="link" target="_blank" href="${esc(d.url)}">Abrir no HubSpot ↗</a></div>
  </div>
  <button class="btn lime" ${starting?'disabled':''} onclick="startPresentation()">${starting?'Preparando cockpit…':'Iniciar apresentação →'}</button>
 </div>
 ${run&&run.error?`<div class="empty" style="margin-top:14px;border-color:var(--line2)">Não foi possível iniciar: ${esc(run.error)}</div>`:''}
 <div class="sec-title">Preparação · antes de demonstrar</div>
 ${prepPanel(d)}
 <div class="sec-title">Trilha de apresentação · ${sections().length} etapas</div>
 ${trailPreview()}`;
}

function cockpit(d){
 let secs=sections(); if(!secs.length)return briefing(d);
 if(stepIdx>=secs.length)stepIdx=secs.length-1;
 let s=secs[stepIdx], n=secs.length, st=cleanStage(d.stageLabel)||'Apresentação Comercial';
 let pct=Math.round(doneCount()/n*100);
 return `<div class="cock-head">
   <div><h1>${esc(d.dealName)}</h1><div class="meta"><span class="tag stage">${esc(st)}</span><span class="tag">${esc(d.owner)}</span><a class="link" target="_blank" href="${esc(d.url)}">HubSpot ↗</a></div></div>
   <button class="btn ghost sm" onclick="backToQueue()">Encerrar</button>
 </div>
 <div class="progress"><i style="width:${pct}%"></i></div>
 <div class="step">
   <div class="kicker">Etapa ${stepIdx+1} de ${n}${done[s.id]?' · concluída':''}</div>
   <h2>${esc(s.title)}</h2>
   <p>${esc(s.body)}</p>
   <div class="step-foot">
     <label class="check"><input type="checkbox" ${done[s.id]?'checked':''} onchange="toggleDone('${esc(s.id)}')"> Apresentei esta etapa</label>
     <div class="nav"><button class="btn ghost sm" ${stepIdx<=0?'disabled':''} onclick="setStep(${stepIdx-1})">← Anterior</button><button class="btn sm" ${stepIdx>=n-1?'disabled':''} onclick="setStep(${stepIdx+1})">Próxima →</button></div>
   </div>
 </div>
 <details class="accord"><summary><span>Briefing &amp; pesquisa da empresa</span><span class="muted">abrir</span></summary><div class="abody">${prepPanel(d)}</div></details>`;
}

function queueRail(){
 if(!deals)return '<div class="empty">Carregando HubSpot…</div>';
 if(deals.error)return `<div class="empty">${esc(deals.error)}</div>`;
 let os=(deals.owners||[]); let a=filteredDeals();
 let pills=`<button class="opill ${ownerFilter==='all'?'on':''}" onclick="ownerFilter='all';draw()">Todos <b>${deals.total||0}</b></button>`+
   os.map(o=>`<button class="opill ${ownerFilter===String(o.ownerId)?'on':''}" onclick="ownerFilter='${esc(o.ownerId)}';draw()">${esc(o.owner)} <b>${o.count}</b></button>`).join('');
 let list=a.length?a.map(d=>`<button class="qitem ${d.dealId===activeDeal?'on':''}" onclick="selectDeal('${esc(d.dealId)}')"><div class="nm">${esc(d.dealName)}</div><div class="mt"><span>${esc(d.owner)}</span><span class="dot"></span><span>${esc((d.contextHints||[])[0]||'Preparar reunião')}</span></div></button>`).join('')
   :`<div class="empty">Nenhum negócio em Apresentação Comercial neste escopo.${deals.permission==='no_hubspot_owner'?' Sem owner HubSpot vinculado.':''}</div>`;
 return `<div class="rail-h"><h2>Fila de apresentações</h2><span class="cnt">${a.length}</span></div>
  <input class="search" placeholder="Buscar empresa ou proprietário" value="${esc(q)}" oninput="q=this.value;draw()">
  <div class="owners">${pills}</div>
  <div class="qlist">${list}</div>`;
}
function cockpitRail(){
 let secs=sections();
 return `<button class="back" onclick="backToQueue()">← Voltar à fila</button>
  <div class="rail-h"><h2>Trilha</h2><span class="cnt">${doneCount()}/${secs.length}</span></div>
  <div class="srail">${secs.map((s,i)=>`<button class="srow ${i===stepIdx?'on':''} ${done[s.id]?'done':''}" onclick="setStep(${i})"><span class="snum">${done[s.id]?'✓':i+1}</span><span class="stt">${esc(s.title)}</span></button>`).join('')}</div>`;
}

function draft(){return {title:document.getElementById('e-title')?.value||'',subtitle:document.getElementById('e-subtitle')?.value||'',sections:[...document.querySelectorAll('.esec')].map((el,i)=>({id:el.dataset.id||('tampa-'+i),title:el.querySelector('[data-title]').value,body:el.querySelector('[data-body]').value})).filter(x=>x.title||x.body)}}
function addSec(){roteiro=draft(); roteiro.sections.push({id:'etapa-'+Date.now(),title:'Nova etapa',body:''}); draw()}
function rmSec(id){roteiro=draft(); roteiro.sections=roteiro.sections.filter(s=>String(s.id)!==String(id)); draw()}
async function save(){statusMsg='Salvando…'; let el=document.getElementById('e-status'); if(el)el.textContent=statusMsg; try{roteiro=await api('/api/roteiro',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(draft())}); statusMsg='Roteiro salvo.'; draw()}catch(e){statusMsg='Erro: '+e.message; let s=document.getElementById('e-status'); if(s)s.textContent=statusMsg}}
function editorView(){
 let secs=sections();
 return `<button class="back" onclick="toggleEditor()">← Voltar à execução</button>
  <div class="sec-title">Editor do roteiro oficial</div>
  <div class="field"><label>Título</label><input id="e-title" value="${esc((roteiro&&roteiro.title)||'')}"></div>
  <div class="field"><label>Descrição</label><input id="e-subtitle" value="${esc((roteiro&&roteiro.subtitle)||'')}"></div>
  ${secs.map(s=>`<div class="esec" data-id="${esc(s.id)}"><div class="esec-head"><input data-title value="${esc(s.title)}"><button class="linkbtn" onclick="rmSec('${esc(s.id)}')">Remover</button></div><textarea data-body>${esc(s.body)}</textarea></div>`).join('')}
  <div class="editor-bar"><button class="btn ghost sm" onclick="addSec()">+ Adicionar etapa</button><button class="btn lime sm" onclick="save()">Salvar roteiro</button><span class="muted" id="e-status">${esc(statusMsg)}</span></div>`;
}

function welcome(){
 let t=(deals&&deals.total)||0;
 return `<div class="welcome"><h1>Linha de produção comercial</h1><p>Selecione uma empresa na fila à esquerda para montar o cockpit da reunião: quem é o negócio, o que confirmar antes de demonstrar e a trilha de apresentação a seguir.</p><div class="sec-title" style="text-align:center">${t} negócio${t===1?'':'s'} em Apresentação Comercial neste escopo</div></div>`;
}
function mainHTML(){
 if(showEditor)return editorView();
 if(!deals)return '<div class="empty">Carregando HubSpot…</div>';
 if(deals.error)return `<div class="empty">${esc(deals.error)}</div>`;
 let d=activeDealObj();
 if(!d)return welcome();
 return (mode==='cockpit'&&run&&!run.error)?cockpit(d):briefing(d);
}
function railHTML(){return `<div class="rail">${(mode==='cockpit'&&run&&!run.error&&!showEditor)?cockpitRail():queueRail()}</div>`}
function topbar(){
 let scope=(deals&&deals.scope)||'@zydon.com.br';
 return `<div class="top"><div class="brand"><img src="/logo.png"> Roteiro Comercial <small>· apresentação B2B</small></div><div class="top-actions"><span class="scope">${esc(scope)}</span><button class="btn ghost sm" onclick="toggleEditor()">${showEditor?'Fechar editor':'Editar roteiro'}</button><a class="btn ghost sm" href="/logout">Sair</a></div></div>`;
}
function draw(){document.getElementById('root').innerHTML=topbar()+`<div class="shell">${railHTML()}<div class="main"><div class="main-wrap">${mainHTML()}</div></div></div>`}
load();
</script></body></html>'''.replace('__CSS__',CSS)

def auth_page(title='Roteiro Comercial'):
    return f'<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{CSS}</style></head><body><div class="login"><div class="login-card"><img src="/logo.png"><h1>Roteiro Comercial</h1><p>Entre com sua conta <b>@zydon.com.br</b>. Projeto separado do Channel.</p><a class="btn" href="/login?go=1">Entrar com Google</a></div></div></body></html>'
class H(BaseHTTPRequestHandler):
    server_version='ZydonRoteiro/1.2'; protocol_version='HTTP/1.1'
    def log_message(self,fmt,*args): print('[%s] '%datetime.now().isoformat(timespec='seconds')+fmt%args)
    def sendb(self,code,body,ctype='application/json; charset=utf-8',cookies=None):
        self.send_response(code); self.send_header('Content-Type',ctype); self.send_header('Cache-Control','no-store'); self.send_header('X-Robots-Tag','noindex,nofollow'); self.send_header('Content-Length',str(len(body)))
        for c in (cookies or []): self.send_header('Set-Cookie',c)
        self.end_headers(); self.wfile.write(body)
    def redirect(self,loc,cookies=None):
        self.send_response(302); self.send_header('Location',loc); self.send_header('Content-Length','0'); self.send_header('Cache-Control','no-store')
        for c in (cookies or []): self.send_header('Set-Cookie',c)
        self.end_headers()
    def do_GET(self):
        parsed=urlparse(self.path); path=parsed.path; uid=identity(self)
        if path=='/health': return self.sendb(200,json.dumps({'ok':True,'app':'roteiro','googleConfigured':google_configured(),'time':datetime.now().isoformat()}).encode())
        if path=='/logo.png':
            try: return self.sendb(200,LOGO_PATH.read_bytes(),'image/png')
            except Exception: return self.sendb(404,b'not found','text/plain')
        if path=='/login':
            if uid: return self.redirect('/')
            if not google_configured(): return self.sendb(200,b'Google OAuth nao configurado','text/plain')
            qs=parse_qs(parsed.query)
            if not (qs.get('go') or [''])[0]: return self.sendb(200,auth_page().encode(),'text/html; charset=utf-8')
            state=make_state(); cfg=google_config(); params={'client_id':cfg['client_id'],'redirect_uri':oauth_redirect_uri(self),'response_type':'code','scope':'openid email profile','state':state,'access_type':'online','prompt':'select_account','hd':'zydon.com.br'}
            return self.redirect('https://accounts.google.com/o/oauth2/v2/auth?'+urllib.parse.urlencode(params),cookies=[build_cookie(OAUTH_STATE_COOKIE,state,OAUTH_STATE_TTL,request_is_https(self),same_site='None')])
        if path=='/oauth/callback':
            qs=parse_qs(parsed.query); code=(qs.get('code') or [''])[0]; state=(qs.get('state') or [''])[0]; jar=cookies(self); cookie_state=jar[OAUTH_STATE_COOKIE].value if OAUTH_STATE_COOKIE in jar else ''; secure=request_is_https(self); clear=build_cookie(OAUTH_STATE_COOKIE,'',0,secure)
            if not code or not state or not verify_state(state) or not (cookie_state and hmac.compare_digest(state,cookie_state)): return self.sendb(400,b'Falha OAuth','text/plain')
            try: tok=google_exchange_code(code,oauth_redirect_uri(self),google_config()); info=google_userinfo(tok.get('access_token') or '')
            except Exception: return self.sendb(502,b'Falha no Google OAuth','text/plain')
            uid=uid_from_email(str(info.get('email') or ''))
            if not uid or not info.get('email_verified',True): return self.sendb(403,b'Acesso negado: use @zydon.com.br autorizado','text/plain',cookies=[clear])
            return self.redirect('/',cookies=[build_cookie(SESSION_COOKIE,make_session(uid),SESSION_TTL,secure,same_site='None'),clear])
        if path=='/logout': return self.redirect('/login',cookies=[build_cookie(SESSION_COOKIE,'',0,request_is_https(self))])
        if not uid:
            if path in ('/','/index.html'): return self.redirect('/login')
            return self.sendb(403,b'Acesso negado','text/plain')
        if path in ('/','/index.html'): return self.sendb(200,HTML.encode(),'text/html; charset=utf-8')
        if path=='/api/roteiro': return self.sendb(200,json.dumps(roteiro_load(),ensure_ascii=False).encode())
        if path=='/api/presentation-deals': return self.sendb(200,json.dumps(presentation_deals(uid),ensure_ascii=False).encode())
        return self.sendb(404,b'Not found','text/plain')
    def do_POST(self):
        uid=identity(self); parsed=urlparse(self.path)
        if not uid: return self.sendb(403,b'Acesso negado','text/plain')
        try:
            n=int(self.headers.get('Content-Length','0') or 0); body=json.loads(self.rfile.read(n).decode() or '{}') if n>0 else {}
        except Exception: body={}
        if parsed.path=='/api/roteiro':
            try: return self.sendb(200,json.dumps(roteiro_save(uid,body),ensure_ascii=False).encode())
            except Exception as e: return self.sendb(400,json.dumps({'ok':False,'error':str(e)},ensure_ascii=False).encode())
        if parsed.path=='/api/start-presentation':
            try: return self.sendb(200,json.dumps(start_presentation(uid,body.get('dealId')),ensure_ascii=False).encode())
            except Exception as e: return self.sendb(404,json.dumps({'ok':False,'error':str(e)},ensure_ascii=False).encode())
        return self.sendb(404,b'Not found','text/plain')
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--host',default='0.0.0.0'); ap.add_argument('--port',type=int,default=8290); args=ap.parse_args(); httpd=ThreadingHTTPServer((args.host,args.port),H); print(f'Roteiro rodando em {args.host}:{args.port}',flush=True); httpd.serve_forever()
if __name__=='__main__': main()
