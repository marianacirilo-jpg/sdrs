#!/bin/bash
# ensure_bridges.sh — Garante que as bridges SDR ativas (4601, 4603, 4605) estão rodando.
# Deve ser chamado antes de cada ciclo de disparo.

BRIDGE_DIR="/root/.hermes/whatsapp-extra"
cd "$BRIDGE_DIR" || exit 1

declare -A PORTS=(
  [4601]="auth_4601"
  [4603]="auth_4603"
  [4605]="auth_4605_breno2"
)

ALL_OK=true

for port in 4601 4603 4605; do
  authdir="${PORTS[$port]}"
  
  # Verificar se a bridge está respondendo
  status=$(curl -s --max-time 5 "http://localhost:$port/status" 2>/dev/null)
  
  if echo "$status" | grep -q '"connected":true'; then
    echo "[OK] Bridge $port conectada"
  else
    # /status pode ficar stale no Baileys; /me válido é a fonte de verdade para sessão pareada.
    me=$(curl -s --max-time 5 "http://localhost:$port/me" 2>/dev/null)
    if echo "$me" | grep -q '"id"' && echo "$me" | grep -q '"phone"'; then
      echo "[OK] Bridge $port com /me válido (status stale; não reiniciar)"
      continue
    fi
    echo "[DOWN] Bridge $port não responde ou desconectada. Reiniciando..."
    # Matar processo antigo se existir
    pkill -f "single-extra.js --port $port" 2>/dev/null
    sleep 1
    # Reiniciar
    nohup node single-extra.js --port "$port" --auth "$authdir" > "/tmp/bridge_${port}.log" 2>&1 &
    echo "[RESTART] Bridge $port reiniciada (PID $!)"
    sleep 5
    # Verificar novamente
    status=$(curl -s --max-time 5 "http://localhost:$port/status" 2>/dev/null)
    if echo "$status" | grep -q '"connected":true'; then
      echo "[OK] Bridge $port reconectada"
    else
      echo "[FAIL] Bridge $port ainda não conectou — pode precisar de QR code"
      ALL_OK=false
    fi
  fi
done

if [ "$ALL_OK" = true ]; then
  echo "Todas as bridges OK"
  exit 0
else
  echo "ALERTA: Uma ou mais bridges precisam de atenção (QR code)"
  exit 1
fi
