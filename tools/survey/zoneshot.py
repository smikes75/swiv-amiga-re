#!/usr/bin/env python3
"""zoneshot.py - snimky ORIGINALU v zonach, kam se hra sama nedostane.

`tools/baseline.sh` dojede nanejvys k prvni instalaci: `0x3cbe` scrolluje
jen pri `fp@(166) == 0` a bit 3 drzi ziva instalace (`0xb6ae`). Bez
skutecneho hrani se tovarna v DESERTu nezniici a mapa tam stoji - snimky
v case 600 i 1200 s ukazuji tutez scenu.

Tenhle skript proto pousti original v harnessu ve WebAssembly a **kazdy
snimek vynuluje `fp@(166)`**. Zamek tim prestane platit a mapa projede
celym retezem. Je to jediny zasah: mapova data, palety, Copper i blitter
delaji dal svou praci, takze pro porovnani TERENU a vykreslovani je snimek
plnohodnotny. Pro porovnani chovani objektu ne - hra bezi s trainerem
(nekonecne zivoty, super zbrane) a hrac strili.

Pozice v mape se cte z `fp@(3530)` (16.16, klesa o `0x4000` za VBL), takze
snimek lze porizovat presne na zadanem miste retezu.

    python3 tools/survey/zoneshot.py 40000 30000 20000 --out build/zone

Ke kazde pozici vznikne `<out>_p<pozice>.raw` (RGB24 716x285) a `.png`.
Radek pro `compare.py` pak najde `tools/align.py --snimek ... --uroven N`.
"""
import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import vacmp                                             # noqa: E402
from playwright.sync_api import sync_playwright          # noqa: E402

MAP_POS = 3530                       # fp@(3530): mapova pozice 16.16

# Jizda je spolecna (vacmp.DRIVE_JS: zamek instalace, zivoty, vyprosteni);
# tady jen prevod parametru {target, limit} -> {od, limit} a vysledku.
DRIVE_JS = ("(cfg) => { const r = (" + vacmp.DRIVE_JS +
            ")({ od: cfg.target, limit: cfg.limit });"
            " return { frames: r.k, pos: r.pos, ctec: r.ctec }; }")


def main():
    args = [a for a in sys.argv[1:]]
    out = "build/zone"
    if "--out" in args:
        i = args.index("--out"); out = args[i + 1]; del args[i:i + 2]
    targets = sorted((int(a) for a in args), reverse=True)
    if not targets:
        raise SystemExit(__doc__)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)

    srv, port = vacmp.serve(os.path.join(vacmp.ROOT, "web"))
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(f"http://127.0.0.1:{port}/vacmp.html")
        page.wait_for_function("window.VA && window.VA.ready", timeout=60000)
        try:
            rom = base64.b64encode(open(vacmp.ROM, "rb").read()).decode()
        except OSError as e:
            b.close(); srv.shutdown()
            sys.exit(f"Kickstart 1.3 nejde precist ({e.strerror}): {vacmp.ROM}\n"
                     f"Poloz ho do korene projektu jako kick13.rom (je v "
                     f".gitignore, stejne jako disketa), nebo nastav "
                     f"SWIV_KICKSTART=/cesta/k/rom.")
        adf = base64.b64encode(open(vacmp.ADF, "rb").read()).decode()
        err = page.evaluate("([r, a]) => VA.boot(r, a)", [rom, adf])
        if err:
            b.close(); srv.shutdown(); sys.exit("boot: " + err)
        # Trainer (nekonecne zivoty) + vstup do hry.
        vacmp.prolog(page)
        start = page.evaluate(
            "([a, o]) => VA.mem().U(a + o)",
            [vacmp.A6_BASE, MAP_POS])
        print(f"start mapove pozice: {start} (0x{start:x})", flush=True)

        for t in targets:
            r = page.evaluate(DRIVE_JS, {"target": t, "limit": 200000})
            raw = base64.b64decode(page.evaluate("() => VA.frameRGB()"))
            name = f"{out}_p{t}"
            open(name + ".raw", "wb").write(raw)
            from PIL import Image
            (Image.frombytes("RGB", (716, 285), raw)
             .crop((62, 18, 702, 274)).resize((320, 256), Image.NEAREST)
             .save(name + ".png"))
            print(f"  pozice {r['pos']:6d} (cil {t:6d}) po {r['frames']} "
                  f"snimcich -> {name}.png", flush=True)
        b.close()
    srv.shutdown()
    if errs:
        sys.exit("chyby stranky: " + "; ".join(errs))


if __name__ == "__main__":
    main()
