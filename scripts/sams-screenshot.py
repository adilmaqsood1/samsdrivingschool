#!/usr/bin/env python3
"""Take screenshots of the dev server using Playwright."""
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = os.environ.get("SAMS_DEV_URL", "http://127.0.0.1:8000/")
OUT = Path("/tmp/sams-shots")
OUT.mkdir(exist_ok=True)

shots = [
    ("01-hero.png",   1440, 900,  None,    None,   "hero/top"),
    ("02-courses.png",1440, 2400, 1500,    1400,   "courses"),
    ("03-contact.png",1440, 4200, 3300,    1900,   "contact form"),
    ("00-full.png",   1440, 6300, None,    None,   "full page"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--no-sandbox"])
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              device_scale_factor=1)
    page = ctx.new_page()
    page.goto(URL, wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2000)
    # wait for fonts
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(500)
    # hero shot (no scroll)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.screenshot(path=str(OUT/"01-hero.png"), full_page=False)
    print("01-hero.png", (OUT/"01-hero.png").stat().st_size)
    # full page
    page.screenshot(path=str(OUT/"00-full.png"), full_page=True)
    print("00-full.png", (OUT/"00-full.png").stat().st_size)
    for fn, vw, vh, sx, sy, label in shots[1:]:
        if fn == "00-full.png":
            continue
        page.set_viewport_size({"width": vw, "height": vh})
        if sx is not None and sy is not None:
            page.evaluate(f"window.scrollTo({sx}, {sy})")
            page.wait_for_timeout(200)
        page.screenshot(path=str(OUT/fn), full_page=False)
        print(fn, (OUT/fn).stat().st_size, label)
    browser.close()
print("done")
