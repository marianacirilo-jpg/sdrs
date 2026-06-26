#!/usr/bin/env bash
# Gera thumbnail da 1ª página de um PDF, OTIMIZADO para pré-visualização do WhatsApp.
# WhatsApp só renderiza a miniatura de documento com thumbnail PEQUENO (~5-15KB).
# Thumbnails grandes (>100KB, ex: 150 DPI cheio) NÃO renderizam.
#
# Uso: gerar_thumb.sh <caminho_do_pdf>
# Saída: <pdf_sem_extensao>_thumb.jpg (mesmo diretório do PDF)
set -euo pipefail

PDF="${1:-}"
if [ -z "$PDF" ] || [ ! -f "$PDF" ]; then
  echo "Uso: $0 <caminho_do_pdf>" >&2
  exit 1
fi

OUT="${PDF%.pdf}_thumb.jpg"
# Passo 1: extrair 1ª página em JPEG (resolução alta p/ qualidade inicial)
pdftoppm -jpeg -r 150 -f 1 -l 1 -singlefile "$PDF" "${OUT%.jpg}"
# Passo 2: redimensionar para 320px de largura + qualidade 70 → ~5-15KB (WhatsApp renderiza)
convert "$OUT" -resize 320x320 -quality 70 "$OUT"
echo "$OUT"
