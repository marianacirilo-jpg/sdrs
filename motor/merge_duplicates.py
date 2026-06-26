#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MERGE (unificação) de duplicatas no HubSpot — Zydon prospecção.

Lê o campo `duplicates` de /tmp/gate_qualified.json (produzido por gate.py) e
unifica os contatos duplicados no HubSpot, fundindo também os deals quando for
claramente o mesmo negócio.

OPERAÇÃO IRREVERSÍVEL -> DRY-RUN por padrão. Só toca no HubSpot com --apply.

Endpoints usados:
- Merge contatos: POST /crm/v3/objects/contacts/merge
- Deals de um contato: GET /crm/v4/associations/contacts/{id}/deals
- Nome do deal: GET /crm/v3/objects/deals/{id}?properties=dealname
- Merge deals: POST /crm/v3/objects/deals/merge

Fail-safe: qualquer erro de API é logado e o processamento CONTINUA. Nunca
derruba o ciclo.

CLI:
  python3 motor/merge_duplicates.py            # DRY-RUN (mostra plano)
  python3 motor/merge_duplicates.py --apply    # executa merges de verdade
  python3 motor/merge_duplicates.py --input /tmp/gate_qualified.json
"""
import os
import re
import sys
import json
import argparse
import unicodedata
import difflib
from datetime import datetime, timezone
from pathlib import Path
import urllib.request
import urllib.error

BASE_DIR = Path(__file__).resolve().parent.parent
CONTROLE_DIR = BASE_DIR / 'controle'
CICLO_LOG = CONTROLE_DIR / 'ciclo.log'
PROCESSED_EMAILS = CONTROLE_DIR / 'processed_emails.txt'
APRENDIZADOS = BASE_DIR / 'aprendizados_dedup.md'
DEFAULT_INPUT = '/tmp/gate_qualified.json'

BASE_URL = 'https://api.hubapi.com'
HTTP_TIMEOUT = 30

# Acima disso, dois nomes de deal são considerados "claramente o mesmo negócio".
DEAL_NAME_SIM_THRESHOLD = 0.85


def log(msg):
    """Append em controle/ciclo.log (best-effort, nunca derruba)."""
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        with open(CICLO_LOG, 'a', encoding='utf-8') as f:
            f.write(f'[{ts}] {msg}\n')
    except Exception:
        pass


def strip_accents(value):
    decomposed = unicodedata.normalize('NFKD', value or '')
    return ''.join(c for c in decomposed if not unicodedata.combining(c))


def norm_text(value):
    return strip_accents((value or '').strip().lower())


def name_similarity(a, b):
    """Similaridade 0..1 entre dois nomes de deal (normalizados)."""
    na, nb = norm_text(a), norm_text(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    # combina razão de sequência com overlap de palavras (pega reordenações).
    seq = difflib.SequenceMatcher(None, na, nb).ratio()
    wa, wb = set(na.split()), set(nb.split())
    overlap = len(wa & wb) / len(wa | wb) if (wa | wb) else 0.0
    return max(seq, overlap)


# --------------------------------------------------------------------------- #
# HubSpot HTTP (urllib stdlib)
# --------------------------------------------------------------------------- #
def get_token():
    return os.environ.get('HUBSPOT_API_KEY', '')


def _request(method, path, token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f'{BASE_URL}{path}',
        data=data,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else {}


def api_get(path, token):
    return _request('GET', path, token)


def api_post(path, token, body):
    return _request('POST', path, token, body)


def fetch_contact_deal_ids(contact_id, token):
    """IDs dos deals associados a um contato (v4 associations)."""
    if not contact_id:
        return []
    data = api_get(f'/crm/v4/associations/contacts/{contact_id}/deals', token)
    ids = []
    for row in data.get('results', []) or []:
        # v4: cada result tem 'toObjectId'
        did = row.get('toObjectId')
        if did is None and isinstance(row.get('to'), dict):
            did = row['to'].get('id')
        if did is not None:
            ids.append(str(did))
    return ids


def fetch_deal_name(deal_id, token):
    data = api_get(f'/crm/v3/objects/deals/{deal_id}?properties=dealname', token)
    return (data.get('properties', {}) or {}).get('dealname') or ''


def plan_deal_merges(deal_ids, token):
    """
    Dado um conjunto de deal_ids, identifica pares com nome muito similar
    (mesmo negócio) que deveriam ser fundidos. Retorna lista de dicts:
      {primary_id, primary_name, secondary_id, secondary_name, similarity}
    Em caso de incerteza, NÃO entra na lista (só seria registrado).
    """
    names = {}
    for did in deal_ids:
        try:
            names[did] = fetch_deal_name(did, token)
        except Exception as e:
            log(f'[merge] erro lendo dealname {did}: {e}')
    ids = list(names.keys())
    merges = []
    used = set()
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            if a in used or b in used:
                continue
            sim = name_similarity(names[a], names[b])
            if sim >= DEAL_NAME_SIM_THRESHOLD:
                merges.append({
                    'primary_id': a, 'primary_name': names[a],
                    'secondary_id': b, 'secondary_name': names[b],
                    'similarity': round(sim, 3),
                })
                used.add(b)  # mantém `a` como primário do deal
    return merges, names


# --------------------------------------------------------------------------- #
# Persistência local
# --------------------------------------------------------------------------- #
def append_aprendizado(dup, primary_company, deal_merges, applied):
    """Anexa um registro legível em aprendizados_dedup.md."""
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')
    modo = 'APLICADO' if applied else 'DRY-RUN'
    lines = [
        f'\n## {ts} — {primary_company or "(empresa desconhecida)"} [{modo}]',
        '',
        f'- **Emails envolvidos:** `{dup.get("primary_email")}` (primário) ⇆ '
        f'`{dup.get("secondary_email")}` (secundário)',
        f'- **Primário escolhido:** `{dup.get("primary_email")}` '
        f'(id {dup.get("primary_id")}, score {dup.get("primary_score")}) > '
        f'secundário score {dup.get("secondary_score")}',
        f'- **Sinais:** {", ".join(dup.get("signals") or []) or "—"}',
        f'- **Motivo:** {dup.get("reason") or "—"}',
    ]
    if deal_merges:
        for dm in deal_merges:
            lines.append(
                f'- **Deal fundido:** "{dm["primary_name"]}" (id {dm["primary_id"]}) '
                f'⇆ "{dm["secondary_name"]}" (id {dm["secondary_id"]}) '
                f'— similaridade {dm["similarity"]}'
            )
    else:
        lines.append('- **Deals:** nenhum par claramente igual para fundir.')
    lines.append('')
    try:
        new_file = not APRENDIZADOS.exists()
        with open(APRENDIZADOS, 'a', encoding='utf-8') as f:
            if new_file:
                f.write('# Aprendizados de deduplicação (merge HubSpot)\n')
            f.write('\n'.join(lines) + '\n')
    except Exception as e:
        log(f'[merge] erro escrevendo aprendizados_dedup.md: {e}')


def mark_secondary_processed(email):
    """Adiciona o email secundário (bare) em processed_emails.txt."""
    if not email:
        return
    email = email.strip().lower()
    try:
        existing = set()
        if PROCESSED_EMAILS.exists():
            with open(PROCESSED_EMAILS, 'r', encoding='utf-8') as f:
                existing = {
                    line.strip().lower().split('|')[0]
                    for line in f if line.strip()
                }
        if email in existing:
            return
        with open(PROCESSED_EMAILS, 'a', encoding='utf-8') as f:
            f.write(f'{email}\n')
    except Exception as e:
        log(f'[merge] erro atualizando processed_emails.txt: {e}')


# --------------------------------------------------------------------------- #
# Núcleo
# --------------------------------------------------------------------------- #
def load_input(path):
    p = Path(path)
    if not p.exists():
        return None
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)


def company_for(dup, leads_by_id):
    lead = leads_by_id.get(str(dup.get('primary_id')))
    if lead:
        return lead.get('company') or ''
    return ''


def print_plan_header(dup, company):
    print('-' * 72)
    print(f'DUPLICATA — {company or "(empresa desconhecida)"}')
    print(f'  PRIMÁRIO   : {dup.get("primary_email")} '
          f'(id {dup.get("primary_id")}, score {dup.get("primary_score")})')
    print(f'  SECUNDÁRIO : {dup.get("secondary_email")} '
          f'(id {dup.get("secondary_id")}, score {dup.get("secondary_score")})')
    print(f'  SINAIS     : {", ".join(dup.get("signals") or []) or "—"}')
    print(f'  MOTIVO     : {dup.get("reason") or "—"}')


def run_dry(dup, company, token):
    print_plan_header(dup, company)
    print('  AÇÃO       : fundir contato secundário -> primário '
          '(associações migram p/ o primário)')
    if not token:
        print('  DEALS      : análise pulada (HUBSPOT_API_KEY ausente). '
              'Com a chave, mostraria deals a fundir.')
        return
    try:
        deal_ids = sorted(set(
            fetch_contact_deal_ids(dup.get('primary_id'), token)
            + fetch_contact_deal_ids(dup.get('secondary_id'), token)
        ))
    except Exception as e:
        print(f'  DEALS      : não foi possível listar deals ({e}).')
        return
    if not deal_ids:
        print('  DEALS      : nenhum deal associado.')
        return
    merges, names = plan_deal_merges(deal_ids, token)
    print(f'  DEALS      : {len(deal_ids)} deal(s) após merge -> '
          f'{[names.get(d, d) for d in deal_ids]}')
    if merges:
        for dm in merges:
            print(f'    + FUNDIR deal "{dm["secondary_name"]}" (id {dm["secondary_id"]}) '
                  f'-> "{dm["primary_name"]}" (id {dm["primary_id"]}) '
                  f'[sim {dm["similarity"]}]')
    else:
        print('    (nenhum par de deals claramente igual; nada a fundir)')


def run_apply(dup, company, token):
    print_plan_header(dup, company)
    primary_id = str(dup.get('primary_id'))
    secondary_id = str(dup.get('secondary_id'))

    if not token:
        msg = 'HUBSPOT_API_KEY ausente'
        print(f'  RESULTADO  : ERRO ({msg})')
        log(f'[merge] primary={primary_id} secondary={secondary_id} resultado=erro:{msg}')
        return

    # 1) Merge de contatos.
    try:
        api_post('/crm/v3/objects/contacts/merge', token, {
            'primaryObjectId': primary_id,
            'objectIdToMerge': secondary_id,
        })
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read().decode()[:200]
        except Exception:
            pass
        msg = f'HTTP {e.code} {body}'
        print(f'  RESULTADO  : ERRO no merge de contato ({msg})')
        log(f'[merge] primary={primary_id} secondary={secondary_id} resultado=erro:{msg}')
        return
    except Exception as e:
        print(f'  RESULTADO  : ERRO no merge de contato ({e})')
        log(f'[merge] primary={primary_id} secondary={secondary_id} resultado=erro:{e}')
        return

    print('  CONTATO    : merge OK (secundário fundido no primário)')
    log(f'[merge] primary={primary_id} secondary={secondary_id} resultado=ok')

    # 2) Merge de deals (best-effort; falha aqui não derruba).
    deal_merges = []
    try:
        deal_ids = fetch_contact_deal_ids(primary_id, token)
        candidate_merges, names = plan_deal_merges(deal_ids, token)
        for dm in candidate_merges:
            try:
                api_post('/crm/v3/objects/deals/merge', token, {
                    'primaryObjectId': dm['primary_id'],
                    'secondaryObjectId': dm['secondary_id'],
                })
                deal_merges.append(dm)
                print(f'  DEAL       : merge OK "{dm["secondary_name"]}" -> '
                      f'"{dm["primary_name"]}" [sim {dm["similarity"]}]')
                log(f'[merge] deal primary={dm["primary_id"]} '
                    f'secondary={dm["secondary_id"]} resultado=ok')
            except Exception as e:
                print(f'  DEAL       : ERRO ao fundir deal {dm["secondary_id"]} ({e})')
                log(f'[merge] deal primary={dm["primary_id"]} '
                    f'secondary={dm["secondary_id"]} resultado=erro:{e}')
    except Exception as e:
        print(f'  DEALS      : análise pós-merge falhou ({e})')
        log(f'[merge] deals primary={primary_id} resultado=erro:{e}')

    # 3) Aprendizado + 4) marcar secundário como processado.
    append_aprendizado(dup, company, deal_merges, applied=True)
    mark_secondary_processed(dup.get('secondary_email'))
    print('  PÓS        : aprendizado registrado + secundário marcado em processed_emails.txt')


def main():
    parser = argparse.ArgumentParser(description='Merge de duplicatas no HubSpot.')
    parser.add_argument('--apply', action='store_true',
                        help='Executa os merges de verdade (sem isto = DRY-RUN).')
    parser.add_argument('--input', default=DEFAULT_INPUT,
                        help=f'JSON de entrada (default {DEFAULT_INPUT}).')
    args = parser.parse_args()

    data = load_input(args.input)
    if not data:
        print('NENHUMA_DUPLICATA')
        return 0
    duplicates = data.get('duplicates') or []
    if not duplicates:
        print('NENHUMA_DUPLICATA')
        return 0

    leads_by_id = {str(l.get('id')): l for l in (data.get('leads') or [])}
    token = get_token()

    modo = 'APPLY (executando merges)' if args.apply else 'DRY-RUN (apenas plano)'
    print(f'=== MERGE DE DUPLICATAS — {modo} ===')
    print(f'Entrada: {args.input} | duplicatas: {len(duplicates)} | '
          f'HubSpot key: {"presente" if token else "AUSENTE"}')

    for dup in duplicates:
        company = company_for(dup, leads_by_id)
        try:
            if args.apply:
                run_apply(dup, company, token)
            else:
                run_dry(dup, company, token)
        except Exception as e:
            # Fail-safe absoluto: nunca derruba o ciclo.
            print(f'  ERRO inesperado processando duplicata: {e}')
            log(f'[merge] primary={dup.get("primary_id")} '
                f'secondary={dup.get("secondary_id")} resultado=erro:{e}')

    print('-' * 72)
    if not args.apply:
        print('DRY-RUN concluído. Nada foi alterado no HubSpot. '
              'Use --apply para executar.')
    else:
        print('APPLY concluído.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
