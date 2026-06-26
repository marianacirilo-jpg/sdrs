#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ciclo Zydon: busca leads novos no HubSpot, gera PDF, envia WhatsApp
e salva controle local + Drive.
"""
import os, sys, json, re, subprocess, time
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import urllib.request, urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'motor'))
from batch_prepare import build_lead_dict, leads
import gen as gen_module
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
HUBSPOT_TOKEN = os.environ.get('HUBSPOT_API_KEY', '')
if not HUBSPOT_TOKEN:
    raise SystemExit('[FATAL] Defina HUBSPOT_API_KEY no ambiente.')
BASE_URL = "https://api.hubapi.com"
HEADERS = {"Authorization": f"Bearer {HUBSPOT_TOKEN}", "Content-Type": "application/json"}

CONTROLE_DIR = BASE_DIR / 'controle'
PROCESSED_EMAILS = str(CONTROLE_DIR / 'processed_emails.txt')
CICLO_LOG = str(CONTROLE_DIR / 'ciclo.log')
WPP_ENVIOS = str(CONTROLE_DIR / 'wpp_envios.json')
PENDENTES = str(CONTROLE_DIR / 'pendentes_validacao.json')
GROUP_JID = '120363408131718880@g.us'
BRIDGE = 'http://127.0.0.1:4600'

os.makedirs(CONTROLE_DIR, exist_ok=True)

def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    with open(CICLO_LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def load_processed():
    if not os.path.exists(PROCESSED_EMAILS):
        return set()
    with open(PROCESSED_EMAILS, 'r', encoding='utf-8') as f:
        return set(line.strip().lower().split('|')[0] for line in f if line.strip())

def save_processed(email):
    with open(PROCESSED_EMAILS, 'a', encoding='utf-8') as f:
        f.write(email.lower() + '\n')

def load_wpp_envios():
    if not os.path.exists(WPP_ENVIOS):
        return []
    with open(WPP_ENVIOS, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_wpp_envios(envios):
    with open(WPP_ENVIOS, 'w', encoding='utf-8') as f:
        json.dump(envios, f, ensure_ascii=False, indent=2)

def load_pendentes():
    if not os.path.exists(PENDENTES):
        return []
    with open(PENDENTES, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_pendentes(pendentes):
    with open(PENDENTES, 'w', encoding='utf-8') as f:
        json.dump(pendentes, f, ensure_ascii=False, indent=2)

def get_last_envio_timestamp():
    """
    Timestamp (UTC, ISO 'YYYY-MM-DDTHH:MM:SSZ') do ÚLTIMO envio registrado em
    controle/wpp_envios.json, ou None se o arquivo não existir / estiver vazio /
    não tiver nenhum registro parseável.

    O campo `date` vem em FORMATOS MISTOS:
    - ISO 8601 UTC com Z: '2026-06-22T17:53:38Z'  -> tratado como UTC direto.
    - 'YYYY-MM-DD HH:MM':  '2026-06-23 00:35'      -> tratado como America/Sao_Paulo
      (BRT) e convertido para UTC.
    Registros não parseáveis (ou sem `date`) são IGNORADOS — falha graciosa.
    """
    SP_TZ = ZoneInfo('America/Sao_Paulo')
    if not os.path.exists(WPP_ENVIOS):
        return None
    try:
        with open(WPP_ENVIOS, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        log(f'erro lendo wpp_envios.json p/ cutoff: {e}')
        return None

    if isinstance(data, dict):
        envios = data.get('envios', [])
    elif isinstance(data, list):
        envios = data
    else:
        envios = []

    best = None
    for entry in envios:
        if not isinstance(entry, dict):
            continue
        raw = entry.get('date')
        if not raw or not isinstance(raw, str):
            continue
        raw = raw.strip()
        dt = None
        try:
            # 1) ISO 8601 com Z => UTC.
            dt = datetime.strptime(raw, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                # 2) 'YYYY-MM-DD HH:MM' => America/Sao_Paulo -> UTC.
                dt = datetime.strptime(raw, '%Y-%m-%d %H:%M').replace(tzinfo=SP_TZ).astimezone(timezone.utc)
            except ValueError:
                dt = None
        if dt is None:
            continue
        if best is None or dt > best:
            best = dt

    if best is None:
        return None
    return best.strftime('%Y-%m-%dT%H:%M:%SZ')

def hubspot_search_contacts(days=1):
    """
    Busca contatos criados DEPOIS do último envio bem-sucedido.

    Cutoff = timestamp do último registro em wpp_envios.json
    (get_last_envio_timestamp), aplicado com operador GT (estritamente maior) em
    createdate — só olha pra FRENTE, nunca reprocessa o próprio último lead.
    Sem envios anteriores, faz fallback para a janela relativa de `days` dias.
    O dedup por email (processed_emails.txt) segue como segunda barreira.
    """
    last_ts = get_last_envio_timestamp()
    if last_ts:
        since_iso = last_ts
        log(f'[cutoff] último envio: {last_ts} (GT createdate)')
    else:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        since_iso = since.strftime('%Y-%m-%dT%H:%M:%SZ')
        log(f'[cutoff] sem envios anteriores, fallback janela {days}d: {since_iso}')
    data = {
        'filterGroups': [{'filters': [{'propertyName': 'createdate', 'operator': 'GT', 'value': since_iso}]}],
        'properties': [
            'firstname','lastname','email','company','phone','lifecyclestage','hs_lead_status',
            'qual_erp_utiliza_','selecione_o_sistema_de_gesto_erp',
            'qual_o_faturamento_anual_da_sua_empresa_','selecione_a_faixa_de_faturamento',
            'qual_seria_o_maior_problema','de_qual_forma_mais_vende_hoje_em_dia',
            'quantos_vendedores_internos','quantas_pessoas_atuam_na_sua_empresa',
            'vende_em_loja_virtual_','voc_acredita_que_o_seu_cliente_compraria_sozinho',
            'qual_a_rea_de_atuao_de_sua_empresa','voc_vende_para_quem'
        ],
        'limit': 50
    }
    req = urllib.request.Request(
        f'{BASE_URL}/crm/v3/objects/contacts/search',
        data=json.dumps(data).encode(),
        headers=HEADERS,
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        log(f'HUBSPOT SEARCH ERROR: {e}')
        return None

def hubspot_get_contact_by_email(email):
    data = {
        'filterGroups': [{'filters': [{'propertyName': 'email', 'operator': 'EQ', 'value': email}]}],
        'properties': ['email','phone','firstname','lastname','company','lifecyclestage'],
        'limit': 1
    }
    req = urllib.request.Request(
        f'{BASE_URL}/crm/v3/objects/contacts/search',
        data=json.dumps(data).encode(),
        headers=HEADERS,
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            results = result.get('results', [])
            return results[0] if results else None
    except Exception as e:
        log(f'HUBSPOT GET ERROR {email}: {e}')
        return None

def render_pdf(html, out):
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.set_content(html, wait_until='networkidle')
        os.makedirs(os.path.dirname(out), exist_ok=True)
        pg.pdf(path=out, width='210mm', height='297mm', print_background=True, margin={"top":"0","bottom":"0","left":"0","right":"0"})
        b.close()

def phone_to_jid(phone):
    if not phone:
        return None
    digits = re.sub(r'[^0-9]', '', phone)
    if not digits:
        return None
    if digits.startswith('55'):
        return f"{digits}@c.us"
    if len(digits) in (10,11):
        return f"55{digits}@c.us"
    return f"{digits}@c.us"

def send_text(jid, text):
    payload = {'to': jid, 'text': text}
    r = subprocess.run(['curl','-s','-X','POST',f'{BRIDGE}/send','-H','Content-Type: application/json','-d',json.dumps(payload)], capture_output=True, text=True)
    return r.stdout.strip()

def send_pdf(jid, pdf_path, file_name, thumbnail_path=None):
    payload = {'to': jid, 'filePath': pdf_path, 'fileName': file_name}
    if thumbnail_path:
        payload['thumbnailPath'] = thumbnail_path
    r = subprocess.run(['curl','-s','-X','POST',f'{BRIDGE}/send-file','-H','Content-Type: application/json','-d',json.dumps(payload)], capture_output=True, text=True)
    return r.stdout.strip()

def main():
    log('Iniciando ciclo Zydon')
    processed = load_processed()
    log(f'Emails já processados: {len(processed)}')

    search = hubspot_search_contacts(days=1)
    if not search:
        log('Nenhum lead novo no HubSpot hoje')
        return

    contacts = search.get('results', [])
    log(f'Contatos encontrados (últimas 24h): {len(contacts)}')

    new_leads = [c for c in contacts if (c.get('properties',{}).get('email') or '').lower() not in processed]
    log(f'Leads novos (não enviados): {len(new_leads)}')

    if not new_leads:
        log('Nenhum lead novo para processar')
        return

    OUT_PDF = str(BASE_DIR / 'outputs')
    THUMB = '/tmp/zydon_thumb.jpg'
    if not os.path.exists(THUMB):
        THUMB = None

    envios = load_wpp_envios()
    sent = 0
    for contact in new_leads:
        props = contact.get('properties', {})
        email = (props.get('email') or '').strip().lower()
        first = (props.get('firstname') or '').strip()
        company = (props.get('company') or '').strip()
        phone_hubspot = (props.get('phone') or '').strip()

        if not email:
            log(f'SKIP sem email: {contact.get("id")}')
            continue

        log(f'Processando: {first} / {company} / {email}')

        # Preferir telefone do HubSpot; se vazio, pular
        phone = phone_hubspot
        if not phone or '****' in phone:
            log(f'SKIP sem telefone válido no HubSpot: {email}')
            continue

        # Build lead dict from HubSpot + defaults
        contact_props = contact.get('properties', {}) if isinstance(contact, dict) else {}
        raw = {
            'name': first,
            'empresa': company,
            'erp': contact_props.get('qual_erp_utiliza_') or contact_props.get('selecione_o_sistema_de_gesto_erp') or 'Outro',
            'fantasia': company,
            'faturamento': contact_props.get('qual_o_faturamento_anual_da_sua_empresa_') or contact_props.get('selecione_a_faixa_de_faturamento') or 'A confirmar',
            'resposta': contact_props.get('de_qual_forma_mais_vende_hoje_em_dia') or 'A confirmar',
            'dor': contact_props.get('qual_seria_o_maior_problema') or '',
            'telefone': phone,
            'email': email,
            'owner_name': first or 'Contato',
            'vendedores': contact_props.get('quantos_vendedores_internos') or '1_a_10',
            'pessoas': contact_props.get('quantas_pessoas_atuam_na_sua_empresa') or '1_a_10',
            'loja': contact_props.get('vende_em_loja_virtual_') or 'nao',
            'autosservico': contact_props.get('voc_acredita_que_o_seu_cliente_compraria_sozinho') or '',
            'cargo_area': contact_props.get('qual_a_rea_de_atuao_de_sua_empresa') or '',
            'vende_para': contact_props.get('voc_vende_para_quem') or '',
        }

        try:
            lead = build_lead_dict(raw)
        except Exception as e:
            log(f'ERROR build_lead_dict {email}: {e}')
            continue

        html_path = str(BASE_DIR / 'motor' / f"{lead['slug']}.html")
        pdf_path = os.path.join(OUT_PDF, f"Potencial-Digitalizacao-{lead['slug']}.pdf")

        if not os.path.exists(html_path):
            try:
                html = gen_module.build_html(lead)
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html)
                log(f'Gerou HTML: {html_path}')
            except Exception as e:
                log(f'ERROR build_html {lead["slug"]}: {e}')
                continue

        if not os.path.exists(pdf_path):
            try:
                render_pdf(open(html_path, 'r', encoding='utf-8').read(), pdf_path)
                log(f'Gerou PDF: {pdf_path}')
            except Exception as e:
                log(f'ERROR render PDF {lead["slug"]}: {e}')
                continue

        jid = phone_to_jid(phone)
        if not jid:
            log(f'SKIP JID inválido: {phone}')
            continue

        # Texto segue EXATAMENTO o template de Mensagens_WhatsApp_junho.md
        # NUNCA adicionar go-live, ERP ou texto técnico aqui.
        dor_lower = (lead.get('dor') or '').lower()
        pushpull = (lead.get('pushpull') or '').lower()
        if 'demora' in dor_lower or 'atendimento' in dor_lower:
            insight = 'parar de perder vendas pela demora no atendimento'
        elif 'puxa' in pushpull or 'recompra' in dor_lower or 'recorrência' in dor_lower:
            insight = 'destravar a recompra dos seus clientes num canal digital próprio'
        elif 'empurra' in pushpull or 'vendedor' in dor_lower or 'visita' in dor_lower:
            insight = 'escalar as vendas sem precisar contratar mais gente'
        else:
            insight = 'organizar os pedidos que hoje chegam soltos no WhatsApp, telefone e planilha'

        msg = (
            f"Oi, {lead['contato']}, tudo bem? Aqui é a Mariana, da Zydon.\n\n"
            f"A partir do que você respondeu no nosso diagnóstico, preparei um material sobre o potencial de digitalização B2B da {lead['empresa']}. Te mando em PDF aqui.\n\n"
            f"Em resumo, dá pra {insight}. Um consultor nosso te chama na segunda-feira para fazer um diagnóstico mais completo da {lead['empresa']} e te mostrar isso na prática. Pode ser?"
        )

        # NÃO enviar nada automaticamente para o lead.
        pendentes = load_pendentes()
        pendentes.append({
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'slug': lead['slug'],
            'email': email,
            'empresa': lead['empresa'],
            'contato': lead['contato'],
            'jid': jid,
            'pdf_path': pdf_path,
            'msg_sugerida': msg,
            'status': 'pendente'
        })
        save_pendentes(pendentes)
        log(f"PENDENTE de validacao: {lead['slug']} ({email})")

        # Aviso CURTO no grupo interno (NAO envia PDF nem mensagem longa para o grupo)
        aviso = f"Novo lead p/ validar: {lead['contato']} — {lead['empresa']} ({email})"
        r_grupo = send_text(GROUP_JID, aviso)
        log(f"GRUPO {lead['slug']} -> {r_grupo}")

        # Marca como processado para nao reprocessar o mesmo lead nos proximos ciclos
        save_processed(email)
        sent += 1
        time.sleep(1)

    save_wpp_envios(envios)
    log(f'Ciclo finalizado. Enviados: {sent}/{len(new_leads)}')

if __name__ == '__main__':
    main()
