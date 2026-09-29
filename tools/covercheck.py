#!/usr/bin/env python3
"""Maska popredi: rovina originalu proti `g.coverMask` prepisu.

Original kresli objekty s `+397` bit 0 a vsechny stiny jen tam, kde je
volna samostatna rovina obrazovky `[fp@(256)]+4` (`0x3fe2`: maska spritu AND
rovina do scratch `fp@(252)`, ta je pak maskou cookie blitu). Rovinu
nuluji snimky dlazdic s atributem bit 1 (bajt `flags` casti LIN, 0x02) pri
kresleni do pruhu (`0x3e38` -> `0x4068`, minterm NOT A AND C). Prepis
sklada tutez masku v `renderMap` (`coverMask`).

Skript pusti original v harnessu vAmiga (tools/survey/vacmp.py), dojede na
zadane mapove pozice stejne jako tools/survey/zoneshot.py (kazdy snimek
smaze bit 3 zamku instalace) a na kazde precte rovinu popredi i ctyri
bitplany terenu. Rovina je kruhova: radek bufferu = (kamera + sy) mod 320,
44 bajtu na radek. Zarovnani s mapou prepisu (radek = pozice - 32826) se
overi shodou barevnych indexu terenu.

Horni pruh obrazovky (sy < 32, jeden pruh terenu 0x3422) se hlasi
zvlast: tam se prave stavi dalsi pruh a rovina muze byt jeste
nedokreslena (ICE: 444 bodu).

    python3 tools/covercheck.py                  # DESERT, GRASS, RIVER, ICE
    python3 tools/covercheck.py 0 52000          # 0 = start TOWN, pak DESERT

Vysledek 2026-09-29: TOWN (start + 3 dalsi okamziky), DESERT 52000, GRASS
48788, RIVER 45488, ICE 42735 - 0 odchylek mimo horni pruh (ICE 444 bodu
v nem). SCIFI a FINAL harness nedojede: scroll v ICE drzi dalsi zamek.
Pozor, jizda neni vzdy stejna - po snimku startu TOWN se RIVER zasekl na
46159 (skript to hlasi a porovna, kde stoji).
"""
import base64
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "survey"))
import vacmp                                        # noqa: E402
import zoneshot                                     # noqa: E402
from playwright.sync_api import sync_playwright     # noqa: E402

K = 32826               # radek retezu prepisu = mapova pozice - K
EDGE = 32               # horni pruh: teren se stavi po pruzich 32 radku (0x3422)

DUMP = """(cfg) => {
  const H = VA.M.HEAPU8, p = VA.fn.chipPtr();
  const L = a => (H[p+a]<<24|H[p+a+1]<<16|H[p+a+2]<<8|H[p+a+3])>>>0;
  const U = a => (H[p+a]<<8)|H[p+a+1];
  if (cfg.start) {                  // start TOWN: az po uvolneni zamku scrollu
    let guard = 0;
    while (H[p + cfg.a6 + 166] !== 0 && guard++ < 3000) VA.run(4, null);
    VA.run(300, null);
  }
  VA.run(2, null);
  const st = L(cfg.a6 + 256);
  const b64 = (a, n) => { let s = '';
    for (let i = 0; i < n; i++) s += String.fromCharCode(H[p + a + i]);
    return btoa(s); };
  return { cam: U(st + 8), cover: b64(L(st + 4), 14080),
           planes: b64(L(st), 56320) };
}"""

COMPARE = """([samples, K, EDGE]) => {
  startGame(0);
  const g = state.g, W = g.mapW || 320, mi = g.mapIndex, cm = g.coverMask;
  return samples.map(s => {
    const R0 = s.cam - K;
    let teren = 0, n = 0;
    const r = { cam: s.cam, obojeZakryto: 0, jenOriginal: 0, jenPrepis: 0,
                okrajJenOriginal: 0, okrajJenPrepis: 0 };
    for (let sy = 0; sy < 256; sy++) for (let x = 0; x < 320; x++) {
      const o = s.cov[sy][x] === 0, q = cm[(R0 + sy) * W + x] === 1;
      n++; if (s.idx[sy][x] === mi[(R0 + sy) * W + x]) teren++;
      if (o && q) r.obojeZakryto++;
      else if (o !== q) {
        const k = (sy < EDGE ? 'okraj' : '') + (o ? 'JenOriginal' : 'JenPrepis');
        r[k.charAt(0).toLowerCase() + k.slice(1)]++;
      }
    }
    r.shodaTerenu = +(100 * teren / n).toFixed(1);
    return r;
  });
}"""


def decode(d):
    cov = base64.b64decode(d["cover"]); pl = base64.b64decode(d["planes"])
    idx, covs = [], []
    for sy in range(256):
        r = (d["cam"] + sy) % 320
        idx.append([sum(((pl[p * 14080 + r * 44 + x // 8] >> (7 - (x & 7))) & 1) << p
                        for p in range(4)) for x in range(320)])
        covs.append([(cov[r * 44 + x // 8] >> (7 - (x & 7))) & 1 for x in range(320)])
    return {"cam": d["cam"], "idx": idx, "cov": covs}


def original(targets):
    srv, port = vacmp.serve(os.path.join(ROOT, "web"))
    out = []
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(); page = br.new_page()
            page.set_default_timeout(3_600_000)
            page.goto(f"http://127.0.0.1:{port}/vacmp.html")
            page.wait_for_function("window.VA && window.VA.ready", timeout=60000)
            page.evaluate("([r, a]) => VA.boot(r, a)", [
                base64.b64encode(open(vacmp.ROM, "rb").read()).decode(),
                base64.b64encode(open(vacmp.ADF, "rb").read()).decode()])
            page.evaluate(vacmp.PLAY_PROLOGUE)
            for t in targets:
                if t:
                    r = page.evaluate(zoneshot.DRIVE_JS,
                                      {"target": t, "limit": 120000})
                    stuck = "  ZASEKNUTO (dalsi zamek scrollu)" \
                        if r["pos"] > t else ""
                    print(f"  original: pozice {r['pos']} (cil {t}){stuck}",
                          flush=True)
                out.append(page.evaluate(DUMP, {"a6": vacmp.A6_BASE,
                                                "start": not t}))
            br.close()
    finally:
        srv.shutdown()
    return out


def main():
    targets = [int(a) for a in sys.argv[1:]] or [52000, 48788, 45488, 42735]
    samples = [decode(d) for d in original(targets)]
    with sync_playwright() as pw:
        b = pw.chromium.launch(); p = b.new_page()
        p.goto("file://" + os.path.join(ROOT, "game.html"))
        p.set_input_files("#fpick", os.path.join(ROOT, "SWIVFIX.ADF"))
        p.wait_for_selector("#titlewrap", state="visible")
        p.evaluate("window.requestAnimationFrame = () => 0")
        res = p.evaluate(COMPARE, [samples, K, EDGE])
        b.close()
    spatne = 0
    for r in res:
        chyb = r["jenOriginal"] + r["jenPrepis"]
        spatne += chyb
        print(f"pozice {r['cam']:5d}: teren {r['shodaTerenu']:5.1f} %, "
              f"zakryto v obou {r['obojeZakryto']:6d}, jen original "
              f"{r['jenOriginal']}, jen prepis {r['jenPrepis']}"
              f"  (horni pruh: {r['okrajJenOriginal']} / {r['okrajJenPrepis']})")
        if r["shodaTerenu"] < 85:
            print("  POZOR: teren nesedi - zarovnani (K) je nejspis spatne")
    print("COVERCHECK OK" if not spatne else f"COVERCHECK: {spatne} odchylek")
    sys.exit(1 if spatne else 0)


if __name__ == "__main__":
    main()
