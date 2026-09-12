#!/usr/bin/env python3
"""Odecte ZIVY seznam BOBu `fp@(208)` z bezici hry v originalu.

Staticke cteni blitovaci rady (docs/CHIPSET.md) nevysvetlilo, proc jsou
pozemni objekty prekryte terenem. Tenhle skript se proto zepta primo
bezici hry: dojede na zadanou mapovou pozici, prochazi obousmerne vazany
seznam `fp@(208)` a vypise kazdy zaznam.

Struktura zaznamu (z `0x4826` a `0x367c`):
    +0  dalsi        +4  predchozi
    +8  klic trideni (u dlazdic `(vrstva << 8) + poradi`)
    +10 graficke slovo    +12 x    +14 radek
    +16/+18 fronta obnovy      +20/+21 priznakove bajty

    python3 tools/survey/boblist.py 45488
"""
import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import vacmp                                             # noqa: E402
import zoneshot                                          # noqa: E402
from playwright.sync_api import sync_playwright          # noqa: E402

A6 = vacmp.A6_BASE
BOB_HEAD = 208            # fp@(208)
TILE_HEAD = 3564          # fp@(3564)

DUMP_JS = """(cfg) => {
  const H = VA.M.HEAPU8, p = VA.fn.chipPtr();
  const be16 = a => (H[a] << 8) | H[a + 1];
  const s16 = a => { const v = be16(a); return v & 0x8000 ? v - 0x10000 : v; };
  const be32 = a => ((H[a]<<24 | H[a+1]<<16 | H[a+2]<<8 | H[a+3]) >>> 0);
  const out = [];
  const hlava = cfg.head;                 // amigovska adresa hlavy seznamu
  let uzel = be32(p + hlava);
  let n = 0;
  while (uzel && uzel !== hlava && n < cfg.limit) {
    const a = p + uzel;
    out.push({ adr: uzel,
               klic: be16(a + 8), gfx: be16(a + 10),
               x: s16(a + 12), radek: s16(a + 14),
               f20: H[a + 20], f21: H[a + 21] });
    uzel = be32(a);
    n++;
  }
  return out;
}"""


def main():
    cil = int(sys.argv[1]) if len(sys.argv) > 1 else 45488
    srv, port = vacmp.serve(os.path.join(vacmp.ROOT, "web"))
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(f"http://127.0.0.1:{port}/vacmp.html")
        page.wait_for_function("window.VA && window.VA.ready", timeout=60000)
        rom = base64.b64encode(open(vacmp.ROM, "rb").read()).decode()
        adf = base64.b64encode(open(vacmp.ADF, "rb").read()).decode()
        err = page.evaluate("([r, a]) => VA.boot(r, a)", [rom, adf])
        if err:
            b.close(); srv.shutdown(); sys.exit("boot: " + err)
        page.evaluate(vacmp.PLAY_PROLOGUE)
        r = page.evaluate(zoneshot.DRIVE_JS, {"target": cil, "limit": 200000})
        print(f"mapova pozice {r['pos']} (cil {cil}) po {r['frames']} snimcich",
              flush=True)

        glob = page.evaluate("""(a6) => {
          const H = VA.M.HEAPU8, p = VA.fn.chipPtr();
          const be16 = a => (H[a] << 8) | H[a + 1];
          const s16 = a => { const v = be16(a); return v & 0x8000 ? v - 65536 : v; };
          const be32 = a => ((H[a]<<24|H[a+1]<<16|H[a+2]<<8|H[a+3])>>>0);
          const g = o => s16(p + a6 + o);
          const desc = o => { const b = be32(p + a6 + o); return {
            adr: b, bitmapa: be32(p + b), radek: be16(p + b + 8),
            obnovCitac: be16(p + b + 16), obnovPtr: be32(p + b + 18) }; };
          return { kamera: g(3530), stavitel: g(3538), ctec: g(3586),
                   zamek: H[p + a6 + 166],
                   obrazovka: desc(256), druhy: desc(260), strip: desc(264) };
        }""", A6)
        print("\nglobaly:")
        print("  fp@(3530) kamera    %7d" % glob["kamera"])
        print("  fp@(3538) stavitel  %7d" % glob["stavitel"])
        print("  fp@(3586) ctec mapy %7d" % glob["ctec"])
        print("  fp@(166)  zamek     0x%02x" % glob["zamek"])
        for jm, k in (("fp@(256) obrazovka", "obrazovka"),
                      ("fp@(260) druhy   ", "druhy"),
                      ("fp@(264) strip   ", "strip")):
            d = glob[k]
            print("  %s popis %06x bitmapa %06x radek %5d obnov %d" %
                  (jm, d["adr"], d["bitmapa"], d["radek"], d["obnovCitac"]))

        for jmeno, head in (("BOBy fp@(208)", A6 + BOB_HEAD),
                            ("dlazdice fp@(3564)", A6 + TILE_HEAD)):
            zaznamy = page.evaluate(DUMP_JS, {"head": head, "limit": 400})
            print(f"\n=== {jmeno}: {len(zaznamy)} zaznamu ===")
            print("  %-8s %-6s %-6s %-5s %-6s %-5s %-5s" %
                  ("adresa", "klic", "gfx", "x", "radek", "+20", "+21"))
            for z in zaznamy[:60]:
                print("  %06x   %5d  0x%04x %5d %6d  0x%02x  0x%02x" %
                      (z["adr"], z["klic"], z["gfx"], z["x"], z["radek"],
                       z["f20"], z["f21"]))
            if len(zaznamy) > 60:
                print(f"  ... a dalsich {len(zaznamy) - 60}")
        b.close()
    srv.shutdown()
    if errs:
        sys.exit("chyby stranky: " + "; ".join(errs))


if __name__ == "__main__":
    main()
