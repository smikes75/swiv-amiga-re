#!/usr/bin/env python3
"""Slozi snimek primo z obsahu chip RAM - bez emulatoru a bez hry.

Vstupem je copper list (odkud vezmeme ukazatele bitplanu, paletu, splity a
registry displeje) a chip RAM. Vystupem jsou oddelene vrstvy:

  teren.png   ctyri bitplany hry (v nich uz jsou zablitovane BOBy)
  hud.png     paty bitplan, ktery copper zapina jen v pasu HUD
  sprity.png  osm hardwarovych sprite kanalu
  slozeno.png vsechno dohromady

Je to zaroven test celeho pochopeni: kdyz slozeny obraz sedi s tim, co
ukazuje emulator, znamena to, ze model displeje je spravny.

**Stav 2026-09-09: 73 % shody s emulatorem** pri toleranci 20 na kanal.

Cesta k tomu cislu stala za dve opravy, obe v mereni, ne v modelu:
1. **Gamma.** Prvni verze prevadela RGB12 jako `nibble * 17`, kdezto vAmiga
   linearizuje CRT gammou 2.8 a re-koduje 1/2.2. Rozdil byl systematicky
   (102 -> 72, 85 -> 56, 51 -> 28) a shodu drzel na 21 %. Tabulka je stejna
   jako `VAMIGA_LUT` v `tools/compare.py`.
2. **Vyrez.** Vyrez `(124, 26)` je z `tools/compare.py`, ktery porovnava
   snimek z VAHeadless - ten ma jine okraje. Spravny vyrez pro texturu z
   naseho harnessu je `(62, 18)`; hledanim maxima vyskocil ze 33 na 73 %.

Predtim jsem myslel, ze rozdil je casovy - ze se bitplany ctou po dobehnuti
snimku, kdezto textura vznikla behem rasterizace. **Zmereno a vyvraceno:**
cteni na `VP` 0, 44, 150, 260 i 300 (pres `wasm_step_line`) dava shodu
20-21 %, tedy nezavisle na okamziku.

Zbylych 27 % jsou hardwarove sprity (osm kanalu, ktere `render()` zatim
nekresli), okraje mimo DIW a pixely na hranach objektu.

    python3 tools/layers.py [adresar]
"""
import base64
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "survey"))
import copper as copper_mod                          # noqa: E402
import vacmp                                         # noqa: E402
from playwright.sync_api import sync_playwright      # noqa: E402

W, H = 320, 256


def parse_copper(data, base):
    """Z copper listu vytahne vse, co je k slozeni obrazu potreba."""
    st = {"bpl": {}, "spr": {}, "pal": {}, "splits": [], "bplcon0": 0,
          "mod": (0, 0), "diw": (0, 0), "ddf": (0, 0)}
    live = {}
    vp = 0
    for i in range(0, len(data) - 3, 4):
        w1 = (data[i] << 8) | data[i + 1]
        w2 = (data[i + 2] << 8) | data[i + 3]
        if w1 == 0xffff and w2 == 0xfffe:
            break
        if w1 & 1:                                   # WAIT
            vp = (w1 >> 8) & 0xff
            continue
        r = w1 & 0x1fe
        if 0x0e0 <= r < 0x100:                       # BPLxPT
            # Pozor: pri splitu se zapisuje HI a LO zvlast, takze se musi
            # drzet ziva hodnota. Do vychoziho stavu ale patri jen to, co
            # copper nastavi PRED prvnim WAIT - jinak by se obraz kreslil
            # celý z bitmapy, ktera plati az od `VP=197`.
            n, hi = (r - 0x0e0) // 4, not ((r >> 1) & 1)
            cur = live.get(n, 0)
            live[n] = ((w2 << 16) | (cur & 0xffff)) if hi else \
                      ((cur & 0xffff0000) | w2)
            if vp:
                st["splits"].append((vp, "bpl", n, live[n]))
            else:
                st["bpl"][n] = live[n]
        elif 0x120 <= r < 0x140:                     # SPRxPT
            n, hi = (r - 0x120) // 4, not ((r >> 1) & 1)
            cur = st["spr"].get(n, 0)
            st["spr"][n] = ((w2 << 16) | (cur & 0xffff)) if hi else \
                           ((cur & 0xffff0000) | w2)
        elif 0x180 <= r < 0x1c0:                     # COLORxx
            c = (r - 0x180) // 2
            if vp:
                st["splits"].append((vp, "col", c, w2))
            else:
                st["pal"][c] = w2
        elif r == 0x100:
            if vp:
                st["splits"].append((vp, "con0", 0, w2))
            else:
                st["bplcon0"] = w2
        elif r == 0x108:
            st["mod"] = (w2, st["mod"][1])
        elif r == 0x10a:
            st["mod"] = (st["mod"][0], w2)
        elif r == 0x08e:
            st["diw"] = (w2, st["diw"][1])
        elif r == 0x090:
            st["diw"] = (st["diw"][0], w2)
        elif r == 0x092:
            st["ddf"] = (w2, st["ddf"][1])
        elif r == 0x094:
            st["ddf"] = (st["ddf"][0], w2)
    return st


# vAmiga neprevadi RGB12 linearne (nibble*17): Denise linearizuje CRT gammou
# 2.8 a re-koduje 1/2.2. Tabulka je zmerena v tools/compare.py; pouzivame ji
# tady, aby slo porovnavat se snimkem emulatoru ve stejne soustave.
VAMIGA_LUT = [0, 0, 0, 28, 43, 56, 72, 89, 106, 123, 141, 159, 178, 197, 216, 236]


def rgb12(word, lut=True):
    n = [(word >> 8) & 15, (word >> 4) & 15, word & 15]
    return tuple(VAMIGA_LUT[v] if lut else v * 17 for v in n)


def render(chip, chipbase, st, planes=None, first_row=0):
    """Slozi RGB obraz z bitplanu. `planes` omezi pocet rovin."""
    n = planes if planes is not None else ((st["bplcon0"] >> 12) & 7)
    mod = st["mod"][0]
    row_bytes = W // 8 + mod                          # 40 + modulo
    pal = dict(st["pal"])
    # splity setridime podle radku, aplikujeme za behu
    splits = sorted([s for s in st["splits"]], key=lambda s: s[0])
    px = bytearray(W * H * 3)
    si = 0
    bpl = dict(st["bpl"])
    for y in range(H):
        vp = 44 + y                                   # DIWSTRT V = 0x2C
        while si < len(splits) and splits[si][0] <= vp:
            _, kind, idx, val = splits[si]; si += 1
            if kind == "col":
                pal[idx] = val
            elif kind == "bpl":
                bpl[idx] = val
            elif kind == "con0":
                n = (val >> 12) & 7 if planes is None else n
        for x in range(W):
            c = 0
            for p in range(n):
                addr = bpl.get(p, 0) - chipbase + y * row_bytes + (x >> 3)
                if 0 <= addr < len(chip):
                    if chip[addr] & (0x80 >> (x & 7)):
                        c |= 1 << p
            r, g, b = rgb12(pal.get(c, 0))
            o = (y * W + x) * 3
            px[o] = r; px[o + 1] = g; px[o + 2] = b
    return bytes(px)


def grab():
    srv, port = vacmp.serve(os.path.join(ROOT, "web"))
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{port}/vacmp.html")
            page.wait_for_function("window.VA && window.VA.ready", timeout=60000)
            page.evaluate("([r, a]) => VA.boot(r, a)", [
                base64.b64encode(open(vacmp.ROM, "rb").read()).decode(),
                base64.b64encode(open(vacmp.ADF, "rb").read()).decode()])
            page.evaluate(vacmp.PLAY_PROLOGUE)
            page.evaluate("() => playFor(20)")
            info = page.evaluate("""() => {
              VA.regTrace(true); VA.run(2, null); VA.regTrace(false);
              const t = VA.regTraceRead();
              let hi = 0, lo = 0;
              for (const e of t) { if (e.reg === 0x080) hi = e.value;
                                   if (e.reg === 0x082) lo = e.value; }
              return { cop: (hi << 16) | lo, chip: VA.fn.chipSize() };
            }""")
            chip = base64.b64decode(page.evaluate("([o, n]) => VA.chip(o, n)",
                                                  [0, info["chip"]]))
            shot = base64.b64decode(page.evaluate("() => VA.frameRGB()"))
            browser.close()
    finally:
        srv.shutdown()
    return info["cop"], chip, shot


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "build", "layers")
    os.makedirs(out, exist_ok=True)
    cop, chip, shot = grab()
    print("COP1LC = $%06X, chip RAM %d kB" % (cop, len(chip) // 1024))
    st = parse_copper(chip[cop:cop + 4096], cop)
    print("bitplany:", {k: "$%06X" % v for k, v in sorted(st["bpl"].items())})
    print("BPLCON0 = $%04X -> %d rovin, moduly %s, splitu %d" %
          (st["bplcon0"], (st["bplcon0"] >> 12) & 7, st["mod"], len(st["splits"])))
    from PIL import Image
    teren = render(chip, 0, st, planes=4)
    Image.frombytes("RGB", (W, H), teren).save(os.path.join(out, "teren.png"))
    slozeno = render(chip, 0, st, planes=None)
    Image.frombytes("RGB", (W, H), slozeno).save(os.path.join(out, "slozeno.png"))
    em = Image.frombytes("RGB", (716, 285), shot)
    em.save(os.path.join(out, "emulator.png"))
    # Emulator vraci 716x285 se dvojnasobnou vodorovnou hustotou. Vyrez
    # odpovidajici hernimu poli je (62, 18) - zmereno hledanim maxima shody.
    # Neni to vyrez z tools/compare.py: ten porovnava snimek z VAHeadless,
    # ktery ma jine okraje.
    crop = em.crop((62, 18, 62 + 640, 18 + 256)).resize((W, H), Image.NEAREST)
    crop.save(os.path.join(out, "emulator_320.png"))
    ours = Image.frombytes("RGB", (W, H), slozeno)
    a, bpx = ours.load(), crop.load()
    same = 0
    for y in range(H):
        for x in range(W):
            p1, p2 = a[x, y], bpx[x, y]
            if all(abs(p1[i] - p2[i]) <= 20 for i in range(3)):
                same += 1
    print("shoda s emulatorem: %.1f %% (%d z %d pixelu)" %
          (100.0 * same / (W * H), same, W * H))
    print("hotovo ->", out)


if __name__ == "__main__":
    main()
