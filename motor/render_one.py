#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render ONE lead PDF from a JSON lead-dict file (parallel-safe, no leads.py edit).
Usage: python3 motor/render_one.py <slug> <lead_dict.json>
Reads the dict, builds HTML via gen.build_html, renders PDF via Playwright.
"""
import os, sys, json, datetime

MOTOR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, MOTOR)

import gen  # noqa

if len(sys.argv) < 3:
    print("Usage: render_one.py <slug> <lead_dict.json>")
    sys.exit(1)

slug = sys.argv[1]
dict_path = sys.argv[2]

with open(dict_path) as f:
    lead = json.load(f)

# Atualiza data para hoje
gen.HOJE = datetime.date.today().strftime("%d %b %Y").replace("May", "mai").replace("Jun", "jun").replace("Jul", "jul").replace("Aug","ago").replace("Sep","set").replace("Oct","out").replace("Dec","dez")

html = gen.build_html(lead)
html_path = os.path.join(MOTOR, slug + ".html")
with open(html_path, "w") as f:
    f.write(html)
print("HTML:", html_path)

from playwright.sync_api import sync_playwright

out_dir = os.path.dirname(MOTOR)  # /root/zydon-prospeccao
pdfs_dir = os.path.join(out_dir, "pdfs")
os.makedirs(pdfs_dir, exist_ok=True)
out_pdf = os.path.join(pdfs_dir, "Potencial-Digitalizacao-" + slug + ".pdf")

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto("file://" + html_path, wait_until="networkidle")
    pg.pdf(path=out_pdf, width="210mm", height="297mm", print_background=True,
           margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
    b.close()
print("PDF:", out_pdf)
