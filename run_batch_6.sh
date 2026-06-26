#!/usr/bin/env bash
# Processa os 6 leads pendentes SEQUENCIALMENTE via run_one.sh (evita 529).
set -u
cd /root/zydon-prospeccao
SLUGS="tetraplus pontes-multi madeira-abc brightgear ib-silva zooz"
echo "=== INICIO $(date) ==="
for s in $SLUGS; do
  echo "########## PROCESSANDO $s ##########"
  bash run_one.sh "$s"
  echo "--- $s concluido, pausa 10s ---"
  sleep 10
done
echo "=== FIM $(date) ==="
echo "=== PDFs gerados ==="
ls -la pdfs/Potencial-Digitalizacao-{tetraplus,pontes-multi,madeira-abc,brightgear,ib-silva,zooz}.pdf 2>&1
echo "=== MQL decision de cada ==="
for s in $SLUGS; do
  head -3 "pesquisas/${s}_claude.txt" 2>/dev/null | grep -i "mql" || echo "$s: (ver arquivo)"
done