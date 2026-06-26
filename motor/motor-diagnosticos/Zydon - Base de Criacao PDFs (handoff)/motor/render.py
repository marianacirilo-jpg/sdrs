# -*- coding: utf-8 -*-
import os, sys
from playwright.sync_api import sync_playwright
from leads import LEADS

OUT = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.dirname(OUT)  # .../outputs

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    for l in LEADS:
        src = "file://" + os.path.join(OUT, f"{l['slug']}.html")
        pg.goto(src, wait_until="networkidle")
        out = os.path.join(DEST, f"Potencial-Digitalizacao-{l['slug']}.pdf")
        pg.pdf(path=out, width="210mm", height="297mm", print_background=True,
               margin={"top":"0","bottom":"0","left":"0","right":"0"})
        print("PDF:", out)
    b.close()
