#!/usr/bin/env bash
# Safe staging + promote workflow for Zydon Channel V2.
# Default is NO public change: it creates a release copy, runs tests, starts a
# candidate on a private port, and validates it. Promotion requires explicit
# `promote <release_dir>` or `deploy`.
set -euo pipefail

ROOT=${CHANNEL_ROOT:-/root/.hermes/zydon-prospeccao}
RELEASES_DIR=${CHANNEL_RELEASES_DIR:-$ROOT/controle/releases/channel-v2}
RUNTIME_DIR=${CHANNEL_RUNTIME_DIR:-$ROOT/controle/runtime/channel}
STAGING_PORT=${CHANNEL_STAGING_PORT:-8891}
PROD_PORT=${CHANNEL_PROD_PORT:-8280}
STABLE_PORT=${CHANNEL_STABLE_PORT:-8791}
AUTH_EMAIL=${CHANNEL_AUTH_EMAIL:-rafael@zydon.com.br}
PUBLIC_URL=${CHANNEL_PUBLIC_URL:-https://sdrs.zydon.com.br}
LOCK_FILE="$RUNTIME_DIR/deploy.lock"

mkdir -p "$RELEASES_DIR" "$RUNTIME_DIR"

log(){ printf '[%s] %s\n' "$(date -Is)" "$*" >&2; }
fail(){ log "ERRO: $*"; exit 1; }

with_lock(){
  exec 9>"$LOCK_FILE"
  flock -n 9 || fail "deploy já em execução ($LOCK_FILE)"
}

extract_js_check(){
  local dir=$1 out=${2:-/tmp/channel_v2_frontend_safe_deploy.js}
  (cd "$dir" && python3 - <<PY
from pathlib import Path
s=Path('scripts/channel_panel_v2.py').read_text()
js=s[s.index('<script>')+8:s.index('</script></body></html>')]
Path('$out').write_text(js)
print('frontend_js_bytes', len(js))
PY
  node --check "$out")
}

copy_release(){
  local ts release
  ts=$(date -u +%Y%m%dT%H%M%SZ)
  release="$RELEASES_DIR/$ts"
  mkdir -p "$release"
  log "criando release copy: $release"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
      --exclude 'controle/releases/' \
      --exclude 'controle/runtime/' \
      --exclude 'docs/channel-watchdog-incidents/' \
      --exclude '__pycache__/' \
      --exclude '*.pyc' \
      "$ROOT/" "$release/"
  else
    (cd "$ROOT" && tar \
      --exclude='./controle/releases' \
      --exclude='./controle/runtime' \
      --exclude='./docs/channel-watchdog-incidents' \
      --exclude='*/__pycache__' \
      --exclude='*.pyc' \
      -cf - .) | (cd "$release" && tar -xf -)
  fi
  printf '%s\n' "$release"
}

run_static_gate(){
  local dir=$1
  log "static gate em $dir"
  (cd "$dir" && python3 -m py_compile scripts/channel_panel_v2.py tests/channel_v2_smoke_gate.py tests/test_channel_v2_core.py)
  extract_js_check "$dir" "/tmp/channel_v2_frontend_safe_deploy.js"
  # Channel deploy gate: keep it scoped to Channel files. Full project discovery
  # currently includes prospection/Roteiro suites with unrelated failures and would
  # make the production-safe Channel deploy path unusable.
  (cd "$dir" && python3 -m unittest \
    tests.test_channel_v2_core \
    tests.test_channel_v2_watchdog_hysteresis \
    -v)
}

pid_for_port(){
  local port=$1
  ps -eo pid,cmd | awk -v port="--port $port" '/scripts\/channel_panel_v2.py/ && index($0, port) && !/awk/ {print $1}' | head -1
}

kill_port_process(){
  local port=$1 pid
  pid=$(pid_for_port "$port" || true)
  if [ -n "${pid:-}" ]; then
    log "parando Channel port $port pid=$pid"
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
      if ! kill -0 "$pid" 2>/dev/null; then return 0; fi
      sleep 0.25
    done
    log "pid=$pid não saiu; SIGKILL"
    kill -9 "$pid" 2>/dev/null || true
  fi
}

start_server(){
  local dir=$1 port=$2 pidfile=$3
  local host=${4:-127.0.0.1}
  kill_port_process "$port"
  log "subindo Channel dir=$dir host=$host port=$port"
  (
    cd "$dir"
    # Não herdar o fd do flock para o servidor longo; se herdar, o deploy.lock
    # fica preso enquanto o Channel roda e bloqueia próximos stages/promotes.
    exec 9>&- || true
    exec python3 scripts/channel_panel_v2.py --host "$host" --port "$port"
  ) >"$RUNTIME_DIR/channel-$port.log" 2>&1 &
  local pid=$!
  printf '%s\n' "$pid" > "$pidfile"
  for _ in $(seq 1 80); do
    if curl -fsS -m 2 "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
      log "port $port saudável pid=$pid"
      return 0
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
      tail -120 "$RUNTIME_DIR/channel-$port.log" >&2 || true
      fail "processo port $port morreu durante startup"
    fi
    sleep 0.25
  done
  tail -120 "$RUNTIME_DIR/channel-$port.log" >&2 || true
  fail "port $port não ficou saudável"
}

validate_api(){
  local base=$1 label=$2 timeout=${3:-80}
  log "validando $label $base"
  local tmp="$RUNTIME_DIR/validate-${label//[^A-Za-z0-9_.-]/_}.json"
  curl -fsS -m "$timeout" -H "Cf-Access-Authenticated-User-Email: $AUTH_EMAIL" \
    "$base/api/conversations" -o "$tmp"
  python3 - <<PY
import json, pathlib, sys
p=pathlib.Path('$tmp')
j=json.loads(p.read_text())
convs=j.get('conversations') or []
print('validated_conversations', len(convs))
if len(convs) < 250:
    sys.exit('conversation count too low')
PY
}

validate_candidate(){
  local dir=$1
  run_static_gate "$dir"
  start_server "$dir" "$STAGING_PORT" "$RUNTIME_DIR/staging.pid" "127.0.0.1"
  validate_api "http://127.0.0.1:$STAGING_PORT" "staging-$STAGING_PORT" 120
  # Check a couple of real message timelines that previously regressed.
  python3 - <<PY
import json, urllib.parse, urllib.request
base='http://127.0.0.1:$STAGING_PORT'
headers={'Cf-Access-Authenticated-User-Email':'$AUTH_EMAIL'}
known=['4601::5527997622516@s.whatsapp.net','4607::5585988903132@s.whatsapp.net']
for conv in known:
    url=base+'/api/messages?conv='+urllib.parse.quote(conv, safe='')
    req=urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        data=json.loads(r.read().decode())
    msgs=data.get('messages') or []
    print('validated_messages', conv, len(msgs))
    if not msgs:
        raise SystemExit('empty messages for '+conv)
PY
  log "candidate OK: $dir em port $STAGING_PORT"
}

promote_release(){
  local dir=$1
  [ -d "$dir" ] || fail "release dir não existe: $dir"
  validate_candidate "$dir"

  # Keep the stable/internal port alive while swapping only the public port.
  if ! curl -fsS -m 3 "http://127.0.0.1:$STABLE_PORT/health" >/dev/null 2>&1; then
    log "AVISO: stable port $STABLE_PORT não saudável antes da promoção; promoção ainda depende do candidate"
  fi

  local previous_dir="$ROOT"
  log "PROMOÇÃO: trocando somente port público $PROD_PORT após candidate estável"
  kill_port_process "$PROD_PORT"
  start_server "$dir" "$PROD_PORT" "$RUNTIME_DIR/prod-$PROD_PORT.pid" "0.0.0.0"
  if ! validate_api "$PUBLIC_URL" "public" 30; then
    log "promoção falhou; rollback para $previous_dir no port $PROD_PORT"
    kill_port_process "$PROD_PORT"
    start_server "$previous_dir" "$PROD_PORT" "$RUNTIME_DIR/prod-$PROD_PORT.pid" "0.0.0.0"
    validate_api "$PUBLIC_URL" "public-rollback" 60 || true
    fail "promoção abortada e rollback executado"
  fi
  ln -sfn "$dir" "$RELEASES_DIR/current"
  log "PROMOÇÃO OK: $dir ativo no port $PROD_PORT; staging $STAGING_PORT mantido para inspeção até próximo deploy"
}

case "${1:-stage}" in
  stage)
    with_lock
    rel=$(copy_release)
    validate_candidate "$rel"
    log "STAGE OK, sem mexer no público. Para promover: $0 promote '$rel'"
    ;;
  promote)
    with_lock
    [ $# -ge 2 ] || fail "uso: $0 promote /path/to/release"
    promote_release "$2"
    ;;
  deploy)
    with_lock
    rel=$(copy_release)
    promote_release "$rel"
    ;;
  *)
    cat >&2 <<EOF
Uso: $0 [stage|promote <release_dir>|deploy]
  stage   = cria release + testa em port privado $STAGING_PORT; NÃO mexe no público
  promote = revalida release no staging e só então troca o port público $PROD_PORT
  deploy  = stage + promote em um comando
EOF
    exit 2
    ;;
esac
