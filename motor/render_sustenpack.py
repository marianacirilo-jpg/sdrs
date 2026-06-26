# -*- coding: utf-8 -*-
import os
from playwright.sync_api import sync_playwright

OUT = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.dirname(OUT)  # /root/zydon-prospeccao

slug = "sustenpack"
src = "file://" + os.path.join(OUT, f"{slug}.html")
out = os.path.join(DEST, "pdfs", f"Potencial-Digitalizacao-{slug}.pdf")
os.makedirs(os.path.join(DEST, "pdfs"), exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto(src, wait_until="networkidle")
    pg.pdf(path=out, width="210mm", height="297mm", print_background=True,
           margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
    print("PDF:", out)
    b.close()
