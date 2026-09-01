#!/usr/bin/env python3
"""Treti kontrakt: snimek originalu (headless vAmiga) vs prepis (game.html).

Original je deterministicky (tools/baseline.sh, vstupni sekvence tamtez);
prepis se pro kazdy checkpoint postavi na PRESNE zmereny radek mapy, aby
porovnani nezaviselo na casu startu. Surove snimky originalu se cachuji
v build/baseline/ (gitignore) - prvni beh je stahne z emulatoru.

Prah celeho snimku je zamerne zarazka (ratchet): lezi tesne pod aktualne
zmerenou hodnotou a smi se jen zvedat. Vedle nej skript diagnosticky vypise
shodu samotneho terenu, HUD a HELI. Masky HUD/HELI se odvozuji ze stejneho
renderu s vypnutymi vrstvami; terrain proto nezahrnuje ani jejich pixely.

Zname zbyvajici zdroje rozdilu: sumova textura terenu (nas LCG neni
generator hry), zbytky profilu/capture (kryje tolerance) a faze animaci
nepratel.

    python3 tools/compare.py            # vsechny checkpointy
    python3 tools/compare.py start      # jeden checkpoint
"""

import base64
import io
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "build", "baseline")
CROP = (62, 18, 640, 256)        # obsah v 716x285 texture, 2:1 -> 320x256
FRAME_SIZE = (320, 256)
TOLERANCE = 24                   # na kanal; kryje zbytek capture profilu

# name: cas snimku originalu v sekundach po fire, zmereny radek mapy
# v img souradnicich prepisu a minimalni whole-frame shoda v %.
CHECKPOINTS = {
    # Po TOWN palete a kalibraci registrovych barev: 22.5 %. Dominantni
    # zbytek je sumova textura terenu - LCG neni generator hry.
    "start": {"t": 17, "row": 3229, "floor": 22.0},
}


def original_frame(t):
    raw = os.path.join(CACHE, f"orig_t{t}.raw")
    if not os.path.exists(raw):
        os.makedirs(CACHE, exist_ok=True)
        subprocess.run([os.path.join(ROOT, "tools", "baseline.sh"),
                        os.path.join(CACHE, "orig"), str(t)],
                       check=True, capture_output=True)
    from PIL import Image
    with open(raw, "rb") as source:
        data = source.read()
    x, y, width, height = CROP
    return (Image.frombytes("RGB", (716, 285), data)
            .crop((x, y, x + width, y + height))
            .resize(FRAME_SIZE, Image.NEAREST))


def _decode_data_url(data):
    from PIL import Image
    payload = base64.b64decode(data.split(",", 1)[1])
    with Image.open(io.BytesIO(payload)) as image:
        return image.convert("RGB")


def remake_frames(row):
    """Return whole, HUD-free/player-free, and player-free frame variants."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            page.goto("file://" + os.path.join(ROOT, "game.html"))
            page.set_input_files("#fpick", os.path.join(ROOT, "SWIVFIX.ADF"))
            page.wait_for_selector("#titlewrap", state="visible")
            # Nativni attract fire spousti TOWN primo; level picker je pouze
            # vyvojarska L zkratka. Wall-clock RAF zastavime jeste pred fire,
            # aby checkpoint vznikl jen z rucne provedeneho renderu nize.
            page.evaluate("window.requestAnimationFrame = () => 0")
            page.keyboard.press(" ")
            page.wait_for_selector("#gamewrap", state="visible")
            encoded = page.evaluate("""(row) => {
              const g = state.g, p = g.player;
              // Presny radek, zadni aktivni mapovi objekty, hrac ve spawn
              // stavu. Original ma HELI frame 0 na (160,192) se stinem.
              g.scroll = row; g.fadeBlack = 0; g.fadeDir = 0;
              g.fadeWhite = 0;
              g.spawns = []; g.air = []; g.hazards = []; g.shots = [];
              g.bullets = []; g.tokens = []; g.booms = []; g.effects = [];
              g.plops = [];
              p.alive = true; p.x = 160; p.y = 192;
              p.inv = 0; p.flash = false;
              resetPlayerHeliAnim(p);

              const canvas = document.querySelector('#game');
              const now = performance.now();
              // Original t17 uz je davno za cold-boot prvnim Copper radkem;
              // checkpoint proto porovnava ustalenou COLOR16 sekvenci.
              const initialHudPrimed = true;
              const render = () => {
                // Kazda varianta musi mit stejny first-pass stav a nesmi
                // posunout scheduler o jediny tick.
                g.hudCopperPrimed = initialHudPrimed;
                g.last = now;
                frame(now);
                return canvas.toDataURL('image/png');
              };

              const whole = render();

              p.alive = false;
              const withoutHeli = render();

              const hudKey = hudStatusText(g) + '\\0PRESS FIRE';
              g.hudPlaneKey = hudKey;
              g.hudPlane = {
                bytes: new Uint8Array(HUD_STRIDE * HUD_ROWS),
                leftWidth: 0, rightWidth: 0, rightX: 0,
              };
              const terrain = render();

              return { whole, withoutHeli, terrain };
            }""", row)
        finally:
            browser.close()
    return {name: _decode_data_url(data) for name, data in encoded.items()}


def _pixel_changed(a, b, x, y):
    return a.getpixel((x, y)) != b.getpixel((x, y))


def region_masks(frames):
    """Build disjoint masks for the HUD, HELI (incl. shadow), and terrain."""
    width, height = FRAME_SIZE
    whole = frames["whole"]
    without_heli = frames["withoutHeli"]
    terrain = frames["terrain"]
    masks = {"whole": [], "terrain": [], "HUD": [], "HELI": []}
    for y in range(height):
        for x in range(width):
            point = (x, y)
            hud = _pixel_changed(without_heli, terrain, x, y)
            heli = _pixel_changed(whole, without_heli, x, y)
            masks["whole"].append(point)
            if heli:
                masks["HELI"].append(point)
            elif hud:
                masks["HUD"].append(point)
            else:
                masks["terrain"].append(point)
    return masks


def match_percent(a, b, pixels=None):
    if pixels is None:
        width, height = FRAME_SIZE
        pixels = ((x, y) for y in range(height) for x in range(width))
    pa, pb = a.load(), b.load()
    same = total = 0
    for x, y in pixels:
        ca, cb = pa[x, y], pb[x, y]
        total += 1
        if (abs(ca[0] - cb[0]) <= TOLERANCE and
                abs(ca[1] - cb[1]) <= TOLERANCE and
                abs(ca[2] - cb[2]) <= TOLERANCE):
            same += 1
    return (same * 100.0 / total) if total else 0.0


def diff_image(a, b, path):
    from PIL import Image
    width, height = FRAME_SIZE
    out = Image.new("RGB", FRAME_SIZE)
    pa, pb, po = a.load(), b.load(), out.load()
    for y in range(height):
        for x in range(width):
            ca, cb = pa[x, y], pb[x, y]
            bad = (abs(ca[0] - cb[0]) > TOLERANCE or
                   abs(ca[1] - cb[1]) > TOLERANCE or
                   abs(ca[2] - cb[2]) > TOLERANCE)
            po[x, y] = ((255, 40, 40) if bad else
                        (ca[0] // 3, ca[1] // 3, ca[2] // 3))
    out.save(path)


def main():
    names = ([arg for arg in sys.argv[1:] if not arg.startswith("-")]
             or list(CHECKPOINTS))
    unknown = [name for name in names if name not in CHECKPOINTS]
    if unknown:
        choices = ", ".join(CHECKPOINTS)
        raise SystemExit(f"neznamy checkpoint: {', '.join(unknown)}; "
                         f"dostupne: {choices}")

    failed = False
    for name in names:
        checkpoint = CHECKPOINTS[name]
        original = original_frame(checkpoint["t"])
        frames = remake_frames(checkpoint["row"])
        masks = region_masks(frames)
        scores = {
            "whole": match_percent(original, frames["whole"], masks["whole"]),
            "terrain": match_percent(original, frames["terrain"],
                                     masks["terrain"]),
            "HUD": match_percent(original, frames["whole"], masks["HUD"]),
            "HELI": match_percent(original, frames["whole"], masks["HELI"]),
        }

        os.makedirs(CACHE, exist_ok=True)
        remake_rel = os.path.join("build", "baseline", f"remake_{name}.png")
        frames["whole"].save(os.path.join(ROOT, remake_rel))
        diff_rel = os.path.join("build", "baseline", f"diff_{name}.png")
        diff_image(original, frames["whole"], os.path.join(ROOT, diff_rel))

        floor = checkpoint["floor"]
        ok = floor is None or scores["whole"] >= floor
        status = "OK" if ok else "POD PRAHEM"
        print(f"{name}: t={checkpoint['t']}, row={checkpoint['row']}")
        print(f"  whole:   {scores['whole']:6.1f} %  "
              f"ratchet >= {floor}  [{status}]")
        print(f"  terrain: {scores['terrain']:6.1f} %  "
              f"({len(masks['terrain'])} px; bez HUD/HELI)")
        print(f"  HUD:     {scores['HUD']:6.1f} %  ({len(masks['HUD'])} px)")
        print(f"  HELI:    {scores['HELI']:6.1f} %  "
              f"({len(masks['HELI'])} px; telo+stin)")
        print(f"  remake: {remake_rel}")
        print(f"  diff: {diff_rel}")
        if not ok:
            failed = True
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
