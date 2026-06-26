#!/usr/bin/env python3
"""Dashboard público (com token) dos envios WhatsApp Zydon.

Lê controle/wpp_envios.json ao vivo e expõe:
  GET /?t=<token>              UI
  GET /api/envios?t=<token>    JSON normalizado
  GET /health                  saúde sem dados sensíveis

Sem dependências externas: usa apenas stdlib.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import secrets
import socket
import sys
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE = Path(__file__).resolve().parents[1]
WPP = BASE / "controle" / "wpp_envios.json"
TOKEN_FILE = BASE / "controle" / "dashboard_token.txt"
UTC = timezone.utc
BRT = timezone(timedelta(hours=-3))


def ensure_token() -> str:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    if TOKEN_FILE.exists():
        tok = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if tok:
            return tok
    tok = secrets.token_urlsafe(24)
    TOKEN_FILE.write_text(tok + "\n", encoding="utf-8")
    try:
        os.chmod(TOKEN_FILE, 0o600)
    except Exception:
        pass
    return tok


def parse_dt(value: str | None):
    if not value:
        return None
    s = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


def normalized_dt(r: dict):
    """Datetime aware correto para ordenação/exibição.

    Ledger histórico misturou formatos:
    - diagnóstico/process_gate: `date` em BRT;
    - primeiro_contato antigo/disparo_dinamico: `date` em UTC sem timezone;
    - primeiro_contato novo: `date_tz` ISO com timezone BRT.
    """
    explicit = str(r.get("date_tz") or r.get("sent_at") or "").strip()
    if explicit:
        try:
            dt = datetime.fromisoformat(explicit.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=BRT)
            return dt
        except Exception:
            pass
    raw = r.get("date") or r.get("data") or r.get("ts") or r.get("created_at") or ""
    dt = parse_dt(str(raw) if raw else None)
    if not dt:
        return None
    if dt.tzinfo is None:
        mt = str(r.get("msg_type") or "").lower()
        dt = dt.replace(tzinfo=UTC if mt == "primeiro_contato" else BRT)
    return dt


def brt_display(dt):
    if not dt:
        return ""
    return dt.astimezone(BRT).strftime("%d/%m/%Y %H:%M")


def status_ok(r: dict) -> bool:
    if str(r.get("status", "")).lower() in {"enviado_lead", "enviado_mql", "enviado", "sent"}:
        return True
    if str(r.get("text_status", "")).lower() in {"ok", "sent", "success"}:
        return True
    if str(r.get("lead_text_status", "")).lower() in {"ok", "sent", "success"}:
        return True
    return False


def tipo(r: dict) -> str:
    mt = str(r.get("msg_type") or "").lower()
    st = str(r.get("status") or "").lower()
    if mt == "primeiro_contato":
        return "Follow-up / 1º contato SDR"
    if st == "nao_mql_grupo":
        return "Não-MQL (aviso interno)"
    if st in {"enviado_lead", "enviado_mql"} or r.get("pdf_status") or r.get("file_response") or r.get("pdf_messageId") or r.get("messageId_pdf"):
        return "Diagnóstico MQL"
    return "Envio WhatsApp"


def get_msg_id(r: dict) -> str:
    for k in (
        "messageId", "message_id", "text_messageId", "pdf_messageId", "messageId_texto", "messageId_pdf",
        "lead_text_messageId", "text_message_id", "pdf_message_id", "group_text_messageId", "group_pdf_messageId"
    ):
        v = r.get(k)
        if v:
            return str(v)
    # alguns registros guardam response como dict/string JSON
    for k in ("response", "text_response", "file_response", "group_summary_response"):
        v = r.get(k)
        if isinstance(v, dict):
            mid = v.get("messageId") or v.get("id")
            if mid:
                return str(mid)
        elif isinstance(v, str) and "messageId" in v:
            try:
                obj = json.loads(v)
                mid = obj.get("messageId") or obj.get("id")
                if mid:
                    return str(mid)
            except Exception:
                pass
    return ""


def normalize() -> list[dict]:
    try:
        raw = json.loads(WPP.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            raw = raw.get("envios") or raw.get("items") or []
        if not isinstance(raw, list):
            raw = []
    except Exception as e:
        return [{"erro": f"Falha lendo {WPP}: {e}"}]

    out = []
    for i, r in enumerate(raw):
        if not isinstance(r, dict):
            continue
        dt_s = r.get("date") or r.get("data") or r.get("ts") or r.get("created_at") or ""
        dt = normalized_dt(r)
        empresa = r.get("empresa") or r.get("company") or r.get("slug") or r.get("lead") or ""
        nome = r.get("nome") or r.get("name") or ""
        text = r.get("text") or r.get("mensagem") or r.get("message") or ""
        item = {
            "idx": i,
            "date": brt_display(dt) or str(dt_s),
            "date_raw": str(dt_s),
            "sort": dt.astimezone(UTC).isoformat() if dt else str(dt_s),
            "tipo": tipo(r),
            "sdr": r.get("sdr") or r.get("conta") or ("Mariana/Institucional" if str(r.get("status", "")).lower() in {"enviado_lead", "enviado_mql", "nao_mql_grupo"} else ""),
            "empresa": str(empresa or ""),
            "nome": str(nome or ""),
            "email": str(r.get("email") or ""),
            "destino": str(r.get("to") or r.get("jid") or r.get("lead_jid") or r.get("telefone") or r.get("tel") or ""),
            "slug": str(r.get("slug") or ""),
            "status": str(r.get("status") or ""),
            "text_status": str(r.get("text_status") or r.get("lead_text_status") or ""),
            "pdf_status": str(r.get("pdf_status") or r.get("lead_pdf_status") or ""),
            "bridge_port": str(r.get("bridge_port") or r.get("porta") or r.get("group_bridge_port") or ""),
            "message_id": get_msg_id(r),
            "hubspot_task": str(r.get("task_id") or ""),
            "deal_id": str(r.get("deal_id") or ""),
            "ok": status_ok(r),
            "text": str(text or ""),
        }
        out.append(item)
    out.sort(key=lambda x: x.get("sort") or "", reverse=True)
    return out


HTML_PAGE = r"""<!doctype html>
<html lang="pt-br"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Zydon — Envios WhatsApp</title>
<style>
:root{--bg:#080b0f;--card:#111821;--muted:#8ca0b3;--txt:#eaf2ff;--green:#cdeb00;--bad:#ff6b6b;--line:#243041}
*{box-sizing:border-box} body{margin:0;background:linear-gradient(180deg,#071016,#080b0f);font-family:Inter,system-ui,-apple-system,Segoe UI,Arial,sans-serif;color:var(--txt)}
header{position:sticky;top:0;z-index:2;background:rgba(8,11,15,.92);backdrop-filter:blur(10px);border-bottom:1px solid var(--line);padding:16px 20px}
h1{margin:0;font-size:22px}.sub{color:var(--muted);font-size:13px;margin-top:4px}.wrap{padding:18px;max-width:1440px;margin:auto}
.stats{display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:12px;margin-bottom:14px}.stat{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px}.stat b{font-size:26px;color:var(--green)}.stat span{display:block;color:var(--muted);font-size:12px;margin-top:4px}
.filters{display:grid;grid-template-columns:1.5fr repeat(3, minmax(140px,.6fr));gap:10px;margin-bottom:14px}input,select{width:100%;background:#0b1118;color:var(--txt);border:1px solid var(--line);border-radius:12px;padding:12px;font-size:14px}
table{width:100%;border-collapse:separate;border-spacing:0 8px}th{font-size:12px;color:var(--muted);text-align:left;font-weight:600;padding:0 10px}td{background:var(--card);border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:12px 10px;vertical-align:top;font-size:13px}td:first-child{border-left:1px solid var(--line);border-radius:12px 0 0 12px}td:last-child{border-right:1px solid var(--line);border-radius:0 12px 12px 0}.badge{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:4px 8px;font-size:12px}.ok{color:#9cff9c;border-color:#295b35}.warn{color:#ffd27a;border-color:#66521f}.bad{color:var(--bad);border-color:#6b2a2a}.muted{color:var(--muted)}.msg{max-width:460px;white-space:pre-wrap;line-height:1.35}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}.small{font-size:12px;color:var(--muted)}button{background:var(--green);color:#111;border:0;border-radius:10px;padding:9px 12px;font-weight:700;cursor:pointer}.copy{background:#1d2a38;color:var(--txt);border:1px solid var(--line)}
@media(max-width:900px){.stats,.filters{grid-template-columns:1fr}table,thead,tbody,tr,td,th{display:block}thead{display:none}td{border-left:1px solid var(--line)!important;border-right:1px solid var(--line)!important;border-radius:0!important}td:first-child{border-radius:12px 12px 0 0!important}td:last-child{border-radius:0 0 12px 12px!important;margin-bottom:10px}.msg{max-width:none}}
</style></head><body>
<header><h1>Zydon — Envios WhatsApp</h1><div class="sub">Diagnósticos, avisos Não-MQL e follow-ups SDR. Atualiza automaticamente a cada 20s. Fonte: controle/wpp_envios.json</div></header>
<div class="wrap">
  <div class="stats" id="stats"></div>
  <div class="filters">
    <input id="q" placeholder="Buscar empresa, nome, email, telefone, mensagem...">
    <select id="tipo"><option value="">Todos os tipos</option></select>
    <select id="sdr"><option value="">Todos os remetentes</option></select>
    <select id="periodo"><option value="7">Últimos 7 dias</option><option value="1">Hoje/24h</option><option value="30">Últimos 30 dias</option><option value="0">Tudo</option></select>
  </div>
  <div class="small" id="updated"></div>
  <table><thead><tr><th>Quando</th><th>Tipo</th><th>Remetente</th><th>Lead/Empresa</th><th>Destino</th><th>Status</th><th>Mensagem</th><th>IDs</th></tr></thead><tbody id="rows"></tbody></table>
</div>
<script>
const token = new URLSearchParams(location.search).get('t') || new URLSearchParams(location.search).get('token') || '';
let all=[];
const esc=s=>(s||'').toString().replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
function statusBadge(r){
  if(r.ok) return '<span class="badge ok">OK</span>';
  if((r.status||'').includes('nao_mql')) return '<span class="badge warn">Interno</span>';
  return '<span class="badge bad">Verificar</span>';
}
function daysAgo(s){const d=new Date(s||''); return isNaN(d)?99999:(Date.now()-d.getTime())/86400000;}
function fillOptions(){
  for(const [id,key] of [['tipo','tipo'],['sdr','sdr']]){
    const el=document.getElementById(id), cur=el.value;
    const vals=[...new Set(all.map(x=>x[key]).filter(Boolean))].sort();
    el.innerHTML='<option value="">'+(id==='tipo'?'Todos os tipos':'Todos os remetentes')+'</option>'+vals.map(v=>`<option>${esc(v)}</option>`).join('');
    el.value=cur;
  }
}
function render(){
 const q=document.getElementById('q').value.toLowerCase(); const tipo=document.getElementById('tipo').value; const sdr=document.getElementById('sdr').value; const per=+document.getElementById('periodo').value;
 let rows=all.filter(r=>(!tipo||r.tipo===tipo)&&(!sdr||r.sdr===sdr)&&(!per||daysAgo(r.sort)<=per));
 if(q) rows=rows.filter(r=>JSON.stringify(r).toLowerCase().includes(q));
 const total=all.length, diag=all.filter(r=>r.tipo==='Diagnóstico MQL').length, foll=all.filter(r=>r.tipo.includes('Follow')).length, ok=all.filter(r=>r.ok).length;
 document.getElementById('stats').innerHTML=`<div class="stat"><b>${total}</b><span>registros totais</span></div><div class="stat"><b>${diag}</b><span>diagnósticos MQL</span></div><div class="stat"><b>${foll}</b><span>follow-ups / 1º contato</span></div><div class="stat"><b>${ok}</b><span>com envio OK</span></div>`;
 document.getElementById('rows').innerHTML=rows.map(r=>`<tr>
  <td><b>${esc(r.date)}</b><div class="small">porta ${esc(r.bridge_port||'-')}</div></td>
  <td><span class="badge">${esc(r.tipo)}</span></td>
  <td>${esc(r.sdr||'-')}</td>
  <td><b>${esc(r.empresa||r.slug||'-')}</b><div class="small">${esc(r.nome)} ${r.email?('· '+esc(r.email)):''}</div></td>
  <td class="mono">${esc(r.destino||'-')}</td>
  <td>${statusBadge(r)}<div class="small">${esc(r.status||'')} ${esc(r.text_status||'')} ${esc(r.pdf_status||'')}</div></td>
  <td><div class="msg">${esc(r.text||'(sem texto salvo no registro)')}</div></td>
  <td class="mono"><div>${esc(r.message_id||'-')}</div><div class="small">deal ${esc(r.deal_id||'-')}<br>task ${esc(r.hubspot_task||'-')}</div></td>
 </tr>`).join('') || '<tr><td colspan="8">Nada encontrado.</td></tr>';
}
async function load(){
 const res=await fetch('/api/envios?t='+encodeURIComponent(token), {cache:'no-store'});
 if(!res.ok){document.body.innerHTML='<div class="wrap"><h1>Acesso negado ou API fora</h1><p>Use o link com token.</p></div>'; return;}
 const data=await res.json(); all=data.items||[]; fillOptions(); render(); document.getElementById('updated').textContent='Atualizado: '+new Date().toLocaleString('pt-BR')+' · mostrando registros mais recentes primeiro';
}
['q','tipo','sdr','periodo'].forEach(id=>document.addEventListener('input',e=>{if(e.target.id===id)render()}));
load(); setInterval(load,20000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "ZydonEnviosDashboard/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (datetime.now().isoformat(timespec="seconds"), fmt % args))

    def _token_ok(self) -> bool:
        qs = parse_qs(urlparse(self.path).query)
        got = (qs.get("t") or qs.get("token") or [""])[0]
        return bool(got) and secrets.compare_digest(got, self.server.token)  # type: ignore[attr-defined]

    def _send(self, code: int, body: bytes, ctype="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            body = json.dumps({"ok": True, "source": str(WPP), "count": len(normalize()), "time": datetime.now().isoformat()}, ensure_ascii=False).encode()
            return self._send(200, body, "application/json; charset=utf-8")
        if not self._token_ok():
            return self._send(403, b"Acesso negado. Use o link com token.\n", "text/plain; charset=utf-8")
        if path == "/api/envios":
            items = normalize()
            body = json.dumps({"items": items, "count": len(items), "source_mtime": WPP.stat().st_mtime if WPP.exists() else None}, ensure_ascii=False).encode()
            return self._send(200, body, "application/json; charset=utf-8")
        if path in {"/", "/index.html"}:
            return self._send(200, HTML_PAGE.encode("utf-8"))
        return self._send(404, b"Not found\n", "text/plain; charset=utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--print-url", action="store_true")
    args = ap.parse_args()
    token = ensure_token()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    httpd.token = token  # type: ignore[attr-defined]
    url = f"http://127.0.0.1:{args.port}/?t={token}"
    if args.print_url:
        print(url)
        return
    print(f"Dashboard rodando em http://{args.host}:{args.port}/?t={token}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
