#!/usr/bin/env python3
"""Najde `ticks` a `row` pro novy checkpoint compare.py mechanicky.

Rucni mereni posunu proti baseline bylo u kazdeho ze ctyr puvodnich
checkpointu jednotlivou praci; proto jich taky ctyri zustaly. Tenhle
skript to dela strojove: v JEDNOM prubehu prohlizece nechá prepis dojit
na spodni okraj okna kandidatu a pak po jednom tiku renderuje, takze
cena je O(ticks + rozsah), ne O(ticks * rozsah).

Renderovani nesmi posunout scheduler - stejne jako v compare.py se vola
`frame(now)` s pevnym casem, ktery neprida zadny tick.

    python3 tools/align.py 26 28 30        # navrhne zaznamy CHECKPOINTS
    python3 tools/align.py 26 --okno 60    # sirsi hledani

Druhy rezim hleda RADEK misto tiku. Pouziva se na snimky z jinych zon,
kam se baseline.sh dostane jen dlouhym behem (a kde tedy neplati zadny
vzorec cas -> tik). Prepis se postavi primo do dane urovne a scroll se
prohleda nejdriv nahrubo po 16 radcich, pak najemno:

    python3 tools/align.py --snimek build/deep/d_t900.raw --uroven 1

Vystup je rovnou telo zaznamu; `floor` je zmerena shoda zaokrouhlena
dolu na desetinu procenta minus rezerva 0.1, tedy stejna zarazka, jakou
pouzivaji stavajici checkpointy.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import compare                                          # noqa: E402

# Baseline drzi joystick v klidu a fade-in TOWN zacina ~17 s po fire;
# prvni checkpoint lezi na 83 tikach, dalsi po 50 na sekundu. vAmiga ma
# ve `wait` jitter jednoho snimku, proto se okolo odhadu hleda.
BASE_T, BASE_TICKS, TICKS_PER_SECOND = 17, 83, 50
VBL_BASE = 186
# Poradi volani 0x813a; RNG originalu nezname, x/vx jsou zmerene z t18/t19
# a t22. Posledni polozka se opakuje, takze dalsi vlny jdou po ni.
FODDER = [{"x": 257, "vx": -0.8125}, {"x": 195, "vx": 0.7}]


def candidates(t, window):
    guess = BASE_TICKS + (t - BASE_T) * TICKS_PER_SECOND
    return max(1, guess - window), guess + window


def remake_series(low, high):
    """Snimky prepisu pro kazdy pocet tiku v <low, high>."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            page.goto("file://" + os.path.join(ROOT, "game.html"))
            page.set_input_files("#fpick", os.path.join(ROOT, "SWIVFIX.ADF"))
            page.wait_for_selector("#titlewrap", state="visible")
            page.evaluate("window.requestAnimationFrame = () => 0")
            page.keyboard.press(" ")
            page.wait_for_selector("#gamewrap", state="visible")
            return page.evaluate("""(cfg) => {
              startGame(0);
              const g = state.g;
              g.scrollMul = 1;
              g.vblBase = cfg.vblBase | 0;
              let n = 0;
              window.fodderInitial = () => {
                const f = cfg.fodder[Math.min(n++, cfg.fodder.length - 1)];
                return { x: f.x, vx: f.vx };
              };
              for (let i = 0; i < cfg.low; i++) step(g);
              const canvas = document.querySelector('#game');
              const now = performance.now();
              const out = [];
              for (let ticks = cfg.low; ticks <= cfg.high; ticks++) {
                g.hudCopperPrimed = true;
                g.last = now;
                frame(now);
                out.push({ ticks,
                           row: Math.floor(g.scroll) - (g.rowOffset | 0),
                           png: canvas.toDataURL('image/png') });
                step(g);
              }
              return out;
            }""", {"low": low, "high": high, "vblBase": VBL_BASE,
                   "fodder": FODDER})
        finally:
            browser.close()


def raw_frame(path):
    """Syrovy 716x285 vyrez z VAHeadless -> stejny format jako baseline."""
    from PIL import Image
    with open(path, "rb") as source:
        data = source.read()
    x, y, width, height = compare.CROP
    return (Image.frombytes("RGB", (716, 285), data)
            .crop((x, y, x + width, y + height))
            .resize(compare.FRAME_SIZE, Image.NEAREST))


def row_series(level, rows=None, span=0, step=16, bare=False):
    """Snimky prepisu v dane urovni pro kazdy zadany radek scrollu."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            page.goto("file://" + os.path.join(ROOT, "game.html"))
            page.set_input_files("#fpick", os.path.join(ROOT, "SWIVFIX.ADF"))
            page.wait_for_selector("#titlewrap", state="visible")
            page.evaluate("window.requestAnimationFrame = () => 0")
            page.keyboard.press(" ")
            page.wait_for_selector("#gamewrap", state="visible")
            return page.evaluate("""(cfg) => {
              startGame(cfg.level);
              const g = state.g;
              // Uroven zacina zacernena (fadeBlack 256, 16 snimku fade-in
              // z 0x1028). Bez nekolika kroku by kazdy kandidat byl cerny.
              for (let i = 0; i < 24; i++) step(g);
              const canvas = document.querySelector('#game');
              const now = performance.now();
              // renderMap staví retez OD `lv` dal a `lv` je na jeho
              // SPODKU (scroll klesa smerem ke konci hry). Rozsah teto
              // urovne jsou proto nejvyssi radky, ne nulte.
              const top = g.mapH - 256;
              const rows = cfg.rows
                ? cfg.rows
                : (() => { const out = [];
                     for (let r = top; r > top - cfg.span; r -= cfg.step)
                       out.push(r);
                     return out; })();
              const out = [];
              for (const row of rows) {
                // Stejne jako vyvojarsky skok: meni se jen scroll a
                // `armed`; zive objekty nas tu nezajimaji, porovnava se
                // teren a staticke instalace.
                g.scroll = row; g.scrollPrev = row;
                for (const s of g.spawns) s.armed = armedAtStart(g, s);
                g.hudCopperPrimed = true;
                g.last = now;
                frame(now);
                const png = canvas.toDataURL('image/png');
                let bare = null;
                if (cfg.bare) {
                  // Druhy render bez jedineho BOBu. Pixely, ktere se od
                  // prvniho nelisi, jsou ciste teren - jen na nich ma
                  // smysl porovnavat zonu, kde original uz nekolik minut
                  // hraje a stav objektu se lisit MUSI.
                  const keep = { spawns: g.spawns, air: g.air,
                                 hazards: g.hazards, shots: g.shots,
                                 bullets: g.bullets, booms: g.booms,
                                 tokens: g.tokens, plops: g.plops,
                                 effects: g.effects, boss: g.boss,
                                 alive: g.player.alive };
                  g.spawns = []; g.air = []; g.hazards = []; g.shots = [];
                  g.bullets = []; g.booms = []; g.tokens = []; g.plops = [];
                  g.effects = []; g.boss = null; g.player.alive = false;
                  g.hudCopperPrimed = true; g.last = now; frame(now);
                  bare = canvas.toDataURL('image/png');
                  Object.assign(g, keep); g.player.alive = keep.alive;
                }
                out.push({ row, png, bare });
              }
              return { top, rows: out };
            }""", {"level": level, "rows": rows,
                   "span": span, "step": step, "bare": bare})
        finally:
            browser.close()


GRID = [(x, y) for y in range(0, 256, 3) for x in range(0, 320, 3)]


def best_row(original, level, rows, pixels, span=0, step=16):
    best = None
    for item in row_series(level, rows, span, step)["rows"]:
        frame = compare.to_vamiga(compare._decode_data_url(item["png"]))
        pct = compare.match_percent(
            original, frame, iter(pixels) if pixels else None)
        if best is None or pct > best[0]:
            best = (pct, item["row"])
    return best


def align_frame(path, level):
    original = raw_frame(path)
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from map import Disk, level_info, parse             # noqa: E402
    disk = Disk()
    pam, dico = level_info(disk, level)
    span = parse(disk.load(pam), dico)[3] + 320
    print(f"hruby sken vlastniho rozsahu urovne ({span} radku, krok 16)",
          flush=True)
    pct, row = best_row(original, level, None, GRID, span=span, step=16)
    print(f"    nejlepsi hrube: radek {row}, {pct:.1f} % na mrizce", flush=True)
    fine = list(range(row - 16, row + 17))
    pct, row = best_row(original, level, fine, GRID)
    print(f"    po zjemneni:    radek {row}, {pct:.1f} % na mrizce", flush=True)
    full = best_row(original, level, [row], None)
    print(f"    cely snimek:    radek {row}, {full[0]:.1f} %", flush=True)


def main():
    args = [a for a in sys.argv[1:]]
    if "--snimek" in args:
        i = args.index("--snimek")
        path = args[i + 1]
        level = int(args[args.index("--uroven") + 1]) if "--uroven" in args else 0
        align_frame(path, level)
        return
    window = 40
    if "--okno" in args:
        i = args.index("--okno")
        window = int(args[i + 1])
        del args[i:i + 2]
    times = [int(a) for a in args]
    if not times:
        raise SystemExit(__doc__)

    for t in times:
        original = compare.original_frame(t)
        low, high = candidates(t, window)
        print(f"t={t}: hledam {low}..{high} tiku", flush=True)
        best = None
        for item in remake_series(low, high):
            frame = compare.to_vamiga(compare._decode_data_url(item["png"]))
            pct = compare.match_percent(original, frame)
            if best is None or pct > best[0]:
                best = (pct, item["ticks"], item["row"])
        pct, ticks, row = best
        floor = round(max(0.0, round(pct - 0.05, 1) - 0.1), 1)
        print(f'    "t{t}": {{"t": {t}, "row": {row}, "floor": {floor},')
        print(f'             "ticks": {ticks}, "vblBase": {VBL_BASE},')
        fodder = "[" + ", ".join(
            '{"x": %g, "vx": %g}' % (f["x"], f["vx"]) for f in FODDER) + "]"
        print(f'             "fodder": {fodder}}},')
        print(f"    # zmerena shoda celeho snimku {pct:.1f} %", flush=True)


if __name__ == "__main__":
    main()
