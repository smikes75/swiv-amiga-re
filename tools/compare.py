#!/usr/bin/env python3
"""Treti kontrakt: snimek originalu (headless vAmiga) vs prepis (game.html).

Original je deterministicky (tools/baseline.sh, vstupni sekvence tamtez);
prepis se pro kazdy checkpoint postavi na PRESNE zmereny radek mapy, aby
porovnani nezaviselo na casu startu. Surove snimky originalu se cachuji
v build/baseline/ (gitignore) - prvni beh je stahne z emulatoru.

Prah shody je zamerne "rachna" (ratchet): lezi tesne pod aktualne
zmerenou hodnotou a smi se jen zvedat. Zname zbyvajici zdroje rozdilu:
sumova textura terenu (nas LCG neni generator hry), vAmiga pridava ke
kazdemu kanalu ~+4 (kryje tolerance) a faze animaci nepratel.

    python3 tools/compare.py            # vsechny checkpointy
    python3 tools/compare.py start      # jeden checkpoint
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "build", "baseline")
CROP = (62, 18, 640, 256)        # obsah v 716x285 texture, 2:1 -> 320x256
TOLERANCE = 24                   # na kanal; kryje vAmiga offset ~+4

# name: (cas snimku originalu v sekundach po fire, zmereny radek mapy
# v img souradnicich prepisu, minimalni shoda v %)
CHECKPOINTS = {
    # radek zmereny scanem proti baseline; 20.1 % pri zavedeni (dominantni
    # zbytek je sumova textura terenu - LCG neni generator hry)
    "start": {"t": 17, "row": 3229, "floor": 18.0},
}


def original_frame(t):
    raw = os.path.join(CACHE, f"orig_t{t}.raw")
    if not os.path.exists(raw):
        os.makedirs(CACHE, exist_ok=True)
        subprocess.run([os.path.join(ROOT, "tools", "baseline.sh"),
                        os.path.join(CACHE, "orig"), str(t)],
                       check=True, capture_output=True)
    from PIL import Image
    d = open(raw, "rb").read()
    x, y, w, h = CROP
    return Image.frombytes("RGB", (716, 285), d) \
        .crop((x, y, x + w, y + h)).resize((320, 256), Image.NEAREST)


def remake_frame(row):
    from playwright.sync_api import sync_playwright
    import base64
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page()
        page.goto("file://" + os.path.join(ROOT, "game.html"))
        page.set_input_files("#fpick", os.path.join(ROOT, "SWIVFIX.ADF"))
        page.wait_for_selector("#titlewrap", state="visible")
        page.keyboard.press(" ")
        page.wait_for_selector("#levelpick", state="visible")
        page.evaluate("window.requestAnimationFrame = () => 0")
        page.click("#levelbtns a:first-child")
        page.wait_for_selector("#gamewrap", state="visible")
        data = page.evaluate("""(row) => {
          const g = state.g, p = g.player;
          // presny radek, zadni aktivni objekty, hrac ve spawn stavu
          // (original ma na snimku hrace frame 0 na 160,192 se stinem)
          g.scroll = row; g.fadeBlack = 0; g.fadeDir = 0; g.fadeWhite = 0;
          g.spawns = []; g.air = []; g.hazards = []; g.shots = [];
          g.bullets = []; g.tokens = []; g.booms = []; g.effects = [];
          g.plops = [];
          p.alive = true; p.x = 160; p.y = 192; p.inv = 0; p.flash = false;
          resetPlayerHeliAnim(p);
          const now = performance.now(); g.last = now; frame(now);
          return document.querySelector('#game').toDataURL('image/png');
        }""", row)
        b.close()
    from PIL import Image
    import io
    return Image.open(io.BytesIO(base64.b64decode(data.split(",", 1)[1]))) \
        .convert("RGB")


def match_percent(a, b):
    pa, pb = a.load(), b.load()
    same = 0
    for y in range(256):
        for x in range(320):
            ca, cb = pa[x, y], pb[x, y]
            if (abs(ca[0] - cb[0]) <= TOLERANCE and
                    abs(ca[1] - cb[1]) <= TOLERANCE and
                    abs(ca[2] - cb[2]) <= TOLERANCE):
                same += 1
    return same * 100.0 / (320 * 256)


def diff_image(a, b, path):
    from PIL import Image
    out = Image.new("RGB", (320, 256))
    pa, pb, po = a.load(), b.load(), out.load()
    for y in range(256):
        for x in range(320):
            ca, cb = pa[x, y], pb[x, y]
            bad = (abs(ca[0] - cb[0]) > TOLERANCE or
                   abs(ca[1] - cb[1]) > TOLERANCE or
                   abs(ca[2] - cb[2]) > TOLERANCE)
            po[x, y] = (255, 40, 40) if bad else \
                (ca[0] // 3, ca[1] // 3, ca[2] // 3)
    out.save(path)


def main():
    names = [a for a in sys.argv[1:] if not a.startswith("-")] \
        or list(CHECKPOINTS)
    failed = False
    for name in names:
        cp = CHECKPOINTS[name]
        orig = original_frame(cp["t"])
        rem = remake_frame(cp["row"])
        pct = match_percent(orig, rem)
        os.makedirs(CACHE, exist_ok=True)
        diff_image(orig, rem, os.path.join(CACHE, f"diff_{name}.png"))
        floor = cp["floor"]
        ok = floor is None or pct >= floor
        print(f"{name}: shoda {pct:.1f} % (prah {floor}), "
              f"diff build/baseline/diff_{name}.png"
              + ("" if ok else "  << POD PRAHEM"))
        if not ok:
            failed = True
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
