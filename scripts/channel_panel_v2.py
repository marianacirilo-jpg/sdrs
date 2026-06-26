#!/usr/bin/env python3
"""Mini-channel WhatsApp multi-SDR Zydon — UI V2 (premium).

Mesma lógica de backend de scripts/channel_panel.py (auth por u/t, PORTS, USERS,
read_history, load_all, conversations, messages_for, /health, /api/conversations,
/api/messages, /api/send, /api/media), porém com uma casca visual premium
inspirada em design/channel-v2-mockup.html (Linear/Superhuman + Intercom).

NÃO substitui o painel atual: roda em paralelo (porta default 8791) e consome
exatamente os mesmos dados reais. Não toca em bridges, crons ou watchdog.
"""
from __future__ import annotations
import argparse, base64, binascii, hashlib, hmac, html, http.cookies, json, mimetypes, os, re, secrets, subprocess, threading, time, unicodedata, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PROJECT = Path('/root/.hermes/zydon-prospeccao')
WA_EXTRA = Path('/root/.hermes/whatsapp-extra')
DATA_DIR = WA_EXTRA / 'channel_data'
UPLOADS_DIR = DATA_DIR / 'uploads'
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # CH-018: limite simples de 20MB decodificado
USERS_FILE = PROJECT / 'controle' / 'channel_users.json'
WPP_ENVIOS_FILE = PROJECT / 'controle' / 'wpp_envios.json'
MEDIA_PROXY_PREFIX = '/media/'
GROUP_JID = '120363408131718880@g.us'
# CH-057: conversas iniciadas por chips institucionais/gestores também devem
# aparecer para o SDR dono do lead/deal. Esses são os chips compartilhados que
# podem mandar mensagem em nome de leads dos SDRs.
SHARED_DEAL_VISIBILITY_PORTS = (4600, 4603, 4606, 4607, 4609, 4610)  # Mariana, Lucas, Lucas Resende, Rafael + comunicadores
SHARED_VISIBILITY_CACHE_FILE = PROJECT / 'controle' / 'channel_shared_visibility.json'
SHARED_VISIBILITY_TTL = 30 * 60
SDR_OWNER_UIDS = {'sarah', 'breno', 'lucas_batista'}
HUBSPOT_OWNER_ID_TO_SDR_UID = {
    '86265630': 'breno',
    '88063842': 'sarah',
    '85778446': 'lucas_batista',
}

def hubspot_owner_uid_map():
    """HubSpot ownerId -> uid. Combina defaults + vínculos cadastrados na tela de equipe."""
    out = dict(HUBSPOT_OWNER_ID_TO_SDR_UID)
    try:
        for uid, cfg in USERS.items():
            oid = str(cfg.get('hubspot_owner_id') or cfg.get('hubspotOwnerId') or '').strip()
            if oid:
                out[oid] = uid
    except Exception:
        pass
    return out

def uid_hubspot_owner_id(uid):
    try:
        return str((USERS.get(uid) or {}).get('hubspot_owner_id') or (USERS.get(uid) or {}).get('hubspotOwnerId') or '').strip()
    except Exception:
        return ''
INSTITUTIONAL_PRIVATE_PORTS = {p for p, meta in PORTS.items()} if False else set()  # preenchido após PORTS

DEFAULT_PORTS = {
    4600: {'label':'Mariana', 'owner':'mariana', 'role':'comunicador', 'auth':'auth_single'},
    4601: {'label':'Sarah 1', 'owner':'sarah', 'role':'sdr', 'auth':'auth_4601'},
    4603: {'label':'Lucas Batista', 'owner':'lucas_batista', 'role':'sdr', 'auth':'auth_4603'},
    4605: {'label':'Breno 2', 'owner':'breno', 'role':'sdr', 'auth':'auth_4605_breno2'},
    4606: {'label':'Lucas Resende', 'owner':'lucas_resende', 'role':'comunicador', 'auth':'auth_4606_lucas_institucional'},
    4607: {'label':'Rafael', 'owner':'rafael', 'role':'comunicador', 'auth':'auth_4607_rafael_institucional'},
    4609: {'label':'João Pedro', 'owner':'joao_pedro', 'role':'comunicador', 'auth':'auth_4609_comunicador_2'},
    4610: {'label':'Gustavo', 'owner':'gustavo', 'role':'comunicador', 'auth':'auth_4610_gustavo'},
}
CHANNEL_PORTS_FILE = PROJECT / 'controle' / 'channel_ports.json'


def _slug_uid(v):
    s = str(v or '').strip().lower()
    s = unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z0-9_]+', '_', s).strip('_')


def load_ports_config():
    CHANNEL_PORTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if CHANNEL_PORTS_FILE.exists():
        try:
            raw = json.loads(CHANNEL_PORTS_FILE.read_text(encoding='utf-8'))
            if isinstance(raw, dict):
                data = raw
        except Exception:
            data = {}
    changed = False
    for p, meta in DEFAULT_PORTS.items():
        if str(p) not in data:
            data[str(p)] = meta; changed = True
        else:
            for k, v in meta.items():
                if k not in data[str(p)]: data[str(p)][k] = v; changed = True
    out = {}
    for k, meta in data.items():
        try: port = int(k)
        except Exception: continue
        if port < 1024 or port > 65535 or not isinstance(meta, dict):
            continue
        label = str(meta.get('label') or f'Chip {port}').strip()[:80]
        owner = _slug_uid(meta.get('owner') or label)
        role = str(meta.get('role') or 'comunicador').strip().lower()
        if role not in {'sdr','comunicador','institucional'}:
            role = 'comunicador'
        auth = str(meta.get('auth') or f'auth_{port}_{owner}').strip()
        out[port] = {'label': label, 'owner': owner, 'role': role, 'auth': auth}
    if changed or not CHANNEL_PORTS_FILE.exists():
        save_ports_config(out)
    return out


def save_ports_config(ports):
    CHANNEL_PORTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {str(int(p)): dict(meta) for p, meta in sorted(ports.items())}
    tmp = CHANNEL_PORTS_FILE.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    try: os.chmod(tmp, 0o600)
    except Exception: pass
    tmp.replace(CHANNEL_PORTS_FILE)
    try: os.chmod(CHANNEL_PORTS_FILE, 0o600)
    except Exception: pass


def next_free_port(preferred=4611):
    used = set(int(p) for p in PORTS.keys())
    try:
        # também considera processos node vivos para não colidir fora do config
        out = subprocess.run(['bash','-lc', "ps -eo args | sed -n 's/.*single-extra.js --port \([0-9][0-9]*\).*/\1/p'"], capture_output=True, text=True, timeout=4)
        for line in out.stdout.splitlines():
            if line.strip().isdigit(): used.add(int(line.strip()))
    except Exception:
        pass
    p = int(preferred)
    while p in used or p < 1024 or p > 65535:
        p += 1
    return p

def bridge_process_running(port):
    try:
        out=subprocess.run(['bash','-lc', f"ps -eo pid,args | awk '/node single-extra\\.js --port {int(port)}/ && !/awk/ {{print $1}}'"], capture_output=True, text=True, timeout=4)
        return bool(out.stdout.strip())
    except Exception:
        return False

def start_bridge_process(port, auth):
    port=int(port); auth=str(auth or f'auth_{port}').strip()
    if bridge_process_running(port):
        return {'started':False,'alreadyRunning':True}
    WA_EXTRA.mkdir(parents=True, exist_ok=True)
    log_dir = PROJECT / 'logs'; log_dir.mkdir(parents=True, exist_ok=True)
    log = open(log_dir / f'channel_bridge_{port}.log', 'ab', buffering=0)
    env=os.environ.copy(); env.pop('WA_VERSION_OVERRIDE', None)
    subprocess.Popen(['node','single-extra.js','--port',str(port),'--auth',auth], cwd=str(WA_EXTRA), stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
    return {'started':True,'alreadyRunning':False}

def stop_bridge_process(port):
    try:
        subprocess.run(['bash','-lc', f"pkill -f 'node single-extra\\.js --port {int(port)}' || true"], timeout=8)
        time.sleep(0.4)
        return {'stopped': not bridge_process_running(port)}
    except Exception as e:
        return {'stopped': False, 'error': str(e)}

def admin_port_payload():
    return [{'port':p, **cfg} for p,cfg in sorted(PORTS.items())]

def validate_port_payload(body):
    label=str(body.get('label') or '').strip()
    if not label or len(label)>80:
        raise ValueError('nome do chip/comunicador obrigatório')
    role=str(body.get('role') or 'comunicador').strip().lower()
    if role not in {'sdr','comunicador','institucional'}:
        raise ValueError('tipo deve ser sdr ou comunicador')
    owner=_slug_uid(body.get('owner') or label)
    if not owner:
        raise ValueError('owner inválido')
    port_raw=body.get('port')
    if port_raw in (None,'','auto'):
        port=next_free_port()
    else:
        port=int(port_raw)
        if port < 1024 or port > 65535:
            raise ValueError('porta inválida')
    auth=str(body.get('auth') or f'auth_{port}_{owner}').strip()
    if '/' in auth or '..' in auth or not re.match(r'^[A-Za-z0-9_.-]+$', auth):
        raise ValueError('auth dir inválido')
    return port, {'label':label,'owner':owner,'role':role,'auth':auth}


PORTS = load_ports_config()
INSTITUTIONAL_PRIVATE_PORTS = {p for p, meta in PORTS.items() if meta.get('role') in {'institucional','comunicador'}}

def is_institutional_port(port):
    return int(port or 0) in INSTITUTIONAL_PRIVATE_PORTS

def is_institutional_dispatch_msg(m):
    """Só eventos operacionais enviados por chips pessoais/institucionais.

    Conversas privadas da Mariana/Rafael/Lucas Resende nunca entram. Entram apenas
    registros de automação/envio para lead/negócio de SDR, com metadado de sdr/empresa/email.
    """
    if not isinstance(m, dict) or not m.get('fromMe'):
        return False
    typ = str(m.get('type') or '')
    has_meta = bool(m.get('sdr') or m.get('empresa') or m.get('lead') or m.get('email') or m.get('slug') or m.get('owner_id') or m.get('hubspot_owner_id') or m.get('deal_id') or m.get('deal_ids') or m.get('contact_id'))
    if typ.startswith('cron-') or typ in ('seed-wpp-envios', 'api-send'):
        return has_meta
    src = str(m.get('source') or '')
    if 'wpp_envios' in src or 'controle/' in src:
        return has_meta
    return False

def institutional_dispatch_owner_uid_from_msgs(msgs):
    for m in msgs:
        uid = _conversation_sdr_hint_from_msg(m)
        if uid in SDR_OWNER_UIDS:
            return uid
    return ''

DEFAULT_USERS = {
    'rafael': {'name':'Rafael', 'ports':[4600,4601,4603,4605,4606,4607,4609,4610], 'admin': True, 'view_all': True, 'role':'supervisor'},
    'mariana': {'name':'Mariana', 'ports':[4600], 'admin': False, 'view_all': True, 'role':'comunicador'},
    'breno': {'name':'Breno', 'ports':[4605], 'admin': False, 'role':'sdr', 'hubspot_owner_id':'86265630'},
    'sarah': {'name':'Sarah', 'ports':[4601], 'admin': False, 'role':'sdr', 'hubspot_owner_id':'88063842'},
    'lucas_batista': {'name':'Lucas Batista', 'ports':[4603], 'admin': False, 'role':'sdr', 'hubspot_owner_id':'85778446'},
    'lucas_resende': {'name':'Lucas Resende', 'ports':[4606], 'admin': False, 'view_all': True, 'role':'comunicador'},
    'gustavo': {'name':'Gustavo', 'ports':[4610], 'admin': False, 'role':'comunicador'},
    'joao_pedro': {'name':'João Pedro', 'ports':[4609], 'admin': False, 'role':'comunicador'},
}

def ensure_users():
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if USERS_FILE.exists():
        data = json.loads(USERS_FILE.read_text(encoding='utf-8'))
    else:
        data = {}
    changed=False
    for uid, cfg in DEFAULT_USERS.items():
        if uid not in data:
            data[uid] = {**cfg, 'token': secrets.token_urlsafe(18)}; changed=True
        else:
            for k,v in cfg.items():
                if k not in data[uid]: data[uid][k]=v; changed=True
            if not data[uid].get('token'):
                data[uid]['token']=secrets.token_urlsafe(18); changed=True
    if changed:
        USERS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        try: os.chmod(USERS_FILE, 0o600)
        except Exception: pass
    return data

USERS = ensure_users()

def save_users(data):
    """Grava channel_users.json com permissões restritas. Não altera tokens existentes."""
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = USERS_FILE.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    try: os.chmod(tmp, 0o600)
    except Exception: pass
    tmp.replace(USERS_FILE)
    try: os.chmod(USERS_FILE, 0o600)
    except Exception: pass

def user_can_view_all(uid):
    """Perfis supervisores veem todas as conversas/chips sem virar admin técnico."""
    return bool(USERS.get(uid, {}).get('admin') or USERS.get(uid, {}).get('view_all'))

def effective_ports(uid):
    if user_can_view_all(uid):
        return sorted(PORTS.keys())
    return [int(p) for p in USERS.get(uid, {}).get('ports', []) if int(p) in PORTS]

def sanitize_user_record(uid, cfg):
    """Versão pública/admin sem token; usada pela UI."""
    ports = sorted(PORTS.keys()) if bool(cfg.get('admin') or cfg.get('view_all')) else [int(p) for p in (cfg.get('ports') or []) if int(p) in PORTS]
    return {
        'id': uid,
        'name': str(cfg.get('name') or uid),
        'ports': ports,
        'admin': bool(cfg.get('admin')),
        'view_all': bool(cfg.get('view_all')),
        'emails': [str(e).lower() for e in (cfg.get('emails') or []) if str(e).strip()],
        'role': str(cfg.get('role') or ('sdr' if any((PORTS.get(int(pp),{}).get('role')=='sdr') for pp in (cfg.get('ports') or []) if str(pp).isdigit()) else 'comunicador')),
        'hubspotOwnerId': str(cfg.get('hubspot_owner_id') or cfg.get('hubspotOwnerId') or ''),
    }

def users_public():
    return [sanitize_user_record(uid, cfg) for uid, cfg in sorted(USERS.items(), key=lambda kv: kv[0])]

def validate_admin_user_payload(body):
    uid = re.sub(r'[^a-z0-9_]+', '_', str(body.get('id') or '').strip().lower()).strip('_')
    if not uid or len(uid) > 48:
        raise ValueError('id inválido')
    name = str(body.get('name') or uid).strip()[:80]
    if not name:
        raise ValueError('nome inválido')
    ports = []
    for p in body.get('ports') or []:
        try: pi = int(p)
        except Exception: continue
        if pi not in PORTS:
            raise ValueError(f'chip/porta inválido: {p}')
        if pi not in ports:
            ports.append(pi)
    admin = bool(body.get('admin'))
    emails = []
    for e in body.get('emails') or []:
        e = str(e or '').strip().lower()
        if not e:
            continue
        if '@' not in e:
            e = e + '@zydon.com.br'
        local, domain = e.rsplit('@', 1)
        if domain not in ALLOWED_EMAIL_DOMAINS or not re.match(r'^[a-z0-9._%+\-]+$', local):
            raise ValueError(f'email não permitido: {e}')
        if e not in emails:
            emails.append(e)
    role = str(body.get('role') or '').strip().lower()
    if role not in {'sdr','comunicador','supervisor'}:
        role = 'sdr' if any((PORTS.get(int(pp),{}).get('role')=='sdr') for pp in ports if int(pp) in PORTS) else 'comunicador'
    hubspot_owner_id = re.sub(r'\D+', '', str(body.get('hubspotOwnerId') or body.get('hubspot_owner_id') or ''))[:32]
    rec = {'name': name, 'ports': ports, 'admin': admin, 'emails': emails, 'role': role}
    if hubspot_owner_id:
        rec['hubspot_owner_id'] = hubspot_owner_id
    return uid, rec

# ---- CH-010: estado local por conversa (status + nota interna) --------------
# Estado de triagem do SDR que NÃO existe no WhatsApp nem no HubSpot: se a
# conversa está em aberto/pendente/resolvida e uma nota interna do time. Mora
# num único JSON local (controle/channel_state.json), escrito de forma atômica
# (tmp + os.replace) e protegido por um lock de processo, já que o servidor é
# multithread. Nunca toca em bridges/HubSpot/envio: é puramente local.
CHANNEL_STATE_FILE = PROJECT / 'controle' / 'channel_state.json'
# CH-052: cache local de transcrições de áudio recebidos. O áudio continua no
# disco da bridge; aqui salvamos só texto/metadados para busca/filas do Channel.
CHANNEL_TRANSCRIPTS_FILE = PROJECT / 'controle' / 'channel_audio_transcripts.json'
HERMES_PY = '/usr/local/lib/hermes-agent/venv/bin/python'
VALID_STATUSES = ('open', 'pending', 'resolved', 'archived')
APP_ROUTES = {'/': 'conversas', '/index.html': 'conversas', '/conversas': 'conversas', '/foco': 'foco', '/gestao': 'gestao'}
NOTE_PREVIEW_LEN = 160
CONVERSATIONS_API_CACHE = {}
CONVERSATIONS_API_LOCK = threading.Lock()
CONVERSATIONS_REFRESHING = set()
CONVERSATIONS_API_TTL = 60
MESSAGES_API_CACHE = {}
MESSAGES_API_LOCK = threading.Lock()
MESSAGES_REFRESHING = set()
MESSAGES_API_TTL = 15
DISPATCH_ROWS_CACHE = {}
DISPATCH_ROWS_TTL = 30
CHIPS_API_CACHE = {}
CHIPS_API_TTL = 20
CONVERSATION_PERMISSION_CACHE = {}
CONVERSATION_PERMISSION_TTL = 30
def invalidate_channel_api_cache(uid=None, conv_id=None):
    """Invalida caches curtos após escrita para evitar timeline/lista obsoletas."""
    try:
        if conv_id:
            keys=[k for k in list(MESSAGES_API_CACHE.keys()) if len(k) == 2 and k[1] == conv_id]
            for k in keys:
                MESSAGES_API_CACHE.pop(k, None)
                CONVERSATION_PERMISSION_CACHE.pop(k, None)
            try:
                p_s, ch = conv_id.split('::',1)
                DISPATCH_ROWS_CACHE.pop((int(p_s), canonical_chat_id(ch)), None)
            except Exception:
                pass
        elif uid:
            keys=[k for k in list(MESSAGES_API_CACHE.keys()) if len(k) == 2 and k[0] == uid]
            for k in keys:
                MESSAGES_API_CACHE.pop(k, None)
                CONVERSATION_PERMISSION_CACHE.pop(k, None)
        else:
            MESSAGES_API_CACHE.clear()
            CONVERSATION_PERMISSION_CACHE.clear()
            DISPATCH_ROWS_CACHE.clear()
    except Exception:
        pass
    try:
        # Não apaga a lista inteira em escrita operacional: várias abas abertas
        # recomputavam /api/conversations ao mesmo tempo e bloqueavam /api/messages.
        # Marca como stale; o endpoint devolve cache rápido e recalcula em background.
        targets=[]
        if uid:
            targets.append(uid)
            if user_can_view_all(uid): targets.append('__view_all__')
        else:
            targets=list(CONVERSATIONS_API_CACHE.keys())
        for k in targets:
            if k in CONVERSATIONS_API_CACHE:
                CONVERSATIONS_API_CACHE[k]['ts']=0
    except Exception:
        pass

_state_lock = threading.Lock()

def valid_status(s):
    return s in VALID_STATUSES

def load_channel_state():
    """Lê o JSON de estado local. Sempre devolve dict (nunca levanta)."""
    try:
        if CHANNEL_STATE_FILE.exists():
            data = json.loads(CHANNEL_STATE_FILE.read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}

def save_channel_state(state):
    """Persiste o estado com escrita atômica (tmp no mesmo dir + os.replace)."""
    CHANNEL_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CHANNEL_STATE_FILE.parent / (CHANNEL_STATE_FILE.name + '.tmp.' + secrets.token_hex(4))
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        os.replace(tmp, CHANNEL_STATE_FILE)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
    try:
        os.chmod(CHANNEL_STATE_FILE, 0o600)
    except Exception:
        pass

def state_for_conversation(conv_id):
    """Estado local de uma conversa (dict vazio se não houver nada salvo)."""
    entry = load_channel_state().get(conv_id)
    return entry if isinstance(entry, dict) else {}

def update_conversation_state(conv_id, uid, status=None, note=None):
    """Aplica status e/ou nota interna a uma conversa, atômico e thread-safe.

    Devolve o estado resultante da conversa. `status` deve ser validado pelo
    chamador (valid_status). `note` é texto livre; guarda autor e timestamp.
    """
    with _state_lock:
        st = load_channel_state()
        entry = st.get(conv_id)
        if not isinstance(entry, dict):
            entry = {}
        now = time.time()
        if status is not None:
            status = str(status)
            entry['status'] = status
            if status == 'resolved':
                entry['resolved_by'] = uid
                entry['resolved_at'] = now
            elif status == 'pending':
                entry['pending_by'] = uid
                entry['pending_at'] = now
            elif status == 'archived':
                entry['archived_by'] = uid
                entry['archived_at'] = now
            elif status == 'open':
                entry['reopened_by'] = uid
                entry['reopened_at'] = now
        if note is not None:
            entry['note'] = str(note)
            entry['note_author'] = uid
            entry['note_at'] = now
        entry['updated_at'] = now
        st[conv_id] = entry
        save_channel_state(st)
        return entry

def local_state_summary(entry):
    """Resumo seguro do estado local para enriquecer respostas da API."""
    entry = entry if isinstance(entry, dict) else {}
    note = str(entry.get('note') or '')
    return {
        'localStatus': entry.get('status') or 'open',
        'localNote': note[:NOTE_PREVIEW_LEN],
        'localNoteAuthor': entry.get('note_author') or '',
        'localUpdatedAt': entry.get('updated_at') or 0,
    }

# ---- CH-022: autenticação real (Cloudflare Access + Google OAuth) -----------
# O acesso público NÃO depende mais de token na URL. A identidade vem, nesta
# ordem: (1) header do Cloudflare Access, (2) cookie de sessão assinado emitido
# após login Google, (3) — só em dev e só se explicitamente habilitado — o antigo
# token u/t na querystring. Sem libs externas: tudo com stdlib.
GOOGLE_OAUTH_ENV = Path('/root/.hermes/credentials/google_oauth.env')
SESSION_SECRET_FILE = PROJECT / 'controle' / 'channel_session_secret.txt'
SESSION_COOKIE = 'zydon_session'
OAUTH_STATE_COOKIE = 'zydon_oauth_state'
SESSION_TTL = 7 * 24 * 3600  # 7 dias: evita relogin durante expediente
OAUTH_STATE_TTL = 3600       # 1h para concluir o login Google sem corrida/pressa

# Domínio corporativo aceito para Google/Cloudflare Access/admin UI.
# Regra Rafael 24/06: login restrito APENAS ao domínio Google Workspace da Zydon.
# Qualquer outro domínio é 403, inclusive gmail/outlook e variantes não listadas.
ALLOWED_EMAIL_DOMAINS = ('zydon.com.br',)

# localpart do e-mail (e aliases comuns) -> uid/chips em USERS. Rafael é admin.
# Inclui variantes comuns (nome.sobrenome, nomesobrenome, sobrenome) para que o
# login OAuth continue funcionando mesmo quando o Google Workspace usa um
# localpart diferente do uid (ex.: rafael.calixto@zydon.com.br -> rafael).
EMAIL_TO_UID = {
    'rafael': 'rafael', 'rafael.calixto': 'rafael', 'rafaelcalixto': 'rafael', 'calixto': 'rafael',
    'mariana': 'mariana', 'mariana.silva': 'mariana', 'marianasilva': 'mariana',
    'breno': 'breno',
    'sarah': 'sarah',
    'lucas_batista': 'lucas_batista', 'lucas.batista': 'lucas_batista', 'lucasbatista': 'lucas_batista', 'batista': 'lucas_batista',
    'lucas_resende': 'lucas_resende', 'lucas.resende': 'lucas_resende', 'lucasresende': 'lucas_resende', 'resende': 'lucas_resende',
}

def _parse_env_file(path):
    """Lê um arquivo KEY=value simples (ignora comentários/linhas vazias)."""
    out = {}
    try:
        if path.exists():
            for line in path.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return out

def google_config():
    """Config Google/OAuth via env do processo OU credentials/google_oauth.env."""
    filecfg = _parse_env_file(GOOGLE_OAUTH_ENV)
    def get(k, default=''):
        v = os.environ.get(k)
        if v is None or v == '':
            v = filecfg.get(k, default)
        return (v or '').strip()
    allow_raw = get('CHANNEL_ALLOW_TOKEN_AUTH', '')
    return {
        'client_id': get('GOOGLE_CLIENT_ID'),
        'client_secret': get('GOOGLE_CLIENT_SECRET'),
        'redirect_uri': get('GOOGLE_REDIRECT_URI'),
        'public_base_url': get('CHANNEL_PUBLIC_BASE_URL'),
        'allow_token_auth': allow_raw.lower() in ('1', 'true', 'yes', 'on'),
    }

def _oauth_value_ready(v):
    """True só para credencial real; evita ativar OAuth com placeholder copiado."""
    s = str(v or '').strip()
    if not s:
        return False
    bad = ('COLE_AQUI', 'TODO', '...', 'YOUR_', 'CLIENT_ID', 'CLIENT_SECRET', '<', '>')
    return not any(x in s.upper() for x in bad)


def google_configured():
    cfg = google_config()
    return bool(_oauth_value_ready(cfg['client_id']) and _oauth_value_ready(cfg['client_secret']))

def _session_secret():
    """Segredo HMAC persistente (controle/channel_session_secret.txt, chmod 600)."""
    try:
        if SESSION_SECRET_FILE.exists():
            s = SESSION_SECRET_FILE.read_text(encoding='utf-8').strip()
            if s:
                return s.encode('utf-8')
    except Exception:
        pass
    secret = secrets.token_urlsafe(48)
    try:
        SESSION_SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
        SESSION_SECRET_FILE.write_text(secret, encoding='utf-8')
        os.chmod(SESSION_SECRET_FILE, 0o600)
    except Exception:
        pass
    return secret.encode('utf-8')

SESSION_SECRET = _session_secret()

def _b64u(b):
    return base64.urlsafe_b64encode(b).decode('ascii').rstrip('=')

def _b64u_dec(s):
    pad = '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)

def uid_from_email(email):
    """Mapeia um e-mail corporativo aceito para um uid de USERS. None se inválido.

    Estratégia (segura — só aceita @zydon.com.br):
      1) mapeamento explícito salvo pelo admin (cfg['emails']);
      2) aliases conhecidos em EMAIL_TO_UID ou localpart == uid;
      3) fuzzy fallback: o localpart contém o token de nome de algum uid
         (ex.: "rafael.calixto" contem "rafael" -> rafael). Só roda quando o
         domínio já foi validado contra ALLOWED_EMAIL_DOMAINS, então continua
         bloqueando @gmail.com / @outlook.com / @zydon.com etc.
    """
    email = str(email or '').strip().lower()
    if '@' not in email:
        return None
    local, domain = email.rsplit('@', 1)
    if domain not in ALLOWED_EMAIL_DOMAINS:
        return None
    local = local.split('+', 1)[0]  # ignora "+alias" (plus addressing)
    # normaliza separadores comuns (rafael.calixto, rafael_calixto, rafael-calixto)
    normalized = local + '@' + domain
    # 1) mapeamento explícito salvo pelo admin na UI.
    for uid, cfg in USERS.items():
        emails = [str(e).strip().lower() for e in (cfg.get('emails') or [])]
        if normalized in emails:
            return uid
    # 2) aliases legados/conhecidos ou uid igual ao localpart.
    uid = EMAIL_TO_UID.get(local) or (local if local in USERS else None)
    if uid in USERS:
        return uid
    # 3) fuzzy fallback por token de nome dentro do localpart.
    # Ex.: rafael.calixto@zydon.com.br -> "rafael.calixto" contem "rafael" -> rafael.
    tokens = [t for t in re.split(r'[._\-]+', local) if t]
    for _uid in USERS:
        # first name / token do uid (ex.: "lucas_batista" -> ["lucas","batista"])
        name = str(USERS[_uid].get('name') or '').strip().lower()
        uid_tokens = set(_uid.split('_')) | set(re.split(r'\s+', name))
        uid_tokens = {t for t in uid_tokens if len(t) >= 3}
        # match: algum token do uid aparece como token EXATO no localpart.
        for tok in tokens:
            if tok in uid_tokens:
                return _uid
    return None

def make_session(uid, ttl=SESSION_TTL):
    """Cria valor de cookie de sessão assinado: b64(uid).exp.b64(hmac)."""
    exp = str(int(time.time() + ttl))
    msg = (uid + '|' + exp).encode('utf-8')
    sig = hmac.new(SESSION_SECRET, msg, hashlib.sha256).digest()
    return _b64u(uid.encode('utf-8')) + '.' + exp + '.' + _b64u(sig)

def verify_session(value):
    """Valida o cookie de sessão. Devolve uid válido ou None."""
    try:
        parts = str(value or '').split('.')
        if len(parts) != 3:
            return None
        uid = _b64u_dec(parts[0]).decode('utf-8')
        exp = parts[1]
        sig = _b64u_dec(parts[2])
        expected = hmac.new(SESSION_SECRET, (uid + '|' + exp).encode('utf-8'), hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return None
        if int(exp) < time.time():
            return None
        return uid if uid in USERS else None
    except Exception:
        return None

def make_state():
    """State OAuth assinado (nonce.ts.sig) para mitigar CSRF no callback."""
    nonce = secrets.token_urlsafe(16)
    ts = str(int(time.time()))
    sig = hmac.new(SESSION_SECRET, (nonce + '|' + ts).encode('utf-8'), hashlib.sha256).hexdigest()[:32]
    return nonce + '.' + ts + '.' + sig

def verify_state(value, max_age=OAUTH_STATE_TTL):
    try:
        nonce, ts, sig = str(value or '').split('.')
        expected = hmac.new(SESSION_SECRET, (nonce + '|' + ts).encode('utf-8'), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):
            return False
        return int(ts) >= time.time() - max_age
    except Exception:
        return False

def user_from_token(path):
    """Auth legada por querystring u/t. Só usada em dev quando habilitada."""
    qs = parse_qs(urlparse(path).query)
    uid = (qs.get('u') or qs.get('user') or [''])[0]
    tok = (qs.get('t') or qs.get('token') or [''])[0]
    if not uid or uid not in USERS:
        return None
    if not tok or not secrets.compare_digest(tok, USERS[uid].get('token', '')):
        return None
    return uid

def _cf_access_email(handler):
    """E-mail autenticado pelo Cloudflare Access (header case-insensitive)."""
    for h in ('Cf-Access-Authenticated-User-Email', 'CF-Access-Authenticated-User-Email'):
        v = handler.headers.get(h)
        if v:
            return v.strip()
    return ''

def _request_cookies(handler):
    jar = http.cookies.SimpleCookie()
    raw = handler.headers.get('Cookie')
    if raw:
        try:
            jar.load(raw)
        except Exception:
            pass
    return jar

def identity_from_request(handler):
    """Identidade do request, na ordem: Cloudflare Access > sessão Google > token dev."""
    # 1) Cloudflare Access
    email = _cf_access_email(handler)
    if email:
        uid = uid_from_email(email)
        if uid:
            return uid
    # 2) cookie de sessão Google
    jar = _request_cookies(handler)
    if SESSION_COOKIE in jar:
        uid = verify_session(jar[SESSION_COOKIE].value)
        if uid:
            return uid
    # 3) token u/t — NUNCA em produção por padrão; só se explicitamente habilitado
    if google_config()['allow_token_auth']:
        uid = user_from_token(handler.path)
        if uid:
            return uid
    return None

def request_is_https(handler):
    """https? via X-Forwarded-Proto, esquema do public base url, ou header."""
    xfp = (handler.headers.get('X-Forwarded-Proto') or '').lower()
    if 'https' in xfp:
        return True
    if google_config()['public_base_url'].lower().startswith('https://'):
        return True
    return False

def build_cookie(name, value, max_age, secure, http_only=True, same_site=None, path='/'):
    """Monta um header Set-Cookie. max_age=0 expira o cookie imediatamente.

    SameSite default: 'Lax' para a maioria dos cookies. O caller pode passar
    same_site='None' explicitamente para cookies que precisam sobreviver a um
    redirect cross-site (ex.: OAUTH_STATE_COOKIE durante o fluxo Google OAuth).

    Regra de SameSite=None: navegadores modernos REJEITAM SameSite=None sem
    Secure. Quando same_site='None' é pedido mas secure=False, cai para 'Lax'
    (seguro e funcional em dev localhost).
    """
    if same_site is None:
        same_site = 'Lax'
    if same_site == 'None' and not secure:
        same_site = 'Lax'  # None sem Secure é rejeitado; Lax é seguro e funciona
    parts = [f'{name}={value}', f'Path={path}', f'Max-Age={int(max_age)}', f'SameSite={same_site}']
    if http_only:
        parts.append('HttpOnly')
    if secure:
        parts.append('Secure')
    return '; '.join(parts)

def oauth_redirect_uri(handler, cfg):
    """URI de callback: GOOGLE_REDIRECT_URI > public base url > Host do request."""
    if cfg['redirect_uri']:
        return cfg['redirect_uri']
    base = cfg['public_base_url'].rstrip('/')
    if base:
        return base + '/oauth/callback'
    host = handler.headers.get('Host', '127.0.0.1')
    scheme = 'https' if request_is_https(handler) else 'http'
    return f'{scheme}://{host}/oauth/callback'

def _google_exchange_code(code, redirect_uri, cfg):
    data = urllib.parse.urlencode({
        'code': code,
        'client_id': cfg['client_id'],
        'client_secret': cfg['client_secret'],
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }).encode('utf-8')
    req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data,
                                 headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8') or '{}')

def _google_userinfo(access_token):
    req = urllib.request.Request('https://openidconnect.googleapis.com/v1/userinfo',
                                 headers={'Authorization': 'Bearer ' + access_token})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8') or '{}')

def _auth_shell(title, body):
    return ('<!doctype html><html lang="pt-br" data-theme="light"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>' + html.escape(title) + '</title><style>'
            'body{margin:0;background:#F6F7F2;color:#162017;font-family:Inter,system-ui,-apple-system,sans-serif;display:grid;place-items:center;min-height:100vh;padding:22px;box-sizing:border-box}'
            '.card{width:min(100%,480px);text-align:center;padding:30px 28px;border:1px solid rgba(20,28,20,.11);border-radius:20px;background:#FFFFFF;box-shadow:0 18px 60px rgba(11,15,12,.10)}'
            '.login-logo{width:132px;height:auto;margin:0 auto 18px;display:block}.card h1{font-size:17px;margin:0 0 6px;color:#162017}.card p{font-size:13px;color:#526057;line-height:1.5}'
            '.btn{display:inline-flex;align-items:center;justify-content:center;gap:9px;margin-top:18px;background:#0B0F0C;color:#CDEB00;font-weight:750;'
            'text-decoration:none;padding:12px 18px;border-radius:12px;font-size:14px;border:1px solid rgba(205,235,0,.55);box-shadow:0 10px 28px rgba(11,15,12,.22)}.btn:active{transform:translateY(1px)}'
            '.muted{font-size:12px;color:#7A857E;margin-top:14px}'
            'code{background:#F3F5ED;border:1px solid rgba(20,28,20,.11);border-radius:6px;padding:1px 6px;font-size:12px;color:#162017}'
            'ul{text-align:left;font-size:12.5px;color:#5B665F;display:inline-block;margin:10px auto 0}'
            '</style></head><body><div class="card">' + body + '</div></body></html>')

def login_page_html(cfg):
    """Tela de login. Mostra botão Google se configurado; senão, o que falta."""
    if google_configured():
        body = ('<img class="login-logo" src="/logo.png" alt="Zydon">'
                '<h1>Inbox comercial</h1>'
                '<p>Faça login com sua conta <b>@zydon.com.br</b> para acessar o inbox comercial.</p>'
                '<a class="btn" href="/login?go=1">Entrar com Google</a>'
                '<p class="muted">Acesso restrito a contas corporativas Zydon.</p>')
        return _auth_shell('Entrar · Zydon', body)
    missing = []
    if not cfg['client_id']:
        missing.append('GOOGLE_CLIENT_ID')
    if not cfg['client_secret']:
        missing.append('GOOGLE_CLIENT_SECRET')
    items = ''.join('<li><code>' + html.escape(m) + '</code></li>' for m in missing)
    body = ('<h1>Login Google ainda não configurado</h1>'
            '<p>O login com Google não está ativo porque faltam credenciais. '
            'Defina as variáveis abaixo no ambiente ou em '
            '<code>/root/.hermes/credentials/google_oauth.env</code>:</p>'
            '<ul>' + items + '</ul>'
            '<p class="muted">Opcionais: <code>GOOGLE_REDIRECT_URI</code>, '
            '<code>CHANNEL_PUBLIC_BASE_URL</code>. Após configurar, recarregue esta página.</p>')
    return _auth_shell('Login pendente · Zydon', body)

def denied_page_html(reason):
    body = ('<h1>Acesso negado</h1><p>' + html.escape(reason) + '</p>'
            '<a class="btn" href="/login">Tentar novamente</a>')
    return _auth_shell('Acesso negado · Zydon', body)

def _event_message_id(m):
    for key in ('messageId','id'):
        v=str((m or {}).get(key) or '').strip()
        if v and not v.startswith('wpp_'):
            return v
    sr=(m or {}).get('send_response') or (m or {}).get('bridge') or {}
    if isinstance(sr, dict):
        v=str(sr.get('messageId') or sr.get('id') or '').strip()
        if v:
            return v
    return ''

def _same_dispatch_payload(a, b):
    aid=_event_message_id(a); bid=_event_message_id(b)
    if aid and bid and aid == bid:
        return True
    at=' '.join(str((a or {}).get('text') or '').split()).strip()
    bt=' '.join(str((b or {}).get('text') or '').split()).strip()
    if at and bt and at == bt:
        return True
    am=str((a or {}).get('mediaName') or '').strip().lower()
    bm=str((b or {}).get('mediaName') or '').strip().lower()
    return bool(am and bm and am == bm)

def merge_institutional_ledger_with_real_messages(port, data):
    """Para chips institucionais, usa a hora REAL da bridge e metadados do ledger.

    O ledger `wpp_envios.json` pode registrar o mesmo envio com +3h/horário do
    processamento. A bridge também captura a bolha real (`append`) com o id e
    timestamp certos. Fundimos os dois para evitar “agora” falso e manter owner/empresa.
    """
    if not is_institutional_port(port) or not isinstance(data, list):
        return data if isinstance(data, list) else []
    out=[]; consumed_events=set()
    events=[(i,m) for i,m in enumerate(data) if isinstance(m,dict) and is_institutional_dispatch_msg(m)]
    # Além de eventos já presentes no history, injeta o ledger de envios para saber
    # quais chats do comunicador são operacionais. Assim respostas do lead nesses
    # chats aparecem no painel central sem expor conversas pessoais do chip.
    try:
        ledger_events=[m for m in wpp_envios_fastlane_events([int(port)], max_age_hours=24*14) if isinstance(m,dict) and is_institutional_dispatch_msg(m)]
        base=len(events)
        events.extend((base+i,m) for i,m in enumerate(ledger_events))
    except Exception:
        pass
    event_by_chat={}
    for _,ev in events:
        ck=canonical_chat_for_message(ev)
        if ck:
            prev=event_by_chat.get(ck)
            if not prev or float(ev.get('timestamp') or 0) >= float(prev.get('timestamp') or 0):
                event_by_chat[ck]=ev
    for i,m in enumerate(data):
        if not isinstance(m, dict):
            continue
        if is_institutional_dispatch_msg(m):
            # será mantido apenas se não houver bolha real correspondente
            continue
        if not (m.get('fromMe') and str(m.get('type') or '') in ('append','notify','message','')):
            # Privacidade: só permite resposta recebida se o chat já teve envio
            # operacional registrado no ledger/painel. Conversas pessoais seguem ocultas.
            if (not m.get('fromMe')) and canonical_chat_for_message(m) in event_by_chat:
                ev=event_by_chat.get(canonical_chat_for_message(m)) or {}
                mm=dict(m)
                for k,v in ev.items():
                    if k in ('timestamp','timestampRaw','date','id','messageId','text','mediaUrl','mediaName','mediaType','mimetype','mediaPath','fromMe','type'):
                        continue
                    if v not in (None,'') and not mm.get(k):
                        mm[k]=v
                mm['fromMe']=False
                _enrich_dispatch_identity(mm)
                mm['source']='bridge+controle/wpp_envios.json:reply'
                mm['readOnlyInstitutionalReply']=True
                out.append(mm)
            continue
        best=None; best_diff=10**9
        mt=float(m.get('timestamp') or 0)
        for ei,ev in events:
            if ei in consumed_events:
                continue
            if canonical_chat_for_message(ev) != canonical_chat_for_message(m):
                continue
            if not _same_dispatch_payload(ev, m):
                continue
            et=float(ev.get('timestamp') or 0)
            diff=abs(et-mt) if et and mt else 0
            if diff <= 4*3600+300 and diff < best_diff:
                best=(ei,ev); best_diff=diff
        if best:
            ei,ev=best; consumed_events.add(ei)
            mm=dict(m)
            # herda metadados de negócio/SDR, preservando id/timestamp reais da bridge
            for k,v in ev.items():
                if k in ('timestamp','timestampRaw','date'):
                    continue
                if k in ('id','messageId') and mm.get(k):
                    continue
                if v not in (None,'') and not mm.get(k):
                    mm[k]=v
            mm['type']=ev.get('type') or mm.get('type')
            mm['source']='bridge+controle/wpp_envios.json'
            mm['ledgerTimestamp']=ev.get('timestamp')
            mm['timestampSource']='bridge'
            out.append(mm)
        else:
            # Sem correspondência no ledger, a bolha pode ser conversa pessoal do chip.
            # Não expor nem para supervisor; o evento operacional puro entra abaixo.
            continue
    # eventos sem bolha real ainda entram como auditoria, mas marcados como ledger
    for ei,ev in events:
        if ei not in consumed_events:
            ee=dict(ev); ee['timestampSource']='ledger'
            out.append(ee)
    out.sort(key=lambda x: float((x or {}).get('timestamp') or 0))
    return out

def read_history(port:int):
    p=DATA_DIR / f'history_{port}.json'
    try:
        data=json.loads(p.read_text(encoding='utf-8')) if p.exists() else []
        data = data if isinstance(data, list) else []
        return merge_institutional_ledger_with_real_messages(int(port), data)
    except Exception:
        return []


def _parse_wpp_envio_ts(r):
    """Timestamp UTC para registros do controle/wpp_envios.json.

    `date_tz` pode vir ISO com offset; `date` antigo vem em BRT (sem offset).
    Retorna epoch seconds ou 0. Read-only; usado só para a inbox fast-lane.
    """
    for key in ('date_tz', 'sent_at', 'timestamp'):
        raw = r.get(key) if isinstance(r, dict) else None
        if raw:
            try:
                if isinstance(raw, (int, float)):
                    return float(raw)
                s = str(raw).strip()
                if s.endswith('Z'):
                    s = s[:-1] + '+00:00'
                # Compat: alguns registros usam "2026-06-24 16:29:45 BRT".
                if s.endswith(' BRT'):
                    s = s[:-4]
                    dt = datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=-3)))
                else:
                    dt = datetime.fromisoformat(s)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone(timedelta(hours=-3)))
                return dt.astimezone(timezone.utc).timestamp()
            except Exception:
                pass
    raw = (r.get('date') if isinstance(r, dict) else '') or ''
    s = str(raw).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            dt = datetime.strptime(s[:19], fmt).replace(tzinfo=timezone(timedelta(hours=-3)))
            return dt.astimezone(timezone.utc).timestamp()
        except Exception:
            pass
    return 0.0


_WPP_ENVIOS_ROWS_CACHE = {'mtime': 0, 'rows': []}
_WPP_FASTLANE_CACHE = {}

def _dispatch_port_for_row(r):
    """Porta/chip usado para o envio operacional.

    `bridge_port` é o chip que efetivamente enviou ao lead. `group_bridge_port`
    é só o chip usado para notificar o grupo interno e NÃO deve virar remetente
    da conversa do cliente (incidente King Talhas 26/06: UI parecia mostrar
    Lucas Resende enviando ao lead, mas o log bruto só tinha OUT pela Sarah).
    """
    for k in ('dispatch_port', 'bridge_port', 'port', 'porta'):
        v = r.get(k) if isinstance(r, dict) else None
        if v not in (None, ''):
            try:
                return int(v)
            except Exception:
                pass
    sdr = str((r or {}).get('sdr') or '').strip().lower()
    if sdr:
        for p, meta in PORTS.items():
            owner = str(meta.get('owner') or '').replace('_',' ').lower()
            label = str(meta.get('label') or '').lower()
            if sdr == owner or sdr in label:
                return int(p)
    return 0

def _wpp_envios_rows():
    try:
        mtime = WPP_ENVIOS_FILE.stat().st_mtime if WPP_ENVIOS_FILE.exists() else 0
        if _WPP_ENVIOS_ROWS_CACHE.get('mtime') == mtime:
            return _WPP_ENVIOS_ROWS_CACHE.get('rows') or []
        data = json.loads(WPP_ENVIOS_FILE.read_text(encoding='utf-8')) if WPP_ENVIOS_FILE.exists() else []
    except Exception:
        return []
    rows = []
    if isinstance(data, dict) and isinstance(data.get('envios'), list):
        rows = data.get('envios') or []
    elif isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = [v for v in data.values() if isinstance(v, dict)]
    _WPP_ENVIOS_ROWS_CACHE['mtime'] = mtime
    _WPP_ENVIOS_ROWS_CACHE['rows'] = rows
    return rows


def _wpp_envio_is_sent_dispatch(r):
    """Todo envio operacional individual deve aparecer no painel central."""
    if not isinstance(r, dict):
        return False
    chat = str(r.get('to') or r.get('jid') or r.get('lead_jid') or '').strip()
    if not chat or chat.endswith('@g.us') or chat == GROUP_JID:
        return False
    status = str(r.get('status') or '').lower().strip()
    if any(x in status for x in ('invalido','inválido','erro','falha','failed','cancel','nao_mql_grupo','não_mql_grupo')):
        return False
    msg_type = str(r.get('msg_type') or r.get('type') or '').lower().strip()
    has_payload = bool(r.get('text') or r.get('pdf_path') or r.get('file_response') or r.get('text_response') or r.get('send_response') or r.get('messageId') or r.get('response'))
    has_port = bool(r.get('bridge_port') or r.get('group_bridge_port') or r.get('port'))
    return bool(has_port and (has_payload or status.startswith('enviado') or msg_type))


def wpp_envios_fastlane_events(ports, max_age_hours=36):
    """Eventos recentes do ledger direto para a inbox, sem esperar history_*.json.

    Root cause real (Nova Ideal, 24/06): `wpp_envios.json` recebeu o diagnóstico
    minutos antes do arquivo history do chip. Como a UI já faz polling rápido, a
    inbox precisa ler esse ledger diretamente para aparecer em segundos. Só traz
    envios operacionais com chat individual e porta permitida/compartilhada; não
    envia nada, não escreve nada, não expõe conversa privada.
    """
    allowed_ports = {int(p) for p in ports if int(p) in PORTS}
    try:
        mtime = WPP_ENVIOS_FILE.stat().st_mtime if WPP_ENVIOS_FILE.exists() else 0
    except Exception:
        mtime = 0
    cache_key = (tuple(sorted(allowed_ports)), int(max_age_hours), mtime)
    cached = _WPP_FASTLANE_CACHE.get(cache_key)
    if cached is not None:
        return [dict(x) for x in cached]
    now = time.time()
    out = []
    for r in _wpp_envios_rows():
        if not isinstance(r, dict):
            continue
        if not _wpp_envio_is_sent_dispatch(r):
            continue
        chat = str(r.get('to') or r.get('jid') or r.get('lead_jid') or '').strip()
        try:
            port = int(r.get('bridge_port') or r.get('port') or 0)
        except Exception:
            port = 0
        try:
            group_port = int(r.get('group_bridge_port') or 0)
        except Exception:
            group_port = 0
        if port not in allowed_ports and group_port not in allowed_ports:
            continue
        ts = _parse_wpp_envio_ts(r)
        if not ts or ts < now - max_age_hours * 3600 or ts > now + 300:
            continue
        empresa = clean_title_value(r.get('empresa') or r.get('slug') or r.get('lead'))
        ev = dict(r)
        ev.update({
            'id': 'wpp_envios:' + str(r.get('email') or r.get('slug') or chat) + ':' + str(int(ts)),
            'chat': chat,
            'port': port,
            'portLabel': PORTS.get(port, {}).get('label', str(port)),
            'fromMe': True,
            'type': 'seed-wpp-envios',
            'source': 'controle/wpp_envios.json:fastlane',
            'timestamp': ts,
            'timestampSource': 'wpp_envios_fastlane',
            'dispatchPort': group_port or port,
            'dispatchLabel': PORTS.get(group_port or port, {}).get('label', str(group_port or port)),
            'leadOwnerId': str(r.get('owner_id') or r.get('hubspot_owner_id') or ''),
            'leadOwnerLabel': HUBSPOT_OWNER_LABELS.get(str(r.get('owner_id') or r.get('hubspot_owner_id') or ''), str(r.get('owner_id') or r.get('hubspot_owner_id') or '')),
        })
        _enrich_dispatch_identity(ev)
        if empresa and not ev.get('empresa'):
            ev['empresa'] = empresa
        # Campo `text` precisa existir para preview/merge, mas não duplicar texto gigante
        # quando só há group_summary. O painel já usa metadados p/ o card.
        if not ev.get('text') and ev.get('group_summary'):
            ev['text'] = ev.get('group_summary')
        if port in allowed_ports:
            out.append(ev)
        # Não criar conversa espelhada para `group_bridge_port`.
        # Esse campo representa a notificação no grupo interno, não uma mensagem
        # individual enviada ao lead. Mostrar isso como conversa read-only do
        # comunicador causou falso positivo de duplicidade de número/remetente.
    if len(_WPP_FASTLANE_CACHE) > 16:
        _WPP_FASTLANE_CACHE.clear()
    _WPP_FASTLANE_CACHE[cache_key] = [dict(x) for x in out]
    return out


def dispatch_stats(uid='rafael', days=14):
    """Disparos WhatsApp por dia x chip/pessoa, read-only.

    Fonte: controle/wpp_envios.json, o ledger operacional de mensagens disparadas.
    Não lê conversa pessoal de comunicador e não chama bridges/HubSpot.
    """
    try:
        days = max(1, min(31, int(days or 14)))
    except Exception:
        days = 14
    tz = timezone(timedelta(hours=-3))
    today = datetime.now(tz).date()
    day_keys = [(today - timedelta(days=i)).isoformat() for i in range(days-1, -1, -1)]
    allowed = set(int(p) for p in (PORTS.keys() if user_can_view_all(uid) else effective_ports(uid)))
    by_day = {d: {} for d in day_keys}
    details = {d: {} for d in day_keys}
    chip_totals = {}
    total = 0
    skipped = 0
    for r in _wpp_envios_rows():
        if not _wpp_envio_is_sent_dispatch(r):
            skipped += 1
            continue
        ts = _parse_wpp_envio_ts(r)
        if not ts:
            skipped += 1
            continue
        dkey = datetime.fromtimestamp(ts, tz).date().isoformat()
        if dkey not in by_day:
            continue
        port = _dispatch_port_for_row(r)
        if not port or port not in allowed:
            skipped += 1
            continue
        meta = PORTS.get(port, {})
        label = meta.get('label') or str(port)
        role = meta.get('role') or ''
        sdr = str(r.get('sdr') or '').strip()
        rec = chip_totals.setdefault(str(port), {'port': port, 'label': label, 'role': role, 'sdr': sdr, 'total': 0})
        if sdr and not rec.get('sdr'):
            rec['sdr'] = sdr
        rec['total'] += 1
        by_day[dkey][str(port)] = by_day[dkey].get(str(port), 0) + 1
        chat = str(r.get('to') or r.get('jid') or r.get('lead_jid') or '').strip()
        msg = str(r.get('text') or r.get('text_response') or r.get('group_summary') or r.get('message') or '').strip()
        if not msg and r.get('pdf_path'):
            msg = 'PDF enviado: ' + os.path.basename(str(r.get('pdf_path') or ''))
        conv_id = f'{int(port)}::{chat}' if chat else ''
        event = {
            'time': datetime.fromtimestamp(ts, tz).strftime('%H:%M'),
            'empresa': clean_title_value(r.get('empresa') or r.get('slug') or r.get('lead') or '') or chat,
            'contact': str(r.get('nome') or r.get('contact_name') or '').strip(),
            'phone': short_phone(chat) if chat else '',
            'to': chat,
            'chip': label,
            'port': port,
            'sdr': sdr,
            'type': str(r.get('msg_type') or r.get('status') or 'envio').strip(),
            'message': msg[:1200],
            'convId': conv_id,
            'link': '/conversas?conv=' + urllib.parse.quote(conv_id, safe='') if conv_id else '',
        }
        details[dkey].setdefault(str(port), []).append(event)
        total += 1
    chips = sorted(chip_totals.values(), key=lambda x: (-x.get('total',0), int(x.get('port') or 0)))
    rows = []
    for d in day_keys:
        counts = by_day.get(d, {})
        rows.append({'date': d, 'total': sum(counts.values()), 'chips': counts, 'details': details.get(d, {})})
    return {'ok': True, 'source': 'controle/wpp_envios.json', 'periodDays': days, 'total': total, 'chips': chips, 'days': rows, 'skipped': skipped, 'scope': 'consolidado' if user_can_view_all(uid) else 'seus chips'}


def _dedupe_loaded_items(items):
    """Remove duplicatas entre fastlane wpp_envios e history/bridge.

    Preferimos a bolha real da bridge quando já existe, mas se só houver fastlane
    ela mantém o card imediato. Chave conservadora: porta+chat+email/slug+minuto.
    """
    seen = {}
    for m in sorted([x for x in items if isinstance(x, dict)], key=lambda x: float(x.get('timestamp') or 0)):
        minute = int(float(m.get('timestamp') or 0) // 60)
        key = (int(m.get('port') or 0), str(m.get('chat') or ''), str(m.get('email') or m.get('slug') or '').lower(), minute)
        if not key[1] or not key[2]:
            key = (int(m.get('port') or 0), str(m.get('chat') or ''), _norm_text(m.get('text'))[:120], minute)
        prev = seen.get(key)
        if not prev:
            seen[key] = m
            continue
        prev_src = str(prev.get('source') or '')
        cur_src = str(m.get('source') or '')
        # Se a bridge/history já chegou, ela vence sobre o fastlane puro.
        if 'wpp_envios_fastlane' in prev_src or 'fastlane' in prev_src:
            seen[key] = m
        elif 'fastlane' not in cur_src:
            seen[key] = m
    return sorted(seen.values(), key=lambda x: float(x.get('timestamp') or 0))


def normalize_channel_timestamp(ts):
    """Normaliza timestamps para ordenação/exibição em Brasília.

    Algumas capturas/importações chegaram com +3h (horário de Brasília salvo como
    UTC), gerando mensagens "do futuro" e quebrando a ordem cronológica. Se a
    mensagem está mais de 2min no futuro e subtrair 3h a coloca no presente/passado
    plausível, corrigimos só em memória e preservamos timestampRaw no payload.
    """
    try:
        t = float(ts or 0)
    except Exception:
        return 0.0
    if t <= 0:
        return 0.0
    now = time.time()
    if t > now + 120 and (t - 3*3600) <= now + 300:
        return t - 3*3600
    return t

def load_ports(ports):
    items=[]
    norm_ports = sorted(set(int(p) for p in ports if int(p) in PORTS))
    for port in norm_ports:
        for m in read_history(int(port)):
            if not isinstance(m, dict): continue
            m=dict(m); m['port']=int(m.get('port') or port); m['portLabel']=PORTS.get(int(port),{}).get('label',str(port));
            raw_ts=m.get('timestamp')
            fixed_ts=normalize_channel_timestamp(raw_ts)
            if fixed_ts and raw_ts is not None and abs(float(raw_ts or 0)-fixed_ts) > 1:
                m['timestampRaw']=raw_ts
                m['timestamp']=fixed_ts
                m['timestampAdjustedBRT']=True
            items.append(m)
    # CH-RT2: fast lane do ledger. Evita esperar history_*.json/bridge consolidar
    # para mostrar diagnóstico recém-enviado na inbox.
    items.extend(wpp_envios_fastlane_events(norm_ports))
    items=_dedupe_loaded_items(items)
    items.sort(key=lambda x: float(x.get('timestamp') or 0))
    return items

def load_all(uid):
    return load_ports(effective_ports(uid))

def load_paused_ports():
    """Lê controle/CHIPS_PAUSED.flag e retorna set de portas pausadas."""
    try:
        p = PROJECT / 'controle' / 'CHIPS_PAUSED.flag'
        if p.exists():
            return set(int(line.strip()) for line in p.read_text().splitlines() if line.strip().isdigit())
    except Exception:
        pass
    return set()

def load_inbox_candidates(uid):
    """Mensagens candidatas para a inbox.

    Além das portas próprias, inclui chips compartilhados (Mariana/Lucas/Rafael)
    para posterior filtro por SDR/deal. O filtro ocorre em `conversations()` e
    `conversation_allowed()`; aqui só disponibilizamos os eventos para montar a
    conversa e inspecionar metadados como `sdr`/empresa/email.
    Chips pausados (controle/CHIPS_PAUSED.flag) são excluídos para não poluir
    a inbox com mensagens antigas de chips desconectados.
    """
    allowed=set(effective_ports(uid))
    if user_can_view_all(uid):
        ports=set(PORTS.keys())
    else:
        ports=allowed | set(SHARED_DEAL_VISIBILITY_PORTS)
    ports -= load_paused_ports()
    return load_ports(ports)

def _norm_owner_token(s):
    s=str(s or '').strip().lower()
    s=(s.replace('á','a').replace('à','a').replace('ã','a').replace('â','a')
        .replace('é','e').replace('ê','e').replace('í','i').replace('ó','o')
        .replace('ô','o').replace('õ','o').replace('ú','u').replace('ç','c'))
    s=re.sub(r'[^a-z0-9]+','_',s).strip('_')
    return s

def sdr_hint_to_uid(s):
    """Converte metadado `sdr`/owner humano do histórico em uid do Channel."""
    t=_norm_owner_token(s)
    if not t:
        return ''
    aliases={
        'breno':'breno','breno_magalhaes':'breno',
        'sarah':'sarah','sarah2':'sarah','sarah_2':'sarah',
        'lucas':'lucas_batista','lucas_batista':'lucas_batista',
        'lucas_resende':'lucas_resende',
        'rafael':'rafael','mariana':'mariana',
    }
    uid=aliases.get(t) or (t if t in USERS else '')
    return uid if uid in USERS else ''

def _conversation_sdr_hint_from_msg(m):
    oid = str((m or {}).get('owner_id') or (m or {}).get('hubspot_owner_id') or '').strip()
    if oid:
        uid = hubspot_owner_uid_map().get(oid, '')
        if uid:
            return uid
    for k in ('sdr','sdrName','ownerName','hubspot_owner_name'):
        uid=sdr_hint_to_uid(m.get(k))
        if uid:
            return uid
    return ''

def clean_title_value(v):
    v = str(v or '').strip()
    if not v or v.lower() in {'none','null','sem empresa','sem nome'}:
        return ''
    return v


# ---- CH-006: LID vs JID real -------------------------------------------------
# history-sync trouxe conversas identificadas só por `@lid` (sem `remoteJidAlt`).
# LID NÃO é telefone: aplicar máscara nele gera números falsos (+22, +18, ...).
# Nunca derivar telefone de um @lid e nunca vazar o identificador bruto na UI.
def is_lid(chat):
    return str(chat or '').strip().lower().endswith('@lid')


def _is_real_jid(v):
    v = str(v or '').strip().lower()
    return (v.endswith('@s.whatsapp.net') or v.endswith('@c.us')) and not is_lid(v)


def real_jid_from(m):
    """Tenta achar o JID real (telefone) de uma mensagem cujo chat é @lid.

    Mensagens `notify`/`append` mais novas trazem o número real em
    `remoteJidAlt`/`jidAlt` (ou já no próprio chat). history-sync antigo de LID
    não tem nada disso — nesse caso retorna '' e a conversa fica sem número.
    """
    if not isinstance(m, dict):
        return ''
    rk = m.get('rawKey') or {}
    for v in (m.get('remoteJidAlt'), m.get('jidAlt'), rk.get('remoteJidAlt'),
              rk.get('jidAlt'), m.get('chat'), m.get('sender')):
        if _is_real_jid(v):
            return str(v)
    return ''


def short_phone(chat):
    chat = str(chat or '')
    # @lid / grupo / broadcast nunca viram telefone (evita +22, +18 falsos).
    if is_lid(chat) or chat.endswith('@g.us') or chat.endswith('@broadcast') or chat == 'status@broadcast':
        return ''
    digits=''.join(ch for ch in chat if ch.isdigit())
    # Só formata telefone real: BR = 55 + DDD + número (12 ou 13 dígitos).
    # IDs de 14-15 dígitos (ou que não começam com 55) são LID-derivados/inválidos
    # e NÃO podem virar "+88 11 ..." falso.
    if 12 <= len(digits) <= 13 and digits.startswith('55'):
        return f"+{digits[:2]} {digits[2:4]} {digits[4:-4]}-{digits[-4:]}"
    return ''


def real_phone_digits(chat):
    """Dígitos de telefone BR válido para agrupar JIDs equivalentes.

    Baileys/WhatsApp às vezes grava o envio como `@c.us` e a resposta como
    `@s.whatsapp.net`/`@lid` com `remoteJidAlt`. Para a UI, esses são a mesma
    conversa se os dígitos são telefone BR válido. Nunca deriva número de @lid puro.
    """
    if not short_phone(chat):
        return ''
    return ''.join(ch for ch in str(chat or '') if ch.isdigit())


def canonical_chat_for_message(m):
    if not isinstance(m, dict):
        return ''
    for v in (real_jid_from(m), m.get('chat')):
        d = real_phone_digits(v)
        if d:
            return f'{d}@s.whatsapp.net'
    return str(m.get('chat') or '')


def canonical_chat_id(chat):
    d = real_phone_digits(chat)
    return f'{d}@s.whatsapp.net' if d else str(chat or '')


def message_matches_chat(m, chat):
    return canonical_chat_for_message(m) == canonical_chat_id(chat)


# Números internos Zydon/SDR/institucionais. Conversas entre esses chips são
# aquecimento, validação ou coordenação interna — não são leads e não devem
# poluir inbox/Responder agora.
INTERNAL_WPP_DIGITS = {
    '553484255965',  # Mariana institucional
    '553484477245',  # Sarah antigo
    '553484291640',  # Sarah 1 novo/canônico — validação/aquecimento interno, não lead
    '553484325076',  # Breno
    '553484295409',  # Lucas Batista
    '553484428888',  # Lucas Resende institucional
    '553496698718',  # Rafael
}

def chat_digits(chat):
    return ''.join(ch for ch in str(chat or '') if ch.isdigit())

def is_internal_contact(chat):
    d = chat_digits(chat)
    return any(d.startswith(n) for n in INTERNAL_WPP_DIGITS)


def _is_diag_dispatch(m):
    """Diagnóstico enviado ao lead, inclusive registros novos do ledger.

    Alguns envios recentes entram em `wpp_envios.json` como status=enviado_lead
    com `pdf_path`/`hubspot_file_id`, sem type cron-mql-*. Se não tratarmos isso
    como diagnóstico, o card fica preso na resposta antiga do lead (ex.: 55min).
    """
    if not isinstance(m, dict) or not m.get('fromMe'):
        return False
    typ = str(m.get('type') or '')
    status = str(m.get('status') or '').lower()
    if typ in ('cron-mql-texto', 'cron-mql-pdf'):
        return True
    if status in {'enviado_lead', 'enviado_mql'} and (m.get('pdf_path') or m.get('hubspot_file_id') or m.get('group_summary')):
        return True
    msg_type = str(m.get('msg_type') or '').lower()
    return 'diagnostico' in msg_type or 'mql' in msg_type


def source_label(m):
    typ=str(m.get('type') or '')
    msg_type=str(m.get('msg_type') or '').lower()
    if _is_diag_dispatch(m): return 'Diagnóstico enviado'
    if 'follow' in msg_type or 'follow' in typ.lower(): return 'Follow-up enviado'
    if 'cadencia' in msg_type or 'sumico' in msg_type: return 'Cadência enviada'
    if typ == 'cron-sdr-primeiro-contato' or 'primeiro_contato' in msg_type or (typ == 'cron-whatsapp-texto' and is_institutional_port(m.get('port'))): return '1º contato SDR'
    if typ.startswith('cron-'): return 'Automação'
    if not m.get('fromMe'): return 'Resposta recebida'
    return 'WhatsApp'


def _enrich_dispatch_identity(m):
    if not isinstance(m, dict):
        return m
    try:
        gp = int(m.get('group_bridge_port') or m.get('dispatchPort') or 0)
    except Exception:
        gp = 0
    try:
        bp = int(m.get('bridge_port') or m.get('port') or 0)
    except Exception:
        bp = 0
    dispatch_port = gp or bp
    if dispatch_port and not m.get('dispatchPort'):
        m['dispatchPort'] = dispatch_port
    if dispatch_port and not m.get('dispatchLabel'):
        m['dispatchLabel'] = PORTS.get(dispatch_port, {}).get('label', str(dispatch_port))
    owner_id = str(m.get('owner_id') or m.get('hubspot_owner_id') or m.get('leadOwnerId') or '').strip()
    if owner_id and not m.get('leadOwnerId'):
        m['leadOwnerId'] = owner_id
    if owner_id and not m.get('leadOwnerLabel'):
        m['leadOwnerLabel'] = HUBSPOT_OWNER_LABELS.get(owner_id, owner_id)
    return m


def _auto_sent_ok(m):
    st = str((m or {}).get('status') or '').lower()
    return (not st) or st in {'ok','sent','enviado','enviado_lead','enviado_mql','1','2'}


def _auto_summary_init():
    return {
        'diagnosticoTextAt': 0, 'diagnosticoPdfAt': 0,
        'primeiroContatoAt': 0, 'followupAt': 0,
        'lastAutomationAt': 0, 'lastAutomationLabel': '',
        'failures': 0, 'failedLabels': [],
    }


def _record_automation(c, m, ts):
    typ = str((m or {}).get('type') or '')
    if not (typ.startswith('cron-') or _is_diag_dispatch(m) or is_institutional_dispatch_msg(m)):
        return
    a = c.setdefault('automation', _auto_summary_init())
    label = source_label(m)
    if ts >= float(a.get('lastAutomationAt') or 0):
        a['lastAutomationAt'] = ts
        a['lastAutomationLabel'] = label
    if not _auto_sent_ok(m):
        a['failures'] = int(a.get('failures') or 0) + 1
        if label not in a.get('failedLabels', []):
            a.setdefault('failedLabels', []).append(label)
    if _is_diag_dispatch(m):
        # Eventos novos do ledger (`status=enviado_lead`) representam texto + PDF.
        a['diagnosticoTextAt'] = max(float(a.get('diagnosticoTextAt') or 0), ts)
        a['diagnosticoPdfAt'] = max(float(a.get('diagnosticoPdfAt') or 0), ts)
    elif typ == 'cron-sdr-primeiro-contato' or 'primeiro_contato' in str((m or {}).get('msg_type') or '') or (typ == 'cron-whatsapp-texto' and is_institutional_port((m or {}).get('port'))):
        a['primeiroContatoAt'] = max(float(a.get('primeiroContatoAt') or 0), ts)
    elif typ == 'cron-whatsapp-texto':
        a['followupAt'] = max(float(a.get('followupAt') or 0), ts)


def _finalize_automation(a):
    a = a if isinstance(a, dict) else _auto_summary_init()
    txt = float(a.get('diagnosticoTextAt') or 0)
    pdf = float(a.get('diagnosticoPdfAt') or 0)
    if txt and pdf:
        diag = 'feito'
    elif txt or pdf:
        diag = 'parcial'
    else:
        diag = 'pendente'
    primeiro = 'feito' if float(a.get('primeiroContatoAt') or 0) else 'pendente'
    follow = 'feito' if float(a.get('followupAt') or 0) else 'pendente'
    risk = 'falha' if int(a.get('failures') or 0) else ('atenção' if diag == 'parcial' else 'ok')
    a.update({'diagnostico': diag, 'primeiroContato': primeiro, 'followup': follow, 'risk': risk})
    return a


# ---- CH-050: resumo automático heurístico da conversa ------------------------
# Resumo determinístico (sem LLM/API externa) montado só com o que já está nas
# mensagens da própria conversa. Linguagem comercial, nunca técnica: jamais usa
# JID/telefone/porta. Não inventa nada — se falta histórico, diz isso.
_AI_MEETING_PAT = re.compile(
    r'reuni|agenda|hor[áa]ri|dispon[ií]v|marcar|call|meet|zoom|amanh[ãa]|'
    r'segunda|ter[çc]a|quarta|quinta|sexta|que horas|podemos conversar|'
    r'bate[ -]?papo|demonstra|apresenta',
    re.I,
)


def _msg_has_media(m):
    if not isinstance(m, dict):
        return False
    if m.get('media'):
        return True
    return bool(m.get('mediaUrl') or m.get('mediaName') or m.get('mediaPath')
                or m.get('mimetype') or m.get('mediaType'))


def _is_audio_msg(m):
    if not isinstance(m, dict):
        return False
    mt = str(m.get('mediaType') or '').lower()
    mime = str(m.get('mimetype') or '').lower()
    name = str(m.get('mediaName') or m.get('mediaPath') or m.get('mediaUrl') or '').lower()
    return mt == 'audio' or mime.startswith('audio/') or name.endswith(('.ogg', '.opus', '.mp3', '.m4a', '.wav', '.aac', '.flac'))


def _audio_key(m):
    port = str(m.get('port') or '')
    mid = str(m.get('id') or '').strip()
    if mid:
        return f'{port}:{mid}'
    return f"{port}:{hashlib.sha1(str(m.get('mediaPath') or m.get('mediaUrl') or '').encode()).hexdigest()[:16]}"


def load_audio_transcripts():
    try:
        if CHANNEL_TRANSCRIPTS_FILE.exists():
            data = json.loads(CHANNEL_TRANSCRIPTS_FILE.read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def save_audio_transcripts(data):
    try:
        CHANNEL_TRANSCRIPTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CHANNEL_TRANSCRIPTS_FILE.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        try: os.chmod(tmp, 0o600)
        except Exception: pass
        tmp.replace(CHANNEL_TRANSCRIPTS_FILE)
        try: os.chmod(CHANNEL_TRANSCRIPTS_FILE, 0o600)
        except Exception: pass
    except Exception:
        pass


def _audio_file_path(m):
    p = Path(str(m.get('mediaPath') or ''))
    if p.exists() and p.is_file():
        return p
    try:
        port = int(m.get('port') or 0)
    except Exception:
        port = 0
    fname = os.path.basename(str(m.get('mediaUrl') or '').split('?', 1)[0])
    if port and fname:
        p = DATA_DIR / 'media' / str(port) / fname
        if p.exists() and p.is_file():
            return p
    return None


def transcribe_audio_message(m, cache=None, force=False):
    """Transcreve um áudio via faster-whisper local do Hermes e cacheia o texto.

    Nunca envia dados ao WhatsApp/HubSpot. Falha vira status `error`/`pending`, sem
    quebrar a UI. Usado sob demanda ao abrir conversa ou pelo endpoint dedicado.
    """
    if not _is_audio_msg(m):
        return None
    cache = load_audio_transcripts() if cache is None else cache
    key = _audio_key(m)
    item = cache.get(key) or {}
    if item.get('transcript') and not force:
        return item
    p = _audio_file_path(m)
    if not p:
        item = {'status':'missing_file','transcript':'','updatedAt':datetime.now(timezone.utc).isoformat()}
        cache[key] = item; save_audio_transcripts(cache); return item
    if p.stat().st_size > 25 * 1024 * 1024:
        item = {'status':'too_large','transcript':'','updatedAt':datetime.now(timezone.utc).isoformat(), 'file':str(p)}
        cache[key] = item; save_audio_transcripts(cache); return item
    code = """
import json, sys
sys.path.insert(0, '/usr/local/lib/hermes-agent')
from tools.transcription_tools import transcribe_audio
r = transcribe_audio(sys.argv[1])
print(json.dumps(r, ensure_ascii=False))
"""
    try:
        env = os.environ.copy()
        env.setdefault('HERMES_LOCAL_STT_LANGUAGE', 'pt')
        cp = subprocess.run([HERMES_PY, '-c', code, str(p)], text=True, capture_output=True, timeout=240, env=env)
        raw = (cp.stdout or '').strip().splitlines()[-1] if cp.stdout else ''
        res = json.loads(raw) if raw else {'success': False, 'error': (cp.stderr or 'sem saída')[:500]}
        txt = ' '.join(str(res.get('transcript') or '').split()).strip()
        item = {'status':'done' if txt else 'empty', 'transcript':txt, 'provider':res.get('provider') or 'local',
                'updatedAt':datetime.now(timezone.utc).isoformat(), 'file':str(p)}
        if not res.get('success') and not txt:
            item['status'] = 'error'; item['error'] = str(res.get('error') or cp.stderr or '')[:500]
    except Exception as e:
        item = {'status':'error','transcript':'','error':str(e)[:500],'updatedAt':datetime.now(timezone.utc).isoformat(), 'file':str(p)}
    cache[key] = item
    save_audio_transcripts(cache)
    return item


def enrich_audio_transcripts(msgs, autotranscribe=False, max_auto=2):
    cache = load_audio_transcripts()
    changed = False
    auto_left = max_auto
    for m in msgs or []:
        if not isinstance(m, dict) or not _is_audio_msg(m):
            continue
        key = _audio_key(m)
        item = cache.get(key)
        if (not item or (not item.get('transcript') and item.get('status') in (None, 'error', 'missing_file'))) and autotranscribe and auto_left > 0 and not m.get('fromMe'):
            item = transcribe_audio_message(m, cache=cache)
            changed = True; auto_left -= 1
        if item:
            m['transcript'] = item.get('transcript') or ''
            m['transcriptStatus'] = item.get('status') or 'pending'
            if item.get('provider'):
                m['transcriptProvider'] = item.get('provider')
        else:
            m['transcript'] = ''
            m['transcriptStatus'] = 'pending'
    if changed:
        save_audio_transcripts(cache)
    return msgs


def conversation_audio_meta(msgs):
    cache = load_audio_transcripts()
    pending = 0; transcripts = []
    for m in msgs or []:
        if not isinstance(m, dict) or m.get('fromMe') or not _is_audio_msg(m):
            continue
        item = cache.get(_audio_key(m)) or {}
        txt = ' '.join(str(item.get('transcript') or '').split()).strip()
        if txt:
            transcripts.append(txt)
        else:
            pending += 1
    return {'audioPending': pending, 'audioTranscriptText': ' '.join(transcripts)[:1200]}


def build_ai_summary(msgs, local_status='open', now=None):
    """CH-050: resumo heurístico + próxima ação da conversa.

    Entrada: lista de mensagens colapsadas (ou snippets equivalentes), em ordem
    ascendente por timestamp. Cada item usa `fromMe`, `text`, `timestamp`,
    `type` e indicadores de mídia. Saída: dict `aiSummary` com `summary`,
    `nextAction`, `temperature` (quente|morno|frio) e `signals` (lista curta).

    Sem chamadas de rede/LLM. Não vaza JID/telefone e não inventa dados.
    """
    msgs = [m for m in (msgs or []) if isinstance(m, dict)]
    now = time.time() if now is None else now
    status = str(local_status or 'open').lower()

    insufficient = {
        'summary': 'Pouco histórico capturado ainda.',
        'nextAction': 'Abrir a conversa e dar o próximo passo manualmente.',
        'temperature': 'frio',
        'signals': [],
    }
    if not msgs:
        return insufficient

    incoming = [m for m in msgs if not m.get('fromMe')]
    outgoing = [m for m in msgs if m.get('fromMe')]
    last = msgs[-1]
    last_in = incoming[-1] if incoming else None

    lead_text = ' '.join(str(m.get('text') or '') for m in incoming)
    asked_meeting = bool(last_in) and bool(_AI_MEETING_PAT.search(lead_text))
    lead_media = any(_msg_has_media(m) for m in incoming)
    lead_audio = any(bool(m.get('audio')) for m in incoming)
    sent_primeiro = any(str(m.get('type') or '') == 'cron-sdr-primeiro-contato' for m in outgoing)
    sent_diag = any(str(m.get('type') or '').startswith('cron-mql') for m in outgoing)

    last_in_age = (now - float(last_in.get('timestamp') or 0)) if last_in else None
    recent_reply = last_in_age is not None and last_in_age <= 48 * 3600
    awaiting_us = not last.get('fromMe')  # última mensagem é do lead -> devemos retorno

    signals = []
    if incoming:
        signals.append('Lead respondeu')
    else:
        signals.append('Sem resposta')
    if asked_meeting:
        signals.append('Pediu reunião')
    if lead_audio:
        signals.append('Áudio do lead')
    elif lead_media:
        signals.append('Enviou mídia')
    if recent_reply:
        signals.append('Resposta recente')
    if sent_diag:
        signals.append('Diagnóstico enviado')
    elif sent_primeiro:
        signals.append('Primeiro contato enviado')
    if status == 'resolved':
        signals.append('Conversa resolvida')
    elif status == 'pending':
        signals.append('Triagem pendente')

    # temperatura: agenda quente; resposta recente aguardando retorno também.
    if asked_meeting or (awaiting_us and recent_reply):
        temperature = 'quente'
    elif incoming:
        temperature = 'morno'
    else:
        temperature = 'frio'

    if status == 'resolved':
        summary = 'Conversa marcada como resolvida pelo time.'
        nextAction = 'Acompanhar no follow-up; nada urgente por agora.'
    elif asked_meeting:
        summary = 'O lead respondeu e tocou em agenda/reunião.'
        nextAction = 'Confirmar um horário e enviar o convite da reunião.'
    elif awaiting_us and lead_audio:
        summary = 'O lead respondeu por áudio e aguarda retorno.'
        nextAction = 'Ler/ouvir o áudio transcrito e responder com próximo passo.'
    elif awaiting_us and incoming:
        summary = 'O lead respondeu e a última mensagem aguarda retorno.'
        nextAction = 'Responder o lead agora para manter o ritmo.'
    elif incoming:
        summary = 'Lead já interagiu; conversa em andamento.'
        nextAction = 'Fazer um follow-up leve com proposta de próximo passo.'
    elif sent_diag or sent_primeiro:
        base = 'Diagnóstico enviado' if sent_diag else 'Primeiro contato enviado'
        summary = f'{base}, ainda sem resposta do lead.'
        nextAction = 'Fazer follow-up — sem resposta até agora.'
    else:
        summary = 'Conversa iniciada, ainda sem resposta do lead.'
        nextAction = 'Aguardar ou enviar um follow-up leve.'

    return {
        'summary': summary,
        'nextAction': nextAction,
        'temperature': temperature,
        'signals': signals[:5],
    }


def conversations(uid):
    conv={}
    is_admin = bool(USERS.get(uid, {}).get('admin'))
    view_all = user_can_view_all(uid)
    allowed_ports=set(effective_ports(uid))
    transcript_cache = load_audio_transcripts()
    for m in load_inbox_candidates(uid):
        chat=m.get('chat') or ''
        if not chat:
            continue
        # Grupo interno polui a visão de conversas/leads e gera falsas "respostas".
        # O Channel é para conversas individuais; auditoria de grupo fica no dashboard de envios.
        if chat == GROUP_JID or chat.endswith('@g.us') or chat == 'status@broadcast' or chat.endswith('@broadcast') or is_internal_contact(chat):
            continue
        # Rafael 24/06: não exibir conversas antigas/protegidas da Zoe ou sem telefone real.
        # O Channel comercial deve mostrar leads com celular real; JID @lid/0@s.whatsapp.net
        # vira "Contato/Lead sem número" e polui fila/SDR.
        txt0 = str(m.get('text') or '')
        if is_lid(chat) or chat.startswith('0@') or 'zoe' in txt0.lower():
            continue
        port_i=int(m.get('port') or 0)
        # Privacidade: chips pessoais/institucionais (Mariana/Rafael/Lucas Resende)
        # nunca aparecem como conversa normal. Só eventos operacionais de envio
        # para negócio de SDR entram como auditoria read-only.
        if is_institutional_port(port_i) and m.get('fromMe') and not is_institutional_dispatch_msg(m):
            continue
        chat_key = canonical_chat_for_message(m)
        key=f"{port_i}::{chat_key}"
        c=conv.setdefault(key, {'id':key,'chat':chat_key,'title':'','subtitle':'','port':port_i,'portLabel':m.get('portLabel'),'messages':0,'last':None,'lastTime':0,'lastIncomingTime':0,'lastOutgoingTime':0,'unread':0,'responses':0,'lastIncoming':None,'lastSource':'','realJid':'','automation':_auto_summary_init(),'audioPending':0,'audioTranscriptText':'','sharedFromPort':False,'sharedVisibilityReason':'','sharedOwnerUid':'','_directVisible':port_i in allowed_ports,'_sdrHintUid':'','_recent':[]})
        c['messages'] += 1
        # CH-050: acumula só os últimos snippets (sem reler load_all por conversa)
        # para montar o resumo heurístico depois. Mantém o custo baixo (~12 itens).
        # CH-050/052: snippets para resumo; se áudio já foi transcrito, ele vira
        # texto pesquisável e entra no resumo sem chamar STT na listagem.
        txt = str(m.get('text') or '')
        if _is_audio_msg(m) and not m.get('fromMe'):
            item = transcript_cache.get(_audio_key(m)) or {}
            tr = ' '.join(str(item.get('transcript') or '').split()).strip()
            if tr:
                txt = tr
                c['audioTranscriptText'] = (str(c.get('audioTranscriptText') or '') + ' ' + tr).strip()[:1200]
            else:
                c['audioPending'] = int(c.get('audioPending') or 0) + 1
        _rec=c['_recent']
        _rec.append({'fromMe':bool(m.get('fromMe')),'text':txt[:240],'timestamp':float(m.get('timestamp') or 0),'type':str(m.get('type') or ''),'media':_msg_has_media(m),'audio':_is_audio_msg(m)})
        if len(_rec)>12: del _rec[0]
        # CH-006: se alguma mensagem revelar o JID real (remoteJidAlt etc), guarda
        # para preferir telefone real em vez de "sem número".
        if not c.get('realJid'):
            rj = real_jid_from(m)
            if rj and not is_lid(rj):
                c['realJid'] = rj
        # CH-057: em chips compartilhados, os eventos de automação carregam
        # `sdr` (ex.: Breno/Sarah/Lucas). Esse é o atalho seguro para mostrar
        # ao SDR a conversa iniciada por Mariana/Lucas/Rafael enquanto o cache
        # HubSpot confirma/enriquece o owner do deal quando disponível.
        if not c.get('_sdrHintUid'):
            hu=_conversation_sdr_hint_from_msg(m)
            if hu:
                c['_sdrHintUid']=hu
        # CH-003: pistas baratas p/ reler o cache HubSpot (email/empresa) sem rede.
        if not c.get('_hsEmail') and m.get('email'):
            c['_hsEmail'] = str(m.get('email')).strip()
        if not c.get('_hsEmpresa'):
            _emp = clean_title_value(m.get('empresa'))
            if _emp:
                c['_hsEmpresa'] = _emp
        ts = float(m.get('timestamp') or 0)
        if ts >= float(c.get('lastTime') or 0):
            c['lastTime'] = ts
            c['last'] = m
            c['lastSource'] = source_label(m)
        if not m.get('fromMe'):
            c['unread'] += 1
            c['responses'] += 1
            if ts > float(c.get('lastIncomingTime') or 0):
                c['lastIncomingTime'] = ts
            if ts >= float((c.get('lastIncoming') or {}).get('timestamp') or 0):
                c['lastIncoming'] = m
        else:
            if ts > float(c.get('lastOutgoingTime') or 0):
                c['lastOutgoingTime'] = ts
        if m.get('fromMe'):
            _record_automation(c, m, ts)
        # melhor título da conversa inteira: empresa > nome > slug > telefone
        best = clean_title_value(m.get('empresa') or m.get('lead'))
        if best and (not c.get('title') or c.get('title') == short_phone(chat) or c.get('title') == chat):
            c['title'] = best
        name = clean_title_value(m.get('nome'))
        sdr = clean_title_value(m.get('sdr'))
        if name and name.lower() not in str(c.get('title','')).lower():
            c['subtitle'] = name + (f" · {sdr}" if sdr else '')
        elif sdr and not c.get('subtitle'):
            c['subtitle'] = sdr
    out=[]
    for c in conv.values():
        chat = c.get('chat') or ''
        real = c.get('realJid') or ''
        # Telefone exibível: real do alt-JID, senão do chat se for número de verdade.
        # @lid e IDs LID-derivados (sem telefone válido) devolvem '' aqui.
        display_phone = short_phone(real) or short_phone(chat)
        # "Protegido" = sem telefone real exibível (inclui @lid e JIDs LID-derivados).
        protected = not display_phone
        c['lid'] = protected
        c['displayPhone'] = display_phone
        # Título: empresa/lead (já definido) > telefone real > "Contato/Lead sem número".
        if not c.get('title'):
            c['title'] = display_phone or ('Lead sem número' if (c.get('responses') or 0) > 0 else 'Contato sem número')
        # Subtítulo: nome/sdr (já definido) > telefone real > aviso amigável (nunca o JID bruto).
        if not c.get('subtitle'):
            c['subtitle'] = display_phone or 'Identificador WhatsApp protegido'
        if is_institutional_port(c.get('port')):
            # Só manter auditoria de envio feito por institucional para negócio de SDR.
            # Sem SDR dono => é privado/operacional interno e sai da inbox.
            inst_owner = c.get('_sdrHintUid') or ''
            if inst_owner not in SDR_OWNER_UIDS or not float((c.get('automation') or {}).get('lastAutomationAt') or 0):
                continue
            c['readOnlyInstitutional'] = True
            c['institutionalDispatchLabel'] = 'Envio institucional'
        # CH-057: se a conversa veio de chip compartilhado (Mariana/Lucas/Rafael),
        # só entra para o SDR quando o metadado/HubSpot aponta que o lead/deal é dele.
        email_hint=c.get('_hsEmail') or ''
        empresa_hint=c.get('_hsEmpresa') or ''
        allowed_info=conversation_allowed(uid, c, email=email_hint, empresa=empresa_hint, use_hubspot=False)
        if not allowed_info.get('allowed'):
            continue
        c['sharedFromPort'] = bool(allowed_info.get('shared'))
        c['sharedOwnerUid'] = allowed_info.get('ownerUid') or ''
        c['sharedVisibilityReason'] = allowed_info.get('reason') or ''
        # Nunca devolver o JID/LID cru como conteúdo visível além do campo técnico `chat`.
        c.pop('realJid', None)
        c.pop('_directVisible', None)
        c['sdrHintUid'] = c.get('_sdrHintUid') or ''
        c.pop('_sdrHintUid', None)
        out.append(c)
    out.sort(key=lambda c: float(c.get('lastTime') or 0), reverse=True)
    # CH-010: enriquece cada conversa com o estado local (status + nota interna).
    state = load_channel_state()
    # CH-042: saúde dos chips do usuário, UMA vez por request (snapshot c/ TTL).
    snap = _port_health_snapshot(USERS.get(uid, {}).get('ports', []))
    # CH-059: cache de vínculo HubSpot para marcar hubspotLinked.
    hs_cache = _load_shared_visibility_cache()
    for c in out:
        c['automation'] = _finalize_automation(c.get('automation'))
        auto = c.get('automation') or {}
        if is_institutional_port(c.get('port')):
            c['readOnlyInstitutional'] = True
            c['institutionalDispatchLabel'] = auto.get('lastAutomationLabel') or 'Envio institucional'
        # Ordenação comercial estilo WhatsApp: resposta do lead sobe; senão,
        # usa entrada real do lead (1º contato/diagnóstico) e não follow-up/replay.
        entry_times = [float(auto.get(k) or 0) for k in ('primeiroContatoAt','diagnosticoPdfAt','diagnosticoTextAt')]
        commercial_entry = max(entry_times) if entry_times else 0
        c['commercialEntryTime'] = commercial_entry or float(c.get('lastTime') or 0)
        c['inboxSortTime'] = float(c.get('lastIncomingTime') or 0) or c['commercialEntryTime']
        c.update(local_state_summary(state.get(c.get('id'))))
        # CH-050: resumo heurístico a partir dos snippets já acumulados no loop.
        c['aiSummary'] = build_ai_summary(c.pop('_recent', []), local_status=c.get('localStatus'))
        # CH-042/057: chip recomendado p/ responder. Em conversa compartilhada,
        # o chip original pode ser Mariana/Rafael/Lucas; o envio deve sair por
        # um chip permitido do SDR dono, nunca por porta sem permissão.
        rt = recommend_send_port(uid, c.get('port'), snap, target_owner=(uid if c.get('sharedFromPort') else None))
        c['sendPort'] = rt['port']
        c['sendPortLabel'] = rt['label']
        c['sendRoutingReason'] = rt['reason']
        c['sendRoutingChanged'] = bool(rt['changed'])
        c['sendRoutingHealth'] = rt['health']
        if c.get('readOnlyInstitutional'):
            c['sendPort'] = None
            c['sendPortLabel'] = ''
            c['sendRoutingReason'] = 'Registro somente leitura: envio feito por chip pessoal/institucional.'
            c['sendRoutingChanged'] = False
        # CH-003: reunião real do HubSpot (lendo só o cache já populado, sem rede).
        mi = _conv_meeting_from_cache(c, email=c.get('_hsEmail') or '', empresa=c.get('_hsEmpresa') or '')
        c['hubspotHasMeeting'] = mi['has']
        c['meetingNextAt'] = mi['nextAt']
        # CH-059/062: vínculo HubSpot REAL é só contato/deal/cache. Resposta do lead
        # ou automação indica origem comercial, mas não prova que achamos contato no CRM.
        hs_entry = hs_cache.get(c.get('id') or '', {})
        hs_link = _conv_hubspot_link_from_cache(c, email=c.get('_hsEmail') or '', empresa=c.get('_hsEmpresa') or '')
        if hs_link.get('contactId'):
            c['hubspotContactId'] = hs_link['contactId']
        if hs_link.get('dealId'):
            c['hubspotDealId'] = hs_link['dealId']
        owner_uid = (hs_entry.get('ownerUid') if isinstance(hs_entry, dict) else '') or c.get('sdrHintUid') or PORTS.get(int(c.get('port') or 0), {}).get('owner') or ''
        c['dealOwnerUid'] = owner_uid
        c['dealOwnerLabel'] = (USERS.get(owner_uid, {}) or {}).get('name') or owner_uid.replace('_',' ').title()
        c['senderLabel'] = PORTS.get(int(c.get('port') or 0), {}).get('label','')
        c['sdrLabel'] = c['dealOwnerLabel']
        c['hubspotLinked'] = bool(c.get('hubspotContactId') or c.get('hubspotDealId') or (isinstance(hs_entry, dict) and (hs_entry.get('contactId') or hs_entry.get('dealId'))))
        c['hubspotOriginHint'] = bool(c.get('automation', {}).get('lastAutomationAt') or c.get('responses', 0) > 0)
        c.pop('_hsEmail', None)
        c.pop('_hsEmpresa', None)
    out.sort(key=lambda c: float(c.get('inboxSortTime') or c.get('lastTime') or 0), reverse=True)
    return out

# ---- CH-007: dedup visual automação + mensagem enviada -----------------------
# A automação registra um evento (cron-*/seed-wpp-envios/api-send) E a bridge
# captura a mensagem realmente enviada (append/notify). As duas têm o mesmo
# texto/minuto/fromMe/chat -> na timeline parece que o SDR mandou duas vezes.
# Aqui colapsamos para UMA bolha, virando a automação um badge dentro dela.
AUTOMATION_EXACT = {'seed-wpp-envios', 'api-send'}

def is_automation_event(m):
    if not isinstance(m, dict) or not m.get('fromMe'):
        return False
    t = str(m.get('type') or '')
    return t.startswith('cron-') or t in AUTOMATION_EXACT

def automation_badge(m):
    t = str(m.get('type') or '')
    if t == 'cron-sdr-primeiro-contato': return 'Automação · 1º contato'
    if t == 'cron-mql-texto': return 'Automação · Diagnóstico'
    if t == 'cron-mql-pdf': return 'Automação · Diagnóstico (PDF)'
    if t == 'cron-whatsapp-texto': return 'Automação'
    if t == 'cron-naomql-grupo': return 'Automação · interno'
    return 'Automação'

def _norm_text(t):
    return ' '.join(str(t or '').split()).strip().lower()

def _media_key(m):
    name = str((m or {}).get('mediaName') or '').strip().lower()
    return name

def collapse_automation(msgs):
    """Funde evento de automação + mensagem enviada idêntica numa bolha única.

    Não remove nada do arquivo (opera sobre cópias de load_all) e não esconde
    PDFs: se a bolha real não tiver mídia mas o evento tiver, herda a mídia.
    Eventos de automação sem mensagem real correspondente continuam aparecendo.
    """
    msgs = [m for m in msgs if isinstance(m, dict)]
    events = [m for m in msgs if is_automation_event(m)]
    consumed = set()
    for m in msgs:
        if not m.get('fromMe') or is_automation_event(m):
            continue  # só mensagens "reais" enviadas (append/notify) puxam um evento
        nt = _norm_text(m.get('text'))
        mk = _media_key(m)
        mt = float(m.get('timestamp') or 0)
        for ev in events:
            if id(ev) in consumed:
                continue
            if abs(float(ev.get('timestamp') or 0) - mt) > 120:
                continue
            ent = _norm_text(ev.get('text'))
            same_text = nt != '' and nt == ent
            same_media = bool(mk) and mk == _media_key(ev)
            if not (same_text or same_media):
                continue
            consumed.add(id(ev))
            m['automation'] = automation_badge(ev)
            # mantém metadados comerciais do ledger/import na bolha real; sem isso
            # uma conversa com append @c.us + resposta @s.whatsapp.net mostra só telefone
            # em vez de empresa/contato (ex.: SURGIC/Geraldo antes do áudio).
            for k in ('empresa','lead','nome','sdr','owner_id','hubspot_owner_id','email','slug','bridge_port','group_bridge_port','dispatchPort','dispatchLabel','leadOwnerId','leadOwnerLabel'):
                if ev.get(k) and not m.get(k):
                    m[k] = ev.get(k)
            # mantém o PDF/diagnóstico visível mesmo que a bolha real não o tenha
            if not m.get('mediaUrl') and ev.get('mediaUrl'):
                for k in ('mediaUrl', 'mediaName', 'mediaType', 'mimetype', 'mediaPath'):
                    if ev.get(k) and not m.get(k):
                        m[k] = ev.get(k)
            break
    return [m for m in msgs if id(m) not in consumed]

def _conversation_permission_context(port, chat):
    """Resumo mínimo para checar permissão de uma conversa sem chamar conversations()."""
    conv={'id':f'{int(port)}::{chat}','port':int(port),'chat':chat,'title':'','subtitle':'','displayPhone':'','realJid':'','_directVisible':False,'_sdrHintUid':''}
    email=''; empresa=''
    for m in read_history(int(port)):
        if not isinstance(m, dict) or not message_matches_chat(m, chat):
            continue
        if not conv.get('_sdrHintUid'):
            hu=_conversation_sdr_hint_from_msg(m)
            if hu: conv['_sdrHintUid']=hu
        if not email and m.get('email'):
            email=str(m.get('email')).strip()
        if not empresa:
            e=clean_title_value(m.get('empresa'))
            if e: empresa=e
        if not conv.get('realJid'):
            rj=real_jid_from(m)
            if rj and not is_lid(rj): conv['realJid']=rj
        if not conv.get('title'):
            best=clean_title_value(m.get('empresa') or m.get('lead'))
            if best: conv['title']=best
    conv['displayPhone']=short_phone(conv.get('realJid') or '') or short_phone(chat)
    if not conv.get('title'):
        conv['title']=conv['displayPhone'] or 'Lead sem número'
    return conv, email, empresa

def _institutional_dispatch_rows_for_chat(port, chat):
    key=(int(port), canonical_chat_id(chat)); now=time.time(); cached=DISPATCH_ROWS_CACHE.get(key)
    if cached and now-cached.get('ts',0) < DISPATCH_ROWS_TTL:
        return list(cached.get('rows') or [])
    # Caminho rápido: ledger operacional é a fonte de auditoria institucional.
    # Não use o carregador completo de portas aqui: ele varre histórico inteiro e travava /api/messages.
    rows=[]
    for m in wpp_envios_fastlane_events([int(port)], max_age_hours=24*30):
        if isinstance(m, dict) and message_matches_chat(m, chat) and is_institutional_dispatch_msg(m):
            rows.append(m)
    DISPATCH_ROWS_CACHE[key]={'ts':now,'rows':rows}
    return list(rows)

def institutional_conv_readonly_allowed(port, chat):
    if not is_institutional_port(port):
        return False
    rows=_institutional_dispatch_rows_for_chat(port, chat)
    return bool(rows and institutional_dispatch_owner_uid_from_msgs(rows))

def conversation_id_allowed(uid, conv_id):
    now=time.time(); cache_key=(uid, conv_id); cached=CONVERSATION_PERMISSION_CACHE.get(cache_key)
    if cached and now-cached.get('ts',0) < CONVERSATION_PERMISSION_TTL:
        return bool(cached.get('allowed'))
    allowed=False
    if '::' not in conv_id:
        return False
    p_s, chat = conv_id.split('::',1)
    try: port=int(p_s)
    except Exception: return False
    if is_institutional_port(port):
        # Mesmo supervisor/admin não abre conversa privada de chip pessoal.
        # Só auditoria de envio institucional para SDR é permitida; SDR comum
        # só abre auditoria do próprio negócio.
        rows=_institutional_dispatch_rows_for_chat(port, chat)
        owner= institutional_dispatch_owner_uid_from_msgs(rows)
        if rows and owner:
            allowed = True if user_can_view_all(uid) else (owner == uid)
    elif user_can_view_all(uid) or port in set(effective_ports(uid)):
        allowed=True
    else:
        conv,email,empresa=_conversation_permission_context(port, chat)
        allowed=bool(conversation_allowed(uid, conv, email=email, empresa=empresa).get('allowed'))
    CONVERSATION_PERMISSION_CACHE[cache_key]={'ts':now,'allowed':allowed}
    return allowed

def _raw_history_for_chat(port, chat):
    p=DATA_DIR / f'history_{int(port)}.json'
    try:
        data=json.loads(p.read_text(encoding='utf-8')) if p.exists() else []
    except Exception:
        data=[]
    out=[]
    for m in (data if isinstance(data,list) else []):
        if not isinstance(m, dict) or not message_matches_chat(m, chat):
            continue
        mm=dict(m); mm['port']=int(mm.get('port') or port); mm['portLabel']=PORTS.get(int(port),{}).get('label',str(port))
        raw_ts=mm.get('timestamp'); fixed_ts=normalize_channel_timestamp(raw_ts)
        if fixed_ts and raw_ts is not None and abs(float(raw_ts or 0)-fixed_ts) > 1:
            mm['timestampRaw']=raw_ts; mm['timestamp']=fixed_ts; mm['timestampAdjustedBRT']=True
        out.append(mm)
    return out

def _timeline_source_for_chat(port, chat):
    """Caminho rápido para /api/messages: filtra o chat antes de varrer/mesclar ledger.
    Preserva privacidade de comunicador: só mostra outbound operacional do ledger e
    resposta recebida daquele chat operacional.
    """
    raw=_raw_history_for_chat(port, chat)
    if not is_institutional_port(port):
        raw.extend([m for m in wpp_envios_fastlane_events([int(port)]) if message_matches_chat(m, chat)])
        out=_dedupe_loaded_items(raw); out.sort(key=lambda x: float(x.get('timestamp') or 0)); return out
    ledger=[m for m in wpp_envios_fastlane_events([int(port)], max_age_hours=24*14) if isinstance(m,dict) and is_institutional_dispatch_msg(m) and message_matches_chat(m, chat)]
    has_ledger=bool(ledger)
    out=[]; consumed=set()
    for m in raw:
        if m.get('fromMe'):
            if not is_institutional_dispatch_msg(m):
                # conversa pessoal do comunicador: nunca expor
                continue
            out.append(m); continue
        if has_ledger:
            mm=dict(m); mm['readOnlyInstitutionalReply']=True; _enrich_dispatch_identity(mm); out.append(mm)
    # Garante auditoria operacional mesmo quando a bolha real ainda não chegou.
    for ev in ledger:
        found=False
        for m in out:
            if _same_dispatch_payload(ev,m) or (_event_message_id(ev) and _event_message_id(ev)==_event_message_id(m)):
                found=True; break
        if not found:
            ee=dict(ev); ee['timestampSource']=ee.get('timestampSource') or 'ledger'; out.append(ee)
    out=_dedupe_loaded_items(out); out.sort(key=lambda x: float(x.get('timestamp') or 0)); return out

def messages_for(uid, conv_id, autotranscribe=False):
    if '::' not in conv_id: return []
    p_s, chat = conv_id.split('::',1)
    try: port=int(p_s)
    except: return []
    if not conversation_id_allowed(uid, conv_id): return []
    msgs=[]
    source_msgs = _timeline_source_for_chat(port, chat)
    for m in source_msgs:
        if not isinstance(m, dict) or not message_matches_chat(m, chat):
            continue
        if is_institutional_port(port) and m.get('fromMe') and not is_institutional_dispatch_msg(m):
            continue
        mm=dict(m, port=int(m.get('port') or port), portLabel=PORTS.get(int(m.get('port') or port),{}).get('label',str(m.get('port') or port)))
        _enrich_dispatch_identity(mm)
        msgs.append(mm)
    # Não transcrever de forma síncrona no GET /api/messages: no mobile isso deixava
    # o header abrir, mas a timeline continuava com "Nenhum lead aberto" enquanto
    # o faster-whisper rodava. O áudio aparece imediatamente; /api/transcribe roda
    # sob demanda e atualiza a conversa depois.
    return enrich_audio_transcripts(collapse_automation(msgs), autotranscribe=(autotranscribe and not is_institutional_port(port)), max_auto=2)

# ---- CH-018: envio de arquivos/áudios pela UI -------------------------------
def decode_data_base64(raw):
    """Decodifica `dataBase64` aceitando base64 puro OU data URL (data:...;base64,xxx).

    Devolve os bytes. Levanta ValueError se vazio/ inválido.
    """
    s = str(raw or '').strip()
    if not s:
        raise ValueError('dataBase64 vazio')
    # data URL: "data:<mime>;base64,<payload>" — fica só com o payload.
    if s.startswith('data:'):
        comma = s.find(',')
        if comma == -1:
            raise ValueError('data URL malformado')
        s = s[comma + 1:]
    # remove espaços/quebras de linha que clientes às vezes injetam
    s = ''.join(s.split())
    try:
        return base64.b64decode(s, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError('dataBase64 não é base64 válido')

def safe_upload_name(file_name):
    """Nome de arquivo seguro com timestamp para evitar colisão.

    Mantém só basename, troca caracteres perigosos por '_' e prefixa um timestamp.
    """
    base = os.path.basename(str(file_name or '').strip()) or 'arquivo'
    base = base.replace('\x00', '')
    # só permite letras/números/.-_ e espaço (vira _); evita path traversal e shell tricks
    base = re.sub(r'[^A-Za-z0-9._\- ]', '_', base).strip().replace(' ', '_')
    base = base.lstrip('.') or 'arquivo'
    base = base[:120]
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-') + secrets.token_hex(3)
    return f'{stamp}_{base}'

def post_json(url, payload, timeout=20):
    data=json.dumps(payload, ensure_ascii=False).encode('utf-8')
    last_err=None
    for attempt in range(2):
        req=urllib.request.Request(url, data=data, headers={'Content-Type':'application/json'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8') or '{}')
        except urllib.error.HTTPError as e:
            body=e.read().decode('utf-8', errors='ignore')
            last_err=RuntimeError(body or str(e))
            if attempt == 0 and ('Connection Closed' in body or 'Not connected' in body or 'timeout' in body.lower()):
                time.sleep(1.5)
                continue
            raise last_err
        except Exception as e:
            last_err=e
            if attempt == 0 and ('Connection Closed' in str(e) or 'Not connected' in str(e) or 'timeout' in str(e).lower()):
                time.sleep(1.5)
                continue
            raise
    raise last_err

def bridge_status(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/status', timeout=2) as r:
            return json.loads(r.read().decode())
    except Exception as e: return {'connected':False,'error':str(e)}

# ---- CH-030: lateral HubSpot real (read-only) -------------------------------
# O SDR vê lead/negócio do HubSpot sem trocar de aba. TUDO é read-only: nenhum
# PATCH/POST de escrita parte daqui. O token nunca aparece em log/HTML e um cache
# em memória (5 min, por telefone/empresa/email) evita martelar a API a cada
# abertura de conversa. Se o token faltar ou a API cair, o painel segue funcionando.
HUBSPOT_ENV = Path('/root/.hermes/credentials/hubspot.env')
HUBSPOT_API = 'https://api.hubapi.com'
LOGO_PATH = PROJECT / 'motor' / 'logo' / 'zydon_full_black.png'
LOGO_DARK_PATH = PROJECT / 'motor' / 'logo' / 'zydon_full.png'
HUBSPOT_TTL = 300  # segundos (5 min)
# Propriedades onde o telefone do WhatsApp pode estar gravado no contato.
HUBSPOT_PHONE_PROPS = ('hs_whatsapp_phone_number', 'hs_searchable_calculated_phone_number', 'phone', 'mobilephone')
HUBSPOT_FORM_PROPS = [
    'qual_erp_utiliza_',
    'selecione_o_sistema_de_gesto_erp',
    'vende_em_loja_virtual_',
    'voc_acredita_que_o_seu_cliente_compraria_sozinho_na_sua_loja_24h_por_dia_sem_precisar_de_vendedor',
    'qual_o_faturamento_anual_da_sua_empresa_',
    'e_qual_faturamento_anual_da_sua_empresa',
    'selecione_a_faixa_de_faturamento',
    'selecione_a_faixa_de_faturamento_atual_por_ano_da_sua_empresa',
    'qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados',
    'voc_vende_para_quem_ex_padarias_restaurantes_petshop_autopeas_supermercados',
    'principais_dores',
    'qual_seria_o_maior_problema_que_voc_enfrenta_em_sua_operao_atualmente',
    'quantas_pessoas_atuam_na_sua_empresa',
    'quantos_vendedores_internos_sua_empresa_possui',
    'de_qual_forma_mais_vende_hoje_em_dia',
]
HUBSPOT_CONTACT_PROPS = ['firstname', 'lastname', 'email', 'company', 'phone', 'mobilephone',
                         'hs_whatsapp_phone_number', 'lifecyclestage', 'hubspot_owner_id'] + HUBSPOT_FORM_PROPS
HUBSPOT_DEAL_PROPS = ['dealname', 'dealstage', 'pipeline', 'hubspot_owner_id', 'amount', 'closedate']
HUBSPOT_PIPE_ACTIVITY_TASK_PROPS = ['hs_task_subject','hs_task_body','hs_task_status','hs_timestamp','hs_task_type','hubspot_owner_id']
HUBSPOT_PIPE_ACTIVITY_NOTE_PROPS = ['hs_note_body','hs_timestamp','hubspot_owner_id']
HUBSPOT_PIPE_ACTIVITY_CALL_PROPS = ['hs_call_title','hs_call_body','hs_call_status','hs_timestamp','hubspot_owner_id']
HUBSPOT_OWNER_LABELS = {
    '86265630': 'Breno',
    '88063842': 'Sarah',
    '85778446': 'Lucas Batista',
}
HUBSPOT_PIPELINE_LABELS = {'671008549': 'Principal'}
MANAGER_MEETING_GOAL_MONTH = 40
INTRO_STAGE_PROPS = ('hs_v2_date_entered_1269308723', 'hs_v2_date_entered_984278846')
# Etapas usadas na visão de geração de demanda / Foco SDR. Leitura pura HubSpot.
DEMAND_PIPELINE_STAGES = ['984052829', '1214320997', '998099482', '1151853491', '1376131958']
HUBSPOT_PORTAL_ID = '48590774'
HUBSPOT_STAGE_LABELS = {
    '984052829': 'Lead Sem Contato',
    '1214320997': 'Primeiro Contato',
    '998099482': 'Retorno Contato',
    '1151853491': 'Diagnóstico SDR 📙🔖',
    '1376131958': 'No Show',
    '1269308723': 'Introdução',
    '1269710168': 'Diagnóstico EC',
    '990617426': 'Apresentação Comercial 🎯',
    '1269308724': 'Apresentação Técnica 💻',
    '984052831': 'Proposta / Negociação',
    '1213797817': 'Termos e condições',
    '984052834': 'Negócio fechado',
    '984052835': 'Negócio perdido',
}
_hs_cache = {}  # chave -> (expira_em_epoch, valor)
_send_dedupe = {}  # chave -> expira_em_epoch; proteção contra duplo Enter/delay
SEND_DEDUPE_TTL = 8

def _hubspot_token():
    """Token do HubSpot via env ou credentials/hubspot.env. '' se não houver (sem raise)."""
    val = os.environ.get('HUBSPOT_API_KEY', '')
    if val:
        return val.strip()
    try:
        if HUBSPOT_ENV.exists():
            for line in HUBSPOT_ENV.read_text(encoding='utf-8').splitlines():
                if line.startswith('HUBSPOT_API_KEY='):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ''

def _hs_cache_get(key):
    item = _hs_cache.get(key)
    if not item:
        return None
    exp, val = item
    if exp < time.time():
        _hs_cache.pop(key, None)
        return None
    return val

def _hs_cache_set(key, val):
    _hs_cache[key] = (time.time() + HUBSPOT_TTL, val)

def _dedupe_send(uid, port, chat, kind, fingerprint):
    """True se este envio deve ser bloqueado como duplicado recente."""
    now = time.time()
    # limpeza leve
    for k, exp in list(_send_dedupe.items())[:200]:
        if exp < now:
            _send_dedupe.pop(k, None)
    key = f'{uid}|{port}|{chat}|{kind}|{fingerprint}'
    exp = _send_dedupe.get(key)
    if exp and exp >= now:
        return True
    _send_dedupe[key] = now + SEND_DEDUPE_TTL
    return False

def _hs_request(method, path, token, payload=None, timeout=12):
    """Chamada crua à API do HubSpot. Levanta em erro HTTP (sem vazar o token)."""
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(HUBSPOT_API + path, data=data,
                                 headers={'Authorization': 'Bearer ' + token,
                                          'Content-Type': 'application/json'}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read().decode('utf-8')
        return json.loads(b) if b else {}

def _looks_like_company(s):
    """Título serve como empresa só se tiver ao menos uma letra (telefone puro não)."""
    s = clean_title_value(s)
    return bool(s) and any(ch.isalpha() for ch in s)

def _real_phone_digits(conv):
    """Dígitos do telefone REAL da conversa (nunca de @lid). '' se protegido."""
    dp = ''.join(ch for ch in str(conv.get('displayPhone') or '') if ch.isdigit())
    if dp:
        return dp
    chat = str(conv.get('chat') or '')
    if _is_real_jid(chat):
        d = ''.join(ch for ch in chat if ch.isdigit())
        if 12 <= len(d) <= 13 and d.startswith('55'):
            return d
    return ''

def _conv_hubspot_hints(port, chat):
    """Extrai email/empresa dos metadados das mensagens da conversa (eventos cron)."""
    email = ''
    empresa = ''
    for m in read_history(port):
        if not isinstance(m, dict) or not message_matches_chat(m, chat):
            continue
        if not email and m.get('email'):
            email = str(m.get('email')).strip()
        if not empresa:
            e = clean_title_value(m.get('empresa'))
            if e:
                empresa = e
        if email and empresa:
            break
    return email, empresa

def _hs_search_contact(token, filter_groups):
    payload = {'filterGroups': filter_groups, 'properties': HUBSPOT_CONTACT_PROPS, 'limit': 1}
    res = _hs_request('POST', '/crm/v3/objects/contacts/search', token, payload)
    results = res.get('results') or []
    return results[0] if results else None

def _phone_search_candidates(digits):
    """Variações BR para casar telefone WhatsApp x HubSpot.

    HubSpot pode guardar: +55 formatado, só DDD+número, sem o nono dígito,
    só últimos 8/9 dígitos, ou em propriedades calculadas normalizadas.
    """
    d=''.join(ch for ch in str(digits or '') if ch.isdigit())
    out=[]
    def add(v):
        v=''.join(ch for ch in str(v or '') if ch.isdigit())
        if len(v) >= 8 and v not in out:
            out.append(v)
    add(d)
    local=d[2:] if d.startswith('55') and len(d)>4 else d
    add(local)
    # BR móvel: 55 + DDD + 9 + 8 dígitos. Alguns CRMs guardam com/sem o 9.
    if d.startswith('55') and len(d)==13:
        add(d[:4] + d[5:])      # 55 + DDD + número 8d
        add(d[2:4] + d[5:])    # DDD + número 8d
    if d.startswith('55') and len(d)==12:
        add(d[:4] + '9' + d[4:])      # 55 + DDD + 9 + número 8d
        add(d[2:4] + '9' + d[4:])    # DDD + 9 + número 8d
    if len(local)==11:
        add(local[:2] + local[3:])
    if len(local)==10:
        add(local[:2] + '9' + local[2:])
    # Últimos dígitos: útil quando HubSpot formatou/normalizou diferente.
    add(d[-9:])
    add(d[-8:])
    return out

def _hs_search_contact_by_phone(digits, token):
    """Procura contato por telefone em todas as propriedades possíveis (OR)."""
    candidates = _phone_search_candidates(digits)
    if not candidates:
        return None
    for val in candidates:
        groups = [{'filters': [{'propertyName': p, 'operator': 'CONTAINS_TOKEN', 'value': val}]}
                  for p in HUBSPOT_PHONE_PROPS]
        try:
            contact = _hs_search_contact(token, groups)
        except Exception:
            continue
        if contact:
            return contact
    return None

def _hs_search_contact_by_email(email, token):
    if not email:
        return None
    return _hs_search_contact(token, [{'filters': [{'propertyName': 'email', 'operator': 'EQ', 'value': email}]}])

def _hs_search_contact_by_company(company, token):
    if not _looks_like_company(company):
        return None
    return _hs_search_contact(token, [{'filters': [{'propertyName': 'company',
                                                    'operator': 'CONTAINS_TOKEN',
                                                    'value': clean_title_value(company)}]}])

def _hs_safe_contact(contact):
    """Só campos seguros e explícitos — nunca devolve o objeto cru/token."""
    p = contact.get('properties') or {}
    return {
        'id': str(contact.get('id') or ''),
        'firstname': p.get('firstname') or '',
        'lastname': p.get('lastname') or '',
        'email': p.get('email') or '',
        'company': p.get('company') or '',
        'phone': p.get('phone') or '',
        'mobilephone': p.get('mobilephone') or '',
        'whatsapp': p.get('hs_whatsapp_phone_number') or '',
        'lifecyclestage': p.get('lifecyclestage') or '',
        'hubspot_owner_id': p.get('hubspot_owner_id') or '',
        'hubspot_owner_name': HUBSPOT_OWNER_LABELS.get(p.get('hubspot_owner_id') or '', p.get('hubspot_owner_id') or ''),
        'form': {k: (p.get(k) or '') for k in HUBSPOT_FORM_PROPS},
    }

def _hs_deal_meetings(deal_id, token):
    """Reuniões associadas ao negócio. Retorna lista segura; falha = lista vazia."""
    if not deal_id:
        return []
    try:
        assoc = _hs_request('GET', f'/crm/v4/objects/deals/{deal_id}/associations/meetings', token)
    except Exception:
        return []
    ids=[]
    for r in (assoc.get('results') or []):
        rid=str((r.get('toObjectId') or r.get('id') or '')).strip()
        if rid and rid not in ids:
            ids.append(rid)
    if not ids:
        return []
    props=['hs_meeting_title','hs_timestamp','hs_meeting_start_time','hs_meeting_end_time','hs_meeting_outcome','hubspot_owner_id']
    try:
        res=_hs_request('POST','/crm/v3/objects/meetings/batch/read',token,{'properties':props,'inputs':[{'id':i} for i in ids]})
    except Exception:
        return []
    out=[]
    for m in (res.get('results') or []):
        p=m.get('properties') or {}
        ts=p.get('hs_meeting_start_time') or p.get('hs_timestamp') or ''
        out.append({
            'id':str(m.get('id') or ''),
            'title':p.get('hs_meeting_title') or 'Reunião',
            'timestamp':ts,
            'endTime':p.get('hs_meeting_end_time') or '',
            'outcome':p.get('hs_meeting_outcome') or '',
            'ownerId':p.get('hubspot_owner_id') or '',
            'ownerName':HUBSPOT_OWNER_LABELS.get(p.get('hubspot_owner_id') or '', p.get('hubspot_owner_id') or ''),
        })
    out.sort(key=lambda x: x.get('timestamp') or '', reverse=True)
    return out[:5]


def _hs_contact_deals(cid, token):
    """Negócios associados ao contato (associations v4 + batch read)."""
    if not cid:
        return []
    try:
        assoc = _hs_request('GET', f'/crm/v4/objects/contacts/{cid}/associations/deals', token)
    except Exception:
        return []
    ids = []
    for r in (assoc.get('results') or []):
        did = r.get('toObjectId') or r.get('id')
        if did:
            ids.append(str(did))
    ids = ids[:25]
    if not ids:
        return []
    try:
        payload = {'properties': HUBSPOT_DEAL_PROPS, 'inputs': [{'id': i} for i in ids]}
        res = _hs_request('POST', '/crm/v3/objects/deals/batch/read', token, payload)
    except Exception:
        return []
    out = []
    for d in (res.get('results') or []):
        p = d.get('properties') or {}
        deal_id=str(d.get('id') or '')
        out.append({
            'id': deal_id,
            'dealname': p.get('dealname') or '',
            'dealstage': p.get('dealstage') or '',
            'dealstage_label': HUBSPOT_STAGE_LABELS.get(p.get('dealstage') or '', p.get('dealstage') or ''),
            'pipeline': p.get('pipeline') or '',
            'pipeline_label': HUBSPOT_PIPELINE_LABELS.get(p.get('pipeline') or '', p.get('pipeline') or ''),
            'hubspot_owner_id': p.get('hubspot_owner_id') or '',
            'hubspot_owner_name': HUBSPOT_OWNER_LABELS.get(p.get('hubspot_owner_id') or '', p.get('hubspot_owner_id') or ''),
            'amount': p.get('amount') or '',
            'closedate': p.get('closedate') or '',
            'meetings': _hs_deal_meetings(deal_id, token),
        })
    return out

def _hs_cache_key(conv, email='', empresa=''):
    """Chave de cache da busca HubSpot p/ a conversa (telefone > email > empresa).

    Mesma ordem usada em hubspot_lookup(); '' quando não há identificador útil.
    Reutilizada para ler o cache SEM rede (ex.: marcar reunião na lista).
    """
    digits = _real_phone_digits(conv)
    company = empresa or conv.get('title') or ''
    if digits:
        return 'phone:' + digits
    if email:
        return 'email:' + email.lower()
    if _looks_like_company(company):
        return 'company:' + clean_title_value(company).lower()
    return ''

def hubspot_lookup(conv, email='', empresa=''):
    """Busca read-only contato+negócios no HubSpot p/ uma conversa. Cacheada 5 min.

    Ordem: telefone real > email (metadados) > empresa/título. Sempre devolve um
    dict seguro com `found`/`configured`; nunca levanta para o caller.
    """
    base = {'found': False, 'configured': True, 'contact': None, 'deals': [], 'source': ''}
    token = _hubspot_token()
    if not token:
        return {**base, 'configured': False}
    company = empresa or conv.get('title') or ''
    cache_key = _hs_cache_key(conv, email=email, empresa=empresa)
    if not cache_key:
        return base
    digits = _real_phone_digits(conv)
    cached = _hs_cache_get(cache_key)
    if cached is not None:
        return cached
    result = dict(base)
    try:
        contact = None
        source = ''
        if digits:
            contact = _hs_search_contact_by_phone(digits, token)
            if contact:
                source = 'phone'
        if not contact and email:
            contact = _hs_search_contact_by_email(email, token)
            if contact:
                source = 'email'
        if not contact and _looks_like_company(company):
            contact = _hs_search_contact_by_company(company, token)
            if contact:
                source = 'company'
        if contact:
            result = {'found': True, 'configured': True, 'source': source,
                      'contact': _hs_safe_contact(contact),
                      'deals': _hs_contact_deals(contact.get('id'), token)}
    except Exception:
        result = {**base, 'error': 'hubspot_unavailable'}
    _hs_cache_set(cache_key, result)
    return result

# ---- CH-057: visibilidade compartilhada por owner do deal --------------------
HUBSPOT_OWNER_UIDS = {
    '86265630': 'breno',
    '88063842': 'sarah',
    '85778446': 'lucas_batista',
}

def _hubspot_owner_to_uid(owner_id='', owner_name=''):
    uid = HUBSPOT_OWNER_UIDS.get(str(owner_id or '').strip())
    if uid:
        return uid
    return sdr_hint_to_uid(owner_name)

def _load_shared_visibility_cache():
    try:
        if SHARED_VISIBILITY_CACHE_FILE.exists():
            data=json.loads(SHARED_VISIBILITY_CACHE_FILE.read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}

def _save_shared_visibility_cache(data):
    try:
        SHARED_VISIBILITY_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp=SHARED_VISIBILITY_CACHE_FILE.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        try: os.chmod(tmp, 0o600)
        except Exception: pass
        tmp.replace(SHARED_VISIBILITY_CACHE_FILE)
        try: os.chmod(SHARED_VISIBILITY_CACHE_FILE, 0o600)
        except Exception: pass
    except Exception:
        pass

def _shared_owner_from_hubspot(conv, email='', empresa=''):
    """Retorna owner uid pelo NEGÓCIO associado; contato é só fallback fraco."""
    look=hubspot_lookup(conv, email=email, empresa=empresa)
    if not look.get('found'):
        return {'ownerUid':'', 'source':'none', 'dealId':'', 'dealName':''}
    for d in (look.get('deals') or []):
        uid=_hubspot_owner_to_uid(d.get('hubspot_owner_id'), d.get('hubspot_owner_name'))
        if uid:
            return {'ownerUid':uid, 'source':'deal', 'dealId':str(d.get('id') or ''), 'dealName':str(d.get('dealname') or '')}
    # Fallback apenas informativo: se não houver deal, usa owner do contato.
    c=look.get('contact') or {}
    uid=_hubspot_owner_to_uid(c.get('hubspot_owner_id'), c.get('hubspot_owner_name'))
    return {'ownerUid':uid, 'source':'contact' if uid else 'none', 'dealId':'', 'dealName':''}

def shared_visibility_info(conv, email='', empresa='', refresh=False):
    """Quem pode ver conversa de chip compartilhado. Cache pequeno em disco."""
    cid=str(conv.get('id') or '')
    now=time.time()
    cache=_load_shared_visibility_cache()
    ent=cache.get(cid)
    if isinstance(ent, dict) and not refresh and float(ent.get('expiresAt') or 0) > now:
        return ent
    info=_shared_owner_from_hubspot(conv, email=email, empresa=empresa)
    ent={
        'ownerUid': info.get('ownerUid') or '',
        'source': info.get('source') or 'none',
        'dealId': info.get('dealId') or '',
        'dealName': info.get('dealName') or '',
        'checkedAt': now,
        'expiresAt': now + SHARED_VISIBILITY_TTL,
    }
    cache[cid]=ent
    # limpeza leve
    for k,v in list(cache.items())[:500]:
        if isinstance(v, dict) and float(v.get('expiresAt') or 0) < now - 86400:
            cache.pop(k, None)
    _save_shared_visibility_cache(cache)
    return ent

def conversation_allowed(uid, conv, email='', empresa='', use_hubspot=True):
    """Permissão de leitura da conversa.

    Direto: porta do usuário/admin. Compartilhado: porta Mariana/Lucas/Rafael e
    metadado `sdr` OU HubSpot indicam que o lead/deal pertence ao uid.
    """
    port=int(conv.get('port') or 0)
    allowed=set(effective_ports(uid))
    if user_can_view_all(uid) or port in allowed:
        return {'allowed': True, 'shared': False, 'ownerUid': uid, 'reason': ''}
    if port not in SHARED_DEAL_VISIBILITY_PORTS:
        return {'allowed': False, 'shared': False, 'ownerUid': '', 'reason': ''}
    hint=conv.get('_sdrHintUid') or ''
    if hint == uid:
        return {'allowed': True, 'shared': True, 'ownerUid': uid,
                'reason': f"Conversa iniciada por {PORTS.get(port,{}).get('label','chip compartilhado')} para lead/deal do SDR."}
    # Inbox/listagem não pode ficar lenta: sem metadado local, usa apenas cache
    # HubSpot já existente; endpoints específicos podem chamar HubSpot sob demanda.
    if not use_hubspot:
        ent=_load_shared_visibility_cache().get(str(conv.get('id') or '')) or {}
        if isinstance(ent, dict) and float(ent.get('expiresAt') or 0) > time.time() and ent.get('ownerUid') == uid:
            return {'allowed': True, 'shared': True, 'ownerUid': uid,
                    'reason': 'Conversa de chip compartilhado vinculada ao negócio HubSpot deste SDR.'}
        return {'allowed': False, 'shared': False, 'ownerUid': hint, 'reason': ''}
    # Se não há metadado local, tenta HubSpot/cache. Não confia em outro owner.
    info=shared_visibility_info(conv, email=email, empresa=empresa)
    if info.get('ownerUid') == uid:
        src='negócio HubSpot' if info.get('source')=='deal' else 'contato HubSpot'
        return {'allowed': True, 'shared': True, 'ownerUid': uid,
                'reason': f"Conversa de chip compartilhado vinculada ao {src} deste SDR."}
    return {'allowed': False, 'shared': False, 'ownerUid': info.get('ownerUid') or hint or '', 'reason': ''}

# ---- CH-031: escrita no HubSpot (task / note) a partir da conversa ----------
# Endpoint POST /api/hubspot/action. Mantém a integridade do CRM: nunca cria
# objeto sem contato associado; usa associações HUBSPOT_DEFINED com typeIds
# padrão; registra auditoria local. Nunca vaza o token nas mensagens de erro.
HS_ASSOC = {
    'task_contact': 204,   # task -> contact (HUBSPOT_DEFINED)
    'task_deal': 216,      # task -> deal
    'note_contact': 202,   # note -> contact
    'note_deal': 214,      # note -> deal
}
HS_ACTIONS_LOG = PROJECT / 'controle' / 'channel_hubspot_actions.jsonl'
HS_SUBJECT_MAX = 255
HS_BODY_MAX = 8000
HS_TRANSCRIPT_BODY_MAX = 60000
BRT_TZ = timezone(timedelta(hours=-3))  # America/Sao_Paulo (sem horário de verão)

def _hs_clean_text(s, limit):
    """Sanitiza texto livre: remove NUL, faz strip e limita o tamanho."""
    return str(s or '').replace('\x00', '').strip()[:limit]

def _hs_now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def _fmt_brt_ts(ts):
    try:
        return datetime.fromtimestamp(float(ts or 0), BRT_TZ).strftime('%d/%m/%Y %H:%M')
    except Exception:
        return ''

def _msg_text_for_transcript(m):
    parts=[]
    txt=' '.join(str((m or {}).get('text') or '').split()).strip()
    if txt:
        parts.append(txt)
    tr=' '.join(str((m or {}).get('transcript') or '').split()).strip()
    if tr and tr.lower() not in txt.lower():
        parts.append('[áudio transcrito] ' + tr)
    media=str((m or {}).get('mediaName') or (m or {}).get('fileName') or '').strip()
    if media:
        parts.append('[anexo] ' + media)
    if (m or {}).get('automation'):
        parts.append('[' + str((m or {}).get('automation')) + ']')
    return ' | '.join(parts) or '[mensagem sem texto]'

def build_whatsapp_history_note(uid, conv_id, conv=None, contact=None, deal=None):
    """Monta uma nota de HubSpot com todo histórico WhatsApp permitido até agora."""
    rows=messages_for(uid, conv_id)
    title=(conv or {}).get('title') or (contact or {}).get('company') or conv_id
    phone=(conv or {}).get('displayPhone') or short_phone((conv or {}).get('chat') or '')
    owner=(conv or {}).get('dealOwnerLabel') or ''
    chip=(conv or {}).get('portLabel') or PORTS.get(int((conv or {}).get('port') or 0),{}).get('label','')
    now_brt=datetime.now(BRT_TZ).strftime('%d/%m/%Y %H:%M')
    header=[
        'Histórico WhatsApp — Channel Zydon',
        f'Gerado em: {now_brt} BRT',
        f'Lead/empresa: {title}',
    ]
    if phone: header.append(f'WhatsApp: {phone}')
    cemail=(contact or {}).get('email') or ''
    if cemail: header.append(f'E-mail HubSpot: {cemail}')
    if owner: header.append(f'Proprietário/SDR: {owner}')
    if chip: header.append(f'Chip/canal: {chip}')
    if deal and deal.get('dealname'):
        header.append(f'Negócio: {deal.get("dealname")}')
    header.append(f'Total de mensagens incluídas: {len(rows)}')
    lines=['\n'.join(header), '', '--- Conversa ---']
    for m in rows:
        who='Zydon' if m.get('fromMe') else 'Lead'
        ts=_fmt_brt_ts(m.get('timestamp'))
        src=source_label(m) or m.get('portLabel') or ''
        prefix=f'[{ts}] {who}' + (f' ({src})' if src else '')
        lines.append(prefix + ': ' + _msg_text_for_transcript(m))
    body='\n'.join(lines).strip()
    if len(body) > HS_TRANSCRIPT_BODY_MAX:
        tail='\n\n[Histórico truncado automaticamente pelo Channel para caber no limite seguro da nota HubSpot.]'
        body=body[:HS_TRANSCRIPT_BODY_MAX-len(tail)] + tail
    return body

def _hs_due_timestamp(due):
    """hs_timestamp (ISO UTC) conforme due: today|tomorrow|none."""
    now_utc = datetime.now(timezone.utc)
    if due == 'today':
        dt = now_utc.astimezone(BRT_TZ).replace(hour=23, minute=59, second=0, microsecond=0).astimezone(timezone.utc)
    elif due == 'tomorrow':
        dt = (now_utc.astimezone(BRT_TZ) + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    else:  # none / desconhecido -> agora + 1h
        dt = now_utc + timedelta(hours=1)
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

def _hs_create_object(obj, properties, assoc_specs, token):
    """Cria objeto HubSpot (tasks/notes) com associações. Retorna (id, error).

    assoc_specs: lista de (to_id, association_type_id). `error` é uma mensagem
    sanitizada (nunca contém o token; só código HTTP + detalhe da API).
    """
    associations = []
    for to_id, type_id in assoc_specs:
        if not to_id:
            continue
        associations.append({
            'to': {'id': str(to_id)},
            'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': int(type_id)}],
        })
    payload = {'properties': properties}
    if associations:
        payload['associations'] = associations
    try:
        res = _hs_request('POST', f'/crm/v3/objects/{obj}', token, payload)
        return str(res.get('id') or ''), ''
    except urllib.error.HTTPError as e:
        detail = ''
        try:
            detail = e.read().decode('utf-8')[:300]
        except Exception:
            detail = ''
        return '', f'HubSpot {e.code}: {detail}'.strip()
    except Exception:
        return '', 'HubSpot indisponível'

def _hs_patch_object(obj, obj_id, properties, token):
    """PATCH seguro de objeto HubSpot. Retorna erro sanitizado ou ''."""
    if not obj_id or not properties:
        return 'objeto/propriedades ausentes'
    try:
        _hs_request('PATCH', f'/crm/v3/objects/{obj}/{obj_id}', token, {'properties': properties})
        return ''
    except urllib.error.HTTPError as e:
        detail=''
        try: detail=e.read().decode('utf-8')[:300]
        except Exception: detail=''
        return f'HubSpot {e.code}: {detail}'.strip()
    except Exception:
        return 'HubSpot indisponível'


PLAYBOOK_ALLOWED_STAGES = {'1269308723': 'Introdução'}
PLAYBOOK_OWNER_IDS = {'86265630': 'Breno', '88063842': 'Sarah', '85778446': 'Lucas Batista'}

def _safe_hs_property_name(name):
    name=str(name or '').strip()
    return name if re.match(r'^[a-zA-Z0-9_]{2,80}$', name) else ''

def _hs_audit_log(entry):
    """Acrescenta uma linha JSON ao log de auditoria (controle/...jsonl)."""
    try:
        HS_ACTIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(HS_ACTIONS_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        try:
            os.chmod(HS_ACTIONS_LOG, 0o600)
        except Exception:
            pass
    except Exception:
        pass

# ---- CH-004: Conexões / saúde dos chips ----------------------------------
# Limite diário sugerido por chip (heurística de risco de bloqueio; sem warm-up
# formal ainda). Volume = mensagens enviadas; respostas = recebidas individuais.
SUGGESTED_DAILY_LIMIT = 30

def _today_str():
    return datetime.now().strftime('%Y-%m-%d')

def _is_individual(chat):
    # Mantém o mesmo filtro de conversations(): nada de grupo/broadcast/status.
    chat = str(chat or '')
    if not chat: return False
    if chat == GROUP_JID or chat.endswith('@g.us'): return False
    if chat == 'status@broadcast' or chat.endswith('@broadcast'): return False
    return True

def chip_metrics(port):
    """Volume enviado e respostas capturadas a partir do histórico do chip."""
    today = _today_str()
    st = {'volumeTotal':0, 'volumeToday':0, 'responses':0, 'responsesToday':0}
    for m in read_history(int(port)):
        if not isinstance(m, dict) or not _is_individual(m.get('chat')):
            continue
        ts = m.get('timestamp')
        try: day = datetime.fromtimestamp(float(ts)).strftime('%Y-%m-%d') if ts else ''
        except Exception: day = ''
        if m.get('fromMe'):
            st['volumeTotal'] += 1
            if day == today: st['volumeToday'] += 1
        else:
            st['responses'] += 1
            if day == today: st['responsesToday'] += 1
    return st

def chip_health(connected, needs_qr, m):
    load_pct = int(round((m['volumeToday'] / max(1, SUGGESTED_DAILY_LIMIT)) * 100))
    response_rate = int(round((m['responses'] / max(1, m['volumeTotal'])) * 100)) if m['volumeTotal'] else 0
    score = 100
    reasons = []
    if needs_qr or not connected:
        score -= 65; reasons.append('desconectado/QR')
    if load_pct >= 100:
        score -= 35; reasons.append('limite diário atingido')
    elif load_pct >= 70:
        score -= 18; reasons.append('volume alto hoje')
    if m['volumeTotal'] < 10:
        score -= 12; reasons.append('chip em aquecimento')
    if m['volumeTotal'] >= 20 and response_rate < 5:
        score -= 10; reasons.append('baixa resposta histórica')
    score = max(0, min(100, score))
    return {'healthScore': score, 'loadPct': load_pct, 'responseRate': response_rate, 'riskReasons': reasons}

def chip_recommendation(connected, needs_qr, m):
    """Recomendação simples: ok / reconectar / aquecer / adicionar_chip + risco."""
    if needs_qr or not connected:
        return 'reconectar', 'alto'
    if m['volumeToday'] >= SUGGESTED_DAILY_LIMIT:
        return 'adicionar_chip', 'alto'
    if m['volumeTotal'] < 10:
        return 'aquecer', 'medio'
    if m['volumeToday'] >= int(SUGGESTED_DAILY_LIMIT * 0.6):
        return 'ok', 'medio'
    return 'ok', 'baixo'

def chips_for(uid):
    """Chips permitidos do usuário com status, volume, risco e ação sugerida."""
    out=[]; online=attention=offline=0
    paused=load_paused_ports()
    for p in effective_ports(uid):
        port=int(p)
        if port in paused:
            continue
        meta=PORTS.get(port, {})
        st=bridge_status(port)
        connected=bool(st.get('connected')); needs_qr=bool(st.get('needsQR'))
        err=str(st.get('error') or '')
        m=chip_metrics(port); rec, risk = chip_recommendation(connected, needs_qr, m); health = chip_health(connected, needs_qr, m)
        if connected and not needs_qr: online+=1
        elif needs_qr: attention+=1
        else: offline+=1
        owner=meta.get('owner') or ''
        out.append({
            'port':port,
            'label':meta.get('label') or ('Chip '+str(port)),
            'owner':owner,
            'ownerName':(owner.replace('_',' ').title() if owner else (meta.get('label') or '')),
            'role':meta.get('role') or '',
            'connected':connected, 'needsQR':needs_qr, 'error':err,
            'volumeTotal':m['volumeTotal'], 'volumeToday':m['volumeToday'],
            'responses':m['responses'], 'responsesToday':m['responsesToday'],
            'suggestedLimit':SUGGESTED_DAILY_LIMIT, 'risk':risk, 'recommendation':rec,
            'healthScore':health['healthScore'], 'loadPct':health['loadPct'], 'responseRate':health['responseRate'], 'riskReasons':health['riskReasons'],
            'qrUrl':('/qr?port=%d' % port) if (needs_qr or not connected) else '',
        })
    summary={'total':len(out),'online':online,'attention':attention,'offline':offline,
             'needsAction':sum(1 for c in out if c['recommendation']!='ok')}
    return out, summary

# ---- CH-003: reunião a partir do HubSpot já cacheado (sem rede) --------------
# A lista de conversas NÃO chama a API do HubSpot (custo proibitivo por conversa).
# Em vez disso, lê o cache `_hs_cache` já preenchido quando o SDR abriu a conversa
# (lateral HubSpot). Conforme o uso, mais conversas ganham o marcador de reunião.
def _conv_meeting_from_cache(conv, email='', empresa=''):
    """{has, nextAt}: reunião HubSpot da conversa, lendo só o cache (zero rede)."""
    out = {'has': False, 'nextAt': ''}
    key = _hs_cache_key(conv, email=email, empresa=empresa)
    if not key:
        return out
    cached = _hs_cache_get(key)
    if not isinstance(cached, dict) or not cached.get('found'):
        return out
    stamps = []
    for d in (cached.get('deals') or []):
        for mt in (d.get('meetings') or []):
            ts = str(mt.get('timestamp') or '').strip()
            if ts:
                stamps.append(ts)
    if not stamps:
        return out
    now_iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
    upcoming = sorted(s for s in stamps if s >= now_iso)
    out['has'] = True
    out['nextAt'] = upcoming[0] if upcoming else sorted(stamps)[-1]
    return out

def _conv_hubspot_link_from_cache(conv, email='', empresa=''):
    """Contato/deal HubSpot já conhecido para a lista, sem rede."""
    out={'contactId':'','dealId':''}
    key=_hs_cache_key(conv, email=email, empresa=empresa)
    if not key:
        return out
    cached=_hs_cache_get(key)
    if not isinstance(cached, dict) or not cached.get('found'):
        return out
    contact=cached.get('contact') or {}
    deals=cached.get('deals') or []
    out['contactId']=str(contact.get('id') or '')
    out['dealId']=str((deals[0] or {}).get('id') or '') if deals else ''
    return out

# ---- CH-042: roteamento inteligente de chip -------------------------------
# Quando um SDR tem 2+ chips do mesmo dono, escolhemos o chip mais saudável para
# RESPONDER (sem mudar o chat destino nem a permissão). A saúde de cada porta é
# calculada UMA vez por request (snapshot com TTL curto) para não martelar as
# bridges nem reler históricos a cada conversa.
_RISK_RANK = {'baixo': 0, 'medio': 1, 'alto': 2, '': 1}
_port_health_cache = {}  # port -> (expira_em_epoch, snapshot)
PORT_HEALTH_TTL = 12     # segundos

def _port_health_one(port):
    port = int(port)
    item = _port_health_cache.get(port)
    if item and item[0] >= time.time():
        return item[1]
    st = bridge_status(port)
    connected = bool(st.get('connected')); needs_qr = bool(st.get('needsQR'))
    m = chip_metrics(port)
    health = chip_health(connected, needs_qr, m)
    _, risk = chip_recommendation(connected, needs_qr, m)
    snap = {'port': port, 'connected': connected, 'needsQR': needs_qr,
            'volumeToday': int(m['volumeToday']), 'healthScore': int(health['healthScore']),
            'risk': risk, 'healthy': connected and not needs_qr}
    _port_health_cache[port] = (time.time() + PORT_HEALTH_TTL, snap)
    return snap

def _port_health_snapshot(ports):
    """Mapa port -> saúde, calculado/cacheado por porta (TTL curto)."""
    return {int(p): _port_health_one(p) for p in ports}

def recommend_send_port(uid, original_port, snap=None, target_owner=None):
    """Melhor chip permitido p/ responder esta conversa.

    Normal: mesmo dono da porta original. Conversa compartilhada (CH-057):
    `target_owner=uid` força responder por chip permitido do SDR dono do deal,
    pois a porta original pode ser Mariana/Lucas/Rafael e não deve ser usada pelo SDR.
    """
    try:
        original_port = int(original_port)
    except Exception:
        return {'port': original_port, 'label': '', 'reason': '', 'changed': False, 'health': None}
    allowed = set(effective_ports(uid))
    owner = target_owner or (PORTS.get(original_port, {}).get('owner') or '')
    label_of = lambda p: PORTS.get(p, {}).get('label') or ('Chip ' + str(p))
    orig_label = label_of(original_port)
    if snap is None:
        snap = _port_health_snapshot(sorted(allowed)) if allowed else {}
    # Candidatos: owner alvo E permitidos ao usuário logado.
    cands = [p for p in snap if p in allowed and (PORTS.get(p, {}).get('owner') or '') == owner]
    if not cands and target_owner:
        cands = [p for p in snap if p in allowed]
    healthy = [p for p in cands if snap[p].get('healthy')]
    if not healthy:
        fallback = original_port if original_port in allowed else (cands[0] if cands else (next(iter(sorted(allowed)), original_port)))
        fb_label = label_of(fallback)
        changed = fallback != original_port
        if target_owner and original_port not in allowed:
            reason = f'Conversa veio por {orig_label}; respondendo pelo chip permitido {fb_label}.'
        else:
            reason = f'Enviando por {fb_label} (sem outro chip saudável disponível agora).'
        return {'port': fallback, 'label': fb_label, 'changed': changed,
                'health': (snap.get(fallback) or {}).get('healthScore'),
                'reason': reason}
    def sort_key(p):
        s = snap[p]
        return (_RISK_RANK.get(s.get('risk'), 1), -int(s.get('healthScore') or 0),
                int(s.get('volumeToday') or 0), 0 if p == original_port else 1, p)
    healthy.sort(key=sort_key)
    best = healthy[0]
    best_label = label_of(best)
    if best == original_port:
        return {'port': best, 'label': best_label, 'changed': False,
                'health': snap[best].get('healthScore'),
                'reason': f'Enviando por {orig_label}.'}
    os_ = snap.get(original_port) or {}
    if target_owner and original_port not in allowed:
        reason = f'Conversa veio por {orig_label}; respondendo pelo chip permitido {best_label}.'
    elif not os_.get('healthy'):
        why = 'desconectado/precisa de QR' if not os_ else 'indisponível'
        reason = f'Enviando por {best_label} porque {orig_label} está {why}.'
    else:
        reason = f'Enviando por {best_label} porque {orig_label} está com volume/risco maior.'
    return {'port': best, 'label': best_label, 'changed': True,
            'health': snap[best].get('healthScore'), 'reason': reason}

def qr_page(port, label, auth, status):
    """Página amigável de reconexão: mostra o QR da bridge (via proxy) ou 'já conectado'."""
    connected = bool(status.get('connected')) and not status.get('needsQR')
    if connected:
        inner = ('<div class="ok">✓ O chip <b>%s</b> já está conectado.</div>'
                 '<p class="muted">Pode fechar esta janela.</p>') % label
    else:
        inner = ('<p>No celular do chip <b>%s</b>, abra o WhatsApp e vá em:</p>'
                 '<p class="step">Configurações → Aparelhos conectados → Conectar um aparelho</p>'
                 '<img class="qr" src="/qr.png?port=%d&%s" alt="QR code" '
                 'onerror="this.replaceWith(Object.assign(document.createElement(\'p\'),'
                 '{className:\'muted\',textContent:\'Aguardando o QR da bridge… atualize em alguns segundos.\'}))">'
                 '<p class="muted">Esta página atualiza sozinha a cada 6 segundos.</p>') % (label, port, auth)
    return ('<!doctype html><html lang="pt-br"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            + ('' if connected else '<meta http-equiv="refresh" content="6">') +
            '<title>Reconectar ' + label + '</title><style>'
            'body{margin:0;background:#06080A;color:#F4F7F5;font-family:Inter,system-ui,-apple-system,sans-serif;display:grid;place-items:center;min-height:100vh}'
            '.card{max-width:420px;text-align:center;padding:28px;border:1px solid rgba(255,255,255,.08);border-radius:18px;background:#0E1114}'
            '.card h1{font-size:16px;margin:0 0 6px}.card .sub{font-size:12px;color:#68736D;margin-bottom:16px}'
            '.qr{width:280px;max-width:80vw;border-radius:12px;margin:8px auto;display:block;background:#fff;padding:8px}'
            '.step{font-size:13px;color:#A7B0AA;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:8px 10px}'
            '.muted{font-size:12px;color:#68736D}.ok{font-size:15px;color:#20C997;margin:18px 0}'
            '.port{font-size:11px;color:#68736D;margin-top:14px}'
            '</style></head><body><div class="card"><h1>Reconectar chip</h1>'
            '<div class="sub">' + label + '</div>' + inner +
            '<div class="port">porta ' + str(port) + '</div></div></body></html>')


def _parse_hs_dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace('Z', '+00:00'))
    except Exception:
        return None

def _br_bounds_for_day(offset_days=0):
    from zoneinfo import ZoneInfo
    br = ZoneInfo('America/Sao_Paulo')
    d = (datetime.now(br) + timedelta(days=offset_days)).date()
    start = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=br).astimezone(timezone.utc)
    end = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=br).astimezone(timezone.utc)
    return start.isoformat().replace('+00:00','Z'), end.isoformat().replace('+00:00','Z'), d

def _month_bounds_br():
    from zoneinfo import ZoneInfo
    br=ZoneInfo('America/Sao_Paulo')
    now=datetime.now(br)
    start=datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=br)
    if now.month==12:
        end=datetime(now.year+1, 1, 1, 0, 0, 0, tzinfo=br)
    else:
        end=datetime(now.year, now.month+1, 1, 0, 0, 0, tzinfo=br)
    return start.astimezone(timezone.utc).isoformat().replace('+00:00','Z'), end.astimezone(timezone.utc).isoformat().replace('+00:00','Z'), now.date(), end.date()

def _business_days_remaining(today, month_end_exclusive):
    # inclui hoje se ainda for dia útil; usado para ritmo restante da meta.
    n=0; d=today
    while d < month_end_exclusive:
        if d.weekday() < 5:
            n += 1
        d = d + timedelta(days=1)
    return max(n, 1)

def _hs_task_search(token, start_iso=None, end_iso=None, overdue=False, limit=5):
    filters=[{'propertyName':'hs_task_status','operator':'NEQ','value':'COMPLETED'}]
    if overdue:
        filters.append({'propertyName':'hs_timestamp','operator':'LT','value':start_iso})
    else:
        filters.append({'propertyName':'hs_timestamp','operator':'GTE','value':start_iso})
        filters.append({'propertyName':'hs_timestamp','operator':'LTE','value':end_iso})
    payload={'filterGroups':[{'filters':filters}],
             'properties':['hs_task_subject','hs_task_body','hs_task_status','hs_timestamp','hubspot_owner_id','hs_task_priority','hs_task_type'],
             'limit':limit,
             'sorts':[{'propertyName':'hs_timestamp','direction':'ASCENDING'}]}
    try:
        return _hs_request('POST','/crm/v3/objects/tasks/search',token,payload,timeout=18)
    except Exception:
        return {'total':0,'results':[]}

def _assoc_ids(token, from_type, to_type, ids):
    if not ids: return {}
    try:
        data=_hs_request('POST',f'/crm/v3/associations/{from_type}/{to_type}/batch/read',token,{'inputs':[{'id':str(i)} for i in ids]},timeout=15)
    except Exception:
        return {}
    out={}
    for r in data.get('results') or []:
        fid=str((r.get('from') or {}).get('id') or '')
        tos=r.get('to') or []
        if fid and tos:
            out[fid]=[str(t.get('id')) for t in tos if t.get('id')]
    return out

def _batch_read_simple(token, obj, ids, props):
    if not ids: return {}
    out={}
    ids=[str(i) for i in ids if i]
    for i in range(0, len(ids), 100):
        chunk=ids[i:i+100]
        try:
            data=_hs_request('POST',f'/crm/v3/objects/{obj}/batch/read',token,{'properties':props,'inputs':[{'id':str(x)} for x in chunk]},timeout=25)
        except Exception:
            continue
        for r in data.get('results') or []:
            out[str(r.get('id'))]=r.get('properties') or {}
    return out

def _format_task_items(token, results):
    ids=[str(r.get('id')) for r in (results or []) if r.get('id')]
    deal_assoc=_assoc_ids(token,'tasks','deals',ids)
    contact_assoc=_assoc_ids(token,'tasks','contacts',ids)
    deal_ids=sorted({i for arr in deal_assoc.values() for i in arr})
    contact_ids=sorted({i for arr in contact_assoc.values() for i in arr})
    deals=_batch_read_simple(token,'deals',deal_ids,['dealname','hubspot_owner_id'])
    contacts=_batch_read_simple(token,'contacts',contact_ids,['firstname','lastname','email','company','hubspot_owner_id'])
    items=[]
    for r in results or []:
        tid=str(r.get('id') or '')
        pr=r.get('properties') or {}
        name=''
        did=(deal_assoc.get(tid) or [''])[0]
        cid=(contact_assoc.get(tid) or [''])[0]
        if did and deals.get(did): name=deals[did].get('dealname') or ''
        if not name and cid and contacts.get(cid):
            cp=contacts[cid]
            nm=' '.join(x for x in [cp.get('firstname') or '', cp.get('lastname') or ''] if x).strip()
            name=nm or cp.get('company') or cp.get('email') or ''
        subject=pr.get('hs_task_subject') or 'Tarefa sem assunto'
        owner=HUBSPOT_OWNER_LABELS.get(pr.get('hubspot_owner_id') or '', '')
        ts=_parse_hs_dt(pr.get('hs_timestamp'))
        due=ts.astimezone().strftime('%d/%m %H:%M') if ts else ''
        items.append({'id':tid,'subject':subject,'name':name or subject,'owner':owner,'due':due,
                      'url':f'https://app.hubspot.com/tasks/{HUBSPOT_PORTAL_ID}/view/all/task/{tid}',
                      'dealId':did,'contactId':cid})
    return items

def _count_intro_meetings_month(token, start_iso, end_iso):
    total=0
    for prop in INTRO_STAGE_PROPS:
        payload={'filterGroups':[{'filters':[{'propertyName':prop,'operator':'GTE','value':start_iso},{'propertyName':prop,'operator':'LT','value':end_iso}]}],
                 'properties':['dealname',prop,'hubspot_owner_id'], 'limit':1}
        try:
            data=_hs_request('POST','/crm/v3/objects/deals/search',token,payload,timeout=18)
            total += int(data.get('total') or 0)
        except Exception:
            pass
    return total


def _search_intro_deals_month(token, uid, start_iso, end_iso, limit=500):
    """Deals que entraram em Introdução no mês. Read-only, dedup por deal.

    Observação: HubSpot não entrega histórico completo de owner por etapa nessa busca;
    usamos o owner atual do deal como aproximação para leitura gerencial.
    """
    owner_ids=_owner_ids_for_user(uid)
    out={}
    for prop in INTRO_STAGE_PROPS:
        filters=[{'propertyName':prop,'operator':'GTE','value':start_iso},{'propertyName':prop,'operator':'LT','value':end_iso}]
        if owner_ids:
            if len(owner_ids)==1:
                filters.append({'propertyName':'hubspot_owner_id','operator':'EQ','value':owner_ids[0]})
            else:
                filters.append({'propertyName':'hubspot_owner_id','operator':'IN','values':owner_ids})
        payload={'filterGroups':[{'filters':filters}],
                 'properties':['dealname','dealstage','pipeline','hubspot_owner_id','createdate',prop],
                 'limit':100,
                 'sorts':[{'propertyName':prop,'direction':'DESCENDING'}]}
        after=None
        while True:
            if after: payload['after']=after
            else: payload.pop('after', None)
            try:
                data=_hs_request('POST','/crm/v3/objects/deals/search',token,payload,timeout=25)
            except Exception:
                break
            for d in data.get('results') or []:
                did=str(d.get('id') or '')
                if not did or did in out: continue
                pr=d.get('properties') or {}
                oid=str(pr.get('hubspot_owner_id') or '')
                owner=HUBSPOT_OWNER_LABELS.get(oid, oid or 'Sem owner')
                out[did]={'dealId':did,'dealName':pr.get('dealname') or '(negócio sem nome)','ownerId':oid,'owner':owner,
                          'stageId':pr.get('dealstage') or '', 'stageLabel':HUBSPOT_STAGE_LABELS.get(pr.get('dealstage') or '', pr.get('dealstage') or ''),
                          'enteredAt':pr.get(prop) or '', 'createdAt':pr.get('createdate') or '', 'url':f'https://app.hubspot.com/contacts/{HUBSPOT_PORTAL_ID}/deal/{did}'}
                if len(out)>=limit: break
            if len(out)>=limit: break
            after=((data.get('paging') or {}).get('next') or {}).get('after')
            if not after: break
    return list(out.values())


def _deal_history_batch(token, deal_ids):
    out={}; deal_ids=[str(x) for x in deal_ids if x]
    for i in range(0, len(deal_ids), 50):
        chunk=deal_ids[i:i+50]
        try:
            data=_hs_request('POST','/crm/v3/objects/deals/batch/read',token,{
                'properties':['dealname','hubspot_owner_id','createdate','dealstage','hs_v2_date_entered_1269308723'],
                'propertiesWithHistory':['hubspot_owner_id','dealstage'],
                'inputs':[{'id':x} for x in chunk]
            },timeout=60)
        except Exception:
            continue
        for r in data.get('results') or []:
            out[str(r.get('id') or '')]=r
    return out

def _iso_ts(s):
    if not s: return None
    try:
        return datetime.fromisoformat(str(s).replace('Z','+00:00')).timestamp()
    except Exception:
        return None

def _owner_before_intro(history_row, entered_at):
    """Owner responsável antes da entrada em Introdução.

    Depois do handoff, o owner atual muitas vezes vira vendedor/EC segundos depois.
    Para medir performance SDR, usamos o histórico de owner imediatamente antes da
    entrada em Introdução; se simultâneo e já mudou para vendedor, procura SDR nas
    48h anteriores.
    """
    sdr_ids=set(HUBSPOT_OWNER_LABELS.keys())
    hist=((history_row.get('propertiesWithHistory') or {}).get('hubspot_owner_id') or [])
    t=_iso_ts(entered_at)
    candidates=[]
    for e in hist:
        et=_iso_ts(e.get('timestamp'))
        if et is not None and t is not None and et <= t + 1:
            candidates.append((et, str(e.get('value') or '')))
    candidates.sort(reverse=True)
    best=candidates[0][1] if candidates else str(((history_row.get('properties') or {}).get('hubspot_owner_id') or ''))
    if best not in sdr_ids and t is not None:
        sdr_cands=[(et,val) for et,val in candidates if val in sdr_ids and et >= t-172800]
        if sdr_cands:
            best=sdr_cands[0][1]
    return best

def _intro_conversion_metrics(token, uid, active_owner_rows):
    month_start, month_end, today_date, month_end_date = _month_bounds_br()
    intro_rows=_search_intro_deals_month(token, uid, month_start, month_end)
    histories=_deal_history_batch(token, [r.get('dealId') for r in intro_rows])
    active_by_owner={str(r.get('owner') or 'Sem owner'):{'ownerId':str(r.get('ownerId') or ''),'owner':str(r.get('owner') or 'Sem owner'),'active':int(r.get('total') or 0),'introduced':0,'createdThisMonth':0,'createdBefore':0,'deals':[]} for r in (active_owner_rows or [])}
    total_intro=0; created_this_month=0; created_before=0; attributed_sdr=0; other_intro=0
    for r in intro_rows:
        did=str(r.get('dealId') or '')
        h=histories.get(did) or {}
        owner_id=_owner_before_intro(h, r.get('enteredAt')) or str(r.get('ownerId') or '')
        owner=HUBSPOT_OWNER_LABELS.get(owner_id, 'Outros')
        created=str(r.get('createdAt') or '')
        is_new = bool(created and created >= month_start and created < month_end)
        r['createdThisMonth'] = is_new
        r['attributedOwnerId'] = owner_id
        r['attributedOwner'] = owner
        total_intro += 1
        if is_new: created_this_month += 1
        else: created_before += 1
        if owner_id not in HUBSPOT_OWNER_LABELS:
            other_intro += 1
            continue
        attributed_sdr += 1
        ent=active_by_owner.setdefault(owner, {'ownerId':owner_id,'owner':owner,'active':0,'introduced':0,'createdThisMonth':0,'createdBefore':0,'deals':[]})
        ent['introduced']+=1
        if is_new: ent['createdThisMonth']+=1
        else: ent['createdBefore']+=1
        ent['deals'].append(r)
    rows=[]
    for ent in active_by_owner.values():
        active=int(ent.get('active') or 0); intro=int(ent.get('introduced') or 0); denom=active+intro
        rows.append({'ownerId':ent.get('ownerId') or '', 'owner':ent.get('owner') or 'Sem owner', 'active':active, 'introduced':intro, 'createdThisMonth':int(ent.get('createdThisMonth') or 0), 'createdBefore':int(ent.get('createdBefore') or 0), 'base':denom,
                     'rate':round((intro/denom*100),1) if denom else 0, 'deals':ent.get('deals',[])[:8]})
    rows.sort(key=lambda r:(r.get('rate',0), r.get('introduced',0), -r.get('active',0)), reverse=True)
    active_total=sum(int(r.get('active') or 0) for r in rows)
    base=active_total+total_intro
    return {'period':'mês atual', 'monthStart':month_start, 'monthEnd':month_end, 'active':active_total,
            'introduced':total_intro, 'createdThisMonth':created_this_month, 'createdBefore':created_before,
            'attributedSdr':attributed_sdr, 'otherIntroduced':other_intro,
            'base':base, 'rate':round((total_intro/base*100),1) if base else 0,
            'targetStageId':'1269308723','targetStageLabel':'Introdução','rows':rows[:10],
            'note':'Introduções do mês = deals que entraram em Introdução neste mês, mesmo que depois tenham avançado para outra etapa ou perdido. Por SDR usa histórico de owner antes da entrada em Introdução; owner atual pode ser vendedor/EC.'}

def _owner_ids_for_user(uid):
    if user_can_view_all(uid):
        # Supervisor/admin: a referência visual do Rafael é o relatório HubSpot
        # consolidado das etapas de demanda. Não filtra owner aqui; é leitura agregada.
        return []
    reverse={v:k for k,v in HUBSPOT_OWNER_UIDS.items()}
    oid=reverse.get(uid)
    return [oid] if oid else []


def _count_deals_stage_owner(token, stage_id, owner_ids):
    filters=[{'propertyName':'dealstage','operator':'EQ','value':stage_id}]
    if owner_ids:
        if len(owner_ids) == 1:
            filters.append({'propertyName':'hubspot_owner_id','operator':'EQ','value':owner_ids[0]})
        else:
            filters.append({'propertyName':'hubspot_owner_id','operator':'IN','values':owner_ids})
    payload={'filterGroups':[{'filters':filters}], 'properties':['dealname','dealstage','hubspot_owner_id'], 'limit':1}
    try:
        data=_hs_request('POST','/crm/v3/objects/deals/search',token,payload,timeout=18)
        return int(data.get('total') or 0)
    except Exception:
        return 0


def _pipeline_stage_summary(token, uid):
    owner_ids=_owner_ids_for_user(uid)
    rows=[]; total=0
    for sid in DEMAND_PIPELINE_STAGES:
        n=_count_deals_stage_owner(token, sid, owner_ids)
        total += n
        rows.append({'stageId':sid,'label':HUBSPOT_STAGE_LABELS.get(sid,sid),'count':n})
    return {'total':total,'rows':rows,'ownerIds':owner_ids,'scope':'consolidado HubSpot' if user_can_view_all(uid) else 'somente sua carteira'}


def _search_pipeline_focus_deals(token, uid, limit=900):
    """Negócios do pipe nas 5 primeiras etapas. Fonte primária do Foco/Gestão."""
    owner_ids=_owner_ids_for_user(uid)
    filters=[
        {'propertyName':'pipeline','operator':'EQ','value':'671008549'},
        {'propertyName':'dealstage','operator':'IN','values':DEMAND_PIPELINE_STAGES},
    ]
    if owner_ids:
        if len(owner_ids)==1:
            filters.append({'propertyName':'hubspot_owner_id','operator':'EQ','value':owner_ids[0]})
        else:
            filters.append({'propertyName':'hubspot_owner_id','operator':'IN','values':owner_ids})
    payload={'filterGroups':[{'filters':filters}],
             'properties':['dealname','dealstage','pipeline','hubspot_owner_id','createdate','hs_lastmodifieddate'],
             'limit':100,
             'sorts':[{'propertyName':'hs_lastmodifieddate','direction':'DESCENDING'}]}
    out=[]; after=None
    while True:
        if after: payload['after']=after
        else: payload.pop('after', None)
        data=_hs_request('POST','/crm/v3/objects/deals/search',token,payload,timeout=25)
        out.extend(data.get('results') or [])
        if len(out)>=limit:
            return out[:limit]
        after=((data.get('paging') or {}).get('next') or {}).get('after')
        if not after:
            return out


def _activity_dt_value(raw):
    if not raw: return 0
    try:
        txt=str(raw).replace('Z','+00:00')
        return datetime.fromisoformat(txt).timestamp()
    except Exception:
        try:
            return float(raw)/1000 if float(raw)>100000000000 else float(raw)
        except Exception:
            return 0


def _safe_activity_label(kind, props):
    if kind=='task':
        return (props.get('hs_task_subject') or 'Tarefa HubSpot').strip()[:140]
    if kind=='call':
        return (props.get('hs_call_title') or props.get('hs_call_body') or 'Ligação HubSpot').strip()[:140]
    body=re.sub(r'<[^>]+>',' ',str(props.get('hs_note_body') or ''))
    body=' '.join(body.split())
    return (body or 'Nota HubSpot')[:140]


def _activity_text_blob(kind, props, label=''):
    vals=[label, kind]
    for k in ('hs_task_subject','hs_task_body','hs_task_type','hs_note_body','hs_call_title','hs_call_body','hs_call_status'):
        vals.append(props.get(k) or '')
    txt=' '.join(str(v or '') for v in vals)
    txt=re.sub(r'<[^>]+>',' ',txt)
    return ' '.join(txt.lower().split())


def _activity_flags(kind, props, label=''):
    """Classifica a atividade HubSpot para filtros da UI.

    HubSpot nem sempre grava ligação como objeto `call`: muitas vezes vem como
    task com assunto "Ligação". WhatsApp normalmente entra em task/note com
    assunto/corpo citando WhatsApp/WPP. Não usa mensagens do Channel.
    """
    blob=_activity_text_blob(kind, props, label)
    has_call = kind == 'call' or bool(re.search(r'\b(call|ligacao|liga[cç][aã]o|telefonema|telefone)\b', blob))
    has_whatsapp = bool(re.search(r'\b(whatsapp|whats|wpp|zap|wa\.me)\b', blob))
    return has_call, has_whatsapp


def _pipeline_activity_assoc_ids(token, from_obj, to_obj, ids):
    """Mapa {from_id: [to_id,...]} via associations v4 batch/read."""
    out={}
    ids=[str(i) for i in ids if i]
    for i in range(0, len(ids), 100):
        chunk=ids[i:i+100]
        try:
            data=_hs_request('POST',f'/crm/v4/associations/{from_obj}/{to_obj}/batch/read',token,{'inputs':[{'id':x} for x in chunk]},timeout=25)
        except Exception:
            continue
        for r in data.get('results') or []:
            fid=str((r.get('from') or {}).get('id') or '')
            if not fid: continue
            vals=[]
            for t in (r.get('to') or []):
                tid=str(t.get('toObjectId') or t.get('id') or '')
                if tid: vals.append(tid)
            if vals: out[fid]=vals
    return out


def pipeline_focus(uid='rafael'):
    """Visão read-only do pipe: 5 etapas HubSpot fatiadas por atividades HubSpot.

    Não usa mensagens WhatsApp/conversas para contar. A atividade é o que está
    associado ao negócio no HubSpot (tasks + notes + calls), pois é a fonte de verdade
    que Rafael pediu para esta tela.
    """
    key='pipeline_focus_v7_'+str(uid)
    cached=_hs_cache_get(key)
    if cached: return cached
    token=_hubspot_token()
    if not token:
        return {'configured':False,'error':'HubSpot não configurado','total':0,'rows':[],'activityBuckets':{},'stageRows':[],'ownerRows':[]}
    deals=_search_pipeline_focus_deals(token, uid)
    deal_ids=[str(d.get('id') or '') for d in deals if d.get('id')]
    task_map=_pipeline_activity_assoc_ids(token,'deals','tasks',deal_ids)
    note_map=_pipeline_activity_assoc_ids(token,'deals','notes',deal_ids)
    call_map=_pipeline_activity_assoc_ids(token,'deals','calls',deal_ids)
    task_ids=sorted({tid for arr in task_map.values() for tid in arr})
    note_ids=sorted({nid for arr in note_map.values() for nid in arr})
    call_ids=sorted({cid for arr in call_map.values() for cid in arr})
    tasks=_batch_read_simple(token,'tasks',task_ids,HUBSPOT_PIPE_ACTIVITY_TASK_PROPS)
    notes=_batch_read_simple(token,'notes',note_ids,HUBSPOT_PIPE_ACTIVITY_NOTE_PROPS)
    calls=_batch_read_simple(token,'calls',call_ids,HUBSPOT_PIPE_ACTIVITY_CALL_PROPS)
    by_bucket={'0':[],'1':[],'2':[],'3':[],'4+':[]}
    by_stage={sid:{'stageId':sid,'label':HUBSPOT_STAGE_LABELS.get(sid,sid),'total':0,'buckets':{'0':0,'1':0,'2':0,'3':0,'4+':0}} for sid in DEMAND_PIPELINE_STAGES}
    by_owner={}
    type_summary={'withCall':0,'withoutCall':0,'withWhatsApp':0,'withoutWhatsApp':0}
    rows=[]
    for d in deals:
        did=str(d.get('id') or '')
        p=d.get('properties') or {}
        stage=str(p.get('dealstage') or '')
        owner_id=str(p.get('hubspot_owner_id') or '')
        owner=HUBSPOT_OWNER_LABELS.get(owner_id, owner_id or 'Sem owner')
        # Foco/Gestão SDR deve mostrar só a carteira operacional dos SDRs mapeados.
        # Owners numéricos desconhecidos (ex.: 76764091) são usuários HubSpot fora da
        # visão solicitada e poluem a análise, então ficam fora da tela.
        if re.fullmatch(r'\d+', owner):
            continue
        acts=[]
        for tid in task_map.get(did,[]):
            props=tasks.get(tid) or {}
            if props:
                label=_safe_activity_label('task',props); has_call,has_whatsapp=_activity_flags('task',props,label)
                acts.append({'kind':'task','id':tid,'label':label,'ts':_activity_dt_value(props.get('hs_timestamp')),'status':props.get('hs_task_status') or '','type':props.get('hs_task_type') or 'TASK','isCall':has_call,'isWhatsApp':has_whatsapp})
        for nid in note_map.get(did,[]):
            props=notes.get(nid) or {}
            if props:
                label=_safe_activity_label('note',props); has_call,has_whatsapp=_activity_flags('note',props,label)
                acts.append({'kind':'note','id':nid,'label':label,'ts':_activity_dt_value(props.get('hs_timestamp')),'status':'','type':'NOTE','isCall':has_call,'isWhatsApp':has_whatsapp})
        for cid in call_map.get(did,[]):
            props=calls.get(cid) or {}
            if props:
                label=_safe_activity_label('call',props); has_call,has_whatsapp=_activity_flags('call',props,label)
                acts.append({'kind':'call','id':cid,'label':label,'ts':_activity_dt_value(props.get('hs_timestamp')),'status':props.get('hs_call_status') or '','type':'CALL','isCall':has_call,'isWhatsApp':has_whatsapp})
        acts.sort(key=lambda a:a.get('ts') or 0, reverse=True)
        n=len(acts); bucket='4+' if n>=4 else str(n)
        has_call=any(a.get('isCall') for a in acts)
        has_whatsapp=any(a.get('isWhatsApp') for a in acts)
        type_summary['withCall' if has_call else 'withoutCall']+=1
        type_summary['withWhatsApp' if has_whatsapp else 'withoutWhatsApp']+=1
        type_counts={'call':sum(1 for a in acts if a.get('isCall')),'whatsapp':sum(1 for a in acts if a.get('isWhatsApp')),'task':sum(1 for a in acts if a.get('kind')=='task'),'note':sum(1 for a in acts if a.get('kind')=='note')}
        row={'dealId':did,'dealName':p.get('dealname') or '(negócio sem nome)','stageId':stage,'stageLabel':HUBSPOT_STAGE_LABELS.get(stage,stage),'ownerId':owner_id,'owner':owner,'activityCount':n,'bucket':bucket,'hasCall':has_call,'hasWhatsApp':has_whatsapp,'typeCounts':type_counts,'lastActivity':acts[0] if acts else None,'activities':acts,'url':f'https://app.hubspot.com/contacts/{HUBSPOT_PORTAL_ID}/deal/{did}'}
        rows.append(row); by_bucket[bucket].append(row)
        st=by_stage.setdefault(stage,{'stageId':stage,'label':HUBSPOT_STAGE_LABELS.get(stage,stage),'total':0,'buckets':{'0':0,'1':0,'2':0,'3':0,'4+':0}})
        st['total']+=1; st['buckets'][bucket]=st['buckets'].get(bucket,0)+1
        ow=by_owner.setdefault(owner_id or 'sem_owner',{'ownerId':owner_id,'owner':owner,'total':0,'buckets':{'0':0,'1':0,'2':0,'3':0,'4+':0}})
        ow['total']+=1; ow['buckets'][bucket]=ow['buckets'].get(bucket,0)+1
    sorted_rows=sorted(rows,key=lambda r: (str(r.get('stageLabel') or ''), str(r.get('owner') or ''), int(r.get('activityCount') or 0), str(r.get('dealName') or '')))
    sample=lambda arr:[{k:r.get(k) for k in ('dealId','dealName','stageLabel','owner','activityCount','bucket','hasCall','hasWhatsApp','typeCounts','activities','url')}|({'lastActivity':r.get('lastActivity')} if r.get('lastActivity') else {}) for r in arr[:8]]
    owner_rows=sorted([v for v in by_owner.values() if not re.fullmatch(r'\d+', str(v.get('owner') or v.get('ownerId') or ''))], key=lambda x:x.get('total',0), reverse=True)
    intro_conversion=_intro_conversion_metrics(token, uid, owner_rows)
    out={'configured':True,'generatedAt':datetime.now(BRT_TZ).isoformat(),'scope':'consolidado HubSpot' if user_can_view_all(uid) else 'somente sua carteira','total':len(rows),'typeSummary':type_summary,'activityBuckets':{k:{'count':len(v),'sample':sample(sorted(v,key=lambda r: (r.get('activityCount') or 0, r.get('dealName') or '')))} for k,v in by_bucket.items()},'stageRows':list(by_stage.values()),'ownerRows':owner_rows,'introConversion':intro_conversion,'deals':sorted_rows,'rows':sample(rows)}
    _hs_cache_set(key,out)
    return out


# --- CH: prévia read-only do saneamento/cadência de Primeiro Contato ---------
# Lê apenas o JSON gerado pelo dry-run (scripts/cadencia_primeiro_contato_dryrun.py).
# NUNCA roda o dry-run, NUNCA envia WhatsApp, NUNCA escreve no HubSpot.
CADENCIA_DRYRUN_FILE = PROJECT / 'controle' / 'cadencia_primeiro_contato_dryrun.json'
CADENCIA_STALE_HOURS = 18          # acima disso, avisa para rodar o dry-run de novo
CADENCIA_SAMPLE_PER_BUCKET = 6     # amostra limitada por bucket
CADENCIA_BUCKET_LABELS = {
    'sem_primeiro_contato_registrado': 'Sem D0 confiável',
    'aguardar_24h': 'Aguardar janela 24h',
    'respondeu_nao_tocar': 'Respondeu — não tocar',
    'nutricao_marketing': 'Nutrição / fora da prioridade SDR',
    'dia_1_proximo_2contato': 'Aptos para 2º contato',
    'dia_2_proximo_3contato': 'Aptos para 3º contato',
    'dia_3_proximo_4contato': 'Aptos para 4º contato',
}
# Ordem de exibição: acionáveis primeiro, depois espera, depois fora de prioridade.
CADENCIA_BUCKET_ORDER = [
    'dia_1_proximo_2contato', 'dia_2_proximo_3contato', 'dia_3_proximo_4contato',
    'aguardar_24h', 'sem_primeiro_contato_registrado',
    'respondeu_nao_tocar', 'nutricao_marketing',
]
CADENCIA_SAFETY_NOTICE = 'Prévia read-only. Nenhum WhatsApp enviado. Nenhum HubSpot alterado. Crons intactos.'
# Mapa de saneamento: 5 destinos operacionais do limbo (espelha o dry-run).
# Cada grupo soma um ou mais sanitationBucket vindos do JSON do dry-run.
CADENCIA_SANITATION_GROUPS = [
    {'key': 'd0_real',     'label': 'D0 real',                       'buckets': ['d0_real']},
    {'key': 'reconciliar', 'label': 'Reconciliar ledger/evidência',  'buckets': ['reconciliar_hubspot', 'reconciliar_whatsapp']},
    {'key': 'cadencia',    'label': 'Cadência 2º/3º/4º',             'buckets': ['d0_confiavel_cadencia']},
    {'key': 'nao_tocar',   'label': 'Não tocar — respondeu',        'buckets': ['nao_tocar_respondeu']},
    {'key': 'nutricao',    'label': 'Nutrição/liberar pipe',         'buckets': ['nutricao_liberar_pipe']},
]


def _cadencia_mask_phone(phone):
    """Mascara o telefone: mantém só DDD e os 2 últimos dígitos."""
    digits = ''.join(ch for ch in str(phone or '') if ch.isdigit())
    if len(digits) < 4:
        return ''
    return digits[:2] + '•' * (len(digits) - 4) + digits[-2:]


# --- CH: decisões humanas LOCAIS sobre o limbo de Primeiro Contato -----------
# Grava a escolha do operador sobre cada deal do dry-run num JSON local, atômico
# e com lock, + auditoria append-only em JSONL. Esta camada é PURAMENTE LOCAL:
# NÃO envia WhatsApp, NÃO escreve no HubSpot, NÃO altera stage/owner/cron e NÃO
# toca no ledger wpp_envios.json. É só a memória da decisão do humano.
CADENCIA_DECISOES_FILE = PROJECT / 'controle' / 'cadencia_primeiro_contato_decisoes.json'
CADENCIA_DECISOES_LOG = PROJECT / 'controle' / 'cadencia_primeiro_contato_decisoes.jsonl'
# Whitelist de ações permitidas -> rótulo curto para a UI. `limpar` remove a decisão.
CADENCIA_DECISION_ACTIONS = {
    'confirmar_d0':   'confirmar D0',          # confirmar evidência como D0 confiável (local)
    'manter_revisao': 'manter revisão',        # manter em revisão
    'tratar_d0_real': 'tratar como D0 real',   # tratar como primeiro contato real
    'nutricao':       'nutrição/liberar pipe', # mandar para nutrição (local)
    'limpar':         'limpar',                # remove a decisão local
}
_cadencia_decisoes_lock = threading.Lock()


def _cadencia_now_iso():
    return datetime.now(BRT_TZ).isoformat()


def _cadencia_dryrun_rows():
    """Lê apenas as rows do dry-run (read-only). [] em qualquer falha."""
    try:
        data = json.loads(CADENCIA_DRYRUN_FILE.read_text(encoding='utf-8'))
        rows = data.get('rows')
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def _cadencia_row_for_deal(deal_id):
    """Row do dry-run para um dealId, ou None se não estiver na prévia."""
    deal_id = str(deal_id)
    for r in _cadencia_dryrun_rows():
        if str(r.get('dealId') or '') == deal_id:
            return r
    return None


def cadencia_deal_in_scope(uid, row):
    """SDR só decide sobre deals da própria carteira; supervisor/admin pode todos."""
    if user_can_view_all(uid):
        return True
    allow = {str(o) for o in _owner_ids_for_user(uid)}
    return bool(allow) and str((row or {}).get('ownerId') or '') in allow


def load_cadencia_decisoes():
    """Lê o JSON de decisões locais. Sempre devolve dict no formato esperado."""
    try:
        if CADENCIA_DECISOES_FILE.exists():
            data = json.loads(CADENCIA_DECISOES_FILE.read_text(encoding='utf-8'))
            if isinstance(data, dict) and isinstance(data.get('decisions'), dict):
                return data
    except Exception:
        pass
    return {'updatedAt': None, 'decisions': {}}


def _save_cadencia_decisoes(data):
    """Escrita atômica (tmp no mesmo dir + os.replace) com permissões restritas."""
    CADENCIA_DECISOES_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CADENCIA_DECISOES_FILE.parent / (CADENCIA_DECISOES_FILE.name + '.tmp.' + secrets.token_hex(4))
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        os.replace(tmp, CADENCIA_DECISOES_FILE)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
    try:
        os.chmod(CADENCIA_DECISOES_FILE, 0o600)
    except Exception:
        pass


def _cadencia_audit(entry):
    """Append-only JSONL de auditoria das decisões locais (best-effort)."""
    try:
        CADENCIA_DECISOES_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(CADENCIA_DECISOES_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        try:
            os.chmod(CADENCIA_DECISOES_LOG, 0o600)
        except Exception:
            pass
    except Exception:
        pass


def set_cadencia_decisao(deal_id, action, uid, note='', previous_sanitation_bucket=''):
    """Grava/remove a decisão local de um deal. Atômico e thread-safe.

    `limpar` remove a decisão; as demais ações gravam {dealId, action, uid, ts,
    note, previousSanitationBucket}. Devolve a decisão resultante (dict) ou None
    quando removida. NÃO toca em WhatsApp/HubSpot/ledger/cron.
    """
    deal_id = str(deal_id)
    note = str(note or '')[:500]
    now = _cadencia_now_iso()
    with _cadencia_decisoes_lock:
        data = load_cadencia_decisoes()
        decisions = data.get('decisions') or {}
        if action == 'limpar':
            decisions.pop(deal_id, None)
            result = None
        else:
            result = {
                'dealId': deal_id,
                'action': action,
                'uid': uid,
                'ts': now,
                'note': note,
                'previousSanitationBucket': str(previous_sanitation_bucket or ''),
            }
            decisions[deal_id] = result
        data['decisions'] = decisions
        data['updatedAt'] = now
        _save_cadencia_decisoes(data)
    _cadencia_audit({'ts': now, 'uid': uid, 'dealId': deal_id, 'action': action,
                     'note': note, 'previousSanitationBucket': str(previous_sanitation_bucket or '')})
    return result


def cadencia_decisoes_scoped(uid):
    """Decisões locais visíveis ao usuário (carteira do SDR; tudo p/ supervisor)."""
    data = load_cadencia_decisoes()
    decisions = data.get('decisions') or {}
    view_all = user_can_view_all(uid)
    allow = None if view_all else {str(o) for o in _owner_ids_for_user(uid)}
    owner_by_deal = {str(r.get('dealId') or ''): str(r.get('ownerId') or '')
                     for r in _cadencia_dryrun_rows()}
    out = {}
    counts = {}
    for did, dec in decisions.items():
        did = str(did)
        if allow is not None and owner_by_deal.get(did, '') not in allow:
            continue
        out[did] = dec
        a = str((dec or {}).get('action') or '')
        if a:
            counts[a] = counts.get(a, 0) + 1
    return {
        'ok': True,
        'scope': 'consolidado' if view_all else 'somente sua carteira',
        'viewAll': view_all,
        'updatedAt': data.get('updatedAt'),
        'decisions': out,
        'decisionCounts': counts,
        'actions': sorted(k for k in CADENCIA_DECISION_ACTIONS if k != 'limpar'),
        'safetyNotice': CADENCIA_SAFETY_NOTICE,
    }


def cadencia_preview(uid='rafael'):
    """Visão agregada read-only da cadência de Primeiro Contato.

    SDR comum vê apenas a própria carteira (filtra por ownerId); supervisor/admin
    vê o consolidado. Não dispara o dry-run — só lê o arquivo já gerado.
    """
    view_all = user_can_view_all(uid)
    info = {
        'ok': False,
        'scope': 'consolidado' if view_all else 'somente sua carteira',
        'viewAll': view_all,
        'safetyNotice': CADENCIA_SAFETY_NOTICE,
        'labels': CADENCIA_BUCKET_LABELS,
        'runCommand': 'python3 scripts/cadencia_primeiro_contato_dryrun.py',
    }
    if not CADENCIA_DRYRUN_FILE.exists():
        info['error'] = 'arquivo_ausente'
        info['message'] = ('Prévia ainda não gerada. Rode o dry-run (read-only): '
                           'python3 scripts/cadencia_primeiro_contato_dryrun.py')
        return info
    try:
        data = json.loads(CADENCIA_DRYRUN_FILE.read_text(encoding='utf-8'))
    except Exception:
        info['error'] = 'arquivo_invalido'
        info['message'] = ('Não foi possível ler a prévia. Rode o dry-run novamente: '
                           'python3 scripts/cadencia_primeiro_contato_dryrun.py')
        return info

    rows = data.get('rows') or []
    # SDR comum: filtra pelo(s) ownerId da carteira. Lista vazia => consolidado.
    owner_ids = _owner_ids_for_user(uid)
    if owner_ids:
        allow = {str(o) for o in owner_ids}
        rows = [r for r in rows if str(r.get('ownerId') or '') in allow]

    # Idade da prévia / staleness.
    generated_at = data.get('generatedAt') or ''
    age_hours = None
    stale = False
    try:
        gdt = datetime.fromisoformat(generated_at)
        if gdt.tzinfo is None:
            gdt = gdt.replace(tzinfo=BRT_TZ)
        age_hours = round((datetime.now(timezone.utc) - gdt.astimezone(timezone.utc)).total_seconds() / 3600, 1)
        stale = age_hours > CADENCIA_STALE_HOURS
    except Exception:
        pass

    # Contagens recomputadas a partir das rows do escopo (consistente com o filtro).
    counts = {}
    for r in rows:
        b = str(r.get('bucket') or 'desconhecido')
        counts[b] = counts.get(b, 0) + 1

    buckets = []
    seen = set()
    for b in CADENCIA_BUCKET_ORDER:
        if b in counts:
            buckets.append({'key': b, 'label': CADENCIA_BUCKET_LABELS.get(b, b), 'count': counts[b]})
            seen.add(b)
    for b in sorted(counts):
        if b not in seen:
            buckets.append({'key': b, 'label': CADENCIA_BUCKET_LABELS.get(b, b), 'count': counts[b]})

    # Mapa de saneamento (5 destinos) — read-only, derivado das rows do escopo.
    sanitation_counts = {}
    for r in rows:
        sb = str(r.get('sanitationBucket') or '')
        if not sb:
            continue
        sanitation_counts[sb] = sanitation_counts.get(sb, 0) + 1
    sanitation_buckets = []
    for g in CADENCIA_SANITATION_GROUPS:
        c = sum(sanitation_counts.get(b, 0) for b in g['buckets'])
        sanitation_buckets.append({'key': g['key'], 'label': g['label'], 'count': c})

    # Decisões humanas LOCAIS (read-only aqui): mapa dealId -> decisão.
    # NÃO altera os buckets automáticos; só anexa a escolha do operador.
    decisions_all = load_cadencia_decisoes().get('decisions') or {}
    decision_counts = {}
    for r in rows:
        dec = decisions_all.get(str(r.get('dealId') or ''))
        if dec:
            a = str(dec.get('action') or '')
            if a:
                decision_counts[a] = decision_counts.get(a, 0) + 1

    # Amostra limitada por bucket, com telefone mascarado.
    samples = {}
    for b in counts:
        sample = []
        for r in rows:
            if str(r.get('bucket')) != b:
                continue
            deal_id = str(r.get('dealId') or '')
            local_decision = decisions_all.get(deal_id) or None
            sample.append({
                'dealId': deal_id,
                'localDecision': local_decision,
                'company': r.get('dealName') or '—',
                'owner': r.get('owner') or '—',
                'attempts': r.get('attempts'),
                'hoursSinceLast': r.get('hoursSinceLast'),
                'phoneMasked': _cadencia_mask_phone(r.get('phone')),
                'respondedAfterLast': bool(r.get('respondedAfterLast')),
                'nextContactNumber': r.get('nextContactNumber'),
                # CH: fonte/evidência do primeiro contato (ledger / atividade HubSpot).
                'attemptSource': r.get('attemptSource') or 'none',
                'evidence': r.get('evidence') or [],
                'lastHubspotActivityAt': r.get('lastHubspotActivityAt') or '',
                'lastHubspotActivitySubject': r.get('lastHubspotActivitySubject') or '',
                'hubspotActivityCount': r.get('hubspotActivityCount'),
                # CH: destino de saneamento (1 dos 5) e ação recomendada curta.
                'sanitationBucket': r.get('sanitationBucket') or '',
                'sanitationLabel': r.get('sanitationLabel') or '',
                'recommendedAction': r.get('recommendedAction') or '',
                'needsReview': bool(r.get('needsReview')),
            })
            if len(sample) >= CADENCIA_SAMPLE_PER_BUCKET:
                break
        samples[b] = sample

    # Aptos seguros para próxima cadência: D0 confiável OU já em janela de próximo
    # contato (bucket dia_*). Amostra limitada; segue prévia, NUNCA dispara envio.
    aptos_rows = [r for r in rows
                  if str(r.get('sanitationBucket') or '') == 'd0_confiavel_cadencia'
                  or str(r.get('bucket') or '').startswith('dia_')]
    aptos_sample = []
    for r in aptos_rows[:CADENCIA_SAMPLE_PER_BUCKET]:
        aptos_sample.append({
            'company': r.get('dealName') or '—',
            'owner': r.get('owner') or '—',
            'phoneMasked': _cadencia_mask_phone(r.get('phone')),
            'bucket': r.get('bucket') or '',
            'sanitationBucket': r.get('sanitationBucket') or '',
            'nextContactNumber': r.get('nextContactNumber'),
        })
    aptos = {
        'count': len(aptos_rows),
        'sample': aptos_sample,
        'sampleLimit': CADENCIA_SAMPLE_PER_BUCKET,
        'notice': 'prévia: ainda sem envio',
    }

    info.update({
        'ok': True,
        'decisionCounts': decision_counts,
        'decisionActions': sorted(k for k in CADENCIA_DECISION_ACTIONS if k != 'limpar'),
        'aptos': aptos,
        'generatedAt': generated_at,
        'ageHours': age_hours,
        'stale': stale,
        'staleHours': CADENCIA_STALE_HOURS,
        'stage': data.get('stage') or 'Primeiro Contato',
        'totalDeals': len(rows),
        'totalDealsSource': data.get('totalDeals'),
        'counts': counts,
        'buckets': buckets,
        'sanitationCounts': sanitation_counts,
        'sanitationBuckets': sanitation_buckets,
        'samples': samples,
        'sampleLimit': CADENCIA_SAMPLE_PER_BUCKET,
    })
    if stale:
        info['warning'] = (f'Prévia gerada há {age_hours}h (> {CADENCIA_STALE_HOURS}h). '
                           'Rode o dry-run de novo para dados frescos: '
                           'python3 scripts/cadencia_primeiro_contato_dryrun.py')
    return info


def manager_overview(uid='rafael'):
    key='manager_overview_v3_'+str(uid)
    cached=_hs_cache_get(key)
    if cached: return cached
    token=_hubspot_token()
    if not token:
        return {'configured':False,'pipeline':{'total':0,'rows':[],'scope':'HubSpot indisponível'},'overdue':[],'today':[],'goal':{'target':MANAGER_MEETING_GOAL_MONTH,'done':0,'remaining':MANAGER_MEETING_GOAL_MONTH,'workdaysLeft':1,'perBusinessDay':MANAGER_MEETING_GOAL_MONTH}}
    start_today, end_today, today = _br_bounds_for_day(0)
    month_start, month_end, today_date, month_end_date = _month_bounds_br()
    overdue_data=_hs_task_search(token,start_iso=start_today,overdue=True,limit=5)
    today_data=_hs_task_search(token,start_iso=start_today,end_iso=end_today,overdue=False,limit=5)
    done=_count_intro_meetings_month(token,month_start,month_end)
    remaining=max(MANAGER_MEETING_GOAL_MONTH-done,0)
    workdays=_business_days_remaining(today_date,month_end_date)
    per_day=round(remaining/workdays,1) if remaining else 0
    out={'configured':True,
         'pipeline':_pipeline_stage_summary(token, uid),
         'overdue':_format_task_items(token, overdue_data.get('results') or []),
         'overdueTotal':int(overdue_data.get('total') or 0),
         'today':_format_task_items(token, today_data.get('results') or []),
         'todayTotal':int(today_data.get('total') or 0),
         'goal':{'target':MANAGER_MEETING_GOAL_MONTH,'done':done,'remaining':remaining,'workdaysLeft':workdays,'perBusinessDay':per_day,
                 'rule':'Conta só quando o negócio entra no estágio Introdução.'}}
    _hs_cache_set(key,out)
    return out

HTML = r'''<!doctype html><html lang="pt-br" data-theme="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Zydon · Inbox Comercial</title>
<style>
/* Zydon Inbox Comercial — tema claro fixo + paleta Zydon */
:root{
  /* Manual Zydon aplicado: verde institucional, lime como energia/acento, neutros calmos. */
  --zydon-green:#1F3D2B;--zydon-lime:#CDEB00;--zydon-cream:#F6F7F2;--zydon-ink:#162017;
  /* CH-027: ações primárias usam ink (preto) + lime como acento/texto, em vez do
     verde institucional pesado como fundo. Tokens compartilhados pelos dois temas. */
  --btn-ink:#0B0F0C;--btn-lime:#CDEB00;--btn-lime-line:rgba(205,235,0,0.55);--btn-ink-shadow:rgba(11,15,12,0.30);
  --bg:#F6F7F2;--panel:#FFFFFF;--panel-2:#FDFEF9;
  --surface:#F3F5ED;--surface-2:#EEF2E4;--surface-hi:#E7ECD8;
  --line:rgba(20,28,20,0.11);--line-soft:rgba(20,28,20,0.075);--line-strong:rgba(20,28,20,0.18);
  --txt:#162017;--txt-2:#526057;--muted:#7A857E;
  --accent:#1F3D2B;--accent-dim:rgba(31,61,43,0.10);--accent-soft:rgba(205,235,0,0.18);
  --success:#1F8F62;--success-soft:rgba(31,143,98,0.12);
  --warning:#D99522;--warning-soft:rgba(217,149,34,0.14);
  --danger:#D9480F;--danger-soft:rgba(217,72,15,0.12);
  --info:#3B6FB6;--info-soft:rgba(59,111,182,0.12);
  --radius:14px;--radius-sm:10px;
  --ff:'Inter',system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --sidebar-w:112px;--list-w:390px;--context-w:304px;
  --chat-bg:#F6F7F2;--chat-dot:rgba(20,28,20,0.045);
  --bubble-out:#DCF8C6;--bubble-in:#FFFFFF;
}
[data-theme="dark"]{
  --bg:#07100B;--panel:#101913;--panel-2:#0B140F;
  --surface:#142019;--surface-2:#1A2A20;--surface-hi:#24362A;
  --line:rgba(205,235,0,0.11);--line-soft:rgba(205,235,0,0.07);--line-strong:rgba(205,235,0,0.20);
  --txt:#F4F7F0;--txt-2:#B9C3BA;--muted:#7F8D84;
  --accent:#CDEB00;--accent-dim:rgba(205,235,0,0.14);--accent-soft:rgba(205,235,0,0.10);
  --success:#20C997;--success-soft:rgba(32,201,151,0.14);
  --warning:#F7B955;--warning-soft:rgba(247,185,85,0.14);
  --danger:#FF7A59;--danger-soft:rgba(255,122,89,0.14);
  --info:#7AA2FF;--info-soft:rgba(122,162,255,0.14);
  --chat-bg:#08130D;--chat-dot:rgba(205,235,0,0.035);
  --bubble-out:#1F3D2B;--bubble-in:#111C15;
}

*{box-sizing:border-box}html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--txt);font-family:var(--ff);font-size:14px;line-height:1.45;-webkit-font-smoothing:antialiased;overflow:hidden;letter-spacing:-0.006em}
button{font-family:inherit;cursor:pointer;color:inherit}input,textarea,select{font-family:inherit}
::-webkit-scrollbar{width:10px;height:10px}::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.07);border-radius:99px;border:3px solid transparent;background-clip:padding-box}::-webkit-scrollbar-thumb:hover{background:rgba(255,255,255,0.13);background-clip:padding-box}::-webkit-scrollbar-track{background:transparent}
a{color:var(--accent);text-decoration:none}
.app{display:grid;grid-template-columns:var(--sidebar-w) var(--list-w) minmax(0,1fr) var(--context-w);height:100vh;height:100dvh}
.col{min-width:0;min-height:0;display:flex;flex-direction:column;position:relative}
.sidebar{background:linear-gradient(180deg,#FBFCFA,#EEF0EC);border-right:1px solid var(--line-soft)}
.list{background:var(--panel-2);border-right:1px solid var(--line-soft)}
.conversation{background:var(--chat-bg)}
.context{background:#FFFFFF;border-left:1px solid var(--line-soft)}
.zone-head{height:60px;flex:0 0 60px;display:flex;align-items:center;gap:10px;padding:0 16px;border-bottom:1px solid var(--line-soft)}
.scroll{overflow-y:auto;overflow-x:hidden;flex:1;min-height:0}
/* sidebar */
.brand{display:flex;align-items:center;gap:11px;padding:18px 18px 14px}
.brand .logo{width:112px;height:30px;flex:0 0 auto;display:flex;align-items:center;background:transparent;border:0;box-shadow:none}
.brand .logo img{max-width:112px;max-height:30px;display:block}
.brand .name{font-weight:650;font-size:12px;letter-spacing:0.02em;line-height:1.1;color:var(--muted);text-transform:uppercase}
.brand .name span{display:none}
.sidebar{align-items:stretch}.brand{justify-content:center;padding:18px 10px 14px}.brand .logo{width:58px;height:38px;justify-content:center}.brand .logo img{max-width:50px;max-height:34px;object-fit:contain}.brand .name{display:none}.nav{display:none}.appnav{width:100%;padding:4px 10px 10px;display:flex;flex-direction:column;gap:5px}.appnav button{width:100%;border:1px solid transparent;background:transparent;color:#667064;border-radius:12px;padding:10px 6px;display:flex;flex-direction:column;align-items:center;gap:6px;font-size:10.5px;font-weight:650;line-height:1.05;letter-spacing:-.01em;transition:background .14s,color .14s,border-color .14s}.appnav button:hover{background:rgba(20,28,20,.045);color:#283129}.appnav button.on{background:rgba(20,28,20,.075);color:#111812;border-color:rgba(20,28,20,.075);box-shadow:none}.appnav button.on::before{content:"";width:20px;height:2px;border-radius:99px;background:var(--accent);order:3;margin-top:1px}.appnav .ico{width:22px;height:22px;display:grid;place-items:center;color:currentColor}.appnav .ico svg{width:19px;height:19px;display:block;stroke:currentColor;fill:none;stroke-width:1.75;stroke-linecap:round;stroke-linejoin:round}.appnav .lbl{white-space:nowrap}.conn-foot{width:100%;margin-top:auto;padding:10px 8px}.conn-btn{justify-content:center}.conn-btn .cl-label,.conn-badge{display:none}.profile-actions{display:flex;gap:6px;margin-left:auto}.profile-actions button{width:28px;height:28px;border-radius:9px;border:1px solid var(--line-soft);background:var(--surface);color:var(--txt-2);display:grid;place-items:center}.theme-btn::before{content:'◐';font-size:13px}.logout-btn svg{width:14px;height:14px}.me{padding:8px 8px 12px;justify-content:center}.me .nm{display:none}[data-theme="dark"] .sidebar{background:linear-gradient(180deg,#101913,#07100B)}[data-theme="dark"] .appnav button{color:#8D988F}[data-theme="dark"] .appnav button:hover{background:rgba(255,255,255,.045);color:#EEF4EE}[data-theme="dark"] .appnav button.on{background:rgba(255,255,255,.07);color:#F6F7F2;border-color:rgba(255,255,255,.06)}[data-theme="dark"] .list{background:var(--panel-2)}[data-theme="dark"] .context{background:#0B140F}[data-theme="dark"] .composer{background:#0B140F}[data-theme="dark"] .task-line{background:var(--panel)}[data-theme="dark"] .logout-link{background:var(--surface)}[data-theme="dark"] .brow.out .btime{color:rgba(244,247,240,.55)}

.nav{padding:6px 10px 4px;overflow-y:auto}
.nav-label{font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:var(--muted);padding:14px 10px 7px}
.q{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:var(--radius-sm);color:var(--txt-2);font-weight:500;font-size:13.5px;cursor:pointer;position:relative;transition:.12s;user-select:none}
.q:hover{background:var(--surface);color:var(--txt)}.q.active{background:var(--surface-2);color:var(--txt)}
.q.active::before{content:"";position:absolute;left:-10px;top:50%;transform:translateY(-50%);width:3px;height:18px;border-radius:0 3px 3px 0;background:var(--accent)}
.q .ic{width:17px;height:17px;flex:0 0 auto;opacity:.85}
.q .qlabel{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.q .count{font-size:11.5px;font-weight:600;color:var(--muted);min-width:18px;text-align:right;font-variant-numeric:tabular-nums}
.q.active .count{color:var(--txt-2)}.q .count.hot{color:var(--accent)}
.chips{border-top:1px solid var(--line-soft);padding:12px 14px 14px;margin-top:auto}
.chips h4{font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:var(--muted);margin:2px 2px 10px;display:flex;justify-content:space-between;align-items:center}
.chips h4 .legend{font-weight:500;letter-spacing:0;text-transform:none;color:var(--muted);font-size:10.5px}
.chip-row{display:flex;align-items:center;gap:9px;padding:5px 4px;font-size:12.5px}
.chip-row .st{width:7px;height:7px;border-radius:50%;flex:0 0 auto}
.st.on{background:var(--success);box-shadow:0 0 0 3px var(--success-soft)}
.st.warn{background:var(--warning);box-shadow:0 0 0 3px var(--warning-soft)}
.st.off{background:var(--muted);box-shadow:0 0 0 3px rgba(255,255,255,0.05)}
.chip-row .who{flex:1;color:var(--txt-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.chip-row .vol{font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums}
.me{width:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;padding:10px 6px 12px;border-top:1px solid var(--line-soft);position:relative;cursor:default}.me:hover{background:rgba(20,28,20,.045)}
.avatar{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;font-size:12px;font-weight:700;flex:0 0 auto;color:#0a0a0a}
.me .nm{display:none!important}.logout-link{display:none}.profile-actions{margin-left:0!important;display:flex;flex-direction:column;gap:6px}.profile-actions button{width:32px;height:32px;border-radius:11px}.me:hover .logout-link{color:#1F3D2B;border-color:rgba(31,61,43,.25)}
/* list */
.search{flex:1;display:flex;align-items:center;gap:9px;background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:0 11px;height:38px;transition:.14s}
.search:focus-within{border-color:var(--line-strong);background:var(--surface-2)}
.search svg{width:15px;height:15px;color:var(--muted);flex:0 0 auto}
.search input{flex:1;background:none;border:0;outline:0;color:var(--txt);font-size:13.5px}
.search input::placeholder{color:var(--muted)}
.search kbd{font-size:10.5px;color:var(--muted);border:1px solid var(--line);border-radius:5px;padding:1px 5px;background:var(--bg)}
.list-sub{display:flex;align-items:center;gap:8px;padding:11px 14px 9px;border-bottom:1px solid var(--line-soft);min-width:0}
.list-sub .title{font-weight:700;font-size:14px;white-space:nowrap}.list-sub .n{font-size:11.5px;color:var(--muted);font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.list-sub .spacer{flex:1}
.live-status{display:inline-flex;align-items:center;gap:5px;font-size:11px;color:var(--muted);font-weight:500;white-space:nowrap;min-width:0;flex:0 1 auto;overflow:hidden}
.live-dot{width:6px;height:6px;border-radius:50%;background:#2BB673;box-shadow:0 0 0 3px rgba(43,182,115,.16);flex:0 0 auto;animation:livePulse 2.2s ease-in-out infinite}
.live-status.paused .live-dot{background:var(--muted);box-shadow:none;animation:none}
.live-txt{font-weight:600;color:var(--txt-2)}.live-status.paused .live-txt{color:var(--muted)}
.live-ago{color:var(--muted);overflow:hidden;text-overflow:ellipsis}
.live-refresh{flex:0 0 auto;border:1px solid var(--line);background:var(--surface);color:var(--txt-2);border-radius:8px;padding:4px 8px;font-size:11px;font-weight:650;line-height:1;cursor:pointer;transition:.12s}
.live-refresh:hover{background:var(--surface-2);color:var(--txt);border-color:var(--line-strong)}
.live-refresh:active{transform:scale(.96)}
@keyframes livePulse{0%,100%{opacity:1}50%{opacity:.4}}
@media(max-width:760px){.live-ago{display:none}.live-refresh{padding:4px 7px}}
.filter-toggle{margin-left:auto;border:1px solid var(--line);background:var(--surface);color:var(--txt-2);border-radius:9px;padding:5px 9px;font-size:11.5px;font-weight:650}.filter-toggle.on{background:var(--accent-dim);color:var(--accent);border-color:var(--line-strong)}.filterbar{display:none;gap:7px;padding:8px 12px;border-bottom:1px solid var(--line-soft);overflow-x:auto;scrollbar-width:none}.filterbar.open{display:flex}.filterbar::-webkit-scrollbar{display:none}.wfilter{flex:0 0 auto;border:1px solid var(--line);background:var(--surface);color:var(--txt-2);border-radius:999px;padding:6px 10px;font-size:12px;font-weight:600;white-space:nowrap}.wfilter.on{background:var(--accent-dim);border-color:var(--line-strong);color:var(--accent)}.wfilter select{border:0;background:transparent;color:inherit;font:inherit;outline:0;max-width:150px}.wfilter.clear{color:var(--danger);background:var(--danger-soft)}

.seg{display:flex;background:var(--surface);border:1px solid var(--line);border-radius:9px;padding:2px;gap:2px}
.seg button{border:0;background:none;color:var(--txt-2);font-size:11.5px;font-weight:600;padding:4px 9px;border-radius:7px;transition:.12s}
.seg button.on{background:var(--surface-hi);color:var(--txt)}
.filters{display:flex;gap:7px;padding:9px 14px;overflow-x:auto;border-bottom:1px solid var(--line-soft);scrollbar-width:none}
.filters::-webkit-scrollbar{display:none}
.fchip{flex:0 0 auto;font-size:12px;font-weight:500;color:var(--txt-2);background:var(--surface);border:1px solid var(--line);border-radius:99px;padding:5px 11px;display:flex;align-items:center;gap:6px;transition:.12s;white-space:nowrap}
.fchip:hover{background:var(--surface-2);color:var(--txt)}
.fchip.on{background:var(--accent-dim);border-color:rgba(205,235,0,0.32);color:var(--accent)}
.fchip .av{width:16px;height:16px;border-radius:50%;font-size:8.5px;display:grid;place-items:center;font-weight:700;color:#0a0a0a}
.cards{padding:5px 8px}
.card{display:block;width:100%;text-align:left;border:1px solid transparent;background:none;border-radius:12px;padding:10px 11px 9px 32px;margin-bottom:1px;position:relative;transition:.12s}
.card:hover{background:var(--surface)}.card.active{background:var(--surface-2);border-color:var(--line-soft)}
.card.reply{background:rgba(205,235,0,0.045)}
.card.reply:hover{background:rgba(205,235,0,0.075)}
.card.reply::after{content:"";position:absolute;left:0;top:9px;bottom:9px;width:3px;border-radius:0 3px 3px 0;background:var(--accent);opacity:.78}
.card.active.reply::after{opacity:1}
.card.new-top{animation:newTop 8s ease-out forwards}
@keyframes newTop{0%{background:var(--accent-soft);box-shadow:inset 0 0 0 1px rgba(43,182,115,.35)}12%{background:var(--accent-soft)}100%{background:none;box-shadow:inset 0 0 0 1px transparent}}
.card.new-top:hover{background:var(--surface)}
.card.readonly{background:linear-gradient(180deg,rgba(205,235,0,.045),var(--surface));border-color:rgba(31,61,43,.13);opacity:1}.readonly-banner{margin:0 0 9px;padding:10px 12px;border:1px solid rgba(31,61,43,.16);background:var(--accent-dim);color:var(--txt-2);border-radius:12px;font-size:12px;line-height:1.4}.readonly-banner b{color:var(--accent)}.inst-map{display:flex;flex-wrap:wrap;gap:5px;margin:5px 0 7px}.inst-pill{display:inline-flex;align-items:center;gap:5px;border:1px solid var(--line-soft);background:var(--panel);border-radius:999px;padding:3px 8px;font-size:11px;color:var(--txt-2);font-weight:650}.inst-pill.owner{background:rgba(205,235,0,.13);border-color:rgba(205,235,0,.25);color:var(--accent)}.inst-pill.sender{background:var(--surface);color:var(--muted)}.readonly-help{margin:4px 10px 9px;padding:8px 10px;border-radius:10px;background:var(--surface);border:1px solid var(--line-soft);font-size:11.5px;color:var(--txt-2);line-height:1.35}.readonly-help b{color:var(--accent)}

.card .row1{display:flex;align-items:center;gap:8px;margin-bottom:2px}
.card .company{font-weight:650;font-size:13.5px;letter-spacing:-0.012em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1}
.card .time{font-size:10.5px;color:var(--muted);font-variant-numeric:tabular-nums;flex:0 0 auto}
.card .time.urgent{color:var(--accent);font-weight:600}
.card .contact{font-size:12px;color:var(--txt-2);margin-bottom:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.card .preview{font-size:12.5px;color:var(--muted);line-height:1.4;display:flex;gap:6px;margin-bottom:7px}
.card .preview .from{font-weight:600;flex:0 0 auto}
.card .preview .from.lead{color:var(--accent)}.card .preview .from.sdr{color:var(--txt-2)}.card .preview .from.auto{color:var(--info)}
.card .preview .txt{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--txt-2)}
.card .row3{display:flex;align-items:center;gap:5px;flex-wrap:wrap;row-gap:4px}.card .row3 .spacer{flex:1}
.badge{font-size:10px;font-weight:600;border-radius:6px;padding:2px 6px;display:inline-flex;align-items:center;gap:4px;white-space:nowrap}
.b-diag{background:var(--info-soft);color:#9fb8ff}.b-pc{background:var(--warning-soft);color:var(--warning)}
.b-reply{background:var(--success-soft);color:var(--success)}.b-done{background:var(--surface-hi);color:var(--txt-2)}.b-hs{background:rgba(255,107,107,.12);color:var(--danger);border:1px solid rgba(255,107,107,.18)}
.b-shared{background:rgba(205,235,0,.10);color:var(--accent);border:1px solid rgba(205,235,0,.18)}
.b-new{background:var(--surface-hi);color:var(--txt-2)}.b-meet{background:rgba(194,164,255,.16);color:#c2a4ff}
.b-pend{background:var(--warning-soft);color:var(--warning)}.b-res{background:var(--success-soft);color:var(--success)}
.b-note{background:var(--info-soft);color:#9fb8ff}.b-risk{background:var(--danger-soft);color:var(--danger)}.b-arch{background:var(--surface-hi);color:var(--muted);border:1px solid var(--line-soft)}
.sla{font-size:10.5px;font-weight:600;display:inline-flex;align-items:center;gap:5px;color:var(--muted);font-variant-numeric:tabular-nums}
.sla .pulse{width:6px;height:6px;border-radius:50%;background:currentColor}
.sla.now{color:var(--accent)}.sla.now .pulse{animation:pulse 1.8s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(205,235,0,.5)}70%{box-shadow:0 0 0 6px rgba(205,235,0,0)}100%{box-shadow:0 0 0 0 rgba(205,235,0,0)}}
.owner{display:inline-flex;align-items:center;gap:5px;font-size:11px;color:var(--muted)}
.owner .av{width:16px;height:16px;border-radius:50%;font-size:8px;display:grid;place-items:center;font-weight:700;color:#0a0a0a}
.chiptag{font-size:10px;color:var(--muted);background:var(--surface);border:1px solid var(--line-soft);border-radius:5px;padding:1.5px 6px}
.card-archive{position:absolute;right:9px;bottom:8px;border:1px solid var(--line-soft);background:var(--surface);color:var(--muted);border-radius:999px;padding:2px 7px;font-size:10.5px;font-weight:700;opacity:0;transition:.12s}.card:hover .card-archive,.card.archived .card-archive{opacity:1}.card-archive:hover{background:var(--surface-2);color:var(--txt)}
.empty{padding:60px 28px;text-align:center;color:var(--muted)}
.empty b{display:block;color:var(--txt-2);font-weight:600;font-size:14px;margin-bottom:5px}.empty span{font-size:12.5px}
/* conversation */
.conv-head{display:flex;align-items:center;gap:12px}
.back-btn{display:none}.conv-head .ttl{flex:1;min-width:0}
.conv-head .ttl b{font-weight:650;font-size:15px;letter-spacing:-0.015em;display:flex;align-items:center;gap:8px}
.conv-head .ttl .sub{font-size:12px;color:var(--txt-2);margin-top:1px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.conv-head .ttl .sub .dotsep{width:3px;height:3px;border-radius:50%;background:var(--muted)}
.conv-head .ttl b .company-title{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.conv-head .ttl b .phone-fallback{color:var(--muted);font-weight:650}.conv-head .ttl .sub .contact-name{font-weight:650;color:var(--txt)}
.card .contact .phone-mini{color:var(--muted);font-weight:500}.card .company.phone-fallback{color:var(--muted)}
.head-actions{display:flex;align-items:center;gap:7px}
.btn{border:1px solid rgba(31,61,43,.16);background:var(--surface);color:var(--txt);font-size:12.5px;font-weight:600;border-radius:999px;padding:7px 13px;display:inline-flex;align-items:center;gap:6px;transition:.12s;white-space:nowrap;box-shadow:0 1px 2px rgba(20,28,20,.06)}
.btn:hover{background:var(--surface-2);border-color:rgba(31,61,43,.26);transform:translateY(-1px)}.btn svg{width:14px;height:14px}
.btn.primary{background:var(--btn-ink);border-color:var(--btn-lime-line);color:var(--btn-lime);box-shadow:0 5px 14px var(--btn-ink-shadow)}
.btn.ghost{background:none;border-color:transparent;padding:7px 9px;color:var(--txt-2)}.btn.ghost:hover{background:var(--surface);color:var(--txt)}
.icon-btn{width:32px;height:32px;border-radius:8px;border:1px solid var(--line);background:var(--surface);display:grid;place-items:center;color:var(--txt-2);transition:.12s;flex:0 0 auto}
.icon-btn:hover{background:var(--surface-2);color:var(--txt)}.icon-btn svg{width:15px;height:15px}
.timeline{flex:1;overflow-y:auto;padding:18px 7% 14px;display:flex;flex-direction:column;gap:2px;min-height:0;background-image:radial-gradient(var(--chat-dot) 1px,transparent 0);background-size:22px 22px}
.day-sep{display:flex;justify-content:center;margin:16px 0 10px}
.day-sep span{font-size:10.5px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--txt-2);background:var(--surface-2);border:1px solid var(--line-soft);border-radius:8px;padding:4px 12px;box-shadow:0 1px 2px rgba(0,0,0,.12)}
.event{align-self:center;max-width:min(440px,82%);width:auto;margin:5px 0}
.event-card{border:1px solid var(--line-soft);background:var(--surface);border-radius:10px;padding:8px 11px;display:flex;gap:9px;align-items:flex-start}
.event-card .eic{width:24px;height:24px;border-radius:7px;flex:0 0 auto;display:grid;place-items:center;background:var(--info-soft);color:var(--info);font-size:12px}
.event-card .eic.sender-eic{border-radius:50%;font-size:10px;font-weight:850;color:#07100B;box-shadow:inset 0 0 0 1px rgba(255,255,255,.2)}
.event-card.warn .eic{background:var(--warning-soft);color:var(--warning)}
.event-card .ebody{flex:1;min-width:0}
.event-card .etitle{font-weight:600;font-size:12px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.event-card .etitle .et{font-size:10px;color:var(--muted);font-weight:500}
.event-card .sender-line{display:inline-flex;align-items:center;gap:7px;color:var(--txt);font-size:13px;font-weight:800;line-height:1.15}
.event-card .sender-line .sender-av{width:20px;height:20px;border-radius:50%;display:grid;place-items:center;font-size:10px;font-weight:850;color:#07100B;box-shadow:inset 0 0 0 1px rgba(255,255,255,.18)}
.event-card .edesc{font-size:11.5px;color:var(--txt-2);margin-top:2px;white-space:pre-wrap;line-height:1.4}
.pdf{margin-top:9px;border:1px solid var(--line);background:var(--panel);border-radius:11px;padding:10px 11px;display:flex;align-items:center;gap:11px;max-width:330px;transition:.12s;text-decoration:none}
.pdf:hover{border-color:var(--line-strong);background:var(--surface)}
.pdf .pic{width:38px;height:46px;border-radius:7px;flex:0 0 auto;display:grid;place-items:center;background:linear-gradient(160deg,#3a1414,#1c0c0c);border:1px solid rgba(255,107,107,.25)}
.pdf .pic span{font-size:8px;font-weight:800;color:#ff8b8b}
.pdf .pmeta{flex:1;min-width:0}.pdf .pmeta b{display:block;font-size:12.5px;font-weight:600;color:var(--txt);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pdf .pmeta span{font-size:11px;color:var(--muted)}
.brow{display:flex;flex-direction:column;max-width:68%;gap:2px;margin-bottom:1px}
.brow.out{align-self:flex-end;align-items:flex-end}.brow.in{align-self:flex-start;align-items:flex-start}
.brow.grp-start{margin-top:9px}
.bubble{padding:6px 9px 7px;border-radius:9px;font-size:13.5px;line-height:1.42;white-space:pre-wrap;border:1px solid transparent;position:relative;word-break:break-word;box-shadow:0 1px 1px rgba(0,0,0,.16);min-width:78px}
.brow.out .bubble{background:var(--bubble-out)}
.brow.in .bubble{background:var(--bubble-in);border-color:var(--line-soft)}
.brow.out.grp-start .bubble{border-top-right-radius:3px}
.brow.in.grp-start .bubble{border-top-left-radius:3px}
.brow.lead.grp-start .bubble{border-color:rgba(205,235,0,0.30)}
.bwho{display:flex;gap:6px;align-items:center;flex-wrap:wrap;font-size:11.5px;font-weight:600;color:var(--txt-2);margin-bottom:2px;line-height:1.2}
.brow.lead .bwho{color:var(--accent)}
.bwho .chip-who{font-size:10.5px;color:var(--txt-2);background:rgba(255,255,255,0.07);border:1px solid var(--line);border-radius:5px;padding:1px 6px}
.bwho .sender-who{display:inline-flex;align-items:center;gap:7px;font-size:13px;font-weight:800;color:var(--txt);background:transparent;border:0;border-radius:0;padding:0}
.bwho .sender-av{width:20px;height:20px;border-radius:50%;display:grid;place-items:center;font-size:10px;font-weight:850;color:#07100B;box-shadow:inset 0 0 0 1px rgba(255,255,255,.18)}
.bwho .autobadge{font-size:9.5px;font-weight:600;color:var(--info);background:var(--info-soft);border-radius:5px;padding:1px 6px}
.bwho .dispatch-who{font-size:10.5px;color:var(--accent);background:var(--accent-soft);border:1px solid var(--btn-lime-line);border-radius:5px;padding:1px 6px}
.btime{float:right;margin:6px 0 -2px 10px;font-size:10px;color:var(--muted);line-height:1;position:relative;top:3px;font-variant-numeric:tabular-nums;user-select:none}
.bubble.has-media .btime{float:none;display:block;text-align:right;margin:7px 0 0;top:0;clear:both}
.bubble.has-media .pdf{margin-top:4px;margin-bottom:2px;max-width:280px}
.bubble.has-media .pdf .pmeta span{color:var(--txt-2)}
.pdf.disabled{pointer-events:none;opacity:.78}.pdf.disabled .pic{background:var(--surface-2)}
.audio-card{margin-top:9px;border:1px solid var(--line);background:var(--panel);border-radius:14px;padding:10px 11px;display:grid;grid-template-columns:34px minmax(0,1fr);gap:10px;max-width:340px}.audio-card .aic{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:var(--btn-ink);color:var(--btn-lime);border:1px solid var(--btn-lime-line);font-size:14px}.audio-card .ameta{min-width:0}.audio-card .ameta b{display:block;font-size:12px;color:var(--txt);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:5px}.audio-card audio{width:100%;height:32px}.audio-card .adownload{display:inline-block;margin-top:5px;font-size:11px;color:var(--muted);text-decoration:none}.audio-card .adownload:hover{color:var(--txt)}.bubble.has-media .audio-card{margin-top:4px;margin-bottom:2px;max-width:300px}
.file-modal .modal-card{width:min(1120px,calc(100vw - 28px));height:min(92vh,880px);max-width:none;max-height:92vh;display:grid;grid-template-rows:auto minmax(0,1fr)}.file-modal .modal-head{min-width:0}.file-modal .modal-head b{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.file-modal .modal-body{padding:0;overflow:hidden;min-height:0;height:100%;display:block}.file-preview{height:100%;min-height:0;background:#111;border-top:1px solid var(--line-soft)}.file-preview iframe{display:block;width:100%;height:100%;min-height:calc(min(92vh,880px) - 62px);border:0;background:#111}.file-preview-fallback{height:100%;display:grid;place-items:center;padding:24px;text-align:center;color:var(--txt-2)}.file-preview-fallback b{display:block;color:var(--txt);margin-bottom:6px}.file-actions{display:flex;gap:8px;align-items:center}.file-actions a,.file-actions button{border:1px solid var(--line-soft);background:var(--surface);color:var(--txt);border-radius:999px;padding:7px 11px;font-size:12px;font-weight:850;text-decoration:none}.file-actions a.primary{background:var(--btn-ink);color:var(--btn-lime);border-color:var(--btn-lime-line)}
/* CH-UX-ANALYTICS: telas de análise em desktop usam a largura toda, sem painel vazio de conversa/contexto. */
.app.analytics-mode{grid-template-columns:var(--sidebar-w) minmax(0,1fr)}
.app.analytics-mode .conversation,.app.analytics-mode .context{display:none}
.app.analytics-mode .list{border-right:0;background:var(--bg)}
.app.analytics-mode .cards{padding:16px 22px 32px;max-width:1440px;width:100%;margin:0 auto}
.app.analytics-mode .list-sub{padding-left:22px;padding-right:22px;background:var(--panel-2)}
.app.analytics-mode .zone-head{background:var(--panel-2)}
.app.analytics-mode .mgmt-panel,.app.analytics-mode .focus-panel{padding:0;gap:16px}
.app.analytics-mode .mgmt-grid{grid-template-columns:repeat(4,minmax(0,1fr))}
.app.analytics-mode .focus-grid{grid-template-columns:repeat(auto-fit,minmax(190px,1fr))}
.app.analytics-mode .mgmt-card,.app.analytics-mode .focus-card{min-height:124px}
.app.analytics-mode .focus-card small{display:block;font-size:11.5px;color:var(--muted);line-height:1.35}
.pipe-filterbar{border:1px solid var(--line-soft);background:var(--surface);border-radius:16px;padding:12px;display:grid;grid-template-columns:minmax(220px,1fr) auto auto auto;gap:12px;align-items:center}.pipe-filterbar>b{font-size:12px}.pipe-filterbar span{display:block;font-size:11.5px;color:var(--muted);line-height:1.35}.pf-group{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.pf-group em{font-style:normal;font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);font-weight:850;margin-right:2px}.pf-group button{border:1px solid var(--line-soft);background:var(--panel);color:var(--txt-2);border-radius:999px;padding:6px 9px;font-size:11.5px;font-weight:750}.pf-group button.clear{color:var(--danger);background:var(--danger-soft)}.pf-group button b{margin-right:4px;color:var(--txt);font-variant-numeric:tabular-nums}.pf-group button.on{background:rgba(205,235,0,.13);border-color:rgba(205,235,0,.38);color:var(--accent)}.focus-card.sample-on{border-color:rgba(205,235,0,.44);box-shadow:0 0 0 2px rgba(205,235,0,.08) inset}.focus-card.insight{cursor:pointer}.focus-card.insight.warn b{color:var(--warning)}.focus-card.insight.hot b{color:var(--accent)}.mini-hint{font-size:11.5px;color:var(--muted);margin:-4px 0 8px}.activity-tags{display:flex;gap:5px;flex-wrap:wrap;margin-top:5px}.atype{font-size:10.5px;font-weight:750;border:1px solid var(--line-soft);background:var(--surface-2);color:var(--muted);border-radius:999px;padding:2px 7px}.atype.on{background:rgba(205,235,0,.11);border-color:rgba(205,235,0,.32);color:var(--accent)}.filter-note{font-style:normal;color:var(--accent);font-size:10px;margin-left:6px}
.focus-card .plain-label{display:block;font-size:12px;font-weight:800;color:var(--txt);margin-top:2px}.focus-card .plain-label em{font-style:normal;color:var(--accent)}
.stage-stack{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:2px 0 4px}.stage-stack .stage-pill{border:1px solid var(--line-soft);background:var(--surface-2);border-radius:10px;padding:7px 6px}.stage-stack b{font-size:20px!important;line-height:1!important}.stage-stack span{font-size:10.5px!important;line-height:1.15!important;color:var(--muted)!important;display:block!important;margin-top:2px}

.pipe-simple-head{border:1px solid var(--line-soft);background:var(--surface);border-radius:16px;padding:14px 16px;display:flex;align-items:flex-start;justify-content:space-between;gap:14px}
.pipe-simple-head b{display:block;font-size:15px;color:var(--txt);margin-bottom:3px}.pipe-simple-head span{display:block;font-size:12px;color:var(--muted);line-height:1.45;max-width:720px}.pipe-simple-head .stamp{font-size:11px;color:var(--muted);white-space:nowrap;border:1px solid var(--line-soft);border-radius:999px;padding:5px 9px;background:var(--panel)}
.pipe-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.pipe-sum{border:1px solid var(--line-soft);background:var(--surface);border-radius:14px;padding:12px 13px;min-width:0;cursor:pointer;text-align:left;transition:transform .12s,background .12s,border-color .12s,box-shadow .12s}.pipe-sum:hover{background:var(--surface-2);border-color:var(--line-strong);transform:translateY(-1px);box-shadow:0 10px 24px rgba(20,28,20,.06)}.pipe-sum b{display:block;font-size:26px;line-height:1;color:var(--txt);font-variant-numeric:tabular-nums}.pipe-sum span{display:block;margin-top:5px;font-size:12px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pipe-sum small{display:block;margin-top:8px;font-size:10.5px;color:var(--muted)}.pipe-sum.zero b,.pipe-sum.mid b,.pipe-sum.done b{color:var(--txt)}
.pipe-note{font-size:12px;color:var(--muted);line-height:1.45;margin:-2px 2px 0}.pipe-note b{color:var(--txt)}
.pipe-state{border:1px solid var(--line-soft);background:var(--surface);border-radius:16px;padding:18px;color:var(--muted);font-size:13px}.pipe-state b{display:block;color:var(--txt);font-size:15px;margin-bottom:4px}.pipe-state button{margin-top:10px;border:1px solid var(--line-soft);background:var(--btn-ink);color:var(--btn-lime);border-radius:999px;padding:8px 12px;font-weight:800}.pipe-skeleton{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.pipe-skel{height:82px;border:1px solid var(--line-soft);border-radius:14px;background:linear-gradient(90deg,var(--surface),var(--surface-2),var(--surface));background-size:200% 100%;animation:pipePulse 1.2s linear infinite}@keyframes pipePulse{to{background-position:-200% 0}}
.app.analytics-mode .pipe-table{overflow-x:auto;padding-bottom:2px}.app.analytics-mode .pipe-tr{min-width:650px}.app.analytics-mode .pipe-tr span:first-child{font-weight:750}
.pipe-act-group{display:flex;flex-direction:column;gap:7px}.pipe-act-group-title{font-size:10.5px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:850;margin:2px 0 0}.pipe-act-upcoming{border-color:rgba(122,90,0,.22);background:rgba(122,90,0,.045)}
#pipeModal .modal-card{width:min(920px,calc(100vw - 40px));max-width:none}.pipe-modal-list{display:flex;flex-direction:column;gap:8px}.pipe-modal-toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}.pipe-modal-toolbar span{font-size:12px;color:var(--muted)}.pipe-modal-toolbar input{border:1px solid var(--line-soft);background:var(--surface);color:var(--txt);border-radius:10px;padding:8px 10px;font-size:13px;min-width:240px}.pipe-lead-row{border:1px solid var(--line-soft);background:var(--surface);border-radius:12px;padding:10px 11px}.pipe-lead-top{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center}.pipe-lead-main{min-width:0;cursor:pointer}.pipe-lead-row .fn{font-size:13px;font-weight:800;color:var(--txt);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pipe-lead-row .fm{font-size:11.5px;color:var(--muted);margin-top:3px;line-height:1.35}.pipe-lead-row .badges{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}.pipe-lead-actions{display:flex;align-items:center;gap:7px}.pipe-lead-actions button,.pipe-lead-actions a{border:1px solid var(--line-soft);background:var(--panel);color:var(--txt);text-decoration:none;border-radius:999px;padding:7px 10px;font-size:12px;font-weight:800;white-space:nowrap}.pipe-lead-actions button{cursor:pointer}.pipe-acts{display:none;margin-top:10px;border-top:1px solid var(--line-soft);padding-top:9px}.pipe-lead-row.open .pipe-acts{display:flex;flex-direction:column;gap:7px}.pipe-act{display:grid;grid-template-columns:96px minmax(0,1fr) auto;gap:9px;align-items:start;border:1px solid var(--line-soft);background:var(--panel);border-radius:10px;padding:8px}.pipe-act-time{font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums}.pipe-act-label{font-size:12px;color:var(--txt);line-height:1.35;min-width:0}.pipe-act-kind{font-size:10.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;border:1px solid var(--line-soft);border-radius:999px;padding:2px 6px;white-space:nowrap}.pipe-empty-acts{font-size:12px;color:var(--muted);border:1px dashed var(--line);border-radius:10px;padding:9px}
.app.analytics-mode .mgmt-panel,.app.analytics-mode .focus-panel{padding:14px 18px 22px!important;gap:12px!important}.app.analytics-mode .mgmt-section{background:var(--surface);border-radius:16px}.app.analytics-mode .pipe-tr{background:var(--panel);border-radius:10px}.app.analytics-mode .pipe-tr.head{background:var(--surface-2)}
@media(max-width:980px){.pipe-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.pipe-simple-head{flex-direction:column}.pipe-simple-head .stamp{white-space:normal}}
@media(max-width:560px){.pipe-summary{grid-template-columns:1fr}}

.perf-hero{border:1px solid var(--line-soft);background:linear-gradient(180deg,var(--surface),var(--panel));border-radius:18px;padding:16px;display:grid;grid-template-columns:1.05fr .95fr;gap:16px}.perf-title>b{display:block;font-size:18px;letter-spacing:-.02em}.perf-title span{display:block;color:var(--muted);font-size:12.5px;line-height:1.45;margin-top:4px;max-width:780px}.perf-title span b{display:inline;font-size:inherit;color:var(--txt);letter-spacing:0}.perf-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:14px}.perf-kpi{border:1px solid var(--line-soft);background:var(--surface);border-radius:14px;padding:12px;min-height:76px;display:flex;flex-direction:column;justify-content:space-between}.perf-kpi b{display:block;font-size:24px;line-height:1;color:var(--txt);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.perf-kpi span{display:block;font-size:11px;color:var(--muted);margin-top:7px;line-height:1.25}.perf-chart{border:1px solid var(--line-soft);background:var(--surface);border-radius:16px;padding:14px;display:flex;flex-direction:column;gap:11px}.perf-chart h4,.perf-board h4{margin:0;font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}.funnel-row{display:grid;grid-template-columns:116px 1fr 58px;gap:10px;align-items:center;font-size:12px;color:var(--txt)}.funnel-track{height:15px;border-radius:999px;background:rgba(31,61,43,.08);overflow:hidden;border:1px solid rgba(31,61,43,.16)}.funnel-fill{display:block;min-width:4px;height:100%;border-radius:999px;background:linear-gradient(90deg,#1F3D2B,#9FB800)}.perf-board{border:1px solid var(--line-soft);background:var(--surface);border-radius:16px;padding:14px;display:flex;flex-direction:column;gap:8px}.perf-owner{display:grid;grid-template-columns:minmax(130px,1fr) 80px minmax(120px,1.2fr) 70px;gap:10px;align-items:center;border-top:1px solid var(--line-soft);padding-top:9px;font-size:12px}.perf-owner:first-of-type{border-top:0}.perf-owner b{font-size:13px}.perf-owner small{color:var(--muted);font-size:11px}.perf-bar{height:9px;border-radius:999px;background:var(--surface-2);overflow:hidden;border:1px solid var(--line-soft)}.perf-bar i{display:block;height:100%;border-radius:999px;background:var(--btn-lime)}.perf-note{font-size:11.5px;color:var(--muted);line-height:1.4;margin-top:2px}.perf-secondary{display:grid;grid-template-columns:1fr;gap:12px}@media(max-width:1100px){.perf-hero{grid-template-columns:1fr}.perf-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.perf-owner{grid-template-columns:1fr 70px;gap:6px}.perf-owner .perf-bar{grid-column:1/-1}}

.dispatch-board{border:1px solid var(--line-soft);background:linear-gradient(180deg,var(--surface),var(--panel));border-radius:18px;padding:14px;display:flex;flex-direction:column;gap:12px}.dispatch-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.dispatch-head b{display:block;font-size:15px}.dispatch-head span{display:block;color:var(--muted);font-size:12px;line-height:1.4;margin-top:3px}.dispatch-total{border:1px solid var(--line-soft);border-radius:999px;padding:6px 10px;font-size:12px;font-weight:800;color:var(--txt);white-space:nowrap;background:var(--surface-2)}.dispatch-chart{height:230px;display:flex;align-items:flex-end;gap:10px;padding:8px 4px 0;border-bottom:1px solid var(--line-soft);overflow-x:auto}.dispatch-col{min-width:42px;flex:1;display:flex;flex-direction:column;align-items:center;gap:6px;border:0;background:transparent;color:var(--txt);padding:0;cursor:pointer}.dispatch-col:hover .dispatch-stack{transform:translateY(-3px);box-shadow:0 14px 28px rgba(31,61,43,.16)}.dispatch-col.on .dispatch-stack{outline:2px solid var(--btn-lime);outline-offset:2px}.dispatch-col .n{font-size:11px;font-weight:850;color:var(--txt);height:14px}.dispatch-col .d{font-size:10.5px;color:var(--muted);font-weight:700}.dispatch-stack{width:100%;max-width:54px;height:var(--h);min-height:4px;border-radius:10px 10px 3px 3px;background:var(--surface-2);border:1px solid var(--line-soft);overflow:hidden;display:flex;flex-direction:column-reverse;box-shadow:inset 0 1px 0 rgba(255,255,255,.18);transition:.14s}.dispatch-seg{width:100%;transition:opacity .12s,filter .12s}.dispatch-seg:hover{filter:brightness(1.05);opacity:.95}.dispatch-seg.dim{opacity:.18;filter:saturate(.55)}.dispatch-legend{display:flex;gap:7px;flex-wrap:wrap}.dispatch-chip{display:flex;align-items:center;gap:6px;border:1px solid var(--line-soft);background:var(--surface);border-radius:999px;padding:5px 8px;font-size:11.5px;color:var(--txt-2);cursor:pointer}.dispatch-chip:hover,.dispatch-chip.on{border-color:var(--btn-lime-line);color:var(--txt);box-shadow:inset 0 0 0 1px rgba(205,235,0,.22)}.dispatch-dot{width:8px;height:8px;border-radius:50%;flex:0 0 auto}.dispatch-detail{border:1px solid var(--line-soft);background:var(--surface);border-radius:14px;padding:10px}.dispatch-detail b{font-size:12px}.dispatch-detail .lines{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:6px;margin-top:8px}.dispatch-detail .line{font-size:11.5px;color:var(--txt-2);display:flex;align-items:center;gap:6px;border:1px solid transparent;background:transparent;border-radius:8px;padding:4px 6px;text-align:left;cursor:pointer}.dispatch-detail .line:hover{border-color:var(--line-soft);background:var(--surface-2);color:var(--txt)}.dispatch-rank{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}.dispatch-rank .r{border:1px solid var(--line-soft);background:var(--surface);border-radius:12px;padding:8px 10px;cursor:pointer}.dispatch-rank .r:hover,.dispatch-rank .r.on{border-color:var(--btn-lime-line)}.dispatch-rank b{display:block;font-size:18px}.dispatch-rank span{display:block;font-size:11px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.dispatch-modal-card{width:min(980px,calc(100vw - 36px));max-width:none}.dispatch-modal-list{display:flex;flex-direction:column;gap:8px}.dispatch-msg-row{border:1px solid var(--line-soft);background:var(--surface);border-radius:14px;padding:11px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px}.dispatch-msg-row h4{margin:0 0 3px;font-size:13px}.dispatch-msg-row small{display:block;color:var(--muted);font-size:11.5px}.dispatch-msg-row p{margin:8px 0 0;color:var(--txt-2);font-size:12px;line-height:1.45;white-space:pre-wrap;max-height:96px;overflow:auto}.dispatch-msg-row a{align-self:start;border:1px solid var(--btn-lime-line);background:var(--btn-ink);color:var(--btn-lime);border-radius:999px;padding:7px 10px;text-decoration:none;font-size:11.5px;font-weight:850;white-space:nowrap}

.cad-board{border:1px solid rgba(31,61,43,.14);background:linear-gradient(180deg,rgba(255,255,255,.72),rgba(31,61,43,.035));border-radius:18px;padding:14px;display:flex;flex-direction:column;gap:12px}
.cad-board-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.cad-board-head b{font-size:15px;display:block}.cad-board-head span{display:block;color:var(--muted);font-size:12px;line-height:1.45;margin-top:3px;max-width:720px}.cad-board-head button{border:1px solid var(--btn-lime-line);background:var(--btn-ink);color:var(--btn-lime);border-radius:999px;padding:7px 12px;font-weight:750;font-size:12px;white-space:nowrap}
.cad-stage-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.pipe-table{display:flex;flex-direction:column;gap:6px}.pipe-tr{display:grid;grid-template-columns:minmax(220px,1fr) repeat(6,64px);gap:8px;align-items:center;padding:9px 10px;border:1px solid var(--line-soft);border-radius:12px;background:var(--panel)}.pipe-tr.head{background:var(--surface);font-size:11px;color:var(--muted);font-weight:800;text-transform:uppercase;letter-spacing:.04em}.pipe-tr span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:650}.pipe-tr b,.pipe-tr em{text-align:right;font-style:normal;font-variant-numeric:tabular-nums}.pipe-tr em{color:var(--txt-2)}.cad-stage-summary{display:flex;flex-wrap:wrap;gap:7px}.cad-stage-summary span{border:1px solid var(--line-soft);background:var(--surface-2);border-radius:999px;padding:5px 10px;font-size:11.5px;font-weight:650;color:var(--txt-2)}.cad-stage-summary span.on{background:rgba(205,235,0,.12);border-color:rgba(205,235,0,.34);color:var(--accent)}.cad-stage-summary b{font-size:13px;color:var(--txt);margin-right:3px}.cad-stage{border:1px solid var(--line-soft);background:var(--panel);border-radius:16px;padding:12px;display:flex;flex-direction:column;gap:10px;min-width:0}.cad-stage-head{display:flex;align-items:center;gap:10px}.cad-stage-head .step{width:34px;height:34px;border-radius:12px;background:var(--btn-ink);color:var(--btn-lime);display:grid;place-items:center;font-size:17px;font-weight:850;flex:0 0 auto}.cad-stage-head div{min-width:0;flex:1}.cad-stage-head b{display:block;font-size:13px}.cad-stage-head small{display:block;color:var(--muted);font-size:11px;line-height:1.25;margin-top:2px}.cad-stage-head strong{font-size:24px;line-height:1;color:var(--txt);font-variant-numeric:tabular-nums}.cad-stage-action{border:1px solid rgba(205,235,0,.24);background:rgba(205,235,0,.10);border-radius:11px;padding:7px 9px;font-size:11.5px;color:var(--txt-2)}.cad-stage-rows{display:flex;flex-direction:column;gap:6px}.cad-stage .focus-row{padding:8px 0}.cad-stage .focus-row .fa{display:none}.cad-stage-foot{display:flex;gap:7px;margin-top:auto}.cad-stage-foot button{border:1px solid rgba(31,61,43,.14);background:var(--surface-2);border-radius:999px;padding:6px 10px;font-size:11.5px;font-weight:700;color:var(--txt-2)}.cad-edge-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:12px}.focus-section h4 em{font-style:normal;margin-left:6px;color:var(--txt);background:var(--surface-2);border:1px solid var(--line-soft);border-radius:999px;padding:1px 7px;font-size:10.5px}
@media(max-width:1180px){.app.analytics-mode .mgmt-grid,.app.analytics-mode .focus-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.cad-stage-grid{grid-template-columns:1fr}.cad-edge-grid{grid-template-columns:1fr}.pipe-filterbar{grid-template-columns:1fr}}
@media(max-width:760px){.app.analytics-mode{grid-template-columns:1fr}.app.analytics-mode .sidebar{display:none}.app.analytics-mode .cards{padding:10px 12px 88px}.app.analytics-mode .mgmt-grid,.app.analytics-mode .focus-grid{grid-template-columns:1fr}.cad-board-head{flex-direction:column}.cad-board-head button{width:100%;justify-content:center}}

.mgmt-panel{padding:14px;display:flex;flex-direction:column;gap:12px}.mgmt-title{display:flex;align-items:center;justify-content:space-between}.mgmt-title b{font-size:15px}.mgmt-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.mgmt-card{border:1px solid var(--line-soft);background:var(--surface);border-radius:14px;padding:12px}.mgmt-card b{font-size:22px;color:var(--txt);display:block;line-height:1}.mgmt-card span{font-size:11px;color:var(--muted)}.mgmt-section{border:1px solid var(--line-soft);background:var(--surface);border-radius:14px;padding:12px}.mgmt-section h4{margin:0 0 9px;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}.mgmt-row{display:flex;align-items:center;gap:8px;padding:7px 0;border-top:1px solid var(--line-soft);font-size:12.5px}.mgmt-row:first-of-type{border-top:0}.mgmt-row .bar{height:6px;background:var(--accent);border-radius:99px;min-width:4px}.mgmt-row em{margin-left:auto;font-style:normal;color:var(--txt-2);font-weight:700}.focus-panel{padding:14px;display:flex;flex-direction:column;gap:12px}.focus-hero{border:1px solid rgba(31,61,43,.12);background:linear-gradient(180deg,rgba(31,61,43,.045),rgba(205,235,0,.035));border-radius:16px;padding:13px}.focus-hero b{display:block;font-size:15px;margin-bottom:4px}.focus-hero span{font-size:12px;color:var(--muted);line-height:1.45}.focus-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.focus-card{border:1px solid var(--line-soft);background:var(--surface);border-radius:15px;padding:12px;display:flex;flex-direction:column;gap:8px}.focus-card b{font-size:22px;line-height:1}.focus-card span{font-size:11.5px;color:var(--muted)}.focus-card button,.focus-row button{align-self:flex-start;border:1px solid rgba(31,61,43,.14);background:var(--surface-2);border-radius:999px;padding:6px 10px;font-size:11.5px;font-weight:650;color:var(--txt-2)}.focus-card button.primary,.focus-row button.primary{background:var(--btn-ink);color:var(--btn-lime);border-color:var(--btn-lime-line)}.focus-section{border:1px solid var(--line-soft);background:var(--surface);border-radius:15px;padding:12px}.focus-section h4{margin:0 0 9px;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}.focus-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:center;padding:9px 0;border-top:1px solid var(--line-soft)}.focus-row:first-of-type{border-top:0}.focus-row .fn{font-weight:700;font-size:13px;color:var(--txt);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.focus-row .fm{font-size:11.5px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.focus-row .fa{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}.focus-safe{border:1px dashed rgba(31,61,43,.2);background:rgba(31,61,43,.035);border-radius:13px;padding:10px;font-size:12px;color:var(--txt-2);line-height:1.45}.focus-safe b{color:var(--txt)}.mode-toggle{margin-left:auto;display:inline-flex;gap:4px;background:var(--surface);border:1px solid var(--line-soft);border-radius:999px;padding:3px}.mode-toggle button{border:0;background:transparent;border-radius:999px;padding:5px 9px;font-size:11.5px;font-weight:650;color:var(--muted)}.mode-toggle button.on{background:var(--btn-ink);color:var(--btn-lime)}.mgmt-hero{border:1px solid var(--line-soft);background:linear-gradient(180deg,rgba(31,61,43,.05),rgba(31,61,43,.02));border-radius:16px;padding:13px}.mgmt-hero b{display:block;font-size:15px;margin-bottom:4px}.mgmt-hero span{font-size:12px;color:var(--muted);line-height:1.45}.mgmt-subhead{display:flex;align-items:center;justify-content:space-between;margin-top:2px}.mgmt-subhead b{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}.mgmt-subhead span{font-size:11px;color:var(--muted)}.pipe-compact{border:1px solid var(--line-soft);background:var(--surface);border-radius:13px;padding:4px 12px}.pipe-compact>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:9px 0;font-size:12px}.pipe-compact>summary::-webkit-details-marker{display:none}.pipe-compact .pc-k{font-weight:700;color:var(--txt-2)}.pipe-compact .pc-v{font-weight:700;color:var(--txt);background:var(--surface-2);border:1px solid var(--line-soft);border-radius:999px;padding:1px 9px}.pipe-compact .pc-hint{font-size:10.5px;color:var(--muted);margin-left:auto}.pipe-compact .pc-rows{display:flex;flex-wrap:wrap;gap:6px;padding:2px 0 10px}.pipe-compact .pc-row{font-size:11.5px;color:var(--txt-2);background:var(--surface-2);border:1px solid var(--line-soft);border-radius:8px;padding:3px 8px}.pipe-compact .pc-row b{color:var(--txt);font-weight:700}
.cad-block .pc-v.warn{color:#9A3412;background:rgba(217,72,15,.08);border-color:rgba(217,72,15,.25)}
.cad-block .cad-stale{font-size:10.5px;font-weight:700;color:#9A3412;background:rgba(217,72,15,.08);border:1px solid rgba(217,72,15,.25);border-radius:999px;padding:1px 8px}
.cad-warn{font-size:11.5px;color:#9A3412;background:rgba(217,72,15,.06);border:1px solid rgba(217,72,15,.2);border-radius:10px;padding:8px 10px;margin:4px 0;line-height:1.4}
.cad-chips{display:flex;flex-wrap:wrap;gap:6px;padding:4px 0 8px}
.cad-chip{font-size:11px;color:var(--txt-2);background:var(--surface-2);border:1px solid var(--line-soft);border-radius:999px;padding:2px 9px}
.cad-chip b{color:var(--txt);font-weight:800;margin-right:3px}
.cad-chip.cad-apt{background:rgba(31,61,43,.07);border-color:rgba(31,61,43,.2)}.cad-chip.cad-apt b{color:#1F3D2B}
.cad-chip.cad-wait{background:rgba(180,140,0,.08);border-color:rgba(180,140,0,.22)}
.cad-chip.cad-reply{background:rgba(20,110,160,.08);border-color:rgba(20,110,160,.22)}
.cad-chip.cad-nutri{opacity:.7}
.cad-chip.cad-s-d0{background:rgba(120,60,160,.08);border-color:rgba(120,60,160,.22)}.cad-chip.cad-s-d0 b{color:#6a3c9c}
.cad-chip.cad-s-rec{background:rgba(180,90,0,.08);border-color:rgba(180,90,0,.22)}.cad-chip.cad-s-rec b{color:#9a4f00}
.cad-sanit{padding:0 0 7px;border-bottom:1px dashed var(--line-soft);margin-bottom:6px}
.cad-sanit-h{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:800;margin:2px 0 4px}
.cad-sanit .cad-chips{padding:0}
.cad-sn{font-weight:700;color:var(--txt-2)}
.cad-sn.rev{color:#9a4f00}
.cad-secs{display:flex;flex-direction:column;gap:8px;padding-bottom:6px}
.cad-sec{border:1px solid var(--line-soft);background:var(--surface);border-radius:11px;padding:9px 10px}
.cad-sec h5{margin:0 0 6px;font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);display:flex;align-items:center;gap:6px}
.cad-sec h5 em{margin-left:auto;font-style:normal;font-weight:800;color:var(--txt-2)}
.cad-row{padding:5px 0;border-top:1px solid var(--line-soft)}.cad-row:first-of-type{border-top:0}
.cad-row .cad-c{font-size:12.5px;font-weight:700;color:var(--txt);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cad-row .cad-m{font-size:11px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cad-src{font-weight:700;border-radius:5px;padding:0 4px}
.cad-src.cad-src-ledger{color:#1F3D2B;background:rgba(31,61,43,.10)}
.cad-src.cad-src-hs{color:#146EA0;background:rgba(20,110,160,.10)}
.cad-src.cad-src-none{color:#9a6a00;background:rgba(180,140,0,.12)}
.cad-more{font-size:10.5px;color:var(--muted);padding-top:5px}
.cad-refresh{margin-top:8px;border:1px solid rgba(31,61,43,.14);background:var(--surface-2);border-radius:999px;padding:6px 11px;font-size:11.5px;font-weight:650;color:var(--txt-2)}
.cad-decsum{display:flex;flex-wrap:wrap;align-items:center;gap:6px;font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);padding:2px 0 6px}
.cad-dec-row{display:flex;flex-wrap:wrap;align-items:center;gap:5px;margin-top:5px}
.cad-dec-btns button{font-size:10.5px;font-weight:650;color:var(--txt-2);background:var(--surface-2);border:1px solid var(--line-soft);border-radius:999px;padding:3px 9px;line-height:1.3}
.cad-dec-btns button:active{background:var(--surface)}
.cad-dec{font-size:10.5px;font-weight:700;color:#6a3c9c;background:rgba(120,60,160,.10);border:1px solid rgba(120,60,160,.22);border-radius:999px;padding:2px 8px}
span.cad-chip.cad-dec{color:#6a3c9c}
.cad-dec-clr{font-size:10.5px;font-weight:650;color:var(--muted);background:transparent;border:1px solid var(--line-soft);border-radius:999px;padding:2px 8px}
.cad-aptos{border:1px solid rgba(31,61,43,.18);background:rgba(31,61,43,.04);border-radius:11px;padding:9px 10px;margin:2px 0 8px}
.cad-aptos h5{margin:0 0 6px;font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:#1F3D2B;display:flex;align-items:center;gap:6px}
.cad-aptos h5 em{margin-left:auto;font-style:normal;font-weight:800;color:#1F3D2B}
.cad-aptos-note{font-size:10.5px;color:#9a6a00;padding-top:5px;font-weight:600}
.transcript{margin-top:7px;padding:7px 9px;border-left:2px solid rgba(205,235,0,.35);background:rgba(205,235,0,.06);border-radius:8px;font-size:12.5px;line-height:1.45;color:var(--txt-2)}
.transcript b{display:block;color:var(--accent);font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px}
.transcript.pending{border-left-color:var(--line-strong);background:var(--surface);color:var(--muted)}
.brow.out .btime{color:rgba(255,255,255,.4)}
.composer{flex:0 0 auto;border-top:1px solid var(--line-soft);background:var(--panel-2);padding:10px 16px 12px}
.composer.readonly-mode{padding:8px 12px calc(8px + env(safe-area-inset-bottom));background:var(--panel-2)}
.quick{display:flex;gap:7px;margin-bottom:9px;overflow-x:auto;scrollbar-width:none}
.quick::-webkit-scrollbar{display:none}
.quick button{flex:0 0 auto;font-size:12px;font-weight:500;color:var(--txt-2);background:var(--surface);border:1px solid var(--line-soft);border-radius:99px;padding:5px 11px;transition:.12s}
.quick button:hover{background:var(--surface-2);color:var(--txt)}
.quick button.ai{color:var(--txt-2);border-color:var(--line-soft);background:var(--surface)}
.quick button.ai:hover{color:var(--accent);border-color:rgba(205,235,0,0.28)}
.route-note{margin:0 0 9px;padding:7px 10px;border:1px solid var(--line-soft);background:var(--surface);color:var(--txt-2);border-radius:10px;font-size:11.5px;line-height:1.35}
.route-note[hidden]{display:none}
.cbox{border:1px solid var(--line);border-radius:22px;background:var(--panel);box-shadow:0 1px 3px rgba(0,0,0,.18);transition:.14s}
.cbox:focus-within{border-color:var(--line-strong)}
.cbox.note{border-color:rgba(247,185,85,0.35);background:linear-gradient(180deg,rgba(247,185,85,0.05),transparent)}
.ctabs{display:flex;gap:2px;padding:6px 10px 0}
.ctab{font-size:11.5px;font-weight:600;color:var(--muted);padding:5px 11px;border-radius:8px;transition:.12s;background:none;border:0}
.ctab.on{color:var(--txt);background:var(--surface)}.ctab.on.noteon{color:var(--warning)}
/* CH-020: linha de input estilo WhatsApp — anexar à esquerda, enviar à direita */
.cinput-row{display:flex;align-items:flex-end;gap:4px;padding:3px 6px 3px 5px}
.cbox textarea{flex:1;width:100%;background:none;border:0;outline:0;color:var(--txt);font-size:14px;line-height:1.5;resize:none;padding:9px 6px;min-height:40px;max-height:160px}
.cbox textarea::placeholder{color:var(--muted)}
.send{background:var(--btn-ink);color:var(--btn-lime);border:1px solid var(--btn-lime-line);border-radius:999px;height:38px;padding:0 16px;font-weight:700;font-size:13px;display:flex;align-items:center;gap:7px;flex:0 0 auto;transition:.12s;box-shadow:0 5px 14px var(--btn-ink-shadow)}
.send .send-ic{width:16px;height:16px}
.send:hover{filter:none;transform:translateY(-1px);box-shadow:0 7px 18px var(--btn-ink-shadow)}.send.note{background:#6B5B2A;color:#F6F7F2;border-color:rgba(246,247,242,.35)}
.send:disabled{opacity:.55;cursor:default;filter:none}
.attach-btn{background:none;border:0;color:var(--txt-2);border-radius:50%;width:38px;height:38px;padding:0;flex:0 0 auto;display:grid;place-items:center;transition:.12s}
.attach-btn:hover:not(:disabled){background:var(--surface);color:var(--txt)}.attach-btn svg{width:20px;height:20px}
.attach-btn:disabled{opacity:.5;cursor:default}
.chint{padding:0 16px 9px;text-align:right}
.chint .hint{font-size:10.5px;color:var(--muted)}
.attach-row{display:flex;align-items:center;gap:8px;margin:2px 10px 0;padding:7px 10px;background:var(--surface);border:1px solid var(--line);border-radius:9px;font-size:12.5px}
.attach-row[hidden]{display:none}
.attach-row .attach-ic{flex:0 0 auto}
.attach-row .attach-name{flex:1;min-width:0;color:var(--txt);font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.attach-row .attach-rm{flex:0 0 auto;background:none;border:0;color:var(--muted);font-size:13px;line-height:1;padding:2px 4px;border-radius:6px;transition:.12s}
.attach-row .attach-rm:hover{background:var(--surface-2);color:var(--danger)}
/* context */
.context .scroll{padding:0}
.ctx-id{padding:18px 16px 14px;border-bottom:1px solid var(--line-soft)}
.ctx-id .top{display:flex;align-items:center;gap:11px}
.ctx-id .ava{width:42px;height:42px;border-radius:50%;display:grid;place-items:center;font-weight:700;font-size:15px;color:#0a0a0a;flex:0 0 auto}
.ctx-id .nm{min-width:0}.ctx-id .nm b{display:block;font-size:14.5px;font-weight:650;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ctx-id .nm span{font-size:12px;color:var(--txt-2)}
.score{display:flex;align-items:center;gap:10px;margin-top:14px}
.score .ring{position:relative;width:46px;height:46px;flex:0 0 auto}.score .ring svg{transform:rotate(-90deg)}
.score .ring .val{position:absolute;inset:0;display:grid;place-items:center;font-size:13px;font-weight:700}
.score .sc-meta b{font-size:12.5px;font-weight:600;display:block}.score .sc-meta span{font-size:11px;color:var(--muted)}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:13px}
.tag{font-size:11px;font-weight:500;color:var(--txt-2);background:var(--surface);border:1px solid var(--line);border-radius:7px;padding:3px 8px}
.tag.hot{color:var(--accent);background:var(--accent-soft);border-color:rgba(205,235,0,0.25)}
.section{padding:15px 16px;border-bottom:1px solid var(--line-soft)}
.section h5{font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:var(--muted);margin:0 0 11px;display:flex;align-items:center;gap:7px}
.section h5 .hs{margin-left:auto;font-size:10px;font-weight:600;color:#ff7a59;background:rgba(255,122,89,0.1);border:1px solid rgba(255,122,89,0.25);border-radius:5px;padding:1.5px 6px;letter-spacing:0;text-transform:none}
.section h5 .soon{margin-left:auto;font-size:10px;font-weight:600;color:var(--muted);background:var(--surface);border:1px solid var(--line-soft);border-radius:5px;padding:1.5px 6px;letter-spacing:0;text-transform:none}
.kv{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:5px 0;font-size:12.5px}
.kv .k{color:var(--muted)}.kv .v{color:var(--txt);font-weight:500;text-align:right;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.kv .v.ph{color:var(--muted);font-weight:400;font-style:italic}
.hs-links{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 10px}
.hs-link{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line-soft);background:var(--surface);border-radius:10px;padding:7px 10px;font-size:12px;font-weight:650;color:var(--txt-2);text-decoration:none;transition:.12s}
.hs-link:hover{border-color:var(--line);background:var(--surface-2);color:var(--txt)}
.hs-link svg{width:14px;height:14px}
.next{border:1px solid var(--line-soft);background:var(--surface);border-radius:var(--radius);padding:13px}
.next .nh{display:flex;align-items:center;gap:8px;font-size:11px;font-weight:600;text-transform:uppercase;color:var(--accent);margin-bottom:8px}
.next p{margin:0 0 11px;font-size:13px;line-height:1.5;color:var(--txt)}.next .nbtns{display:flex;gap:7px}.next .nbtns .btn{flex:1;justify-content:center}
.ctx-id.compact{padding:13px 16px 10px}.ctx-id.compact .tags{margin-top:9px}.ops{background:linear-gradient(180deg,rgba(31,61,43,.04),transparent)}.ops-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:10px}.ops-card{border:1px solid var(--line-soft);background:var(--surface);border-radius:12px;padding:9px 10px;display:flex;flex-direction:column;gap:2px}.ops-card b{font-size:17px;color:var(--txt);line-height:1}.ops-card span{font-size:10.5px;color:var(--muted);line-height:1.25}.ops-card.alert b{color:#D9480F}.ops-card.goal b{color:#1F3D2B}.goalbar{height:7px;background:var(--line-soft);border-radius:999px;overflow:hidden;margin:8px 0}.goalbar i{display:block;height:100%;background:linear-gradient(90deg,#1F3D2B,#CDEB00);border-radius:999px}.goalnote{font-size:11.5px;color:var(--txt-2);line-height:1.4;margin-bottom:9px}.goalnote b{color:var(--txt)}.goalnote small{display:block;color:var(--muted);margin-top:2px}.ops details{border-top:1px solid var(--line-soft);padding-top:8px;margin-top:8px}.ops summary{cursor:pointer;font-size:12px;font-weight:650;color:var(--txt);margin-bottom:6px}.task-line{display:block;text-decoration:none;color:var(--txt);border:1px solid var(--line-soft);background:#fff;border-radius:10px;padding:8px 9px;margin:6px 0}.task-line:hover{border-color:rgba(31,61,43,.35);box-shadow:0 5px 18px rgba(20,30,20,.06)}.task-line b{display:block;font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.task-line span{display:block;font-size:11px;color:var(--muted);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.mini-empty{font-size:12px;color:var(--muted);background:var(--surface);border:1px dashed var(--line);border-radius:10px;padding:9px}
.add-note{width:100%;text-align:left;font-size:12px;color:var(--muted);background:var(--surface);border:1px dashed var(--line);border-radius:10px;padding:9px 11px;display:flex;align-items:center;gap:8px;transition:.12s}
.add-note:hover{color:var(--txt-2);border-color:var(--line-strong)}
.health{display:grid;grid-template-columns:1fr 1fr;gap:9px}
.hcell{border:1px solid var(--line-soft);background:var(--surface);border-radius:10px;padding:10px 11px}
.hcell .hl{font-size:10.5px;color:var(--muted);margin-bottom:5px}
.hcell .hv{font-size:16px;font-weight:700;font-variant-numeric:tabular-nums}.hcell .hv small{font-size:11px;font-weight:500;color:var(--muted)}
.placeholder{font-size:12px;color:var(--muted);line-height:1.5}
/* CH-016: chip/conexão rebaixado ao rodapé do contexto comercial */
.ctx-channel{display:flex;align-items:center;gap:8px;padding:11px 16px 18px;font-size:11.5px;color:var(--muted)}
.ctx-channel .k{color:var(--muted)}.ctx-channel .v{color:var(--txt-2);font-weight:500}
.ctx-channel .ctx-channel-link{margin-left:auto;font-size:11px;color:var(--txt-2);background:none;border:1px solid var(--line-soft);border-radius:7px;padding:3px 9px;transition:.12s}
.ctx-channel .ctx-channel-link:hover{background:var(--surface);color:var(--txt);border-color:var(--line)}
/* CH-004 — resumo de conexões na sidebar + modal Conexões */
.chips-summary{display:flex;gap:12px;padding:2px 2px 10px;flex-wrap:wrap}
.chips-summary .cs{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--txt-2);font-variant-numeric:tabular-nums}
/* CH-015: Conexões é suporte secundário — botão discreto no rodapé da sidebar */
.conn-foot{margin-top:auto;padding:10px 12px 12px;border-top:1px solid var(--line-soft)}
.conn-btn{width:100%;border:1px solid var(--line-soft);background:none;color:var(--txt-2);font-size:12px;font-weight:500;border-radius:9px;padding:7px 10px;display:flex;align-items:center;gap:8px;transition:.12s}
.conn-btn:hover{background:var(--surface);color:var(--txt);border-color:var(--line)}
.conn-btn .cl-label{flex:1;text-align:left;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.conn-btn .st{flex:0 0 auto}
.conn-btn.alert{border-color:rgba(247,185,85,.4);color:var(--warning);background:var(--warning-soft)}
.conn-badge{font-size:10.5px;font-weight:700;background:var(--warning);color:#0a0a0a;border-radius:99px;padding:1px 7px}
.modal{position:fixed;inset:0;z-index:60;display:flex;align-items:center;justify-content:center}
.modal[hidden]{display:none}
.modal-scrim{position:absolute;inset:0;background:rgba(0,0,0,.6)}
.modal-card{position:relative;width:580px;max-width:94vw;max-height:88vh;display:flex;flex-direction:column;background:var(--panel);border:1px solid var(--line);border-radius:18px;box-shadow:0 30px 80px -30px rgba(0,0,0,.8);overflow:hidden}
.modal-head{display:flex;align-items:center;gap:10px;padding:16px 18px;border-bottom:1px solid var(--line-soft)}
.modal-head b{font-size:15px;font-weight:650}.modal-head .modal-sub{font-size:12px;color:var(--muted)}.modal-head .spacer{flex:1}
.modal-body{padding:14px 18px;overflow-y:auto}
.modal-foot{padding:11px 18px;border-top:1px solid var(--line-soft);font-size:11.5px;color:var(--muted)}
.conn-group{margin-bottom:18px}
.cg-head{display:flex;align-items:center;gap:9px;margin-bottom:9px}
.cg-head b{font-size:13px;font-weight:650}.cg-head .cg-n{font-size:11px;color:var(--muted);background:var(--surface);border:1px solid var(--line-soft);border-radius:99px;padding:1px 8px}
.cg-av{width:24px;height:24px;border-radius:50%;display:grid;place-items:center;font-size:10px;font-weight:700;color:#0a0a0a;flex:0 0 auto}
.conn-card{border:1px solid var(--line);background:var(--surface);border-radius:14px;padding:13px;margin-bottom:9px}
.cc-head{display:flex;align-items:center;gap:9px;margin-bottom:11px}
.cc-head .st{flex:0 0 auto}
.cc-head .cc-name{font-weight:650;font-size:14px}
.cc-head .cc-status{font-size:11.5px;color:var(--txt-2)}
.cc-head .cc-port{margin-left:auto;font-size:10px;color:var(--muted);background:var(--bg);border:1px solid var(--line-soft);border-radius:5px;padding:1.5px 6px}
.cc-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:11px}
.cc-metrics>div{background:var(--bg);border:1px solid var(--line-soft);border-radius:9px;padding:7px 8px}
.cc-metrics .m-l{display:block;font-size:10px;color:var(--muted);margin-bottom:3px}
.cc-metrics .m-v{font-size:14px;font-weight:700;font-variant-numeric:tabular-nums}.cc-metrics .m-v small{font-size:10px;font-weight:500;color:var(--muted)}
.risk-low{color:var(--success)}.risk-med{color:var(--warning)}.risk-high{color:var(--danger)}
.cc-foot{display:flex;align-items:center;gap:9px}
.cc-foot .rec{font-size:11.5px;font-weight:600;border-radius:7px;padding:4px 9px}
.rec-ok{background:var(--success-soft);color:var(--success)}.rec-warn{background:var(--warning-soft);color:var(--warning)}.rec-bad{background:var(--danger-soft);color:var(--danger)}
.cc-foot .spacer{flex:1}.cc-foot .none{font-size:11.5px;color:var(--muted)}
.login{max-width:460px;margin:12vh auto;background:var(--panel);padding:24px;border:1px solid var(--line);border-radius:20px}
/* responsive */
.scrim{display:none}
@media (max-width:1320px){
  :root{--sidebar-w:96px;--context-w:0px}
  .app{grid-template-columns:var(--sidebar-w) var(--list-w) minmax(0,1fr)}
  .brand .name,.nav-label,.q .qlabel,.q .count,.chips,.conn-btn .cl-label,.conn-badge,.me .nm{display:none}
  .brand{justify-content:center;padding:16px 0}.q{justify-content:center;padding:10px}.me{justify-content:center}
  .conn-foot{padding:10px 8px}.conn-btn{justify-content:center;padding:8px}
  .context{position:fixed;top:0;right:0;height:100dvh;width:340px;max-width:88vw;z-index:40;transform:translateX(100%);transition:transform .28s;box-shadow:-20px 0 60px -20px rgba(0,0,0,.7)}
  .app.ctx-open .context{transform:translateX(0)}
  .scrim{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:35}.app.ctx-open .scrim{display:block}
}
@media (max-width:820px){
  .app{grid-template-columns:1fr}.sidebar{display:none}.list{display:flex}
  .conversation{position:fixed;inset:0;z-index:30;transform:translateX(100%);transition:transform .28s}
  .app.conv-open .conversation{transform:translateX(0)}.back-btn{display:grid}.timeline{padding:18px 16px}.brow{max-width:86%}
}
/* ===== CH-019: tema claro/calm (override de variáveis em [data-theme=light]) ===== */
:root[data-theme="light"]{
  --bg:#F4F5F2;--panel:#FFFFFF;--panel-2:#F8F9F6;
  --surface:rgba(20,28,20,0.035);--surface-2:rgba(20,28,20,0.06);--surface-hi:rgba(20,28,20,0.09);
  --line:rgba(20,28,20,0.12);--line-soft:rgba(20,28,20,0.07);--line-strong:rgba(20,28,20,0.2);
  --txt:#1B211C;--txt-2:#4C554E;--muted:#8B938C;
  --accent:#566912;--accent-dim:rgba(86,105,18,0.14);--accent-soft:rgba(86,105,18,0.08);
  --success:#0E9F6E;--success-soft:rgba(14,159,110,0.13);
  --warning:#B9770B;--warning-soft:rgba(185,119,11,0.14);
  --danger:#D64545;--danger-soft:rgba(214,69,69,0.12);
  --info:#3F62C8;--info-soft:rgba(63,98,200,0.12);
  --chat-bg:#ECE5DC;--chat-dot:rgba(20,28,20,0.025);
  --bubble-out:#D9FDD3;--bubble-in:#FFFFFF;
}
[data-theme="light"] body{background:var(--bg)}
[data-theme="light"] .sidebar{background:linear-gradient(180deg,#FBFCFA,#EEF0EC);border-right-color:rgba(20,28,20,0.08)}
[data-theme="light"] .brand .logo{background:transparent!important;border-color:transparent!important;box-shadow:none!important}
[data-theme="light"] .brand .name,[data-theme="light"] .me .nm b{color:var(--txt)}
[data-theme="light"] .q{color:#5D665F}
[data-theme="light"] .q:hover,[data-theme="light"] .q.active{background:rgba(20,28,20,0.055);color:#182018}
[data-theme="light"] .conn-foot,[data-theme="light"] .me{border-top-color:rgba(20,28,20,0.08)}
[data-theme="light"] .list{background:var(--panel)}
[data-theme="light"] .conversation{background:var(--chat-bg)}
[data-theme="light"] .brow.out .btime{color:rgba(20,28,20,0.42)}
[data-theme="light"] .brow.in .bubble{box-shadow:0 1px 1px rgba(20,28,20,.08)}
[data-theme="light"] .day-sep span{box-shadow:0 1px 1px rgba(20,28,20,.06)}
[data-theme="light"] .context{background:linear-gradient(180deg,#FCFCFB,#F3F4F0)}
[data-theme="light"] ::-webkit-scrollbar-thumb{background:rgba(20,28,20,0.14)}
[data-theme="light"] ::-webkit-scrollbar-thumb:hover{background:rgba(20,28,20,0.24)}
[data-theme="light"] .btn.primary,[data-theme="light"] .send{color:var(--btn-lime)}
[data-theme="light"] .brow.out .bubble{border-color:rgba(20,28,20,0.05)}
[data-theme="light"] .brow.lead .bubble{border-color:rgba(86,105,18,0.4)}
[data-theme="light"] .b-diag{color:var(--info)}
[data-theme="light"] .b-meet{background:rgba(108,70,193,0.12);color:#6B46C1}
[data-theme="light"] .card .preview .from.auto,[data-theme="light"] .bmeta .autobadge,[data-theme="light"] .event-card .eic{color:var(--info)}
[data-theme="light"] .pdf .pic span{color:#c0392b}

/* Playbooks dentro da conversa */
.playbook-panel{padding:10px 12px 12px;display:flex;flex-direction:column;gap:10px}.playbook-panel[hidden]{display:none}
.pb-intro{border:1px solid var(--line-soft);background:var(--accent-soft);border-radius:11px;padding:9px 11px;font-size:11.5px;line-height:1.4;color:var(--txt-2)}.pb-intro b{color:var(--txt)}.route-pill{display:inline-flex;align-items:center;gap:5px;border:1px solid rgba(31,61,43,.18);background:rgba(31,61,43,.06);border-radius:999px;padding:2px 8px;font-size:10.5px;font-weight:750;color:#1F3D2B;margin-left:6px}.route-pill.warn{background:rgba(180,140,0,.08);border-color:rgba(180,140,0,.24);color:#8a6500}.route-pill.hot{background:rgba(20,110,160,.08);border-color:rgba(20,110,160,.22);color:#146e9f}.route-pill.off{background:rgba(255,107,107,.09);border-color:rgba(255,107,107,.2);color:#a33}
.pb-group{display:flex;flex-direction:column;gap:7px}.pb-group-h{font-size:10.5px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:800;padding-left:2px}
.pb-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.pb-card{border:1px solid var(--line-soft);background:var(--surface);border-radius:13px;padding:10px;text-align:left;display:flex;flex-direction:column;gap:5px}.pb-card b{font-size:12.5px}.pb-card span{font-size:11.5px;color:var(--muted);line-height:1.35}.pb-card button{align-self:flex-start;margin-top:4px;border:1px solid var(--btn-lime-line);background:var(--btn-ink);color:var(--btn-lime);border-radius:999px;padding:6px 10px;font-size:11px;font-weight:750}.pb-form{border:1px solid var(--line-soft);background:var(--panel);border-radius:13px;padding:10px;display:grid;gap:8px}.pb-form>b{font-size:12.5px;color:var(--txt)}.pb-form label{display:grid;gap:4px;font-size:11px;color:var(--muted);font-weight:700}.pb-form input,.pb-form select,.pb-form textarea{border:1px solid var(--line);background:var(--surface);border-radius:9px;padding:8px 9px;color:var(--txt);font-size:12.5px;outline:0}.pb-form textarea{resize:vertical;line-height:1.45}.pb-hint{font-size:10.5px;color:var(--muted);line-height:1.35}.pb-actions{display:flex;gap:8px;flex-wrap:wrap}.pb-actions button{border:1px solid var(--line);border-radius:999px;padding:7px 11px;font-weight:750;font-size:11.5px;background:var(--surface);color:var(--txt-2)}.pb-actions button.primary{background:var(--btn-ink);color:var(--btn-lime);border-color:var(--btn-lime-line)}.pb-actions button.hs{border-color:var(--line);color:var(--info)}
@media(max-width:820px){.pb-grid{grid-template-columns:1fr}.playbook-panel{max-height:42dvh;overflow:auto}}

/* ===== CH-026: seleção + ações em massa ===== */
.card-check{position:absolute;left:11px;top:14px;width:16px;height:16px;margin:0;cursor:pointer;accent-color:var(--accent);opacity:.5;transition:.12s;z-index:2}
.card:hover .card-check,.card-check:hover,.card-check:checked{opacity:1}
.card.selected{background:var(--accent-soft);border-color:rgba(205,235,0,.32)}
.card.selected:hover{background:var(--accent-dim)}
.bulkbar{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:50;display:flex;align-items:center;gap:8px;padding:7px 8px 7px 12px;border:1px solid rgba(20,28,20,.12);background:rgba(255,255,255,.92);box-shadow:0 16px 45px rgba(20,28,20,.16);border-radius:999px;backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px)}
.bulkbar[hidden]{display:none}
.bulkbar .bb-n{font-size:12px;font-weight:750;color:var(--txt);white-space:nowrap;padding-right:4px}.bulkbar .bb-n span{color:var(--accent)}
.bulkbar .spacer{display:none}.bulkbar .bulk-extra{display:none}.bulkbar .bulk-open{border:1px solid var(--btn-lime-line);background:var(--btn-ink);color:var(--btn-lime);border-radius:999px;padding:7px 12px;font-size:12px;font-weight:800}.bulkbar .bulk-clear{border:0;background:transparent;color:var(--muted);border-radius:999px;padding:7px 9px;font-size:12px;font-weight:700}.bulkbar .bulk-clear:hover{background:var(--surface);color:var(--danger)}
.bb-btn{font-size:11.5px;font-weight:600;border:1px solid var(--line);background:var(--surface);color:var(--txt-2);border-radius:8px;padding:5px 10px;display:inline-flex;align-items:center;gap:5px;transition:.12s;white-space:nowrap}
.bb-btn:hover:not(:disabled){background:var(--surface-2);color:var(--txt);border-color:var(--line-strong)}.bb-btn:disabled{opacity:.45;cursor:not-allowed}.bb-btn.danger{color:var(--danger)}
[data-theme="dark"] .context,[data-theme="dark"] .modal-card,[data-theme="dark"] .wizard-steps,[data-theme="dark"] .wiz-foot{background:var(--panel-2)!important}
[data-theme="dark"] .bulkbar{background:rgba(11,20,15,.92);border-color:var(--line);box-shadow:0 18px 46px rgba(0,0,0,.44)}
[data-theme="dark"] .cad-board,[data-theme="dark"] .focus-hero,[data-theme="dark"] .mgmt-hero{background:linear-gradient(180deg,rgba(205,235,0,.07),rgba(7,16,11,.42));border-color:var(--line-soft)}
[data-theme="dark"] .mgmt-card,[data-theme="dark"] .mgmt-section,[data-theme="dark"] .focus-card,[data-theme="dark"] .focus-section,[data-theme="dark"] .dispatch-board,[data-theme="dark"] .dispatch-rank .r,[data-theme="dark"] .dispatch-chip,[data-theme="dark"] .pipe-tr,[data-theme="dark"] .wiz-kpi,[data-theme="dark"] .wiz-box,[data-theme="dark"] .wiz-action,[data-theme="dark"] .pb-form,[data-theme="dark"] .event-card,[data-theme="dark"] .pdf{background:var(--surface)!important;border-color:var(--line-soft)!important;color:var(--txt)}
[data-theme="dark"] .card.readonly{background:linear-gradient(180deg,rgba(205,235,0,.07),rgba(16,25,19,.72));border-color:var(--line-soft)}
[data-theme="dark"] .readonly-banner,[data-theme="dark"] .readonly-help,[data-theme="dark"] .inst-pill,[data-theme="dark"] .route-note,[data-theme="dark"] .focus-safe{background:var(--surface)!important;border-color:var(--line-soft)!important;color:var(--txt-2)!important}
[data-theme="dark"] .cad-chip.cad-apt b,[data-theme="dark"] .cad-aptos h5,[data-theme="dark"] .cad-aptos h5 em,[data-theme="dark"] .route-pill{color:var(--accent)!important}
[data-theme="dark"] .modal-scrim{background:rgba(0,0,0,.62)}
[data-theme="dark"] .pipe-act-upcoming{border-color:rgba(205,235,0,.26);background:rgba(205,235,0,.07)}
.wizard-modal .modal-card{width:860px;max-width:94vw}.wizard-steps{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:12px 16px;border-bottom:1px solid var(--line-soft);background:var(--panel-2)}.wiz-step{border:1px solid var(--line-soft);background:var(--surface);border-radius:12px;padding:9px 10px;color:var(--muted);font-size:11.5px;font-weight:750}.wiz-step b{display:block;color:var(--txt);font-size:12px}.wiz-step.on{background:rgba(205,235,0,.12);border-color:rgba(205,235,0,.35);color:var(--accent)}.wiz-panel{display:none}.wiz-panel.on{display:block}.wiz-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:12px}.wiz-kpi{border:1px solid var(--line-soft);background:var(--surface);border-radius:14px;padding:11px}.wiz-kpi b{display:block;font-size:24px;line-height:1}.wiz-kpi span{font-size:11px;color:var(--muted)}.wiz-list{display:grid;grid-template-columns:1fr 1fr;gap:12px}.wiz-box{border:1px solid var(--line-soft);background:var(--surface);border-radius:14px;padding:10px;min-height:220px}.wiz-box h4{margin:0 0 8px;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}.wiz-row{padding:7px 0;border-top:1px solid var(--line-soft)}.wiz-row:first-of-type{border-top:0}.wiz-row b{font-size:12.5px}.wiz-row span{display:block;font-size:11px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.wiz-actions{display:flex;gap:9px;flex-wrap:wrap}.wiz-action{flex:1;min-width:170px;text-align:left;border:1px solid var(--line-soft);background:var(--surface);border-radius:14px;padding:12px}.wiz-action b{display:block}.wiz-action span{display:block;margin-top:3px;font-size:11.5px;color:var(--muted);line-height:1.35}.wiz-foot{display:flex;align-items:center;gap:8px;padding:12px 16px;border-top:1px solid var(--line-soft);background:var(--panel-2)}.wiz-foot .spacer{flex:1}.wiz-foot button{border:1px solid var(--line);background:var(--surface);border-radius:999px;padding:8px 13px;font-size:12px;font-weight:800}.wiz-foot button.primary{background:var(--btn-ink);border-color:var(--btn-lime-line);color:var(--btn-lime)}
@media(max-width:760px){.bulkbar{left:10px;right:10px;bottom:76px;transform:none;justify-content:space-between}.wizard-steps,.wiz-kpis,.wiz-list{grid-template-columns:1fr}.wizard-modal .modal-card{max-height:92dvh}}

/* Mobile bottom tab bar — iOS/liquid glass inspired, Zydon tokens */
.mobile-tabbar{display:none}
@media (max-width:820px){
  .app{grid-template-columns:1fr; padding-bottom:76px; height:100dvh}
  .sidebar{display:none!important}
  .list{display:flex; min-height:0; padding-bottom:0}
  .conversation{position:fixed;left:0;right:0;top:0;bottom:72px;z-index:30;transform:translateX(100%);transition:transform .28s cubic-bezier(.2,.9,.2,1)}
  .app.conv-open .conversation{transform:translateX(0)}
  .context{bottom:72px;height:auto!important}
  .mobile-tabbar{
    position:fixed;left:max(10px,env(safe-area-inset-left));right:max(10px,env(safe-area-inset-right));
    bottom:calc(6px + env(safe-area-inset-bottom));height:60px;display:grid;grid-template-columns:repeat(3,1fr);gap:4px;
    padding:5px;border:1px solid rgba(255,255,255,.56);border-radius:22px;
    background:linear-gradient(180deg,rgba(255,255,255,.82),rgba(246,247,242,.68));
    box-shadow:0 18px 50px rgba(20,28,20,.18),0 6px 18px rgba(20,28,20,.10),inset 0 1px 0 rgba(255,255,255,.92);
    z-index:60;backdrop-filter:saturate(180%) blur(24px);-webkit-backdrop-filter:saturate(180%) blur(24px);
  }
  .mobile-tabbar::before{content:"";position:absolute;inset:3px;border-radius:19px;pointer-events:none;background:radial-gradient(circle at 50% 0%,rgba(255,255,255,.72),transparent 55%)}
  [data-theme="dark"] .mobile-tabbar{border-color:rgba(255,255,255,.10);background:linear-gradient(180deg,rgba(21,27,23,.78),rgba(7,16,11,.68));box-shadow:0 18px 54px rgba(0,0,0,.42),0 6px 18px rgba(0,0,0,.32),inset 0 1px 0 rgba(255,255,255,.08)}
  [data-theme="dark"] .mobile-tabbar::before{background:radial-gradient(circle at 50% 0%,rgba(255,255,255,.12),transparent 58%)}
  .mobile-tabbar button{position:relative;z-index:1;border:0;background:transparent;color:var(--muted);border-radius:18px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;font-size:10px;font-weight:760;letter-spacing:-.12px;line-height:1;min-width:0;transition:transform .16s cubic-bezier(.2,.9,.2,1),color .16s,background .16s,box-shadow .16s}
  .mobile-tabbar button:active{transform:scale(.96)}
  .mobile-tabbar button .ico{width:24px;height:24px;border-radius:999px;display:grid;place-items:center;line-height:1;color:currentColor;transition:.18s cubic-bezier(.2,.9,.2,1)}
  .mobile-tabbar button .ico svg{width:18px;height:18px;display:block;stroke:currentColor;stroke-width:2;fill:none;stroke-linecap:round;stroke-linejoin:round}
  .mobile-tabbar button .lbl{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%;opacity:.82}
  .mobile-tabbar button.on{background:rgba(11,15,12,.055);color:var(--txt);box-shadow:inset 0 0 0 1px rgba(20,28,20,.05)}
  .mobile-tabbar button.on .ico{background:var(--btn-ink);color:var(--btn-lime);box-shadow:0 8px 20px rgba(11,15,12,.26),0 0 0 1px var(--btn-lime-line),inset 0 1px 0 rgba(255,255,255,.13)}
  [data-theme="dark"] .mobile-tabbar button.on{background:rgba(255,255,255,.055);color:#F6F7F2;box-shadow:inset 0 0 0 1px rgba(255,255,255,.06)}
  [data-theme="dark"] .mobile-tabbar button.on .ico{box-shadow:0 9px 24px rgba(0,0,0,.38),0 0 0 1px var(--btn-lime-line),inset 0 1px 0 rgba(255,255,255,.14)}
  .back-btn{display:grid}.timeline{padding:18px 16px}.brow{max-width:86%}
  .composer{padding:7px 9px calc(74px + env(safe-area-inset-bottom))}.composer.readonly-mode{padding:6px 8px calc(8px + env(safe-area-inset-bottom))}.bulkbar{padding-bottom:12px}
  .conv-head{min-height:64px;height:auto;flex:0 0 auto;padding:8px 10px}.conv-head .ttl b{font-size:14px}.conv-head .ttl .sub{gap:5px;font-size:11.5px;line-height:1.25}.head-actions{gap:4px}.head-actions .icon-btn{width:30px;height:30px}.timeline{padding:14px 12px 10px}.brow{max-width:92%}.event{max-width:94%}.ctabs{overflow-x:auto;padding:6px 9px 0}.cbox{border-radius:22px}.cinput-row{align-items:flex-end;gap:5px;padding:4px 6px}.send{height:40px;min-width:40px;padding:0 11px}.send span{display:none}.attach-btn{width:40px;height:40px}.quick{margin-bottom:6px}.quick button{padding:4px 9px;font-size:11.5px}.cbox textarea{min-height:52px;padding:8px 7px;font-size:14.5px;line-height:1.42;max-height:150px}.chint{padding:1px 13px 7px}.readonly-help{margin:0 0 2px}.inst-map{gap:4px}.inst-pill{font-size:10.5px;padding:4px 7px}
}


/* Admin WhatsApp/equipe — SDRs separados de comunicadores, sem prompts nativos */
#connModal .modal-card{width:min(1180px,calc(100vw - 44px));max-width:none;max-height:92vh;border-radius:22px}
#connModal .modal-body{padding:16px 18px 18px;overflow:auto}
#connModal .modal-head{align-items:flex-start;gap:12px;flex-wrap:wrap}
#connModal .modal-head b{font-size:17px}.modal-head .modal-sub{line-height:1.35}
.team-tabs{display:flex;gap:8px;margin:0 0 14px;position:sticky;top:-16px;background:var(--panel);z-index:2;padding:0 0 10px}.team-tabs button{border:1px solid var(--line-soft);background:var(--surface);border-radius:999px;padding:9px 14px;font-size:12px;font-weight:850;color:var(--muted);cursor:pointer;white-space:nowrap}.team-tabs button.on{background:var(--btn-ink);color:var(--btn-lime);border-color:var(--btn-lime-line);box-shadow:0 8px 22px rgba(11,15,12,.14)}
.team-layout{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:16px;align-items:start}.team-section{min-width:0;border:1px solid var(--line-soft);background:var(--surface);border-radius:18px;padding:14px}.team-section h3{margin:0 0 4px;font-size:14px}.team-section p{margin:0 0 12px;color:var(--muted);font-size:12px;line-height:1.45}.team-list{display:grid;gap:10px}.team-card{min-width:0;border:1px solid var(--line-soft);background:var(--panel);border-radius:16px;padding:12px;overflow:hidden}.team-card.top-sdr{border-left:4px solid #7AA2FF}.team-card.top-com{border-left:4px solid var(--accent)}.team-card .cc-head{flex-wrap:wrap;margin-bottom:8px}.team-card .cc-name{min-width:0;overflow:hidden;text-overflow:ellipsis}.team-card .cc-port{margin-left:0!important}.team-card .meta{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin-top:7px}.pill{display:inline-flex;align-items:center;gap:5px;max-width:100%;border:1px solid var(--line-soft);border-radius:999px;padding:4px 8px;font-size:11px;color:var(--muted);background:var(--surface);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pill.good{color:#0f8f5f;border-color:rgba(32,201,151,.25);background:rgba(32,201,151,.08)}.pill.warn{color:#bd7500;border-color:rgba(247,185,85,.35);background:rgba(247,185,85,.09)}.pill.bad{color:#c23b3b;border-color:rgba(255,107,107,.25);background:rgba(255,107,107,.08)}
.team-card .cc-metrics{grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.team-card .cc-metrics>div{min-width:0}.team-actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:10px}.team-actions button,.team-actions a,.team-form button{min-height:34px;border:1px solid var(--line-soft);background:var(--surface);border-radius:999px;padding:7px 10px;font-size:12px;font-weight:850;color:var(--txt);text-decoration:none;cursor:pointer;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.team-actions .primary,.team-form .primary{background:var(--btn-ink);color:var(--btn-lime);border-color:var(--btn-lime-line)}.team-actions .danger{color:#c23b3b}.team-form{display:grid;gap:10px}.team-form label{display:grid;gap:5px;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:850}.team-form input,.team-form select{min-width:0;border:1px solid var(--line-soft);background:var(--panel);color:var(--txt);border-radius:12px;padding:10px;font-size:13px;outline:none}.form-row{display:grid;grid-template-columns:1fr 1fr;gap:8px}.team-toast{margin:0 0 10px;padding:9px 11px;border-radius:12px;background:rgba(205,235,0,.12);border:1px solid rgba(205,235,0,.28);font-size:12px;color:var(--txt)}.team-empty{padding:16px;border:1px dashed var(--line);border-radius:14px;color:var(--muted);font-size:12px}.confirm-inline{background:rgba(255,107,107,.10)!important;color:#c23b3b!important;border-color:rgba(255,107,107,.35)!important}
@media(max-width:980px){#connModal .modal-card{width:calc(100vw - 20px);max-height:94vh}.team-layout{grid-template-columns:1fr}.form-row{grid-template-columns:1fr}.team-actions{grid-template-columns:1fr 1fr}}
@media(max-width:560px){.team-actions{grid-template-columns:1fr}.team-card .cc-metrics{grid-template-columns:1fr}.team-tabs{overflow-x:auto}}


</style></head><body><div id="root"></div>
<script>
const qs=new URLSearchParams(location.search), user=qs.get('u')||'', token=qs.get('t')||'', deepConv=qs.get('conv')||'';
const auth=`u=${encodeURIComponent(user)}&t=${encodeURIComponent(token)}`;
let deepConvOpened=false;
let convs=[], active=null, msgs=[], me=null, portMeta={};
let queue='todos', sortMode='recent', mode='reply';
let hubspotFilter=false; // WhatsApp mode: mostra todas as conversas reais do WhatsApp
let managerOverview=null, managerOverviewLoading=false;
let pipelineFocus=null, pipelineFocusLoading=false;
let dispatchStats=null, dispatchStatsLoading=false, dispatchSelectedChip='', dispatchSelectedDay='';
let pipeCallFilter='all', pipeWhatsFilter='all', pipeBucketFilter='all', pipeSampleBucket='1';
let cadenciaPreview=null, cadenciaLoading=false;
// CH-026/CH-010: seleção em massa (ids). O estado de triagem (status/nota) é
// persistido no backend via /api/state e chega em cada conversa (localStatus,
// localNote, localUpdatedAt). Mutamos a conversa em memória de forma otimista e
// reconciliamos no próximo loadAll().
let selected=new Set();
let filterOpen=false, filterOwner='', filterStatus='', filterChip='';
// CH-027: viewMode precisa ser declarado explicitamente. Sem isto, drawCards()
// (chamado em loadAll antes de qualquer setViewMode) lê uma variável inexistente
// e o Safari mobile lança "Can't find variable: viewMode", caindo na tela de
// "Sessão expirada / acesso negado".
let viewMode='conversas';
// CH-RT: polling rápido só da inbox. Cargas pesadas (chips/gestão/cadência)
// ficam desacopladas para o mobile mostrar diagnóstico novo em segundos sem F5.
let loadAllInFlight=false, lastHeavyLoad=0;
// CH-RT/UX: feedback "ao vivo" da inbox + destaque do card que chegou no topo.
let lastInboxUpdatedAt=0, newTopConvId='', newTopTimer=null;

const QUEUES=[
  {key:'responder', label:'Responder agora', hot:true},
  {key:'novos', label:'Novos leads'},
  {key:'negocios', label:'Meus negócios'},
  {key:'institucional', label:'Disparos institucionais', hot:true},
  {key:'diagnostico', label:'Diagnóstico enviado'},
  {key:'primeiro', label:'1º contato SDR'},
  {key:'reunioes', label:'Reuniões / tarefas'},
  {key:'audios', label:'Áudios pendentes', hot:true},
  {key:'sem_resposta', label:'Sem resposta'},
  {key:'todos', label:'Todas as conversas'},
];
const PALETTE=['#CDEB00','#7AA2FF','#F7B955','#20C997','#FF6B6B','#c2a4ff','#ff7a59','#5ad1e0'];

function esc(s){return (s??'').toString().replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
function normText(s){return (s??'').toString().normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim()}
function digitsOnly(s){return (s??'').toString().replace(/\D/g,'')}
function phoneVariants(raw){
  const set=new Set(); let d=digitsOnly(raw); if(!d) return set;
  const add=x=>{x=digitsOnly(x); if(x){set.add(x); if(x.startsWith('55')) set.add(x.slice(2)); else if(x.length>=10) set.add('55'+x);} };
  add(d);
  const br=d.startsWith('55')?d.slice(2):d;
  add(br);
  if(br.length===11 && br[2]==='9') add(br.slice(0,2)+br.slice(3));
  if(br.length===10) add(br.slice(0,2)+'9'+br.slice(2));
  return set;
}
function searchIndex(c){
  const parts=[c.title,c.subtitle,c.displayPhone,c.chat,c.realJid,c.email,c.hubspotEmail,c.empresa,c.company,c.dealName,c.dealOwnerLabel,c.sdrLabel,c.portLabel,c.senderLabel,c.institutionalDispatchLabel,c.sharedVisibilityReason,c.audioTranscriptText,c.aiSummary,phoneText(c)];
  if(c.last) parts.push(c.last.text,c.last.transcript,c.last.mediaName,c.last.sender);
  const txt=normText(parts.filter(Boolean).join(' '));
  const nums=[...phoneVariants(parts.join(' '))].join(' ');
  return `${txt} ${nums}`;
}
function matchesSearch(c,raw){
  const q=normText(raw); if(!q) return true;
  const idx=searchIndex(c);
  const qNums=[...phoneVariants(q)];
  if(qNums.length && qNums.some(n=>idx.includes(n))) return true;
  return q.split(/\s+/).filter(Boolean).every(tok=>idx.includes(tok));
}
function initials(s){s=(s||'').trim(); if(!s) return '?'; const p=s.split(/\s+/); return ((p[0][0]||'')+(p[1]?p[1][0]:'')).toUpperCase()}
function colorFor(s){let h=0; for(const c of (s||'')) h=(h*31+c.charCodeAt(0))>>>0; return PALETTE[h%PALETTE.length]}
async function api(path, opts={}){
  const timeoutMs=opts.timeoutMs||9000;
  const ctrl=new AbortController();
  const timer=setTimeout(()=>ctrl.abort(), timeoutMs);
  try{
    const authPath=path+(path.includes('?')?'&':'?')+auth;
    const req=Object.assign({}, opts, {signal:ctrl.signal});
    delete req.timeoutMs;
    const r=await fetch(authPath, req);
    if(!r.ok){
      const err=new Error(await r.text());
      err.status=r.status;
      throw err;
    }
    return r.json();
  }catch(e){
    if(e && e.name==='AbortError'){
      const err=new Error('Tempo esgotado ao carregar. Tente novamente.');
      err.timeout=true;
      throw err;
    }
    throw e;
  }finally{ clearTimeout(timer); }
}

/* ---- Tema Zydon: Light/Dark seguindo paleta da marca. Toggle no perfil. ---- */
function currentTheme(){ try{return localStorage.getItem('zydon-theme')||'light'}catch{return 'light'} }
function applyTheme(t){
  t=(t||currentTheme()); if(t!=='dark') t='light';
  document.documentElement.setAttribute('data-theme',t);
  try{localStorage.setItem('zydon-theme',t)}catch(e){}
  const logo=document.getElementById('brandLogo'); if(logo) logo.src=(t==='dark'?'/logo-dark.png':'/logo.png');
  const btn=document.getElementById('themeBtn'); if(btn) btn.innerHTML=themeIcon(t==='dark'?'sun':'moon');
}
function toggleTheme(ev){ if(ev) ev.stopPropagation(); applyTheme(currentTheme()==='dark'?'light':'dark'); }
function themeIcon(k){
  const moon='<path d="M21 12.8A8.5 8.5 0 1 1 11.2 3a6.5 6.5 0 0 0 9.8 9.8z"/>';
  const sun='<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>';
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${k==='sun'?sun:moon}</svg>`;
}
applyTheme(currentTheme());

function maskPhone(chat){
  const s=(chat||'').toString();
  // CH-006: nunca vazar @lid/@s.whatsapp.net/@g.us nem mascarar LID como telefone.
  if(/@lid$/i.test(s)) return 'Número protegido';
  if(/@g\.us$/i.test(s)||/@broadcast$/i.test(s)||s==='status@broadcast') return '—';
  const d=s.replace(/\D/g,'');
  if(d.length>=12) return `+${d.slice(0,2)} ${d.slice(2,4)} ${d[4]||'9'}•••• ••${d.slice(-2)}`;
  return '—';
}
// Telefone para exibição: usa o que o servidor já validou (displayPhone), senão
// um rótulo seguro. Nunca renderiza o JID/LID bruto.
function phoneText(c){
  if(!c) return '—';
  if(c.displayPhone) return c.displayPhone;   // já validado no servidor (BR real)
  return c.lid ? 'Número protegido' : '—';    // nunca cai para o JID/LID bruto
}
const identityHydrated=new Set();
const identityHydrating=new Set();
let identityHydrateTimer=null;
function needsHubspotIdentity(c){
  if(!c||!c.id||hsCache[c.id]) return false;
  const title=String(c.title||'').trim(), sub=String(c.subtitle||'').trim();
  return looksLikePhoneName(title) || !title || looksLikePhoneName(sub) || sub===phoneText(c);
}
async function hydrateConvIdentity(c){
  if(!c||!c.id||identityHydrated.has(c.id)||identityHydrating.has(c.id)||hsCache[c.id]) return;
  identityHydrating.add(c.id);
  try{
    const data=await api('/api/hubspot?conv='+encodeURIComponent(c.id));
    hsCache[c.id]=data;
    applyHubspotIdentityToConv(c,data);
    if(viewMode==='conversas') drawCards();
    if(active===c.id){ drawHead(c); const el=document.getElementById('hsBody'); if(el) el.innerHTML=hubspotView(c,ownerOf(c.port),statusLeadOf(c),data); }
  }catch(e){} finally{ identityHydrating.delete(c.id); identityHydrated.add(c.id); }
}
function scheduleIdentityHydration(reason='visible'){
  // Produção: não hidratar 24 cards em background. Isso competia com /api/messages
  // e deixava a timeline presa em "Carregando mensagens" durante disparos em massa.
  // A identidade/contexto do lead continua sendo carregada no clique/abertura.
  return;
}
function relTime(ts){
  const raw=Math.floor(Date.now()/1000 - (+ts||0));
  const s=Math.max(0, raw);
  if(!ts) return '';
  if(s<60) return 'agora'; if(s<3600) return Math.floor(s/60)+'min';
  if(s<86400) return Math.floor(s/3600)+'h'; if(s<7*86400) return Math.floor(s/86400)+'d';
  try{return new Date((+ts)*1000).toLocaleDateString('pt-BR',{timeZone:'America/Sao_Paulo',day:'2-digit',month:'short'})}catch{return ''}
}
function dt(ts){try{return new Date((+ts)*1000).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo'})}catch{return ''}}
function hhmm(ts){try{return new Date((+ts)*1000).toLocaleTimeString('pt-BR',{timeZone:'America/Sao_Paulo',hour:'2-digit',minute:'2-digit'})}catch{return ''}}
function dayKey(ts){try{return new Date((+ts)*1000).toLocaleDateString('pt-BR',{timeZone:'America/Sao_Paulo',weekday:'long',day:'2-digit',month:'long'})}catch{return ''}}

function ownerOf(port){const m=portMeta[port]||{}; return (m.owner||'').replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase())||m.label||('Chip '+port)}
function chipLabel(port){return (portMeta[port]||{}).label||('Chip '+port)}

/* ---- queue classification (front-end, derivado dos dados reais) ---- */
function leadLast(c){return c.last && c.last.fromMe===false}
function hasActionableLeadReply(c){
  // CH-008: “Responder agora” só deve mostrar bola REAL com o comercial.
  // Critério: última mensagem recebida do lead existe, é a última interação da
  // conversa (posterior à última saída/automação), e não é apenas um estado já
  // resolvido sem nova entrada. Isso evita mídia/status/contatos inválidos ou
  // conversas antigas com respostas históricas contaminarem a fila quente.
  const li=+(c.lastIncomingTime||0), lo=+(c.lastOutgoingTime||0), lt=+(c.lastTime||0);
  if(!li) return false;
  if(li < lo) return false;           // SDR/automação já respondeu depois
  if(Math.abs(li-lt)>2 && !leadLast(c)) return false; // última interação não é do lead
  if(localStatusOf(c)==='resolved' && li <= +(c.localUpdatedAt||0)) return false;
  const m=c.lastIncoming||c.last||{};
  const txt=((m.text||'')+'').trim();
  const hasMedia=!!(m.mediaUrl||m.mediaName||m.mediaPath||m.mimetype);
  if(!txt && !hasMedia) return false;
  return true;
}
function autoType(c){return (c.last&&c.last.type)||''}
function isMeeting(c){
  // CH-003: dado real do HubSpot (reunião no negócio) tem prioridade sobre o regex.
  if(c&&(c.hubspotHasMeeting||c.meetingNextAt)) return true;
  const txt=((c.last&&c.last.text)||'').toLowerCase();
  return /reuni[aã]o|reuni\b|agendar|agenda|hor[áa]rio|marcar.*call|call\b|meeting/.test(txt);
}
function inQueue(c,q){
  const t=autoType(c), src=c.lastSource||'';
  if(q==='todos') return true;
  // Responder agora: o lead respondeu e a bola está com o comercial.
  if(q==='responder'){
    return hasActionableLeadReply(c);
  }
  // Novos leads: lead que acabou de entrar e ainda não recebeu interação/resposta.
  if(q==='novos') return (c.responses||0)===0 && (t==='cron-sdr-primeiro-contato' || (c.messages||0)<=2);
  // Meus negócios: lead engajado (já respondeu ao menos uma vez) = negócio em andamento.
  if(q==='negocios') return (c.responses||0)>0;
  // Disparos institucionais: mensagens enviadas pelos chips Rafael/Mariana/Lucas
  // que tratam de leads/negócios dos SDRs. Inclui também conversas compartilhadas
  // (badge ↗ Chip) onde o chip original é institucional.
  if(q==='institucional'){
    const instPorts=[4600,4606,4607,4609,4610]; // Comunicadores/institucionais
    return instPorts.includes(c.port) || !!c.sharedFromPort;
  }
  if(q==='diagnostico') return /^cron-mql/.test(t) || /diagn/i.test(src);
  if(q==='primeiro') return t==='cron-sdr-primeiro-contato' || /1º contato/i.test(src);
  if(q==='reunioes') return isMeeting(c);
  if(q==='audios') return +(c.audioPending||0)>0;
  if(q==='sem_resposta') return !leadLast(c) && (c.responses||0)===0;
  return true;
}
function stageBadge(c){
  if(leadLast(c)) return '<span class="badge b-reply">⚡ Lead respondeu</span>';
  const t=autoType(c), src=c.lastSource||'';
  if(/^cron-mql/.test(t)||/diagn/i.test(src)) return '<span class="badge b-diag">Automação · diagnóstico</span>';
  if(t==='cron-sdr-primeiro-contato'||/1º contato/i.test(src)) return '<span class="badge b-pc">Automação · 1º contato</span>';
  if((c.responses||0)===0 && (c.messages||0)<=2) return '<span class="badge b-new">Novo lead</span>';
  return '<span class="badge b-done">Aguardando resposta</span>';
}
// CH-010: estado de triagem local (status + nota), persistido via /api/state.
function localStatusOf(c){return (c&&c.localStatus)||'open'}
function localBadge(c){
  const s=localStatusOf(c);
  let out='';
  if(s==='pending') out+='<span class="badge b-pend">◷ Pendente</span>';
  else if(s==='resolved') out+='<span class="badge b-res">✓ Resolvido</span>';
  else if(s==='archived') out+='<span class="badge b-arch">Arquivada</span>';
  if(c.localNote) out+=`<span class="badge b-note" title="${esc(c.localNote)}">📝 Nota</span>`;
  return out;
}
function automationBadge(c){
  const a=(c&&c.automation)||{};
  let out='';
  if(a.risk==='falha') out+='<span class="badge b-risk">⚠ Automação falhou</span>';
  else if(a.diagnostico==='parcial') out+='<span class="badge b-risk">⚠ Diagnóstico parcial</span>';
  else if(a.diagnostico==='feito') out+='<span class="badge b-diag">Diagnóstico feito</span>';
  if(a.primeiroContato==='feito') out+='<span class="badge b-pc">1º contato feito</span>';
  if(a.count>1) out+=`<span class="badge b-auto">🤖 ${a.count} automações</span>`;
  if(a.followup==='feito') out+='<span class="badge b-done">Follow-up feito</span>';
  return out;
}
function sharedBadge(c){
  if(!c || !c.sharedFromPort) return '';
  const label=chipLabel(c.port);
  const title=c.sharedVisibilityReason||'Conversa de chip compartilhado vinculada ao SDR';
  return `<span class="badge b-shared" title="${esc(title)}">↗ ${esc(label)}</span>`;
}
function hubspotBadge(c){
  if(!c || c.readOnlyInstitutional || c.hubspotLinked) return '';
  const title='Telefone não encontrado no HubSpot por telefone/contato/deal. Tratar como avulso ou vincular no CRM.';
  return `<span class="badge b-hs" title="${esc(title)}">Sem HubSpot</span>`;
}
function autoStatusText(v){return ({feito:'Feito',pendente:'Pendente',parcial:'Parcial',ok:'OK','atenção':'Atenção',falha:'Falha'})[v]||v||'Pendente'}
function previewFrom(c){
  if(leadLast(c)) return {cls:'lead', label:'Lead'};
  const t=autoType(c);
  if(/^cron-/.test(t)) return {cls:'auto', label:'Auto'};
  return {cls:'sdr', label:'SDR'};
}
function slaTag(c){
  if(hasActionableLeadReply(c)) return '<span class="sla now"><span class="pulse"></span>Responder agora</span>';
  const s=Math.floor(Date.now()/1000-(+c.lastTime||0));
  if(!c.lastTime) return '';
  if(s>3*3600) return `<span class="sla warn"><span class="pulse"></span>há ${relTime(c.lastTime)} sem resposta</span>`;
  return `<span class="sla ok">enviado há ${relTime(c.lastTime)}</span>`;
}

/* ---------- render ---------- */
function renderShell(){
  document.getElementById('root').innerHTML=`<div class="app" id="app">
    <aside class="col sidebar">
      <div class="brand"><div class="logo"><img id="brandLogo" src="/logo.png" alt="Zydon"></div><div class="name">Inbox comercial</div></div>
      <div class="appnav" aria-label="Menu principal">
        <button id="modeConv" data-view="conversas" class="on" onclick="setViewMode('conversas')" title="Conversas"><span class="ico"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7.5A4.5 4.5 0 0 1 9.5 3h5A4.5 4.5 0 0 1 19 7.5v3A4.5 4.5 0 0 1 14.5 15H11l-4.5 3v-3.2A4.5 4.5 0 0 1 5 10.5v-3Z"/><path d="M9 8h6M9 11h4"/></svg></span><span class="lbl">Conversas</span></button>
        <button id="modeFocus" data-view="foco" onclick="setViewMode('foco')" title="Foco SDR"><span class="ico"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13 3 6 13h5l-1 8 8-11h-5l0-7Z"/></svg></span><span class="lbl">Foco SDR</span></button>
        <button id="modeMgmt" data-view="gestao" onclick="setViewMode('gestao')" title="Gestão"><span class="ico"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 19V5"/><path d="M4 19h16"/><path d="M8 16v-5"/><path d="M12 16V8"/><path d="M16 16v-3"/></svg></span><span class="lbl">Gestão</span></button>
      </div>
      <nav class="nav"><div class="nav-label">Conversas</div><div id="queues"></div></nav>
      <div class="conn-foot"><button class="conn-btn" id="connBtn" onclick="openConnections()"><span class="st off"></span><span class="cl-label">WhatsApp e equipe</span></button></div>
      <div class="me" title="Perfil"><div class="avatar" id="meAva"></div><div class="nm"><b id="meName">—</b><span id="meSub"></span></div><div class="profile-actions"><button class="theme-btn" id="themeBtn" onclick="toggleTheme(event)" title="Alternar tema"></button><button class="logout-btn" onclick="event.stopPropagation(); location.href='/logout'" title="Sair"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/></svg></button></div></div>
    </aside>
    <section class="col list">
      <div class="zone-head"><div class="search"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m20 20-3-3"/></svg><input id="search" placeholder="Buscar empresa, contato, telefone…"><kbd>/</kbd></div></div>
      <div class="list-sub"><span class="title" id="queueTitle">Conversas</span><span class="n" id="queueCount"></span><span class="live-status" id="liveStatus" title="A inbox atualiza sozinha"><span class="live-dot"></span><span class="live-txt">ao vivo</span><span class="live-ago"></span></span><button class="live-refresh" onclick="loadAll({fast:true,force:true})" title="Atualizar agora">Atualizar</button><span class="spacer"></span><button class="filter-toggle" id="filterToggle" onclick="toggleFilters()">Filtros</button></div>
      <div class="filterbar" id="filterbar"></div>
      <div class="scroll"><div class="cards" id="cards"></div></div>
      <div class="bulkbar" id="bulkbar" hidden>
        <span class="bb-n" id="bbN"></span>
        <button class="bulk-open" onclick="openBulkWizard('stress')">Ações</button>
        <button class="bulk-clear" onclick="clearSelection()">Limpar</button>
      </div>
    </section>
    <main class="col conversation">
      <div class="zone-head conv-head" id="convHead"><div class="ttl"><b>Selecione um lead</b><div class="sub">Escolha um lead para ver WhatsApp, HubSpot e próximas ações.</div></div></div>
      <div class="timeline" id="timeline"><div class="empty"><b>Nenhum lead aberto</b><span>Selecione um lead para ver mensagens, negócio e próximas ações.</span></div></div>
      <div class="composer">
        <div class="quick" id="quick"></div>
        <div class="route-note" id="routeNote" hidden></div>
        <div class="cbox" id="cbox">
          <div class="ctabs"><button class="ctab on" id="tabReply" onclick="setMode('reply')">WhatsApp</button><button class="ctab" id="tabPlaybook" onclick="setMode('playbook')">Playbooks</button><button class="ctab" id="tabNote" onclick="setMode('note')">Nota interna</button></div>
          <div class="playbook-panel" id="playbookPanel" hidden></div>
          <div class="attach-row" id="attachRow" hidden><span class="attach-ic">📎</span><span class="attach-name" id="attachName"></span><button class="attach-rm" id="attachRm" onclick="clearAttachment()" title="Remover anexo">✕</button></div>
          <input type="file" id="fileInput" hidden accept=".pdf,image/*,audio/*,.doc,.docx,.xls,.xlsx,.csv,.txt" onchange="onFilePicked(this)">
          <div class="cinput-row">
            <button class="attach-btn" id="attachBtn" onclick="document.getElementById('fileInput').click()" title="Anexar arquivo"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg></button>
            <textarea id="composer" placeholder="Selecione um lead para responder…" rows="1"></textarea>
            <button class="send" id="sendBtn" onclick="sendReply()"><svg class="send-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg><span id="sendLabel">Enviar</span></button>
          </div>
          <div class="chint"><span class="hint">Enter envia uma vez · Shift+Enter quebra linha</span></div>
        </div>
      </div>
    </main>
    <aside class="col context" id="context"><div class="zone-head" style="justify-content:space-between"><b style="font-size:13.5px;font-weight:650">Contexto comercial</b><button class="icon-btn" onclick="toggleCtx(false)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg></button></div><div class="scroll" id="ctxBody"><div class="placeholder" style="padding:20px">Selecione um lead para ver negócio, tarefa e histórico comercial.</div></div></aside>
    <div class="scrim" onclick="toggleCtx(false)"></div>
    <nav class="mobile-tabbar" aria-label="Navegação principal">
      <button data-view="conversas" class="on" onclick="setViewMode('conversas')"><span class="ico"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7.5A4.5 4.5 0 0 1 9.5 3h5A4.5 4.5 0 0 1 19 7.5v4A4.5 4.5 0 0 1 14.5 16H11l-4.5 3v-3.4A4.5 4.5 0 0 1 5 12V7.5Z"/><path d="M9 8h6M9 11h4"/></svg></span><span class="lbl">Conversas</span></button>
      <button data-view="foco" onclick="setViewMode('foco')"><span class="ico"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13 2 5 13h6l-1 9 9-13h-6l0-7Z"/></svg></span><span class="lbl">Foco SDR</span></button>
      <button data-view="gestao" onclick="setViewMode('gestao')"><span class="ico"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 19V5"/><path d="M4 19h16"/><path d="M8 16v-5"/><path d="M12 16V8"/><path d="M16 16v-3"/></svg></span><span class="lbl">Gestão</span></button>
    </nav>
    <div class="modal file-modal" id="fileModal" hidden>
      <div class="modal-scrim" onclick="closeFilePreview()"></div>
      <div class="modal-card">
        <div class="modal-head"><b id="fileModalTitle">Arquivo</b><span class="modal-sub" id="fileModalSub"></span><span class="spacer"></span><div class="file-actions"><a id="fileModalDownload" class="primary" href="#" target="_blank" download>Baixar</a><button onclick="closeFilePreview()">Fechar</button></div></div>
        <div class="modal-body" id="fileModalBody"><div class="file-preview-fallback"><b>Selecione um arquivo</b></div></div>
      </div>
    </div>
    <div class="modal" id="connModal" hidden>
      <div class="modal-scrim" onclick="closeConnections()"></div>
      <div class="modal-card">
        <div class="modal-head"><b>WhatsApp e equipe</b><span class="modal-sub" id="connSub"></span><span class="spacer"></span><button class="icon-btn" onclick="closeConnections()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg></button></div>
        <div class="modal-body" id="connBody"></div>
        <div class="modal-foot">SDR = usuário comercial vinculado ao owner do HubSpot e ao próprio chip. Comunicador = chip auxiliar/institucional com porta exclusiva, usado pela régua de disparos.</div>
      </div>
    </div>
    <div class="modal" id="adminModal" hidden>
      <div class="modal-scrim" onclick="closeAdminUsers()"></div>
      <div class="modal-card">
        <div class="modal-head"><b>Admin usuários e chips</b><span class="modal-sub">Google email → usuário → chips visíveis</span><span class="spacer"></span><button class="bb-btn" onclick="adminEditUser(null)">＋ Usuário</button><button class="icon-btn" onclick="closeAdminUsers()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg></button></div>
        <div class="modal-body" id="adminBody"></div>
        <div class="modal-foot">Somente admin. Não mostra tokens. Produção deve usar Google/Cloudflare Access; token por URL segue desligado.</div>
      </div>
    </div>
    <div class="modal" id="pipeModal" hidden>
      <div class="modal-scrim" onclick="closePipeModal()"></div>
      <div class="modal-card">
        <div class="modal-head"><b id="pipeModalTitle">Leads do card</b><span class="modal-sub" id="pipeModalSub"></span><span class="spacer"></span><button class="icon-btn" onclick="closePipeModal()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg></button></div>
        <div class="modal-body" id="pipeModalBody"></div>
        <div class="modal-foot">Lista read-only para validação. Clique em HubSpot para abrir o negócio.</div>
      </div>
    </div>
    <div class="modal" id="dispatchModal" hidden>
      <div class="modal-scrim" onclick="closeDispatchModal()"></div>
      <div class="modal-card dispatch-modal-card">
        <div class="modal-head"><b id="dispatchModalTitle">Disparos</b><span class="modal-sub" id="dispatchModalSub"></span><span class="spacer"></span><button class="icon-btn" onclick="closeDispatchModal()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg></button></div>
        <div class="modal-body" id="dispatchModalBody"></div>
        <div class="modal-foot">Lista read-only do ledger operacional. Abrir conversa leva para o chat/auditoria correspondente.</div>
      </div>
    </div>
    <div class="modal wizard-modal" id="bulkWizard" hidden>
      <div class="modal-scrim" onclick="closeBulkWizard()"></div>
      <div class="modal-card">
        <div class="modal-head"><b id="wizTitle">Ações da seleção</b><span class="modal-sub" id="wizSub"></span><span class="spacer"></span><button class="icon-btn" onclick="closeBulkWizard()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg></button></div>
        <div class="wizard-steps"><div class="wiz-step on" id="wizStep1"><b>1. Conferir</b>Resumo e limites</div><div class="wiz-step" id="wizStep2"><b>2. Revisar leads</b>Aptos e bloqueados</div><div class="wiz-step" id="wizStep3"><b>3. Próxima ação</b>Seguro, sem disparo</div></div>
        <div class="modal-body" id="wizBody"></div>
        <div class="wiz-foot"><button onclick="wizMove(-1)" id="wizPrev">Voltar</button><span class="spacer"></span><button onclick="closeBulkWizard()">Fechar</button><button class="primary" onclick="wizMove(1)" id="wizNext">Continuar</button></div>
      </div>
    </div>
  </div>`;
  const s=document.getElementById('search'); s.oninput=()=>{drawCards(); scheduleIdentityHydration('search');};
  document.addEventListener('keydown',e=>{if(e.key==='/'&&document.activeElement.tagName!=='INPUT'&&document.activeElement.tagName!=='TEXTAREA'){e.preventDefault();s.focus()}if(e.key==='Escape'){ if(connOpen) closeConnections(); closePipeModal(); }});
  const ta=document.getElementById('composer');
  ta.addEventListener('input',()=>{ta.style.height='auto';ta.style.height=Math.min(160,ta.scrollHeight)+'px'});
  ta.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendReply()}});
  renderQuick();
  applyTheme(currentTheme());
}

function routeForViewMode(mode){return mode==='foco'?'/foco':(mode==='gestao'?'/gestao':'/conversas')}
function initialViewModeFromPath(){
  const p=window.location.pathname||'/';
  if(p==='/foco') return 'foco';
  if(p==='/gestao') return 'gestao';
  return 'conversas';
}
function setViewMode(mode, opts={}){
  viewMode=mode||'conversas';
  if(!opts.skipHistory){
    const target=routeForViewMode(viewMode);
    if(window.location.pathname!==target) history.pushState({viewMode},'',target);
  }
  document.querySelectorAll('[data-view]').forEach(btn=>btn.classList.toggle('on', btn.dataset.view===viewMode));
  const app=document.getElementById('app');
  if(app) app.classList.toggle('analytics-mode', viewMode==='foco'||viewMode==='gestao');
  const ft=document.getElementById('filterToggle');
  if(ft) ft.style.display=(viewMode==='conversas')?'':'none';
  const fb=document.getElementById('filterbar');
  if(fb && viewMode!=='conversas'){ fb.classList.remove('open'); fb.innerHTML=''; }
  if(viewMode==='foco'||viewMode==='gestao'){
    if(!pipelineFocus && !pipelineFocusLoading) loadPipelineFocus();
    if(viewMode==='gestao' && !dispatchStats && !dispatchStatsLoading) loadDispatchStats();
  }
  drawCards();
}

function sdrNameForActive(){
  const c=convs.find(x=>x.id===active)||{};
  let n=ownerOf(c.port)||'Zydon';
  // Owner pode vir como “Lucas Batista”, “Breno”, “Sarah”, “Mariana”.
  return n.replace(/\s+1$|\s+2$/,'').trim()||'Zydon';
}
function companyForActive(){
  const c=convs.find(x=>x.id===active)||{};
  const t=(c.title||'').trim();
  if(!t || /^\+55|Lead sem número|Contato sem número/i.test(t)) return 'sua empresa';
  return t;
}
function quickTemplates(){
  const sdr=sdrNameForActive(), emp=companyForActive();
  return [
    {label:'Retomar', text:`Oi, tudo bem? Vi sua mensagem aqui. Vou te ajudar com isso.`},
    {label:'Agendar', text:`Perfeito. Posso te mandar alguns horários para uma conversa rápida sobre a ${emp}?`},
    {label:'Detalhes', text:`Claro. Me conta só um pouco mais do cenário da ${emp} hoje para eu te orientar melhor.`},
    {label:'Recebi', text:`Recebi sim. Vou olhar com atenção e já te retorno por aqui.`},
    {label:'Assinatura', text:`Aqui é ${sdr}, da Zydon. Fico à disposição por aqui.`},
  ];
}
function suggestedReplyForActive(){
  const c=convs.find(x=>x.id===active);
  if(!c) return '';
  const emp=companyForActive();
  const ai=c.aiSummary||{};
  const sig=ai.signals||[];
  const has=s=>sig.indexOf(s)>=0;
  const hs=hsCache[c.id]||{};
  const deal=(hs.deals&&hs.deals[0])||{};
  const meetings=(deal.meetings||[]);
  const meeting=meetings[0]||null;
  const dealStage=deal.dealstageLabel||deal.dealstage||'';
  const dealOwner=deal.hubspot_owner_name||deal.hubspot_owner_id||'';
  const transcript=(c.audioTranscriptText||'').toLowerCase();
  const replied=leadLast(c)||has('Lead respondeu')||(c.responses||0)>0;
  const askedMeeting=has('Pediu reunião')||!!meeting;
  const hasAudio=has('Áudio do lead')||!!c.audioTranscriptText||!!c.audioPending;
  const noReply=!replied && (has('Diagnóstico enviado')||has('Primeiro contato enviado')||has('Sem resposta'));
  // Reunião real no HubSpot -> confirmar contexto e evitar pedir para marcar de novo.
  if(meeting){
    const when=meeting.timestamp ? hsDateTime(meeting.timestamp) : 'o horário combinado';
    const who=meeting.ownerName||dealOwner||'o consultor responsável';
    return `Perfeito, vi aqui que já temos uma conversa agendada para ${when} com ${who}. Se quiser, pode me mandar por aqui os principais pontos que você quer tratar na ${emp} para chegarmos mais direto ao assunto.`;
  }
  // Lead mandou áudio -> reconhecer que recebeu/viu a transcrição, sem inventar conteúdo.
  if(hasAudio && replied){
    return `Recebi seu áudio, obrigado! Vou considerar o que você comentou sobre a ${emp}. Para eu te responder com mais precisão, o ponto principal agora é avançarmos para uma conversa rápida ou você prefere me mandar mais detalhes por aqui?`;
  }
  // Lead pediu reunião/agenda -> oferecer horários/conversa rápida.
  if(askedMeeting)
    return `Perfeito! Posso te sugerir alguns horários para uma conversa rápida sobre a ${emp}. Funciona melhor pra você ainda esta semana ou na próxima? Me diz um período que eu já reservo.`;
  // Se HubSpot mostra deal em etapa avançada, não tratar como lead frio.
  if(dealStage && /diagn[oó]stico|apresenta|proposta|negocia/i.test(dealStage))
    return `Boa. Pelo que vi aqui, a ${emp} já está em andamento com a Zydon. Me conta o que você precisa agora que eu te ajudo a dar sequência do jeito certo.`;
  // Lead respondeu, mas sem pedido de reunião -> reconhecer e perguntar próximo ponto.
  if(replied)
    return `Valeu pelo retorno! Para eu te orientar do jeito certo na ${emp}, me conta qual é a principal dúvida ou o ponto mais importante pra você nesse momento?`;
  // Sem resposta após primeiro contato -> follow-up leve.
  if(noReply)
    return `Oi! Passando rápido só para retomar nosso contato. Se fizer sentido conversarmos sobre a ${emp}, é só me avisar por aqui que eu sigo com você. Sem pressa.`;
  return `Oi, tudo bem? Estou por aqui para te ajudar com a ${emp}. Como posso te apoiar?`;
}
function suggestReply(){
  const ta=document.getElementById('composer'); if(!ta) return;
  const text=suggestedReplyForActive(); if(!text) return;
  ta.value=text; ta.focus(); ta.dispatchEvent(new Event('input'));
}
function renderQuick(){
  const items=quickTemplates();
  document.getElementById('quick').innerHTML=
    `<button class="ai" title="Preenche o texto, não envia" onclick="suggestReply()">✨ Sugerir resposta</button>`+
    items.map((it,i)=>`<button title="${esc(it.text)}" onclick="quick(${i})">${esc(it.label)}</button>`).join('');
}
function quick(i){const ta=document.getElementById('composer'); const it=quickTemplates()[i]; if(!it) return; ta.value=it.text; ta.focus(); ta.dispatchEvent(new Event('input'))}

function renderQueues(){ const q=document.getElementById('queues'); if(q) q.innerHTML=''; }
function queueIcon(k){
  const I={
    responder:'<path d="M13 2 3 14h7l-1 8 10-12h-7l1-8z"/>',
    novos:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6M22 11h-6"/>',
    negocios:'<path d="M3 3v18h18"/><path d="M7 14l4-4 3 3 5-6"/>',
    institucional:'<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    diagnostico:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
    primeiro:'<path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z"/>',
    reunioes:'<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    audios:'<path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><path d="M12 19v3"/>',
    sem_resposta:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    todos:'<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  };
  return `<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round">${I[k]||''}</svg>`;
}

/* ---- CH-004: conexões / saúde dos chips (dados reais de /api/chips) ---- */
let chips=[], chipsSummary={}, connOpen=false;

async function loadChips(){
  try{ const d=await api('/api/chips'); chips=d.chips||[]; chipsSummary=d.summary||{}; }
  catch(e){ /* mantém último estado conhecido */ }
  renderChipsSummary();
  if(connOpen) renderConnections();
}

function renderChipsSummary(){
  // Conexão é suporte secundário: vira um botão discreto no rodapé da sidebar.
  // Só "grita" (badge + cor de alerta) quando algum chip precisa de ação real.
  const s=chipsSummary||{};
  const act=s.needsAction||0;
  const btn=document.getElementById('connBtn'); if(!btn) return;
  const dot = act>0 ? 'warn' : (s.online ? 'on' : 'off');
  btn.innerHTML = `<span class="st ${dot}"></span><span class="cl-label">Conexões WhatsApp</span>`
    + (act>0 ? `<span class="conn-badge">${act}</span>` : '');
  btn.classList.toggle('alert', act>0);
  btn.title = `${s.online||0} de ${s.total||0} conexões ativas`+(act>0?` · ${act} precisam de ação`:'');
}

function statusMeta(c){
  if(c.connected && !c.needsQR) return {dot:'on', label:'Online'};
  if(c.needsQR) return {dot:'warn', label:'Precisa de QR'};
  return {dot:'off', label:'Offline'};
}
function recMeta(r){return ({
  ok:{label:'Tudo certo',cls:'rec-ok'},
  reconectar:{label:'Reconectar',cls:'rec-bad'},
  aquecer:{label:'Aquecer chip',cls:'rec-warn'},
  adicionar_chip:{label:'Volume alto · adicionar chip',cls:'rec-warn'},
})[r]||{label:r,cls:''}}
function riskMeta(r){return ({
  baixo:{label:'Baixo',cls:'risk-low'},medio:{label:'Médio',cls:'risk-med'},alto:{label:'Alto',cls:'risk-high'}
})[r]||{label:r||'—',cls:''}}

function connCard(c){
  const sm=statusMeta(c), rec=recMeta(c.recommendation), rk=riskMeta(c.risk);
  const action = c.qrUrl
    ? `<a class="btn primary" target="_blank" rel="noopener" href="${c.qrUrl}&${auth}">Reconectar / QR</a>`
    : (c.recommendation==='ok' ? '<span class="none">Nenhuma ação necessária</span>'
                               : '<span class="none">Acompanhar volume</span>');
  return `<div class="conn-card">
    <div class="cc-head"><span class="st ${sm.dot}"></span><span class="cc-name">${esc(c.label)}</span><span class="cc-status">${sm.label}</span><span class="cc-port">porta ${c.port}</span></div>
    <div class="cc-metrics">
      <div><span class="m-l">Hoje</span><span class="m-v">${c.volumeToday}<small>/${c.suggestedLimit}</small></span></div>
      <div><span class="m-l">Uso do limite</span><span class="m-v">${c.loadPct||0}<small>%</small></span></div>
      <div><span class="m-l">Saúde</span><span class="m-v ${c.healthScore<50?'risk-high':(c.healthScore<75?'risk-med':'risk-low')}">${c.healthScore??'—'}<small>/100</small></span></div>
      <div><span class="m-l">Total enviado</span><span class="m-v">${c.volumeTotal}</span></div>
      <div><span class="m-l">Respostas</span><span class="m-v">${c.responses}<small>${c.responseRate?(' · '+c.responseRate+'%'):''}</small></span></div>
      <div><span class="m-l">Risco</span><span class="m-v ${rk.cls}">${rk.label}</span></div>
    </div>
    <div class="cc-foot"><span class="rec ${rec.cls}">${rec.label}</span><span class="spacer"></span>${action}</div>
  </div>`;
}

let connTab='sdr', pendingDisconnectPort=null;
function portByNum(port){ return (adminPorts||[]).find(p=>String(p.port)===String(port)) || (chips||[]).find(p=>String(p.port)===String(port)) || {}; }
function chipForPort(port){ return (chips||[]).find(c=>String(c.port)===String(port)) || {}; }
function userForOwner(owner){ return (adminUsers||[]).find(u=>u.id===owner) || {}; }
function roleLabel(role){ return role==='sdr'?'SDR':'Comunicador'; }
function statusPill(c){ const sm=statusMeta(c||{}); return `<span class="pill ${sm.dot==='on'?'good':(sm.dot==='warn'?'warn':'bad')}"><span class="st ${sm.dot}"></span>${sm.label}</span>`; }
function renderTeamCard(portMeta, kind){
  const c=chipForPort(portMeta.port), u=userForOwner(portMeta.owner), isSdr=(kind==='sdr');
  const online = c && Object.keys(c).length ? statusPill(c) : '<span class="pill warn">sem leitura de status</span>';
  const hs = isSdr ? (u.hubspotOwnerId?`<span class="pill good">HubSpot owner ${esc(u.hubspotOwnerId)}</span>`:'<span class="pill bad">sem owner HubSpot</span>') : '<span class="pill">régua institucional/comunicador</span>';
  const emails = (u.emails||[]).length ? `<span class="pill">${esc((u.emails||[]).join(', '))}</span>` : '<span class="pill warn">sem e-mail Google vinculado</span>';
  const qrHref=`/qr?port=${portMeta.port}&${auth}`;
  const needsQr=(c.needsQR || !c.connected);
  const confirm=pendingDisconnectPort===portMeta.port;
  return `<div class="team-card ${isSdr?'top-sdr':'top-com'}">
    <div class="cc-head"><span class="cg-av" style="background:${colorFor(portMeta.label)}">${esc(initials(portMeta.label))}</span><span class="cc-name">${esc(portMeta.label)}</span><span class="cc-status">${roleLabel(portMeta.role)}</span><span class="cc-port">porta ${portMeta.port}</span></div>
    <div class="meta">${online}<span class="pill">usuário: ${esc(portMeta.owner)}</span>${hs}${isSdr?emails:''}</div>
    ${c.port?`<div class="cc-metrics" style="margin-top:10px"><div><span class="m-l">Hoje</span><span class="m-v">${c.volumeToday||0}<small>/${c.suggestedLimit||30}</small></span></div><div><span class="m-l">Saúde</span><span class="m-v ${(c.healthScore||0)<50?'risk-high':((c.healthScore||0)<75?'risk-med':'risk-low')}">${c.healthScore??'—'}<small>/100</small></span></div><div><span class="m-l">Risco</span><span class="m-v ${riskMeta(c.risk).cls}">${riskMeta(c.risk).label}</span></div></div>`:''}
    <div class="team-actions">
      <a class="primary" target="_blank" rel="noopener" href="${qrHref}">${needsQr?'Vincular / QR':'Ver conexão'}</a>
      <button onclick="adminStartPort(${portMeta.port})">Subir bridge</button>
      <button onclick="adminRegenQR(${portMeta.port})">Gerar QR novo</button>
      <button class="${confirm?'confirm-inline':'danger'}" onclick="${confirm?`adminDisconnectPort(${portMeta.port})`:`askDisconnect(${portMeta.port})`}">${confirm?'Confirmar desconexão':'Desconectar'}</button>
      ${(!isSdr && portMeta.port>=4608)?`<button class="danger" onclick="adminDeletePort(${portMeta.port})">Remover porta</button>`:''}
    </div>
  </div>`;
}
function teamForm(kind){
  const isSdr=kind==='sdr';
  return `<div class="team-section"><h3>${isSdr?'Adicionar SDR':'Adicionar comunicador'}</h3>
    <p>${isSdr?'SDR precisa de usuário Google, owner do HubSpot e porta/chip próprio.':'Comunicador ganha uma porta exclusiva e entra na régua institucional usada por Rafael, Mariana e Lucas Resende.'}</p>
    <div class="team-form">
      <label>Nome<input id="${kind}Name" placeholder="${isSdr?'Ex: Amanda SDR':'Ex: João Pedro'}"></label>
      <div class="form-row"><label>Porta<input id="${kind}Port" placeholder="auto" inputmode="numeric"></label><label>Auth dir<input id="${kind}Auth" placeholder="auto"></label></div>
      ${isSdr?`<label>HubSpot owner ID<input id="${kind}Hs" placeholder="ex: 86265630"></label><label>E-mail Google do SDR<input id="${kind}Email" placeholder="nome@zydon.com.br"></label>`:''}
      <button class="primary" onclick="saveTeamPort('${kind}')">Criar porta exclusiva + vínculo</button>
    </div>
  </div>`;
}
function renderConnections(){
  const all=(me&&me.admin&&adminPorts.length?adminPorts:(chips||[])).slice().sort((a,b)=>a.port-b.port);
  const online=all.filter(p=>{const c=chipForPort(p.port); return c.connected && !c.needsQR}).length;
  const qr=all.filter(p=>{const c=chipForPort(p.port); return c.needsQR || (!c.connected && c.port)}).length;
  document.getElementById('connSub').textContent=`${all.length} portas · ${online} online`+(qr?` · ${qr} aguardando QR`:'');
  const sdrs=all.filter(p=>p.role==='sdr');
  const comms=all.filter(p=>p.role!=='sdr');
  const current=connTab==='comunicadores'?comms:sdrs;
  const cards=current.map(p=>renderTeamCard(p, p.role==='sdr'?'sdr':'comunicador')).join('') || '<div class="team-empty">Nenhuma porta neste bloco.</div>';
  const adminPanel=(me&&me.admin)?teamForm(connTab==='comunicadores'?'comunicador':'sdr'):'<div class="team-section"><h3>Somente admin</h3><p>Peça ao Rafael para cadastrar ou desconectar chips.</p></div>';
  document.getElementById('connBody').innerHTML=`<div id="teamToast"></div><div class="team-tabs"><button class="${connTab==='sdr'?'on':''}" onclick="connTab='sdr';renderConnections()">SDRs (${sdrs.length})</button><button class="${connTab==='comunicadores'?'on':''}" onclick="connTab='comunicadores';renderConnections()">Comunicadores (${comms.length})</button></div><div class="team-layout"><div class="team-section"><h3>${connTab==='sdr'?'SDRs vinculados ao HubSpot':'Comunicadores / régua institucional'}</h3><p>${connTab==='sdr'?'Cada SDR deve ter owner do HubSpot + usuário Google + chip próprio para responder a carteira dele.':'Cada comunicador tem porta exclusiva e pode ser usado pelos serviços de disparo institucional.'}</p><div class="team-list">${cards}</div></div>${adminPanel}</div>`;
}
function teamMsg(txt, bad=false){ const el=document.getElementById('teamToast'); if(el) el.innerHTML=`<div class="team-toast" style="${bad?'border-color:rgba(255,107,107,.35);background:rgba(255,107,107,.08)':''}">${esc(txt)}</div>`; }
function openConnections(){ connOpen=true; document.getElementById('connModal').hidden=false; renderConnections(); loadChips(); if(me&&me.admin) loadAdminUsers(); }
function closeConnections(){ connOpen=false; document.getElementById('connModal').hidden=true; pendingDisconnectPort=null; }

/* ---- CH-014/064: admin de equipe/chips (sem token e sem prompt/confirm nativo) ---- */
let adminUsers=[], adminPorts=[];
async function loadAdminUsers(){
  try{ const d=await api('/api/admin/users'); adminUsers=d.users||[]; adminPorts=d.ports||[]; if(connOpen) renderConnections(); }
  catch(e){ teamMsg('Falha ao carregar admin: '+e.message, true); }
}
function slugUid(v){return normText(v).replace(/[^a-z0-9]+/g,'_').replace(/^_+|_+$/g,'')}
async function saveTeamPort(kind){
  const name=(document.getElementById(kind+'Name')?.value||'').trim();
  if(!name) return teamMsg('Informe o nome.', true);
  const port=(document.getElementById(kind+'Port')?.value||'').trim();
  const authDir=(document.getElementById(kind+'Auth')?.value||'').trim();
  const hs=(document.getElementById(kind+'Hs')?.value||'').trim();
  const email=(document.getElementById(kind+'Email')?.value||'').trim();
  const owner=slugUid(name);
  const payload={action:'create',label:name,owner,role:kind==='sdr'?'sdr':'comunicador',port:port||'auto',auth:authDir||'',start:true};
  if(kind==='sdr') payload.hubspotOwnerId=hs;
  try{
    const r=await api('/api/admin/ports',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if(kind==='sdr' && email){
      await api('/api/admin/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'upsert',id:owner,name,role:'sdr',hubspotOwnerId:hs,emails:[email],ports:[r.port],admin:false})});
    }
    teamMsg(`${name} criado na porta ${r.port}. Clique em Vincular / QR para parear.`);
    await loadAdminUsers(); await loadChips(); connTab=kind==='sdr'?'sdr':'comunicadores'; renderConnections();
  }catch(e){ teamMsg('Falha ao criar: '+e.message, true); }
}
function askDisconnect(port){ pendingDisconnectPort=port; renderConnections(); teamMsg('Clique em “Confirmar desconexão” para apagar a sessão/QR da porta '+port+'.'); }
async function adminStartPort(port){ try{ await api('/api/admin/ports',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'start',port})}); teamMsg('Bridge da porta '+port+' iniciada.'); await loadChips(); }catch(e){teamMsg('Falha ao subir bridge: '+e.message,true)} }
async function adminRegenQR(port){ try{ await api('/api/admin/ports',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'regen',port})}); teamMsg('QR novo solicitado para porta '+port+'.'); window.open(`/qr?port=${port}&${auth}`,'_blank'); await loadChips(); }catch(e){teamMsg('Falha ao gerar QR: '+e.message,true)} }
async function adminDisconnectPort(port){ try{ await api('/api/admin/ports',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'disconnect',port})}); pendingDisconnectPort=null; teamMsg('Porta '+port+' desconectada. Gere/vincule um QR novo quando quiser.'); await loadChips(); }catch(e){teamMsg('Falha ao desconectar: '+e.message,true)} }
async function adminDeletePort(port){ if(pendingDisconnectPort!==('del'+port)){ pendingDisconnectPort='del'+port; renderConnections(); return teamMsg('Clique em Remover porta de novo para confirmar remoção da porta '+port+'.'); }
  try{ await api('/api/admin/ports',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'delete',port})}); pendingDisconnectPort=null; teamMsg('Porta '+port+' removida.'); await loadAdminUsers(); await loadChips(); }catch(e){teamMsg('Falha ao remover porta: '+e.message,true)} }
// Compatibilidade: antigo botão Admin, se algum HTML antigo chamar.
async function openAdminUsers(){ openConnections(); connTab='sdr'; await loadAdminUsers(); renderConnections(); }
function closeAdminUsers(){ closeConnections(); }


function renderFilters(){} // noop — filtros SDR/chip removidos da UI


function ownerUidOfConv(c){ return c.dealOwnerUid || c.sharedOwnerUid || c.sdrHintUid || ((portMeta[c.port]||{}).owner) || ''; }
function ownerLabelOfConv(c){ return c.dealOwnerLabel || ((me&&me.ports||[]).find(p=>String(p.port)===String(c.port))||{}).owner || ownerUidOfConv(c).replace(/_/g,' '); }
function filterActiveCount(){ return [filterOwner,filterStatus,filterChip].filter(Boolean).length; }
function toggleFilters(){ filterOpen=!filterOpen; renderFilterBar(); }
function setWFilter(k,v){ if(k==='owner') filterOwner=v||''; if(k==='status') filterStatus=v||''; if(k==='chip') filterChip=v||''; drawCards(); }
function clearWFilters(){ filterOwner=''; filterStatus=''; filterChip=''; drawCards(); }
function renderFilterBar(){
  const bar=document.getElementById('filterbar'), btn=document.getElementById('filterToggle'); if(!bar) return;
  const owners=[...new Map(convs.map(c=>[ownerUidOfConv(c), ownerLabelOfConv(c)]).filter(x=>x[0]).sort((a,b)=>String(a[1]).localeCompare(String(b[1])))).entries()];
  const chips=[...new Map(convs.map(c=>[String(c.port), chipLabel(c.port)]).filter(x=>x[0]).sort((a,b)=>String(a[1]).localeCompare(String(b[1])))).entries()];
  const n=filterActiveCount();
  if(btn){ btn.classList.toggle('on', filterOpen||n>0); btn.textContent=n?`Filtros (${n})`:'Filtros'; }
  bar.classList.toggle('open', filterOpen||n>0);
  bar.innerHTML=`
    <span class="wfilter ${filterStatus==='unread'?'on':''}" onclick="setWFilter('status',filterStatus==='unread'?'':'unread')">Não lidas / responder</span>
    <span class="wfilter ${filterStatus==='audio'?'on':''}" onclick="setWFilter('status',filterStatus==='audio'?'':'audio')">Áudios</span>
    <span class="wfilter ${filterStatus==='meeting'?'on':''}" onclick="setWFilter('status',filterStatus==='meeting'?'':'meeting')">Reuniões/tarefas</span>
    <span class="wfilter ${filterStatus==='archived'?'on':''}" onclick="setWFilter('status',filterStatus==='archived'?'':'archived')">Arquivadas</span>
    <label class="wfilter ${filterOwner?'on':''}">Dono <select onchange="setWFilter('owner',this.value)"><option value="">Todos</option>${owners.map(([id,label])=>`<option value="${esc(id)}" ${id===filterOwner?'selected':''}>${esc(label)}</option>`).join('')}</select></label>
    <label class="wfilter ${filterChip?'on':''}">Chip <select onchange="setWFilter('chip',this.value)"><option value="">Todos</option>${chips.map(([id,label])=>`<option value="${esc(id)}" ${id===filterChip?'selected':''}>${esc(label)}</option>`).join('')}</select></label>
    ${n?'<button class="wfilter clear" onclick="clearWFilters()">Limpar</button>':''}`;
}
function autoRiskScore(c){const r=((c&&c.automation)||{}).risk; return r==='falha'?2:(r==='atenção'?1:0)}
function brDay(ts){try{return new Date((+ts||0)*1000).toLocaleDateString('en-CA',{timeZone:'America/Sao_Paulo'})}catch(e){return ''}}
function todayBR(){return new Date().toLocaleDateString('en-CA',{timeZone:'America/Sao_Paulo'})}
function incMap(map,k,n=1){k=k||'—'; map[k]=(map[k]||0)+n}
function cadenceActivities(c){return Math.max(0, Math.min(99, (+c.messages||0)-(+c.responses||0)))}
function cadenceBucket(c){const n=cadenceActivities(c); return n>=4?'4+':String(n)}
function cadenceNextAction(c){const n=cadenceActivities(c); if(n<=0) return 'D0 / 1º contato'; if(n===1) return '2º contato educativo'; if(n===2) return '3º contato com relevância'; if(n===3) return '4º toque / despedida'; return 'Nutrição / liberar prioridade';}
function cadenceProgress(c){const n=Math.min(4,cadenceActivities(c)); return `${n}/4 atividades`;}
function stressCandidate(c){return !c.readOnlyInstitutional && !hasActionableLeadReply(c) && (+c.responses||0)===0 && !isMeeting(c) && cadenceActivities(c)>0 && cadenceActivities(c)<4;}
function chipSnapshot(port){return (chips||[]).find(x=>String(x.port)===String(port))||null}
function routeSuggestion(c){
  const n=cadenceActivities(c), s=chipSnapshot(c.sendPort||c.port), label=(s&&s.label)||c.sendPortLabel||chipLabel(c.sendPort||c.port);
  const vol=s?`${s.volumeToday||0}/${s.suggestedLimit||30}`:'';
  if(s && (!s.connected || s.needsQR || s.risk==='alto')) return {kind:'oficial/comunicador', cls:'off', reason:`chip ${label} indisponível/risco alto${vol?' · '+vol:''}`};
  if(n>=3) return {kind:'oficial ou comunicador', cls:'hot', reason:`4º toque/despedida com mais consciência${vol?' · chip '+label+' '+vol:''}`};
  if(s && s.risk==='medio') return {kind:'comunicador leve', cls:'warn', reason:`chip ${label} em atenção${vol?' · '+vol:''}`};
  return {kind:'chip do SDR', cls:'', reason:`usar ${label}${vol?' · hoje '+vol:''}`};
}
function routePill(c){const r=routeSuggestion(c); return `<span class="route-pill ${r.cls}" title="${esc(r.reason)}">canal: ${esc(r.kind)}</span>`}
function topRows(map,total){const arr=Object.entries(map).sort((a,b)=>b[1]-a[1]); const max=Math.max(1,...arr.map(x=>x[1])); return arr.slice(0,8).map(([k,v])=>`<div class="mgmt-row"><span>${esc(k)}</span><span class="bar" style="width:${Math.max(4,Math.round(v/max*90))}px"></span><em>${v}</em></div>`).join('')||'<div class="mini-empty">Sem dados hoje.</div>'}
function responseRows(sentByOwner,respByOwner){const owners=[...new Set([...Object.keys(sentByOwner),...Object.keys(respByOwner)])]; const arr=owners.map(o=>[o, sentByOwner[o]||0, respByOwner[o]||0]).sort((a,b)=>b[2]-a[2]||b[1]-a[1]); return arr.slice(0,8).map(([o,s,r])=>`<div class="mgmt-row"><span>${esc(o)}</span><span>${r}/${s} respostas</span><em>${s?Math.round(r/s*100):0}%</em></div>`).join('')||'<div class="mini-empty">Sem respostas hoje.</div>'}
function managementMetrics(){
  const day=todayBR(), firstByChip={}, diagByChip={}, sentByOwner={}, respByOwner={}, cadenceByOwner={}, cadenceBuckets={'0':0,'1':0,'2':0,'3':0,'4+':0}, cadenceLists={'0':[],'1':[],'2':[],'3':[],'4+':[]}; let first=0, diag=0, responses=0, readonly=0, stress=0;
  convs.forEach(c=>{
    const a=c.automation||{}, chip=chipLabel(c.port), owner=c.dealOwnerLabel||ownerLabelOfConv(c)||'—';
    if(c.readOnlyInstitutional) readonly++;
    if(a.primeiroContatoAt && brDay(a.primeiroContatoAt)===day){ first++; incMap(firstByChip,chip); incMap(sentByOwner,owner); }
    const dt=Math.max(+a.diagnosticoTextAt||0,+a.diagnosticoPdfAt||0);
    if(dt && brDay(dt)===day){ diag++; incMap(diagByChip,chip); incMap(sentByOwner,owner); }
    // follow-up/backlog institucional também conta como envio do dia para o proprietário
    if(a.followupAt && brDay(a.followupAt)===day){ incMap(sentByOwner,owner); }
    if(c.lastIncomingTime && brDay(c.lastIncomingTime)===day){ responses++; incMap(respByOwner,owner); }
    if(!c.readOnlyInstitutional && !isMeeting(c) && (+c.responses||0)===0){
      const b=cadenceBucket(c); cadenceBuckets[b]=(cadenceBuckets[b]||0)+1; (cadenceLists[b]=cadenceLists[b]||[]).push(c);
      if(cadenceActivities(c)>0 && cadenceActivities(c)<4) stress++;
      const key=owner+' · '+b+' ativ.'; incMap(cadenceByOwner,key);
    }
  });
  Object.keys(cadenceLists).forEach(k=>cadenceLists[k].sort((a,b)=>(+a.lastOutgoingTime||+a.lastTime||0)-(+b.lastOutgoingTime||+b.lastTime||0)));
  return {day,first,diag,responses,readonly,firstByChip,diagByChip,sentByOwner,respByOwner,cadenceBuckets,cadenceByOwner,cadenceLists,stress};
}
function cadenceCoverageBlock(m){
  const cb=m.cadenceBuckets||{}, labels={'0':'0 atividades','1':'1 atividade','2':'2 atividades','3':'3 atividades','4+':'4+ atividades'};
  const total=Object.values(cb).reduce((a,b)=>a+(+b||0),0);
  const chips=['0','1','2','3','4+'].map(k=>`<span class="cad-chip ${k==='4+'?'cad-nutri':(k==='1'||k==='2'||k==='3'?'cad-wait':'cad-apt')}"><b>${cb[k]||0}</b> ${labels[k]}</span>`).join('');
  const lists=m.cadenceLists||{};
  const board={stress1:lists['1']||[],stress2:lists['2']||[],stress3:lists['3']||[]};
  const zeroRows=(lists['0']||[]).slice(0,5).map(c=>focusRow(c,'Ainda sem D0 confiável · iniciar 1º contato')).join('')||'<div class="mini-empty">Sem leads zerados.</div>';
  const nutriRows=(lists['4+']||[]).slice(0,5).map(c=>focusRow(c,'4+ atividades · avaliar nutrição/perda')).join('')||'<div class="mini-empty">Sem leads em 4+.</div>';
  return `<div class="mgmt-section cadence-wide"><h4>Cobertura de cadência · base sem resposta</h4>
    <div class="focus-safe"><b>Objetivo:</b> deixar claro quem está em cada etapa do disparo. 1 atividade → 2º contato; 2 atividades → 3º contato; 3 atividades → 4º toque/despedida; 4+ → nutrição/perda. Read-only — não dispara WhatsApp.</div>
    <div class="cad-chips">${chips}</div>
    <div class="mgmt-grid"><div class="mgmt-card"><b>${m.stress||0}</b><span>leads para estressar agora (1–3 atividades)</span></div><div class="mgmt-card"><b>${total}</b><span>base sem resposta no escopo</span></div></div>
    ${cadenceBoard(board, cb)}
    <div class="cad-edge-grid"><div class="focus-section"><h4>0 atividades · iniciar D0 <em>${cb['0']||0}</em></h4>${zeroRows}</div><div class="focus-section"><h4>4+ atividades · nutrir/perder <em>${cb['4+']||0}</em></h4>${nutriRows}</div></div>
    <h4 style="margin-top:12px">Por SDR e atividade</h4>${topRows(m.cadenceByOwner,total)}
  </div>`;
}
function resetPipeFilters(){ pipeCallFilter='all'; pipeWhatsFilter='all'; pipeBucketFilter='all'; }
function pipeSimpleSummary(){
  const p=pf(), st=pfStats(), b0=pfBucket('0').count||0, b1=pfBucket('1').count||0, b2=pfBucket('2').count||0, b3=pfBucket('3').count||0, b4=pfBucket('4+').count||0;
  const mid=b1+b2+b3;
  return `<div class="pipe-summary">
    <div class="pipe-sum" onclick="openPipeModal('all')" onkeydown="pipeCardKey(event,'all')" role="button" tabindex="0"><b>${st.total||p.total||0}</b><span>negócios no pipe</span><small>abrir negócios</small></div>
    <div class="pipe-sum zero" onclick="openPipeModal('0')" onkeydown="pipeCardKey(event,'0')" role="button" tabindex="0"><b>${b0}</b><span>0 atividades</span><small>abrir negócios</small></div>
    <div class="pipe-sum mid" onclick="openPipeModal('1-3')" onkeydown="pipeCardKey(event,'1-3')" role="button" tabindex="0"><b>${mid}</b><span>1–3 atividades</span><small>abrir negócios</small></div>
    <div class="pipe-sum done" onclick="openPipeModal('4+')" onkeydown="pipeCardKey(event,'4+')" role="button" tabindex="0"><b>${b4}</b><span>4+ atividades</span><small>abrir negócios</small></div>
  </div>`;
}
function pipeModalRows(bucket){
  let rows=pfAllDeals().slice();
  if(bucket==='0') rows=rows.filter(r=>String(r.bucket)==='0');
  else if(bucket==='1-3') rows=rows.filter(r=>['1','2','3'].includes(String(r.bucket)));
  else if(bucket==='4+') rows=rows.filter(r=>String(r.bucket)==='4+');
  return rows.sort((a,b)=>String(a.stageLabel||'').localeCompare(String(b.stageLabel||''),'pt-BR') || ((a.activityCount||0)-(b.activityCount||0)) || String(a.owner||'').localeCompare(String(b.owner||''),'pt-BR'));
}
function pipeBucketTitle(bucket){
  return ({'all':'Todos os negócios do pipe','0':'Negócios com 0 atividades','1-3':'Negócios com 1–3 atividades','4+':'Negócios com 4+ atividades'})[bucket]||'Negócios do card';
}
function actKindLabel(a){
  if(a.isCall) return 'Ligação';
  if(a.isWhatsApp) return 'WhatsApp';
  if(a.kind==='note') return 'Nota';
  if(a.kind==='call') return 'Ligação';
  return 'Tarefa';
}
function fmtActDate(ts){
  if(!ts) return 'sem data';
  try{return new Date(ts*1000).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo',day:'2-digit',month:'2-digit',year:'2-digit',hour:'2-digit',minute:'2-digit'});}catch(e){return 'sem data';}
}
function actStatusLabel(status){
  const s=String(status||'').toUpperCase();
  return ({NOT_STARTED:'não iniciada',COMPLETED:'concluída',IN_PROGRESS:'em andamento',WAITING:'aguardando',DEFERRED:'adiada'})[s] || String(status||'');
}
function pipeActivityRow(a, upcoming=false){
  return `<div class="pipe-act ${upcoming?'pipe-act-upcoming':''}"><div class="pipe-act-time">${esc(fmtActDate(a.ts))}</div><div class="pipe-act-label">${esc(a.label||a.type||'Atividade HubSpot')}${a.status?`<br><span class="fm">status: ${esc(actStatusLabel(a.status))}</span>`:''}</div><div class="pipe-act-kind">${esc(actKindLabel(a))}</div></div>`;
}
function pipeActivitiesHtml(acts){
  if(!acts.length) return '<div class="pipe-empty-acts">Esse negócio está no card 0 atividades: não há tarefa, nota ou ligação associada ao deal no HubSpot.</div>';
  const now=Date.now()/1000;
  const upcoming=acts.filter(a=>String(a.status||'').toUpperCase()==='NOT_STARTED' || (a.ts||0)>now).sort((a,b)=>(a.ts||0)-(b.ts||0));
  const history=acts.filter(a=>!upcoming.includes(a)).sort((a,b)=>(b.ts||0)-(a.ts||0));
  const parts=[];
  if(upcoming.length) parts.push(`<div class="pipe-act-group"><div class="pipe-act-group-title">Próximas atividades</div>${upcoming.map(a=>pipeActivityRow(a,true)).join('')}</div>`);
  if(history.length) parts.push(`<div class="pipe-act-group"><div class="pipe-act-group-title">Histórico realizado</div>${history.map(a=>pipeActivityRow(a,false)).join('')}</div>`);
  return parts.join('');
}

function togglePipeDeal(dealId){
  const row=document.querySelector(`.pipe-lead-row[data-deal="${CSS.escape(String(dealId))}"]`);
  if(row){
    const open=row.classList.toggle('open');
    const btn=row.querySelector('[data-act-toggle]');
    if(btn) btn.textContent=open?'Ocultar':'Ver atividades';
  }
}
function pipeLeadModalRow(r){
  const tc=r.typeCounts||{};
  const acts=(r.activities||[]).slice().sort((a,b)=>(b.ts||0)-(a.ts||0));
  const last=r.lastActivity?` · última: ${esc(r.lastActivity.label||r.lastActivity.type||'atividade')}`:'';
  const actsHtml=pipeActivitiesHtml(acts);
  return `<div class="pipe-lead-row" data-deal="${esc(r.dealId||'')}"><div class="pipe-lead-top"><div class="pipe-lead-main" onclick="togglePipeDeal('${esc(r.dealId||'')}')"><div class="fn">${esc(r.dealName||'Negócio sem nome')}</div><div class="fm">${esc(r.stageLabel||'Sem etapa')} · ${esc(r.owner||'Sem owner')} · ${r.activityCount||0} atividade(s) · ${tc.call||0} lig. · ${tc.whatsapp||0} WhatsApp${last}</div><div class="badges"><span class="atype ${r.hasCall?'on':'off'}">${r.hasCall?'com ligação':'sem ligação'}</span><span class="atype ${r.hasWhatsApp?'on':'off'}">${r.hasWhatsApp?'com WhatsApp':'sem WhatsApp'}</span></div></div><div class="pipe-lead-actions"><button data-act-toggle onclick="togglePipeDeal('${esc(r.dealId||'')}')">Ver atividades</button><a target="_blank" rel="noopener" href="${esc(r.url||'#')}">HubSpot</a></div></div><div class="pipe-acts">${actsHtml}</div></div>`;
}

function filterPipeModalList(){
  const q=(document.getElementById('pipeModalSearch')?.value||'').toLowerCase().trim();
  const bucket=document.getElementById('pipeModal')?.dataset.bucket||'all';
  let rows=pipeModalRows(bucket);
  if(q) rows=rows.filter(r=>[r.dealName,r.stageLabel,r.owner,String(r.activityCount||0)].join(' ').toLowerCase().includes(q));
  const list=document.getElementById('pipeModalList'), count=document.getElementById('pipeModalCount');
  if(count) count.textContent=`${rows.length} negócio${rows.length===1?'':'s'}`;
  if(list) list.innerHTML=rows.map(pipeLeadModalRow).join('')||'<div class="mini-empty">Nenhum negócio neste card.</div>';
}
function openPipeModal(bucket='all'){
  const modal=document.getElementById('pipeModal'); if(!modal) return;
  modal.dataset.bucket=bucket;
  const rows=pipeModalRows(bucket);
  document.getElementById('pipeModalTitle').textContent=pipeBucketTitle(bucket);
  document.getElementById('pipeModalSub').textContent=`${rows.length} negócio${rows.length===1?'':'s'} para validar`;
  document.getElementById('pipeModalBody').innerHTML=`<div class="pipe-modal-toolbar"><span id="pipeModalCount">${rows.length} negócio${rows.length===1?'':'s'}</span><input id="pipeModalSearch" placeholder="Buscar na lista…" oninput="filterPipeModalList()"></div><div class="pipe-modal-list" id="pipeModalList"></div>`;
  modal.hidden=false;
  filterPipeModalList();
  setTimeout(()=>document.getElementById('pipeModalSearch')?.focus(),40);
}
function closePipeModal(){const m=document.getElementById('pipeModal'); if(m) m.hidden=true;}
function pipeCardKey(e,bucket){if(e.key==='Enter'||e.key===' '){e.preventDefault();openPipeModal(bucket);}}
function pipeSimpleHeader(title){
  const p=pf(), total=p.total||pfStats().total||0;
  return `<div class="pipe-simple-head"><div><b>${esc(title)}</b><span>Deals das etapas comerciais acompanhados por quantidade de atividades registradas no HubSpot. A leitura é simples: etapa do pipe na linha, quantidade de atividades nas colunas.</span></div><div class="stamp">${total} negócios · HubSpot</div></div>`;
}
function pipeStateNotice(){
  if(pipelineFocusLoading && !pipelineFocus) return `<div class="pipe-skeleton"><div class="pipe-skel"></div><div class="pipe-skel"></div><div class="pipe-skel"></div><div class="pipe-skel"></div></div><div class="pipe-state"><b>Carregando HubSpot…</b>Buscando negócios, etapas e atividades associadas aos deals.</div>`;
  const p=pf();
  if(p && p.error) return `<div class="pipe-state"><b>Não foi possível carregar o HubSpot</b>${esc(p.error)}<br><button onclick="pipelineFocus=null; loadPipelineFocus()">Tentar novamente</button></div>`;
  if(p && p.configured===false) return `<div class="pipe-state"><b>HubSpot não configurado</b>${esc(p.error||'Sem credencial ativa para consultar o pipe.')}<br><button onclick="loadPipelineFocus()">Tentar novamente</button></div>`;
  return '';
}
function introConv(){return (pf().introConversion)||{active:0,introduced:0,base:0,rate:0,rows:[],targetStageLabel:'Introdução',period:'mês atual'}}
function pct(n){return `${Number(n||0).toLocaleString('pt-BR',{maximumFractionDigits:1})}%`}
function perfTopIntroductions(rows){
  rows=(rows||[]).filter(r=>(r.introduced||0)>0 || (r.active||0)>0);
  if(!rows.length) return {owner:'—',rate:0,introduced:0};
  return rows.slice().sort((a,b)=>(b.introduced||0)-(a.introduced||0)||(b.rate||0)-(a.rate||0))[0];
}
function performanceDashboard(){
  const c=introConv(), st=pfStats(), top=perfTopIntroductions(c.rows||[]), active=c.active||st.total||0, intro=c.introduced||0, base=c.base||active+intro;
  const max=Math.max(active,intro,1);
  const ownerRows=(c.rows||[]).filter(r=>r.owner&&!/^\d+$/.test(String(r.owner))).sort((a,b)=>(b.introduced||0)-(a.introduced||0)||(b.rate||0)-(a.rate||0)).slice(0,6);
  return `<div class="perf-hero">
    <div class="perf-title"><b>Performance SDR → Introdução</b><span>Meta da gestão: entender quantos negócios que entram nas etapas comerciais estão evoluindo para <b>Introdução</b>, que é a passagem real para o vendedor. Fonte: HubSpot, read-only.</span>
      <div class="perf-kpis">
        <div class="perf-kpi"><b>${active}</b><span>deals nas etapas SDR</span></div>
        <div class="perf-kpi"><b>${intro}</b><span>entraram em Introdução no mês</span></div>
        <div class="perf-kpi"><b>${c.createdThisMonth||0}</b><span>criadas no mês e foram para Introdução</span></div>
        <div class="perf-kpi"><b>${esc(top.owner||'—')}</b><span>mais Introduções · ${top.introduced||0}</span></div>
      </div>
    </div>
    <div class="perf-chart"><h4>Funil do mês</h4>
      <div class="funnel-row"><span>Entrada SDR</span><div class="funnel-track"><i class="funnel-fill" style="width:${Math.max(6,Math.round(active/max*100))}%"></i></div><b>${active}</b></div>
      <div class="funnel-row"><span>Introdução</span><div class="funnel-track"><i class="funnel-fill" style="width:${Math.max(intro?6:0,Math.round(intro/max*100))}%"></i></div><b>${intro}</b></div>
      <div class="perf-note">${esc(c.note||'Taxa estimada com base no mês atual.')} <b>${c.createdBefore||0}</b> criadas antes do mês · <b>${c.createdThisMonth||0}</b> criadas no mês.</div>
    </div>
  </div>
  <div class="perf-board"><h4>Performance por SDR</h4>
    ${ownerRows.map(r=>`<div class="perf-owner"><b>${esc(r.owner)}</b><small>${r.introduced||0} intro (${r.createdBefore||0} antigas / ${r.createdThisMonth||0} novas) · ${r.active||0} em SDR</small><div class="perf-bar"><i style="width:${Math.min(100,Math.max(0,r.rate||0))}%"></i></div><strong>${pct(r.rate||0)}</strong></div>`).join('')||'<div class="mini-empty">Sem dados de owner para este mês.</div>'}
  </div>`;
}

function dispatchColor(i){return ['#CDEB00','#1F3D2B','#6B7C00','#8AA000','#D7B56D','#7BA05B','#B6C74A','#455A35'][i%8]}
function setDispatchChip(port){dispatchSelectedChip=(dispatchSelectedChip===String(port)?'':String(port)); drawCards()}
function setDispatchDay(day){dispatchSelectedDay=(dispatchSelectedDay===String(day)?'':String(day)); drawCards()}
function previewDispatchDay(day){if(dispatchSelectedDay!==String(day)){dispatchSelectedDay=String(day); drawCards()}}
function dispatchDayObj(day){return ((dispatchStats&&dispatchStats.days)||[]).find(d=>d.date===day)||null}
function closeDispatchModal(){const m=document.getElementById('dispatchModal'); if(m) m.hidden=true}
function dispatchEventRow(ev){
  const meta=[ev.time,ev.chip,ev.sdr?('SDR '+ev.sdr):'',ev.phone,ev.type].filter(Boolean).join(' · ');
  const msg=ev.message||'Mensagem sem texto no ledger; registro de envio operacional.';
  const link=ev.link||'#';
  return `<div class="dispatch-msg-row"><div><h4>${esc(ev.empresa||ev.contact||ev.to||'Envio')}</h4><small>${esc(meta)}</small><p>${esc(msg)}</p></div><a href="${esc(link)}" target="_blank" rel="noopener noreferrer">Abrir conversa</a></div>`;
}
function openDispatchModal(day, port=''){
  const d=dispatchDayObj(day); if(!d) return;
  const ports=port?[String(port)]:Object.keys(d.details||{});
  const rows=[]; ports.forEach(p=>{((d.details||{})[String(p)]||[]).forEach(ev=>rows.push(ev))});
  rows.sort((a,b)=>String(a.time||'').localeCompare(String(b.time||'')));
  const chip=(dispatchStats&&dispatchStats.chips||[]).find(c=>String(c.port)===String(port));
  document.getElementById('dispatchModalTitle').textContent=`${rows.length} disparo${rows.length===1?'':'s'} · ${day}`;
  document.getElementById('dispatchModalSub').textContent=chip?`${chip.label} · porta ${chip.port}`:'Todos os chips do dia';
  document.getElementById('dispatchModalBody').innerHTML=`<div class="dispatch-modal-list">${rows.map(dispatchEventRow).join('')||'<div class="mini-empty">Sem registros neste recorte.</div>'}</div>`;
  document.getElementById('dispatchModal').hidden=false;
}
function dispatchStatsBlock(){
  const ds=dispatchStats;
  if(dispatchStatsLoading && !ds) return `<div class="dispatch-board"><div class="dispatch-head"><div><b>Disparos WhatsApp por dia</b><span>Carregando ledger de envios…</span></div></div></div>`;
  if(!ds) return `<div class="dispatch-board"><div class="dispatch-head"><div><b>Disparos WhatsApp por dia</b><span>Sem dados carregados ainda.</span></div><button class="bb-btn" onclick="loadDispatchStats(true)">Carregar</button></div></div>`;
  if(ds.error) return `<div class="dispatch-board"><div class="dispatch-head"><div><b>Disparos WhatsApp por dia</b><span>${esc(ds.error)}</span></div><button class="bb-btn" onclick="loadDispatchStats(true)">Tentar de novo</button></div></div>`;
  const chips=(ds.chips||[]).slice(0,8);
  const max=Math.max(1,...(ds.days||[]).map(d=>d.total||0));
  const fmtDay=d=>{try{return new Date(d+'T12:00:00').toLocaleDateString('pt-BR',{day:'2-digit',month:'2-digit'})}catch(e){return d}};
  const selectedDay=(ds.days||[]).find(d=>d.date===dispatchSelectedDay)||[...(ds.days||[])].reverse().find(d=>(d.total||0)>0)||(ds.days||[])[0]||{date:'',chips:{},total:0};
  const cols=(ds.days||[]).map(day=>{
    const h=Math.max(day.total?8:2,Math.round((day.total||0)/max*190));
    const segs=chips.map((c,i)=>{const n=(day.chips||{})[String(c.port)]||0; if(!n) return ''; const dim=dispatchSelectedChip&&dispatchSelectedChip!==String(c.port); return `<i class="dispatch-seg ${dim?'dim':''}" title="${esc(c.label)} · ${n}" style="height:${Math.max(4,Math.round(n/(day.total||1)*100))}%;background:${dispatchColor(i)}"></i>`}).join('');
    return `<button class="dispatch-col ${dispatchSelectedDay===day.date?'on':''}" onmouseenter="previewDispatchDay('${esc(day.date)}')" onclick="openDispatchModal('${esc(day.date)}',dispatchSelectedChip)" title="${esc(fmtDay(day.date))} · ${day.total||0} mensagens · clique para ver detalhes"><span class="n">${day.total||0}</span><div class="dispatch-stack" style="--h:${h}px">${segs}</div><span class="d">${esc(fmtDay(day.date))}</span></button>`;
  }).join('');
  const legend=chips.map((c,i)=>`<button class="dispatch-chip ${dispatchSelectedChip===String(c.port)?'on':''}" onclick="setDispatchChip('${c.port}')"><i class="dispatch-dot" style="background:${dispatchColor(i)}"></i>${esc(c.label||('Chip '+c.port))}</button>`).join('');
  const detailLines=chips.map((c,i)=>{const n=(selectedDay.chips||{})[String(c.port)]||0; if(!n) return ''; return `<button class="line" onclick="openDispatchModal('${esc(selectedDay.date)}','${c.port}')"><i class="dispatch-dot" style="background:${dispatchColor(i)}"></i>${esc(c.label)}: <b>${n}</b></button>`}).join('')||'<span class="line">Sem disparos neste dia.</span>';
  const rank=chips.map((c,i)=>`<div class="r ${dispatchSelectedChip===String(c.port)?'on':''}" onclick="setDispatchChip('${c.port}')"><b>${c.total||0}</b><span><i class="dispatch-dot" style="display:inline-block;background:${dispatchColor(i)}"></i> ${esc(c.label||('Chip '+c.port))} · porta ${c.port}</span></div>`).join('');
  return `<div class="dispatch-board"><div class="dispatch-head"><div><b>Disparos WhatsApp por dia · por chip</b><span>Colunas verticais empilhadas. Passe o mouse para prévia; clique na coluna ou no total do chip para abrir os envios com mensagem e link. Fonte: ${esc(ds.source||'ledger')} · últimos ${ds.periodDays||14} dias · ${esc(ds.scope||'')}</span></div><div class="dispatch-total">${ds.total||0} mensagens</div></div><div class="dispatch-chart">${cols||'<div class="mini-empty">Sem disparos no período.</div>'}</div><div class="dispatch-legend">${legend}</div><div class="dispatch-detail"><b>${esc(fmtDay(selectedDay.date||''))} · ${selectedDay.total||0} mensagens</b><div class="lines">${detailLines}</div></div><div class="dispatch-rank">${rank}</div></div>`;
}

function drawManagement(){
  resetPipeFilters();
  const el=document.getElementById('cards'), p=pf(), st=pfStats(), c=introConv();
  const scope=(me&&(me.view_all||me.admin))?'consolidado permitido':'somente sua carteira';
  document.getElementById('queueTitle').textContent='Gestão';
  document.getElementById('queueCount').textContent=`${c.introduced||0} Introduções no mês · ${pct(c.rate||0)} avanço estimado · ${scope}`;
  const state=pipeStateNotice();
  el.innerHTML=`<div class="mgmt-panel">
    ${pipeSimpleHeader('Dashboard de evolução para Introdução')}
    ${dispatchStatsBlock()}
    ${state || `${performanceDashboard()}<div class="perf-secondary">${pfStageMatrix()}<details class="mgmt-section"><summary style="cursor:pointer;font-weight:800;font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)">Detalhe por atividade</summary>${pipeSimpleSummary()}<div class="pipe-note"><b>Leitura:</b> 0 atividades = sem follow-up no HubSpot. 1–3 = em cadência. 4+ = já muito tocado, revisar prioridade.</div></details></div>`}
  </div>`;
}

function pipelineSummaryBlock(){
  const p=(managerOverview&&managerOverview.pipeline)||null;
  if(!p) return `<div class="focus-safe"><b>Pipeline HubSpot:</b> carregando contagem por etapa…</div>`;
  const rows=p.rows||[];
  return `<div class="mgmt-section"><h4>Pipeline HubSpot · ${esc(p.scope||'escopo permitido')}</h4>
    <div class="mgmt-grid"><div class="mgmt-card"><b>${p.total||0}</b><span>negócios nas etapas de demanda</span></div></div>
    ${rows.map(r=>`<div class="mgmt-row"><span>${esc(r.label)}</span><em>${r.count||0}</em></div>`).join('')||'<div class="mini-empty">Sem dados do HubSpot agora.</div>'}
  </div>`;
}
function pf(){return pipelineFocus||{total:0,activityBuckets:{},stageRows:[],ownerRows:[],deals:[]}}
function pfAllDeals(){return (pf().deals||[])}
function pfFilterActive(){return pipeCallFilter!=='all'||pipeWhatsFilter!=='all'||pipeBucketFilter!=='all'}
function pfDealPass(r){
  if(pipeCallFilter==='with'&&!r.hasCall) return false;
  if(pipeCallFilter==='without'&&r.hasCall) return false;
  if(pipeWhatsFilter==='with'&&!r.hasWhatsApp) return false;
  if(pipeWhatsFilter==='without'&&r.hasWhatsApp) return false;
  if(pipeBucketFilter==='1-3' && !['1','2','3'].includes(String(r.bucket))) return false;
  if(['0','1','2','3','4+'].includes(pipeBucketFilter) && String(r.bucket)!==pipeBucketFilter) return false;
  return true;
}
function pfDeals(){const rows=pfAllDeals(); return rows.length?rows.filter(pfDealPass):[]}
function pfStats(){
  const rows=pfDeals(), buckets={'0':[],'1':[],'2':[],'3':[],'4+':[]};
  rows.forEach(r=>{const k=r.bucket||'0'; (buckets[k]=buckets[k]||[]).push(r)});
  return {total:rows.length, activityBuckets:Object.fromEntries(Object.entries(buckets).map(([k,v])=>[k,{count:v.length,sample:v.slice(0,8)}])), rows};
}
function pfBucket(k){
  const st=pfStats();
  return ((st.activityBuckets||{})[k]||{count:0,sample:[]});
}
function pfFilterCount(callMode, whatsMode){
  const oldC=pipeCallFilter, oldW=pipeWhatsFilter; pipeCallFilter=callMode; pipeWhatsFilter=whatsMode;
  const n=pfDeals().length; pipeCallFilter=oldC; pipeWhatsFilter=oldW; return n;
}
function setPipeFilter(kind,val){
  if(kind==='call') pipeCallFilter=val||'all';
  if(kind==='whats') pipeWhatsFilter=val||'all';
  if(kind==='bucket') pipeBucketFilter=val||'all';
  drawCards();
}
function setPipeFilters(callMode,whatsMode,bucketMode){
  pipeCallFilter=callMode||'all'; pipeWhatsFilter=whatsMode||'all'; pipeBucketFilter=bucketMode||'all'; drawCards();
}
function clearPipeFilters(){ setPipeFilters('all','all','all'); }
function pipeFilterPill(kind,val,label,count){
  const cur=kind==='call'?pipeCallFilter:(kind==='whats'?pipeWhatsFilter:pipeBucketFilter);
  return `<button class="${cur===val?'on':''}" onclick="setPipeFilter('${kind}','${val}')"><b>${count}</b>${esc(label)}</button>`;
}
function pipeFiltersBlock(){
  const all=pfAllDeals();
  if(!all.length) return `<div class="pipe-filterbar"><span>Filtros carregam junto com o HubSpot…</span></div>`;
  const callBase=(w)=>all.filter(r=>(w==='all'||(w==='with'?r.hasWhatsApp:!r.hasWhatsApp))).length;
  const callWith=(w)=>all.filter(r=>(w==='all'||(w==='with'?r.hasWhatsApp:!r.hasWhatsApp)) && r.hasCall).length;
  const callWithout=(w)=>all.filter(r=>(w==='all'||(w==='with'?r.hasWhatsApp:!r.hasWhatsApp)) && !r.hasCall).length;
  const whatsBase=(c)=>all.filter(r=>(c==='all'||(c==='with'?r.hasCall:!r.hasCall))).length;
  const whatsWith=(c)=>all.filter(r=>(c==='all'||(c==='with'?r.hasCall:!r.hasCall)) && r.hasWhatsApp).length;
  const whatsWithout=(c)=>all.filter(r=>(c==='all'||(c==='with'?r.hasCall:!r.hasCall)) && !r.hasWhatsApp).length;
  const title=pfFilterActive()?`Mostrando ${pfDeals().length} de ${all.length} negócios`:`Mostrando todos os ${all.length} negócios`;
  const countFor=(c,w,b)=>all.filter(r=>{
    const oldC=pipeCallFilter, oldW=pipeWhatsFilter, oldB=pipeBucketFilter;
    pipeCallFilter=c; pipeWhatsFilter=w; pipeBucketFilter=b;
    const ok=pfDealPass(r); pipeCallFilter=oldC; pipeWhatsFilter=oldW; pipeBucketFilter=oldB; return ok;
  }).length;
  return `<div class="pipe-filterbar"><div><b>Filtros de atividade HubSpot</b><span>${title}. Filtra a própria análise, as matrizes e a lista abaixo. Fonte: tasks, notas e ligações associadas ao negócio.</span></div>
    <div class="pf-group"><em>Ligação</em>${pipeFilterPill('call','all','Todas',callBase(pipeWhatsFilter))}${pipeFilterPill('call','with','Com ligação',callWith(pipeWhatsFilter))}${pipeFilterPill('call','without','Sem ligação',callWithout(pipeWhatsFilter))}</div>
    <div class="pf-group"><em>WhatsApp</em>${pipeFilterPill('whats','all','Todos',whatsBase(pipeCallFilter))}${pipeFilterPill('whats','with','Com WhatsApp',whatsWith(pipeCallFilter))}${pipeFilterPill('whats','without','Sem WhatsApp',whatsWithout(pipeCallFilter))}</div>
    <div class="pf-group"><em>Atividades</em>${pipeFilterPill('bucket','all','Todas',countFor(pipeCallFilter,pipeWhatsFilter,'all'))}${pipeFilterPill('bucket','0','0',countFor(pipeCallFilter,pipeWhatsFilter,'0'))}${pipeFilterPill('bucket','1-3','1–3',countFor(pipeCallFilter,pipeWhatsFilter,'1-3'))}${pipeFilterPill('bucket','4+','4+',countFor(pipeCallFilter,pipeWhatsFilter,'4+'))}${pfFilterActive()?'<button class="clear" onclick="clearPipeFilters()">Limpar</button>':''}</div>
  </div>`;
}
function pfDealRow(r){
  const last=r.lastActivity?` · última: ${esc(r.lastActivity.label||r.lastActivity.type||'atividade')}`:'';
  const tc=r.typeCounts||{};
  const badges=`<span class="atype ${r.hasCall?'on':'off'}">${r.hasCall?'com ligação':'sem ligação'}</span><span class="atype ${r.hasWhatsApp?'on':'off'}">${r.hasWhatsApp?'com WhatsApp':'sem WhatsApp'}</span>`;
  return `<div class="focus-row"><div><div class="fn">${esc(r.dealName||'Negócio sem nome')}</div><div class="fm">${esc(r.stageLabel||'')} · ${esc(r.owner||'Sem owner')} · ${r.activityCount||0} atividade(s) HubSpot · ${tc.call||0} lig. · ${tc.whatsapp||0} WhatsApp${last}</div><div class="activity-tags">${badges}</div></div><div class="fa"><a class="bb-btn" target="_blank" rel="noopener" href="${esc(r.url||'#')}">HubSpot</a></div></div>`;
}
function pfMatrixRows(kind){
  const rows=pfDeals();
  if(!rows.length && !pfAllDeals().length) return kind==='stage'?(pf().stageRows||[]):(pf().ownerRows||[]).filter(r=>!/^\d+$/.test(String(r.owner||r.ownerId||'')));
  const map=new Map();
  rows.forEach(r=>{
    if(kind==='owner' && /^\d+$/.test(String(r.owner||r.ownerId||''))) return;
    const id=kind==='stage'?(r.stageId||r.stageLabel||'sem_stage'):(r.ownerId||r.owner||'sem_owner');
    const label=kind==='stage'?(r.stageLabel||r.stageId||'Sem etapa'):(r.owner||'Sem owner');
    if(!map.has(id)) map.set(id,{stageId:kind==='stage'?id:'',ownerId:kind==='owner'?id:'',label,owner:label,total:0,buckets:{'0':0,'1':0,'2':0,'3':0,'4+':0}});
    const o=map.get(id); o.total++; const b=r.bucket||'0'; o.buckets[b]=(o.buckets[b]||0)+1;
  });
  return [...map.values()].sort((a,b)=>(b.total||0)-(a.total||0));
}
function pfStageMatrix(){
  const rows=pfMatrixRows('stage');
  const empty=pipelineFocusLoading?'Carregando HubSpot…':'Nenhum negócio nas etapas comerciais deste escopo.';
  return `<div class="mgmt-section"><h4>Etapas do pipe x atividades HubSpot ${pfFilterActive()?'<em class="filter-note">filtrado</em>':''}</h4>
    <div class="pipe-table"><div class="pipe-tr head"><span>Etapa</span><b>Total</b><b>0</b><b>1</b><b>2</b><b>3</b><b>4+</b></div>
    ${rows.map(r=>`<div class="pipe-tr"><span>${esc(r.label)}</span><b>${r.total||0}</b><em>${(r.buckets||{})['0']||0}</em><em>${(r.buckets||{})['1']||0}</em><em>${(r.buckets||{})['2']||0}</em><em>${(r.buckets||{})['3']||0}</em><em>${(r.buckets||{})['4+']||0}</em></div>`).join('')||`<div class="mini-empty">${empty}</div>`}
    </div></div>`;
}
function pfOwnerMatrix(inner=false){
  const rows=pfMatrixRows('owner').slice(0,8);
  const body=`<h4>SDR x atividades HubSpot ${pfFilterActive()?'<em class="filter-note">filtrado</em>':''}</h4>
    <div class="pipe-table"><div class="pipe-tr head"><span>Proprietário</span><b>Total</b><b>0</b><b>1</b><b>2</b><b>3</b><b>4+</b></div>
    ${rows.map(r=>`<div class="pipe-tr"><span>${esc(r.owner||'Sem owner')}</span><b>${r.total||0}</b><em>${(r.buckets||{})['0']||0}</em><em>${(r.buckets||{})['1']||0}</em><em>${(r.buckets||{})['2']||0}</em><em>${(r.buckets||{})['3']||0}</em><em>${(r.buckets||{})['4+']||0}</em></div>`).join('')||'<div class="mini-empty">Nenhum SDR neste escopo.</div>'}
    </div>`;
  return inner?`<div style="margin-top:10px">${body}</div>`:`<div class="mgmt-section">${body}</div>`;
}
function pfActivityCard(k,title,next){
  const b=pfBucket(k);
  return `<div class="focus-card ${pipeSampleBucket===k?'sample-on':''}"><b>${b.count||0}</b><span>${esc(title)}</span><small>${esc(next)}</small><button onclick="showPipeBucket('${esc(k)}')">Ver exemplos</button></div>`;
}
function pfInsightCard(cls,count,title,desc,callMode,whatsMode,bucketMode){
  const on=(pipeCallFilter===(callMode||'all') && pipeWhatsFilter===(whatsMode||'all') && pipeBucketFilter===(bucketMode||'all'));
  return `<div class="focus-card insight ${cls||''} ${on?'sample-on':''}" onclick="setPipeFilters('${callMode||'all'}','${whatsMode||'all'}','${bucketMode||'all'}')"><b>${count||0}</b><span>${esc(title)}</span><small>${esc(desc)}</small><button>${on?'Filtro ativo':'Filtrar'}</button></div>`;
}
function pipeAnalysisCards(){
  const all=pfAllDeals();
  const rows=pfDeals();
  const noCall=all.filter(r=>!r.hasCall).length, withCall=all.filter(r=>r.hasCall).length;
  const noWhats=all.filter(r=>!r.hasWhatsApp).length, withWhats=all.filter(r=>r.hasWhatsApp).length;
  const gapCall=all.filter(r=>['1','2','3'].includes(String(r.bucket))&&!r.hasCall).length;
  const gapWhats=all.filter(r=>['1','2','3'].includes(String(r.bucket))&&!r.hasWhatsApp).length;
  const fourPlus=rows.filter(r=>String(r.bucket)==='4+').length;
  return `<div class="focus-grid analysis-grid">
    <div class="focus-card primary-metric"><b>${rows.length||0}</b><span>${pfFilterActive()?'negócios no filtro':'negócios no pipe'}</span><small>Use os filtros de ligação/WhatsApp para entender onde o follow-up está falhando.</small><button class="primary" onclick="clearPipeFilters()">Ver tudo</button></div>
    ${pfInsightCard('warn',noCall,'Sem ligação','Negócios sem nenhuma ligação registrada no HubSpot. Bom corte para cobrar cadência por telefone.','without','all','all')}
    ${pfInsightCard('',withCall,'Com ligação','Negócios que já têm ligação registrada. Use para medir cobertura telefônica.','with','all','all')}
    ${pfInsightCard('warn',noWhats,'Sem WhatsApp','Negócios sem atividade de WhatsApp registrada no HubSpot. Bom corte para achar follow-up ausente.','all','without','all')}
    ${pfInsightCard('',withWhats,'Com WhatsApp','Negócios com tarefa/nota de WhatsApp associada ao deal.','all','with','all')}
    ${pfInsightCard('hot',gapCall,'1–3 atividades sem ligação','Leads em follow-up que ainda não tiveram ligação. Prioridade comercial clara.','without','all','1-3')}
    ${pfInsightCard('hot',gapWhats,'1–3 atividades sem WhatsApp','Leads em follow-up sem registro de WhatsApp no HubSpot. Corrigir execução ou registro.','all','without','1-3')}
    <div class="focus-card"><b>${fourPlus}</b><span>4+ atividades no filtro</span><small>Já foram muito tocados; revisar nutrição, perda ou retirada da prioridade SDR.</small><button onclick="showPipeBucket('4+')">Ver lista</button></div>
  </div>`;
}
function pipeSamplesBlock(){
  const rows=pfDeals().slice(0,14);
  const title=pfFilterActive()?'Negócios do filtro atual':'Amostra do pipe para auditoria';
  const hint=pfFilterActive()?'A lista abaixo já respeita ligação/WhatsApp/faixa de atividades selecionados.':'Clique nos filtros acima para transformar esta lista em uma fila de auditoria.';
  return `<div id="pipeSamples"><div class="focus-section"><h4>${title} <em>${pfDeals().length}</em></h4><div class="mini-hint">${esc(hint)}</div>${rows.map(pfDealRow).join('')||'<div class="mini-empty">Sem negócios nesse corte com os filtros atuais.</div>'}</div></div>`;
}
function showPipeBucket(k){
  pipeBucketFilter=k||'all'; drawCards();
}

// Foco SDR: pipeline HubSpot só como resumo compacto/secundário (colapsável), nunca como bloco dominante.
function pipelineCompactBlock(){
  const p=(managerOverview&&managerOverview.pipeline)||null;
  if(!p) return `<div class="pipe-compact"><summary><span class="pc-k">Pipeline HubSpot</span><span class="pc-hint">carregando contagem por etapa…</span></summary></div>`;
  const rows=(p.rows||[]).slice(0,6);
  return `<details class="pipe-compact"><summary><span class="pc-k">Pipeline HubSpot</span><span class="pc-v">${p.total||0} negócios</span><span class="pc-hint">${esc(p.scope||'escopo permitido')} · toque para detalhar</span></summary>
    <div class="pc-rows">${rows.map(r=>`<span class="pc-row"><b>${r.count||0}</b> ${esc(r.label)}</span>`).join('')||'<span class="pc-row">Sem dados do HubSpot agora.</span>'}</div>
  </details>`;
}

function ageDays(ts){return Math.floor((Date.now()/1000-(+ts||0))/86400)}
function actionableConvs(){return convs.filter(c=>!c.readOnlyInstitutional)}
function focusBuckets(){
  const base=actionableConvs();
  const pipe=(managerOverview&&managerOverview.pipeline)||{};
  const pipeTotal=+pipe.total||0;
  const pipeRows=pipe.rows||[];
  const responder=base.filter(c=>hasActionableLeadReply(c)).sort((a,b)=>(+b.lastIncomingTime||0)-(+a.lastIncomingTime||0));
  const semAtividade=base.filter(c=>!hasActionableLeadReply(c) && (+c.lastTime||0)>0 && ageDays(c.lastTime)>=5).sort((a,b)=>(+a.lastTime||0)-(+b.lastTime||0));
  const aguardando=base.filter(c=>(+c.responses||0)===0 && !hasActionableLeadReply(c) && (+c.lastOutgoingTime||+c.lastTime||0)>0 && (Date.now()/1000-(+c.lastOutgoingTime||+c.lastTime||0))>24*3600).sort((a,b)=>(+a.lastOutgoingTime||+a.lastTime||0)-(+b.lastOutgoingTime||+b.lastTime||0));
  const audios=base.filter(c=>+(c.audioPending||0)>0 || c.audioTranscriptText).sort((a,b)=>(+b.lastTime||0)-(+a.lastTime||0));
  const reunioes=base.filter(c=>isMeeting(c)).sort((a,b)=>(+b.lastTime||0)-(+a.lastTime||0));
  const quentes=base.filter(c=>(+c.responses||0)>0 && !hasActionableLeadReply(c)).sort((a,b)=>(+b.lastIncomingTime||+b.lastTime||0)-(+a.lastIncomingTime||+a.lastTime||0));
  const stress=base.filter(stressCandidate).sort((a,b)=>cadenceActivities(a)-cadenceActivities(b) || (+a.lastOutgoingTime||+a.lastTime||0)-(+b.lastOutgoingTime||+b.lastTime||0));
  const stress1=stress.filter(c=>cadenceActivities(c)===1), stress2=stress.filter(c=>cadenceActivities(c)===2), stress3=stress.filter(c=>cadenceActivities(c)===3);
  return {base,pipeTotal,pipeRows,responder,semAtividade,aguardando,audios,reunioes,quentes,stress,stress1,stress2,stress3};
}
function focusRow(c,reason){
  const last=c.lastTime?relTime(c.lastTime):'—';
  const owner=c.dealOwnerLabel||ownerLabelOfConv(c)||chipLabel(c.port);
  return `<div class="focus-row"><div><div class="fn">${esc(c.title)}${stressCandidate(c)?routePill(c):''}</div><div class="fm">${esc(reason)} · ${esc(owner)} · ${esc(last)}</div></div><div class="fa"><button onclick="openLead('${esc(c.id)}')">Abrir</button><button class="primary" onclick="selectOne('${esc(c.id)}')">Selecionar</button></div></div>`;
}
function focusList(title,items,reasonFn){
  return `<div class="focus-section"><h4>${esc(title)} <em>${items.length}</em></h4>${items.slice(0,8).map(c=>focusRow(c,reasonFn(c))).join('')||'<div class="mini-empty">Nada crítico aqui.</div>'}</div>`;
}
function cadenceStageCard(n,items,title,subtitle){
  const rows=items.slice(0,5).map(c=>focusRow(c,`${cadenceProgress(c)} · ${cadenceNextAction(c)} · ${routeSuggestion(c).kind}`)).join('')||'<div class="mini-empty">Sem leads nesta etapa.</div>';
  return `<div class="cad-stage stage-${n}">
    <div class="cad-stage-head"><span class="step">${n}</span><div><b>${esc(title)}</b><small>${esc(subtitle)}</small></div><strong>${items.length}</strong></div>
    <div class="cad-stage-action">Próximo passo: <b>${esc(n===1?'2º contato educativo':(n===2?'3º contato com relevância':'4º toque / despedida'))}</b></div>
    <div class="cad-stage-rows">${rows}</div>
    <div class="cad-stage-foot"><button onclick="selectStress('${n}',20)">Selecionar etapa</button><button onclick="bulkStressPreview()">Prévia segura</button></div>
  </div>`;
}
function cadenceBoard(b,counts){
  const summary=counts?`<div class="cad-stage-summary">
    <span><b>${counts['0']||0}</b> sem contato · mandar 1º</span>
    <span class="on"><b>${counts['1']||0}</b> já receberam 1 contato</span>
    <span class="on"><b>${counts['2']||0}</b> já receberam 2 contatos</span>
    <span class="on"><b>${counts['3']||0}</b> já receberam 3 contatos</span>
    <span><b>${counts['4+']||0}</b> 4+ contatos · nutrir/perder</span>
  </div>`:'';
  return `<div class="cad-board">
    <div class="cad-board-head"><div><b>Leads sem resposta separados por contatos já feitos</b><span>Simples: uma coluna para quem já recebeu 1 contato, outra para quem já recebeu 2 contatos, outra para quem já recebeu 3 contatos. Cada coluna mostra esses leads e o próximo contato recomendado. Nada é enviado automaticamente.</span></div><button onclick="bulkStressPreview()">🎯 Ver prévia geral</button></div>
    ${summary}
    <div class="cad-stage-grid">
      ${cadenceStageCard(1,b.stress1,'Receberam 1 contato','Agora preparar o 2º contato')}
      ${cadenceStageCard(2,b.stress2,'Receberam 2 contatos','Agora preparar o 3º contato')}
      ${cadenceStageCard(3,b.stress3,'Receberam 3 contatos','Agora preparar o 4º toque / despedida')}
    </div>
  </div>`;
}
function selectOne(id){selected.add(id); drawBulk(); if(viewMode==='conversas') drawCards();}
function stressRouteKey(c){
  const k=String(routeSuggestion(c).kind||'').toLowerCase();
  if(k.includes('chip do sdr')) return 'sdr';
  if(k.includes('comunicador leve')) return 'comm';
  if(k.includes('oficial')) return 'official';
  return 'other';
}
function selectStress(filter,limit=20){
  const b=focusBuckets(); let items=b.stress||[];
  if(['1','2','3'].includes(String(filter))) items=items.filter(c=>cadenceActivities(c)===+filter);
  else if(filter) items=items.filter(c=>stressRouteKey(c)===filter);
  items=items.slice(0,limit);
  items.forEach(c=>selected.add(c.id)); drawBulk();
  openBulkWizard('stress', items);
}
function selectFocus(kind,limit=10){
  const b=focusBuckets(); const items=(b[kind]||[]).slice(0,limit);
  items.forEach(c=>selected.add(c.id)); drawBulk();
  alert(`${items.length} lead(s) selecionados. Use a barra inferior para criar tarefa HubSpot ou marcar pendente. Disparo WhatsApp em massa continua bloqueado até ter prévia/limite por chip.`);
}
function focusAutomation(kind){
  selectFocus(kind,10);
  alert('Prévia criada. Próximo passo seguro: criar tarefas no HubSpot ou revisar os leads selecionados. Não disparei WhatsApp automaticamente.');
}
function drawFocus(){
  resetPipeFilters();
  const el=document.getElementById('cards'), p=pf(), st=pfStats();
  const loading=!pipelineFocus && pipelineFocusLoading;
  const total=p.total||st.total||0;
  document.getElementById('queueTitle').textContent='Foco SDR';
  document.getElementById('queueCount').textContent=loading?'carregando HubSpot…':`${total} negócios no pipe · etapas x atividades`;
  renderQueues();
  const state=pipeStateNotice();
  el.innerHTML=`<div class="focus-panel">
    ${pipeSimpleHeader('Foco SDR: deals por etapa e atividade')}
    ${state || `${pipeSimpleSummary()}${pfStageMatrix()}`}
  </div>`;
}


function filteredCards(){
  const q=(document.getElementById('search')?.value||'');
  let list=[...convs];
  if(filterStatus==='archived') list=list.filter(c=>localStatusOf(c)==='archived');
  else list=list.filter(c=>localStatusOf(c)!=='archived');
  if(filterOwner) list=list.filter(c=>ownerUidOfConv(c)===filterOwner);
  if(filterChip) list=list.filter(c=>String(c.port)===String(filterChip));
  if(filterStatus==='unread') list=list.filter(c=>hasActionableLeadReply(c));
  if(filterStatus==='audio') list=list.filter(c=>c.audioPending||c.audioTranscriptText);
  if(filterStatus==='meeting') list=list.filter(c=>isMeeting(c));
  if(q) list=list.filter(c=>matchesSearch(c,q));
  // WhatsApp mode: sempre cronológico por última atividade, sem abas/filtros.
  list.sort((a,b)=>(+(b.inboxSortTime||b.lastTime)||0)-(+(a.inboxSortTime||a.lastTime)||0));
  return list;
}
function leadOwnerLabel(c){return c.dealOwnerLabel||c.sdrLabel||ownerLabelOfConv(c)||'SDR'}
function senderLabel(c){return c.senderLabel||chipLabel(c.port)||'Comunicador'}
function hasCommunicator(c){
  const meta=portMeta[c.port]||{}, sender=senderLabel(c), owner=leadOwnerLabel(c);
  return !!(c.readOnlyInstitutional || meta.role==='comunicador' || meta.role==='institucional' || (sender && owner && sender!==owner && !String(sender).startsWith('Chip ')));
}
function communicatorChip(c){return hasCommunicator(c)?`<span class="inst-pill sender">Comunicador: ${esc(senderLabel(c))}</span>`:''}
function institutionalMap(c){
  if(!c.readOnlyInstitutional) return '';
  return `<div class="inst-map"><span class="inst-pill owner">Lead do SDR: ${esc(leadOwnerLabel(c))}</span>${communicatorChip(c)}</div>`;
}
function readonlyBadge(c){return c.readOnlyInstitutional?'<span class="badge b-shared">Auditoria institucional</span>':''}

function drawCards(){
  if(viewMode==='gestao') return drawManagement();
  if(viewMode==='foco') return drawFocus();
  const list=filteredCards();
  document.getElementById('queueTitle').textContent='Conversas';
  document.getElementById('queueCount').textContent=`${list.length} ${list.length===1?'conversa':'conversas'}`;
  renderFilterBar();
  renderQueues();
  const el=document.getElementById('cards');
  if(!list.length){ el.innerHTML=`<div class="empty"><b>Nada por aqui 🎉</b><span>Nenhuma conversa encontrada.</span></div>`; return; }
  el.innerHTML=list.map(c=>{
    const from=previewFrom(c);
    const preview=(c.last&&(c.last.text||c.last.transcript||c.last.mediaName||c.last.mediaType))||(c.audioTranscriptText?('Áudio: '+c.audioTranscriptText):'');
    const urgent=leadLast(c);
    const owner=ownerOf(c.port);
    const sel=selected.has(c.id);
    const meet=isMeeting(c)?'<span class="badge b-meet">Reunião/tarefa</span>':'';
    const aud=c.audioPending?`<span class="badge b-risk">🎙 ${c.audioPending} áudio(s)</span>`:(c.audioTranscriptText?'<span class="badge b-note">🎙 Transcrito</span>':'');
    const cardCompany=headCompanyName(c);
    const cardContact=headContactName(c);
    const cardPhone=phoneText(c);
    const contactLine=c.readOnlyInstitutional
      ? `${cardContact?esc(cardContact)+' · ':''}<span class="phone-mini">${esc(cardPhone)}</span>`
      : `${cardContact?esc(cardContact)+' · ':''}<span class="phone-mini">${esc(cardPhone)}</span>`;
    const titlePhone=looksLikePhoneName(cardCompany);
    return `<button class="card ${active===c.id?'active':''} ${sel?'selected':''} ${urgent?'reply unreadcard':''} ${c.readOnlyInstitutional?'readonly':''} ${localStatusOf(c)==='archived'?'archived':''} ${c.id===newTopConvId?'new-top':''}" data-conv="${esc(c.id)}" onclick="openConv('${esc(c.id)}')">
      <input type="checkbox" class="card-check" ${sel?'checked':''} onclick="event.stopPropagation();selToggle(this,'${esc(c.id)}')" title="Selecionar lead">
      <div class="row1"><span class="company ${titlePhone?'phone-fallback':''}">${esc(cardCompany)}</span><span class="time ${urgent?'urgent':''}">${relTime(c.lastTime)}</span></div>
      <div class="contact">${contactLine}</div>
      ${!c.readOnlyInstitutional && hasCommunicator(c)?`<div class="inst-map">${communicatorChip(c)}</div>`:''}
      ${institutionalMap(c)}
      <div class="preview"><span class="from ${from.cls}">${from.label}:</span><span class="txt">${esc(preview)}</span></div>
      <div class="row3">${readonlyBadge(c)}${stageBadge(c)}${hubspotBadge(c)}${sharedBadge(c)}${meet}${aud}${localBadge(c)}${automationBadge(c)}<span class="owner"><span class="av" style="background:${colorFor(c.readOnlyInstitutional?senderLabel(c):owner)}">${esc(initials(c.readOnlyInstitutional?senderLabel(c):owner))}</span>${c.readOnlyInstitutional?`via ${esc(senderLabel(c))}`:esc(chipLabel(c.port))}</span><span class="spacer"></span>${slaTag(c)}</div>
      <span class="card-archive" onclick="event.stopPropagation(); archiveConv('${esc(c.id)}')">${localStatusOf(c)==='archived'?'Desarquivar':'Arquivar'}</span>
    </button>`;
  }).join('');
}
function updateActiveCard(id){
  if(viewMode!=='conversas') return;
  document.querySelectorAll('#cards .card.active').forEach(el=>el.classList.remove('active'));
  const safe=String(id||'').replace(/\\/g,'\\\\').replace(/"/g,'\\"');
  const el=document.querySelector(`#cards .card[data-conv="${safe}"]`);
  if(el) el.classList.add('active');
}

/* ---- CH-025: painel de carga por agente removido (Rafael: redundante) ---- */
function drawLoad(){} // noop — seção removida da UI (loadPanel/loadCards/loadTitle não existem mais no HTML)
/* ---- CH-026: seleção e ações em massa (sem disparo/escrita ainda) ---- */
function selToggle(input,id){
  if(input.checked) selected.add(id); else selected.delete(id);
  const card=input.closest('.card'); if(card) card.classList.toggle('selected', input.checked);
  drawBulk();
}
function drawBulk(){
  const bar=document.getElementById('bulkbar'); if(!bar) return;
  const n=selected.size; bar.hidden=(n===0);
  if(n) document.getElementById('bbN').innerHTML=`<span>${n}</span> selecionado${n>1?'s':''}`;
}
function clearSelection(){ selected.clear(); drawBulk(); drawCards(); }
// CH-010: persiste estado/nota de uma conversa no backend (/api/state).
async function saveState(convId, payload){
  return api('/api/state',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.assign({conv:convId},payload))});
}
function setLocalStatusOptimistic(id,state){
  const c=convs.find(x=>x.id===id);
  if(c){ c.localStatus=state; c.localUpdatedAt=Date.now()/1000; }
}
async function bulkState(state){
  if(!selected.size) return;
  const ids=[...selected];
  ids.forEach(id=>setLocalStatusOptimistic(id,state));   // feedback imediato
  selected.clear(); drawBulk(); drawCards();
  let fail=0;
  for(const id of ids){ try{ await saveState(id,{status:state}); }catch(e){ fail++; } }
  if(fail) alert(fail+' conversa(s) não puderam ser atualizadas.');
  await loadAll();
}
async function bulkHubspotTask(){
  if(!selected.size) return;
  const ids=[...selected];
  if(ids.length>10) return alert('Limite de segurança: selecione no máximo 10 leads por vez para criar tarefa no HubSpot.');
  const rows=ids.map(id=>convs.find(c=>c.id===id)).filter(Boolean);
  const preview=rows.map((c,i)=>`${i+1}. ${c.title} · ${chipLabel(c.port)}`).join('\n');
  const subject=prompt(`Criar tarefa HubSpot para ${rows.length} lead(s):\n\n${preview}\n\nAssunto da tarefa:`, 'Follow-up WhatsApp');
  if(subject===null) return;
  const body=prompt('Descrição da tarefa:', 'Fazer follow-up pelo WhatsApp e registrar próximo passo.');
  if(body===null) return;
  if(!confirm(`Confirmar criação de tarefa no HubSpot para ${rows.length} lead(s)?\n\n${preview}`)) return;
  let ok=0, fail=[];
  for(const c of rows){
    try{
      await api('/api/hubspot/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({conv:c.id,action:'task',subject,body,due:'today'})});
      ok++;
    }catch(e){ fail.push(`${c.title}: ${e.message.slice(0,140)}`); }
  }
  clearSelection();
  alert(`Tarefas criadas no HubSpot: ${ok}/${rows.length}`+(fail.length?'\n\nFalhas:\n'+fail.slice(0,5).join('\n'):''));
  await loadAll();
}
// Modal simples para seleção em massa: nada de alert gigante. Step-by-step.
let bulkWizard={kind:'stress',step:1,rows:[],aptos:[],bloqueados:[],routeSummary:'—'};
function selectedRows(){return [...selected].map(id=>convs.find(c=>c.id===id)).filter(Boolean)}
function _routeSummary(aptos){const by={}; aptos.forEach(c=>{const r=routeSuggestion(c).kind; by[r]=(by[r]||0)+1;}); return Object.entries(by).map(([k,v])=>`${k}: ${v}`).join(' · ')||'—'}
function analyzeStressRows(rows){
  const aptos=[], bloqueados=[];
  for(const c of rows){
    let motivo='';
    if(c.readOnlyInstitutional) motivo='auditoria institucional / somente leitura';
    else if(hasActionableLeadReply(c) || (+c.responses||0)>0) motivo='lead respondeu — bola com SDR';
    else if(cadenceActivities(c)<=0) motivo='sem D0/atividade de saída confiável';
    else if(cadenceActivities(c)>=4) motivo='já tem 4+ atividades — nutrição/perda';
    if(motivo) bloqueados.push({c,motivo}); else aptos.push(c);
  }
  return {aptos,bloqueados,routeSummary:_routeSummary(aptos)};
}
function analyzeFollowupRows(rows){
  const aptos=[], bloqueados=[];
  for(const c of rows){
    let motivo='';
    if(c.readOnlyInstitutional) motivo='auditoria institucional / somente leitura';
    else if(leadLast(c) || (+c.responses||0)>0) motivo='lead respondeu — tratar manualmente';
    else if(!(+c.lastTime||0)) motivo='sem histórico confiável';
    if(motivo) bloqueados.push({c,motivo}); else aptos.push(c);
  }
  return {aptos,bloqueados,routeSummary:'Chip do SDR / rota segura'};
}
function openBulkWizard(kind='stress', rows=null){
  let base=rows||selectedRows();
  if(!base.length) base=(focusBuckets().stress||[]).slice(0,20);
  const max=kind==='followup'?10:20;
  if(base.length>max){ base=base.slice(0,max); }
  const a=kind==='followup'?analyzeFollowupRows(base):analyzeStressRows(base);
  bulkWizard={kind,step:1,rows:base,aptos:a.aptos,bloqueados:a.bloqueados,routeSummary:a.routeSummary};
  document.getElementById('bulkWizard').hidden=false;
  renderBulkWizard();
}
function closeBulkWizard(){const m=document.getElementById('bulkWizard'); if(m) m.hidden=true;}
function wizMove(delta){bulkWizard.step=Math.max(1,Math.min(3,(bulkWizard.step||1)+delta)); renderBulkWizard();}
function wizRows(items, blocked=false){
  return (items||[]).slice(0,12).map((x,i)=>{const c=blocked?x.c:x; const meta=blocked?x.motivo:`${cadenceProgress(c)} · ${cadenceNextAction(c)} · ${routeSuggestion(c).kind}`; return `<div class="wiz-row"><b>${i+1}. ${esc(c.title)}</b><span>${esc(meta)} · ${esc(c.dealOwnerLabel||ownerLabelOfConv(c)||chipLabel(c.port))}</span></div>`;}).join('')||'<div class="mini-empty">Nenhum.</div>';
}
function renderBulkWizard(){
  const w=bulkWizard, title=w.kind==='followup'?'Prévia de follow-up':'Prévia para estressar base';
  document.getElementById('wizTitle').textContent=title;
  document.getElementById('wizSub').textContent=`${w.rows.length} analisados · ${w.aptos.length} aptos · ${w.bloqueados.length} bloqueados`;
  [1,2,3].forEach(i=>document.getElementById('wizStep'+i)?.classList.toggle('on',w.step===i));
  const prev=document.getElementById('wizPrev'), next=document.getElementById('wizNext');
  if(prev) prev.disabled=w.step===1;
  if(next) next.textContent=w.step===3?'Concluir':'Continuar';
  const body=document.getElementById('wizBody'); if(!body) return;
  if(w.step===1){
    body.innerHTML=`<div class="wiz-panel on"><div class="wiz-kpis"><div class="wiz-kpi"><b>${w.rows.length}</b><span>analisados agora</span></div><div class="wiz-kpi"><b>${w.aptos.length}</b><span>aptos</span></div><div class="wiz-kpi"><b>${w.bloqueados.length}</b><span>bloqueados</span></div><div class="wiz-kpi"><b>${esc(w.routeSummary)}</b><span>canal sugerido</span></div></div><div class="focus-safe"><b>Importante:</b> isto é só prévia. Nenhum WhatsApp é enviado e nada muda no HubSpot aqui.</div></div>`;
  } else if(w.step===2){
    body.innerHTML=`<div class="wiz-panel on"><div class="wiz-list"><div class="wiz-box"><h4>Aptos (${w.aptos.length})</h4>${wizRows(w.aptos,false)}</div><div class="wiz-box"><h4>Bloqueados (${w.bloqueados.length})</h4>${wizRows(w.bloqueados,true)}</div></div></div>`;
  } else {
    body.innerHTML=`<div class="wiz-panel on"><div class="wiz-actions"><button class="wiz-action" onclick="bulkHubspotTask()"><b>＋ Criar tarefa HubSpot</b><span>Cria tarefa para seleção atual com confirmação antes de escrever.</span></button><button class="wiz-action" onclick="bulkState('pending'); closeBulkWizard()"><b>◷ Marcar pendente</b><span>Estado local do Channel. Não escreve no HubSpot.</span></button><button class="wiz-action" onclick="bulkState('resolved'); closeBulkWizard()"><b>✓ Marcar resolvido</b><span>Remove da fila operacional local até nova resposta.</span></button><button class="wiz-action" onclick="clearSelection(); closeBulkWizard()"><b>Limpar seleção</b><span>Fecha o fluxo sem executar nada.</span></button></div><div class="focus-safe" style="margin-top:12px"><b>Disparo real continua bloqueado.</b> A próxima etapa correta é revisar texto individual/playbook ou criar tarefa — sem automação em massa.</div></div>`;
  }
  if(w.step===3 && next) next.onclick=()=>closeBulkWizard(); else if(next) next.onclick=()=>wizMove(1);
}
function bulkFollowupPreview(){
  const rows=selectedRows();
  if(!rows.length) return;
  openBulkWizard('followup', rows);
}
function bulkStressPreview(){
  let rows=selectedRows();
  if(!rows.length) rows=(focusBuckets().stress||[]).slice(0,20);
  openBulkWizard('stress', rows);
}
// Estado a partir da conversa aberta (lateral / próxima ação).
async function convState(state){
  if(!active) return;
  setLocalStatusOptimistic(active,state);
  const c=convs.find(x=>x.id===active); if(c){ drawContext(c); }
  drawCards();
  try{ await saveState(active,{status:state}); }catch(e){ alert('Falha ao salvar: '+e.message); }
  await loadAll();
}
async function archiveConv(id){
  const c=convs.find(x=>x.id===id); if(!c) return;
  const next=localStatusOf(c)==='archived'?'open':'archived';
  setLocalStatusOptimistic(id,next);
  if(active===id && next==='archived') active=null;
  drawCards(); drawBulk();
  try{ await saveState(id,{status:next}); }catch(e){ alert('Falha ao arquivar: '+e.message); }
  await loadAll({fast:true,force:true});
}

/* ---------- conversation pane ---------- */
function mLabel(m){if(!m) return ''; if(!m.fromMe) return 'Resposta do lead';
  if(m.type==='cron-sdr-primeiro-contato') return '1º contato SDR';
  if(m.type==='cron-mql-texto') return 'Diagnóstico · texto';
  if(m.type==='cron-mql-pdf') return 'Diagnóstico · PDF';
  const mt=String(m.msg_type||'').toLowerCase();
  if(mt.includes('follow')) return 'Follow-up';
  if(mt.includes('cadencia')||mt.includes('sumico')) return 'Cadência';
  return 'WhatsApp';}
function isEvent(m){return m.fromMe && /^cron-/.test(m.type||'')}
function isOperationalDispatchMsg(m){
  const t=String((m&&m.type)||'').toLowerCase(), mt=String((m&&m.msg_type)||'').toLowerCase(), a=String((m&&m.automation)||'').toLowerCase();
  return m&&m.fromMe&&(!!(m.dispatchLabel||m.dispatchPort||m.group_bridge_port||m.port)||t.includes('mql')||mt.includes('diagnostico')||mt.includes('mql')||mt.includes('follow')||mt.includes('cadencia')||mt.includes('sumico')||mt.includes('primeiro_contato')||a.includes('diagnóstico')||a.includes('diagnostico')||m.pdf_path||m.hubspot_file_id);
}
function isDiagnosticDispatchMsg(m){return isOperationalDispatchMsg(m)}
function dispatchSenderLabel(m){
  if(!isOperationalDispatchMsg(m)) return '';
  return String(m.dispatchLabel||chipLabel(m.dispatchPort||m.group_bridge_port||m.port||'')||'').trim();
}
function dispatchSenderHtml(m){
  const dispatch=dispatchSenderLabel(m);
  if(!dispatch) return '';
  return `<span class="sender-who"><span class="sender-av" style="background:${colorFor(dispatch)}">${esc(initials(dispatch).slice(0,1))}</span>${esc(dispatch)}</span>`;
}
function dispatchIdentityHtml(m){
  if(!isDiagnosticDispatchMsg(m)) return '';
  const owner=String(m.leadOwnerLabel||'').trim();
  if(!owner) return '';
  return `<span class="dispatch-who">lead do ${esc(owner)}</span>`;
}
function eventIconHtml(m){
  const sender=dispatchSenderLabel(m);
  if(sender) return '';
  return `<div class="eic">${/pdf/.test(m.type)?'📄':'⚙️'}</div>`;
}
function eventTitleHtml(m){
  const sender=dispatchSenderLabel(m), owner=String(m.leadOwnerLabel||'').trim();
  const base=esc(mLabel(m));
  if(!sender) return `${base}<span class="et">${esc(hhmm(m.timestamp))}</span>`;
  const ownerTxt=owner?`<span class="dispatch-who">lead do ${esc(owner)}</span>`:'';
  const av=`<span class="sender-av" style="background:${colorFor(sender)}">${esc(initials(sender).slice(0,1))}</span>`;
  return `<span class="sender-line">${av}${esc(sender)}</span><span class="et">${base}</span>${ownerTxt}<span class="et">${esc(hhmm(m.timestamp))}</span>`;
}
function mediaUrlFor(m,file){
  const chat=encodeURIComponent(m.chat||active||'');
  return `/api/media?port=${encodeURIComponent(m.port||'')}&file=${encodeURIComponent(file)}&chat=${chat}&${auth}`;
}
function fileKind(name,m){
  const n=String(name||'').toLowerCase(), mime=String((m&&m.mimetype)||'').toLowerCase(), mt=String((m&&m.mediaType)||'').toLowerCase();
  if(mt==='audio'||mime.startsWith('audio/')||/\.(ogg|opus|mp3|m4a|wav|aac|flac)$/i.test(n)) return 'audio';
  if(mime.includes('pdf')||n.endsWith('.pdf')) return 'pdf';
  if(mime.startsWith('image/')||/\.(png|jpe?g|webp|gif)$/i.test(n)) return 'image';
  return 'file';
}
function mediaLink(m){
  const raw=m.mediaUrl||m.mediaPath||'';
  const file=raw?String(raw).split('/').pop():'';
  const name=m.mediaName||m.fileName||m.mediaType||m.mimetype||'mídia';
  const ext=((name.includes('.')?name.split('.').pop():(m.mimetype||'file').split('/').pop())||'FILE').toUpperCase().slice(0,4);
  if(!file) return `<button type="button" class="pdf missing" onclick="openMissingFileInfo('${esc(String(name))}')"><div class="pic"><span>${esc(ext||'FILE')}</span></div><div class="pmeta"><b>${esc(name)}</b><span>Arquivo registrado no WhatsApp · abrir detalhes</span></div></button>`;
  const url=mediaUrlFor(m,file), kind=fileKind(name,m), label=kind==='pdf'?'Pré-visualizar PDF':(kind==='image'?'Pré-visualizar imagem':'Abrir arquivo');
  if(kind==='audio'){
    return `<div class="audio-card"><div class="aic">▶</div><div class="ameta"><b>${esc(name==='audio'?'Áudio WhatsApp':name)}</b><audio controls preload="metadata" src="${esc(url)}"></audio><a class="adownload" href="${esc(url)}" target="_blank" download>Baixar áudio</a></div></div>`;
  }
  return `<button type="button" class="pdf" onclick="openFilePreview('${esc(url)}','${esc(String(name))}','${esc(kind)}')"><div class="pic"><span>${esc(ext||'FILE')}</span></div><div class="pmeta"><b>${esc(name)}</b><span>${esc(label)}</span></div></button>`;
}
function openFilePreview(url,name,kind){
  const modal=document.getElementById('fileModal'), body=document.getElementById('fileModalBody'), title=document.getElementById('fileModalTitle'), sub=document.getElementById('fileModalSub'), dl=document.getElementById('fileModalDownload');
  if(!modal||!body) return window.open(url,'_blank');
  title.textContent=name||'Arquivo'; sub.textContent=kind==='pdf'?'Pré-visualização do PDF':(kind==='image'?'Pré-visualização da imagem':'Arquivo');
  dl.hidden=false; dl.href=url; dl.setAttribute('download', name||'arquivo');
  if(kind==='pdf') body.innerHTML=`<div class="file-preview"><iframe src="${url}#toolbar=1&navpanes=0&view=FitH" title="${esc(name||'PDF')}"></iframe></div>`;
  else if(kind==='image') body.innerHTML=`<div class="file-preview-fallback"><img src="${url}" alt="${esc(name||'imagem')}" style="max-width:100%;max-height:100%;object-fit:contain;border-radius:12px"></div>`;
  else body.innerHTML=`<div class="file-preview-fallback"><div><b>Pré-visualização indisponível</b><span>Baixe o arquivo para abrir no aplicativo adequado.</span></div></div>`;
  modal.hidden=false;
}
function openMissingFileInfo(name){
  const modal=document.getElementById('fileModal'), body=document.getElementById('fileModalBody'), title=document.getElementById('fileModalTitle'), sub=document.getElementById('fileModalSub'), dl=document.getElementById('fileModalDownload');
  if(!modal||!body) return;
  title.textContent=name||'Mídia'; sub.textContent='Arquivo sem binário local'; if(dl) dl.hidden=true;
  body.innerHTML=`<div class="file-preview-fallback"><div><b>Não encontrei o arquivo para pré-visualizar</b><span>O WhatsApp registrou uma mídia nessa posição, mas a bridge não salvou o PDF/arquivo no disco. Quando o arquivo estiver disponível, este card abre a pré-visualização direto no modal.</span></div></div>`;
  modal.hidden=false;
}
function closeFilePreview(){
  const modal=document.getElementById('fileModal'), body=document.getElementById('fileModalBody');
  if(body) body.innerHTML='<div class="file-preview-fallback"><b>Selecione um arquivo</b></div>';
  if(modal) modal.hidden=true;
}

function transcriptBlock(m){
  if(!m.mediaUrl && !m.mediaName && !m.mimetype) return '';
  if(m.transcript) return `<div class="transcript"><b>Transcrição do áudio</b>${esc(m.transcript)}</div>`;
  if((m.mediaType||'').toLowerCase()==='audio' || /^audio\//.test((m.mimetype||'').toLowerCase())) return `<div class="transcript pending"><b>Áudio</b>Áudio carregado. Transcrição em processamento; a conversa atualiza sozinha quando terminar.</div>`;
  return '';
}
function isIncomingAudio(m){return m && m.fromMe===false && (((m.mediaType||'').toLowerCase()==='audio') || /^audio\//.test((m.mimetype||'').toLowerCase()))}
function audioNeedsTranscript(m){return isIncomingAudio(m) && !m.transcript && ['pending','error','missing_file',''].includes(String(m.transcriptStatus||'pending'))}

function drawTimeline(autoScroll=true){
  const tl=document.getElementById('timeline');
  if(!msgs.length){ tl.innerHTML=`<div class="empty"><b>Sem mensagens</b><span>Esta conversa ainda não tem histórico.</span></div>`; return; }
  let html='', lastDay='', lastSender='';
  msgs.forEach(m=>{
    const dk=dayKey(m.timestamp);
    if(dk!==lastDay){ html+=`<div class="day-sep"><span>${esc(dk)}</span></div>`; lastDay=dk; lastSender=''; }
    if(isEvent(m)){
      html+=`<div class="event"><div class="event-card">${eventIconHtml(m)}<div class="ebody"><div class="etitle">${eventTitleHtml(m)}</div>${m.text?`<div class="edesc">${esc(m.text)}</div>`:''}${(m.mediaUrl||m.mediaPath||m.mediaName||m.mimetype||m.mediaType)?mediaLink(m):''}</div></div></div>`;
      lastSender='';
      return;
    }
    const lead=m.fromMe===false;
    // Agrupa mensagens consecutivas do mesmo remetente como no WhatsApp: o nome
    // (chip / lead) só aparece no início de cada bloco, reduzindo ruído.
    const sender=m.fromMe?('out:'+(m.port||'')):'in';
    const grp=sender!==lastSender; lastSender=sender;
    // Conversa 1:1 estilo WhatsApp: o nome já está no header, então não repetimos
    // remetente dentro da bolha. Mantemos só badge discreto de automação quando houver.
    const defaultSender=chipLabel(m.port||'');
    const senderWho=(m.fromMe&&grp)?(dispatchSenderHtml(m)||`<span class="sender-who"><span class="sender-av" style="background:${colorFor(defaultSender)}">${esc(initials(defaultSender).slice(0,1))}</span>${esc(defaultSender)}</span>`):'';
    const dispatchWho=dispatchIdentityHtml(m);
    const whoHtml=grp?`<span class="bwho">${senderWho}${dispatchWho}${m.automation?`<span class="autobadge">⚙ ${esc(m.automation)}</span>`:''}</span>`:'';
    const anyMedia=!!(m.mediaUrl||m.mediaPath||m.mediaName||m.mimetype||m.mediaType);
    const body=esc(m.text||'')||(anyMedia?'':'<i style="color:var(--muted)">(mensagem sem texto)</i>');
    const hasMedia=anyMedia;
    html+=`<div class="brow ${m.fromMe?'out':'in'} ${lead?'lead':''} ${grp?'grp-start':''}">
      <div class="bubble ${hasMedia?'has-media':''}">${whoHtml}<span class="btext">${body}${anyMedia?mediaLink(m):''}${transcriptBlock(m)}</span><span class="btime">${esc(hhmm(m.timestamp))}</span></div>
    </div>`;
  });
  tl.innerHTML=html;
  if(autoScroll) tl.scrollTop=tl.scrollHeight;
}
function titleOf(id){const c=convs.find(x=>x.id===id); return c?c.title:''}

function looksLikePhoneName(v){
  const t=String(v||'').trim();
  if(!t) return true;
  return /^\+?\d[\d\s().-]{6,}$/.test(t) || t==='Número protegido' || t==='—';
}
function headCompanyName(c){
  const hs=hsCache[c.id]||{}, ct=hs.contact||{}, d=(hs.deals&&hs.deals[0])||{};
  const candidates=[ct.company,d.dealname,c.company,c.empresa,c.dealName,c.title].map(x=>String(x||'').trim()).filter(Boolean);
  const best=candidates.find(x=>!looksLikePhoneName(x));
  return best || phoneText(c) || 'Contato sem empresa';
}
function headContactName(c){
  const hs=hsCache[c.id]||{}, ct=hs.contact||{};
  const hsN=hsName(ct);
  const sub=String(c.subtitle||'').trim();
  const candidates=[hsN,sub,c.contactName,c.nome].map(x=>String(x||'').trim()).filter(Boolean);
  return candidates.find(x=>!looksLikePhoneName(x) && x!==headCompanyName(c)) || '';
}
function applyHubspotIdentityToConv(c,data){
  if(!c||!data||!data.found||!data.contact) return;
  const ct=data.contact||{}, d=(data.deals&&data.deals[0])||{};
  const company=String(ct.company||d.dealname||'').trim();
  const contact=String(hsName(ct)||'').trim();
  if(company && !looksLikePhoneName(company)){
    c.company=company; c.empresa=company; c.dealName=d.dealname||company;
    if(looksLikePhoneName(c.title) || !String(c.title||'').trim()) c.title=company;
  }
  if(contact && !looksLikePhoneName(contact)){
    c.contactName=contact;
    if(!c.subtitle || looksLikePhoneName(c.subtitle) || String(c.subtitle).includes(phoneText(c))) c.subtitle=contact;
  }
  if(ct.email) c.hubspotEmail=ct.email;
  if(ct.id) c.hubspotContactId=ct.id;
  if(d.id) c.hubspotDealId=d.id;
}
function drawHead(c){
  const owner=ownerOf(c.port);
  const ptxt=phoneText(c);
  const company=headCompanyName(c);
  const contact=headContactName(c);
  const titleIsPhone=looksLikePhoneName(company);
  const ro=!!c.readOnlyInstitutional;
  const leadOwner=leadOwnerLabel(c);
  const sender=senderLabel(c);
  const contactPhoneHtml=`${contact?`<span class="contact-name">${esc(contact)}</span><span class="dotsep"></span>`:''}<span>${esc(ptxt)}</span>`;
  const subHtml = ro
    ? `${contactPhoneHtml}<span class="dotsep"></span><span class="inst-pill owner">Proprietário SDR: ${esc(leadOwner)}</span><span class="inst-pill sender">Comunicador: ${esc(sender)}</span>`
    : `${contactPhoneHtml}<span class="dotsep"></span><span class="owner"><span class="av" style="background:${colorFor(owner)};width:16px;height:16px;border-radius:50%;font-size:8px;display:grid;place-items:center;font-weight:700;color:#0a0a0a">${esc(initials(owner))}</span> SDR ${esc(owner)}</span>${hasCommunicator(c)?`<span class="dotsep"></span>${communicatorChip(c)}`:''}`;
  document.getElementById('convHead').innerHTML=`
    <button class="icon-btn back-btn" onclick="mobileBack()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m15 18-6-6 6-6"/></svg></button>
    <div class="avatar" style="background:${colorFor(company)};width:40px;height:40px;border-radius:50%">${esc(initials(company))}</div>
    <div class="ttl"><b><span class="company-title ${titleIsPhone?'phone-fallback':''}">${esc(company)}</span> ${stageBadge(c)}</b><div class="sub">${subHtml}</div></div>
    <div class="head-actions">
      <button class="icon-btn" title="Arquivar" onclick="archiveConv('${esc(c.id)}')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 8v13H3V8"/><path d="M1 3h22v5H1z"/><path d="M10 12h4"/></svg></button>
      <button class="icon-btn" title="Resolver" onclick="convState('resolved')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg></button>
      <button class="icon-btn" title="Contexto / HubSpot" onclick="toggleCtx()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12h18M3 6h18M3 18h18"/></svg></button>
    </div>`;
}

function ring(pct,color){
  const r=20,c=2*Math.PI*r,off=c*(1-pct/100);
  return `<svg width="46" height="46" viewBox="0 0 46 46"><circle cx="23" cy="23" r="${r}" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="4"/><circle cx="23" cy="23" r="${r}" fill="none" stroke="${color}" stroke-width="4" stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${off}"/></svg>`;
}

/* ---- CH-030: lateral HubSpot real (read-only) ---- */
let hsCache={};   // conv.id -> resposta de /api/hubspot (1 busca por conversa por sessão)
function statusLeadOf(c){
  if(leadLast(c)) return 'Respondeu · bola com o comercial';
  return (c.responses>0) ? 'Em conversa' : 'Aguardando 1ª resposta';
}
function hsName(ct){return [ct.firstname,ct.lastname].filter(Boolean).join(' ').trim()}
function hsPhone(ct){return ct.whatsapp||ct.mobilephone||ct.phone||''}
function lifecycleLabel(s){
  const M={lead:'Lead',subscriber:'Assinante',marketingqualifiedlead:'MQL',salesqualifiedlead:'SQL',
    opportunity:'Oportunidade',customer:'Cliente',evangelist:'Evangelista',other:'Outro'};
  return M[(s||'').toLowerCase()]||s||'—';
}
function hsSourceLabel(s){return ({phone:'telefone',company:'empresa',email:'e-mail'})[s]||'—'}
function hubspotRecordUrl(kind,id){
  id=String(id||'').trim(); if(!id) return '';
  const obj=kind==='deal'?'0-3':'0-1';
  return 'https://app.hubspot.com/contacts/48590774/record/'+obj+'/'+encodeURIComponent(id);
}
function hsExternalIcon(){return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 3h7v7"/><path d="M10 14 21 3"/><path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5"/></svg>'}
function hubspotRecordLinks(c,data){
  const ct=(data&&data.contact)||{};
  const deals=(data&&data.deals)||[];
  const contactId=ct.id||c.hubspotContactId||'';
  const dealId=(deals[0]&&deals[0].id)||c.hubspotDealId||'';
  const links=[];
  if(contactId) links.push(`<a class="hs-link" href="${esc(hubspotRecordUrl('contact',contactId))}" target="_blank" rel="noopener noreferrer">${hsExternalIcon()}Contato</a>`);
  if(dealId) links.push(`<a class="hs-link" href="${esc(hubspotRecordUrl('deal',dealId))}" target="_blank" rel="noopener noreferrer">${hsExternalIcon()}Negócio</a>`);
  return links.length?`<div class="hs-links">${links.join('')}</div>`:'';
}
function firstVal(obj, keys){for(const k of keys){const v=(obj&&obj[k])||''; if(String(v).trim()) return String(v).trim();} return ''}
function formRows(ct){
  const f=(ct&&ct.form)||{};
  const rows=[
    ['ERP', firstVal(f,['qual_erp_utiliza_','selecione_o_sistema_de_gesto_erp'])],
    ['Loja virtual', firstVal(f,['vende_em_loja_virtual_'])],
    ['Compraria online 24h?', firstVal(f,['voc_acredita_que_o_seu_cliente_compraria_sozinho_na_sua_loja_24h_por_dia_sem_precisar_de_vendedor'])],
    ['Faturamento', firstVal(f,['qual_o_faturamento_anual_da_sua_empresa_','e_qual_faturamento_anual_da_sua_empresa','selecione_a_faixa_de_faturamento','selecione_a_faixa_de_faturamento_atual_por_ano_da_sua_empresa'])],
    ['Área de atuação', firstVal(f,['qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados'])],
    ['Vende para', firstVal(f,['voc_vende_para_quem_ex_padarias_restaurantes_petshop_autopeas_supermercados'])],
    ['Dor principal', firstVal(f,['principais_dores','qual_seria_o_maior_problema_que_voc_enfrenta_em_sua_operao_atualmente'])],
    ['Pessoas', firstVal(f,['quantas_pessoas_atuam_na_sua_empresa'])],
    ['Vendedores', firstVal(f,['quantos_vendedores_internos_sua_empresa_possui'])],
    ['Venda hoje', firstVal(f,['de_qual_forma_mais_vende_hoje_em_dia'])],
  ].filter(r=>r[1]);
  if(!rows.length) return '<div class="mini-empty">Formulário sem campos comerciais preenchidos.</div>';
  return rows.slice(0,10).map(([k,v])=>`<div class="kv"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`).join('');
}
function hsDateTime(s){
  if(!s) return '—';
  try{return new Date(s).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})}catch(e){return s}
}
function meetingRows(d){
  const ms=d.meetings||[];
  if(!ms.length) return '';
  return ms.map(m=>`
    <div class="kv"><span class="k">Reunião</span><span class="v">${esc(m.title||'Reunião')}</span></div>
    <div class="kv"><span class="k">Quando</span><span class="v">${esc(hsDateTime(m.timestamp))}</span></div>
    <div class="kv"><span class="k">Organizador</span><span class="v ${m.ownerName||m.ownerId?'':'ph'}">${esc(m.ownerName||m.ownerId||'—')}</span></div>
    ${m.outcome?`<div class="kv"><span class="k">Resultado</span><span class="v">${esc(m.outcome)}</span></div>`:''}`
  ).join('');
}
// CTA padrão: usado quando HubSpot não está configurado ou o contato não foi achado.
function hubspotCtaView(c,owner,statusLead,note){
  return `
    ${hubspotRecordLinks(c,null)}
    <div class="kv"><span class="k">Empresa</span><span class="v">${esc(c.title||'—')}</span></div>
    <div class="kv"><span class="k">Contato</span><span class="v">${esc(c.subtitle||'—')}</span></div>
    <div class="kv"><span class="k">Telefone</span><span class="v ${c.displayPhone?'':'ph'}">${esc(phoneText(c))}</span></div>
    <div class="kv"><span class="k">SDR / Owner</span><span class="v">${esc(owner)}</span></div>
    <div class="kv"><span class="k">Status do lead</span><span class="v">${esc(statusLead)}</span></div>
    <div class="kv"><span class="k">Negócio</span><span class="v ph">${esc(note||'Não encontrado no HubSpot')}</span></div>
    <button class="add-note" style="margin-top:11px" onclick="alert('Integração HubSpot — em configuração')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>Conectar contato ao HubSpot</button>`;
}
function hubspotLoadingView(c,owner,statusLead){
  return hubspotCtaView(c,owner,statusLead,'Buscando no HubSpot…');
}
function hubspotView(c,owner,statusLead,data){
  if(!data) return hubspotLoadingView(c,owner,statusLead);
  if(data.configured===false) return hubspotCtaView(c,owner,statusLead,'HubSpot não configurado');
  if(!data.found||!data.contact) return hubspotCtaView(c,owner,statusLead,'');
  const ct=data.contact, deals=data.deals||[];
  const d=deals[0]||{};
  const dealRows = deals.length ? `
      <div class="kv"><span class="k">Negócio</span><span class="v">${esc(d.dealname||'—')}</span></div>
      <div class="kv"><span class="k">Etapa</span><span class="v">${esc(d.dealstage_label||d.dealstage||'—')}</span></div>
      <div class="kv"><span class="k">Owner negócio</span><span class="v">${esc(d.hubspot_owner_name||d.hubspot_owner_id||'—')}</span></div>
      ${meetingRows(d)}`
    : `<div class="kv"><span class="k">Negócio</span><span class="v ph">Sem negócio associado</span></div>`;
  return `
    ${hubspotRecordLinks(c,data)}
    <div class="kv"><span class="k">Empresa</span><span class="v">${esc(ct.company||c.title||'—')}</span></div>
    <div class="kv"><span class="k">Contato</span><span class="v">${esc(hsName(ct)||c.subtitle||'—')}</span></div>
    <div class="kv"><span class="k">Telefone</span><span class="v ${hsPhone(ct)?'':'ph'}">${esc(hsPhone(ct)||phoneText(c))}</span></div>
    ${dealRows}
    <div style="height:8px"></div><h5 style="margin:8px 0 8px;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)">Formulário preenchido</h5>
    ${formRows(ct)}`;
}
let hsReqSeq=0;
async function loadHubspot(c){
  const owner=ownerOf(c.port), st=statusLeadOf(c), seq=++hsReqSeq;
  try{
    const data=await api('/api/hubspot?conv='+encodeURIComponent(c.id));
    hsCache[c.id]=data;
    applyHubspotIdentityToConv(c,data);
    if(seq!==hsReqSeq||active!==c.id) return;   // conversa mudou: não pisa no contexto atual
    drawHead(c);
    drawCards();
    const el=document.getElementById('hsBody'); if(el) el.innerHTML=hubspotView(c,owner,st,data);
  }catch(e){
    if(seq!==hsReqSeq||active!==c.id) return;
    const el=document.getElementById('hsBody'); if(el) el.innerHTML=hubspotCtaView(c,owner,st,'');
  }
}

// CH-031/055: cria task/nota no HubSpot a partir da conversa aberta.
// Modo normal usa prompt; presets `followup`/`summary_note` são 1 clique.
async function hubspotAction(action,preset=''){
  if(!active){ alert('Abra uma conversa primeiro.'); return; }
  const c=convs.find(x=>x.id===active); if(!c) return;
  const hs=hsCache[c.id];
  if(hs && (hs.configured===false)){ alert('HubSpot não está configurado neste ambiente.'); return; }
  if(hs && (hs.found===false || !hs.contact)){ alert('Contato ainda não encontrado no HubSpot para esta conversa — não é possível registrar '+(action==='task'?'tarefa':'nota')+'.'); return; }
  const ai=c.aiSummary||{};
  const transcript=c.audioTranscriptText?`\n\nÁudio transcrito: ${c.audioTranscriptText.slice(0,1200)}`:'';
  let subject='', bodyTxt='';
  if(preset==='followup'){
    action='task'; subject='Follow-up WhatsApp';
    bodyTxt=`Próxima ação sugerida pelo Channel: ${ai.nextAction||'Retomar conversa pelo WhatsApp e registrar próximo passo.'}${transcript}`;
  }else if(preset==='summary_note'){
    action='note';
    bodyTxt=`Resumo Channel: ${ai.summary||'Conversa acompanhada pelo Channel.'}\nPróxima ação: ${ai.nextAction||'Definir próximo passo comercial.'}${transcript}`;
  }else if(action==='task'){
    subject=prompt('Assunto da tarefa no HubSpot:','Follow-up WhatsApp'); if(subject===null) return;
    bodyTxt=prompt('Descrição da tarefa:',''); if(bodyTxt===null) return;
  }else{
    bodyTxt=prompt('Texto da nota (será registrada no HubSpot):',''); if(bodyTxt===null) return;
  }
  if(!bodyTxt || !bodyTxt.trim()){ alert('Texto obrigatório.'); return; }
  if(preset && !confirm((action==='task'?'Criar tarefa':'Registrar nota')+' no HubSpot para '+c.title+'?')) return;
  const payload={conv:c.id, action, body:bodyTxt};
  if(action==='task'){ payload.subject=(subject&&subject.trim())||'Follow-up WhatsApp'; payload.due='today'; }
  try{
    const r=await api('/api/hubspot/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    alert((action==='task'?'Tarefa':'Nota')+' criada no HubSpot ✓ (id '+r.id+')'+(r.dealId?' · negócio associado':''));
    // Também registra uma nota local para o time ver no Channel (não vai ao lead).
    try{
      const localNote=(action==='task'?('[HubSpot · tarefa] '+payload.subject+' — '):'[HubSpot · nota] ')+bodyTxt;
      await saveState(c.id,{note:localNote});
      await loadAll();
    }catch(e){ /* nota local é best-effort */ }
  }catch(e){
    alert('Falha ao criar no HubSpot: '+(e&&e.message?e.message:e));
  }
}

async function hubspotConversationHistory(){
  if(!active){ alert('Abra uma conversa primeiro.'); return; }
  const c=convs.find(x=>x.id===active); if(!c) return;
  const hs=hsCache[c.id];
  if(hs && (hs.configured===false)){ alert('HubSpot não está configurado neste ambiente.'); return; }
  if(hs && (hs.found===false || !hs.contact)){ alert('Contato ainda não encontrado no HubSpot para esta conversa.'); return; }
  if(!confirm('Criar observação no HubSpot com TODO o histórico de WhatsApp até agora para '+c.title+'?')) return;
  try{
    const r=await api('/api/hubspot/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({conv:c.id, action:'conversation_history'})});
    alert('Observação com histórico criada no HubSpot ✓ (id '+r.id+')'+(r.dealId?' · negócio associado':''));
    try{ await saveState(c.id,{note:'[HubSpot · histórico WhatsApp] Observação criada com o histórico completo até este momento.'}); await loadAll(); }catch(e){}
  }catch(e){
    alert('Falha ao criar histórico no HubSpot: '+(e&&e.message?e.message:e));
  }
}

async function hubspotMarkTaskDone(){
  // Atalho operacional: registra uma TAREFA já CONCLUÍDA (COMPLETED) no HubSpot,
  // associada ao contato/deal da conversa. Não mexe em tarefas existentes.
  if(!active){ alert('Abra uma conversa primeiro.'); return; }
  const c=convs.find(x=>x.id===active); if(!c) return;
  const hs=hsCache[c.id];
  if(hs && (hs.configured===false)){ alert('HubSpot não está configurado neste ambiente.'); return; }
  if(hs && (hs.found===false || !hs.contact)){ alert('Contato ainda não encontrado no HubSpot para esta conversa.'); return; }
  const subject='Atividade WhatsApp realizada pelo SDR no Channel';
  const agora=new Date().toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo'});
  const bodyTxt='Atividade de WhatsApp registrada como realizada pelo SDR via Channel em '+agora+'.';
  if(!confirm('Marcar TAREFA como REALIZADA no HubSpot — prévia\n\nAssunto: '+subject+'\nStatus: Concluída (COMPLETED)\nNegócio/contato: '+c.title+'\n\n'+bodyTxt+'\n\nConfirmar?')) return;
  try{
    const r=await api('/api/hubspot/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({conv:c.id,action:'task',subject,body:bodyTxt,status:'COMPLETED',due:'none'})});
    alert('Tarefa marcada como realizada no HubSpot ✓ (id '+r.id+')'+(r.dealId?' · negócio associado':''));
    try{ await saveState(c.id,{note:'[HubSpot · tarefa realizada] '+subject}); await loadAll(); }catch(e){}
  }catch(e){ alert('Falha ao marcar tarefa realizada: '+(e&&e.message?e.message:e)); }
}

async function loadManagerOverview(){
  if(managerOverviewLoading) return;
  managerOverviewLoading=true;
  try{ managerOverview=await api('/api/manager/overview'); }
  catch(e){ managerOverview={configured:false,error:String(e&&e.message||e)}; }
  finally{ managerOverviewLoading=false; }
  if(active){ const c=convs.find(x=>x.id===active); if(c) drawContext(c); }
  if(viewMode==='foco'||viewMode==='gestao') drawCards();
}
async function loadPipelineFocus(){
  if(pipelineFocusLoading) return;
  pipelineFocusLoading=true;
  try{ pipelineFocus=await api('/api/pipeline/focus'); }
  catch(e){ pipelineFocus={configured:false,error:String(e&&e.message||e),total:0,activityBuckets:{},stageRows:[],ownerRows:[]}; }
  finally{ pipelineFocusLoading=false; }
  if(viewMode==='foco'||viewMode==='gestao') drawCards();
}
async function loadDispatchStats(force=false){
  if(dispatchStatsLoading && !force) return;
  dispatchStatsLoading=true;
  try{ dispatchStats=await api('/api/dispatch-stats?days=14'); }
  catch(e){ dispatchStats={ok:false,error:String(e&&e.message||e),days:[],chips:[],total:0}; }
  finally{ dispatchStatsLoading=false; }
  if(viewMode==='gestao') drawCards();
}
// --- Prévia read-only do limbo de Primeiro Contato / cadência segura ----------
async function loadCadenciaPreview(force){
  if(cadenciaLoading && !force) return;
  cadenciaLoading=true;
  try{ cadenciaPreview=await api('/api/cadencia/preview'); }
  catch(e){ cadenciaPreview={ok:false,message:'Não foi possível carregar a prévia: '+String(e&&e.message||e)}; }
  finally{ cadenciaLoading=false; }
  if(viewMode==='foco'||viewMode==='gestao') drawCards();
}
function fmtCadTime(iso){ try{ return new Date(iso).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}); }catch(e){ return iso; } }
function cadChipClass(key){
  if(String(key).indexOf('proximo')>=0) return 'cad-apt';
  if(key==='aguardar_24h') return 'cad-wait';
  if(key==='respondeu_nao_tocar') return 'cad-reply';
  if(key==='nutricao_marketing') return 'cad-nutri';
  return '';
}
function cadSanitClass(key){
  // Cor do chip por destino de saneamento (5 grupos).
  return ({d0_real:'cad-s-d0',reconciliar:'cad-s-rec',cadencia:'cad-apt',nao_tocar:'cad-reply',nutricao:'cad-nutri'})[key]||'';
}
function cadFonteLabel(r){
  // Indicação curta da fonte de evidência do 1º contato.
  if(r.attemptSource==='ledger') return {cls:'cad-src-ledger', txt:'fonte: ledger'};
  if(r.attemptSource==='hubspot_activity') return {cls:'cad-src-hs', txt:'fonte: atividade HubSpot'};
  return {cls:'cad-src-none', txt:'sem evidência D0'};
}
// Rótulos curtos das decisões locais (espelham CADENCIA_DECISION_ACTIONS no backend).
const CAD_DECISION_LABELS={confirmar_d0:'confirmar D0',manter_revisao:'manter revisão',tratar_d0_real:'tratar D0 real',nutricao:'nutrição'};
// Escape p/ string JS dentro de atributo onclick="" (single-quoted no JS).
function cadJq(s){return String(s==null?'':s).replace(/\\/g,'\\\\').replace(/'/g,"\\'").replace(/"/g,'&quot;').replace(/</g,'&lt;');}
// Grava (ou limpa) a decisão LOCAL de um deal e recarrega só a prévia da cadência.
async function cadDecide(dealId, action, company){
  const human=CAD_DECISION_LABELS[action]||action;
  if(action==='limpar'){ if(!confirm('Limpar decisão local de '+(company||dealId)+'?')) return; }
  else if(!confirm('Registrar decisão LOCAL «'+human+'» para '+(company||dealId)+'?\\n(não envia WhatsApp, não altera HubSpot)')) return;
  try{
    await api('/api/cadencia/decisao',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dealId:String(dealId),action})});
    await loadCadenciaPreview(true);
  }catch(e){ alert('Não foi possível gravar a decisão: '+String(e&&e.message||e)); }
}
// Controles de decisão por linha da amostra: badge+limpar se já houver decisão;
// botões pequenos se a linha precisa de revisão ou é D0 real / reconciliar_*.
function cadDecisionUI(r){
  const did=r.dealId; if(!did) return '';
  const dec=r.localDecision;
  if(dec){
    const lbl=CAD_DECISION_LABELS[dec.action]||dec.action;
    return `<div class="cad-dec-row"><span class="cad-dec">decisão: ${esc(lbl)}</span>`
      +`<button class="cad-dec-clr" onclick="cadDecide('${esc(did)}','limpar','${cadJq(r.company)}')">limpar</button></div>`;
  }
  const sb=String(r.sanitationBucket||'');
  const show = r.needsReview || sb==='d0_real' || sb.indexOf('reconciliar')===0;
  if(!show) return '';
  const c=cadJq(r.company);
  return `<div class="cad-dec-row cad-dec-btns">`
    +`<button onclick="cadDecide('${esc(did)}','confirmar_d0','${c}')">Confirmar D0</button>`
    +`<button onclick="cadDecide('${esc(did)}','manter_revisao','${c}')">Revisar</button>`
    +`<button onclick="cadDecide('${esc(did)}','tratar_d0_real','${c}')">D0 real</button>`
    +`<button onclick="cadDecide('${esc(did)}','nutricao','${c}')">Nutrição</button></div>`;
}
function cadenciaBlock(){
  const d=cadenciaPreview;
  if(!d) return `<details class="pipe-compact cad-block"><summary><span class="pc-k">Limbo Primeiro Contato</span><span class="pc-hint">carregando prévia da cadência…</span></summary></details>`;
  const safe=`<div class="focus-safe"><b>Prévia read-only.</b> Nenhum WhatsApp enviado. Nenhum HubSpot alterado. Crons intactos.${d.sampleLimit?` Amostra limitada a ${d.sampleLimit} por bucket; telefones mascarados.`:''}</div>`;
  if(!d.ok){
    return `<details class="pipe-compact cad-block"><summary><span class="pc-k">Limbo Primeiro Contato / Cadência segura</span><span class="pc-v warn">prévia indisponível</span><span class="pc-hint">${esc(d.scope||'')}</span></summary>
      <div class="cad-warn">${esc(d.message||'Prévia indisponível. Rode o dry-run read-only.')}</div>
      ${safe}
      <button class="cad-refresh" onclick="loadCadenciaPreview(true)">Atualizar após dry-run</button>
    </details>`;
  }
  const buckets=d.buckets||[], samples=d.samples||{};
  const gen=d.generatedAt?fmtCadTime(d.generatedAt):'—';
  const staleTag=d.stale?`<span class="cad-stale">prévia de ${d.ageHours}h atrás</span>`:'';
  const chips=buckets.map(b=>`<span class="cad-chip ${cadChipClass(b.key)}"><b>${b.count}</b> ${esc(b.label)}</span>`).join('')||'<span class="cad-chip">Sem leads no escopo.</span>';
  // Mapa de saneamento: resumo compacto dos 5 destinos operacionais.
  const sanit=d.sanitationBuckets||[];
  const sanitBlock=sanit.length
    ? `<div class="cad-sanit"><div class="cad-sanit-h">Mapa de saneamento</div><div class="cad-chips">${sanit.map(s=>`<span class="cad-chip ${cadSanitClass(s.key)}"><b>${s.count}</b> ${esc(s.label)}</span>`).join('')}</div></div>`
    : '';
  const sections=buckets.map(b=>{
    const rows=samples[b.key]||[];
    if(!rows.length) return '';
    const items=rows.map(r=>{
      const src=cadFonteLabel(r);
      const subj=(r.attemptSource==='hubspot_activity'||r.attemptSource==='ledger')&&r.lastHubspotActivitySubject
        ? ` · «${esc(String(r.lastHubspotActivitySubject).slice(0,42))}${String(r.lastHubspotActivitySubject).length>42?'…':''}»` : '';
      // Destino de saneamento curto + ação recomendada no title (tooltip).
      const sn=r.sanitationLabel?` · <span class="cad-sn${r.needsReview?' rev':''}">${esc(r.sanitationLabel)}${r.needsReview?' ⚑':''}</span>`:'';
      const act=r.recommendedAction?` title="${esc(r.recommendedAction)}"`:'';
      return `<div class="cad-row"${act}><div class="cad-c">${esc(r.company)}</div><div class="cad-m">${esc(r.owner)} · ${r.attempts!=null?r.attempts:0} tent.${r.hoursSinceLast!=null?' · '+r.hoursSinceLast+'h':''}${r.phoneMasked?' · '+esc(r.phoneMasked):''} · <span class="cad-src ${src.cls}">${esc(src.txt)}</span>${subj}${sn}</div>${cadDecisionUI(r)}</div>`;
    }).join('');
    const extra=b.count>rows.length?`<div class="cad-more">+${b.count-rows.length} além da amostra</div>`:'';
    return `<div class="cad-sec"><h5>${esc(b.label)} <em>${b.count}</em></h5>${items}${extra}</div>`;
  }).join('');
  // Resumo das decisões locais (não muda buckets automáticos; só informa).
  const dc=d.decisionCounts||{}; const dcKeys=Object.keys(dc);
  const decBlock = dcKeys.length
    ? `<div class="cad-decsum">Decisões locais: ${dcKeys.map(k=>`<span class="cad-chip cad-dec"><b>${dc[k]}</b> ${esc(CAD_DECISION_LABELS[k]||k)}</span>`).join('')}</div>`
    : '';
  // Lista compacta de aptos seguros para a próxima cadência (prévia, sem envio).
  const ap=d.aptos||null;
  const aptosRows=(ap&&ap.sample||[]).map(a=>`<div class="cad-row"><div class="cad-c">${esc(a.company)}</div><div class="cad-m">${esc(a.owner)}${a.phoneMasked?' · '+esc(a.phoneMasked):''}${a.nextContactNumber?' · próx '+esc(String(a.nextContactNumber))+'º':''}${a.sanitationBucket==='d0_confiavel_cadencia'?' · D0 confiável':''}</div></div>`).join('');
  const aptosBlock = ap
    ? `<div class="cad-aptos"><h5>Aptos seguros para próxima cadência <em>${ap.count||0}</em></h5>${aptosRows||'<div class="mini-empty">Sem aptos no escopo atual.</div>'}<div class="cad-aptos-note">⚑ ${esc(ap.notice||'prévia: ainda sem envio')}${ap.count>(ap.sample||[]).length?` · +${ap.count-(ap.sample||[]).length} além da amostra`:''}</div></div>`
    : '';
  const warn=d.warning?`<div class="cad-warn">${esc(d.warning)}</div>`:'';
  return `<details class="pipe-compact cad-block"><summary>
      <span class="pc-k">Limbo Primeiro Contato / Cadência segura</span>
      <span class="pc-v">${d.totalDeals||0} deals</span>
      ${staleTag}
      <span class="pc-hint">${esc(d.scope||'')} · prévia ${esc(gen)} · toque para detalhar</span>
    </summary>
    ${warn}
    ${sanitBlock}
    ${decBlock}
    <div class="cad-chips">${chips}</div>
    ${aptosBlock}
    <div class="cad-secs">${sections||'<div class="mini-empty">Sem amostra para exibir no escopo atual.</div>'}</div>
    ${safe}
    <button class="cad-refresh" onclick="loadCadenciaPreview(true)">Atualizar após dry-run</button>
  </details>`;
}
function shortTaskList(items, empty){
  if(!items||!items.length) return `<div class="mini-empty">${esc(empty)}</div>`;
  return items.slice(0,5).map(t=>`<a class="task-line" href="${esc(t.url)}" target="_blank" rel="noopener"><b>${esc(t.name||t.subject)}</b><span>${esc(t.subject)}${t.owner?' · '+esc(t.owner):''}${t.due?' · '+esc(t.due):''}</span></a>`).join('');
}
function managerOverviewView(){
  const ov=managerOverview;
  if(!ov) return '<div class="ops-card"><b>Visão comercial</b><span>Carregando HubSpot…</span></div>';
  if(ov.configured===false) return '<div class="ops-card"><b>Visão comercial</b><span>HubSpot indisponível agora.</span></div>';
  const g=ov.goal||{}, pct=Math.min(100, Math.round(((+g.done||0)/(+g.target||40))*100));
  return `<div class="section ops"><h5>Operação comercial <span class="hs">HubSpot</span></h5>
    <div class="ops-grid">
      <div class="ops-card alert"><b>${ov.overdueTotal||0}</b><span>atividades atrasadas</span></div>
      <div class="ops-card"><b>${ov.todayTotal||0}</b><span>atividades hoje</span></div>
      <div class="ops-card goal"><b>${g.done||0}/${g.target||40}</b><span>reuniões/mês</span></div>
    </div>
    <div class="goalbar"><i style="width:${pct}%"></i></div>
    <div class="goalnote">Faltam <b>${g.remaining||0}</b> · ${g.workdaysLeft||1} dias úteis · precisa ${g.perBusinessDay||0}/dia. <small>${esc(g.rule||'')}</small></div>
    <details open><summary>Atrasadas</summary>${shortTaskList(ov.overdue,'Sem atividades atrasadas.')}</details>
    <details><summary>Hoje</summary>${shortTaskList(ov.today,'Sem atividades para hoje.')}</details>
  </div>`;
}

function drawContext(c){
  const owner=ownerOf(c.port);
  const ls=localStatusOf(c);
  const hot=leadLast(c);
  // score = heurística leve (placeholder honesto): respondeu = quente
  const score=hot?78:(c.responses>0?54:32);
  const scoreColor=score>=70?'var(--accent)':score>=45?'var(--warning)':'var(--muted)';
  const ai = c.aiSummary || {};
  const next=ai.nextAction||(hot?'O lead respondeu. Responda agora para manter o ritmo da conversa.'
                :(c.responses>0?'Lead já interagiu antes. Faça follow-up com proposta de agenda.'
                :'Aguardando primeira resposta. Considere um follow-up leve em 24h.'));
  const statusLead = statusLeadOf(c);
  const auto = c.automation || {};
  document.getElementById('ctxBody').innerHTML=`
    <div class="ctx-id compact">
      <div class="top"><div class="ava" style="background:${colorFor(c.title)}">${esc(initials(c.title))}</div><div class="nm"><b>${esc(c.title)}</b><span>${esc(c.subtitle||phoneText(c))}</span></div></div>
      <div class="tags"><span class="tag ${hot?'hot':''}">${esc(statusLead)}</span><span class="tag">${c.messages} mensagens</span><span class="tag">${esc(chipLabel(c.port))}</span></div>
    </div>
${c.readOnlyInstitutional?`<div class="section"><div class="readonly-banner"><b>Auditoria institucional — não é bug.</b><br>O lead pertence ao SDR <b>${esc(leadOwnerLabel(c))}</b>. O envio foi feito usando o chip comunicador <b>${esc(senderLabel(c))}</b> para preservar capacidade/entrega. Por privacidade, esta tela mostra só o registro operacional; a resposta deve acontecer na conversa/carteira do SDR responsável.</div></div>`:`<div class="section"><div class="next"><div class="nh">⚡ Próxima ação sugerida</div><p>${esc(next)}</p><div class="nbtns"><button class="btn primary" onclick="document.getElementById('composer').focus()">Responder</button><button class="btn" onclick="hubspotAction('task')">Criar tarefa</button></div></div></div>`}
    ${ai.summary?`<div class="section"><h5>Resumo da conversa <span class="soon">auto</span></h5>
      <p style="margin:2px 0 9px;color:var(--txt);font-size:13px;line-height:1.5">${esc(ai.summary)}</p>
      ${ai.nextAction?`<div class="kv"><span class="k">Próxima ação</span><span class="v">${esc(ai.nextAction)}</span></div>`:''}
      ${ai.signals&&ai.signals.length?`<div class="tags" style="margin-top:9px">${ai.signals.map(s=>`<span class="tag">${esc(s)}</span>`).join('')}</div>`:''}
    </div>`:''}
    <div class="section"><h5>Ações rápidas</h5>
      <div class="nbtns" style="display:flex;gap:7px;flex-wrap:wrap">
        <button class="btn ${ls==='pending'?'primary':''}" onclick="convState('pending')">◷ Pendente</button>
        <button class="btn ${ls==='resolved'?'primary':''}" onclick="convState('resolved')">✓ Resolvido</button>
        <button class="btn" onclick="hubspotConversationHistory()">⇪ Histórico HubSpot</button>
        <button class="btn" onclick="hubspotAction('task','followup')">＋ Follow-up hoje</button>
        <button class="btn" onclick="hubspotMarkTaskDone()">✓ Tarefa realizada</button>
      </div>
      ${c.localNote?`<div class="kv" style="margin-top:10px"><span class="k">Nota interna</span><span class="v" title="${esc(c.localNote)}">${esc(c.localNote)}</span></div>`:''}
    </div>
    <div class="section"><h5>Lead e formulário <span class="hs">HubSpot</span></h5>
      <div id="hsBody">${hsCache[c.id]?hubspotView(c,owner,statusLead,hsCache[c.id]):hubspotLoadingView(c,owner,statusLead)}</div>
    </div>
    <div class="section"><h5>Resumo rápido</h5>
      <div class="kv"><span class="k">Cadência</span><span class="v">${esc(cadenceProgress(c))} · ${esc(cadenceNextAction(c))}</span></div>
      <div class="kv"><span class="k">Canal sugerido</span><span class="v">${esc(routeSuggestion(c).kind)} · ${esc(routeSuggestion(c).reason)}</span></div>
      <div class="kv"><span class="k">Mensagens</span><span class="v">${c.messages} total · ${c.responses||0} resposta(s)</span></div>
      <div class="kv"><span class="k">Última</span><span class="v">${esc(c.lastSource||'')} · ${esc(dt(c.lastTime))}</span></div>
      ${ai.summary?`<div class="kv"><span class="k">Resumo</span><span class="v">${esc(ai.summary)}</span></div>`:''}
    </div>
    <div class="ctx-channel"><span class="k">Canal WhatsApp usado</span><span class="v">${esc(chipLabel(c.port))}</span><button class="ctx-channel-link" onclick="openConnections()">Conexões</button></div>`;
}

/* ---------- actions ---------- */
function setQueue(k){queue=k; renderQueues(); drawCards()}
function setSort(s){sortMode=s; document.querySelectorAll('.seg button').forEach(b=>b.classList.toggle('on',b.dataset.sort===s)); drawCards()}
function setFilter(){} // noop — filtros SDR/chip removidos da UI (não há pills nem #filters)
function toggleHubspotFilter(){hubspotFilter=!hubspotFilter; drawCards();}
function agendaLinkForOwner(uid){return ({breno:'https://meetings.hubspot.com/breno-mendonca',lucas_batista:'https://meetings.hubspot.com/lucas-alcantara-nogueira-batista',sarah:'https://meetings.hubspot.com/sarah-bento'})[uid]||'https://meetings.hubspot.com/zydon'}
function draftAgendaLink(){
  const c=convs.find(x=>x.id===active)||{}; const owner=ownerUidOfConv(c)||''; const emp=companyForActive();
  const text=`Perfeito. Para facilitar, você pode escolher o melhor horário por aqui: ${agendaLinkForOwner(owner)}\n\nAssim já deixamos a conversa sobre a ${emp} organizada com o consultor responsável.`;
  setMode('reply'); const ta=document.getElementById('composer'); ta.value=text; ta.focus(); ta.dispatchEvent(new Event('input'));
}
function renderPlaybooks(){
  const el=document.getElementById('playbookPanel'); if(!el) return;
  const c=convs.find(x=>x.id===active)||{};
  const rt=active?routeSuggestion(c):null;
  const route=rt?` Canal sugerido: <b>${esc(rt.kind)}</b> <span title="${esc(rt.reason)}">(${esc(rt.reason)})</span>.`:'';
  const cad=active?`<div class="pb-intro"><b>Cadência manual segura:</b> ${esc(cadenceProgress(c))} · próxima ação sugerida: <b>${esc(cadenceNextAction(c))}</b>.${route} Objetivo: chegar até 4 atividades úteis antes de perder/nutrir. Nada é enviado sozinho.</div>`:'';
  el.innerHTML=`
  ${cad}
  <div class="pb-intro">Fluxos guiados para a operação do SDR. <b>Nada é enviado sem você revisar:</b> rascunhos vão para o WhatsApp e só você dispara; toda ação no HubSpot mostra uma prévia antes de gravar.</div>
  <div class="pb-group"><div class="pb-group-h">Comunicação</div><div class="pb-grid">
    <div class="pb-card"><b>Mandar agenda</b><span>Preenche o WhatsApp com o link de agenda do owner. Não envia sozinho.</span><button onclick="draftAgendaLink()">Gerar rascunho</button></div>
    <div class="pb-card"><b>2º contato</b><span>Rascunho calmo e personalizado para quem recebeu o D0 e não respondeu.</span><button onclick="showSecondContact()">Abrir</button></div>
    <div class="pb-card"><b>3º contato</b><span>Rascunho com um insight/relevância seu para reativar o lead.</span><button onclick="showThirdContact()">Abrir</button></div>
  </div></div>
  <div class="pb-group"><div class="pb-group-h">Cadência segura</div><div class="pb-grid">
    <div class="pb-card"><b>No-show / Retomada</b><span>Rascunho + tarefa para retomar quem faltou. Não muda etapa do negócio.</span><button onclick="showNoShow()">Abrir</button></div>
    <div class="pb-card"><b>Despedida / Nutrição</b><span>Encerramento elegante + nota/tarefa de nutrição. Não envia sozinho.</span><button onclick="showFarewell()">Abrir</button></div>
  </div></div>
  <div class="pb-group"><div class="pb-group-h">HubSpot / CRM</div><div class="pb-grid">
    <div class="pb-card"><b>Follow-up hoje</b><span>Cria tarefa no HubSpot associada ao contato/negócio.</span><button onclick="hubspotAction('task','followup')">Criar tarefa</button></div>
    <div class="pb-card"><b>Histórico no HubSpot</b><span>Registra o histórico permitido da conversa como nota.</span><button onclick="hubspotConversationHistory()">Registrar</button></div>
    <div class="pb-card"><b>Handoff / Introdução</b><span>Move negócio para Introdução, troca owner e registra auditoria.</span><button onclick="showIntroPlaybook()">Abrir</button></div>
  </div></div>
  <div id="pbForm"></div>`;
}
/* ---- Playbooks guiados: rascunho WhatsApp (revisado pelo SDR) + HubSpot com prévia ---- */
function contactFirstName(){
  const c=convs.find(x=>x.id===active)||{}; const hs=hsCache[c.id]||{}; const ct=hs.contact||{};
  let n=String(ct.firstname||'').trim();
  if(!n){ const full=String(hsName(ct)||c.subtitle||'').trim(); n=full.split(/\s+/)[0]||''; }
  if(/^\+?\d/.test(n)) n='';
  return n;
}
function _pbVal(id){ const e=document.getElementById(id); return e?String(e.value||'').trim():''; }
function pbDraftSecond(){
  const nome=contactFirstName(), emp=companyForActive();
  const greet=nome?`Oi ${nome}, tudo bem?`:'Oi, tudo bem?';
  const core={
    retomada:`Passando para retomar nossa conversa sobre a ${emp}. Sem pressa — sigo à disposição para te ajudar quando fizer sentido para você.`,
    valor:`Continuo por aqui caso queira entender como a Zydon pode ajudar a ${emp} a vender mais sem depender só do vendedor. Qualquer dúvida, é só me chamar.`,
    leve:`Só passando para saber se faz sentido seguirmos a conversa sobre a ${emp}. Se não for o momento, sem problema — é só me avisar por aqui.`,
  }[_pbVal('pbTone')||'retomada'];
  return `${greet} ${core}`;
}
function pbDraftThird(){
  const nome=contactFirstName(), emp=companyForActive();
  const greet=nome?`Oi ${nome}!`:'Oi!';
  const insight=_pbVal('pbInsight');
  const ins=insight?` ${insight}`:` Vi um movimento no seu segmento que me lembrou da ${emp}.`;
  return `${greet} Lembrei de você por aqui.${ins} Acho que vale trocarmos uma ideia rápida sobre a ${emp}. Posso te enviar um horário para conversarmos?`;
}
function pbDraftFarewell(){
  const nome=contactFirstName(), emp=companyForActive();
  const greet=nome?`Oi ${nome},`:'Oi,';
  return {
    respeitoso:`${greet} imagino que esse não seja o melhor momento para falar sobre a ${emp} — totalmente compreensível. Vou pausar meus contatos por aqui para não te incomodar. Se mudar de ideia, é só me chamar. Sucesso! 🙌`,
    porta:`${greet} vou deixar nossa conversa sobre a ${emp} em standby por enquanto, sem pressa nenhuma. Continuo por aqui e, quando fizer sentido para você, é só dar um sinal. Conte comigo! 🙂`,
  }[_pbVal('pbTone')||'respeitoso'];
}
function pbDraftNoShow(){
  const nome=contactFirstName(), emp=companyForActive();
  const greet=nome?`Oi ${nome}!`:'Oi!';
  return `${greet} Acho que nos desencontramos no horário que combinamos — acontece! Quer que eu te envie uma nova opção para conversarmos sobre a ${emp}? Fico no aguardo. 🙂`;
}
function pbRecalc(kind){
  const map={second:pbDraftSecond,third:pbDraftThird,farewell:pbDraftFarewell,noshow:pbDraftNoShow};
  const fn=map[kind], t=document.getElementById('pbPreview'); if(fn&&t) t.value=fn();
}
function pbToComposer(){
  const t=document.getElementById('pbPreview'); const txt=t?t.value:'';
  if(!txt||!txt.trim()) return alert('Rascunho vazio. Gere o texto antes.');
  setMode('reply'); const ta=document.getElementById('composer'); ta.value=txt; ta.focus(); ta.dispatchEvent(new Event('input'));
}
function _pbHubspotReady(){
  if(!active){ alert('Abra uma conversa primeiro.'); return null; }
  const c=convs.find(x=>x.id===active); if(!c) return null;
  const hs=hsCache[c.id];
  if(hs && hs.configured===false){ alert('HubSpot não está configurado neste ambiente.'); return null; }
  if(hs && (hs.found===false || !hs.contact)){ alert('Contato ainda não encontrado no HubSpot para esta conversa.'); return null; }
  return c;
}
async function pbCreateTask(subject, body, due){
  const c=_pbHubspotReady(); if(!c) return;
  due=due||'today';
  const dueLabel={today:'hoje',tomorrow:'amanhã',none:'sem data'}[due]||'hoje';
  if(!confirm(`Criar TAREFA no HubSpot — prévia\n\nAssunto: ${subject}\nVencimento: ${dueLabel}\nNegócio/contato: ${c.title}\n\nDescrição:\n${body}\n\nConfirmar?`)) return;
  try{
    const r=await api('/api/hubspot/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({conv:c.id,action:'task',subject,body,due})});
    alert('Tarefa criada no HubSpot ✓ (id '+r.id+')'+(r.dealId?' · negócio associado':''));
    try{ await saveState(c.id,{note:'[HubSpot · tarefa] '+subject+' — '+body}); await loadAll(); }catch(e){}
  }catch(e){ alert('Falha ao criar tarefa: '+(e&&e.message?e.message:e)); }
}
async function pbCreateNote(body){
  const c=_pbHubspotReady(); if(!c) return;
  if(!confirm(`Registrar NOTA no HubSpot — prévia\n\nNegócio/contato: ${c.title}\n\n${body}\n\nConfirmar?`)) return;
  try{
    const r=await api('/api/hubspot/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({conv:c.id,action:'note',body})});
    alert('Nota criada no HubSpot ✓ (id '+r.id+')'+(r.dealId?' · negócio associado':''));
    try{ await saveState(c.id,{note:'[HubSpot · nota] '+body}); await loadAll(); }catch(e){}
  }catch(e){ alert('Falha ao criar nota: '+(e&&e.message?e.message:e)); }
}
function pbTaskBody(kind){
  const emp=companyForActive(); const draft=_pbVal('pbPreview');
  return `Playbook ${kind} (Channel) — ${emp}.`+(draft?`\nRascunho preparado:\n${draft}`:'');
}
function showSecondContact(){
  if(!active) return alert('Abra uma conversa primeiro.');
  const f=document.getElementById('pbForm'); if(!f) return;
  f.innerHTML=`<div class="pb-form">
    <b>2º contato — retomada calma</b>
    <label>Tom da mensagem<select id="pbTone" onchange="pbRecalc('second')">
      <option value="retomada">Retomar com leveza</option>
      <option value="valor">Reforçar valor</option>
      <option value="leve">Pergunta leve</option>
    </select></label>
    <label>Prévia do WhatsApp (pode editar antes de enviar)<textarea id="pbPreview" rows="4"></textarea></label>
    <div class="pb-actions">
      <button onclick="renderPlaybooks()">Cancelar</button>
      <button onclick="pbRecalc('second')">Recalcular</button>
      <button class="primary" onclick="pbToComposer()">Pôr no WhatsApp</button>
      <button class="hs" onclick="pbCreateTask('2º contato WhatsApp', pbTaskBody('2º contato'), 'today')">Criar tarefa hoje</button>
    </div>
    <div class="pb-hint">O rascunho não é enviado: revise e dispare você mesmo na aba WhatsApp.</div>
  </div>`;
  pbRecalc('second');
}
function showThirdContact(){
  if(!active) return alert('Abra uma conversa primeiro.');
  const f=document.getElementById('pbForm'); if(!f) return;
  f.innerHTML=`<div class="pb-form">
    <b>3º contato — com relevância</b>
    <label>Insight / relevância (uma frase sua, opcional)<input id="pbInsight" oninput="pbRecalc('third')" placeholder="ex: vi que vocês abriram uma nova unidade…"></label>
    <label>Prévia do WhatsApp (pode editar antes de enviar)<textarea id="pbPreview" rows="4"></textarea></label>
    <div class="pb-actions">
      <button onclick="renderPlaybooks()">Cancelar</button>
      <button onclick="pbRecalc('third')">Recalcular</button>
      <button class="primary" onclick="pbToComposer()">Pôr no WhatsApp</button>
      <button class="hs" onclick="pbCreateTask('3º contato WhatsApp', pbTaskBody('3º contato'), 'today')">Criar tarefa hoje</button>
    </div>
    <div class="pb-hint">Campo guiado: escreva um fato relevante seu. Não é IA — o texto é só seu insight.</div>
  </div>`;
  pbRecalc('third');
}
function showNoShow(){
  if(!active) return alert('Abra uma conversa primeiro.');
  const f=document.getElementById('pbForm'); if(!f) return;
  f.innerHTML=`<div class="pb-form">
    <b>No-show / Retomada</b>
    <label>Quando retomar (tarefa)<select id="pbDue"><option value="today">Hoje</option><option value="tomorrow">Amanhã</option></select></label>
    <label>Observação interna (opcional)<input id="pbObs" placeholder="ex: faltou na reunião das 15h"></label>
    <label>Prévia do WhatsApp (pode editar antes de enviar)<textarea id="pbPreview" rows="4"></textarea></label>
    <div class="pb-actions">
      <button onclick="renderPlaybooks()">Cancelar</button>
      <button onclick="pbRecalc('noshow')">Recalcular</button>
      <button class="primary" onclick="pbToComposer()">Pôr no WhatsApp</button>
      <button class="hs" onclick="pbCreateNoShowTask()">Criar tarefa de retomada</button>
    </div>
    <div class="pb-hint">Este playbook não altera a etapa do negócio — só cria rascunho/tarefa segura.</div>
  </div>`;
  pbRecalc('noshow');
}
function pbCreateNoShowTask(){
  const due=_pbVal('pbDue')||'today', obs=_pbVal('pbObs'), emp=companyForActive();
  const body=`Retomar no-show — ${emp}.`+(obs?` Obs: ${obs}.`:'')+(_pbVal('pbPreview')?`\nRascunho:\n${_pbVal('pbPreview')}`:'');
  pbCreateTask('Retomar no-show', body, due);
}
function showFarewell(){
  if(!active) return alert('Abra uma conversa primeiro.');
  const f=document.getElementById('pbForm'); if(!f) return;
  f.innerHTML=`<div class="pb-form">
    <b>Despedida / Nutrição</b>
    <label>Tom do encerramento<select id="pbTone" onchange="pbRecalc('farewell')">
      <option value="respeitoso">Encerramento respeitoso</option>
      <option value="porta">Porta aberta</option>
    </select></label>
    <label>Prévia do WhatsApp (pode editar antes de enviar)<textarea id="pbPreview" rows="4"></textarea></label>
    <div class="pb-actions">
      <button onclick="renderPlaybooks()">Cancelar</button>
      <button onclick="pbRecalc('farewell')">Recalcular</button>
      <button class="primary" onclick="pbToComposer()">Pôr no WhatsApp</button>
      <button class="hs" onclick="pbFarewellNote()">Nota de nutrição</button>
      <button class="hs" onclick="pbFarewellTask()">Tarefa de retomada</button>
    </div>
    <div class="pb-hint">Encerramento elegante. A nota/tarefa de nutrição registra a retomada futura, sem mudar etapa.</div>
  </div>`;
  pbRecalc('farewell');
}
function pbFarewellNote(){
  const emp=companyForActive();
  pbCreateNote(`Lead em NUTRIÇÃO (Channel) — ${emp}. Encerramento cordial enviado/proposto. Retomar quando houver novo gatilho (~30 dias).`);
}
function pbFarewellTask(){
  const emp=companyForActive();
  pbCreateTask('Retomar lead (nutrição)', `Retomada futura do lead ${emp} após nutrição. Sem data fixa — reavaliar o contexto antes de reabrir.`, 'none');
}
function showIntroPlaybook(){
  const c=convs.find(x=>x.id===active)||{}; const hs=hsCache[c.id]||{}; const d=(hs.deals&&hs.deals[0])||{}; const f=document.getElementById('pbForm');
  if(!f) return;
  f.innerHTML=`<div class="pb-form">
    <b>Handoff / Passar para Introdução</b>
    <label>Negócio<input id="pbDeal" disabled value="${esc(d.dealname||'Negócio da conversa')}"></label>
    <label>Novo proprietário<select id="pbOwner"><option value="">Não alterar</option><option value="86265630">Breno</option><option value="88063842">Sarah</option><option value="85778446">Lucas Batista</option></select></label>
    <label>Campo extra opcional (nome técnico HubSpot)<input id="pbField" placeholder="ex: responsavel_pt"></label>
    <label>Valor do campo extra<input id="pbValue" placeholder="ex: Nome X"></label>
    <label>Observação / contexto<textarea id="pbNote" rows="2" placeholder="Ex: lead levantou a mão, pediu introdução..."></textarea></label>
    <div class="pb-actions"><button onclick="renderPlaybooks()">Cancelar</button><button class="primary" onclick="executeIntroPlaybook()">Prévia e executar</button></div>
  </div>`;
}
async function executeIntroPlaybook(){
  if(!active) return alert('Abra uma conversa primeiro.');
  const c=convs.find(x=>x.id===active)||{}; const hs=hsCache[c.id]||{}; const d=(hs.deals&&hs.deals[0])||{};
  const ownerId=document.getElementById('pbOwner')?.value||''; const fieldName=document.getElementById('pbField')?.value.trim()||''; const fieldValue=document.getElementById('pbValue')?.value.trim()||''; const note=document.getElementById('pbNote')?.value.trim()||'';
  const ownerLabel=({'86265630':'Breno','88063842':'Sarah','85778446':'Lucas Batista'})[ownerId]||'sem alteração';
  const preview=`Playbook: Handoff / Introdução\n\nNegócio: ${d.dealname||c.title}\nEtapa: Introdução\nNovo proprietário: ${ownerLabel}\nCampo extra: ${fieldName&&fieldValue?fieldName+' = '+fieldValue:'nenhum'}\n\nConfirmar execução no HubSpot?`;
  if(!confirm(preview)) return;
  try{
    const r=await api('/api/hubspot/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({conv:active,action:'playbook',playbook:'intro_handoff',stageId:'1269308723',ownerId,fieldName,fieldValue,note})});
    alert('Playbook executado ✓ Negócio '+(r.dealId||'')+' atualizado.');
    try{ await saveState(active,{note:'[Playbook] Handoff / Introdução executado no HubSpot.'}); }catch(e){}
    delete hsCache[active]; await loadAll(); await openConv(active,true); setMode('playbook');
  }catch(e){ alert('Falha no playbook: '+(e&&e.message?e.message:e)); }
}
function setMode(m){
  mode=m; const isPb=m==='playbook';
  document.getElementById('tabReply').classList.toggle('on',m==='reply');
  const tp=document.getElementById('tabPlaybook'); if(tp) tp.classList.toggle('on',isPb);
  const tn=document.getElementById('tabNote'); tn.classList.toggle('on',m==='note'); tn.classList.toggle('noteon',m==='note');
  const box=document.getElementById('cbox'); box.classList.toggle('note',m==='note');
  const panel=document.getElementById('playbookPanel'); if(panel){ panel.hidden=!isPb; if(isPb) renderPlaybooks(); }
  const input=document.querySelector('.cinput-row'); const hint=document.querySelector('.chint'); const attach=document.getElementById('attachRow');
  if(input) input.style.display=isPb?'none':''; if(hint) hint.style.display=isPb?'none':''; if(attach&&!isPb&&pendingFile) attach.hidden=false;
  const ta=document.getElementById('composer'); ta.placeholder=m==='note'?'Nota interna — visível só para o time, não vai ao lead…':'Responder por este chip…';
  const sb=document.getElementById('sendBtn'); sb.classList.toggle('note',m==='note'); document.getElementById('sendLabel').textContent=m==='note'?'Salvar nota':'Enviar';
}
function toggleCtx(force){const app=document.getElementById('app'); if(force===false) app.classList.remove('ctx-open'); else app.classList.toggle('ctx-open')}
function mobileBack(){document.getElementById('app').classList.remove('conv-open')}

function applyReadonlyComposer(c){
  const ro=!!(c&&c.readOnlyInstitutional);
  const composerBox=document.querySelector('.conversation .composer');
  const cbox=document.getElementById('cbox');
  const quick=document.getElementById('quick');
  const route=document.getElementById('routeNote');
  const ta=document.getElementById('composer');
  const send=document.getElementById('sendBtn');
  const attach=document.getElementById('attachBtn');
  if(composerBox) composerBox.classList.toggle('readonly-mode', ro);
  if(cbox) cbox.hidden=ro;
  if(quick) quick.style.display=ro?'none':'';
  if(ta){ ta.disabled=ro; ta.placeholder=ro?'':`Responder pelo chip ${c.sendPortLabel||chipLabel(c.sendPort||c.port)}…`; }
  if(send) send.disabled=ro;
  if(attach) attach.disabled=ro;
  if(route && ro){ route.hidden=true; route.textContent=''; }
  let help=document.getElementById('readonlyHelp');
  if(!help){ help=document.createElement('div'); help.id='readonlyHelp'; help.className='readonly-help'; const host=document.querySelector('.conversation .composer'); if(host) host.insertBefore(help, host.firstChild); }
  if(help){
    help.hidden=!ro;
    help.innerHTML=ro?`<b>Somente leitura:</b> envio feito por ${esc(senderLabel(c))} para lead do SDR ${esc(leadOwnerLabel(c))}. Esta tela é só auditoria; para responder, abra a conversa/carteira do SDR responsável.`:'';
  }
}

async function transcribePendingAudioForActive(convId){
  const m=(msgs||[]).find(audioNeedsTranscript);
  if(!m) return;
  try{
    await api('/api/transcribe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({conv:convId,msgId:m.id})});
    if(active!==convId) return;
    const d=await api('/api/messages?conv='+encodeURIComponent(convId));
    if(active!==convId) return;
    msgs=d.messages||[];
    drawTimeline(); drawCards();
  }catch(e){ /* transcrição é best-effort; áudio já está visível */ }
}

async function openConv(id, keep){
  active=id;
  const c=convs.find(x=>x.id===id)||{};
  const tlBefore=document.getElementById('timeline');
  const preserveScroll=!!keep && !!tlBefore;
  const prevScrollTop=preserveScroll?tlBefore.scrollTop:0;
  const prevScrollHeight=preserveScroll?tlBefore.scrollHeight:0;
  const wasNearBottom=preserveScroll ? (tlBefore.scrollHeight - tlBefore.scrollTop - tlBefore.clientHeight < 80) : true;
  if(!keep){ document.getElementById('app').classList.add('conv-open'); }
  drawHead(c); drawContext(c); renderQuick(); if(mode==='playbook') renderPlaybooks();
  // Performance: timeline primeiro. HubSpot é contexto auxiliar e não pode competir
  // com /api/messages nem causar “Carregando mensagens” em horário de operação.
  const shouldLoadHubspot=!hsCache[c.id];
  const route=document.getElementById('routeNote');
  const ro=!!c.readOnlyInstitutional;
  if(route && !ro){
    route.hidden=!c.sendRoutingChanged;
    route.textContent=c.sendRoutingChanged ? (c.sendRoutingReason||`Enviando por ${c.sendPortLabel||chipLabel(c.sendPort)} para equilibrar os chips.`) : '';
  }
  applyReadonlyComposer(c);
  if(!ro && mode!=='playbook'){
    const input=document.querySelector('.cinput-row'); const hint=document.querySelector('.chint');
    if(input) input.style.display=''; if(hint) hint.style.display='';
  }
  const tl=document.getElementById('timeline');
  let loadingTimer=null;
  if(!keep && tl){
    // Não piscar “Carregando mensagens” para requests normais (<350ms).
    // Se aparecer por segundos, é sinal real de gargalo/timeout, não estado normal.
    loadingTimer=setTimeout(()=>{
      if(active===id) tl.innerHTML=`<div class="empty"><b>Carregando mensagens…</b><span>Se houver áudio, ele aparece primeiro e a transcrição vem em seguida.</span></div>`;
    },350);
  }
  try{
    const d=await api('/api/messages?conv='+encodeURIComponent(id));
    if(loadingTimer) clearTimeout(loadingTimer);
    if(active!==id) return;
    msgs=d.messages||[];
  }catch(e){
    if(loadingTimer) clearTimeout(loadingTimer);
    if(active!==id) return;
    if((msgs||[]).length){
      // Mantém histórico anterior em vez de piscar “Sem mensagens”.
    }else if(tl){
      tl.innerHTML=`<div class="empty"><b>Não consegui carregar mensagens agora</b><span>A conexão demorou. Vou tentar de novo automaticamente; clique em Atualizar se precisar.</span></div>`;
      return;
    }
  }
  drawTimeline(!preserveScroll || wasNearBottom);
  if(preserveScroll && !wasNearBottom){
    const tlAfter=document.getElementById('timeline');
    if(tlAfter){
      const delta=tlAfter.scrollHeight-prevScrollHeight;
      tlAfter.scrollTop=Math.max(0, prevScrollTop + Math.max(0, delta));
    }
  }
  updateActiveCard(id);
  if(shouldLoadHubspot){
    setTimeout(()=>{ if(active===id && !hsCache[id] && !document.hidden) loadHubspot(c); }, 1800);
  }
  transcribePendingAudioForActive(id);
}

/* ---- CH-018: anexo de arquivo/áudio ---- */
let pendingFile=null;
function onFilePicked(input){
  const f=input.files&&input.files[0];
  if(!f){ clearAttachment(); return; }
  if(f.size>20*1024*1024){ alert('Arquivo acima de 20MB. Escolha um menor.'); clearAttachment(); return; }
  pendingFile=f;
  document.getElementById('attachName').textContent=f.name;
  document.getElementById('attachRow').hidden=false;
}
function clearAttachment(){
  pendingFile=null;
  const inp=document.getElementById('fileInput'); if(inp) inp.value='';
  const row=document.getElementById('attachRow'); if(row) row.hidden=true;
  const nm=document.getElementById('attachName'); if(nm) nm.textContent='';
}
function readAsDataURL(file){
  return new Promise((resolve,reject)=>{
    const fr=new FileReader();
    fr.onload=()=>resolve(fr.result);
    fr.onerror=()=>reject(new Error('Falha ao ler o arquivo'));
    fr.readAsDataURL(file);
  });
}

/* ---- Proteção contra duplo envio ----
   Root cause: Enter podia chamar sendReply() repetidas vezes enquanto a primeira
   requisição ainda aguardava rede/bridge. Desabilitar o botão não bloqueia
   keydown no textarea. Usamos trava global + limpeza imediata do composer. */
let sendInFlight=false;
function newClientMessageId(){
  try{ if(window.crypto&&crypto.randomUUID) return crypto.randomUUID(); }catch(e){}
  return String(Date.now())+'-'+Math.random().toString(16).slice(2);
}
function setSending(on){
  sendInFlight=!!on;
  const btn=document.getElementById('sendBtn');
  if(btn){ btn.disabled=!!on; const lbl=document.getElementById('sendLabel'); if(lbl) lbl.textContent=on?'Enviando…':'Enviar'; }
  const ta=document.getElementById('composer'); if(ta) ta.disabled=!!on;
  const attach=document.getElementById('attachBtn'); if(attach) attach.disabled=!!on;
}
async function sendReply(){
  if(sendInFlight) return;
  if(!active) return alert('Selecione uma conversa');
  const ta=document.getElementById('composer'); const text=ta.value.trim();
  if(mode==='note'){
    // CH-010: salva nota interna no backend (local-only, nunca vai ao lead).
    if(!text) return;
    setSending(true);
    const prevH=ta.style.height;
    try{
      await saveState(active,{note:text});
      ta.value=''; ta.style.height='auto';
      setMode('reply');
      await loadAll(); await openConv(active,true);
    }catch(e){
      if(!ta.value){ ta.value=text; ta.style.height=prevH||'auto'; }
      alert('Falha ao salvar nota: '+e.message);
    }finally{ setSending(false); }
    return;
  }
  if(!text && !pendingFile) return;
  const [origPort,chat]=active.split('::');
  // CH-042: envia pelo chip recomendado (mesmo dono/permitido, mais saudável);
  // o chat destino é sempre o mesmo. Sem recomendação -> porta original.
  const c=convs.find(x=>x.id===active)||{};
  if(c.readOnlyInstitutional) return alert('Esse é um registro institucional somente leitura. Não é permitido responder por chip pessoal da Mariana, Rafael ou Lucas Resende.');
  const port=String((c.sendPort!=null?c.sendPort:origPort));
  const file=pendingFile;
  const payloadText=text;
  const prevHeight=ta.style.height;
  setSending(true);
  // Feedback imediato: impede novo Enter no mesmo texto durante delay de rede.
  ta.value=''; ta.style.height='auto';
  try{
    if(file){
      const dataUrl=await readAsDataURL(file);
      await api('/api/send-file',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({port:+port,chat,fileName:file.name,mime:file.type||'',dataBase64:dataUrl,caption:payloadText,clientMessageId:newClientMessageId()})});
      clearAttachment();
      await loadAll(); await openConv(active,true);
    }else{
      await api('/api/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({port:+port,chat,text:payloadText,clientMessageId:newClientMessageId()})});
      await loadAll(); await openConv(active,true);
    }
  }catch(e){
    // Se falhar, restaura texto para o SDR não perder a mensagem.
    if(payloadText && !ta.value){ ta.value=payloadText; ta.style.height=prevHeight||'auto'; }
    alert('Falha ao enviar: '+e.message);
  }
  finally{ setSending(false); }
}

// CH-RT/UX: reflete no rótulo "ao vivo" quando a inbox foi atualizada pela última
// vez. Se a aba está em segundo plano o polling pausa, então mostramos "pausado".
function updateLiveStatus(){
  const el=document.getElementById('liveStatus'); if(!el) return;
  const txt=el.querySelector('.live-txt'), ago=el.querySelector('.live-ago');
  if(document.hidden){
    el.classList.add('paused');
    if(txt) txt.textContent='pausado';
    if(ago) ago.textContent='';
    return;
  }
  el.classList.remove('paused');
  if(txt) txt.textContent='ao vivo';
  if(ago){
    if(!lastInboxUpdatedAt){ ago.textContent=''; return; }
    const s=Math.max(0,Math.round((Date.now()-lastInboxUpdatedAt)/1000));
    ago.textContent = s<5 ? '· atualizado agora' : (s<60 ? '· há '+s+'s' : '· há '+Math.round(s/60)+'min');
  }
}
// CH-RT/UX: quando uma conversa nova assume o topo, destaca por ~8s sem alert.
function markNewTop(id){
  newTopConvId=id;
  if(newTopTimer) clearTimeout(newTopTimer);
  newTopTimer=setTimeout(()=>{ newTopConvId=''; if(viewMode==='conversas') drawCards(); },8000);
}
async function loadAll(opts={}){
  // Em telas analíticas, não recalcule a inbox inteira em background.
  // Foco/Gestão têm rota e carga própria; competir com /api/messages derrubava fluidez.
  if((viewMode==='foco'||viewMode==='gestao') && !opts.force && opts.fast){
    if(!pipelineFocus && !pipelineFocusLoading) loadPipelineFocus();
    updateLiveStatus();
    return;
  }
  // CH-RT: a inbox precisa refletir diagnóstico/primeiro contato quase em tempo real.
  // Antes o polling era 15s e sempre puxava blocos pesados; no mobile parecia que
  // precisava F5. Agora /api/conversations roda rápido (3s quando visível) e as
  // cargas pesadas continuam no máximo a cada 30s.
  if(loadAllInFlight && !opts.force) return;
  loadAllInFlight=true;
  try{
    const d=await api('/api/conversations',{timeoutMs: opts.fast?9000:20000});
    let incoming=d.conversations||[];
    if(!incoming.length){
      try{
        const d2=await api('/api/conversations-safe',{timeoutMs:12000});
        if((d2.conversations||[]).length) { incoming=d2.conversations||[]; d.user=d2.user||d.user; }
      }catch(_e){}
    }
    const prevFirst=(convs[0]&&convs[0].id)||'';
    convs=incoming; me=d.user;
    lastInboxUpdatedAt=Date.now();
    // Card novo no topo: marca antes de desenhar para o destaque já sair no 1º draw.
    if(prevFirst && convs[0] && convs[0].id!==prevFirst && viewMode==='conversas') markNewTop(convs[0].id);
    portMeta={}; (me.ports||[]).forEach(p=>portMeta[p.port]=p);
    document.getElementById('meName').textContent=me.name;
    document.getElementById('meSub').textContent=(me.admin?'Admin · ':(me.view_all?'Supervisor · ':''))+(me.ports||[]).length+' conexões';
    const ava=document.getElementById('meAva'); ava.textContent=initials(me.name); ava.style.background=colorFor(me.name);
    renderQueues(); drawCards();
    if(deepConv && !deepConvOpened){
      deepConvOpened=true;
      setViewMode('conversas',{skipHistory:true});
      openConv(deepConv,true);
    }
    scheduleIdentityHydration('load');
    const now=Date.now();
    if(!opts.fast || now-lastHeavyLoad>30000){
      lastHeavyLoad=now;
      loadChips();
      if(viewMode==='foco'||viewMode==='gestao') loadPipelineFocus();
    }
    updateLiveStatus();
  }catch(e){
    if(!opts.fast){
      const root=document.getElementById('root');
      const isAuthError=e && (e.status===401 || e.status===403);
      if(isAuthError){
        root.innerHTML='<div class="login"><h2>Sessão expirada / acesso negado</h2><p>'+esc(e.message)+'</p><p><a href="/login" style="color:#CDEB00">Fazer login novamente</a></p></div>';
      }else{
        root.innerHTML='<div class="login"><h2>Não consegui carregar o inbox agora</h2><p>'+esc(e.message||'Falha temporária ao carregar conversas.')+'</p><p>Não é logout. Sua sessão continua válida; tente recarregar.</p><p><button class="btn primary" onclick="location.reload()">Atualizar</button></p></div>';
      }
    }
  }finally{
    loadAllInFlight=false;
  }
}

renderShell();
setViewMode(initialViewModeFromPath(), {skipHistory:true});
window.addEventListener('popstate',()=>setViewMode(initialViewModeFromPath(), {skipHistory:true}));
loadAll({force:true});
setInterval(()=>{ if(!document.hidden) loadAll({fast:true}); },45000);
setInterval(()=>loadAll({fast:false}),180000);
setInterval(()=>{ const composing=document.activeElement && document.activeElement.id==='composer'; if(!document.hidden && active && !composing) openConv(active,true); },30000);
setInterval(updateLiveStatus,10000);
document.addEventListener('visibilitychange',()=>{ updateLiveStatus(); if(!document.hidden){ loadAll({fast:true}); } });
window.addEventListener('focus',()=>{ updateLiveStatus(); });
</script></body></html>'''

def background_refresh_conversations(uid, cache_key):
    def run():
        try:
            convs=conversations(uid)
            with CONVERSATIONS_API_LOCK:
                CONVERSATIONS_API_CACHE[cache_key]={'ts':time.time(),'conversations':convs}
        except Exception as e:
            try:
                log_oauth_error(f'conversations background refresh failed uid={uid} cache_key={cache_key}: {e}')
            except Exception:
                pass
        finally:
            with CONVERSATIONS_API_LOCK:
                CONVERSATIONS_REFRESHING.discard(cache_key)
    with CONVERSATIONS_API_LOCK:
        if cache_key in CONVERSATIONS_REFRESHING:
            return
        CONVERSATIONS_REFRESHING.add(cache_key)
    threading.Thread(target=run, name=f'conv-refresh-{cache_key}', daemon=True).start()

def background_refresh_messages(uid, conv, cache_key):
    def run():
        try:
            payload={'messages':messages_for(uid, conv)}
            payload.update(local_state_summary(state_for_conversation(conv)))
            body=json.dumps(payload, ensure_ascii=False).encode()
            with MESSAGES_API_LOCK:
                MESSAGES_API_CACHE[cache_key]={'ts':time.time(),'body':body}
        except Exception as e:
            try:
                log_oauth_error(f'messages background refresh failed uid={uid} conv={conv}: {e}')
            except Exception:
                pass
        finally:
            with MESSAGES_API_LOCK:
                MESSAGES_REFRESHING.discard(cache_key)
    with MESSAGES_API_LOCK:
        if cache_key in MESSAGES_REFRESHING:
            return
        MESSAGES_REFRESHING.add(cache_key)
    threading.Thread(target=run, name=f'msg-refresh-{uid}', daemon=True).start()

class H(BaseHTTPRequestHandler):
    server_version='ZydonChannelV2/0.1'
    protocol_version = 'HTTP/1.1'  # compatível com Nginx proxy_http_version 1.1
    def log_message(self, fmt, *args): print('[%s] '%datetime.now().isoformat(timespec='seconds') + fmt%args)
    def sendb(self, code, body, ctype='application/json; charset=utf-8', cookies=None):
        self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Cache-Control','no-store'); self.send_header('X-Robots-Tag','noindex,nofollow'); self.send_header('Content-Length', str(len(body)))
        for c in (cookies or []): self.send_header('Set-Cookie', c)
        self.end_headers(); self.wfile.write(body)
    def redirect(self, location, cookies=None):
        self.send_response(302); self.send_header('Location', location); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length','0')
        for c in (cookies or []): self.send_header('Set-Cookie', c)
        self.end_headers()
    def auth(self): return identity_from_request(self)
    # ---- CH-022: rotas de autenticação --------------------------------------
    def handle_login(self, parsed):
        existing_uid = identity_from_request(self)
        if existing_uid:
            return self.redirect('/')
        cfg = google_config()
        if not google_configured():
            return self.sendb(200, login_page_html(cfg).encode(), 'text/html; charset=utf-8')
        qs = parse_qs(parsed.query)
        # /login sem ?go=1 mostra a tela com o botão; o clique inicia o OAuth.
        if not (qs.get('go') or [''])[0]:
            return self.sendb(200, login_page_html(cfg).encode(), 'text/html; charset=utf-8')
        state = make_state()
        secure = request_is_https(self)
        params = {
            'client_id': cfg['client_id'],
            'redirect_uri': oauth_redirect_uri(self, cfg),
            'response_type': 'code',
            'scope': 'openid email profile',
            'state': state,
            'access_type': 'online',
            'prompt': 'select_account',
            'hd': 'zydon.com.br',
        }
        url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode(params)
        # OAUTH_STATE_COOKIE precisa de SameSite=None para sobreviver ao redirect
        # cross-site: accounts.google.com -> sdrs.zydon.com.br/oauth/callback.
        # SameSite=None exige Secure (garantido por build_cookie quando secure=True).
        return self.redirect(url, cookies=[build_cookie(OAUTH_STATE_COOKIE, state, OAUTH_STATE_TTL, secure, same_site='None')])
    def handle_oauth_callback(self, parsed):
        cfg = google_config()
        qs = parse_qs(parsed.query)
        if (qs.get('error') or [''])[0]:
            return self.sendb(400, denied_page_html('Login Google cancelado ou negado.').encode(), 'text/html; charset=utf-8')
        code = (qs.get('code') or [''])[0]
        state = (qs.get('state') or [''])[0]
        jar = _request_cookies(self)
        cookie_state = jar[OAUTH_STATE_COOKIE].value if OAUTH_STATE_COOKIE in jar else ''
        secure = request_is_https(self)
        if not code:
            return self.sendb(400, denied_page_html('Código OAuth ausente.').encode(), 'text/html; charset=utf-8')
        if not state or not verify_state(state) or not (cookie_state and hmac.compare_digest(state, cookie_state)):
            return self.sendb(400, denied_page_html('Falha de validação de segurança (state/CSRF).').encode(), 'text/html; charset=utf-8')
        if not google_configured():
            return self.sendb(200, login_page_html(cfg).encode(), 'text/html; charset=utf-8')
        try:
            tok = _google_exchange_code(code, oauth_redirect_uri(self, cfg), cfg)
            access_token = tok.get('access_token')
            if not access_token:
                raise ValueError('sem access_token')
            info = _google_userinfo(access_token)
        except Exception as e:
            try:
                import datetime as _dt
                (PROJECT / 'logs').mkdir(parents=True, exist_ok=True)
                with open(PROJECT / 'logs' / 'oauth_error.log', 'a') as _lf:
                    _lf.write(f"{_dt.datetime.now().isoformat()} exchange_failed path={self.path!r} error={type(e).__name__}: {e}\n")
            except Exception:
                pass
            existing_uid = identity_from_request(self)
            if existing_uid:
                return self.redirect('/')
            return self.sendb(502, denied_page_html('Não foi possível concluir o login com o Google. Tente de novo.').encode(), 'text/html; charset=utf-8')
        email = str(info.get('email') or '')
        verified = info.get('email_verified', True)
        # CH-DEBUG: log temporário para diagnosticar negativas de acesso.
        try:
            import datetime as _dt
            with open(PROJECT / 'logs' / 'oauth_debug.log', 'a') as _lf:
                _lf.write(f"{_dt.datetime.now().isoformat()} email={email!r} verified={verified!r} hd={info.get('hd')!r} uid_result={uid_from_email(email)!r}\n")
        except Exception:
            pass
        uid = uid_from_email(email)
        clear_state = build_cookie(OAUTH_STATE_COOKIE, '', 0, secure)
        if not uid or not verified:
            detected = email or 'não identificado'
            reason = f'Esta conta não tem acesso ao Channel. Conta detectada: {detected}. Use um e-mail @zydon.com.br liberado.'
            return self.sendb(403, denied_page_html(reason).encode(),
                              'text/html; charset=utf-8', cookies=[clear_state])
        session = build_cookie(SESSION_COOKIE, make_session(uid), SESSION_TTL, secure, same_site='None')
        return self.redirect('/', cookies=[session, clear_state])
    def handle_logout(self):
        secure = request_is_https(self)
        return self.redirect('/login', cookies=[build_cookie(SESSION_COOKIE, '', 0, secure)])
    def do_GET(self):
        parsed=urlparse(self.path); path=parsed.path; uid=self.auth()
        if path=='/health': return self.sendb(200, json.dumps({'ok':True,'ui':'v2','users':list(USERS),'googleConfigured':google_configured(),'time':datetime.now().isoformat()}).encode())
        if path=='/logo.png':
            try:
                return self.sendb(200, LOGO_PATH.read_bytes(), 'image/png')
            except Exception:
                return self.sendb(404, b'logo not found', 'text/plain; charset=utf-8')
        if path=='/logo-dark.png':
            try:
                return self.sendb(200, LOGO_DARK_PATH.read_bytes(), 'image/png')
            except Exception:
                return self.sendb(404, b'logo dark not found', 'text/plain; charset=utf-8')
        # Rotas de autenticação (públicas; não exigem sessão).
        if path=='/login': return self.handle_login(parsed)
        if path=='/oauth/callback': return self.handle_oauth_callback(parsed)
        if path=='/logout': return self.handle_logout()
        if not uid:
            # HTML do app -> manda para o login; APIs/recursos -> 403 explícito.
            if path in APP_ROUTES: return self.redirect('/login')
            return self.sendb(403, b'Acesso negado. Faca login em /login.\n', 'text/plain; charset=utf-8')
        if path in APP_ROUTES:
            refresh_session = build_cookie(SESSION_COOKIE, make_session(uid), SESSION_TTL, request_is_https(self), same_site='None')
            return self.sendb(200, HTML.encode(), 'text/html; charset=utf-8', cookies=[refresh_session])
        if path in ('/api/conversations','/api/conversations-safe'):
            now=time.time(); cache_key='__view_all__' if user_can_view_all(uid) else uid; cache=CONVERSATIONS_API_CACHE.get(cache_key)
            u=USERS[uid]; ports=[{'port':p, **PORTS.get(int(p),{})} for p in effective_ports(uid) if int(p) not in load_paused_ports()]
            user_payload={'id':uid,'name':u['name'],'admin':u.get('admin'), 'view_all':bool(u.get('view_all') or u.get('admin')), 'ports':ports}
            if cache:
                if now-cache.get('ts',0) >= CONVERSATIONS_API_TTL:
                    background_refresh_conversations(uid, cache_key)
                body=json.dumps({'user':user_payload, 'conversations':cache['conversations']}, ensure_ascii=False).encode()
                return self.sendb(200, body)
            # Primeiro carregamento sem cache ainda precisa calcular; depois disso nunca bloqueia a UI.
            with CONVERSATIONS_API_LOCK:
                cache=CONVERSATIONS_API_CACHE.get(cache_key)
                if cache:
                    body=json.dumps({'user':user_payload, 'conversations':cache['conversations']}, ensure_ascii=False).encode()
                    return self.sendb(200, body)
                convs=conversations(uid)
                CONVERSATIONS_API_CACHE[cache_key]={'ts':time.time(),'conversations':convs}
            body=json.dumps({'user':user_payload, 'conversations':convs}, ensure_ascii=False).encode()
            return self.sendb(200, body)
        if path=='/api/messages':
            qs=parse_qs(parsed.query); conv=(qs.get('conv') or [''])[0]
            if not conversation_id_allowed(uid, conv):
                return self.sendb(403, json.dumps({'error':'Conversa nao permitida','messages':[]}, ensure_ascii=False).encode())
            now=time.time(); cache_key=(uid, conv); cache=MESSAGES_API_CACHE.get(cache_key)
            if cache:
                if now-cache.get('ts',0) >= MESSAGES_API_TTL:
                    background_refresh_messages(uid, conv, cache_key)
                return self.sendb(200, cache['body'])
            # Primeiro carregamento sem cache calcula síncrono; depois usa stale-while-revalidate.
            payload={'messages':messages_for(uid, conv)}
            payload.update(local_state_summary(state_for_conversation(conv)))  # CH-010
            body=json.dumps(payload, ensure_ascii=False).encode()
            MESSAGES_API_CACHE[cache_key]={'ts':time.time(),'body':body}
            return self.sendb(200, body)
        if path=='/api/chips':
            now=time.time(); cache=CHIPS_API_CACHE.get(uid)
            if cache and now-cache.get('ts',0) < CHIPS_API_TTL:
                return self.sendb(200, cache['body'])
            chips, summary = chips_for(uid); u=USERS[uid]
            body=json.dumps({'user':{'id':uid,'name':u['name'],'admin':u.get('admin')}, 'chips':chips, 'summary':summary}, ensure_ascii=False).encode()
            CHIPS_API_CACHE[uid]={'ts':time.time(),'body':body}
            return self.sendb(200, body)
        if path=='/api/manager/overview':
            # Leitura pura HubSpot. Supervisores/admin veem consolidado dos 3 SDRs;
            # SDR comum recebe apenas seu owner. Não altera crons nem propriedades.
            return self.sendb(200, json.dumps(manager_overview(uid), ensure_ascii=False).encode())
        if path=='/api/pipeline/focus':
            # Fonte primária do Foco/Gestão: negócios nas 5 primeiras etapas do
            # HubSpot, fatiados por atividades HubSpot associadas ao deal.
            # Não lê/contempla mensagens WhatsApp e não escreve nada.
            return self.sendb(200, json.dumps(pipeline_focus(uid), ensure_ascii=False).encode())
        if path=='/api/dispatch-stats':
            # Gestão operacional: volume de mensagens disparadas por dia/chip.
            # Fonte local read-only: controle/wpp_envios.json. Sem bridge/HubSpot.
            qs=parse_qs(parsed.query)
            return self.sendb(200, json.dumps(dispatch_stats(uid, (qs.get('days') or [14])[0]), ensure_ascii=False).encode())
        if path=='/api/cadencia/preview':
            # CH: prévia read-only do limbo de Primeiro Contato. Apenas lê o JSON do
            # dry-run (NÃO roda o script, NÃO envia WhatsApp, NÃO escreve HubSpot).
            # SDR comum vê só sua carteira; supervisor/admin vê consolidado.
            return self.sendb(200, json.dumps(cadencia_preview(uid), ensure_ascii=False).encode())
        if path=='/api/cadencia/decisoes':
            # CH: decisões humanas LOCAIS do limbo de Primeiro Contato (read-only aqui).
            # SDR vê só a própria carteira; supervisor/admin vê tudo. Sem side-effects.
            return self.sendb(200, json.dumps(cadencia_decisoes_scoped(uid), ensure_ascii=False).encode())
        if path=='/api/admin/users':
            if not USERS.get(uid,{}).get('admin'):
                return self.sendb(403, json.dumps({'ok':False,'error':'admin_required'}).encode())
            return self.sendb(200, json.dumps({'ok':True,'users':users_public(),'ports':[{'port':p, **cfg} for p,cfg in sorted(PORTS.items())]}, ensure_ascii=False).encode())
        if path=='/api/hubspot':
            # CH-030: lateral HubSpot read-only. Nunca quebra a UI: token ausente
            # ou erro de API devolvem 200 com found=false.
            qs=parse_qs(parsed.query); conv_id=(qs.get('conv') or [''])[0]
            if '::' not in conv_id:
                return self.sendb(400, json.dumps({'found':False,'error':'conv inválido'}).encode())
            p_s, chat = conv_id.split('::',1)
            try: port=int(p_s)
            except Exception: return self.sendb(400, json.dumps({'found':False,'error':'conv inválido'}).encode())
            if not conversation_id_allowed(uid, conv_id):
                return self.sendb(403, json.dumps({'found':False,'error':'Conversa nao permitida'}).encode())
            try:
                conv=next((c for c in conversations(uid) if c.get('id')==conv_id), None)
                if not conv:
                    return self.sendb(200, json.dumps({'found':False,'configured':True,'contact':None,'deals':[]}).encode())
                email, empresa = _conv_hubspot_hints(port, chat)
                data=hubspot_lookup(conv, email=email, empresa=empresa)
            except Exception:
                data={'found':False,'configured':True,'contact':None,'deals':[],'error':'hubspot_unavailable'}
            return self.sendb(200, json.dumps(data, ensure_ascii=False).encode())
        if path in ('/qr','/qr.png'):
            qs=parse_qs(parsed.query)
            try: port=int((qs.get('port') or [0])[0])
            except Exception: port=0
            if port not in effective_ports(uid):
                return self.sendb(403, b'Chip nao permitido', 'text/plain; charset=utf-8')
            if path=='/qr.png':
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/qr.png', timeout=4) as r:
                        return self.sendb(200, r.read(), 'image/png')
                except Exception:
                    return self.sendb(404, b'Sem QR disponivel no momento', 'text/plain; charset=utf-8')
            label=PORTS.get(port,{}).get('label', str(port))
            # Não embute token no HTML: /qr.png é buscado pelo browser com o cookie
            # de sessão (mesma origem). Evita vazar credencial na página.
            auth=f"port={port}"
            return self.sendb(200, qr_page(port, label, auth, bridge_status(port)).encode(), 'text/html; charset=utf-8')
        if path=='/api/media':
            qs=parse_qs(parsed.query); port=int((qs.get('port') or [0])[0]); fname=os.path.basename((qs.get('file') or [''])[0]); chat=(qs.get('chat') or [''])[0]
            allowed_media = port in effective_ports(uid)
            if not allowed_media and chat:
                try:
                    allowed_media = conversation_id_allowed(uid, f'{port}::{chat}')
                except Exception:
                    allowed_media = False
            if not allowed_media: return self.sendb(403,b'Forbidden','text/plain')
            f=DATA_DIR/'media'/str(port)/fname
            if not f.exists(): return self.sendb(404,b'Not found','text/plain')
            data=f.read_bytes(); ctype=mimetypes.guess_type(str(f))[0] or 'application/octet-stream'
            low=fname.lower()
            if low.endswith(('.ogg','.opus')): ctype='audio/ogg'
            elif low.endswith('.m4a'): ctype='audio/mp4'
            elif low.endswith('.mp3'): ctype='audio/mpeg'
            elif low.endswith('.wav'): ctype='audio/wav'
            self.send_response(200); self.send_header('Content-Type',ctype); self.send_header('Content-Disposition',f'inline; filename="{fname}"'); self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','private, max-age=300'); self.end_headers(); self.wfile.write(data); return
        return self.sendb(404,b'Not found','text/plain')
    def do_POST(self):
        global USERS, PORTS, INSTITUTIONAL_PRIVATE_PORTS
        parsed=urlparse(self.path); uid=self.auth()
        if not uid: return self.sendb(403,b'Acesso negado','text/plain')
        if parsed.path=='/api/admin/ports':
            if not USERS.get(uid,{}).get('admin'):
                return self.sendb(403, json.dumps({'ok':False,'error':'admin_required'}).encode())
            try:
                n=int(self.headers.get('Content-Length','0') or 0)
                body=json.loads(self.rfile.read(n).decode() or '{}') if n>0 else {}
                action=str(body.get('action') or 'upsert').strip().lower()
                data={str(k):dict(v) for k,v in json.loads(CHANNEL_PORTS_FILE.read_text(encoding='utf-8')).items()} if CHANNEL_PORTS_FILE.exists() else {str(k):dict(v) for k,v in PORTS.items()}
                if action in ('upsert','create'):
                    port, meta = validate_port_payload(body)
                    if action=='create' and str(port) in data:
                        port = next_free_port(port+1)
                        meta['auth'] = f"auth_{port}_{meta['owner']}"
                    data[str(port)] = meta
                    save_ports_config({int(k):v for k,v in data.items()})
                    PORTS = load_ports_config()
                    INSTITUTIONAL_PRIVATE_PORTS = {p for p, meta in PORTS.items() if meta.get('role') in {'institucional','comunicador'}}
                    # cria/atualiza usuário operacional do chip e libera para Rafael/admin
                    users=json.loads(USERS_FILE.read_text(encoding='utf-8')) if USERS_FILE.exists() else {}
                    ouid=meta['owner']; u=users.get(ouid,{})
                    u.setdefault('name', meta['label']); u['role']='sdr' if meta['role']=='sdr' else 'comunicador'; u['ports']=[port]; u.setdefault('admin', False); u.setdefault('token', secrets.token_urlsafe(18))
                    if body.get('hubspotOwnerId') or body.get('hubspot_owner_id'):
                        u['hubspot_owner_id']=re.sub(r'\D+','',str(body.get('hubspotOwnerId') or body.get('hubspot_owner_id') or ''))[:32]
                    users[ouid]=u
                    if 'rafael' in users:
                        rp=sorted(set(int(x) for x in users['rafael'].get('ports',[]) if str(x).isdigit()) | {port})
                        users['rafael']['ports']=rp; users['rafael']['admin']=True; users['rafael']['view_all']=True
                    save_users(users); USERS=ensure_users()
                    started = start_bridge_process(port, meta['auth']) if bool(body.get('start', True)) else {'started':False}
                    return self.sendb(200,json.dumps({'ok':True,'port':port,'meta':meta,'started':started,'ports':admin_port_payload(),'users':users_public()},ensure_ascii=False).encode())
                try: port=int(body.get('port'))
                except Exception: return self.sendb(400,json.dumps({'ok':False,'error':'porta obrigatória'},ensure_ascii=False).encode())
                if action=='delete':
                    if port in (4600,4601,4603,4605,4606,4607):
                        return self.sendb(400,json.dumps({'ok':False,'error':'não remover portas base; use desconectar se precisar'},ensure_ascii=False).encode())
                    stop_bridge_process(port); data.pop(str(port), None); save_ports_config({int(k):v for k,v in data.items()})
                    PORTS=load_ports_config(); INSTITUTIONAL_PRIVATE_PORTS={p for p, meta in PORTS.items() if meta.get('role') in {'institucional','comunicador'}}
                    users=json.loads(USERS_FILE.read_text(encoding='utf-8')) if USERS_FILE.exists() else {}
                    for cfg in users.values(): cfg['ports']=[int(x) for x in cfg.get('ports',[]) if int(x)!=port]
                    save_users(users); USERS=ensure_users()
                    return self.sendb(200,json.dumps({'ok':True,'ports':admin_port_payload(),'users':users_public()},ensure_ascii=False).encode())
                meta=PORTS.get(port)
                if not meta: return self.sendb(404,json.dumps({'ok':False,'error':'porta não cadastrada'},ensure_ascii=False).encode())
                if action=='start':
                    r=start_bridge_process(port, meta.get('auth') or f'auth_{port}')
                    return self.sendb(200,json.dumps({'ok':True,'result':r,'status':bridge_status(port)},ensure_ascii=False).encode())
                if action=='disconnect':
                    stop=stop_bridge_process(port)
                    auth=str(meta.get('auth') or '')
                    removed=False
                    if auth and '/' not in auth and '..' not in auth:
                        ap=WA_EXTRA/auth
                        try:
                            if ap.exists():
                                subprocess.run(['rm','-rf',str(ap)], timeout=10); removed=True
                        except Exception: pass
                    return self.sendb(200,json.dumps({'ok':True,'stopped':stop,'authRemoved':removed},ensure_ascii=False).encode())
                if action=='regen':
                    start_bridge_process(port, meta.get('auth') or f'auth_{port}')
                    try: resp=post_json(f'http://127.0.0.1:{port}/regen', {})
                    except Exception as e: resp={'error':str(e)}
                    return self.sendb(200,json.dumps({'ok':True,'bridge':resp,'qrUrl':f'/qr?port={port}'},ensure_ascii=False).encode())
                return self.sendb(400,json.dumps({'ok':False,'error':'ação inválida'},ensure_ascii=False).encode())
            except ValueError as e:
                return self.sendb(400,json.dumps({'ok':False,'error':str(e)},ensure_ascii=False).encode())
            except Exception as e:
                return self.sendb(500,json.dumps({'ok':False,'error':str(e)},ensure_ascii=False).encode())
        if parsed.path=='/api/admin/users':
            if not USERS.get(uid,{}).get('admin'):
                return self.sendb(403, json.dumps({'ok':False,'error':'admin_required'}).encode())
            try:
                n=int(self.headers.get('Content-Length','0') or 0)
                body=json.loads(self.rfile.read(n).decode() or '{}') if n>0 else {}
                action=str(body.get('action') or 'upsert').strip().lower()
                target=str(body.get('id') or '').strip().lower()
                data=json.loads(USERS_FILE.read_text(encoding='utf-8')) if USERS_FILE.exists() else {}
                if action=='delete':
                    if target=='rafael':
                        return self.sendb(400,json.dumps({'ok':False,'error':'não é permitido remover Rafael/admin principal'},ensure_ascii=False).encode())
                    if target not in data:
                        return self.sendb(404,json.dumps({'ok':False,'error':'usuário não encontrado'},ensure_ascii=False).encode())
                    data.pop(target)
                else:
                    new_uid, rec = validate_admin_user_payload(body)
                    existing = data.get(new_uid, {})
                    token = existing.get('token') or secrets.token_urlsafe(18)
                    # Proteção: sempre manter Rafael como admin e com todos os chips.
                    if new_uid == 'rafael':
                        rec['admin'] = True
                        rec['ports'] = sorted(PORTS.keys())
                    rec['token'] = token
                    data[new_uid] = rec
                save_users(data)
                USERS = ensure_users()
                return self.sendb(200,json.dumps({'ok':True,'users':users_public()},ensure_ascii=False).encode())
            except ValueError as e:
                return self.sendb(400,json.dumps({'ok':False,'error':str(e)},ensure_ascii=False).encode())
            except Exception as e:
                return self.sendb(500,json.dumps({'ok':False,'error':str(e)},ensure_ascii=False).encode())
        if parsed.path=='/api/cadencia/decisao':
            # CH: grava decisão humana LOCAL sobre um deal do limbo de Primeiro
            # Contato. Local-only: NÃO envia WhatsApp, NÃO escreve HubSpot, NÃO
            # altera stage/owner/cron nem o ledger wpp_envios.json. Apenas grava em
            # cadencia_primeiro_contato_decisoes.json + auditoria JSONL.
            try:
                n=int(self.headers.get('Content-Length','0') or 0)
                body=json.loads(self.rfile.read(n).decode() or '{}') if n>0 else {}
            except Exception:
                return self.sendb(400,json.dumps({'ok':False,'error':'JSON inválido'}).encode())
            deal_id=str(body.get('dealId') or '').strip()
            action=str(body.get('action') or '').strip().lower()
            note=str(body.get('note') or '')
            if not deal_id:
                return self.sendb(400,json.dumps({'ok':False,'error':'dealId obrigatório'}).encode())
            if action not in CADENCIA_DECISION_ACTIONS:
                return self.sendb(400,json.dumps({'ok':False,'error':'action inválida','valid':sorted(CADENCIA_DECISION_ACTIONS)},ensure_ascii=False).encode())
            row=_cadencia_row_for_deal(deal_id)
            if not row:
                return self.sendb(404,json.dumps({'ok':False,'error':'deal não está na prévia do dry-run'},ensure_ascii=False).encode())
            if not cadencia_deal_in_scope(uid, row):
                return self.sendb(403,json.dumps({'ok':False,'error':'deal fora do seu escopo'},ensure_ascii=False).encode())
            try:
                decision=set_cadencia_decisao(deal_id, action, uid, note=note,
                                              previous_sanitation_bucket=row.get('sanitationBucket') or '')
            except Exception as e:
                return self.sendb(500,json.dumps({'ok':False,'error':str(e)},ensure_ascii=False).encode())
            return self.sendb(200,json.dumps({'ok':True,'cleared':action=='limpar','decision':decision,'scope':cadencia_decisoes_scoped(uid)},ensure_ascii=False).encode())
        if parsed.path=='/api/transcribe':
            # CH-052: transcrição manual/forçada de áudio recebido. Não envia nada;
            # apenas atualiza cache local e devolve o texto.
            try:
                n=int(self.headers.get('Content-Length','0') or 0)
                body=json.loads(self.rfile.read(n).decode() or '{}') if n>0 else {}
                conv=str(body.get('conv') or '')
                msg_id=str(body.get('id') or '')
                force=bool(body.get('force'))
                rows=messages_for(uid, conv) if conv else []
                m=next((x for x in rows if str(x.get('id') or '')==msg_id), None) if msg_id else next((x for x in rows if _is_audio_msg(x) and not x.get('fromMe')), None)
                if not m:
                    return self.sendb(404,json.dumps({'ok':False,'error':'áudio não encontrado'},ensure_ascii=False).encode())
                item=transcribe_audio_message(m, force=force) or {}
                return self.sendb(200,json.dumps({'ok':bool(item.get('transcript')),'transcript':item.get('transcript') or '', 'status':item.get('status') or 'pending', 'provider':item.get('provider') or ''},ensure_ascii=False).encode())
            except Exception as e:
                return self.sendb(500,json.dumps({'ok':False,'error':str(e)},ensure_ascii=False).encode())
        if parsed.path=='/api/send':
            try:
                n=int(self.headers.get('Content-Length','0')); body=json.loads(self.rfile.read(n).decode() or '{}')
                port=int(body.get('port')); chat=str(body.get('chat') or ''); text=str(body.get('text') or '').strip()
                if port not in effective_ports(uid): return self.sendb(403,b'Porta nao permitida','text/plain')
                if is_institutional_port(port): return self.sendb(403,b'Chip institucional/pessoal somente leitura no Channel','text/plain')
                if not chat or not text: return self.sendb(400,b'Missing chat/text','text/plain')
                if _dedupe_send(uid, port, chat, 'text', text):
                    return self.sendb(200,json.dumps({'ok':True,'duplicate':True,'skipped':True},ensure_ascii=False).encode())
                resp=post_json(f'http://127.0.0.1:{port}/send', {'to':chat,'text':text})
                invalidate_channel_api_cache(uid, f'{port}::{canonical_chat_id(chat)}')
                return self.sendb(200,json.dumps({'ok':True,'bridge':resp},ensure_ascii=False).encode())
            except Exception as e:
                return self.sendb(500,json.dumps({'ok':False,'error':str(e)},ensure_ascii=False).encode())
        if parsed.path=='/api/send-file':
            # CH-018: envio de arquivo/áudio pelo painel (JSON com base64, sem multipart).
            try:
                n=int(self.headers.get('Content-Length','0') or 0)
                body=json.loads(self.rfile.read(n).decode() or '{}') if n>0 else {}
            except Exception:
                return self.sendb(400,json.dumps({'ok':False,'error':'JSON inválido'}).encode())
            try:
                port=int(body.get('port'))
            except (TypeError, ValueError):
                return self.sendb(400,json.dumps({'ok':False,'error':'port inválido'}).encode())
            chat=str(body.get('chat') or '').strip()
            file_name=str(body.get('fileName') or '').strip()
            caption=str(body.get('caption') or '')
            data_b64=body.get('dataBase64')
            if port not in effective_ports(uid):
                return self.sendb(403,json.dumps({'ok':False,'error':'Porta nao permitida'}).encode())
            if is_institutional_port(port):
                return self.sendb(403,json.dumps({'ok':False,'error':'Chip institucional/pessoal somente leitura no Channel'},ensure_ascii=False).encode())
            if not chat:
                return self.sendb(400,json.dumps({'ok':False,'error':'chat obrigatório'}).encode())
            if not file_name:
                return self.sendb(400,json.dumps({'ok':False,'error':'fileName obrigatório'}).encode())
            if not data_b64:
                return self.sendb(400,json.dumps({'ok':False,'error':'dataBase64 obrigatório'}).encode())
            try:
                raw=decode_data_base64(data_b64)
            except ValueError as e:
                return self.sendb(400,json.dumps({'ok':False,'error':str(e)},ensure_ascii=False).encode())
            if not raw:
                return self.sendb(400,json.dumps({'ok':False,'error':'arquivo vazio'}).encode())
            if len(raw) > MAX_UPLOAD_BYTES:
                return self.sendb(413,json.dumps({'ok':False,'error':'Arquivo acima de 20MB'},ensure_ascii=False).encode())
            try:
                dest_dir=UPLOADS_DIR/str(port)
                dest_dir.mkdir(parents=True, exist_ok=True)
                safe_name=safe_upload_name(file_name)
                if _dedupe_send(uid, port, chat, 'file', f'{safe_name}|{len(raw)}|{caption.strip()}'):
                    return self.sendb(200,json.dumps({'ok':True,'duplicate':True,'skipped':True},ensure_ascii=False).encode())
                dest=dest_dir/safe_name
                dest.write_bytes(raw)
                payload={'to':chat,'filePath':str(dest),'fileName':os.path.basename(file_name) or safe_name}
                if caption: payload['caption']=caption
                resp=post_json(f'http://127.0.0.1:{port}/send-file', payload)
                invalidate_channel_api_cache(uid, f'{port}::{canonical_chat_id(chat)}')
                return self.sendb(200,json.dumps({'ok':True,'bridge':resp},ensure_ascii=False).encode())
            except Exception as e:
                return self.sendb(500,json.dumps({'ok':False,'error':str(e)},ensure_ascii=False).encode())
        if parsed.path=='/api/state':
            # CH-010: persiste status e/ou nota interna de uma conversa. Local-only:
            # não envia WhatsApp nem escreve no HubSpot. Aceita {conv,status} e/ou
            # {conv,note}. Permissão: admin pode tudo; demais só portas que possuem.
            try:
                n=int(self.headers.get('Content-Length','0') or 0)
                body=json.loads(self.rfile.read(n).decode() or '{}') if n>0 else {}
            except Exception:
                return self.sendb(400,json.dumps({'ok':False,'error':'JSON inválido'}).encode())
            conv_id=str(body.get('conv') or '').strip()
            if '::' not in conv_id:
                return self.sendb(400,json.dumps({'ok':False,'error':'conv inválido'}).encode())
            p_s, chat = conv_id.split('::',1)
            try:
                port=int(p_s)
            except Exception:
                return self.sendb(400,json.dumps({'ok':False,'error':'conv inválido'}).encode())
            is_admin=bool(USERS.get(uid,{}).get('admin'))
            if not is_admin and not conversation_id_allowed(uid, conv_id):
                return self.sendb(403,json.dumps({'ok':False,'error':'Conversa nao permitida'}).encode())
            status=body.get('status')
            note=body.get('note')
            if status is None and note is None:
                return self.sendb(400,json.dumps({'ok':False,'error':'Informe status ou note'}).encode())
            if status is not None and not valid_status(str(status)):
                return self.sendb(400,json.dumps({'ok':False,'error':'status inválido','valid':list(VALID_STATUSES)},ensure_ascii=False).encode())
            try:
                entry=update_conversation_state(conv_id, uid, status=status, note=note)
            except Exception as e:
                return self.sendb(500,json.dumps({'ok':False,'error':str(e)},ensure_ascii=False).encode())
            invalidate_channel_api_cache(uid, conv_id)
            return self.sendb(200,json.dumps({'ok':True,'state':entry},ensure_ascii=False).encode())
        if parsed.path=='/api/hubspot/action':
            # CH-031: cria task/note no HubSpot a partir da conversa. Auth já
            # garantido (do_POST devolve 403 sem uid). Permissão por porta: admin
            # pode tudo; demais só portas que possuem. Integridade do CRM: só cria
            # se houver contato associado e sempre registra auditoria local.
            try:
                n=int(self.headers.get('Content-Length','0') or 0)
                body=json.loads(self.rfile.read(n).decode() or '{}') if n>0 else {}
            except Exception:
                return self.sendb(400,json.dumps({'ok':False,'error':'JSON inválido'}).encode())
            conv_id=str(body.get('conv') or '').strip()
            if '::' not in conv_id:
                return self.sendb(400,json.dumps({'ok':False,'error':'conv inválido'}).encode())
            p_s, chat = conv_id.split('::',1)
            try:
                port=int(p_s)
            except Exception:
                return self.sendb(400,json.dumps({'ok':False,'error':'conv inválido'}).encode())
            is_admin=bool(USERS.get(uid,{}).get('admin'))
            if not is_admin and not conversation_id_allowed(uid, conv_id):
                return self.sendb(403,json.dumps({'ok':False,'error':'Conversa nao permitida'}).encode())
            action=str(body.get('action') or '').strip().lower()
            if action not in ('task','note','conversation_history','playbook'):
                return self.sendb(400,json.dumps({'ok':False,'error':'action deve ser task, note, conversation_history ou playbook'}).encode())
            body_txt='' if action in ('conversation_history','playbook') else _hs_clean_text(body.get('body'), HS_BODY_MAX)
            if action not in ('conversation_history','playbook') and not body_txt:
                return self.sendb(400,json.dumps({'ok':False,'error':'body obrigatório'}).encode())
            token=_hubspot_token()
            if not token:
                return self.sendb(503,json.dumps({'ok':False,'error':'HubSpot não configurado'},ensure_ascii=False).encode())
            # Reusa o lookup read-only para achar contato + deals desta conversa.
            try:
                conv=next((c for c in conversations(uid) if c.get('id')==conv_id), None)
            except Exception:
                conv=None
            if not conv:
                conv={'id':conv_id,'port':port,'chat':chat,'title':'','displayPhone':''}
            email, empresa = _conv_hubspot_hints(port, chat)
            look=hubspot_lookup(conv, email=email, empresa=empresa)
            contact_id=str((look.get('contact') or {}).get('id') or '')
            if not look.get('found') or not contact_id:
                return self.sendb(404,json.dumps({'ok':False,'error':'Contato não encontrado no HubSpot para esta conversa'},ensure_ascii=False).encode())
            deals=look.get('deals') or []
            deal_id=str((deals[0] or {}).get('id') or '') if deals else ''
            if action == 'playbook':
                playbook=str(body.get('playbook') or '').strip().lower()
                if playbook != 'intro_handoff':
                    return self.sendb(400,json.dumps({'ok':False,'error':'playbook inválido'},ensure_ascii=False).encode())
                if not deal_id:
                    return self.sendb(400,json.dumps({'ok':False,'error':'Negócio HubSpot não encontrado para este lead'},ensure_ascii=False).encode())
                stage_id=str(body.get('stageId') or '1269308723').strip()
                if stage_id not in PLAYBOOK_ALLOWED_STAGES:
                    return self.sendb(400,json.dumps({'ok':False,'error':'Etapa não permitida neste playbook'},ensure_ascii=False).encode())
                owner_id=str(body.get('ownerId') or '').strip()
                if owner_id and owner_id not in PLAYBOOK_OWNER_IDS:
                    return self.sendb(400,json.dumps({'ok':False,'error':'Proprietário não permitido neste playbook'},ensure_ascii=False).encode())
                field_name=_safe_hs_property_name(body.get('fieldName'))
                field_value=_hs_clean_text(body.get('fieldValue'), 400)
                note_txt=_hs_clean_text(body.get('note'), HS_BODY_MAX)
                deal_props={'dealstage': stage_id}
                contact_props={}
                if owner_id:
                    deal_props['hubspot_owner_id']=owner_id
                    contact_props['hubspot_owner_id']=owner_id
                if field_name and field_value:
                    # Campo operacional explícito informado pelo usuário. Aplica no negócio;
                    # se o campo existir só em contato, a API devolverá erro e a prévia evita surpresa.
                    deal_props[field_name]=field_value
                errors=[]
                err=_hs_patch_object('deals', deal_id, deal_props, token)
                if err: errors.append('deal: '+err)
                if contact_props:
                    err=_hs_patch_object('contacts', contact_id, contact_props, token)
                    if err: errors.append('contato: '+err)
                audit_body=(f"Playbook Channel: Handoff / Introdução\n"
                            f"Etapa: {PLAYBOOK_ALLOWED_STAGES.get(stage_id, stage_id)}\n"
                            f"Owner: {PLAYBOOK_OWNER_IDS.get(owner_id, owner_id) if owner_id else 'sem alteração'}\n"
                            f"Campo extra: {field_name+'='+field_value if field_name and field_value else 'nenhum'}\n"
                            f"Observação: {note_txt or '—'}")
                note_id=''
                if not errors:
                    props={'hs_note_body':audit_body,'hs_timestamp':_hs_now_iso()}
                    specs=[(contact_id, HS_ASSOC['note_contact'])]
                    if deal_id: specs.append((deal_id, HS_ASSOC['note_deal']))
                    note_id, note_err=_hs_create_object('notes', props, specs, token)
                    if note_err: errors.append('nota: '+note_err)
                _hs_audit_log({'ts':_hs_now_iso(),'uid':uid,'conv':conv_id,'action':'playbook','playbook':playbook,
                               'contactId':contact_id,'dealId':deal_id,'stageId':stage_id,'ownerId':owner_id,
                               'fieldName':field_name,'ok':not errors,'errors':errors})
                if errors:
                    return self.sendb(502,json.dumps({'ok':False,'error':' | '.join(errors)},ensure_ascii=False).encode())
                invalidate_channel_api_cache(uid, conv_id)
                return self.sendb(200,json.dumps({'ok':True,'action':'playbook','playbook':playbook,'contactId':contact_id,'dealId':deal_id,'noteId':note_id,'stageId':stage_id,'ownerId':owner_id},ensure_ascii=False).encode())
            subject=''; status=''
            if action=='task':
                subject=_hs_clean_text(body.get('subject'), HS_SUBJECT_MAX) or 'Follow-up WhatsApp'
                due=str(body.get('due') or 'today').strip().lower()
                if due not in ('today','tomorrow','none'):
                    due='today'
                # CH: atalho operacional "tarefa realizada" cria uma task já COMPLETED.
                # Só permitimos NOT_STARTED (padrão) ou COMPLETED — nada de mexer em
                # tasks existentes por ID. Task concluída usa o horário de agora.
                status=str(body.get('status') or 'NOT_STARTED').strip().upper()
                if status not in ('NOT_STARTED','COMPLETED'):
                    status='NOT_STARTED'
                ts=_hs_now_iso() if status=='COMPLETED' else _hs_due_timestamp(due)
                props={
                    'hs_task_subject':subject,
                    'hs_task_body':body_txt,
                    'hs_task_status':status,
                    'hs_task_priority':'NONE',
                    'hs_task_type':'TODO',
                    'hs_timestamp':ts,
                }
                specs=[(contact_id, HS_ASSOC['task_contact'])]
                if deal_id: specs.append((deal_id, HS_ASSOC['task_deal']))
                obj_id, err=_hs_create_object('tasks', props, specs, token)
                preview=subject
            else:
                if action=='conversation_history':
                    body_txt=build_whatsapp_history_note(uid, conv_id, conv=conv, contact=(look.get('contact') or {}), deal=(deals[0] if deals else {}))
                props={'hs_note_body':body_txt,'hs_timestamp':_hs_now_iso()}
                specs=[(contact_id, HS_ASSOC['note_contact'])]
                if deal_id: specs.append((deal_id, HS_ASSOC['note_deal']))
                obj_id, err=_hs_create_object('notes', props, specs, token)
                preview=('Histórico WhatsApp completo' if action=='conversation_history' else body_txt[:120])
            _hs_audit_log({
                'ts':_hs_now_iso(),'uid':uid,'conv':conv_id,'action':action,
                'contactId':contact_id,'dealId':deal_id,'objectId':obj_id,
                'subject':subject,'status':status,'preview':preview[:160],
                'ok':bool(obj_id),'error':err,
            })
            if not obj_id:
                return self.sendb(502,json.dumps({'ok':False,'error':err or 'Falha ao criar no HubSpot'},ensure_ascii=False).encode())
            invalidate_channel_api_cache(uid, conv_id)
            return self.sendb(200,json.dumps({'ok':True,'action':action,'id':obj_id,'contactId':contact_id,'dealId':deal_id,'status':status},ensure_ascii=False).encode())
        return self.sendb(404,b'Not found','text/plain')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--host',default='0.0.0.0'); ap.add_argument('--port',type=int,default=8791); ap.add_argument('--print-links',action='store_true')
    args=ap.parse_args();
    if args.print_links:
        for uid,cfg in USERS.items(): print(f"{cfg['name']}: http://127.0.0.1:{args.port}/?u={uid}&t={cfg['token']}")
        return
    httpd=ThreadingHTTPServer((args.host,args.port),H); print(f'Channel V2 rodando em {args.host}:{args.port}', flush=True); httpd.serve_forever()
if __name__=='__main__': main()
