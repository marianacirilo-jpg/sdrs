#!/bin/bash
# ============================================================
# Backup Google Drive BLINDADO (pos--incidente 22/06/2026)
#
# DUAS camadas de protecao contra perda de dados:
#   1. GUARD FAIL-CLOSED: se o source tiver < ARQUIVOS_MIN, ABORTA.
#      (Impediria o desastre: source vazio nunca esvazia o Drive.)
#   2. --backup-dir versionado: arquivos deletados/alterados no Drive
#      sao MOVIDOS para backup-AAAA-MM-DD/ ANTES de sumir.
#      Nada se perde definitivamente.
#
# NUNCA usar rclone sync puro aqui novamente.
# ============================================================
set -uo pipefail

RCLONE="/usr/local/bin/rclone"
CONF="/root/.config/rclone/rclone.conf"
# IMPORTANTE: apontar pro caminho REAL (nao symlink). O `find` do guard
# fail-closed nao segue symlinks; apontar pro real garante contagem correta.
SRC="/root/.hermes/zydon-prospeccao"
DST="gdrive:prospeccao_zydon"
BACKUP_DIR="gdrive:prospeccao_zydon-backups/backup-$(date -u +%Y-%m-%d)"
LOG="$SRC/logs/drive_sync.log"
FLAG="$SRC/logs/BACKUP_FAILED.flag"

# Projeto standalone do Roteiro, fora do diretório SDR/Channel.
# Também precisa backup porque tem persistência própria em controle/*.json/jsonl.
ROTEIRO_SRC="/root/.hermes/roteiro-zydon-arquivo-fora-do-sdrs"
ROTEIRO_DST="$DST/roteiro-standalone"
ROTEIRO_BACKUP_DIR="$BACKUP_DIR/roteiro-standalone"

# Guard fail-closed: quantos arquivos o projeto DEVE ter no minimo.
# Hoje tem ~568. Se cair abaixo de 100, algo apagou o source -> ABORTAR.
ARQUIVOS_MIN=100
ROTEIRO_ARQUIVOS_MIN=5

mkdir -p "$SRC/logs"

# ============================================================
# CAMADA 1: Guard fail-closed
# ============================================================
COUNT=$(find "$SRC" -type f \
  ! -path "*/.venv/*" \
  ! -path "*/__pycache__/*" \
  ! -path "*/logs/*" \
  ! -name "*.pyc" 2>/dev/null | wc -l)

if [ "$COUNT" -lt "$ARQUIVOS_MIN" ]; then
  echo "[$(date -u)] ABORTADO: source tem apenas $COUNT arquivos (minimo $ARQUIVOS_MIN)." > "$FLAG"
  echo "[$(date -u)] ABORTADO por guard fail-closed: $COUNT arquivos no source (min=$ARQUIVOS_MIN). Backup NAO executado para proteger o Drive." >> "$LOG"
  exit 2
fi

ROTEIRO_COUNT=0
if [ -d "$ROTEIRO_SRC" ]; then
  ROTEIRO_COUNT=$(find "$ROTEIRO_SRC" -type f \
    ! -path "*/.venv/*" \
    ! -path "*/__pycache__/*" \
    ! -path "*/logs/*" \
    ! -name "*.pyc" 2>/dev/null | wc -l)
  if [ "$ROTEIRO_COUNT" -lt "$ROTEIRO_ARQUIVOS_MIN" ]; then
    echo "[$(date -u)] ABORTADO: roteiro standalone tem apenas $ROTEIRO_COUNT arquivos (minimo $ROTEIRO_ARQUIVOS_MIN)." > "$FLAG"
    echo "[$(date -u)] ABORTADO por guard fail-closed do Roteiro: $ROTEIRO_COUNT arquivos no source (min=$ROTEIRO_ARQUIVOS_MIN). Backup NAO executado para proteger o Drive." >> "$LOG"
    exit 3
  fi
fi

# ============================================================
# CAMADA 2: sync com --backup-dir versionado
# (deletados/overwrite no Drive -> movidos para backup-AAAA-MM-DD/)
# ============================================================
do_sync() {
  "$RCLONE" --config "$CONF" sync "$SRC" "$DST" \
    --backup-dir "$BACKUP_DIR" \
    --exclude ".venv/**" \
    --exclude "__pycache__/**" \
    --exclude "*.pyc" \
    --exclude "*.tar" \
    --exclude "*secret*" \
    --exclude "controle/dashboard_token.txt" \
    --exclude "roteiro-standalone/**" \
    --exclude "logs/**" \
    --transfers 1 \
    --log-file "$LOG" \
    --log-level INFO 2>&1 || return $?

  if [ -d "$ROTEIRO_SRC" ]; then
    "$RCLONE" --config "$CONF" sync "$ROTEIRO_SRC" "$ROTEIRO_DST" \
      --backup-dir "$ROTEIRO_BACKUP_DIR" \
      --exclude ".venv/**" \
      --exclude "__pycache__/**" \
      --exclude "*.pyc" \
      --exclude "*.tar" \
      --exclude "*secret*" \
      --exclude "logs/**" \
      --transfers 1 \
      --log-file "$LOG" \
      --log-level INFO 2>&1 || return $?
  fi
}

if do_sync; then
  rm -f "$FLAG"
  if [ -d "$ROTEIRO_SRC" ]; then
    echo "[$(date -u)] sync OK ($COUNT arquivos + roteiro $ROTEIRO_COUNT arquivos, backup-dir=$BACKUP_DIR)" >> "$LOG"
  else
    echo "[$(date -u)] sync OK ($COUNT arquivos, backup-dir=$BACKUP_DIR)" >> "$LOG"
  fi
  exit 0
fi

# Falhou — tentar renovar token/recuperar uma vez. Não mascarar erro por
# mensagem antiga no log: se o rclone retornou falha, a execução é falha.
echo "[$(date -u)] sync falhou, tentando renovar token..." >> "$LOG"
echo "y" | timeout 20 "$RCLONE" --config "$CONF" config reconnect gdrive: >> "$LOG" 2>&1 || true

if do_sync; then
  rm -f "$FLAG"
  echo "[$(date -u)] token renovado, sync OK apos retry (backup-dir=$BACKUP_DIR)" >> "$LOG"
  exit 0
fi

# Ainda falhando — sentinela
echo "[$(date -u)] BACKUP FALHOU — token Google Drive invalido/revogado. Rafael precisa re-autorizar." > "$FLAG"
echo "[$(date -u)] BACKUP FALHOU apos retry — sentinela criada" >> "$LOG"
exit 1
