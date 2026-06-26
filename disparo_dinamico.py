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

# ─── Config ───
BRIDGES = {
    'breno': {'port': 4605, 'ports': [4605], 'owner_id': '86265630', 'owner_name': 'Breno'},
    # Sarah usa somente a principal/4601; 4604 foi removida/desativada.
    'sarah': {'port': 4601, 'ports': [4601], 'owner_id': '88063842', 'owner_name': 'Sarah'},
    'lucas': {'port': 4603, 'owner_id': '85778446', 'owner_name': 'Lucas Batista'},
}

PAT = os.environ.get("HUBSPOT_ACCESS_TOKEN", "")
HS_HEADERS = {"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"}
PIPELINE = '671008549'
FIRST_5_STAGES = ['984052829', '1214320997', '998099482', '1151853491', '1376131958']

WPP_ENVIOS = '/root/.hermes/zydon-prospeccao/controle/wpp_envios.json'
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
    """Grava a LISTA no formato real {"envios": [...]}."""
    with open(WPP_ENVIOS, 'w') as f:
        json.dump({"envios": envios}, f, ensure_ascii=False, indent=2)


def registrar_envio(registro):
    """READ-MODIFY-WRITE: relê a lista atual, faz APPEND do novo registro e
    grava de volta. Nunca sobrescreve a lista inteira — preserva o histórico
    dos outros crons (gate/ciclo)."""
    envios = load_envios()
    envios.append(registro)
    save_envios(envios)
    return envios


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
            if any(normalize_phone(str(v or '')) == phone_key for v in vals):
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
            if any(normalize_phone(str(v or '')) == phone_key for v in vals):
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

    Regra Rafael: diagnóstico/PDF, mesmo respondido, NÃO muda fase e NÃO bloqueia
    o primeiro contato/follow-up do SDR. Aqui bloqueamos somente mensagens SDR já
    enviadas, para não repetir a primeira abordagem do SDR.
    """
    chaves = set()
    sdr_statuses = {'enviado', 'sent'}
    sdr_msg_types = {'primeiro_contato', 'primeiro_contato_backlog_institucional', 'primeiro_contato_cadencia', 'mql_sdr_followup'}
    for r in envios:
        if not isinstance(r, dict):
            continue
        status = str(r.get('status', '')).lower()
        msg_type = str(r.get('msg_type', '')).lower()
        # enviado_lead/enviado_mql são diagnóstico/MQL: servem de contexto, não de bloqueio.
        if msg_type not in sdr_msg_types and status not in sdr_statuses:
            continue
        for campo in PHONE_FIELDS:
            raw = str(r.get(campo, '') or '')
            if raw.endswith('@g.us'):
                continue
            p = normalize_phone(raw)
            if p:
                chaves.add(p)
    return chaves


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
        if not any(normalize_phone(v) == phone_key for v in vals):
            continue
        text = str(r.get('text') or r.get('group_summary') or r.get('summary') or '').strip()
        if text:
            matches.append(text)
    if not matches:
        return ''
    txt = re.sub(r'\s+', ' ', matches[-1])
    # Pegar um trecho útil, sem transformar em afirmação forte.
    return txt[:360]


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
        if not any(normalize_phone(v) == phone_key for v in vals):
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


def buscar_deals_sem_tarefa(owner_id):
    """
    Busca deals nas 5 primeiras etapas pertencentes ao owner.
    Retorna lista de {deal_id, dealname, dealstage, createdate}.
    Prioridade do Rafael: lead novo/quente primeiro — quem acabou de entrar
    deve ser chamado antes do backlog antigo.
    """
    url = "https://api.hubapi.com/crm/v3/objects/deals/search"
    body = {
        "filterGroups": [{
            "filters": [
                {"propertyName": "pipeline", "operator": "EQ", "value": PIPELINE},
                {"propertyName": "dealstage", "operator": "IN", "values": FIRST_5_STAGES},
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


def empresa_valida(empresa):
    empresa = (empresa or '').strip()
    if not empresa or empresa.lower() in ('sem nome', 'sem empresa'):
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


def montar_msg_breno(nome, empresa, erp):
    nome_ok = primeiro_nome_valido(nome)
    empresa_ok = empresa_valida(empresa)
    var_idx = escolher_variacao('breno', nome, empresa, erp, 8)
    saudacao = saudacao_por_variacao(nome_ok, var_idx, 'Oi')
    empresa_txt = f" da {empresa_ok}" if empresa_ok else ""
    empresa_contexto = f"a {empresa_ok}" if empresa_ok else "a empresa"
    erp_txt = f" Vi aqui também que vocês usam {erp}." if erp else ""
    variacoes = [
        # Ideia do Breno aprovada pelo Rafael: variar entre ligação e conversa por WhatsApp.
        f"{saudacao} Breno aqui da Zydon. Vi que você preencheu nosso formulário para conhecer nossa plataforma de digitalização comercial.{erp_txt}\n\nVocê tem um tempo agora? Posso te ligar rapidinho?",
        f"{saudacao} Breno aqui, da Zydon. Vi seu diagnóstico{empresa_txt} e queria entender melhor o cenário antes de te direcionar.\n\nVocê tem um tempo agora? Posso te ligar rapidinho?",
        f"{saudacao} Breno aqui da Zydon. Recebi seu formulário sobre digitalização comercial B2B e queria tirar 2 dúvidas rápidas para orientar melhor {empresa_contexto}.\n\nVocê tem um tempo agora? Posso te ligar rapidinho?",
        f"{saudacao} Aqui é o Breno, da Zydon. Vi que você deixou seus dados para conhecer a Zydon{empresa_txt}.{erp_txt}\n\nVocê tem um tempo agora? Posso te ligar rapidinho?",
        f"{saudacao} Breno da Zydon por aqui. Chegou pra mim seu cadastro{empresa_txt}; queria entender rapidinho o momento de vocês.\n\nVocê tem um tempo agora? Posso te ligar rapidinho?",
        f"{saudacao} Aqui é o Breno, da Zydon. Recebi o interesse{empresa_txt} e queria só entender qual canal hoje concentra mais os pedidos B2B de vocês.\n\nVocê tem um tempo agora? Posso te ligar rapidinho?",
        f"{saudacao} Breno aqui da Zydon. Estou olhando seu cadastro{empresa_txt} e queria validar se faz sentido falar de portal B2B agora ou mais pra frente.\n\nVocê tem um tempo agora? Posso te ligar rapidinho?",
        f"{saudacao} Breno, da Zydon. Vi o formulário{empresa_txt} e queria te fazer 2 perguntas para não te mandar uma apresentação fora do contexto.\n\nVocê tem um tempo agora? Posso te ligar rapidinho?",
    ]
    return variacoes[var_idx % len(variacoes)]


def montar_msg_sarah(nome, empresa, erp):
    nome_ok = primeiro_nome_valido(nome)
    empresa_ok = empresa_valida(empresa)
    var_idx = escolher_variacao('sarah', nome, empresa, erp, 10)
    saudacao = saudacao_por_variacao(nome_ok, var_idx, 'Oie')
    empresa_txt = f" da {empresa_ok}" if empresa_ok else ""
    empresa_contexto = f"a {empresa_ok}" if empresa_ok else "a empresa"
    erp_txt = f" Vi aqui que vocês usam {erp}, então queria entender como está o fluxo comercial hoje." if erp else ""
    variacoes = [
        f"{saudacao} Sarah aqui, da Zydon. Recebi o cadastro{empresa_txt} e queria entender melhor o cenário antes de te direcionar.{erp_txt}\n\nVocê tem um tempo agora? Posso te ligar rapidinho?",
        f"{saudacao} Aqui é a Sarah, da Zydon. Vi que {empresa_contexto} demonstrou interesse em digitalizar vendas B2B.{erp_txt}\n\nVocê tem um tempo agora? Posso te ligar rapidinho?",
        f"{saudacao} Sarah da Zydon por aqui. Chegou pra mim o cadastro{empresa_txt}; queria entender melhor como vocês vendem hoje.\n\nVocê tem um tempo agora? Posso te ligar rapidinho?",
        f"{saudacao} Aqui é a Sarah, da Zydon. Vi seu interesse em e-commerce B2B e queria entender se hoje os pedidos ainda chegam por WhatsApp, ligação ou vendedor.\n\nVocê tem um tempo agora? Posso te ligar rapidinho?",
        f"{saudacao} Sarah aqui da Zydon. Recebi seu formulário{empresa_txt} e queria tirar 2 dúvidas rápidas para ver se a Zydon encaixa no cenário de vocês.\n\nVocê tem um tempo agora? Posso te ligar rapidinho?",
        f"{saudacao} Sarah, da Zydon. Estou com seu cadastro{empresa_txt} aqui e queria entender se vocês já têm algum canal B2B online ou se ainda centralizam no time comercial.\n\nVocê tem um tempo agora? Posso te ligar rapidinho?",
        f"{saudacao} Aqui é a Sarah da Zydon. Vi que vocês buscaram saber mais sobre digitalização comercial{empresa_txt}.{erp_txt}\n\nVocê tem um tempo agora? Posso te ligar rapidinho?",
        f"{saudacao} Sarah da Zydon por aqui. Antes de te encaminhar um diagnóstico, queria entender uma coisa: hoje o cliente de vocês compra mais por pedido recorrente, catálogo ou contato direto com vendedor?",
        f"{saudacao} Aqui é a Sarah, da Zydon. Recebi seu formulário e queria confirmar se a prioridade aí é organizar pedidos B2B ou abrir um canal de venda online para clientes atuais.\n\nVocê tem um tempo agora? Posso te ligar rapidinho?",
        f"{saudacao} Sarah aqui. Vi seu interesse na Zydon{empresa_txt} e queria entender rapidamente o cenário.\n\nVocê tem um tempo agora? Posso te ligar rapidinho?",
    ]
    return variacoes[var_idx % len(variacoes)]


def montar_msg_lucas(nome, empresa, erp):
    nome_ok = primeiro_nome_valido(nome) or 'tudo bem'
    empresa_ok = empresa_valida(empresa)
    empresa_txt = f" da {empresa_ok}" if empresa_ok else ""
    erp_txt = f" Vi também que vocês usam {erp}." if erp else ""
    var_idx = escolher_variacao('lucas_batista', nome, empresa, erp, 6)
    variacoes = [
        f"Olá {nome_ok}! Tudo bem?\nLucas Batista aqui da Zydon.\n\nVocê solicitou um contato para fazer o *Diagnóstico Comercial B2B*{empresa_txt}.{erp_txt}\n\nQueria confirmar algumas informações. Você tem um tempo agora? Posso te ligar rapidinho?",
        f"Oi, {nome_ok}. Lucas Batista, da Zydon. Recebi o pedido de diagnóstico{empresa_txt} e queria entender rapidinho o cenário comercial de vocês antes de avançar.\n\nVocê tem um tempo agora? Posso te ligar rapidinho?",
        f"{nome_ok}, tudo bem? Lucas Batista aqui. Vi seu cadastro{empresa_txt} para falar sobre digitalização comercial B2B.{erp_txt}\n\nPrefere que eu te chame por aqui ou uma ligação rápida?",
        f"Olá, {nome_ok}. Aqui é o Lucas Batista da Zydon. Chegou para mim sua solicitação de diagnóstico{empresa_txt}.\n\nQueria validar 2 pontos para encaminhar corretamente. Você tem um tempo agora? Posso te ligar rapidinho?",
        f"Oi {nome_ok}, tudo certo? Lucas Batista por aqui, da Zydon. Antes de te mandar qualquer material, queria entender como vocês recebem pedidos B2B hoje.\n\nVocê tem um tempo agora? Posso te ligar rapidinho?",
        f"Bom dia, {nome_ok}. Lucas Batista da Zydon. Estou com o cadastro{empresa_txt} aqui e queria confirmar se o objetivo é organizar pedidos atuais ou abrir um canal B2B online.\n\nVocê tem um tempo agora? Posso te ligar rapidinho?",
    ]
    return variacoes[var_idx % len(variacoes)]


MSG_BUILDERS = {
    'breno': montar_msg_breno,
    'sarah': montar_msg_sarah,
    'lucas': montar_msg_lucas,
}


def send_whatsapp(port, jid, text):
    url = f"http://localhost:{port}/send"
    body = json.dumps({"to": jid, "text": text}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            r = json.loads(resp.read().decode())
            return r.get('success', False), r
    except Exception as e:
        return False, {"error": str(e)}


def escolher_porta_online(bridge, envios):
    """Retorna a porta online menos usada para o SDR.

    Breno usa 4605; Sarah usa 4601. Algumas instâncias Baileys
    ficam com /status stale (connected=false/needsQR=true) logo após o scan,
    enquanto /me já retorna id/nome/phone válidos. Nessa condição, tratar como
    online para NÃO perder a sessão recém-conectada nem excluir o chip da rotação.
    """
    ports = bridge.get('ports') or [bridge['port']]
    def used_count(port):
        return sum(1 for e in envios if isinstance(e, dict) and e.get('bridge_port') == port)
    erros = []
    for port in sorted(ports, key=lambda p: (used_count(p), p)):
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


def envios_porta_periodo(envios, port, seconds=None, same_day=False):
    agora = datetime.now(timezone(timedelta(hours=-3)))
    total = 0
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
        total += 1
    return total


def port_within_external_limits(envios, port, max_per_hour=MAX_EXTERNAL_PER_PORT_HOUR, max_per_day=MAX_EXTERNAL_PER_PORT_DAY):
    hour = envios_porta_periodo(envios, port, seconds=3600)
    day = envios_porta_periodo(envios, port, same_day=True)
    ok = hour < max_per_hour and day < max_per_day
    reason = f'porta {port}: {hour}/{max_per_hour} na última hora, {day}/{max_per_day} hoje'
    return ok, reason


def create_hubspot_task(deal_id, contact_id, owner_id, owner_name, lead_name, tel, bridge_port=None, sender_phone=None, sender_label=None, message_id=None):
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
    if not dry_run_requested and not acquire_global_send_lock(blocking=False):
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
    enviados_keys = envios_phone_set(envios)
    print(f"   {len(envios)} registros de envio carregados (controle compartilhado).")

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
    all_deals = buscar_deals_sem_tarefa(owner_id)
    print(f"   {len(all_deals)} deals nas 5 primeiras etapas.")

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
        recent_diag_hours = diagnostico_recente_hours(envios, phone_key)
        # Se o lead já respondeu depois de uma mensagem nossa/diagnóstico, não mandar
        # follow-up por cima. Move direto para Retorno Contato para o SDR assumir.
        incoming = history_incoming_after_outgoing(phone_key, bridge_ports)
        if incoming:
            try:
                hs_request(
                    f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}",
                    'PATCH',
                    {'properties': {'dealstage': '998099482'}},
                )
                print(f"   ↪️  {dealname}: lead já respondeu após mensagem nossa; movido para Retorno Contato ({len(incoming)} msg).")
            except Exception as e:
                print(f"   ⚠️  {dealname}: resposta detectada, mas falhou mover para Retorno Contato: {e}")
            ja_enviado += 1
            continue

        # Diagnóstico/PDF antigo pode orientar o follow-up, mas nunca deve ser
        # copiado no corpo da mensagem. Histórico solto só bloqueia quando não
        # há diagnóstico contextual para tratar como origem.
        if phone_key in enviados_keys or (history_outgoing_exists(phone_key, bridge_ports) and not diag_context):
            ja_enviado += 1
            # Não mover fase aqui. Rafael: etapa só muda quando o lead receber
            # o primeiro contato/follow-up SDR confirmado, não por diagnóstico
            # nem por evidência histórica solta.
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
            msg = (
                f"{nome_msg}, seguindo o diagnóstico que te mandei, queria entender qual é o principal gargalo hoje nas vendas B2B.\n\n"
                "Você tem um tempo agora? Posso te ligar rapidinho?"
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
        port, status, port_errors = escolher_porta_online(bridge, envios_rotacao)
        if not port:
            print(f"     ❌ Nenhuma porta online no momento. Abortando lote para proteger os chips.")
            for err in port_errors:
                print(f"        - {err}")
            break
        print(f"     🔁 Porta escolhida: {port}")
        sender_phone = ''
        sender_label = owner_name
        try:
            with urllib.request.urlopen(urllib.request.Request(f"http://localhost:{port}/me"), timeout=5) as resp_me:
                me_info = json.loads(resp_me.read().decode())
            sender_phone = str(me_info.get('phone') or me_info.get('id') or '')
            sender_label = str(me_info.get('name') or owner_name)
        except Exception:
            pass

        # Recheca a fonte compartilhada IMEDIATAMENTE antes de enviar. Isso cobre
        # a corrida em que o diagnóstico acabou de registrar o mesmo telefone entre
        # a montagem dos candidatos e este ponto, e também aplica teto global por chip.
        envios_finais = load_envios()
        if normalize_phone(lead['jid']) in envios_phone_set(envios_finais):
            print("     ↪️ Pulado: telefone apareceu no ledger compartilhado antes do envio.")
            enviados_keys.add(normalize_phone(lead['jid']))
            continue
        port_ok, port_reason = port_within_external_limits(envios_finais, port)
        if not port_ok:
            print(f"     🛑 Limite global do chip atingido: {port_reason}. Pulando este envio.")
            continue

        if dry_run:
            print("     🧪 DRY-RUN: não envia WhatsApp, não cria task, não move etapa.")
            enviados += 1
            continue

        ok, resp = send_whatsapp(port, lead['jid'], msg)
        if ok:
            print(f"     ✅ Enviado!")
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
