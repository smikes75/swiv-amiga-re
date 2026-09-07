#!/usr/bin/env python3
"""vacmp.py - original SWIVu ve WebAssembly (vAmiga) v prohlizeci.

Prvni krok srovnavaciho harnessu: jadro z web/vamiga.js se nabootuje se
SWIVFIX.ADF a Kickstartem, projede kanonickou vstupni sekvenci (stejnou jako
tools/baseline.sh) a v zadanem case ulozi snimek. Slouzi k overeni, ze beh
v prohlizeci je totozny s VAHeadless, a pozdeji ke cteni stavu hry z chip RAM.

    python3 tools/survey/vacmp.py 17 build/x_t17.raw

Sekvence (emulovane sekundy od zapnuti, 50 snimku = 1 s):
    32  mouse1 press left      pryc z cracktra
    40  mouse1 press left      MEGA TRAINER (vychozi volby = cista hra)
    85  joystick2 press 1      fire na kreditove obrazovce
    86  joystick2 unpress 1
Harness je **deterministicky** (dva behy daji tentyz obsah chip RAM i tentyz
pocet zvukovych vzorku), ale **neni snimek po snimku shodny s VAHeadless**:
vstup jde jinou cestou a hra ma RNG michany hodnotou VHPOSR z audio
preruseni, takze se behy brzy rozejdou. Harness proto slouzi jako **vlastni
reference** (obraz, chip RAM i zvuk z jednoho behu), ne jako nahrada
tools/baseline.sh.
"""
import base64
import functools
import http.server
import os
import socketserver
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROM = ("/Users/mik/Documents/FS-UAE/Kickstarts/"
       "Kickstart v1.3 rev 34.5 (1987)(Commodore)(A500-A1000-A2000-CDTV)[!].rom")
ADF = os.path.join(ROOT, "SWIVFIX.ADF")
FPS = 50                                        # PAL

# (sekunda od zapnuti, prikaz RetroShellu)
# Vstup se posila PRIMO pres GamePadAction (wasm_mouse/wasm_joystick), ne
# prikazem RetroShellu: retezce typu "mouse1 press left" se v tomto rezimu
# neprojevily a hra zustala viset na cracktru (zmereno 2026-09-07 - snimek
# v case 25 s po "fire" porad ukazoval text cracku).
#   (sekunda od zapnuti, ('mouse'|'joy'), port, akce stisk, akce uvolneni)
SEQUENCE = [(32, "mouse", 1, 7, 16),    # pryc z cracktra
            (40, "mouse", 1, 7, 16),    # MEGA TRAINER (vychozi volby)
            (85, "joy", 2, 4, 13)]      # fire na kreditove obrazovce
ZERO_AT = 85                            # cas na radce se pocita od fire
HOLD = 4                                # snimku mezi stiskem a uvolnenim


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve(root):
    """WebAssembly se z file:// nenacte (CORS), takze web/ servirujeme lokalne."""
    handler = functools.partial(_Quiet, directory=root)
    srv = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def playSequence(page, target):
    """Odsimuluje vstupni sekvenci az do `target` sekund od zapnuti."""
    now = 0
    for sec, dev, port, down, up in SEQUENCE:
        if sec > target:
            break
        if sec > now:
            page.evaluate("n => VA.run(n, null)", (sec - now) * FPS)
            now = sec
        page.evaluate("([d, p, a]) => (d === 'mouse' ? VA.fn.mouse : VA.fn.joy)(p, a)",
                      [dev, port, down])
        page.evaluate("n => VA.run(n, null)", HOLD)
        page.evaluate("([d, p, a]) => (d === 'mouse' ? VA.fn.mouse : VA.fn.joy)(p, a)",
                      [dev, port, up])
    return now


def grab(t_after_fire, out_raw, chip=None, headless=True):
    """Vrati (raw RGB24 716x285, volitelne kopii chip RAM) v case t po fire."""
    target = ZERO_AT + t_after_fire
    srv, port = serve(os.path.join(ROOT, "web"))
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=headless)
        page = b.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append("console: " + m.text)
                if m.type == "error" else None)
        page.goto(f"http://127.0.0.1:{port}/vacmp.html")
        page.wait_for_function("window.VA && window.VA.ready", timeout=60000)
        rom = base64.b64encode(open(ROM, "rb").read()).decode()
        adf = base64.b64encode(open(ADF, "rb").read()).decode()
        err = page.evaluate("([r, a]) => VA.boot(r, a)", [rom, adf])
        if err:
            b.close(); sys.exit("boot: " + err)
        now = playSequence(page, target)
        if target > now:
            e = page.evaluate("n => VA.run(n, null)", (target - now) * FPS)
            if e:
                b.close(); sys.exit(e)
        raw = base64.b64decode(page.evaluate("() => VA.frameRGB()"))
        ram = (base64.b64decode(page.evaluate("([o, n]) => VA.chip(o, n)", list(chip)))
               if chip else None)
        frames = page.evaluate("() => VA.frames")
        b.close()
    srv.shutdown()
    if errs:
        sys.exit("chyby stranky: " + "; ".join(errs))
    open(out_raw, "wb").write(raw)
    return raw, ram, frames


if __name__ == "__main__":
    t = int(sys.argv[1]); out = os.path.abspath(sys.argv[2])
    raw, _, fr = grab(t, out)
    print(f"ok t={t} snimku={fr} bajtu={len(raw)} -> {out}")
