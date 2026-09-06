#!/usr/bin/env python3
"""smoothtest.py - kontrakt plynuleho rezimu ("vylepseno").

Interpolace jde u terenu i objektu od predchoziho tiku k aktualnimu a polohy
se kvantuji na 1/S px smerem dolu jako v klasicke ceste, takze na S = 1:
  - pri alfa -> 1 se plynuly snimek rovna klasickemu snimku aktualniho tiku,
  - pri alfa = 0 klasickemu snimku predchoziho tiku.
Meri se pixel po pixelu bez HUD (radky 16..255). Prah je zarazka; dnes
zmereno 0 a 0 ruznych pixelu v zonach 1, 2 a 6.

    python3 tools/smoothtest.py [zona 1..7] [tik]
"""
import os, sys
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
zone = int(sys.argv[1]) if len(sys.argv) > 1 else 2
tick = int(sys.argv[2]) if len(sys.argv) > 2 else 2400
LIMIT = 200

JS = """(tick) => {
  const g = state.g; g.lives = 100000; const cv = document.querySelector('#game');
  const grab = () => cv.getContext('2d').getImageData(0, 16, 320, 240).data.slice();
  const diff = (a, b) => { let n = 0; for (let i = 0; i < a.length; i += 4)
    if (a[i] !== b[i] || a[i+1] !== b[i+1] || a[i+2] !== b[i+2]) n++; return n; };
  // frame(0) s g.last = 0 ma dt = 0, takze nekrokuje; g.frac = TICK krokuje
  // presne jeden tik. Parovani poloh (bobPrev/bobCur) se zaznamenava jen pri
  // zapnutem smooth, proto se oba tiky krokuji v plynulem rezimu.
  const render = (smooth, frac) => { state.smooth = smooth; g.frac = frac; g.last = 0; frame(0); };
  for (let t = 0; t < tick - 2; t++) step(g);
  render(true, TICK);                                   // tik n, zaznam poloh
  if (cv.width !== 320) return { error: 'S != 1: ' + cv.width };
  render(false, 0); const prevClassic = grab();         // klasicky snimek tiku n
  render(true, TICK);                                   // tik n+1, bobPrev = tik n
  render(true, 0); const smooth0 = grab();              // alfa = 0
  render(true, TICK * 0.999); const smooth1 = grab();   // alfa ~ 1
  render(false, 0); const curClassic = grab();          // klasicky snimek tiku n+1
  return { d0: diff(smooth0, prevClassic), d1: diff(smooth1, curClassic),
           classicMoved: diff(prevClassic, curClassic) };
}"""

with sync_playwright() as pw:
    b = pw.chromium.launch(); page = b.new_page(viewport={"width": 380, "height": 440})
    errs = []; page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto("file://" + os.path.join(ROOT, "game.html"))
    page.set_input_files("#fpick", os.path.join(ROOT, "SWIVFIX.ADF"))
    page.wait_for_selector("#titlewrap", state="visible"); page.wait_for_selector("#levelpick", state="visible")
    page.evaluate("window.requestAnimationFrame = () => 0")
    page.click(f"#levelbtns a:nth-child({zone})"); page.wait_for_selector("#gamewrap", state="visible")
    res = page.evaluate(JS, tick)
    b.close()
if errs or "error" in res:
    sys.exit("CHYBA: " + (res.get("error") or "; ".join(errs)))
ok = res["d0"] <= LIMIT and res["d1"] <= LIMIT
print(f"zona {zone} tik {tick}: alfa=0 vs klasicky predchozi tik {res['d0']} px, alfa~1 vs aktualni "
      f"{res['d1']} px (klasicke snimky se lisi v {res['classicMoved']} px) -> {'OK' if ok else 'FAIL'}")
sys.exit(0 if ok else 1)
