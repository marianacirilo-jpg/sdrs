#!/usr/bin/env python3
"""Smoke/performance gate for Zydon Channel V2.

Starts no services by default; expects 8280/8791 already running.
Fails if core routes/APIs are slow or broken.
"""
import importlib.util
import json
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

# Health
for port in (8280, 8791):
    code, body, ms = fetch(f'http://127.0.0.1:{port}/health', timeout=3)
    check(code == 200 and ms < 1000, f'health {port} {ms}ms')

# Direct routes
for route in ('/conversas', '/foco', '/gestao'):
    code, body, ms = fetch(f'http://127.0.0.1:8280{route}', timeout=8)
    check(code == 200 and b'Inbox comercial' in body and ms < 2000, f'route {route} {ms}ms')

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
    '4607::5534992492012@s.whatsapp.net',  # BIOCOM Rafael/Sarah
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
