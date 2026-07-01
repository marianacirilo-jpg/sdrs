#!/usr/bin/env python3
"""Fast Zydon inbound intake/review qualifier.

This script intentionally DOES NOT generate diagnostic PDFs and DOES NOT send
WhatsApp to leads. Rafael rule 2026-06-29: diagnosis is a consequence of a
confirmed MQL, not part of investigation.

Role of this 1-minute worker when enabled:
- detect recent form/demo/site/Facebook Lead Ads contacts;
- do a quick deterministic classification hint;
- write/update controle/mql_pipeline_queue.json for the main MQL pipeline;
- stay silent when nothing changes.

The slower/safer pipeline is responsible for confirmed-MQL PDF generation,
WhatsApp combo, HubSpot attachment, ledger and group notification.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path('/root/.hermes/zydon-prospeccao')
if str(ROOT / 'scripts') not in sys.path:
    sys.path.insert(0, str(ROOT / 'scripts'))
from zydon_operational_queues import update_json_locked  # noqa: E402
CONTROL = ROOT / 'controle'
PROCESSED = CONTROL / 'processed_emails.txt'
WPP = CONTROL / 'wpp_envios.json'
PIPELINE = CONTROL / 'mql_pipeline_queue.json'
LOCK = Path('/tmp/zydon_active_mql_qualifier.lock')
HS = 'https://api.hubapi.com'

CONTACT_PROPS = [
    'email','firstname','lastname','company','phone','mobilephone','hs_searchable_calculated_phone_number','hs_whatsapp_phone_number',
    'createdate','recent_conversion_date','recent_conversion_event_name','lifecyclestage','hubspot_owner_id','hs_object_source','hs_object_source_label',
    'hs_analytics_source','hs_analytics_source_data_1','hs_analytics_source_data_2','hs_latest_source','hs_latest_source_data_1','hs_latest_source_data_2',
    'qual_erp_utiliza_','selecione_o_sistema_de_gesto_erp','quantas_pessoas_atuam_na_sua_empresa','qual_o_faturamento_anual_da_sua_empresa_',
    'de_qual_forma_mais_vende_hoje_em_dia','vende_em_loja_virtual_','quantos_vendedores_internos_sua_empresa_possui',
    'voc_acredita_que_o_seu_cliente_compraria_sozinho_na_sua_loja_24h_por_dia_sem_precisar_de_vendedor',
    'qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados','qual_a_area_de_atuacao_de_sua_empresa_',
    'qual_seria_o_maior_problema_que_voc_enfrenta_em_sua_operao_atualmente','voc_vende_para_quem','cargo_area'
]


def now_iso_brt():
    return datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat()


def load_env():
    env = Path('/root/.hermes/credentials/hubspot.env')
    if env.exists():
        for line in env.read_text(errors='ignore').splitlines():
            if '=' in line and not line.strip().startswith('#'):
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def tok():
    load_env()
    t = (os.environ.get('HUBSPOT_PRIVATE_APP_TOKEN') or os.environ.get('HUBSPOT_TOKEN')
         or os.environ.get('HUBSPOT_ACCESS_TOKEN') or os.environ.get('HUBSPOT_API_KEY'))
    if not t:
        raise RuntimeError('HubSpot token ausente')
    return t


def hs(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        HS + path,
        data=data,
        method=method,
        headers={'Authorization': 'Bearer ' + tok(), 'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=35) as r:
        txt = r.read().decode()
        return json.loads(txt) if txt else {}


def only_digits(s):
    return re.sub(r'\D+', '', s or '')


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def final_emails():
    out = set()
    if PROCESSED.exists():
        for line in PROCESSED.read_text(errors='ignore').splitlines():
            if line.strip():
                out.add(line.split('|', 1)[0].strip().lower())
    data = load_json(WPP, {'envios': []})
    rows = data.get('envios', []) if isinstance(data, dict) else data
    final_statuses = {'enviado_lead','enviado_mql','nao_mql_grupo','mql_telefone_invalido_grupo'}
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, dict) and str(r.get('status') or '').lower() in final_statuses:
            e = str(r.get('email') or '').lower()
            if e:
                out.add(e)
    return out


def recent_form_contacts(hours=3):
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    body = {
        'filterGroups': [
            {'filters': [{'propertyName':'createdate','operator':'GTE','value':since}, {'propertyName':'hs_object_source','operator':'EQ','value':'FORM'}]},
            {'filters': [{'propertyName':'recent_conversion_date','operator':'GTE','value':since}]},
        ],
        'properties': CONTACT_PROPS,
        'limit': 50,
        'sorts': [{'propertyName':'createdate','direction':'ASCENDING'}],
    }
    return hs('POST', '/crm/v3/objects/contacts/search', body).get('results', [])


def _dt(s):
    try:
        return datetime.fromisoformat((s or '').replace('Z', '+00:00'))
    except Exception:
        return None


def is_reentry_contact(p):
    recent_dt = _dt(p.get('recent_conversion_date'))
    created_dt = _dt(p.get('createdate'))
    return bool(recent_dt and created_dt and (recent_dt - created_dt).total_seconds() > 300)


def is_test_or_internal_base(p):
    """Base teste/admin interno não entra na fila MQL."""
    blob = ' '.join(str(p.get(k) or '') for k in (
        'email','firstname','lastname','company','recent_conversion_event_name',
        'hs_analytics_source','hs_analytics_source_data_1','hs_analytics_source_data_2',
        'hs_latest_source','hs_latest_source_data_1','hs_latest_source_data_2',
    )).lower()
    return any(tok in blob for tok in (
        'form admin', 'base teste', ' leo testes', 'leonardo tester',
        'joao@empresa.com.br', 'empresa ltda.', 'empresa ltda', '+55(11) 99999-9999',
    ))


def is_form_signal(p, *, is_reentry=False):
    """Aceita form/Lead Ads; bloqueia eventos operacionais/teste."""
    if is_test_or_internal_base(p):
        return False
    event = (p.get('recent_conversion_event_name') or '').lower()
    blocked = ('meeting', 'meetings link', 'agenda', 'calendly', 'conversation',
               'conversations', 'whatsapp', 'whats app', 'chat', 'inbox', 'offline', 'call', 'interno')
    if event:
        if any(x in event for x in blocked):
            return False
        return True
    if is_reentry:
        return False
    src = (p.get('hs_object_source') or '').upper()
    label = (p.get('hs_object_source_label') or '').upper()
    latest = ' '.join(str(p.get(k) or '').lower() for k in ('hs_analytics_source','hs_latest_source','hs_latest_source_data_1','hs_latest_source_data_2'))
    return src == 'FORM' or label in {'FORM','FORMS'} or 'facebook' in latest


def domain_from_email(email):
    return (email.split('@', 1)[1].lower() if '@' in email else '').strip()


def fetch_site(domain):
    if not domain or domain in {'gmail.com','hotmail.com','outlook.com','yahoo.com.br','yahoo.com'}:
        return {'ok': False, 'domain': domain, 'summary': 'sem domínio corporativo validável'}
    for url in [f'https://{domain}', f'https://www.{domain}', f'http://{domain}']:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 ZydonQualificador/1.0'})
            with urllib.request.urlopen(req, timeout=8) as r:
                html = r.read(5000).decode('utf-8', 'ignore')
                title = re.search(r'<title[^>]*>(.*?)</title>', html, flags=re.I|re.S)
                text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))[:700]
                summary = ('title: ' + re.sub(r'\s+', ' ', title.group(1)).strip()[:160] + ' | ' if title else '') + 'texto: ' + text[:450]
                return {'ok': True, 'domain': domain, 'url': r.url, 'summary': summary}
        except Exception:
            continue
    return {'ok': False, 'domain': domain, 'summary': f'{domain}: site não abriu no ciclo rápido'}


def classify_hint(p, site):
    blob = ' '.join(str(p.get(k) or '') for k in CONTACT_PROPS).lower()
    company = (p.get('company') or '').lower()
    site_txt = (site.get('summary') or '').lower()
    strong_icp_terms = ['autope', 'motope', 'atacado', 'atacad', 'distribuidor', 'distribuidora', 'indústria', 'industria', 'importador', 'importadora', 'food service', 'hospitalar', 'produto médico', 'produtos medicos', 'posto', 'frota', 'oficina', 'revenda', 'lojista']
    obvious_disqualifiers = [
        'base teste', 'form admin', 'teste fake', 'lead teste', 'empresa teste',
        'sem empresa', 'não tenho empresa', 'nao tenho empresa', 'não tenho cnpj',
        'nao tenho cnpj', 'estudante', 'trabalho escolar', 'currículo', 'curriculo',
    ]
    # Regra Rafael 2026-07-01: os anúncios já vêm bem qualificados e os follow-ups
    # qualificam mais. Em dúvida/pending_review, considerar MQL e mandar para o
    # pipeline de diagnóstico. Só desqualificar automaticamente quando for óbvio
    # que é teste/fake/sem empresa/sem qualquer estrutura comercial real.
    if any(t in blob or t in company or t in site_txt for t in obvious_disqualifiers):
        return 'classified_non_mql_hint', 'Não-MQL: indício claro de teste/fake/sem empresa ou sem estrutura comercial real.'
    form_icp = any(t in blob or t in company for t in strong_icp_terms)
    public_icp = any(t in site_txt for t in strong_icp_terms)
    if form_icp or public_icp:
        return 'mql_candidate_needs_main_pipeline', 'MQL provável: formulário/site indicam ICP B2B; seguir diagnóstico e follow-up.'
    return 'mql_candidate_needs_main_pipeline', 'MQL por regra Rafael: lead de anúncio/formulário com dúvida inicial deve seguir diagnóstico; follow-ups qualificam mais. Só desqualificar teste/fake/sem estrutura clara.'


def upsert_pipeline(contact, state, reason, site):
    p = contact.get('properties') or {}
    email = (p.get('email') or '').strip().lower()
    if not email:
        return False
    key = f"{email}|{p.get('recent_conversion_date') or p.get('createdate') or ''}"
    changed = {'value': False}

    def update(data):
        if not isinstance(data, dict):
            data = {'items': []}
        items = data.setdefault('items', [])
        existing = next((x for x in items if isinstance(x, dict) and x.get('key') == key), None)
        # Sem ruído: se o candidato já foi registrado igual, manter o estado e não
        # imprimir de novo a cada minuto. Só há novidade quando é item novo ou mudou
        # state/reason/site_summary.
        if existing and existing.get('state') == state and existing.get('reason') == reason and existing.get('site_summary') == site.get('summary'):
            changed['value'] = False
            return data
        row = existing or {'key': key, 'events': []}
        row.update({
            'updated_at': now_iso_brt(),
            'state': state,
            'reason': reason,
            'contact_id': contact.get('id'),
            'email': email,
            'company': p.get('company'),
            'firstname': p.get('firstname'),
            'phone': p.get('hs_searchable_calculated_phone_number') or p.get('mobilephone') or p.get('phone'),
            'source': p.get('recent_conversion_event_name') or p.get('hs_latest_source_data_1') or p.get('hs_object_source_label'),
            'createdate': p.get('createdate'),
            'recent_conversion_date': p.get('recent_conversion_date'),
            'site_summary': site.get('summary'),
            'mql_confirmed': state in {'mql_candidate_needs_main_pipeline','mql_opportunity_needs_diagnostic','mql_confirmado_rafael_manual','mql_opportunity_diagnostico_autorizado'},
            'diagnostic_allowed': state in {'mql_candidate_needs_main_pipeline','mql_opportunity_needs_diagnostic','mql_confirmado_rafael_manual','mql_opportunity_diagnostico_autorizado'},
        })
        row.setdefault('events', []).append({'at': now_iso_brt(), 'state': state, 'reason': reason})
        if not existing:
            row['created_at'] = now_iso_brt()
            items.append(row)
        changed['value'] = True
        return data

    update_json_locked(PIPELINE, {'items': []}, update)
    return changed['value']


def main():
    CONTROL.mkdir(exist_ok=True)
    with LOCK.open('w') as lf:
        try:
            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        done = final_emails()
        out = []
        for c in recent_form_contacts(hours=3):
            p = c.get('properties') or {}
            email = (p.get('email') or '').strip().lower()
            is_reentry = is_reentry_contact(p)
            if not email or email in done or not is_form_signal(p, is_reentry=is_reentry) or (p.get('lifecyclestage') or '').lower() == 'customer':
                continue
            site = fetch_site(domain_from_email(email))
            lifecycle = (p.get('lifecyclestage') or '').strip().lower()
            if lifecycle == 'opportunity':
                state, reason = 'mql_opportunity_needs_diagnostic', 'Lifecycle opportunity: Rafael definiu que oportunidade segue diagnóstico/follow-up; não tratar como Não-MQL.'
            else:
                state, reason = classify_hint(p, site)
            if upsert_pipeline(c, state, reason, site):
                out.append(f"{state}: {p.get('company') or email} — {email} — {reason}")
        if out:
            print('\n'.join(out))


if __name__ == '__main__':
    main()
