#!/usr/bin/env python3
"""End-to-end test hry v realnem Chromiu (playwright).

Projde cely tok: vlozeni ADF -> intro -> vyber urovne -> hra bezi,
a hlasi kazdou JS chybu. Presne tenhle test odhalil, ze headless
stub s hoistingem prezije chybejici funkci, kterou browser ne.

    python3 tools/uitest.py
"""

from playwright.sync_api import sync_playwright
import sys, time
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={'width':1200,'height':900})
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append('console.%s: %s' % (m.type, m.text)) if m.type=='error' else None)
    import os; pg.goto('file://'+os.path.abspath('game.html'))
    # vlozit ADF pres file input
    pg.set_input_files('#fpick', os.path.abspath('SWIVFIX.ADF'))
    pg.wait_for_timeout(1500)
    print("po vlozeni: titlewrap viditelny:", pg.is_visible('#titlewrap'))
    # press fire
    pg.keyboard.press(' ')
    pg.wait_for_timeout(300)
    print("levelpick viditelny:", pg.is_visible('#levelpick'))
    # klik na TOWN
    t0=time.time()
    pg.click('#levelbtns a:first-child')
    pg.wait_for_timeout(6000)
    print("po kliknuti (%.1fs): gamewrap=%s" % (time.time()-t0, pg.is_visible('#gamewrap')))
    pg.screenshot(path='build/uitest.png')
    print("chyby:", errs[:6] if errs else "zadne")
    b.close()
