# -*- coding: utf-8 -*-
"""Generate a 600x338 JPEG thumbnail (q90, sRGB) from the first page of a motor HTML."""
import os, sys
from playwright.sync_api import sync_playwright

OUT = os.path.dirname(os.path.abspath(__file__))  # motor/
PROJ = os.path.dirname(OUT)
slug = sys.argv[1] if len(sys.argv) > 1 else "lumaville"
html_path = os.path.join(OUT, f"{slug}.html")
thumb_path = os.path.join(PROJ, "pdfs", f"{slug}_thumb.jpg")

with sync_playwright() as p:
    b = p.chromium.launch()
    # 210mm = 793.7px @96dpi ; render first page at that width
    pg = b.new_page(viewport={"width": 794, "height": 600}, device_scale_factor=1)
    pg.goto("file://" + html_path, wait_until="networkidle")
    # Screenshot just the top portion of the first page (16:9-ish 600x338)
    pg.screenshot(path=thumb_path, clip={"x": 0, "y": 0, "width": 600, "height": 338}, type="jpeg", quality=90)
    b.close()
print("THUMB:", thumb_path, os.path.getsize(thumb_path), "bytes")
