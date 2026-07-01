#!/usr/bin/env python3
"""
disparo_dinamico.py — Dispara primeiro contato via WhatsApp para leads
sem atividade, consultando o HubSpot AO VIVO a cada execução.

Pega leads NOVOS que entram durante o dia. Pula leads já enviados
(wpp_envios.json) e cria tarefa no HubSpot a cada envio (anti-loop).

Uso: python3 disparo_dinamico.py <sdr_name> [--limit N]
  sdr_name: breno | sarah | lucas
  --limit N: máximo de envios nesta execução (default: 5)

Fluxo:
  1. Consulta HubSpot: deals nas 5 primeiras etapas do pipeline (671008549)
  2. Filtra: sem telefone = skip; telefone fixo = skip; já enviado = skip
  3. Envia WhatsApp pela bridge do SDR
  4. Cria tarefa no HubSpot (associada a contato + negócio)
  5. Registra em wpp_envios.json
"""
import sys
import json
import time
import hashlib
import urllib.request
import fcntl
import atexit
import os
import re
from datetime import datetime, timezone, timedelta
from scripts.whatsapp_safe_send import safe_send_text
from scripts.whatsapp_send_orchestrator import enrich_legacy_row
from scripts.whatsapp_routing import choose_outbound_port
from scripts.zydon_operational_queues import append_wpp_envio_locked, replace_wpp_envios_locked
from scripts.whatsapp_dispatch_flow import record_dispatch_shadow_from_row, record_dispatch_worker_owned

# ─── Config ───
BRIDGES = {
    'breno': {'port': 4611, 'ports': [4611, 4605], 'owner_id': '86265630', 'owner_name': 'Breno', 'owner_uid': 'breno'},
    # Sarah 2 recém-conectada fica prioritária; 4601 continua como fallback/afinidade.
    'sarah': {'port': 4612, 'ports': [4612, 4601], 'owner_id': '88063842', 'owner_name': 'Sarah', 'owner_uid': 'sarah'},
    'lucas': {'port': 4603, 'ports': [4603], 'owner_id': '85778446', 'owner_name': 'Lucas Batista', 'owner_uid': 'lucas_batista'},
}

def _load_hubspot_token():
    token = os.environ.get('HUBSPOT_API_KEY') or os.environ.get('HUBSPOT_PRIVATE_APP_TOKEN')
    if token:
        return token.strip()
    env_path = '/root/.hermes/credentials/hubspot.env'
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('HUBSPOT_API_KEY='):
                    return line.split('=', 1)[1].strip().strip('"\'')
    except FileNotFoundError:
        pass
    raise RuntimeError('HUBSPOT_API_KEY não configurado em env ou /root/.hermes/credentials/hubspot.env')

PAT = _load_hubspot_token()
HS_HEADERS = {"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"}
PIPELINE = '671008549'
STAGE_LEAD_SEM_CONTATO = '984052829'
STAGE_PRIMEIRO_CONTATO = '1214320997'
STAGE_RETORNO_CONTATO = '998099482'
FIRST_5_STAGES = ['984052829', '1214320997', '998099482', '1151853491', '1376131958']
# Rafael 30/06: nunca regredir lead em Introdução ou etapa superior para Retorno/Primeiro.
PROTECTED_ADVANCED_STAGES = {
    '1269308723',  # Introdução
    '1269710168',  # Diagnóstico EC
    '990617426',   # Apresentação Comercial
    '1269308724',  # Apresentação Técnica
    '984052831',   # Proposta / Negociação
    '1213797817',  # Termos e condições
    '984052834',   # Fechado
    '984052835',   # Perdido
}

WPP_ENVIOS = '/root/.hermes/zydon-prospeccao/controle/wpp_envios.json'
OUTBOUND_AUDIT = '/root/.hermes/zydon-prospeccao/controle/channel_outbound_audit.jsonl'
GLOBAL_SEND_LOCK = '/tmp/zydon_external_whatsapp_send.lock'
_GLOBAL_LOCK_FH = None
DELAY_SEGUNDOS = 300  # 5min entre envios: cadência mais humana, menor risco no WhatsApp Business
# Teto global conservador por chip/porta, somando camadas externas no ledger.
# Primeiro contato ainda pode ter limite próprio menor; este teto protege o chip
# quando diagnóstico, primeiro contato e cadência coexistem no mesmo dia.
# Rafael 26/06: acelerar fila usando melhor os chips disponíveis.
# Mantém teto diário conservador, mas permite mais que 3/h em mutirões manuais/crons.
MAX_EXTERNAL_PER_PORT_HOUR = 8
MAX_EXTERNAL_PER_PORT_DAY = 30
# SDRs bloqueados temporariamente.
# 25/06: Rafael pediu remover/desconsiderar chips offline/desativados 4602/4604/4500.
SDRS_BLOQUEADOS = {}

# Propriedades do contato que queremos
CONTACT_PROPS = 'firstname,lastname,email,phone,hs_searchable_calculated_phone_number,hs_whatsapp_phone_number,createdate,recent_conversion_date,recent_conversion_event_name,qual_erp_utiliza_,selecione_o_sistema_de_gesto,selecione_o_sistema_de_gesto_erp,vende_em_loja_virtual_'


# Campos que podem conter o telefone/JID do lead nos registros (formatos
# variam entre os crons: 'to', 'jid', 'lead_jid', 'tel', 'telefone').
PHONE_FIELDS = ('to', 'jid', 'lead_jid', 'tel', 'telefone', 'phone', 'whatsapp', 'numero')
WA_DATA = '/root/.hermes/whatsapp-extra/channel_data'


def load_envios():
    """Retorna SEMPRE uma LISTA de registros de envio, lendo a fonte única
    compartilhada (controle/wpp_envios.json — mesma dos crons gate/ciclo).

    Aceita os formatos:
      - {"envios": [ ... ]}  → retorna a lista interna
      - [ ... ]              → retorna a lista direta
      - {chave: {...}, ...}  → dict de dicts (legacy) → lista de valores
      - arquivo inexistente  → []  (NUNCA dict vazio)
    """
    try:
        with open(WPP_ENVIOS, 'r') as f:
            data = json.load(f)
    except Exception:
        return []

    if isinstance(data, dict):
        if isinstance(data.get('envios'), list):
            return data['envios']
        return [v for v in data.values() if isinstance(v, dict)]
    if isinstance(data, list):
        return data
    return []


def save_envios(envios):
    """Grava a LISTA no formato real {"envios": [...]} sob lock central."""
    replace_wpp_envios_locked(envios, WPP_ENVIOS)


def _central_nature_for_registro(registro):
    msg_type = str((registro or {}).get('msg_type') or '').lower()
    status = str((registro or {}).get('status') or '').lower()
    campaign = str((registro or {}).get('campaign_id') or '').lower()
    try:
        attempt = int((registro or {}).get('attempt_number') or 0)
    except Exception:
        attempt = 0
    if 'mql_followup1' in msg_type or 'pos_diagnostico' in msg_type or 'pós-diagn' in msg_type:
        return 'followup_f1_postdiag', 'post_diagnostic'
    if 'cadencia_primeiro_contato' in campaign or 'primeiro_contato_cadencia' in msg_type:
        return f'followup_f{attempt}' if attempt in (1, 2, 3, 4) else 'followup_f1', 'cold_outreach'
    if 'primeiro_contato' in msg_type or 'primeiro_contato' in status:
        return 'first_contact', 'cold_outreach'
    if 'diagnostic' in msg_type or 'diagnostico' in msg_type or 'diagnóstico' in msg_type:
        return 'diagnostic_bundle', 'post_diagnostic'
    return 'first_contact', 'cold_outreach'


def registrar_envio(registro):
    """Append centralizado no ledger WhatsApp, preservando histórico sob flock."""
    nature, thread_state = _central_nature_for_registro(registro)
    dispatch_origin = 'followup' if str(nature).startswith('followup_') else ('diagnostico' if 'diagnostic' in nature or 'diagnostico' in nature else 'proatividade')
    registro = enrich_legacy_row(
        registro,
        nature=nature,
        origin=str((registro or {}).get('campaign_id') or (registro or {}).get('msg_type') or 'disparo_dinamico'),
        thread_state=thread_state,
        owner_uid=(registro or {}).get('owner_sdr') or (registro or {}).get('sdr') or (registro or {}).get('owner_id'),
    )
    record_dispatch_shadow_from_row(
        registro,
        origin=dispatch_origin,
        nature=nature,
        thread_state=thread_state,
        owner_uid=(registro or {}).get('owner_sdr') or (registro or {}).get('sdr') or (registro or {}).get('owner_id'),
    )
    data = append_wpp_envio_locked(registro, WPP_ENVIOS)
    return data.get('envios', []) if isinstance(data, dict) else []


def normalize_phone(value):
    """Normaliza um telefone/JID para apenas dígitos do DDD+número (sem o DDI
    55). Funciona para JID (55...@s.whatsapp.net / @c.us) e para telefones
    formatados (+55 (11) 9....). Chave estável de dedup entre os formatos."""
    if not value or not isinstance(value, str):
        return ''
    digits = ''.join(c for c in value if c.isdigit())
    if len(digits) in (12, 13) and digits.startswith('55'):
        digits = digits[2:]
    return digits


def phone_key_variants(value):
    """Equivalências BR com/sem nono dígito para dedupe real WhatsApp.

    Baileys/onWhatsApp pode canonicalizar +55 DDD 9xxxx-xxxx para +55 DDD xxxx-xxxx
    (ou o inverso). Se o ledger só comparar a chave exata, o mesmo lead aparece em
    dois chats/chips. Sempre compare interseção desse conjunto.
    """
    k = normalize_phone(value) if not isinstance(value, str) or '@' in value or not value.isdigit() else normalize_phone(value)
    vals = {k} if k else set()
    if len(k) == 11 and k[2] == '9':
        vals.add(k[:2] + k[3:])
    elif len(k) == 10 and k[2] in '6789':
        vals.add(k[:2] + '9' + k[2:])
    return {v for v in vals if v}


def same_phone_key(a, b):
    return bool(phone_key_variants(str(a or '')) & phone_key_variants(str(b or '')))


def sender_first_name(sender_name):
    name = str(sender_name or '').strip()
    return name.split()[0] if name else 'Rafael'


def presentation_line_for_sender(sender_name):
    return f"{sender_first_name(sender_name)} da Zydon aqui, plataforma de ecommerce B2B."


def add_sender_presentation(text, sender_name):
    line = presentation_line_for_sender(sender_name)
    raw = str(text or '').strip()
    if not raw or 'plataforma de ecommerce b2b' in raw.lower():
        return raw
    paras = [p.strip() for p in re.split(r'\n\s*\n+', raw) if p.strip()]
    if not paras:
        return line
    if len(paras) == 1:
        return paras[0] + '\n\n' + line
    return '\n\n'.join([paras[0], line] + paras[1:])


def history_outgoing_exists(phone_key, ports):
    """Anti-repetição extra: confere histórico real do Channel/WhatsApp.

    O ledger pode falhar/estar incompleto; se o chat já mostra uma mensagem
    nossa para o número, não mandar outro 1º contato.
    """
    if not phone_key:
        return False
    for port in sorted(set(int(p) for p in (ports or []))):
        path = f"{WA_DATA}/history_{port}.json"
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for m in data:
            if not isinstance(m, dict) or m.get('fromMe') is not True:
                continue
            vals = []
            for field in ('chat', 'sender', 'participant', 'jid', 'remoteJidAlt', 'jidAlt'):
                vals.append(m.get(field))
            raw = m.get('rawKey') or {}
            if isinstance(raw, dict):
                vals += [raw.get('remoteJid'), raw.get('remoteJidAlt'), raw.get('participant')]
            if any(same_phone_key(str(v or ''), phone_key) for v in vals):
                return True
    return False


def _history_messages_for_phone(phone_key, ports):
    rows = []
    if not phone_key:
        return rows
    for port in sorted(set(int(p) for p in (ports or []))):
        path = f"{WA_DATA}/history_{port}.json"
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for m in data:
            if not isinstance(m, dict):
                continue
            vals = []
            for field in ('chat', 'sender', 'participant', 'jid', 'remoteJidAlt', 'jidAlt'):
                vals.append(m.get(field))
            raw = m.get('rawKey') or {}
            if isinstance(raw, dict):
                vals += [raw.get('remoteJid'), raw.get('remoteJidAlt'), raw.get('participant')]
            if any(same_phone_key(str(v or ''), phone_key) for v in vals):
                mm = dict(m)
                try:
                    mm['_ts'] = float(m.get('timestamp') or 0)
                except Exception:
                    mm['_ts'] = 0
                rows.append(mm)
    rows.sort(key=lambda x: float(x.get('_ts') or 0))
    return rows


def history_incoming_after_outgoing(phone_key, ports):
    """Se o lead respondeu depois de qualquer mensagem nossa, não enviar follow.

    Rafael 26/06: se o lead respondeu antes do follow do SDR, mover direto para
    Retorno Contato; não ignorar resposta e mandar outra mensagem em cima.
    """
    rows = _history_messages_for_phone(phone_key, ports)
    last_out = 0
    incoming = []
    for m in rows:
        ts = float(m.get('_ts') or 0)
        if not ts:
            continue
        if m.get('fromMe') is True:
            last_out = max(last_out, ts)
            incoming = []
        elif last_out and ts > last_out + 30:
            incoming.append(m)
    return incoming


def envios_phone_set(envios):
    """Anti-loop do fluxo SDR de primeiro follow-up.

    Regra pós-incidente Atalaia 30/06: diagnóstico/PDF enviado por um chip também
    bloqueia novo primeiro contato por outro chip. O próximo passo precisa seguir
    pelo mesmo contexto/chip ou por fluxo de agenda/follow-up idempotente; nunca
    criar uma segunda conversa de "primeiro contato" para o mesmo telefone.
    """
    chaves = set()
    sdr_statuses = {'enviado', 'sent', 'enviado_lead', 'enviado_mql', 'mql_diagnostico_em_andamento'}
    sdr_msg_types = {'primeiro_contato', 'primeiro_contato_backlog_institucional', 'primeiro_contato_cadencia', 'mql_sdr_followup', 'diagnostico_mql', 'mql_diagnostico'}
    for r in envios:
        if not isinstance(r, dict):
            continue
        status = str(r.get('status', '')).lower()
        msg_type = str(r.get('msg_type', '')).lower()
        # Diagnóstico/MQL também bloqueiam nova abertura por outro chip para evitar duas conversas do mesmo lead.
        if msg_type not in sdr_msg_types and status not in sdr_statuses:
            continue
        for campo in PHONE_FIELDS:
            raw = str(r.get(campo, '') or '')
            if raw.endswith('@g.us'):
                continue
            p = normalize_phone(raw)
            if p:
                chaves.update(phone_key_variants(p))
    return chaves


def outbound_audit_phone_set(uid_filter=None):
    """Telefones já enviados segundo a auditoria real da bridge.

    O incidente de 30/06 mostrou que o ledger `wpp_envios.json` pode ter o número
    solicitado, enquanto a bridge canonicaliza para outro JID. Para anti-loop de
    primeiro contato, qualquer envio SDR real no audit bloqueia novo disparo para
    o telefone solicitado OU canonicalizado.
    """
    chaves = set()
    try:
        with open(OUTBOUND_AUDIT, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception:
        return chaves
    allowed_uids = set(uid_filter or ['disparo_dinamico', 'fix_partial_followup'])
    for line in lines[-10000:]:
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get('event') != 'send':
            continue
        uid = str(r.get('uid') or '')
        if uid not in allowed_uids:
            continue
        vals = [r.get('targetJid'), r.get('chatOriginal')]
        bridge = r.get('bridge') or {}
        vals += [bridge.get('to'), bridge.get('requestedTo')]
        canon = bridge.get('canonicalization') or {}
        vals += [canon.get('jid'), canon.get('requested')]
        for v in vals:
            s = str(v or '')
            if s.endswith('@g.us'):
                continue
            p = normalize_phone(s)
            if p:
                chaves.update(phone_key_variants(p))
    return chaves


def diagnostico_ports_for_phone(envios, phone_key):
    ports = set()
    if not phone_key:
        return ports
    for r in envios:
        if not isinstance(r, dict):
            continue
        status = str(r.get('status') or '').lower()
        msg_type = str(r.get('msg_type') or '').lower()
        if status not in {'enviado_lead', 'enviado_mql'} and msg_type not in {'diagnostico_mql', 'mql_diagnostico'}:
            continue
        vals = [str(r.get(c) or '') for c in PHONE_FIELDS]
        if not any(same_phone_key(v, phone_key) for v in vals):
            continue
        for field in ('bridge_port', 'port', 'sender_port'):
            try:
                if r.get(field):
                    ports.add(int(r.get(field)))
            except Exception:
                pass
    return ports


def diagnostico_context_for_phone(envios, phone_key):
    """Retorna contexto curto do diagnóstico/MQL já enviado para o telefone."""
    if not phone_key:
        return ''
    matches = []
    for r in envios:
        if not isinstance(r, dict):
            continue
        status = str(r.get('status') or '').lower()
        msg_type = str(r.get('msg_type') or '').lower()
        if status not in {'enviado_lead', 'enviado_mql'} and msg_type not in {'diagnostico_mql', 'mql_diagnostico'}:
            continue
        vals = [str(r.get(c) or '') for c in PHONE_FIELDS]
        if not any(same_phone_key(v, phone_key) for v in vals):
            continue
        text = str(r.get('text') or r.get('group_summary') or r.get('summary') or '').strip()
        if text:
            matches.append(text)
    if not matches:
        return ''
    txt = re.sub(r'\s+', ' ', matches[-1])
    # Pegar um trecho útil, sem transformar em afirmação forte.
    return txt[:360]


def intent_question_already_asked(text):
    t = re.sub(r'\s+', ' ', str(text or '').lower())
    return ('como você imagina' in t or 'como voce imagina' in t or 'por que se cadastrou' in t or 'o que te chamou atenção' in t or 'o que te chamou atencao' in t)


def parse_envio_datetime(record):
    """Lê data do ledger em formatos usados pelos crons."""
    raw = str(record.get('date_tz') or record.get('created_at') or record.get('date') or '').strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone(timedelta(hours=-3)))
    except Exception:
        pass
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone(timedelta(hours=-3)))
        except Exception:
            continue
    return None


def company_recently_touched(envios, company, current_deal_id='', max_hours=72):
    """Evita duplicar abordagem quando a mesma empresa tem outro negócio ativo.

    Caso Tuzzon 26/06: dois contatos/negócios da mesma empresa entraram pelo anúncio.
    Um já tinha diagnóstico/primeiro contato; o segundo não deve receber novo D0
    nem mover etapa só por ser outro contato da mesma empresa.
    """
    key = slugify(company or '')
    if not key:
        return None
    now = datetime.now(timezone(timedelta(hours=-3)))
    relevant_status = {'enviado_lead', 'enviado_mql'}
    relevant_msg_types = {'primeiro_contato', 'primeiro_contato_backlog_institucional', 'primeiro_contato_cadencia', 'mql_sdr_followup'}
    for r in reversed(envios):
        if not isinstance(r, dict):
            continue
        r_company = r.get('empresa') or r.get('company') or ''
        if slugify(r_company) != key:
            continue
        r_deal = str(r.get('deal_id') or '')
        if current_deal_id and r_deal and r_deal == str(current_deal_id):
            continue
        status = str(r.get('status') or '').lower()
        msg_type = str(r.get('msg_type') or '').lower()
        if status not in relevant_status and msg_type not in relevant_msg_types:
            continue
        dt = parse_envio_datetime(r)
        if dt:
            hours = (now - dt.astimezone(now.tzinfo)).total_seconds() / 3600
            if hours > max_hours:
                continue
        return r
    return None


def diagnostico_recente_hours(envios, phone_key, min_hours=20):
    """Retorna idade do diagnóstico recente apenas para contexto/log.

    Rafael 26/06: diagnóstico NÃO bloqueia follow-up/1º contato. O follow-up pode
    vir logo em seguida, principalmente pelo SDR proprietário, como continuidade
    curta e contextualizada. Nunca copiar/repetir o diagnóstico no WhatsApp.
    """
    if not phone_key:
        return None
    now = datetime.now(timezone(timedelta(hours=-3)))
    latest = None
    for r in envios:
        if not isinstance(r, dict):
            continue
        status = str(r.get('status') or '').lower()
        msg_type = str(r.get('msg_type') or '').lower()
        if status not in {'enviado_lead', 'enviado_mql'} and msg_type not in {'diagnostico_mql', 'mql_diagnostico'}:
            continue
        vals = [str(r.get(c) or '') for c in PHONE_FIELDS]
        if not any(same_phone_key(v, phone_key) for v in vals):
            continue
        dt = parse_envio_datetime(r)
        if dt and (latest is None or dt > latest):
            latest = dt
    if not latest:
        return None
    # Rafael 26/06: diagnóstico enviado no dia anterior não pode segurar o SDR
    # a manhã inteira. Bloqueia só retomada no mesmo dia do diagnóstico; no dia
    # útil seguinte o SDR deve seguir como continuidade e mover para Primeiro Contato.
    latest_brt = latest.astimezone(timezone(timedelta(hours=-3)))
    if latest_brt.date() != now.date():
        return None
    hours = (now - latest).total_seconds() / 3600
    return hours if hours < min_hours else None


def slugify(texto):
    """Gera um slug simples (a partir do nome da empresa) para registrar junto
    do envio, compatível com o campo 'slug' usado pelos outros crons."""
    t = (texto or '').strip().lower()
    out = ''.join(c if c.isalnum() else '-' for c in t)
    while '--' in out:
        out = out.replace('--', '-')
    return out.strip('-')


def hs_request(url, method='GET', body=None):
    """Faz request ao HubSpot API. Retorna JSON ou None."""
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=HS_HEADERS, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  ⚠️  Erro API: {e}")
        return None


DIAGNOSTICO_TASK_MARKERS = (
    'diagnóstico',
    'diagnostico',
    'potencial de digitalização',
    'potencial de digitalizacao',
    'diagnóstico "potencial de digitalização b2b" enviado ao lead',
    "diagnóstico 'potencial de digitalização b2b' enviado ao lead",
    'diagnostico potencial de digitalizacao b2b enviado ao lead',
)


def is_tarefa_diagnostico(props):
    """Tarefa criada pelo cron 24/7 de diagnóstico NÃO conta como atividade
    humana/comercial para bloquear o follow-up SDR."""
    texto = ' '.join([
        str(props.get('hs_task_subject') or ''),
        str(props.get('hs_task_body') or ''),
    ]).strip().lower()
    if not texto:
        return False
    return any(marker in texto for marker in DIAGNOSTICO_TASK_MARKERS)


def buscar_tasks_props(task_ids):
    """Lê subject/body das tasks em batch. Se falhar, retorna None para o
    chamador aplicar fail-safe e não abordar lead com atividade desconhecida."""
    if not task_ids:
        return {}

    out = {}
    batch_size = 100
    for i in range(0, len(task_ids), batch_size):
        batch = task_ids[i:i+batch_size]
        url = "https://api.hubapi.com/crm/v3/objects/tasks/batch/read"
        body = {
            "properties": ["hs_task_subject", "hs_task_body"],
            "inputs": [{"id": str(tid)} for tid in batch],
        }
        result = hs_request(url, 'POST', body)
        if not result:
            return None
        for item in result.get('results', []):
            out[str(item.get('id'))] = item.get('properties', {}) or {}
    return out


def extrair_task_ids_assoc(r):
    """HubSpot pode retornar `to` como dict ou lista dependendo da API/versão."""
    to_obj = r.get('to')
    if isinstance(to_obj, dict):
        tid = to_obj.get('id')
        return [str(tid)] if tid else []
    if isinstance(to_obj, list):
        ids = []
        for item in to_obj:
            if isinstance(item, dict) and item.get('id'):
                ids.append(str(item['id']))
        return ids
    return []


def ler_assoc_deals_objetos(deal_ids, object_type):
    """Lê associações deal -> activity/object em batch.

    Fail-safe: retorna None em erro para o chamador bloquear o lote, porque
    backlog/primeiro contato só pode abordar negócio que realmente nunca teve
    contato comercial relevante. `object_type` exemplos: tasks, calls, meetings.
    """
    url = f"https://api.hubapi.com/crm/v3/associations/deals/{object_type}/batch/read"
    body = {"inputs": [{"id": str(did)} for did in deal_ids]}
    result = hs_request(url, 'POST', body)
    if not result:
        return None
    out = {str(did): [] for did in deal_ids}
    for r in result.get('results', []):
        from_obj = r.get('from', {})
        from_id = from_obj.get('id') if isinstance(from_obj, dict) else from_obj
        if not from_id:
            continue
        out.setdefault(str(from_id), []).extend(extrair_task_ids_assoc(r))
    # Objetos sem associação costumam aparecer em errors/context; já estão como [].
    for e in result.get('errors', []):
        ctx = e.get('context', {}).get('fromObjectId', [])
        for did in ctx:
            out.setdefault(str(did), [])
    return out


def buscar_objetos_props(object_type, object_ids, properties):
    """Lê propriedades de calls/meetings em batch; None = falha fail-closed."""
    if not object_ids:
        return {}
    out = {}
    batch_size = 100
    for i in range(0, len(object_ids), batch_size):
        batch = object_ids[i:i+batch_size]
        url = f"https://api.hubapi.com/crm/v3/objects/{object_type}/batch/read"
        body = {"properties": properties, "inputs": [{"id": str(oid)} for oid in batch]}
        result = hs_request(url, 'POST', body)
        if not result:
            return None
        for item in result.get('results', []):
            out[str(item.get('id'))] = item.get('properties', {}) or {}
    return out


def call_efetuada(props):
    """Só ligação atendida/com conversa bloqueia.

    Rafael 24/06: ligação por si só não bloqueia WhatsApp. Bloqueia apenas
    quando foi concluída/atendida e teve alguma conversa. No HubSpot usamos
    status COMPLETED + duração mínima para separar de tentativa curta/caixa postal.
    """
    status = str(props.get('hs_call_status') or '').upper()
    body = str(props.get('hs_call_body') or '').lower()
    title = str(props.get('hs_call_title') or '').lower()
    try:
        duration_ms = int(float(props.get('hs_call_duration') or 0))
    except Exception:
        duration_ms = 0
    if status != 'COMPLETED':
        return False
    if any(x in body for x in ('caixa postal', 'não atendeu', 'nao atendeu', 'sem atendimento')):
        return False
    # Conversa real: nota manual no corpo OU duração razoável (>=15s).
    return bool(body.strip()) or duration_ms >= 15000 or 'atendida' in title or 'conversa' in title


def meeting_efetuada(props):
    """Só reunião efetuada/completada bloqueia; reunião futura/agendada não bloqueia."""
    txt = ' '.join(str(props.get(k) or '') for k in ('hs_meeting_outcome', 'hs_meeting_title', 'hs_meeting_body')).lower()
    return 'completed' in txt or 'efetuad' in txt or 'realizad' in txt


def filtrar_deals_sem_atividade_valida(deals):
    """
    Retorna deals que NÃO têm atividade comercial/humana válida.

    Regra dura para primeiro contato/backlog: se o negócio já teve ligação,
    reunião ou e-mail associado, NÃO abordar. Tarefa de diagnóstico/PDF do cron
    24/7 é a única task que não bloqueia; qualquer outra task bloqueia.
    Fail-safe: erro ao ler associações bloqueia o batch.
    """
    elegiveis = set()
    batch_size = 50  # conservador para não estourar rate limit

    for i in range(0, len(deals), batch_size):
        batch = deals[i:i+batch_size]
        deal_ids = [str(d['id']) for d in batch]

        deal_to_tasks = ler_assoc_deals_objetos(deal_ids, 'tasks')
        deal_to_calls = ler_assoc_deals_objetos(deal_ids, 'calls')
        deal_to_meetings = ler_assoc_deals_objetos(deal_ids, 'meetings')
        # E-mail NÃO bloqueia primeiro contato/backlog (Rafael 24/06):
        # só ligação/reunião/task comercial contam como atividade relevante.
        if any(x is None for x in (deal_to_tasks, deal_to_calls, deal_to_meetings)):
            print(f"    Batch {i//batch_size + 1}: erro ao ler atividades; bloqueado por segurança")
            continue

        all_task_ids = sorted({tid for tids in deal_to_tasks.values() for tid in tids})
        all_call_ids = sorted({cid for cids in deal_to_calls.values() for cid in cids})
        all_meeting_ids = sorted({mid for mids in deal_to_meetings.values() for mid in mids})
        task_props = buscar_tasks_props(all_task_ids)
        call_props = buscar_objetos_props('calls', all_call_ids, ['hs_call_status', 'hs_call_disposition', 'hs_call_title', 'hs_call_body'])
        meeting_props = buscar_objetos_props('meetings', all_meeting_ids, ['hs_meeting_outcome', 'hs_meeting_title', 'hs_meeting_body'])
        if task_props is None or call_props is None or meeting_props is None:
            print(f"    Batch {i//batch_size + 1}: erro ao ler detalhes das atividades; bloqueado por segurança")
            continue

        sem_contato = 0
        so_diagnostico = 0
        bloqueio_task = 0
        bloqueio_call = 0
        bloqueio_meeting = 0
        for did in deal_ids:
            if any(call_efetuada(call_props.get(str(cid), {})) for cid in deal_to_calls.get(did, [])):
                bloqueio_call += 1
                continue
            if any(meeting_efetuada(meeting_props.get(str(mid), {})) for mid in deal_to_meetings.get(did, [])):
                bloqueio_meeting += 1
                continue

            tids = deal_to_tasks.get(did, [])
            if not tids:
                elegiveis.add(did)
                sem_contato += 1
                continue

            # Se alguma task não for diagnóstico, existe atividade válida.
            if all(is_tarefa_diagnostico(task_props.get(str(tid), {})) for tid in tids):
                elegiveis.add(did)
                so_diagnostico += 1
            else:
                bloqueio_task += 1

        print(
            f"    Batch {i//batch_size + 1}: {sem_contato} sem contato, "
            f"{so_diagnostico} só diagnóstico (entra), "
            f"bloqueios task/call/meeting="
            f"{bloqueio_task}/{bloqueio_call}/{bloqueio_meeting}"
        )

    return elegiveis


def buscar_deals_sem_tarefa(owner_id, stages=None):
    """
    Busca deals pertencentes ao owner nas etapas informadas.
    Padrão histórico: 5 primeiras etapas. Para primeiro contato automático,
    Rafael definiu escopo estrito: somente Lead Sem Contato.
    Retorna lista de {deal_id, dealname, dealstage, createdate}.
    Prioridade do Rafael: lead novo/quente primeiro — quem acabou de entrar
    deve ser chamado antes do backlog antigo.
    """
    stages = list(stages or FIRST_5_STAGES)
    url = "https://api.hubapi.com/crm/v3/objects/deals/search"
    body = {
        "filterGroups": [{
            "filters": [
                {"propertyName": "pipeline", "operator": "EQ", "value": PIPELINE},
                {"propertyName": "dealstage", "operator": "IN", "values": stages},
                {"propertyName": "hubspot_owner_id", "operator": "EQ", "value": owner_id},
            ]
        }],
        "properties": ["dealname", "dealstage", "hubspot_owner_id", "createdate"],
        "limit": 100,
        "sorts": [{"propertyName": "createdate", "direction": "DESCENDING"}],
    }

    all_deals = []
    after = None
    while True:
        if after:
            body['after'] = after
        result = hs_request(url, 'POST', body)
        if not result:
            break
        deals = result.get('results', [])
        all_deals.extend(deals)
        paging = result.get('paging', {})
        after = paging.get('next', {}).get('after')
        if not after:
            break

    return all_deals


def parse_hubspot_datetime(raw):
    """Converte timestamps ISO do HubSpot para datetime UTC aware."""
    if not raw:
        return None
    txt = str(raw).strip()
    try:
        if txt.endswith('Z'):
            txt = txt[:-1] + '+00:00'
        dt = datetime.fromisoformat(txt)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def filtrar_deals_por_idade(deals, min_age_hours=None, max_age_hours=None):
    """Filtra deals por idade desde createdate.

    Uso operacional:
      - max_age_hours=48: cron rápido de leads novos/quentes.
      - min_age_hours=48: backlog antigo em cadência calma.
    Fail-safe: se não houver createdate parseável, o deal não entra no filtro
    temporal para evitar abordagem fora da faixa pretendida.
    """
    if min_age_hours is None and max_age_hours is None:
        return deals
    now_utc = datetime.now(timezone.utc)
    out = []
    sem_data = 0
    for deal in deals:
        created = parse_hubspot_datetime((deal.get('properties') or {}).get('createdate'))
        if not created:
            sem_data += 1
            continue
        age_hours = (now_utc - created).total_seconds() / 3600
        if min_age_hours is not None and age_hours < min_age_hours:
            continue
        if max_age_hours is not None and age_hours > max_age_hours:
            continue
        out.append(deal)
    label = []
    if min_age_hours is not None:
        label.append(f">={min_age_hours:g}h")
    if max_age_hours is not None:
        label.append(f"<={max_age_hours:g}h")
    extra = f"; {sem_data} sem createdate" if sem_data else ""
    print(f"   Filtro idade ({' e '.join(label)}): {len(out)}/{len(deals)} deals mantidos{extra}")
    return out


def get_contact_for_deal(deal_id):
    """Busca o contato correto associado ao deal.

    Regra Rafael (25/06): se o negócio tem mais de 1 contato associado,
    escolher o contato MAIS NOVO — primeiro por último preenchimento de formulário
    (recent_conversion_date), depois por createdate. Normalmente é quem acabou de
    preencher o formulário/reentrar agora. Isso evita mandar follow-up para um
    contato antigo de meses atrás quando outra pessoa gerou o deal/reentrada.
    """
    # 1. Buscar IDs dos contatos associados
    url = f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}/associations/contacts"
    result = hs_request(url)
    if not result or not result.get('results'):
        return None

    contact_ids = [str(r.get('id')) for r in result.get('results', []) if r.get('id')]
    if not contact_ids:
        return None

    props = CONTACT_PROPS + ',createdate'

    # 2. Se houver só um contato, caminho simples.
    if len(contact_ids) == 1:
        contact_id = contact_ids[0]
        url2 = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}?properties={props}"
        contact = hs_request(url2)
        if not contact:
            return None
        return contact_id, contact.get('properties', {})

    # 3. Vários contatos: ler todos e escolher o mais novo por último preenchimento/formulário.
    url2 = "https://api.hubapi.com/crm/v3/objects/contacts/batch/read"
    body = {
        "properties": props.split(','),
        "inputs": [{"id": cid} for cid in contact_ids],
    }
    batch = hs_request(url2, 'POST', body)
    if not batch or not batch.get('results'):
        return None

    def contact_recency_ts(item):
        p = item.get('properties', {}) or {}
        dt = parse_hubspot_datetime(p.get('recent_conversion_date') or p.get('createdate'))
        return dt.timestamp() if dt else 0

    escolhido = max(batch.get('results', []), key=contact_recency_ts)
    contact_id = str(escolhido.get('id'))
    contact_props = escolhido.get('properties', {}) or {}
    recency = contact_props.get('recent_conversion_date') or contact_props.get('createdate')
    print(f"  ↳ Deal {deal_id}: {len(contact_ids)} contatos associados; usando contato mais recente {contact_id} ({recency})")
    return contact_id, contact_props


def extrair_telefone(props):
    """Extrai telefone celular válido.

    Regra Rafael/Zydon: antes de considerar inválido, tentar variações,
    especialmente inserir 9 após o DDD. Ex.: 55 62 8219-5606 vira
    55 62 98219-5606. Retorna (tel_raw, jid, tel_fmt) ou None.
    """
    values = [
        props.get('hs_searchable_calculated_phone_number', ''),
        props.get('hs_whatsapp_phone_number', ''),
        props.get('mobilephone', ''),
        props.get('phone', ''),
    ]
    candidates = []
    seen = set()
    for tel in values:
        if not tel:
            continue
        digits = ''.join(c for c in str(tel) if c.isdigit())
        if not digits:
            continue
        if len(digits) in (12, 13) and digits.startswith('55'):
            digits = digits[2:]
        variants = [digits]
        # Principal fallback: DDD + número de 8 dígitos recebe 9 após DDD.
        if len(digits) == 10:
            variants.append(digits[:2] + '9' + digits[2:])
        # Se veio DDI 55 + DDD + 8 dígitos em algum formato estranho.
        if len(digits) == 12 and digits.startswith('55'):
            stripped = digits[2:]
            if len(stripped) == 10:
                variants.append(stripped[:2] + '9' + stripped[2:])
        for v in variants:
            if v not in seen:
                seen.add(v)
                candidates.append(v)
    for digits in candidates:
        if len(digits) == 11 and digits[2] == '9':
            jid = f"55{digits}@s.whatsapp.net"
            fmt = f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
            return digits, jid, fmt
    return None


def extrair_erp(props):
    """Extrai ERP do formulário."""
    erp = props.get('qual_erp_utiliza_', '') or props.get('selecione_o_sistema_de_gesto_erp', '') or props.get('selecione_o_sistema_de_gesto', '') or ''
    if erp and erp.lower() not in ('outro', ''):
        return erp.strip()
    return ''


def primeiro_nome_valido(nome):
    nome = (nome or '').strip()
    if not nome or nome.lower() in ('tudo bem', 'lead', 'cliente'):
        return ''
    return nome


def empresa_parece_endereco(empresa):
    """Evita usar endereço digitado no campo empresa como se fosse nome comercial.

    Exemplo real: lead preencheu `Rua Pedro Gusso, 1540, Cidade Industrial...`
    e a mensagem saiu `cadastro da Rua...`. Quando o campo parece endereço,
    ele deve ser tratado como desconhecido; é melhor dizer apenas "seu cadastro"
    do que personalizar errado.
    """
    text = re.sub(r'\s+', ' ', str(empresa or '')).strip()
    if not text:
        return False
    low = text.lower()
    address_prefixes = (
        'rua ', 'r. ', 'avenida ', 'av ', 'av. ', 'rodovia ', 'estrada ', 'travessa ',
        'alameda ', 'praça ', 'praca ', 'largo ', 'quadra ', 'qd ', 'qd. ',
        'lote ', 'lt ', 'lt. ', 'bairro ', 'cep ',
    )
    if low.startswith(address_prefixes):
        return True
    address_words = (
        ' cidade industrial', ' distrito industrial', ' jardim ', ' bairro ',
        ' cep', ' cep:', ' lote ', ' quadra ', ' km ', ' nº', ' n°', ' numero ', ' número ',
    )
    if any(w in low for w in address_words) and re.search(r'\d{2,}', low):
        return True
    # Padrão típico: logradouro + número + cidade/UF/CEP. Evita pegar nomes
    # comerciais comuns que tenham um único número pequeno.
    if ',' in text and re.search(r'\b\d{3,}\b', text) and re.search(r'\b[A-Z]{2}\b|\b\d{5}-?\d{3}\b', text, re.I):
        return True
    return False


def empresa_valida(empresa):
    empresa = (empresa or '').strip()
    # HubSpot usa sufixos internos como "- Nova oportunidade" no nome do negócio.
    # Isso é etiqueta operacional e nunca deve aparecer na mensagem para o lead.
    empresa = re.sub(r'\s*[-–—]\s*nova\s+oportunidade\s*$', '', empresa, flags=re.I).strip()
    empresa = re.sub(r'\s+', ' ', empresa).strip()
    if not empresa or empresa.lower() in ('sem nome', 'sem empresa', 'nova oportunidade'):
        return ''
    if empresa_parece_endereco(empresa):
        return ''
    return empresa


def escolher_variacao(sdr, nome, empresa, erp, total):
    """Escolha determinística por lead: varia sem parecer aleatório/robótico e
    mantém a mesma mensagem se o script for reexecutado antes do envio."""
    base = f"{sdr}|{nome}|{empresa}|{erp}"
    h = hashlib.sha256(base.encode('utf-8')).hexdigest()
    return int(h[:8], 16) % total


def saudacao_por_variacao(nome_ok, idx, casual='Oi'):
    """Varia a abertura para reduzir impressão de blast sem perder naturalidade."""
    if nome_ok:
        opts = [
            f"{casual}, {nome_ok}.",
            f"{nome_ok}, tudo bem?",
            f"Olá, {nome_ok}.",
            f"Bom dia, {nome_ok}.",
            f"Oi {nome_ok}, tudo certo?",
        ]
    else:
        opts = [f"{casual}, tudo bem?", "Olá, tudo bem?", "Bom dia, tudo bem?", "Oi, tudo certo?"]
    return opts[idx % len(opts)]


FIRST_SDR_QUESTION = 'Como você imagina que a Zydon poderia te apoiar?'
FIRST_SDR_QUESTION_ALT = 'Como você imagina que a Zydon poderia te apoiar?'
SECOND_INTENT_QUESTION = 'Para eu não repetir a mesma pergunta: hoje você está buscando um portal B2B próprio, reduzir pedido manual ou entender se a Zydon é diferente de marketplace/site comum?'
MIN_HOURS_AFTER_DIAG_FOR_SDR_FOLLOW = 3.0


def first_sdr_question_for_key(key):
    try:
        import hashlib
        h = int(hashlib.sha256(str(key or '').encode()).hexdigest()[:8], 16)
        return FIRST_SDR_QUESTION_ALT if h % 2 else FIRST_SDR_QUESTION
    except Exception:
        return FIRST_SDR_QUESTION


def diagnostico_intro(empresa=''):
    # Régua Rafael 27/06: primeiro contato precisa explicar rapidamente a Zydon
    # antes de perguntar. Evita mensagem abstrata de "diagnóstico" sem o lead
    # entender o produto.
    if empresa:
        return f"Vi seu cadastro da {empresa} e queria te contextualizar rápido."
    return "Vi seu cadastro e queria te contextualizar rápido."


def zydon_explicacao_curta():
    return (
        "O cliente entra com login, vê catálogo, tabela comercial e formas de pagamento dele, "
        "e faz o pedido direto."
    )


FALLBACK_PORTAL_EXAMPLES = [
    'https://voolt3datacado.com.br/',
    'https://stoky.com.br/',
    'https://portal.ceasamais.com.br/',
]


def portal_real_para_lead(empresa='', nome='', erp=''):
    key = f"{empresa}|{nome}|{erp}"
    idx = int(hashlib.sha256(key.encode('utf-8')).hexdigest()[:8], 16) % len(FALLBACK_PORTAL_EXAMPLES)
    return FALLBACK_PORTAL_EXAMPLES[idx]


def bloco_portal_real(empresa='', nome='', erp=''):
    return f"Separei um portal real para visualizar a experiência:\n\n{portal_real_para_lead(empresa, nome, erp)}"


def contextualizacao_obrigatoria(text='', empresa=''):
    """Contextualiza sem repetir diagnóstico nem fazer questionário abstrato."""
    return "Isso conversa com o que vocês estão buscando?"


SDR_PORTS = {4601, 4603, 4605}
CALL_CTA = 'Você tem um tempo agora? Posso te ligar rapidinho?'


def is_business_hours_brt(dt=None):
    dt = dt or datetime.now(timezone(timedelta(hours=-3)))
    return dt.weekday() < 5 and 8 <= dt.hour < 18


def can_offer_call(port=None, is_sdr_sender=True, dt=None):
    try:
        port_ok = int(port) in SDR_PORTS
    except Exception:
        port_ok = False
    return bool(is_sdr_sender and port_ok and is_business_hours_brt(dt))


def apply_contact_cta(text, port=None, is_sdr_sender=True, dt=None):
    # Rafael: só falar de ligação se sair do WhatsApp do SDR e em horário comercial.
    # Se não couber ligação, não adicionar CTA genérico do tipo "responde por aqui".
    for phrase in (CALL_CTA, 'Prefere que eu te chame por aqui ou uma ligação rápida?',
                   'Pode me responder por aqui mesmo.', 'Pode me responder por aqui?', 'Pode ser por aqui?'):
        text = text.replace('\n\n' + phrase, '').replace(phrase, '').strip()
    if can_offer_call(port, is_sdr_sender=is_sdr_sender, dt=dt) and CALL_CTA not in text:
        text = text.rstrip() + '\n\n' + CALL_CTA
    return text


def montar_msg_breno(nome, empresa, erp):
    nome_ok = primeiro_nome_valido(nome)
    empresa_ok = empresa_valida(empresa)
    var_idx = escolher_variacao('breno', nome, empresa, erp, 3)
    saudacao = saudacao_por_variacao(nome_ok, var_idx, 'Oi')
    empresa_txt = f" da {empresa_ok}" if empresa_ok else ""
    erp_txt = f" Vi aqui também que vocês usam {erp}." if erp else ""
    contexto = contextualizacao_obrigatoria(empresa=empresa_ok or empresa)
    portal = bloco_portal_real(empresa_ok or empresa, nome, erp)
    explicacao = zydon_explicacao_curta()
    variacoes = [
        f"{saudacao} Breno aqui da Zydon. Vi seu cadastro{empresa_txt}.{erp_txt}\n\n{portal}\n\n{explicacao}\n\n{contexto}",
        f"{saudacao} Aqui é o Breno, da Zydon. Recebi seu interesse{empresa_txt}.{erp_txt}\n\n{portal}\n\n{explicacao}\n\n{contexto}",
        f"{saudacao} Breno da Zydon por aqui. Estou com seu cadastro{empresa_txt} aqui.{erp_txt}\n\n{portal}\n\n{explicacao}\n\n{contexto}",
    ]
    return variacoes[var_idx % len(variacoes)]


def montar_msg_sarah(nome, empresa, erp):
    nome_ok = primeiro_nome_valido(nome)
    empresa_ok = empresa_valida(empresa)
    var_idx = escolher_variacao('sarah', nome, empresa, erp, 3)
    saudacao = saudacao_por_variacao(nome_ok, var_idx, 'Oie')
    empresa_txt = f" da {empresa_ok}" if empresa_ok else ""
    erp_txt = f" Vi aqui que vocês usam {erp}." if erp else ""
    contexto = contextualizacao_obrigatoria(empresa=empresa_ok or empresa)
    portal = bloco_portal_real(empresa_ok or empresa, nome, erp)
    explicacao = zydon_explicacao_curta()
    variacoes = [
        f"{saudacao} Sarah aqui, da Zydon. Recebi seu cadastro{empresa_txt}.{erp_txt}\n\n{portal}\n\n{explicacao}\n\n{contexto}",
        f"{saudacao} Aqui é a Sarah, da Zydon. Vi o interesse{empresa_txt}.{erp_txt}\n\n{portal}\n\n{explicacao}\n\n{contexto}",
        f"{saudacao} Sarah da Zydon por aqui. Chegou para mim o cadastro{empresa_txt}.{erp_txt}\n\n{portal}\n\n{explicacao}\n\n{contexto}",
    ]
    return variacoes[var_idx % len(variacoes)]


def montar_msg_lucas(nome, empresa, erp):
    nome_ok = primeiro_nome_valido(nome) or 'tudo bem'
    empresa_ok = empresa_valida(empresa)
    empresa_txt = f" da {empresa_ok}" if empresa_ok else ""
    erp_txt = f" Vi também que vocês usam {erp}." if erp else ""
    contexto = contextualizacao_obrigatoria(empresa=empresa_ok or empresa)
    portal = bloco_portal_real(empresa_ok or empresa, nome, erp)
    explicacao = zydon_explicacao_curta()
    var_idx = escolher_variacao('lucas_batista', nome, empresa, erp, 3)
    variacoes = [
        f"Olá {nome_ok}! Tudo bem?\nLucas Batista aqui da Zydon. Recebi seu cadastro{empresa_txt}.{erp_txt}\n\n{portal}\n\n{explicacao}\n\n{contexto}",
        f"Oi, {nome_ok}. Lucas Batista, da Zydon. Estou com seu interesse{empresa_txt} aqui.{erp_txt}\n\n{portal}\n\n{explicacao}\n\n{contexto}",
        f"{nome_ok}, tudo bem? Lucas Batista aqui. Vi seu cadastro{empresa_txt}.{erp_txt}\n\n{portal}\n\n{explicacao}\n\n{contexto}",
    ]
    return variacoes[var_idx % len(variacoes)]


MSG_BUILDERS = {
    'breno': montar_msg_breno,
    'sarah': montar_msg_sarah,
    'lucas': montar_msg_lucas,
}


def send_whatsapp(port, jid, text):
    return safe_send_text(port, jid, text, uid='disparo_dinamico', timeout=30)


def greeting_period_brt(dt=None):
    dt = dt or datetime.now(timezone(timedelta(hours=-3)))
    if dt.hour < 12:
        return 'Bom dia'
    if dt.hour < 18:
        return 'Boa tarde'
    return 'Boa noite'


def first_para_is_greeting_or_intro(first_para):
    """Detecta se o primeiro parágrafo é abertura pessoal, não conteúdo operacional."""
    text = str(first_para or '').strip()
    if re.match(r'^(Bom dia|Boa tarde|Boa noite),\s*([^.!?\n,]{2,40})\.\s*Tudo bem\??$', text, re.I):
        return True
    if re.match(r'^(?:fala\s+|oi\s+|olá\s+)?([^,!.?\n]{2,40})[,!.?]\s*(?:aqui|tudo bem|bom dia|boa tarde|boa noite|oi|olá|fala)\b', text, re.I):
        return True
    if re.match(r'^(?:oi|olá|ola|fala)\s+[^\n]{2,40}(?:,|!|\.)', text, re.I):
        return True
    return False


def greeting_from_intro(first_para):
    """Transforma a abertura em cumprimento curto: 'Bom dia, Nome. Tudo bem?'"""
    text = str(first_para or '').strip()
    # Se já vier no formato aprovado (Bom dia/Boa tarde/Boa noite, Nome. Tudo bem?), preserva.
    m0 = re.match(r'^(Bom dia|Boa tarde|Boa noite),\s*([^.!?\n,]{2,40})\.\s*Tudo bem\??$', text, re.I)
    if m0:
        # Rafael: o template é fixo, mas o cumprimento é variável operacional.
        # Ao dividir em bolhas, ajustar Bom dia/Boa tarde/Boa noite conforme horário BRT.
        name0 = m0.group(2).strip()
        return f"{greeting_period_brt()}, {name0}. Tudo bem?"
    # Pega o nome antes da primeira vírgula em aberturas tipo
    # 'Andre, aqui é Rafael...' ou 'Fala Andre!'.
    name = ''
    m = re.match(r'^(?:fala\s+|oi\s+|olá\s+)?([^,!.?\n]{2,40})[,!.?]', text, re.I)
    if m:
        name = m.group(1).strip()
    if not name or name.lower() in {'tudo bem', 'tudo certo', 'cliente', 'lead'}:
        return f"{greeting_period_brt()}, tudo bem?"
    return f"{greeting_period_brt()}, {name}. Tudo bem?"


def split_whatsapp_text(text, max_parts=3):
    """Divide abordagem em mensagens menores sem esconder link.

    Rafael 29/06: primeira mensagem é só saudação por horário + pergunta se
    está bem; depois de 1 minuto vem a parte operacional. Sempre que possível,
    a pergunta final fica em uma mensagem separada. Mantém URL limpa em linha
    própria para preview do WhatsApp.
    """
    raw = str(text or '').strip()
    if not raw:
        return []
    paras = [p.strip() for p in re.split(r'\n\s*\n+', raw) if p.strip()]
    if not paras:
        return []

    if first_para_is_greeting_or_intro(paras[0]):
        greeting = greeting_from_intro(paras[0])
        # A primeira bolha é sempre só a saudação; o conteúdo operacional começa na segunda.
        body_paras = paras[1:]
    else:
        # Se o texto já começa com conteúdo operacional (ex.: "Separei um portal..."),
        # NÃO descartar esse parágrafo. Gera uma saudação curta e preserva o conteúdo.
        greeting = f"{greeting_period_brt()}, tudo bem?"
        body_paras = paras[:]

    # Remove CTAs antigos que o Rafael pediu para não usar.
    banned = {'pode me responder por aqui mesmo.', 'pode me responder por aqui?', 'pode ser por aqui?'}
    body_paras = [p for p in body_paras if p.strip().lower() not in banned]

    # Se a última pergunta está dentro de um bloco com explicação, separa para
    # virar a última bolha própria.
    question = ''
    if body_paras:
        last = body_paras[-1]
        matches = list(re.finditer(r'([^?\n][^?]*\?)\s*$', last, re.S))
        if matches:
            q = matches[-1].group(1).strip()
            before_q = last[:matches[-1].start(1)].strip()
            if before_q:
                # Se o último parágrafo já é um CTA composto por duas perguntas
                # curtas (ex.: "Faz sentido...? Podemos...?"), manter tudo junto
                # na última bolha em vez de jogar a primeira pergunta no corpo.
                if '?' in before_q:
                    question = last
                    body_paras = body_paras[:-1]
                else:
                    body_paras[-1] = before_q
                    question = q
            else:
                question = q
                body_paras = body_paras[:-1]

    url_idx = next((i for i, p in enumerate(body_paras) if re.search(r'https?://', p, re.I)), None)
    parts = [greeting]
    if url_idx is not None:
        before = body_paras[:url_idx]
        url_para = body_paras[url_idx]
        after = body_paras[url_idx + 1:]
        second_chunks = []
        if before:
            second_chunks.extend(before)
        second_chunks.append(url_para)
        parts.append('\n\n'.join(second_chunks))
        if after:
            parts.append('\n\n'.join(after))
    else:
        if len(body_paras) <= 1:
            if body_paras:
                parts.append(body_paras[0])
        else:
            mid = max(1, (len(body_paras) + 1) // 2)
            parts.extend(['\n\n'.join(body_paras[:mid]), '\n\n'.join(body_paras[mid:])])

    if question:
        parts.append(question)

    # Se passar de max_parts, compacte corpo, mas preserve saudação e pergunta separadas.
    while len(parts) > max_parts:
        if question and len(parts) > 3:
            parts[1] = parts[1].rstrip() + '\n\n' + parts.pop(2)
        else:
            parts[-2] = parts[-2].rstrip() + '\n\n' + parts.pop(-1)
    return [p for p in parts if p.strip()]


def delay_before_next_part(idx, total_parts, pause_seconds=12.0, final_pause_seconds=60.0):
    """Intervalo entre bolhas do follow-up.

    Rafael 29/06: entre saudação e mensagem de contexto pode ser curto (~12s),
    mas antes da pergunta final deve parecer mais natural: ~1 minuto.
    """
    if idx < total_parts and idx == total_parts - 1:
        return final_pause_seconds
    return pause_seconds


def send_whatsapp_sequence(port, jid, text, pause_seconds=12.0, final_pause_seconds=60.0, max_parts=3, delay_schedule=None):
    parts = split_whatsapp_text(text, max_parts=max_parts)
    if not parts:
        return False, {"error": "empty text"}
    responses = []
    for idx, part in enumerate(parts, 1):
        ok, resp = send_whatsapp(port, jid, part)
        responses.append({'part': idx, 'text': part, 'ok': ok, 'response': resp})
        if not ok:
            return False, {'error': 'partial_sequence_failed', 'failed_part': idx, 'responses': responses}
        if idx < len(parts):
            if delay_schedule and idx <= len(delay_schedule):
                wait = float(delay_schedule[idx - 1])
            else:
                wait = delay_before_next_part(idx, len(parts), pause_seconds=pause_seconds, final_pause_seconds=final_pause_seconds)
            time.sleep(wait)
    message_ids = [(r.get('response') or {}).get('messageId') for r in responses]
    return True, {
        'success': True,
        'messageId': next((m for m in reversed(message_ids) if m), None),
        'messageIds': [m for m in message_ids if m],
        'parts': len(parts),
        'responses': responses,
    }


def enqueue_worker_owned_first_contact(lead, port, msg, *, owner_id, owner_name, sender_label='', sender_phone=''):
    parts = split_whatsapp_text(msg, max_parts=3)
    delay_schedule = [delay_before_next_part(i, len(parts), pause_seconds=12.0, final_pause_seconds=60.0) for i in range(1, len(parts))]
    res = record_dispatch_worker_owned(
        origin='proatividade',
        nature='first_contact',
        thread_state='cold_outreach',
        to=lead['jid'],
        text=msg,
        owner_uid=lead.get('owner_uid') or owner_name,
        lead_key=lead.get('deal_id') or lead.get('contact_id') or lead['jid'],
        port=port,
        sender_role=sender_label or owner_name,
        completion_type='first_contact',
        parts=parts,
        delay_schedule=delay_schedule,
        deal_id=lead.get('deal_id'),
        contact_id=lead.get('contact_id'),
        owner_id=owner_id,
        owner_name=owner_name,
        lead_name=lead.get('nome'),
        tel_fmt=lead.get('tel_fmt'),
        empresa=lead.get('empresa'),
        slug=slugify(lead.get('empresa') or ''),
        sender_name=sender_label or owner_name,
        sender_phone=sender_phone,
        campaign_id='lead_sem_contato_follow1',
        msg_type='primeiro_contato',
        attempt_number=1,
    )
    return {'ok': bool(res.get('ok')), 'deduped': bool(res.get('deduped')), 'dispatch_id': res.get('dispatch_id'), 'skipped': res.get('skipped'), 'reason': res.get('reason')}


def escolher_porta_online(bridge, envios, jid=None, lead_key=None):
    """Retorna a porta online para o SDR usando roteamento central + fallback legado.

    Regra nova: se o lead já conversa por um chip do SDR, testar esse chip
    primeiro; lead novo segue distribuição central. Se o chip escolhido estiver
    offline, mantém fallback antigo de menor uso entre portas online.
    """
    ports = bridge.get('ports') or [bridge['port']]
    central_first = None
    if jid:
        try:
            decision = choose_outbound_port(bridge.get('owner_uid') or '', jid, lead_key=lead_key or jid, rows=envios)
            if decision.get('port') in ports:
                central_first = int(decision.get('port'))
        except Exception:
            central_first = None
    def used_count(port):
        return sum(1 for e in envios if isinstance(e, dict) and e.get('bridge_port') == port)
    ordered = sorted(ports, key=lambda p: (used_count(p), p))
    if central_first in ordered:
        ordered = [central_first] + [p for p in ordered if p != central_first]
    erros = []
    for port in ordered:
        try:
            url = f"http://localhost:{port}/status"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = json.loads(resp.read().decode())
            if status.get('connected'):
                return port, status, erros

            # Fallback defensivo: /status pode ficar stale depois do QR, mas /me
            # válido prova que a sessão está pareada e o socket responde.
            me_url = f"http://localhost:{port}/me"
            with urllib.request.urlopen(urllib.request.Request(me_url), timeout=10) as resp:
                me = json.loads(resp.read().decode())
            if me.get('id') and me.get('phone'):
                status['_status_stale_but_me_ok'] = True
                status['_me'] = me
                return port, status, erros

            erros.append(f"porta {port} desconectada/status={status}/me={me}")
        except Exception as e:
            erros.append(f"porta {port}: {e}")
    return None, None, erros


def envio_datetime_brt(e):
    """Extrai datetime aware em BRT para limites anti-bloqueio."""
    raw_tz = str(e.get('date_tz') or '').strip()
    if raw_tz:
        try:
            dt = datetime.fromisoformat(raw_tz.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone(timedelta(hours=-3)))
            return dt.astimezone(timezone(timedelta(hours=-3)))
        except Exception:
            pass
    raw = str(e.get('date', '')).strip()
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(raw[:19], fmt).replace(tzinfo=timezone(timedelta(hours=-3)))
        except Exception:
            pass
    return None


def envios_sdr_ultima_hora(envios, owner_name):
    """Conta primeiro_contato do SDR nos últimos 60 min (limite anti-bloqueio)."""
    agora = datetime.now(timezone(timedelta(hours=-3)))
    total = 0
    for e in envios:
        if not isinstance(e, dict):
            continue
        if e.get('msg_type') != 'primeiro_contato':
            continue
        if str(e.get('sdr', '')).lower() != owner_name.lower():
            continue
        dt = envio_datetime_brt(e)
        if dt and 0 <= (agora - dt).total_seconds() < 3600:
            total += 1
    return total


def envios_sdr_hoje(envios, owner_name):
    """Conta primeiro_contato do SDR no dia BRT atual (limite diário conservador)."""
    agora = datetime.now(timezone(timedelta(hours=-3)))
    total = 0
    for e in envios:
        if not isinstance(e, dict):
            continue
        if e.get('msg_type') != 'primeiro_contato':
            continue
        if str(e.get('sdr', '')).lower() != owner_name.lower():
            continue
        dt = envio_datetime_brt(e)
        if dt and dt.date() == agora.date():
            total += 1
    return total


def is_direct_external_envio(e):
    """Registro que pesa chip por falar com lead/contato externo.

    Grupo interno @g.us não entra nesse teto. O painel/ledger ainda registra,
    mas o risco comercial principal é mensagem direta ao lead.
    """
    if not isinstance(e, dict):
        return False
    to = str(e.get('to') or e.get('jid') or e.get('lead_jid') or '')
    if to.endswith('@g.us'):
        return False
    if not e.get('bridge_port'):
        return False
    status = str(e.get('status') or '').lower()
    msg_type = str(e.get('msg_type') or '').lower()
    return bool(e.get('text_status') or e.get('messageId') or msg_type or status in {'enviado_lead','enviado_mql','enviado','sent'})


def envio_external_contact_key(e):
    """Chave do lead/pessoa para limites de WhatsApp.

    Regra Rafael 30/06: limite operacional conta pessoa/lead único, não quantidade
    de bolhas/partes enviadas para a mesma pessoa. Uma sequência com saudação,
    apresentação e CTA continua valendo 1 unidade se for o mesmo telefone/JID.
    """
    if not isinstance(e, dict):
        return ''
    for field in PHONE_FIELDS:
        raw = str(e.get(field) or '').strip()
        if not raw or raw.endswith('@g.us'):
            continue
        key = normalize_phone(raw)
        if key:
            return key
    return ''


def envios_porta_periodo(envios, port, seconds=None, same_day=False):
    agora = datetime.now(timezone(timedelta(hours=-3)))
    contacts = set()
    for e in envios:
        if not is_direct_external_envio(e):
            continue
        try:
            if int(e.get('bridge_port')) != int(port):
                continue
        except Exception:
            continue
        dt = envio_datetime_brt(e)
        if not dt:
            continue
        delta = (agora - dt).total_seconds()
        if seconds is not None and not (0 <= delta < seconds):
            continue
        if same_day and dt.date() != agora.date():
            continue
        key = envio_external_contact_key(e)
        if key:
            variants = phone_key_variants(key) or {key}
            # Um telefone com/sem 9º dígito precisa cair na MESMA unidade.
            contacts.add(sorted(variants, key=lambda v: (len(v), v))[0])
        else:
            # Fallback conservador quando não há telefone no registro: conta o
            # próprio registro para não liberar envio sem rastreabilidade.
            contacts.add(f"registro:{id(e)}")
    return len(contacts)


def port_within_external_limits(envios, port, max_per_hour=MAX_EXTERNAL_PER_PORT_HOUR, max_per_day=MAX_EXTERNAL_PER_PORT_DAY):
    hour = envios_porta_periodo(envios, port, seconds=3600)
    day = envios_porta_periodo(envios, port, same_day=True)
    ok = hour < max_per_hour and day < max_per_day
    reason = f'porta {port}: {hour}/{max_per_hour} na última hora, {day}/{max_per_day} hoje'
    return ok, reason


def current_deal_stage(deal_id):
    if not deal_id:
        return ''
    res = hs_request(f'https://api.hubapi.com/crm/v3/objects/deals/{deal_id}?properties=dealstage')
    return str(((res or {}).get('properties') or {}).get('dealstage') or '')


def is_protected_advanced_stage(stage):
    return str(stage or '') in PROTECTED_ADVANCED_STAGES


def create_retorno_task(deal_id, contact_id, owner_id, owner_name, lead_name, tel, incoming_messages):
    if is_protected_advanced_stage(current_deal_stage(deal_id)):
        # Rafael 30/06: não criar atividade para leads fora das primeiras 6 etapas.
        return None
    snippets = []
    for m in (incoming_messages or [])[-5:]:
        txt = re.sub(r'\s+', ' ', str(m.get('text') or '')).strip()
        if txt:
            snippets.append(f"- {txt[:500]}")
    body_txt = "Lead respondeu após mensagem/diagnóstico da Zydon. Não enviar follow-up por cima; abrir histórico e seguir de forma contextual, sem repetir apresentação ou explicação já enviada.\n\n"
    if snippets:
        body_txt += "Últimas mensagens do lead:\n" + "\n".join(snippets)
    body_txt += "\n\nPróxima ação: se for resposta fraca, continuar aquecimento; se houver dúvida/intenção real, conduzir para agenda ou Retorno Contato conforme contexto."
    url = "https://api.hubapi.com/crm/v3/objects/tasks"
    body = {
        "properties": {
            "hs_timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "hs_task_subject": f"Retorno WhatsApp - {lead_name} ({tel})",
            "hs_task_body": body_txt,
            "hs_task_status": "NOT_STARTED",
            "hs_task_priority": "HIGH",
            "hubspot_owner_id": owner_id,
        },
        "associations": [
            {"to": {"id": int(contact_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 204}]},
            {"to": {"id": int(deal_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 216}]},
        ]
    }
    result = hs_request(url, 'POST', body)
    return result.get('id') if result else None


def resposta_fraca_whatsapp(incoming_messages):
    """Resposta curta/fraca não deve mover automaticamente para Retorno Contato."""
    texts = []
    for m in (incoming_messages or [])[-3:]:
        txt = re.sub(r'\s+', ' ', str(m.get('text') or '')).strip().lower()
        if txt:
            texts.append(txt)
    if not texts:
        return False
    last = texts[-1]
    weak_exact = {'oi', 'olá', 'ola', 'bom dia', 'boa tarde', 'boa noite', 'ok', 'okk', 'obrigado', 'obrigada', 'valeu', 'sim', 'whatsapp', 'wpp', 'zap'}
    normalized = re.sub(r'[^a-z0-9áàâãéêíóôõúç ]+', '', last).strip()
    if normalized in weak_exact:
        return True
    words = normalized.split()
    if len(words) <= 2 and any(w in weak_exact for w in (normalized, words[0] if words else '')):
        return True
    # Se já há conteúdo comercial, não é fraca.
    commercial_terms = ('agenda', 'reuni', 'preço', 'preco', 'valor', 'erp', 'omie', 'bling', 'tiny', 'pedido', 'vendedor', 'cliente', 'portal', 'tabela', 'pagamento', 'integr')
    return len(words) <= 2 and not any(t in normalized for t in commercial_terms)


def create_hubspot_task(deal_id, contact_id, owner_id, owner_name, lead_name, tel, bridge_port=None, sender_phone=None, sender_label=None, message_id=None):
    if is_protected_advanced_stage(current_deal_stage(deal_id)):
        # Rafael 30/06: atividades automáticas só nas primeiras 6 etapas.
        return None
    url = "https://api.hubapi.com/crm/v3/objects/tasks"
    sender_label = sender_label or owner_name
    sender_phone = sender_phone or ''
    details = [
        f"Disparo de primeiro contato via WhatsApp ({tel}) — {owner_name}.",
        "",
        f"Remetente/SDR: {sender_label}",
    ]
    if bridge_port:
        details.append(f"Porta/chip: {bridge_port}")
    if sender_phone:
        details.append(f"Telefone do remetente: {sender_phone}")
    if message_id:
        details.append(f"MessageId WhatsApp: {message_id}")
    body = {
        "properties": {
            "hs_timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "hs_task_subject": f"Primeiro contato WhatsApp - {lead_name} ({tel}) — {sender_label}" + (f" / porta {bridge_port}" if bridge_port else ""),
            "hs_task_body": "\n".join(details),
            "hs_task_status": "COMPLETED",
            "hs_task_priority": "MEDIUM",
            "hubspot_owner_id": owner_id,
        },
        "associations": [
            {"to": {"id": int(contact_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 204}]},
            {"to": {"id": int(deal_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 216}]},
        ]
    }
    result = hs_request(url, 'POST', body)
    return result.get('id') if result else None


def acquire_global_send_lock(blocking=False):
    """Lock global compartilhado com o cron de diagnóstico/PDF.

    Primeiro contato não deve competir com diagnóstico no mesmo tick. Se o
    diagnóstico estiver processando/envio em andamento, este cron sai silencioso
    e tenta de novo no próximo ciclo.
    """
    global _GLOBAL_LOCK_FH
    _GLOBAL_LOCK_FH = open(GLOBAL_SEND_LOCK, 'w')
    flags = 0 if blocking else fcntl.LOCK_NB
    try:
        fcntl.flock(_GLOBAL_LOCK_FH, fcntl.LOCK_EX | flags)
    except BlockingIOError:
        return False
    _GLOBAL_LOCK_FH.write(f"disparo_dinamico pid={os.getpid()} at={datetime.now(timezone.utc).isoformat()}\n")
    _GLOBAL_LOCK_FH.flush()
    def _release():
        try:
            fcntl.flock(_GLOBAL_LOCK_FH, fcntl.LOCK_UN)
            _GLOBAL_LOCK_FH.close()
        except Exception:
            pass
    atexit.register(_release)
    return True


def main():
    args = sys.argv[1:]
    dry_run_requested = '--dry-run' in args
    worker_owned = str(os.environ.get('ZYDON_DISPARO_DINAMICO_WORKER_OWNED') or '').lower() in {'1', 'true', 'yes', 'on'}
    if not dry_run_requested and not worker_owned and not acquire_global_send_lock(blocking=False):
        # Outro fluxo externo está enviando/registrando agora (diagnóstico/PDF ou outro SDR).
        # Sair sem enviar evita corrida; cron tenta de novo no próximo tick.
        print("🕒 Lock global de envio ocupado; pulando este ciclo para evitar duplicidade com diagnóstico/SDR.")
        return
    if not args or args[0].lower() not in BRIDGES:
        print("Uso: python3 disparo_dinamico.py <breno|sarah|lucas> [--limit N]")
        sys.exit(1)

    sdr_key = args[0].lower()
    if sdr_key in SDRS_BLOQUEADOS:
        print(f"🛑 {SDRS_BLOQUEADOS[sdr_key]}")
        print("   Nenhuma consulta/envio será feita para este SDR.")
        return

    LIMIT = 5
    if '--limit' in args:
        idx = args.index('--limit')
        if idx + 1 < len(args):
            LIMIT = int(args[idx + 1])

    delay_segundos = DELAY_SEGUNDOS
    if '--delay' in args:
        idx = args.index('--delay')
        if idx + 1 < len(args):
            delay_segundos = int(args[idx + 1])

    max_per_hour = None
    if '--max-per-hour' in args:
        idx = args.index('--max-per-hour')
        if idx + 1 < len(args):
            max_per_hour = int(args[idx + 1])

    max_per_day = None
    if '--max-per-day' in args:
        idx = args.index('--max-per-day')
        if idx + 1 < len(args):
            max_per_day = int(args[idx + 1])

    min_age_hours = None
    if '--min-age-hours' in args:
        idx = args.index('--min-age-hours')
        if idx + 1 < len(args):
            min_age_hours = float(args[idx + 1])

    max_age_hours = None
    if '--max-age-hours' in args:
        idx = args.index('--max-age-hours')
        if idx + 1 < len(args):
            max_age_hours = float(args[idx + 1])

    dry_run = '--dry-run' in args

    stage_scope = 'first5'
    if '--stage-scope' in args:
        idx = args.index('--stage-scope')
        if idx + 1 < len(args):
            stage_scope = str(args[idx + 1]).strip().lower()
    if stage_scope in ('lead_sem_contato', 'lead-sem-contato', 'lsc'):
        search_stages = [STAGE_LEAD_SEM_CONTATO]
        stage_label = 'Lead Sem Contato'
        # Regra padrão: a régua automática só olha Primeiro Contato. Exceção
        # operacional explícita do Rafael (01/07): iniciar os leads que ainda estão
        # em Lead Sem Contato pelos chips recém-conectados de Sarah/Breno. Mantém
        # opt-in por variável para o cron principal não reabrir LSC sozinho.
        allow_lsc_send = str(os.environ.get('ZYDON_ALLOW_LEAD_SEM_CONTATO_SEND') or '').lower() in ('1', 'true', 'yes', 'sim')
        if not dry_run and not allow_lsc_send:
            print('🛑 Regra Rafael 01/07: automação padrão só envia se o negócio estiver em Primeiro Contato. Lead Sem Contato exige autorização explícita por execução.')
            return
    elif stage_scope in ('primeiro_contato', 'primeiro-contato', 'pc'):
        search_stages = [STAGE_PRIMEIRO_CONTATO]
        stage_label = 'Primeiro Contato'
    else:
        # Fail-closed: não varrer 5 etapas para envio automático. O escopo de
        # WhatsApp SDR agora é somente Primeiro Contato.
        search_stages = [STAGE_PRIMEIRO_CONTATO]
        stage_label = 'Primeiro Contato'

    bridge = BRIDGES[sdr_key]
    owner_id = bridge['owner_id']
    owner_name = bridge['owner_name']
    msg_builder = MSG_BUILDERS[sdr_key]

    now = datetime.now(timezone(timedelta(hours=-3)))
    print(f"\n{'='*60}")
    print(f"  DISPARO DINÂMICO — {owner_name.upper()} | {now.strftime('%d/%m %H:%M')} BRT")
    print(f"  Portas {bridge.get('ports') or [bridge['port']]} | Limite: {LIMIT} envios | Delay: {delay_segundos}s")
    print(f"{'='*60}")

    # 1. Carregar envios (anti-loop) — fonte ÚNICA compartilhada (lista)
    envios = load_envios()
    enviados_keys = envios_phone_set(envios) | outbound_audit_phone_set()
    print(f"   {len(envios)} registros de envio carregados (controle compartilhado).")
    print(f"   {len(enviados_keys)} telefones bloqueados por anti-loop ledger/audit.")

    if max_per_hour is not None:
        usados_ultima_hora = envios_sdr_ultima_hora(envios, owner_name)
        restante_hora = max(0, max_per_hour - usados_ultima_hora)
        print(f"⏱️  Limite horário {owner_name}: {usados_ultima_hora}/{max_per_hour} usados na última hora; restante={restante_hora}.")
        if restante_hora <= 0:
            print("🛑 Limite horário já atingido. Encerrando sem enviar.")
            return
        if LIMIT > restante_hora:
            LIMIT = restante_hora
            print(f"   Ajustando limite deste lote para {LIMIT} para respeitar o máximo por hora.")

    if max_per_day is not None:
        usados_hoje = envios_sdr_hoje(envios, owner_name)
        restante_dia = max(0, max_per_day - usados_hoje)
        print(f"🛡️  Limite diário {owner_name}: {usados_hoje}/{max_per_day} usados hoje; restante={restante_dia}.")
        if restante_dia <= 0:
            print("🛑 Limite diário já atingido. Encerrando sem enviar.")
            return
        if LIMIT > restante_dia:
            LIMIT = restante_dia
            print(f"   Ajustando limite deste lote para {LIMIT} para respeitar o máximo diário.")

    # 2. Verificar se existe ao menos uma bridge online para este SDR.
    # A porta final é escolhida A CADA MENSAGEM para rotacionar entre chips ativos.
    port_inicial, status, port_errors = escolher_porta_online(bridge, envios)
    if not port_inicial:
        print(f"❌ Nenhuma bridge online para {owner_name}. Abortando.")
        for err in port_errors:
            print(f"   - {err}")
        sys.exit(1)
    print(f"✅ Bridge disponível. Primeira porta candidata: {port_inicial}. Rotação por mensagem ativa.")

    # 3. Buscar deals AO VIVO
    print(f"🔍 Consultando HubSpot (owner {owner_id})...")
    all_deals = buscar_deals_sem_tarefa(owner_id, stages=search_stages)
    print(f"   {len(all_deals)} deals em {stage_label}.")

    all_deals = filtrar_deals_por_idade(all_deals, min_age_hours=min_age_hours, max_age_hours=max_age_hours)

    if not all_deals:
        print("   Nenhum deal encontrado. Encerrando.")
        return

    # 2b. Filtrar: deals sem atividade comercial válida.
    # Tarefa de diagnóstico enviada pelo cron 24/7 NÃO bloqueia follow-up SDR.
    print(f"🔎 Filtrando deals sem atividade válida (ignorando task de diagnóstico)...")
    ids_elegiveis = filtrar_deals_sem_atividade_valida(all_deals)
    deals = [d for d in all_deals if str(d['id']) in ids_elegiveis]
    print(f"   {len(deals)} deals elegíveis para follow-up SDR (de {len(all_deals)} totais).")

    ja_enviados_count = sum(1 for r in envios
                            if isinstance(r, dict)
                            and str(r.get('sdr', '') or '').lower() in (sdr_key, owner_name.lower()))

    # 4. Processar deals (parar quando tiver candidatos suficientes)
    candidatos = []
    sem_tel = 0
    ja_enviado = 0
    # Precamos LIMIT + 5 candidatos extras (margem pra falhas)
    TARGET_CANDIDATOS = LIMIT + 5
    CHECADOS = 0
    MAX_CHECAR = min(len(deals), 80)  # cap pra não estourar rate limit

    for deal in deals:
        if len(candidatos) >= TARGET_CANDIDATOS or CHECADOS >= MAX_CHECAR:
            break
        CHECADOS += 1
        deal_id = deal['id']
        props = deal.get('properties', {})
        dealname = props.get('dealname', 'Sem nome')
        dealstage = str(props.get('dealstage') or '')
        if dealstage == '998099482':
            # Já está em Retorno Contato. Não repetir task/movimentação a cada ciclo.
            ja_enviado += 1
            continue

        # Buscar contato
        result = get_contact_for_deal(deal_id)
        if not result:
            continue
        contact_id, contact_props = result

        # Extrair telefone
        tel_data = extrair_telefone(contact_props)
        if not tel_data:
            sem_tel += 1
            continue

        tel_raw, jid, tel_fmt = tel_data

        # Pular se já enviado — compara o telefone normalizado (DDD+número)
        # do JID contra a lista compartilhada dos 3 crons e também contra o
        # histórico real do Channel/WhatsApp. Isso evita repetir "1º contato"
        # quando uma mensagem antiga existe no chat, mas não entrou no ledger.
        phone_key = normalize_phone(jid)
        bridge_ports = bridge.get('ports') or [bridge['port']]
        diag_context = diagnostico_context_for_phone(envios, phone_key)
        history_ports = sorted(set(int(p) for p in bridge_ports) | diagnostico_ports_for_phone(envios, phone_key))
        recent_diag_hours = diagnostico_recente_hours(envios, phone_key)
        # Se o lead já respondeu depois de uma mensagem nossa/diagnóstico, não mandar
        # follow-up por cima. Nova régua Rafael: resposta fraca NÃO move sozinha
        # para Retorno Contato; cria tarefa/alerta e mantém aquecimento.
        incoming = history_incoming_after_outgoing(phone_key, history_ports)
        if incoming:
            fraca = resposta_fraca_whatsapp(incoming)
            if dry_run:
                acao = 'criaria tarefa e manteria na etapa atual (resposta fraca)' if fraca else 'criaria tarefa e moveria para Retorno Contato'
                print(f"   🧪 DRY-RUN: {dealname}: lead já respondeu após mensagem nossa em portas {history_ports}; {acao} ({len(incoming)} msg).")
            else:
                task_id = create_retorno_task(deal_id, contact_id, owner_id, owner_name, dealname, tel_fmt, incoming)
                if fraca:
                    if dealstage == STAGE_LEAD_SEM_CONTATO:
                        try:
                            hs_request(
                                f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}",
                                'PATCH',
                                {'properties': {'dealstage': STAGE_PRIMEIRO_CONTATO}},
                            )
                            print(f"   ↪️  {dealname}: resposta fraca detectada; movido de Lead Sem Contato para Primeiro Contato. Task={task_id} ({len(incoming)} msg).")
                        except Exception as e:
                            print(f"   ⚠️  {dealname}: resposta fraca, task={task_id}, mas falhou mover para Primeiro Contato: {e}")
                    else:
                        print(f"   ↪️  {dealname}: resposta fraca detectada; NÃO movido para Retorno. Task={task_id} ({len(incoming)} msg).")
                else:
                    if dealstage in PROTECTED_ADVANCED_STAGES:
                        print(f"   ↪️  {dealname}: resposta detectada, mas negócio já está em etapa avançada ({dealstage}); NÃO movido para Retorno. Task={task_id} ({len(incoming)} msg).")
                    else:
                        try:
                            hs_request(
                                f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}",
                                'PATCH',
                                {'properties': {'dealstage': STAGE_RETORNO_CONTATO}},
                            )
                            print(f"   ↪️  {dealname}: resposta com sinal/contexto; movido para Retorno Contato. Task={task_id} ({len(incoming)} msg).")
                        except Exception as e:
                            print(f"   ⚠️  {dealname}: resposta detectada, task={task_id}, mas falhou mover para Retorno Contato: {e}")
            ja_enviado += 1
            continue

        # Diagnóstico/PDF orienta o follow-up, mas não pode virar mensagem colada.
        # Se acabou de sair, aguardar algumas horas; se já passou do fim do dia,
        # o próprio cron só volta no próximo horário útil.
        if diag_context and recent_diag_hours is not None and recent_diag_hours < MIN_HOURS_AFTER_DIAG_FOR_SDR_FOLLOW:
            ja_enviado += 1
            if dealstage == STAGE_LEAD_SEM_CONTATO and not dry_run:
                try:
                    hs_request(
                        f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}",
                        'PATCH',
                        {'properties': {'dealstage': STAGE_PRIMEIRO_CONTATO}},
                    )
                    print(f"   ⏳ {dealname}: diagnóstico enviado há {recent_diag_hours:.2f}h; movido para Primeiro Contato e aguardando respiro antes do follow SDR.")
                except Exception as e:
                    print(f"   ⚠️  {dealname}: diagnóstico recente, mas falhou mover para Primeiro Contato: {e}")
            else:
                print(f"   ⏳ {dealname}: diagnóstico enviado há {recent_diag_hours:.2f}h; aguardando antes do follow SDR para não repetir contato colado.")
            continue
        if phone_key in enviados_keys or history_outgoing_exists(phone_key, bridge_ports):
            ja_enviado += 1
            if dealstage == STAGE_LEAD_SEM_CONTATO and not dry_run:
                try:
                    hs_request(
                        f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}",
                        'PATCH',
                        {'properties': {'dealstage': STAGE_PRIMEIRO_CONTATO}},
                    )
                    print(f"   ↪️  {dealname}: já tinha contato/saída registrada; movido de Lead Sem Contato para Primeiro Contato.")
                except Exception as e:
                    print(f"   ⚠️  {dealname}: já tinha contato, mas falhou mover para Primeiro Contato: {e}")
            continue

        # Se a mesma empresa já teve outro negócio/contato abordado recentemente,
        # não criar novo D0 nem mover este segundo negócio para Primeiro Contato.
        # Mantém o follow-up concentrado no negócio/contato que já está ativo.
        duplicate_touch = company_recently_touched(envios, dealname.strip(), current_deal_id=deal_id)
        if duplicate_touch:
            ja_enviado += 1
            print(f"   ↪️  pulando duplicado por empresa: {dealname.strip()} já teve envio recente em outro negócio ({duplicate_touch.get('deal_id') or duplicate_touch.get('email') or duplicate_touch.get('slug')})")
            continue

        # Extrair dados para mensagem
        firstname = contact_props.get('firstname', '') or ''
        nome = firstname.strip().split()[0].capitalize() if firstname.strip() else 'tudo bem'
        erp = extrair_erp(contact_props)

        candidatos.append({
            'deal_id': deal_id,
            'contact_id': contact_id,
            'nome': nome,
            'empresa': dealname.strip(),
            'erp': erp,
            'tel': tel_raw,
            'jid': jid,
            'tel_fmt': tel_fmt,
            'diagnostico_context': diag_context,
        })

    print(f"📊 {len(candidatos)} prontos para disparar | {ja_enviado} já enviados | {sem_tel} sem tel/fixo")

    if not candidatos:
        print("   Nenhum lead novo para disparar agora. ✅")
        return

    # 5. Disparar (respeitando limite)
    enviados = 0
    falhas = 0

    for i, lead in enumerate(candidatos):
        if enviados >= LIMIT:
            print(f"\n  🛑 Limite de {LIMIT} atingido. Restantes: {len(candidatos) - i}")
            break

        if lead.get('diagnostico_context'):
            nome_msg = lead['nome'] if lead['nome'] and lead['nome'] != 'tudo bem' else 'tudo bem'
            question = SECOND_INTENT_QUESTION if intent_question_already_asked(lead.get('diagnostico_context')) else first_sdr_question_for_key(lead.get('deal_id') or lead.get('jid'))
            msg = (
                f"{nome_msg}, seguindo o diagnóstico que te mandei, quero começar pelo motivo principal.\n\n"
                f"{bloco_portal_real(lead.get('empresa') or '', lead.get('nome') or '', lead.get('erp') or '')}\n\n"
                f"{zydon_explicacao_curta()}\n\n"
                f"{question}"
            )
        else:
            msg = msg_builder(lead['nome'], lead['empresa'], lead['erp'])
        # Nunca anexar/citar o texto do diagnóstico anterior aqui. O diagnóstico
        # é apenas contexto interno para não soar frio; copiar o bloco no WhatsApp
        # gera textão e repete a mensagem do comunicador. Mesmo se a retomada vier
        # logo em seguida ao diagnóstico, ela precisa ser continuidade da conversa.
        print(f"\n  📤 [{enviados+1}] {lead['nome']} | {lead['empresa']} | ERP={lead['erp'] or '?'} | {lead['tel_fmt']}")

        # Escolhe a porta a cada mensagem para alternar entre chips ativos
        # (ex.: rotação entre portas quando houver múltiplos chips ativos).
        envios_rotacao = load_envios()
        port, status, port_errors = escolher_porta_online(bridge, envios_rotacao, jid=lead['jid'], lead_key=lead.get('deal_id') or lead.get('contact_id') or lead['jid'])
        if not port:
            print(f"     ❌ Nenhuma porta online no momento. Abortando lote para proteger os chips.")
            for err in port_errors:
                print(f"        - {err}")
            break
        print(f"     🔁 Porta escolhida: {port}")
        msg = apply_contact_cta(msg, port=port, is_sdr_sender=True)
        sender_phone = ''
        sender_label = owner_name
        try:
            with urllib.request.urlopen(urllib.request.Request(f"http://localhost:{port}/me"), timeout=5) as resp_me:
                me_info = json.loads(resp_me.read().decode())
            sender_phone = str(me_info.get('phone') or me_info.get('id') or '')
            sender_label = str(me_info.get('name') or owner_name)
        except Exception:
            pass

        if not history_outgoing_exists(normalize_phone(lead['jid']), [port]):
            msg = add_sender_presentation(msg, sender_label)

        # Recheca a fonte compartilhada IMEDIATAMENTE antes de enviar. Isso cobre
        # a corrida em que o diagnóstico acabou de registrar o mesmo telefone entre
        # a montagem dos candidatos e este ponto, e também aplica teto global por chip.
        envios_finais = load_envios()
        if normalize_phone(lead['jid']) in envios_phone_set(envios_finais):
            print("     ↪️ Pulado: telefone apareceu no ledger compartilhado antes do envio.")
            enviados_keys.add(normalize_phone(lead['jid']))
            continue
        port_ok, port_reason = port_within_external_limits(
            envios_finais,
            port,
            max_per_hour=max_per_hour or MAX_EXTERNAL_PER_PORT_HOUR,
            max_per_day=max_per_day or MAX_EXTERNAL_PER_PORT_DAY,
        )
        if not port_ok:
            print(f"     🛑 Limite global do chip atingido: {port_reason}. Pulando este envio.")
            continue

        if dry_run:
            print("     🧪 DRY-RUN: não envia WhatsApp, não cria task, não move etapa.")
            enviados += 1
            continue

        if worker_owned:
            res = enqueue_worker_owned_first_contact(
                lead,
                port,
                msg,
                owner_id=owner_id,
                owner_name=owner_name,
                sender_label=sender_label,
                sender_phone=sender_phone,
            )
            if res.get('ok') or res.get('deduped'):
                print(f"     🧾 Enfileirado worker_owned: {res.get('dispatch_id') or 'dedupe'}")
                enviados += 1
                enviados_keys.add(normalize_phone(lead['jid']))
                continue
            print(f"     ❌ Falha ao enfileirar worker_owned: {res}")
            falhas += 1
            break

        ok, resp = send_whatsapp_sequence(port, lead['jid'], msg)
        if ok:
            print(f"     ✅ Enviado em {resp.get('parts', 1)} partes!")
            enviados += 1

            # Registrar envio na fonte ÚNICA (read-modify-write: append,
            # nunca sobrescreve a lista → preserva histórico dos outros crons).
            sent_at_brt = datetime.now(timezone(timedelta(hours=-3)))
            registrar_envio({
                # IMPORTANTE: usar BRT explícito. Antes era time.strftime() no timezone
                # do servidor (UTC), causando "últimos envios há X horas" errado nos painéis.
                'date': sent_at_brt.strftime('%Y-%m-%d %H:%M'),
                'date_tz': sent_at_brt.isoformat(),
                'to': lead['jid'],
                'slug': slugify(lead['empresa']),
                'nome': lead['nome'],
                'sdr': owner_name,
                'sender_name': sender_label,
                'sender_phone': sender_phone,
                'bridge_port': port,
                'text': msg,
                'text_status': 'ok',
                'messageId': (resp or {}).get('messageId'),
                'send_response': resp,
                'empresa': lead['empresa'],
                'msg_type': 'primeiro_contato',
                'attempt_number': 1,
                'campaign_id': 'lead_sem_contato_follow1',
                'deal_id': lead['deal_id'],
                'contact_id': lead['contact_id'],
            })
            # Marca como enviado também na sessão atual (evita reenvio no lote).
            enviados_keys.add(normalize_phone(lead['jid']))

            # Criar tarefa no HubSpot
            task_id = create_hubspot_task(
                lead['deal_id'], lead['contact_id'], owner_id, owner_name, lead['nome'], lead['tel_fmt'],
                bridge_port=port,
                sender_phone=sender_phone,
                sender_label=sender_label,
                message_id=(resp or {}).get('messageId'),
            )
            if task_id:
                print(f"     📋 Tarefa: {task_id}")

            # Depois do primeiro contato/follow-up SDR confirmado, o card não pode
            # ficar em Lead Sem Contato. Diagnóstico/PDF sozinho não move etapa.
            moved = hs_request(
                f"https://api.hubapi.com/crm/v3/objects/deals/{lead['deal_id']}",
                'PATCH',
                {'properties': {'dealstage': '1214320997'}},
            )
            moved_stage = ((moved or {}).get('properties') or {}).get('dealstage')
            print(f"     🔁 Etapa HubSpot: {moved_stage or 'não confirmado'}")

        else:
            print(f"     ❌ Falha: {resp}")
            falhas += 1
            print("     🛑 Parando este SDR após a primeira falha para evitar retry em massa/risco de ban.")
            break

        if enviados < LIMIT and i < len(candidatos) - 1:
            time.sleep(delay_segundos)

    # 6. Resumo
    print(f"\n{'='*60}")
    print(f"  RESUMO — {owner_name.upper()} | {now.strftime('%d/%m %H:%M')} BRT")
    print(f"  Disparados neste lote: {enviados}")
    print(f"  Falhas: {falhas}")
    print(f"  Já enviados (pulados): {ja_enviado}")
    total_enviado_sdr = ja_enviados_count + enviados
    print(f"  Total {owner_name} já contatado: {total_enviado_sdr}")
    restantes = len(candidatos) - enviados
    if restantes > 0:
        print(f"  ⏳ Restantes para próximos lotes: {restantes}")
    else:
        print(f"  ✅ TODOS os leads atuais contatados! Novos leads serão pegos no próximo ciclo.")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
