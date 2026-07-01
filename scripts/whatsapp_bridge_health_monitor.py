#!/usr/bin/env python3
"""Watchdog silencioso da saúde dos bridges WhatsApp Zydon.

Não envia mensagens. Verifica apenas:
- /status conectado e sem QR nos chips esperados;
- endpoint /canonicalize disponível;
- canonicalização de um número BR conhecido com 9º dígito para o JID canônico.

Sem falha => stdout vazio, próprio para cron script-only.
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

PORTS = [4600, 4601, 4603, 4605, 4606, 4607, 4609, 4610]
TEST_REQUESTED = '5533988274655@s.whatsapp.net'
TEST_CANONICAL = '553388274655@s.whatsapp.net'


@dataclass(frozen=True)
class HealthFinding:
    port: int
    reason: str
    detail: str = ''


def get_json(url: str, timeout: float = 3.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def post_json(url: str, payload: dict[str, Any], timeout: float = 8.0) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def check_port(port: int, test_requested: str = TEST_REQUESTED, test_canonical: str = TEST_CANONICAL) -> list[HealthFinding]:
    findings: list[HealthFinding] = []
    base = f'http://127.0.0.1:{port}'
    try:
        status = get_json(f'{base}/status')
    except Exception as e:
        return [HealthFinding(port, 'status_indisponivel', str(e)[:160])]

    if status.get('connected') is not True:
        findings.append(HealthFinding(port, 'bridge_desconectado', json.dumps(status, ensure_ascii=False)[:240]))
    if status.get('needsQR') is True:
        findings.append(HealthFinding(port, 'qr_necessario', json.dumps(status, ensure_ascii=False)[:240]))
    if status.get('hasAuth') is not True:
        findings.append(HealthFinding(port, 'auth_ausente', json.dumps(status, ensure_ascii=False)[:240]))

    try:
        canon = post_json(f'{base}/canonicalize', {'to': test_requested})
    except urllib.error.HTTPError as e:
        findings.append(HealthFinding(port, 'canonicalize_http_error', f'{e.code} {e.reason}'[:160]))
        return findings
    except Exception as e:
        findings.append(HealthFinding(port, 'canonicalize_indisponivel', str(e)[:160]))
        return findings

    if canon.get('success') is not True:
        findings.append(HealthFinding(port, 'canonicalize_sem_success', json.dumps(canon, ensure_ascii=False)[:240]))
    if canon.get('jid') != test_canonical:
        findings.append(HealthFinding(port, 'canonicalize_jid_inesperado', json.dumps(canon, ensure_ascii=False)[:300]))
    if canon.get('changed') is not True:
        findings.append(HealthFinding(port, 'canonicalize_nao_corrigiu_9digito', json.dumps(canon, ensure_ascii=False)[:300]))
    return findings


def format_findings(findings: list[HealthFinding]) -> str:
    if not findings:
        return ''
    lines = ['⚠️ WhatsApp bridge health: falha em bridge/canonicalização']
    for f in findings:
        line = f'- port={f.port} motivo={f.reason}'
        if f.detail:
            line += f' detalhe={f.detail}'
        lines.append(line)
    return '\n'.join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--ports', default=','.join(str(p) for p in PORTS))
    ap.add_argument('--test-requested', default=TEST_REQUESTED)
    ap.add_argument('--test-canonical', default=TEST_CANONICAL)
    args = ap.parse_args()

    ports = [int(p.strip()) for p in args.ports.split(',') if p.strip()]
    findings: list[HealthFinding] = []
    for port in ports:
        findings.extend(check_port(port, args.test_requested, args.test_canonical))
    output = format_findings(findings)
    if output:
        print(output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
