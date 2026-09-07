#!/usr/bin/env python3
"""smoothtest.py - kontrakt plynuleho rezimu ("vylepseno").

Interpoluje se mezi dvema klasickymi snimky (scroll i rohy spritu cela cisla,
mezipoloha na nejblizsi 1/S px), vzhled spritu je vzdy z aktualniho tiku
(animacni snimek se interpolovat neda). Na S = 1 proto plati:
  - pri alfa -> 1 se plynuly snimek rovna klasickemu snimku aktualniho tiku
    presne (0 px),
  - pri alfa = 0 se od klasickeho snimku predchoziho tiku lisi jen uvnitr
    obdelniku spritu, kterym se mezi tiky zmenil snimek animace (zmereno
    v TOWN: 1388 px, vsechny v letcich YELLOW); mimo ne nejvyse OUT_LIMIT
    px (SCIFI tik 9000: 95 px na hranach prekryvu letících kamenu se
    stinem a BOSu orezaneho hornim okrajem - vzhled aktualniho tiku na
    hranach, ne poloha).
Meri se pixel po pixelu bez HUD (radky 16..255).

    python3 tools/smoothtest.py [zona 1..7] [tik]
"""
import os, sys
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
zone = int(sys.argv[1]) if len(sys.argv) > 1 else 2
tick = int(sys.argv[2]) if len(sys.argv) > 2 else 2400
OUT_LIMIT = 150                                 # zarazka, zmereno 95 (SCIFI)

JS = """(tick) => {
  const g = state.g; g.lives = 100000; const cv = document.querySelector('#game');
  const grab = () => cv.getContext('2d').getImageData(0, 16, 320, 240).data.slice();
  const diff = (a, b, mask) => { let n = 0, out = 0; for (let i = 0; i < a.length; i += 4)
    if (a[i] !== b[i] || a[i+1] !== b[i+1] || a[i+2] !== b[i+2]) { n++; if (mask && !mask[i >> 2]) out++; } return [n, out]; };
  // frame(0) s g.last = 0 ma dt = 0, takze nekrokuje; g.frac = TICK krokuje
  // presne jeden tik. Parovani poloh se zaznamenava jen pri zapnutem smooth.
  const render = (smooth, frac) => { state.smooth = smooth; g.frac = frac; g.last = 0; frame(0); };
  const snap = () => { const top = Math.max(0, Math.min(g.mapH - 256, Math.floor(g.scroll)));
    return composeTownBobs(g, top).ordered.filter(r => r.spr).map(r => ({ key: smoothBobKey(r),
      ax: r.x, ay: r.y, spr: r.spr, op: r.op })); };
  const box = (mask, ax, ay, spr) => { const bx = Math.floor(ax + spr.ox), by = Math.floor(ay + spr.oy) - 16;
    for (let y = Math.max(0, by); y < Math.min(240, by + spr.h); y++)
      for (let x = Math.max(0, bx); x < Math.min(320, bx + spr.w); x++) mask[y * 320 + x] = 1; };
  // Maska: kde se smi lisit vzhled - sprity se zmenenym snimkem animace nebo
  // op, nove a zanikle zaznamy. Poloha uvnitr masky se nekontroluje.
  const maskOf = (recPrev, recCur) => { const mask = new Uint8Array(320 * 240);
    const prevBy = new Map(recPrev.map(r => [r.key, r])), curKeys = new Set(recCur.map(r => r.key));
    let changed = 0;
    for (const r of recCur) { const p = prevBy.get(r.key);
      if (p && p.spr === r.spr && p.op === r.op) continue;
      changed++;
      if (p) { box(mask, p.ax, p.ay, p.spr); box(mask, p.ax, p.ay, r.spr); } else box(mask, r.ax, r.ay, r.spr); }
    for (const p of recPrev) if (!curKeys.has(p.key)) { changed++; box(mask, p.ax, p.ay, p.spr); }
    return { mask, changed }; };
  // Scroll bezi 0,25 radku za tik a plynuly rezim ho interpoluje ZLOMKOVE,
  // takze plynuly a klasicky snimek splynou jen v tiku, kde je scroll cele
  // cislo (kazdy ctvrty). Pro kazdy konec intervalu se proto zarovnava zvlast,
  // a to krokovanim PRES render() - jinak by se neaktualizovalo parovani
  // poloh (g.bobPrev) a interpolace by se vypnula.
  const isInt = () => Math.abs(g.scroll - Math.round(g.scroll)) < 1e-9;
  for (let t = 0; t < tick - 2; t++) step(g);
  if (cv.width !== 320) return { error: 'S != 1: ' + cv.width };

  // A) alfa = 0 vs klasicky snimek PREDCHOZIHO tiku - ten musi mit cely scroll
  for (let k = 0; k < 8 && !isInt(); k++) render(true, TICK);
  const recA0 = snap();
  render(false, 0); const prevClassic = grab();
  render(true, TICK); const recA1 = snap();
  render(true, 0); const smooth0 = grab();
  const mA = maskOf(recA0, recA1);
  const [d0, d0out] = diff(smooth0, prevClassic, mA.mask);

  // B) alfa -> 1 vs klasicky snimek AKTUALNIHO tiku - ten musi mit cely scroll
  let recB0 = snap(), recB1 = recB0;
  for (let k = 0; k < 8; k++) { recB0 = snap(); render(true, TICK); recB1 = snap(); if (isInt()) break; }
  render(true, TICK * 0.999); const smooth1 = grab();   // frac < TICK: nekrokuje
  render(false, 0); const curClassic = grab();
  const mB = maskOf(recB0, recB1);
  const [d1, d1out] = diff(smooth1, curClassic, mB.mask);

  const [moved] = diff(prevClassic, curClassic, null);
  return { d0, d0out, d1, d1out, classicMoved: moved, changed: mA.changed + mB.changed };
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
ok = res["d0out"] <= OUT_LIMIT and res["d1out"] <= OUT_LIMIT
print(f"zona {zone} tik {tick}: alfa=0 vs predchozi {res['d0']} px (mimo masku {res['d0out']}), "
      f"alfa~1 vs aktualni {res['d1']} px (mimo masku {res['d1out']}); "
      f"maska {res['changed']} spritu se zmenenou animaci -> {'OK' if ok else 'FAIL'}")
sys.exit(0 if ok else 1)
