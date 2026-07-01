#!/usr/bin/env python3
"""Fila/SLA de follow-up SDR Zydon — somente leitura.

Gera um snapshot simples e auditável da máquina de follow-up:
- pós-diagnóstico => Follow-up 1 determinístico
- régua Primeiro Contato => Follow-up 1/2/3/4
- vencidos/bloqueados por pesquisa
- produção do dia por fase

Não envia WhatsApp, não cria task e não move deals.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/root/.hermes/zydon-prospeccao')
BRT = None
try:
    from zoneinfo import ZoneInfo
    BRT = ZoneInfo('America/Sao_Paulo')
except Exception:
    BRT = timezone.utc


def load_module(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).replace('Z', '+00:00')
    try:
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def today_brt_str():
    return datetime.now(timezone.utc).astimezone(BRT).date().isoformat()


def phase_from_msg_type(msg_type: str, status: str = '') -> str | None:
    t = (msg_type or '').lower()
    st = (status or '').lower()
    if 'mql_followup1' in t or 'followup1' in t or 'follow_1' in t or 'follow-up 1' in t or 'enviado_followup1' in st:
        return 'F1'
    if 'followup2' in t or 'follow_2' in t or 'follow-up 2' in t:
        return 'F2'
    if 'followup3' in t or 'follow_3' in t or 'follow-up 3' in t:
        return 'F3'
    if 'followup4' in t or 'follow_4' in t or 'follow-up 4' in t:
        return 'F4'
    # cadencia_primeiro_contato records sometimes carry attempt/next_attempt instead.
    return None


def sent_today_by_phase(envios):
    today = today_brt_str()
    c = Counter()
    for e in envios:
        if not isinstance(e, dict):
            continue
        dt = parse_dt(e.get('date_tz') or e.get('date'))
        if not dt or dt.astimezone(BRT).date().isoformat() != today:
            continue
        if str(e.get('status') or '').lower() in {'deleted', 'deletado', 'superseded', 'cancelado'}:
            continue
        phase = None
        for k in ('next_attempt', 'attempt', 'attempt_number', 'followup_attempt'):
            if e.get(k):
                try:
                    n = int(e.get(k))
                    if 1 <= n <= 4:
                        phase = f'F{n}'
                        break
                except Exception:
                    pass
        if not phase:
            phase = phase_from_msg_type(str(e.get('msg_type') or ''), str(e.get('status') or ''))
        if phase:
            c[phase] += 1
    return c


def count_deals_in_stage(d, stage_id: str) -> int:
    """Conta todos os deals do HubSpot em uma etapa do pipeline principal.

    Concilia a foto visual do quadro (ex.: Primeiro Contato / Lead Sem Contato)
    com a régua de follow-up. Somente leitura.
    """
    url = 'https://api.hubapi.com/crm/v3/objects/deals/search'
    body = {
        'filterGroups': [{'filters': [
            {'propertyName': 'pipeline', 'operator': 'EQ', 'value': d.PIPELINE},
            {'propertyName': 'dealstage', 'operator': 'EQ', 'value': stage_id},
        ]}],
        'properties': ['dealstage'],
        'limit': 100,
    }
    total = 0
    after = None
    while True:
        if after:
            body['after'] = after
        elif 'after' in body:
            del body['after']
        res = d.hs_request(url, 'POST', body)
        if not res:
            break
        total += len(res.get('results') or [])
        after = (res.get('paging') or {}).get('next', {}).get('after')
        if not after:
            break
    return total


def build_snapshot():
    sys.path.insert(0, str(ROOT))
    cad = load_module('cadencia_primeiro_contato_status', 'scripts/cadencia_primeiro_contato.py')
    mql = load_module('mql_sdr_followup_status', 'scripts/mql_sdr_followup.py')
    d = cad.d
    envios = d.load_envios()

    # Pós-diagnóstico => F1
    mql_candidates = mql.collect(envios, max_age_hours=48)
    mql_by_owner = Counter((r.get('sdr') or r.get('owner_name') or r.get('owner_id') or 'sem_owner') for r in mql_candidates)

    # Régua F1/F2/F3/F4 em Primeiro Contato. Rafael exigiu transparência total:
    # não mostrar só os prontos; mostrar também o que ainda não venceu janela e
    # o que está bloqueado por pesquisa, para provar que nada fica travado.
    candidates, nurture_due, stats, blocked_examples = cad.collect_candidates(move_interacted=False, max_deals_per_owner=None, require_research=False)
    raw_by_phase = Counter()
    researched_by_phase = Counter()
    missing_research_by_phase = Counter()
    owner_phase = defaultdict(Counter)
    overdue = []
    now = datetime.now(timezone.utc)
    for lead in candidates:
        n = int(lead.get('next_attempt') or 1)
        if n < 1 or n > 4:
            continue
        phase = f'F{n}'
        raw_by_phase[phase] += 1
        owner_phase[lead.get('owner_name') or lead.get('owner_key') or 'sem_owner'][phase] += 1
        has_study = bool(cad.lead_has_study(lead, n))
        if has_study:
            researched_by_phase[phase] += 1
        else:
            missing_research_by_phase[phase] += 1
        # SLA simples: se já venceu pela lógica da cadência mas ainda falta estudo, risco operacional.
        age_days = float(lead.get('days_since_first') or 0)
        if not has_study and len(overdue) < 12:
            overdue.append({
                'phase': phase,
                'owner': lead.get('owner_name'),
                'empresa': lead.get('empresa'),
                'deal_id': lead.get('deal_id'),
                'days_since_first': age_days,
                'reason': 'pronto pela janela, bloqueado por falta de pesquisa/estudo',
            })

    # Não somar matriz histórica ao total atual: a fonte de verdade para
    # contagem de fluxo é a leitura viva do HubSpot + ledger. A matriz serve para
    # destravar pesquisa, mas pode carregar deal antigo/stale.
    pending_by_phase = Counter(raw_by_phase)
    pending_by_phase['F1'] += len(mql_candidates)

    ready_by_phase = Counter(researched_by_phase)
    ready_by_phase['F1'] += len(mql_candidates)

    sent = sent_today_by_phase(envios)
    phases = ['F1', 'F2', 'F3', 'F4']
    stage_counts = {
        'Lead Sem Contato': count_deals_in_stage(d, '984052829'),
        'Primeiro Contato': count_deals_in_stage(d, '1214320997'),
    }
    stats_totals = Counter()
    for st in stats.values():
        for k, v in (st or {}).items():
            try:
                stats_totals[k] += int(v or 0)
            except Exception:
                pass
    primeiro_contato_bucket_total = (
        sum(raw_by_phase[p] for p in phases)
        + stats_totals['nao_venceu_janela']
        + stats_totals['sem_tel']
        + stats_totals['sem_d0']
        + stats_totals['respondidos_interagidos']
        + len(nurture_due)
    )
    primeiro_contato_explicacao = {
        'total_hubspot': stage_counts['Primeiro Contato'],
        'pendentes_follow_agora': sum(raw_by_phase[p] for p in phases),
        'ainda_nao_venceu_janela': stats_totals['nao_venceu_janela'],
        'sem_telefone': stats_totals['sem_tel'],
        'sem_d0_ou_ledger_claro': stats_totals['sem_d0'],
        'respondeu_ou_interagiu': stats_totals['respondidos_interagidos'],
        'nurture_due': len(nurture_due),
        'fora_da_regua_ou_owner_nao_sdr': max(0, stage_counts['Primeiro Contato'] - primeiro_contato_bucket_total),
    }
    lead_sem_contato_explicacao = {
        'total_hubspot': stage_counts['Lead Sem Contato'],
        'proxima_acao': 'entrada de funil / Follow 1 quando passar gates de MQL, telefone, dedupe, horário e limite de chip',
    }
    snapshot = {
        'generated_at_brt': datetime.now(timezone.utc).astimezone(BRT).isoformat(),
        'summary': {
            'pending_total': sum(pending_by_phase[p] for p in phases),
            'ready_total': sum(ready_by_phase[p] for p in phases),
            'blocked_research_total': sum(missing_research_by_phase[p] for p in phases),
            'sent_today_total': sum(sent[p] for p in phases),
            'hubspot_inicio_funil_total': sum(stage_counts.values()),
        },
        'hubspot_stage_counts': stage_counts,
        'pipeline_flow': {
            'garantia': 'não existe travamento permanente: todo lead fica em um bucket explícito e recebe follow quando vencer janela/gate ou é movido para a etapa correta se respondeu/interagiu',
            'Lead Sem Contato': lead_sem_contato_explicacao,
            'Primeiro Contato': primeiro_contato_explicacao,
        },
        'pending_by_phase': {p: pending_by_phase[p] for p in phases},
        'ready_by_phase': {p: ready_by_phase[p] for p in phases},
        'blocked_research_by_phase': {p: missing_research_by_phase[p] for p in phases},
        'sent_today_by_phase': {p: sent[p] for p in phases},
        'mql_f1': {
            'pending': len(mql_candidates),
            'by_owner': dict(mql_by_owner),
        },
        'cadence_primeiro_contato': {
            'pending_raw_by_phase': {p: raw_by_phase[p] for p in phases},
            'ready_with_research_by_phase': {p: researched_by_phase[p] for p in phases},
            'missing_research_by_phase': {p: missing_research_by_phase[p] for p in phases},
            'owner_phase': {owner: dict(cnt) for owner, cnt in owner_phase.items()},
            'stats_by_owner': stats,
            'blocked_examples': blocked_examples[:8],
        },
        'sla_risks_examples': overdue,
        'nurture_due': len(nurture_due),
    }
    return snapshot


def render_human(s):
    lines = []
    lines.append(f"Fila follow-up SDR — {s['generated_at_brt']}")
    lines.append('')
    hs = s.get('hubspot_stage_counts') or {}
    flow = s.get('pipeline_flow') or {}
    pc = flow.get('Primeiro Contato') or {}
    lsc = flow.get('Lead Sem Contato') or {}
    lines.append('QUADRO HUBSPOT / INÍCIO DO FUNIL:')
    lines.append(f"- Lead Sem Contato: {hs.get('Lead Sem Contato', 0)} | próxima ação: {lsc.get('proxima_acao', 'Follow 1 quando elegível')}")
    lines.append(f"- Primeiro Contato: {hs.get('Primeiro Contato', 0)} | {pc.get('pendentes_follow_agora', 0)} já elegíveis na régua | {pc.get('ainda_nao_venceu_janela', 0)} ainda não venceram janela")
    lines.append(f"TOTAL INÍCIO DO FUNIL: {s['summary'].get('hubspot_inicio_funil_total', 0)}")
    lines.append('')
    lines.append('PENDENTES POR FOLLOW:')
    for p in ['F1', 'F2', 'F3', 'F4']:
        lines.append(f"- {p}: {s['pending_by_phase'][p]} pendentes | {s['ready_by_phase'][p]} prontos | {s['blocked_research_by_phase'][p]} bloqueados por pesquisa | {s['sent_today_by_phase'][p]} enviados hoje")
    lines.append(f"TOTAL FOLLOWS: {s['summary']['pending_total']} pendentes | {s['summary']['ready_total']} prontos | {s['summary']['blocked_research_total']} bloqueados por pesquisa | {s['summary']['sent_today_total']} enviados hoje")
    lines.append('')
    lines.append('GARANTIA DE FLUXO:')
    lines.append(f"- {flow.get('garantia', 'Todo lead tem que ficar em bucket explícito e voltar para a régua quando elegível.')}")
    lines.append(f"- Primeiro Contato não elegível agora: {pc.get('ainda_nao_venceu_janela', 0)} janela | {pc.get('sem_telefone', 0)} sem telefone | {pc.get('sem_d0_ou_ledger_claro', 0)} sem D0/ledger claro | {pc.get('respondeu_ou_interagiu', 0)} respondeu/interagiu | {pc.get('nurture_due', 0)} nutrição/perdido pós-F4 | {pc.get('fora_da_regua_ou_owner_nao_sdr', 0)} fora da régua/owner não SDR")
    if s.get('sla_risks_examples'):
        lines.append('')
        lines.append('RISCOS/SLA — exemplos bloqueados por pesquisa:')
        for r in s['sla_risks_examples'][:6]:
            lines.append(f"- {r['phase']} {r.get('owner')}: {r.get('empresa')} (deal {r.get('deal_id')}) — {r.get('reason')}")
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--write', default='controle/sdr_followup_queue_status.json')
    ap.add_argument('--alert', action='store_true', help='stdout only on anomaly')
    ap.add_argument('--min-ready-alert', type=int, default=50)
    ap.add_argument('--min-blocked-research-alert', type=int, default=50)
    args = ap.parse_args()

    # Algumas funções legadas imprimem avisos de HubSpot durante a coleta
    # (ex.: contato associado escolhido). Capturar isso para manter stdout
    # limpo/parseável; o snapshot é a saída oficial.
    noise = io.StringIO()
    with contextlib.redirect_stdout(noise):
        snap = build_snapshot()
    out_path = ROOT / args.write
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding='utf-8')

    if args.alert:
        alerts = []
        flow = snap.get('pipeline_flow') or {}
        pc = flow.get('Primeiro Contato') or {}
        non_time = {
            'bloqueados_por_pesquisa': int(snap['summary'].get('blocked_research_total') or 0),
            'sem_telefone': int(pc.get('sem_telefone') or 0),
            'sem_d0_ou_ledger_claro': int(pc.get('sem_d0_ou_ledger_claro') or 0),
            'respondeu_ou_interagiu': int(pc.get('respondeu_ou_interagiu') or 0),
            'fora_da_regua_ou_owner_nao_sdr': int(pc.get('fora_da_regua_ou_owner_nao_sdr') or 0),
        }
        non_time_total = sum(non_time.values())
        if non_time_total > 0:
            alerts.append(f"{non_time_total} leads parados por motivo que NÃO é tempo/janela: " + ', '.join(f"{k}={v}" for k, v in non_time.items() if v))
        if snap['summary']['ready_total'] >= args.min_ready_alert:
            alerts.append(f"fila pronta alta: {snap['summary']['ready_total']} leads prontos para follow-up")
        if alerts:
            print('ALERTA — lead parado fora de janela / fila follow-up SDR')
            for a in alerts:
                print(f'- {a}')
            print(render_human(snap))
        return 0

    if args.json:
        print(json.dumps(snap, ensure_ascii=False, indent=2))
    else:
        print(render_human(snap))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
