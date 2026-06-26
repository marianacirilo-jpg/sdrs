#!/usr/bin/env python3
"""Reconstrói o histórico do Zydon Channel a partir do ledger único dos dois crons.

Fontes:
- controle/wpp_envios.json: índice compartilhado dos crons SDR e diagnóstico 5min
- pesquisas/<slug>_msg.txt: texto exato do diagnóstico quando o ledger antigo não guardou `text`
- pdfs/Potencial-Digitalizacao-<slug>.pdf: PDF enviado ao lead quando disponível

Mantém mensagens live capturadas pela bridge (notify/append/api-send) e substitui apenas imports antigos.
"""
from __future__ import annotations
import json, pathlib, datetime, time, hashlib, re, glob

PROJ = pathlib.Path('/root/.hermes/zydon-prospeccao')
WPP = PROJ/'controle'/'wpp_envios.json'
PESQ = PROJ/'pesquisas'
PDFS = PROJ/'pdfs'
WA_DATA = pathlib.Path('/root/.hermes/whatsapp-extra/channel_data')
WA_DATA.mkdir(parents=True, exist_ok=True)
IMPORT_TYPES = {'cron-sdr-primeiro-contato','cron-mql-texto','cron-mql-pdf','cron-naomql-grupo','cron-whatsapp-texto','seed-wpp-envios'}
GROUP = '120363408131718880@g.us'

def load_wpp():
    data=json.loads(WPP.read_text(encoding='utf-8'))
    if isinstance(data, dict):
        rows=data.get('envios') or data.get('results') or []
        if isinstance(rows, dict): rows=list(rows.values())
    elif isinstance(data, list): rows=data
    else: rows=[]
    return [r for r in rows if isinstance(r,dict)]

def parse_ts(r):
    """Normaliza timestamps do ledger para epoch.

    Histórico real:
    - `process_gate_once.py` (diagnóstico MQL) grava `date` em BRT.
    - `disparo_dinamico.py` antigo gravava `date` com `time.strftime()` no servidor UTC.
    - `disparo_dinamico.py` novo grava `date_tz` ISO BRT explícito.

    Sem essa distinção, os painéis mostram envios recentes como horas atrasados
    ou deslocados para o futuro.
    """
    # Novo formato explícito: sempre preferir timezone embutido.
    explicit = str(r.get('date_tz') or r.get('sent_at') or '').strip()
    if explicit:
        try:
            dt = datetime.datetime.fromisoformat(explicit.replace('Z','+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=-3)))
            return int(dt.timestamp())
        except Exception:
            pass

    s=str(r.get('date') or r.get('data') or r.get('ts') or r.get('created_at') or '').strip()
    if not s: return int(time.time())
    s=s.replace('T',' ').replace('Z','').replace('/', '-').strip()
    # corrige strings quebradas antigas tipo "2026\n21 21:00" se aparecerem
    s=' '.join(s.split())
    naive=None
    for fmt in ('%Y-%m-%d %H:%M:%S','%Y-%m-%d %H:%M'):
        try:
            naive = datetime.datetime.strptime(s[:19] if fmt.endswith('S') else s[:16], fmt)
            break
        except Exception:
            pass
    if naive is None: return int(time.time())

    mt=str(r.get('msg_type') or '').lower()
    # Registros antigos de 1º contato SDR foram salvos em UTC pelo time.strftime().
    if mt == 'primeiro_contato':
        return int(naive.replace(tzinfo=datetime.timezone.utc).timestamp())
    # Diagnóstico/gate sempre registrou BRT.
    brt=datetime.timezone(datetime.timedelta(hours=-3))
    return int(naive.replace(tzinfo=brt).timestamp())

def norm_chat(to):
    if not to: return ''
    to=str(to).strip()
    if to=='grupo': return GROUP
    if '@' in to: return to
    digits=''.join(ch for ch in to if ch.isdigit())
    if not digits: return to
    return digits + '@s.whatsapp.net'

def sdr_port(r):
    for k in ('bridge_port','porta','lead_bridge_port'):
        v=r.get(k)
        if v:
            try: return int(v)
            except Exception: pass
    s=str(r.get('sdr') or r.get('conta') or '').lower()
    if 'sarah' in s: return 4601
    if 'breno' in s: return 4605
    if 'lucas' in s and 'resende' not in s: return 4603
    if 'rafael' in s: return 4607
    if 'resende' in s: return 4606
    return 4600

def group_port(r):
    for k in ('group_bridge_port','bridge_port','porta'):
        v=r.get(k)
        if v:
            try: return int(v)
            except Exception: pass
    return 4600

def primeiro_nome_valido(nome):
    nome=(nome or '').strip()
    return '' if not nome or nome.lower() in ('tudo bem','lead','cliente','none') else nome

def empresa_valida(empresa):
    empresa=(empresa or '').strip()
    return '' if not empresa or empresa.lower() in ('sem nome','sem empresa','none') else empresa

def escolher(sdr,nome,empresa,erp,total):
    return int(hashlib.sha256(f'{sdr}|{nome}|{empresa}|{erp}'.encode()).hexdigest()[:8],16)%total

def msg_breno(nome,empresa,erp=''):
    n=primeiro_nome_valido(nome); e=empresa_valida(empresa); saud=f'Oi, {n}.' if n else 'Oi, tudo bem?'; et=f' da {e}' if e else ''
    v=[f'{saud} Aqui é o Breno, da Zydon. Vi que você preencheu nosso formulário para conhecer melhor a nossa plataforma de digitalização de vendas. Correto?',f'{saud} Breno aqui, da Zydon. Recebi o cadastro{et} sobre digitalização de vendas e queria confirmar se faz sentido a gente conversar. Correto?',f'{saud} Aqui é o Breno da Zydon. Vi seu interesse em entender melhor nossa plataforma de vendas B2B. Posso te chamar por aqui mesmo?',f'{saud} Breno, da Zydon. Vi que chegou um formulário{et} para conhecer nossa plataforma de digitalização comercial. Você que solicitou?']
    return v[escolher('breno',nome,empresa,erp,len(v))]

def msg_sarah(nome,empresa,erp=''):
    n=primeiro_nome_valido(nome); e=empresa_valida(empresa); saud=f'Oie, {n}.' if n else 'Oie, tudo bem?'; et=f' da {e}' if e else ''
    v=[f'{saud} Aqui é a Sarah da Zydon, e-commerce b2b. Como você está? Recebi o seu cadastro e quero nos apresentar melhor. Você já vende on-line?',f'{saud} Sarah aqui, da Zydon. Recebi o cadastro{et} e queria entender melhor a operação de vocês. Hoje vocês já vendem on-line?',f'{saud} Aqui é a Sarah, da Zydon. Vi seu interesse em e-commerce B2B e queria nos apresentar melhor. Vocês já têm venda on-line hoje?',f'{saud} Sarah da Zydon por aqui. Chegou pra mim o cadastro{et}; queria confirmar algumas informações e entender se vocês já vendem on-line.']
    return v[escolher('sarah',nome,empresa,erp,len(v))]

def msg_lucas(nome,empresa,erp=''):
    n=primeiro_nome_valido(nome) or 'tudo bem'
    e=empresa_valida(empresa) or 'sua empresa'
    base=f'Olá {n}! Tudo bem?\nLucas aqui da Zydon.\n\nVocê solicitou um contato para fazer o *Diagnóstico Comercial B2B* da {e}.\n\n'
    if erp: return base+f'Notei aqui que vocês rodam a operação no {erp}. Gostaria de confirmar algumas informações para te direcionar para o meu melhor consultor e executar o diagnóstico com você.'
    return base+'Gostaria de confirmar algumas informações para te direcionar para o meu melhor consultor e executar o diagnóstico com você.'

def text_for_sdr(r):
    if r.get('text') or r.get('mensagem') or r.get('message'):
        return str(r.get('text') or r.get('mensagem') or r.get('message'))
    s=str(r.get('sdr') or '').lower(); nome=r.get('nome') or ''; empresa=r.get('empresa') or r.get('slug') or ''
    if 'breno' in s: return msg_breno(nome,empresa)
    if 'sarah' in s: return msg_sarah(nome,empresa)
    if 'lucas' in s: return msg_lucas(nome,empresa)
    return f'Primeiro contato SDR para {empresa}'.strip()

def msg_file(slug):
    if not slug: return ''
    p=PESQ/f'{slug}_msg.txt'
    return p.read_text(encoding='utf-8').strip() if p.exists() else ''

def pdf_for(slug, empresa=''):
    if slug:
        p=PDFS/f'Potencial-Digitalizacao-{slug}.pdf'
        if p.exists(): return str(p)
    # fallback por nome contendo slug/empresa
    needles=[slug, empresa]
    for n in needles:
        if not n: continue
        low=re.sub(r'[^a-z0-9]+','-',str(n).lower()).strip('-')
        for p in PDFS.glob('*.pdf'):
            hay=re.sub(r'[^a-z0-9]+','-',p.name.lower())
            if low and low in hay: return str(p)
    return ''

def text_for_mql(r):
    for k in ('text','mensagem','message','lead_text'):
        if r.get(k): return str(r[k])
    slug=r.get('slug') or ''
    m=msg_file(slug)
    if m: return m
    nome=r.get('nome') or 'tudo bem'; empresa=r.get('empresa') or r.get('slug') or 'sua empresa'
    return (f'Mensagem de diagnóstico enviada ao lead {nome} ({empresa}).\n'
            f'Observação: o registro antigo do cron confirmou o envio, mas não preservou o texto exato em wpp_envios.json nem em pesquisas/{slug}_msg.txt.')

def mk(port, chat, ts, rid, typ, text='', **extra):
    iso=datetime.datetime.fromtimestamp(ts).isoformat()
    empresa=extra.get('empresa') or ''
    return {
        'port':port,'id':rid,'chat':chat,'sender':'cron-import','participant':None,'fromMe':True,
        'type':typ,'text':text or '', 'mediaType':extra.get('mediaType'), 'mimetype':extra.get('mimetype'),
        'mediaName':extra.get('mediaName'), 'mediaPath':extra.get('mediaPath'), 'mediaUrl':extra.get('mediaUrl'),
        'timestamp':ts,'iso':iso,'status':extra.get('status'),'empresa':empresa,'nome':extra.get('nome'),
        'sdr':extra.get('sdr'),'owner_id':extra.get('owner_id'),'hubspot_owner_id':extra.get('hubspot_owner_id'),
        'email':extra.get('email'),'slug':extra.get('slug'),'source':'controle/wpp_envios.json'
    }

OWNER_ID_TO_SDR = {
    '86265630': 'Breno',
    '88063842': 'Sarah',
    '85778446': 'Lucas',
}


def build_records(rows):
    out=[]
    for idx,r in enumerate(rows):
        ts=parse_ts(r); slug=r.get('slug') or ''; empresa=r.get('empresa') or r.get('lead') or slug; nome=r.get('nome') or ''
        status=str(r.get('status') or '').lower(); mt=str(r.get('msg_type') or '').lower()
        chat=norm_chat(r.get('to') or r.get('jid') or r.get('lead_jid') or r.get('telefone'))
        base_id=str(r.get('messageId') or r.get('text_messageId') or r.get('messageId_texto') or f'wpp_{idx}_{slug}_{ts}')
        owner_id=str(r.get('owner_id') or r.get('hubspot_owner_id') or '').strip()
        sdr = r.get('sdr') or OWNER_ID_TO_SDR.get(owner_id) or r.get('sdr_original')
        common={'empresa':empresa,'nome':nome,'sdr':sdr,'owner_id':owner_id,'hubspot_owner_id':owner_id,'email':r.get('email'),'slug':slug,'status':r.get('status') or r.get('text_status')}
        if mt=='primeiro_contato':
            if not chat: continue
            out.append(mk(sdr_port(r), chat, ts, base_id+'_sdr_text', 'cron-sdr-primeiro-contato', text_for_sdr(r), **common))
        elif status in {'enviado_lead','enviado_mql'} or r.get('pdf_status') or r.get('file_response'):
            if not chat: continue
            p=sdr_port(r)
            out.append(mk(p, chat, ts, base_id+'_mql_text', 'cron-mql-texto', text_for_mql(r), **common))
            pdf= r.get('pdf_path') or pdf_for(slug, empresa)
            pdf_name=(pathlib.Path(pdf).name if pdf else f'Diagnóstico {empresa or slug}.pdf')
            out.append(mk(p, chat, ts+1, base_id+'_mql_pdf', 'cron-mql-pdf', f'PDF enviado: {pdf_name}', mediaType='document', mimetype='application/pdf', mediaName=pdf_name, mediaPath=pdf or None, **common))
            # se houve resumo para grupo, também entra na conversa do grupo
            gs=r.get('group_summary')
            if gs:
                out.append(mk(group_port(r), GROUP, ts+2, base_id+'_mql_group', 'cron-naomql-grupo', str(gs), **common))
        elif status=='nao_mql_grupo' or r.get('mql') is False:
            text=r.get('group_summary') or r.get('motivo') or r.get('reason') or f'Lead NÃO-MQL: {empresa or slug or r.get("email") or "sem empresa"}'
            out.append(mk(group_port(r), norm_chat(r.get('grupo') or r.get('group') or r.get('to') or GROUP), ts, base_id+'_naomql', 'cron-naomql-grupo', str(text), **common))
        elif chat and (r.get('text') or status in {'sent','enviado'}):
            out.append(mk(sdr_port(r), chat, ts, base_id+'_text', 'cron-whatsapp-texto', str(r.get('text') or r.get('mensagem') or r.get('message') or 'Mensagem WhatsApp enviada'), **common))
    return out

def load_existing_by_port():
    d={}
    for f in WA_DATA.glob('history_*.json'):
        try:
            port=int(f.stem.split('_')[1]); arr=json.loads(f.read_text(encoding='utf-8'))
            if not isinstance(arr,list): arr=[]
        except Exception: continue
        # remove imports antigos; preserva live bridge notify/append/api-send
        d[port]=[x for x in arr if x.get('type') not in IMPORT_TYPES and not str(x.get('type','')).startswith('cron-')]
    return d

def merge(existing, imports):
    byport=existing
    for rec in imports:
        byport.setdefault(int(rec['port']),[]).append(rec)
    summary={}
    for port, arr in byport.items():
        seen={}; merged=[]
        for x in arr:
            key=(x.get('id'),x.get('chat'),bool(x.get('fromMe')),x.get('type'))
            if key in seen:
                merged[seen[key]]={**merged[seen[key]], **x}
            else:
                seen[key]=len(merged); merged.append(x)
        merged.sort(key=lambda x: float(x.get('timestamp') or 0))
        (WA_DATA/f'history_{port}.json').write_text(json.dumps(merged[-5000:], ensure_ascii=False, indent=2), encoding='utf-8')
        summary[port]=len(merged)
    return summary

def main():
    rows=load_wpp(); imports=build_records(rows); summary=merge(load_existing_by_port(), imports)
    bytype={}
    for r in imports: bytype[r['type']]=bytype.get(r['type'],0)+1
    print(json.dumps({'wpp_rows':len(rows),'imported_messages':len(imports),'by_type':bytype,'history_counts':summary}, ensure_ascii=False, indent=2))
if __name__=='__main__': main()
