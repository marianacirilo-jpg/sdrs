# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lead_dualcolor import LEAD
import gen

OUT = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.dirname(OUT)  # .../zydon-prospeccao/

# Update HOJE
gen.HOJE = "24 jun 2026"

# Build HTML
html = gen.build_html(LEAD)

# Write HTML
html_path = os.path.join(OUT, "dualcolor.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"HTML written: {html_path}")

# Check for "A confirmar" count
count = html.count("A confirmar")
print(f"'A confirmar' count: {count}")

# Render PDF
from playwright.sync_api import sync_playwright

pdf_path = os.path.join(DEST, "pdfs", "Potencial-Digitalizacao-dualcolor.pdf")
os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    src = "file://" + html_path
    pg.goto(src, wait_until="networkidle")
    pg.pdf(path=pdf_path, width="210mm", height="297mm", print_background=True,
           margin={"top":"0","bottom":"0","left":"0","right":"0"})
    print(f"PDF written: {pdf_path}")
    b.close()

# File size
sz = os.path.getsize(pdf_path)
print(f"PDF size: {sz} bytes ({sz/1024:.0f} KB)")
