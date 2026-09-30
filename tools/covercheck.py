#!/usr/bin/env python3
"""Maska popredi: rovina originalu proti `g.coverMask` prepisu.

Original kresli objekty s `+397` bit 0 a vsechny stiny jen tam, kde je
volna samostatna rovina obrazovky `[fp@(256)]+4` (`0x3fe2`: maska spritu AND
rovina do scratch `fp@(252)`, ta je pak maskou cookie blitu). Rovinu
nuluji snimky dlazdic s atributem bit 1 (bajt `flags` casti LIN, 0x02) pri
kresleni do pruhu (`0x3e38` -> `0x4068`, minterm NOT A AND C). Prepis
sklada tutez masku v `renderMap` (`coverMask`).

Skript pusti original v harnessu vAmiga (tools/survey/vacmp.py), dojede na
zadane mapove pozice jizdou `vacmp.jizda` (kazdy snimek smaze bit 3
zamku instalace, drzi zivoty a vyprosti zablokovany zavadec) a na kazde precte rovinu popredi i ctyri
bitplany terenu. Rovina je kruhova: radek bufferu = (kamera + sy) mod 320,
44 bajtu na radek. Zarovnani s mapou prepisu (radek = pozice - 32826) se
overi shodou barevnych indexu terenu.

Horni pruh obrazovky (sy < 32, jeden pruh terenu 0x3422) se hlasi
zvlast: tam se prave stavi dalsi pruh a rovina muze byt jeste
nedokreslena (ICE: 444 bodu).

    python3 tools/covercheck.py                  # DESERT, GRASS, RIVER, ICE
    python3 tools/covercheck.py 42000 37000 33100   # ICE, SCIFI, FINAL
    python3 tools/covercheck.py 0 52000          # 0 = start TOWN, pak DESERT

Vysledek 2026-09-29: TOWN (start + 3 dalsi okamziky), DESERT 52000, GRASS
48788, RIVER 45488, ICE 42735 - 0 odchylek mimo horni pruh (ICE 444 bodu
v nem). "Zamek ICE" byl konec hry (harness ted drzi zivoty) a zaseknuti
na 46159 roztristena chip RAM kvuli chybe skenu pameti ve fix wrapperu
(harness ji zaplatuje, docs/LOADER.md); jizda projede az do FINAL.
"""
import base64
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "survey"))
import vacmp                                        # noqa: E402
from playwright.sync_api import sync_playwright     # noqa: E402

K = 32826               # radek retezu prepisu = mapova pozice - K
EDGE = 32               # horni pruh: teren se stavi po pruzich 32 radku (0x3422)

DUMP = """(cfg) => {
  const m = VA.mem(), L = m.L, U = m.U;
  if (cfg.start) {                  // start TOWN: az po uvolneni zamku scrollu
    let guard = 0;
    while (m.rd(cfg.a6 + 166) !== 0 && guard++ < 3000) VA.run(4, null);
    VA.run(300, null);
  }
  VA.run(2, null);
  const st = L(cfg.a6 + 256);       // popis obrazovky (ve slow RAM), bitplany v chip
  const b64 = (a, n) => { let s = '';
    for (let i = 0; i < n; i++) s += String.fromCharCode(m.rd(a + i));
    return btoa(s); };
  return { cam: U(st + 8), cover: b64(L(st + 4), 14080),
           planes: b64(L(st), 56320) };
}"""

COMPARE = """([samples, K, EDGE]) => {
  // Retez map prepisu: TOWN..RIVER je jeden (startGame(0)), ICE, SCIFI
  // a FINAL maji vlastni. Uroven a presny posun radku (K +-4) se vybere
  // podle nejlepsi shody barevnych indexu terenu.
  const maps = {};
  const mapOf = lv => { if (!maps[lv]) { startGame(lv); const g = state.g;
    maps[lv] = { W: g.mapW || 320, mi: g.mapIndex, cm: g.coverMask }; }
    return maps[lv]; };
  return samples.map(s => {
    let best = null;
    for (const lv of [0, 4, 5, 6]) {
      const m = mapOf(lv);
      for (let dk = -4; dk <= 4; dk++) {
        const R0 = s.cam - K - dk;
        if (R0 < 0 || (R0 + 256) * m.W > m.mi.length) continue;
        let t = 0, n = 0;
        for (let sy = 0; sy < 256; sy += 4) for (let x = 0; x < 320; x += 4) {
          n++; if (s.idx[sy][x] === m.mi[(R0 + sy) * m.W + x]) t++; }
        if (!best || t / n > best.q) best = { q: t / n, lv, R0 };
      }
    }
    const { W, mi, cm } = mapOf(best.lv), R0 = best.R0;
    let teren = 0, n = 0;
    const r = { cam: s.cam, uroven: best.lv, radek: R0, obojeZakryto: 0,
                jenOriginal: 0, jenPrepis: 0, okrajJenOriginal: 0, okrajJenPrepis: 0 };
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
            vacmp.prolog(page)
            for t in targets:
                if t:
                    r = vacmp.jizda(page, t)
                    stuck = "  ZASEKNUTO" if r["pos"] > t else ""
                    stuck += f"  (vyprosteni {r['vyprosteni']})" if r["vyprosteni"] else ""
                    print(f"  original: pozice {r['pos']} (cil {t}){stuck}",
                          flush=True)
                out.append(page.evaluate(DUMP, {"a6": vacmp.A6_BASE,
                                                "start": not t}))
            br.close()
    finally:
        srv.shutdown()
    return out


CACHE = os.path.join(ROOT, "build", "vacmp", "cover.json")


def main():
    # --ulozene: znovu porovnat posledni zaznam originalu (jizda trva ~30 min)
    if "--ulozene" in sys.argv:
        raw = json.load(open(CACHE))
    else:
        targets = [int(a) for a in sys.argv[1:]] or [52000, 48788, 45488, 42000]
        raw = original(targets)
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        json.dump(raw, open(CACHE, "w"))
    samples = [decode(d) for d in raw]
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
        print(f"pozice {r['cam']:5d} (uroven {r['uroven']}, radek {r['radek']}): "
              f"teren {r['shodaTerenu']:5.1f} %, "
              f"zakryto v obou {r['obojeZakryto']:6d}, jen original "
              f"{r['jenOriginal']}, jen prepis {r['jenPrepis']}"
              f"  (horni pruh: {r['okrajJenOriginal']} / {r['okrajJenPrepis']})")
        if r["shodaTerenu"] < 85:
            print("  POZOR: teren nesedi - zarovnani (K) je nejspis spatne")
    print("COVERCHECK OK" if not spatne else f"COVERCHECK: {spatne} odchylek")
    sys.exit(1 if spatne else 0)


if __name__ == "__main__":
    main()
