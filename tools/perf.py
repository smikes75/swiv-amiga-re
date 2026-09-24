#!/usr/bin/env python3
"""Cena snimku vylepseneho renderu - SPRAVNYM protokolem.

Dve pasti, kvuli kterym byla starsi cisla v docs spatne (CHIPSET, "Vykon
vylepseneho rezimu"):

1. `g.frac` je v SEKUNDACH a TICK = 0,02. `g.frac = 0.37` znamena 18 kroku
   simulace na snimek - a snimek bez interpolace, protoze `bobPrev` se plni
   jen pri jednom kroku. Podpixelovy snimek je `alfa * TICK` a musi mu
   predchazet snimek s `g.frac = TICK` (jeden krok).
2. Chromium kreslici prikazy jen zaznamenava a rastruje az pri flushi. Bez
   vynuceneho cteni (`getImageData(0,0,1,1)`) se meri jen JS: tataz scena
   dava 1,44 ms bez flushe a 243,77 ms s nim.

Kazda varianta bezi v NOVE zalozce (cache se neprenaseji). Mereni je
neplatne, kdyz se behem nej posune `g.tick` nebo chybi `bobPrev` - skript to
vypise.

    python3 tools/perf.py                          # vychozi sada variant
    python3 tools/perf.py --html jina/game.html    # jina verze (A/B)
    python3 tools/perf.py --var 'DOF vyp={"depthOfField": false}'
    python3 tools/perf.py --zoom 6 --uroven 0 --alfa 0
    python3 tools/perf.py --hra     # za behu: krok + podpixelovy snimek

Cisla jsou z headless Chromia, tedy ze softwaroveho rasteru. Pro hrace na
GPU plati POMERY, ne absolutni ms.
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADF = os.path.join(ROOT, "SWIVFIX.ADF")

JS = """(arg) => {
  const { lv, prep, alfa, warm, n, zoom, hra: zaBehu } = arg;
  startGame(lv);
  state.zoom = zoom; state.smooth = true; state.blendBg = true;
  state.subpixelSprites = true; state.depthOfField = true;
  state.heliTilt = false; state.vehicleTracks = false; state.waterWaves = true;
  state.softShadows = true; state.spriteScale = "bez";
  Object.assign(state, prep);
  const g = state.g;
  for (let i = 0; i < warm; i++) { step(g); g.lives = 99999; g.player.inv = 0; }
  g.frac = 0; g.last = 0; frame(0);              // vznikne bobCur
  g.frac = TICK; g.last = 0; frame(0);           // jeden krok -> bobPrev
  g.player.inv = 0;
  const tick0 = g.tick;
  const hra = document.querySelector('#game').getContext('2d');
  const jeden = () => { g.frac = alfa * TICK; g.last = 0; frame(0);
    hra.getImageData(0, 0, 1, 1); };             // flush = rasterizace
  // Za behu: kazda iterace = jeden krok simulace (snimek s TICK) a jeden
  // podpixelovy snimek, tedy dva vykreslene snimky na tik jako pri 100 Hz.
  // Tady se pohyblive objekty opravdu hybou a cache mijeji.
  const dvojice = () => { g.frac = TICK; g.last = 0; frame(0);
    hra.getImageData(0, 0, 1, 1);
    g.lives = 99999; g.player.inv = 0; jeden(); };
  let ms;
  if (zaBehu) {
    for (let i = 0; i < 10; i++) dvojice();
    const t0 = performance.now();
    for (let i = 0; i < n; i++) dvojice();
    ms = (performance.now() - t0) / (2 * n);
  } else {
    for (let i = 0; i < n; i++) jeden();         // zahrati
    const t0 = performance.now();
    for (let i = 0; i < n; i++) jeden();
    ms = (performance.now() - t0) / n;
  }
  const top = Math.max(0, Math.min(g.mapH - 256, Math.floor(g.scroll)));
  let stinu = 0, letcu = 0, spritu = 0;
  for (const r of composeTownBobs(g, top).ordered) {
    spritu++;
    if (r.kind === "shadow") stinu++;
    if (r.kind === "main" && (r.z | 0)) letcu++;
  }
  return { ms: +ms.toFixed(2), prev: !!g.bobPrev,
           tikyBeze: zaBehu ? 0 : g.tick - tick0,
           stinu, letcu, spritu,
           S: document.querySelector('#game').width / 320 };
}"""

VYCHOZI = [
    ("vse zap", {}),
    ("mekke stiny vyp", {"softShadows": False}),
    ("hloubka ostrosti vyp", {"depthOfField": False}),
    ("hrany Scale2x", {"spriteScale": "scale2x"}),
    ("hrany vyhlazeno", {"spriteScale": "vyhlazeno"}),
]


def zmer(html, varianty, lv=3, warm=1000, n=20, zoom=5, alfa=0.37, hra=False):
    out = []
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        for jm, prep in varianty:
            p = br.new_page(viewport={"width": 2400, "height": 1800},
                            device_scale_factor=1)
            p.set_default_timeout(600_000)
            chyby = []
            p.on("pageerror", lambda e: chyby.append(str(e)))
            p.goto("file://" + os.path.abspath(html))
            p.set_input_files("#fpick", ADF)
            p.wait_for_selector("#titlewrap", state="visible")
            p.evaluate("window.requestAnimationFrame = () => 0")
            r = p.evaluate(JS, {"lv": lv, "prep": prep, "alfa": alfa,
                                "warm": warm, "n": n, "zoom": zoom,
                                "hra": hra})
            r["chyby"] = chyby
            out.append((jm, r))
            p.close()
        br.close()
    return out


def main():
    args = sys.argv[1:]

    def vezmi(jm, vychozi, typ=str):
        if jm in args:
            i = args.index(jm); v = args[i + 1]; del args[i:i + 2]
            return typ(v)
        return vychozi

    html = vezmi("--html", os.path.join(ROOT, "game.html"))
    zoom = vezmi("--zoom", 5, int)
    lv = vezmi("--uroven", 3, int)
    alfa = vezmi("--alfa", 0.37, float)
    hra = "--hra" in args
    if hra:
        args.remove("--hra")
    varianty = []
    while "--var" in args:
        i = args.index("--var"); spec = args[i + 1]; del args[i:i + 2]
        jm, _, js = spec.partition("=")
        varianty.append((jm, json.loads(js or "{}")))
    varianty = varianty or VYCHOZI

    print("%s  uroven %d, zvetseni %d, alfa %.2f, %s"
          % (os.path.relpath(html, ROOT), lv, zoom, alfa,
             "ZA BEHU (krok + podpixelovy snimek, 40 snimku)" if hra
             else "stojici scena, prumer z 20 snimku"))
    for jm, r in zmer(html, varianty, lv=lv, zoom=zoom, alfa=alfa, hra=hra):
        chyba = ""
        if r["tikyBeze"] or not r["prev"]:
            chyba = "  NEPLATNE (tik +%d, bobPrev %s)" % (r["tikyBeze"], r["prev"])
        if r["chyby"]:
            chyba += "  CHYBY %s" % r["chyby"]
        print("  %-26s %8.2f ms   (S=%d, spritu %d, stinu %d, letcu %d)%s"
              % (jm, r["ms"], r["S"], r["spritu"], r["stinu"], r["letcu"], chyba))


if __name__ == "__main__":
    main()
