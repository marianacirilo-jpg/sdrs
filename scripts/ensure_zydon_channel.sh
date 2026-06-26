#!/usr/bin/env bash
set -euo pipefail
PROJECT="/root/.hermes/zydon-prospeccao"
WA="/root/.hermes/whatsapp-extra"
LOG_DIR="$PROJECT/logs"
mkdir -p "$LOG_DIR"

start_bridge() {
  local port="$1" auth="$2"
  # CHIPS_PAUSED.flag: chips que NÃO devem ser reiniciados pelo watchdog.
  if [ -f "$PROJECT/controle/CHIPS_PAUSED.flag" ]; then
    if grep -qxE "${port}" "$PROJECT/controle/CHIPS_PAUSED.flag" 2>/dev/null; then
      return 0
    fi
  fi
  if ! curl -fsS --max-time 3 "http://127.0.0.1:${port}/status" >/dev/null 2>&1; then
    cd "$WA"
    nohup node single-extra.js --port "$port" --auth "$auth" >> "$LOG_DIR/channel_bridge_${port}.log" 2>&1 &
    echo "Bridge ${port} reiniciada (${auth})"
  fi
}

start_bridge 4600 auth_single
start_bridge 4601 auth_4601
start_bridge 4603 auth_4603
start_bridge 4605 auth_4605_breno2
start_bridge 4606 auth_4606_lucas_institucional
start_bridge 4607 auth_4607_rafael_institucional

# Reimporta o ledger compartilhado dos dois crons para o Channel.
# Isso mantém o painel completo mesmo quando a mensagem veio do cron SDR
# ou do diagnóstico 5min e não apenas de evento live da bridge.
cd "$PROJECT"
python3 scripts/import_channel_history.py >> "$LOG_DIR/channel_import.log" 2>&1 || echo "Falha ao importar histórico channel"

# Channel V2 é o produto oficial. NÃO ressuscitar a V1 (8790).
# Público autenticado: :8280 (sdrs.zydon.com.br). Local interno: :8791.
if ! curl -fsS --max-time 3 "http://127.0.0.1:8280/health" >/dev/null 2>&1; then
  cd "$PROJECT"
  nohup python3 scripts/channel_panel_v2.py --host 0.0.0.0 --port 8280 >> "$LOG_DIR/channel_panel_v2_public.log" 2>&1 &
  echo "Painel Channel V2 público reiniciado em :8280"
fi

if ! curl -fsS --max-time 3 "http://127.0.0.1:8791/health" >/dev/null 2>&1; then
  cd "$PROJECT"
  nohup python3 scripts/channel_panel_v2.py --host 127.0.0.1 --port 8791 >> "$LOG_DIR/channel_panel_v2.log" 2>&1 &
  echo "Painel Channel V2 local reiniciado em :8791"
fi

if [ -f "$PROJECT/controle/SECURITY_PAUSE_PUBLIC_TUNNELS.flag" ]; then
  echo "Túneis públicos do Channel pausados por segurança; aguardando Google/Cloudflare Access."
elif ! pgrep -f "cloudflared tunnel --url http://127.0.0.1:8790" >/dev/null 2>&1; then
  cd "$PROJECT"
  : > "$LOG_DIR/channel_cloudflared.log"
  nohup cloudflared tunnel --url http://127.0.0.1:8790 --no-autoupdate >> "$LOG_DIR/channel_cloudflared.log" 2>&1 &
  sleep 8
  URL=$(grep -oE 'https://[-a-zA-Z0-9]+\.trycloudflare\.com' "$LOG_DIR/channel_cloudflared.log" | tail -1 || true)
  if [ -n "$URL" ]; then
    echo "Túnel Cloudflare channel reiniciado: $URL"
    echo "$URL" > "$PROJECT/controle/channel_public_base_url.txt"
  else
    echo "Túnel Cloudflare reiniciado, mas URL ainda não apareceu no log"
  fi
fi
