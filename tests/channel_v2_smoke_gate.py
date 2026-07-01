#!/usr/bin/env python3
"""Smoke/performance gate for Zydon Channel V2.

Starts no services by default; expects 8280/8791 already running.
Fails if core routes/APIs are slow or broken.
"""
import html
import importlib.util
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD_PATH = ROOT / 'scripts' / 'channel_panel_v2.py'

spec = importlib.util.spec_from_file_location('channel_panel_v2', MOD_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
TOKEN = mod.make_session('rafael')
COOKIE = {'Cookie': f'zydon_session={TOKEN}'}

FAILS = []

def fetch(url, timeout=10):
    req = urllib.request.Request(url, headers=COOKIE)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
        code = r.status
    return code, body, int((time.time() - t0) * 1000)

def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print('FAIL:', msg)
    else:
        print('OK:', msg)

def visible_text_from_html(raw_html):
    """Approximate text users can see without counting JS/CSS/internal code."""
    raw_html = re.sub(r'<script\b[^>]*>.*?</script>', ' ', raw_html, flags=re.I | re.S)
    raw_html = re.sub(r'<style\b[^>]*>.*?</style>', ' ', raw_html, flags=re.I | re.S)
    raw_html = re.sub(r'<!--.*?-->', ' ', raw_html, flags=re.S)
    text = re.sub(r'<[^>]+>', ' ', raw_html)
    return re.sub(r'\s+', ' ', html.unescape(text)).strip().lower()

# Health
for port in (8280, 8791):
    code, body, ms = fetch(f'http://127.0.0.1:{port}/health', timeout=3)
    check(code == 200 and ms < 1000, f'health {port} {ms}ms')

# Direct routes
route_bodies = {}
for route in ('/conversas', '/foco', '/gestao', '/agendas'):
    code, body, ms = fetch(f'http://127.0.0.1:8280{route}', timeout=8)
    route_bodies[route] = body.decode('utf-8', errors='replace')
    check(code == 200 and b'Inbox comercial' in body and ms < 2000, f'route {route} {ms}ms')

# Visible copy guard: users should see operação/comercial context, not internal provenance.
forbidden_visible_terms = ('auditoria', 'ledger', 'debug', 'evento técnico', 'fonte interna', 'log técnico')
for route, raw_html in route_bodies.items():
    visible = visible_text_from_html(raw_html)
    bad = [term for term in forbidden_visible_terms if term in visible]
    check(not bad, f'no internal/audit copy visible on {route}')

# Visual dark-mode guard: Rafael flagged a white native tab bar in /foco.
# Keep this in smoke gate (not only unittest) so a bad candidate cannot promote.
foco_html = route_bodies.get('/foco', '')
if '.focus-subtabs{' in foco_html:
    idx = foco_html.index('.focus-subtabs{')
    focus_tabs_css = foco_html[idx:idx+1400].lower()
    check('rgba(16,25,19,.86)' in focus_tabs_css and 'background:white' not in focus_tabs_css and 'background:#fff' not in focus_tabs_css and 'background:#ffffff' not in focus_tabs_css,
          'foco subtab dark visual guard')
else:
    check(False, 'foco subtab dark visual guard')

# Gestão SDR / Saúde da máquina: APIs read-only e rápidas precisam estar vivas no gate.
code, body, ms = fetch('http://127.0.0.1:8280/api/ops-health-summary', timeout=5)
ops = json.loads(body)
check(code == 200 and ops.get('mutates') is False and ops.get('risk') in ('ok', 'attention', 'critical') and ms < 1000,
      f'ops health summary risk={ops.get("risk")} {ms}ms')
check(bool(ops.get('watchdog')) and ops.get('watchdog', {}).get('label'),
      'ops health exposes monitoramento signal')

code, body, ms = fetch('http://127.0.0.1:8280/api/sdr-orchestrator-summary', timeout=8)
orch = json.loads(body)
check(code == 200 and orch.get('configured') is True and len(orch.get('sdrCards') or []) >= 3 and ms < 5000,
      f'sdr orchestrator cards={len(orch.get("sdrCards") or [])} {ms}ms')
check('approachPerformance' in orch and 'taskHygienePreview' in orch,
      'sdr orchestrator exposes approach performance and hygiene preview')

# Central Dexter: Gestão deve materializar crons/contextos em um endpoint read-only.
code, body, ms = fetch('http://127.0.0.1:8280/api/dexter-center?days=7&limit=20', timeout=6)
dexter = json.loads(body)
check(code == 200 and dexter.get('ok') is True and dexter.get('summary', {}).get('cronsTotal', 0) >= 1
      and isinstance(dexter.get('crons'), list) and isinstance(dexter.get('contexts'), list) and ms < 2000,
      f'dexter center crons={dexter.get("summary", {}).get("cronsTotal")} contexts={len(dexter.get("contexts") or [])} {ms}ms')

# Controle de agendas: endpoint read-only precisa estar vivo e rápido.
code, body, ms = fetch('http://127.0.0.1:8280/api/agendas?days=7', timeout=6)
agendas = json.loads(body)
check(code == 200 and agendas.get('ok') is True and isinstance(agendas.get('rows'), list)
      and isinstance(agendas.get('summary'), dict) and ms < 2000,
      f'agendas endpoint rows={len(agendas.get("rows") or [])} {ms}ms')

# Centralizador Dexter (subabas Crons/Contextos da rota /agendas): read-only e rápido.
code, body, ms = fetch('http://127.0.0.1:8280/api/dexter-center?days=14&limit=20', timeout=6)
dexter = json.loads(body)
check(code == 200 and dexter.get('ok') is True and isinstance(dexter.get('crons'), list)
      and isinstance(dexter.get('contexts'), list) and isinstance(dexter.get('summary'), dict)
      and ms < 2000,
      f'dexter-center endpoint crons={len(dexter.get("crons") or [])} contexts={len(dexter.get("contexts") or [])} {ms}ms')
# Privacidade: o resumo do centralizador nunca carrega o prompt completo do cron.
check(all('prompt' not in c for c in (dexter.get('crons') or [])),
      'dexter-center never exposes full cron prompt')

code, body, ms = fetch('http://127.0.0.1:8280/api/chips', timeout=6)
chips_payload = json.loads(body)
check(code == 200 and len(chips_payload.get('chips') or []) >= 8 and ms < 2500,
      f'chips endpoint count={len(chips_payload.get("chips") or [])} {ms}ms')

# Conversations endpoint: first call may compute, cached calls must be fast
code, body, ms = fetch('http://127.0.0.1:8280/api/conversations', timeout=12)
convs = json.loads(body).get('conversations', [])
check(code == 200 and len(convs) >= 250 and ms < 12000, f'conversations first {len(convs)} items {ms}ms')
for i in range(3):
    code, body, ms = fetch('http://127.0.0.1:8280/api/conversations', timeout=8)
    check(code == 200 and ms < 1500, f'conversations cached #{i+1} {ms}ms')

# Known institutional conversations that previously showed loading/empty.
known = [
    '4610::5519993361631@s.whatsapp.net',  # Cris/Boutique/Gustavo-like institutional path
    '4610::5555997175688@s.whatsapp.net',  # Boutique Gustavo PDF
    # 4607::5555997175688 era espelho de group_bridge_port, não envio real ao lead.
    # Incidente King Talhas 26/06: não exigir/mostrar falso remetente do comunicador.
    # 4607::5534992492012 é caso de card operacional sem bolha real no device; pelo
    # contrato atual, a listagem pode existir, mas o detalhe não deve inventar mensagem.
    '4607::5585988903132@s.whatsapp.net',  # Rafael institucional com bolhas reais verificadas
    '4605::5511987045720@s.whatsapp.net',  # Lunar/Breno: print com loading lento
]
for conv in known:
    url = 'http://127.0.0.1:8280/api/messages?conv=' + urllib.parse.quote(conv, safe='')
    code, body, ms = fetch(url, timeout=10)
    data = json.loads(body)
    msgs = data.get('messages', [])
    has_text = bool((msgs or [{}])[0].get('text') if msgs else '')
    check(code == 200 and msgs and has_text and ms < 2500, f'messages {conv} count={len(msgs)} {ms}ms')
    code2, body2, ms2 = fetch(url, timeout=8)
    check(code2 == 200 and ms2 < 500, f'messages cache {conv} {ms2}ms')

if FAILS:
    print('\nFAILED smoke gate:')
    for f in FAILS:
        print('-', f)
    sys.exit(1)
print('\nChannel V2 smoke/performance gate OK')
