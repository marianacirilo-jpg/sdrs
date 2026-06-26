#!/usr/bin/env python3
"""Tenta recuperar WhatsApps dos leads pulados da campanha sumiço início de funil.
Não envia mensagens nem altera HubSpot.
"""
import csv, importlib.util, json, re, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path('/root/.hermes/zydon-prospeccao')
OUT=ROOT/'controle/sumico_inicio_funil'
PIPELINE='671008549'
STAGE_PRIMEIRO='1214320997'
CUTOFF_DAYS=21
BRT=timezone(timedelta(hours=-3))
OWNER_MAP={'86265630':'Breno','88063842':'Sarah','85778446':'Lucas Batista'}
PHONE_PROPS=['phone','mobilephone','hs_whatsapp_phone_number','hs_searchable_calculated_phone_number','hs_searchable_calculated_mobile_number','hs_searchable_calculated_international_phone_number','hs_searchable_calculated_international_mobile_number','hs_calculated_phone_number','hs_calculated_mobile_number']
CONTACT_PROPS=['firstname','lastname','email','company','createdate','recent_conversion_date']+PHONE_PROPS

spec=importlib.util.spec_from_file_location('d', str(ROOT/'disparo_dinamico.py'))
d=importlib.util.module_from_spec(spec); spec.loader.exec_module(d)

def parse_dt(raw):
    if not raw: return None
    s=str(raw).strip()
    try:
        if s.endswith('Z'): s=s[:-1]+'+00:00'
        dt=datetime.fromisoformat(s)
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception: return None

def digits(v): return ''.join(c for c in str(v or '') if c.isdigit())

def valid_mobile(v):
    ds=digits(v)
    if len(ds)==13 and ds.startswith('55'): ds=ds[2:]
    if len(ds)==12 and ds.startswith('55'): ds=ds[2:]
    if len(ds)==11 and ds[2]=='9':
        return ds, f'55{ds}@s.whatsapp.net', f'({ds[:2]}) {ds[2:7]}-{ds[7:]}'
    return None

def best_phone(props):
    for p in PHONE_PROPS:
        got=valid_mobile(props.get(p))
        if got: return p, got
    return None, None

def hs_get(path): return d.hs_request('https://api.hubapi.com'+path)

def batch_contacts(ids):
    if not ids: return {}
    res=d.hs_request('https://api.hubapi.com/crm/v3/objects/contacts/batch/read','POST',{'properties':CONTACT_PROPS,'inputs':[{'id':str(i)} for i in ids]}) or {}
    return {str(x.get('id')):x.get('properties',{}) or {} for x in res.get('results',[])}

def assoc_ids(obj, oid, to):
    res=hs_get(f'/crm/v3/objects/{obj}/{oid}/associations/{to}') or {}
    return [str(x.get('id')) for x in res.get('results',[]) if x.get('id')]

def search_contacts_company(term, limit=5):
    term=(term or '').strip()
    if not term: return []
    # sanitize shorter tokens, try company and email domain-ish tokens
    body={'filterGroups':[{'filters':[{'propertyName':'company','operator':'CONTAINS_TOKEN','value':term[:80]}]}], 'properties':CONTACT_PROPS, 'limit':limit}
    res=d.hs_request('https://api.hubapi.com/crm/v3/objects/contacts/search','POST',body) or {}
    return [(str(x.get('id')), x.get('properties',{}) or {}) for x in res.get('results',[])]

def deals_primeiro():
    body={'filterGroups':[{'filters':[{'propertyName':'pipeline','operator':'EQ','value':PIPELINE},{'propertyName':'dealstage','operator':'EQ','value':STAGE_PRIMEIRO}]}], 'properties':['dealname','hubspot_owner_id','createdate','notes_last_updated','notes_last_contacted','hs_latest_meeting_activity'], 'limit':100, 'sorts':[{'propertyName':'notes_last_updated','direction':'ASCENDING'}]}
    out=[]; after=None
    while True:
        if after: body['after']=after
        else: body.pop('after',None)
        res=d.hs_request('https://api.hubapi.com/crm/v3/objects/deals/search','POST',body) or {}
        out += res.get('results',[])
        after=((res.get('paging') or {}).get('next') or {}).get('after')
        if not after: break
    return out

def eligible_age(props):
    cutoff=datetime.now(timezone.utc)-timedelta(days=CUTOFF_DAYS)
    dts=[parse_dt(props.get(k)) for k in ('notes_last_updated','notes_last_contacted','hs_latest_meeting_activity')]
    last=max([x for x in dts if x], default=None) or parse_dt(props.get('createdate'))
    return last and last < cutoff, last

def main():
    rows=[]; summary={}
    for deal in deals_primeiro():
        did=str(deal['id']); props=deal.get('properties') or {}; owner=str(props.get('hubspot_owner_id') or '')
        ok_age,last=eligible_age(props)
        if not ok_age: continue
        if owner not in OWNER_MAP:
            summary['owner_fora_escopo']=summary.get('owner_fora_escopo',0)+1; continue
        dealname=props.get('dealname') or ''
        contact_ids=assoc_ids('deals', did, 'contacts')
        found=[]; source=''
        if contact_ids:
            contacts=batch_contacts(contact_ids)
            for cid,cprops in contacts.items():
                field, phone=best_phone(cprops)
                if phone:
                    found.append((cid,cprops,field,phone,'contact_associado'))
            if not found:
                summary['sem_celular_em_contato_associado']=summary.get('sem_celular_em_contato_associado',0)+1
        else:
            # tenta via empresas associadas ao deal
            company_ids=assoc_ids('deals', did, 'companies')
            for coid in company_ids:
                cids=assoc_ids('companies', coid, 'contacts')
                contacts=batch_contacts(cids[:20])
                for cid,cprops in contacts.items():
                    field,phone=best_phone(cprops)
                    if phone:
                        found.append((cid,cprops,field,phone,'company_associada'))
            # fallback por company/dealname token se não achou
            if not found and dealname:
                for cid,cprops in search_contacts_company(dealname, limit=5):
                    field,phone=best_phone(cprops)
                    if phone:
                        found.append((cid,cprops,field,phone,'busca_company_nome_deal'))
            if not found:
                summary['sem_contato_sem_phone_recuperado']=summary.get('sem_contato_sem_phone_recuperado',0)+1
        for cid,cprops,field,phone,src in found[:3]:
            raw,jid,fmt=phone
            rows.append({'deal_id':did,'dealname':dealname,'owner_id':owner,'sdr':OWNER_MAP[owner],'last_activity':last.isoformat() if last else '', 'contact_id':cid,'firstname':cprops.get('firstname') or '', 'lastname':cprops.get('lastname') or '', 'email':cprops.get('email') or '', 'company':cprops.get('company') or '', 'phone_field':field,'phone':raw,'jid':jid,'phone_fmt':fmt,'source':src})
    OUT.mkdir(parents=True, exist_ok=True)
    path=OUT/'recuperacao_whatsapps_pulados.csv'
    with path.open('w',encoding='utf-8',newline='') as f:
        fields=['deal_id','dealname','owner_id','sdr','last_activity','contact_id','firstname','lastname','email','company','phone_field','phone','jid','phone_fmt','source']
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    print(json.dumps({'recuperados':len(rows),'summary':summary,'csv':str(path)},ensure_ascii=False,indent=2))
    for r in rows[:20]:
        print(json.dumps(r,ensure_ascii=False))
if __name__=='__main__': main()
