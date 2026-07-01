"""Regras centrais de entrada/saída WhatsApp por SDR e múltiplos chips.

Este módulo é regra de negócio, não UI:
- Se já existe conversa com o lead em um chip do SDR, continuar pelo mesmo chip.
- Se é lead novo, sortear de forma determinística/justa entre chips saudáveis do SDR.
- Nunca escolher chip de outro SDR para conversa comercial do dono.

Os crons novos devem importar daqui em vez de decidir porta localmente.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

# Fronteira única de privacidade: grupo/broadcast/chip interno nunca é lead.
# Reaproveita o helper central em vez de reimplementar a regra aqui.
try:
    from .whatsapp_jid_utils import is_blocked_operational_target
except Exception:
    try:
        from whatsapp_jid_utils import is_blocked_operational_target  # type: ignore
    except Exception:  # fail-closed conservador: sem o helper, nada é liberado
        def is_blocked_operational_target(value: Any) -> bool:  # type: ignore
            return True

PROJECT = Path('/root/.hermes/zydon-prospeccao')
CHANNEL_PORTS_FILE = PROJECT / 'controle' / 'channel_ports.json'
CHANNEL_USERS_FILE = PROJECT / 'controle' / 'channel_users.json'
WPP_ENVIOS_FILE = PROJECT / 'controle' / 'wpp_envios.json'
DISPATCH_QUEUE_FILE = PROJECT / 'controle' / 'whatsapp_dispatch_queue.json'

PHONE_RE = re.compile(r'\d+')

# Estados de disparo que ainda "prendem" o lead a um chip para efeito de trava
# anti-duplo-contato. Um disparo cancelado/pulado/falho não segura o lead, pois
# não representa uma conversa em andamento.
ACTIVE_DISPATCH_STATUSES = frozenset({'queued', 'locked', 'sent', 'blocked'})


def digits(value: Any) -> str:
    return ''.join(PHONE_RE.findall(str(value or '')))


def br_phone_key(value: Any) -> str:
    """Canonicaliza telefone BR o suficiente para comparar com/sem 9º dígito."""
    d = digits(value)
    if d.startswith('00'):
        d = d[2:]
    if not d.startswith('55') and len(d) in (10, 11):
        d = '55' + d
    if d.startswith('55') and len(d) == 13 and d[4] == '9':
        return d[:4] + d[5:]
    return d


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def load_ports(path: Path = CHANNEL_PORTS_FILE) -> dict[int, dict[str, Any]]:
    raw = load_json(path, {})
    out: dict[int, dict[str, Any]] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            try:
                p = int(k)
            except Exception:
                continue
            if isinstance(v, dict):
                out[p] = dict(v)
    return out


def load_users(path: Path = CHANNEL_USERS_FILE) -> dict[str, dict[str, Any]]:
    raw = load_json(path, {})
    return raw if isinstance(raw, dict) else {}


def sdr_ports(owner_uid: str, ports: dict[int, dict[str, Any]] | None = None, users: dict[str, dict[str, Any]] | None = None) -> list[int]:
    """Portas comerciais vinculadas ao SDR, aceitando múltiplos chips por usuário."""
    owner_uid = str(owner_uid or '').strip()
    ports = ports or load_ports()
    users = users or load_users()
    allowed = set()
    u = users.get(owner_uid) or {}
    for p in u.get('ports') or []:
        try:
            allowed.add(int(p))
        except Exception:
            pass
    out = []
    for p, meta in ports.items():
        if meta.get('role') != 'sdr':
            continue
        if meta.get('owner') == owner_uid or p in allowed:
            out.append(int(p))
    return sorted(set(out))


def _rows_from_ledger(path: Path = WPP_ENVIOS_FILE) -> list[dict[str, Any]]:
    data = load_json(path, {})
    rows = data.get('envios') if isinstance(data, dict) else data
    return [r for r in (rows or []) if isinstance(r, dict)]


def row_phone_key(row: dict[str, Any]) -> str:
    for k in ('to', 'jid', 'phone', 'telefone', 'tel', 'whatsapp', 'hs_whatsapp_phone_number'):
        val = row.get(k)
        if val:
            key = br_phone_key(val)
            if key:
                return key
    return ''


def existing_thread_port(phone_or_jid: Any, owner_uid: str, *, rows: Iterable[dict[str, Any]] | None = None, ports: dict[int, dict[str, Any]] | None = None, users: dict[str, dict[str, Any]] | None = None) -> int | None:
    """Retorna o último chip do SDR que já conversou com esse lead, se existir."""
    target = br_phone_key(phone_or_jid)
    if not target:
        return None
    candidates = set(sdr_ports(owner_uid, ports=ports, users=users))
    if not candidates:
        return None
    best = None
    best_ts = ''
    for row in rows if rows is not None else _rows_from_ledger():
        try:
            port = int(row.get('bridge_port') or row.get('port') or row.get('sender_port') or 0)
        except Exception:
            continue
        if port not in candidates:
            continue
        if row_phone_key(row) != target:
            continue
        ts = str(row.get('date_tz') or row.get('date') or row.get('ts') or '')
        if ts >= best_ts:
            best_ts = ts
            best = port
    return best


def choose_new_thread_port(owner_uid: str, lead_key: Any, *, ports: dict[int, dict[str, Any]] | None = None, users: dict[str, dict[str, Any]] | None = None, health: dict[int, dict[str, Any]] | None = None, rows: Iterable[dict[str, Any]] | None = None) -> int | None:
    """Escolhe chip para lead novo por menor carga + hash estável para desempate."""
    candidates = sdr_ports(owner_uid, ports=ports, users=users)
    if not candidates:
        return None
    health = health or {}
    healthy = [p for p in candidates if (health.get(p, {}).get('healthy', True) and not health.get(p, {}).get('needsQR', False))]
    pool = healthy or candidates
    counts = Counter()
    for row in rows if rows is not None else _rows_from_ledger():
        try:
            p = int(row.get('bridge_port') or row.get('port') or row.get('sender_port') or 0)
        except Exception:
            continue
        if p in pool:
            counts[p] += 1
    seed = int(hashlib.sha256(str(lead_key or '').encode('utf-8')).hexdigest()[:8], 16)

    def priority(p: int) -> int:
        try:
            return int((ports or {}).get(p, {}).get('priority') or 0)
        except Exception:
            return 0

    # Chips recém-conectados podem receber prioridade temporária para equilibrar
    # aquecimento/volume. Ex.: priority=100 faz o chip novo vencer até a diferença
    # de carga compensar, sem quebrar afinidade nem saúde.
    return sorted(pool, key=lambda p: (counts[p] - priority(p), seed % 997 + p % 997, p))[0]


def _dispatch_rows(dispatches: Any) -> list[dict[str, Any]]:
    """Normaliza a fila unificada: aceita lista de linhas ou o dict do arquivo."""
    if dispatches is None:
        dispatches = load_json(DISPATCH_QUEUE_FILE, {})
    if isinstance(dispatches, dict):
        dispatches = dispatches.get('dispatches')
    return [r for r in (dispatches or []) if isinstance(r, dict)]


def _dispatch_port(row: dict[str, Any]) -> int:
    try:
        return int(row.get('port') or row.get('bridge_port') or row.get('sender_port') or 0)
    except Exception:
        return 0


def active_contact_port(phone_or_jid: Any, *, dispatches: Any = None, owner_uid: str | None = None,
                        ports: dict[int, dict[str, Any]] | None = None, users: dict[str, dict[str, Any]] | None = None,
                        active_statuses: Iterable[str] | None = None) -> int | None:
    """Porta que já está em contato ativo com o lead na fila unificada.

    Base da trava anti-duplo-contato: se algum chip já tem disparo ativo
    (queued/locked/sent/blocked) para esse destino, essa porta é a única que
    pode continuar falando com o lead.

    Se `owner_uid` for informado, restringe aos chips daquele SDR; sem owner,
    varre todas as portas (proteção global contra dois números diferentes
    chamando o mesmo lead, mesmo entre SDRs distintos).
    """
    target = br_phone_key(phone_or_jid)
    if not target:
        return None
    statuses = set(active_statuses) if active_statuses is not None else set(ACTIVE_DISPATCH_STATUSES)
    allowed = set(sdr_ports(owner_uid, ports=ports, users=users)) if owner_uid else None
    best = None
    best_ts = ''
    for row in _dispatch_rows(dispatches):
        if str(row.get('status') or '') not in statuses:
            continue
        if row_phone_key(row) != target:
            continue
        port = _dispatch_port(row)
        if not port:
            continue
        if allowed is not None and port not in allowed:
            continue
        ts = str(row.get('updated_at') or row.get('created_at') or '')
        if ts >= best_ts:
            best_ts = ts
            best = port
    return best


def would_double_contact(phone_or_jid: Any, candidate_port: Any, *, dispatches: Any = None,
                         active_statuses: Iterable[str] | None = None) -> bool:
    """True se enfileirar `candidate_port` abriria um 2º contato com o lead.

    Guarda que produtores/enqueue devem checar: mesmo lead/destino não pode ser
    enfileirado por duas portas ao mesmo tempo. A checagem é global (não filtra
    por SDR) justamente para pegar também o caso de dois números diferentes.
    """
    try:
        candidate = int(candidate_port)
    except Exception:
        return False
    other = active_contact_port(phone_or_jid, dispatches=dispatches, active_statuses=active_statuses)
    return other is not None and int(other) != candidate


def choose_outbound_port(owner_uid: str, phone_or_jid: Any, *, lead_key: Any = '', rows: Iterable[dict[str, Any]] | None = None, dispatches: Any = None, ports: dict[int, dict[str, Any]] | None = None, users: dict[str, dict[str, Any]] | None = None, health: dict[int, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Decisão central para qualquer camada de envio.

    Ordem de decisão:
    1. Privacidade: grupo/broadcast/chip interno nunca vira envio operacional.
    2. Trava anti-duplo-contato: se o lead já tem disparo ativo na fila, mantém
       o chip que já fala com ele (e recusa se for chip de outro SDR).
    3. Afinidade por histórico (ledger) do próprio SDR.
    4. Lead novo: distribuição balanceada entre chips saudáveis do SDR.

    Retorna razão explícita para painel/log e NÃO envia WhatsApp.
    """
    if is_blocked_operational_target(phone_or_jid):
        return {'port': None, 'mode': 'blocked_private_target',
                'reason': 'Destino é grupo/broadcast/chip interno; nunca abrir conversa operacional.'}

    # Trava anti-duplo-contato via fila unificada. Opt-in: só age quando a fila
    # é passada explicitamente pelo caller (evita ler produção em chamadas
    # legadas/testes e mantém o comportamento por ledger como padrão).
    if dispatches is not None:
        locked_any = active_contact_port(phone_or_jid, dispatches=dispatches, ports=ports, users=users)
        if locked_any:
            own_ports = set(sdr_ports(owner_uid, ports=ports, users=users))
            if int(locked_any) in own_ports:
                return {'port': locked_any, 'mode': 'active_contact_lock',
                        'reason': 'Lead já tem disparo ativo neste chip do SDR; manter continuidade e evitar contato duplicado.'}
            return {'port': None, 'mode': 'active_contact_conflict', 'locked_port': locked_any,
                    'reason': 'Lead já está em contato ativo por outro número; não abrir segundo contato.'}

    existing = existing_thread_port(phone_or_jid, owner_uid, rows=rows, ports=ports, users=users)
    if existing:
        return {'port': existing, 'mode': 'existing_thread', 'reason': 'Lead já conversa com este SDR por esse chip; manter continuidade da conversa.'}
    selected = choose_new_thread_port(owner_uid, lead_key or phone_or_jid, ports=ports, users=users, health=health, rows=rows)
    if selected:
        return {'port': selected, 'mode': 'new_thread_balanced', 'reason': 'Lead novo; chip escolhido por distribuição central entre chips saudáveis do SDR.'}
    return {'port': None, 'mode': 'no_sdr_port', 'reason': 'SDR sem chip comercial disponível/vinculado.'}
