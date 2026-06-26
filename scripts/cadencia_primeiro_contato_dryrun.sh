#!/usr/bin/env bash
# Wrapper seguro para prévia da cadência de Primeiro Contato sem resposta.
# Não envia WhatsApp e não cria task: serve para cron/report ou revisão manual.
set -euo pipefail
cd /root/.hermes/zydon-prospeccao
python3 scripts/cadencia_primeiro_contato.py --dry-run --limit "${1:-20}"
