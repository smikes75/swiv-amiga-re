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


# Vstup do skutecne hry pres MEGA TRAINER: F1 nekonecne zivoty, F3 ponechani
# zbrani, F4 super zbrane (wasm_key, surove kody Amigy). Overeno snimkem -
# volby se prepnou na YES. Palba se musi pulzovat; drzene PRESS_FIRE hru
# nestrili. Pozor: pulzovana palba behem continue okna hned vhodi kredit a
# resetuje skore, takze "skore = 0" neznamena, ze hrac ve hre neni.
TRAINER_KEYS = (0x50, 0x52, 0x53)          # F1, F3, F4
JOY_UP, JOY_FIRE, JOY_RELEASE_FIRE = 0, 4, 13

PLAY_PROLOGUE = """() => {
  VA.run(32*50, null); VA.fn.mouse(1,7); VA.run(4,null); VA.fn.mouse(1,16);
  VA.run(8*50, null);
  const key = c => { VA.fn.key(c,1); VA.run(6,null);
                     VA.fn.key(c,0); VA.run(6,null); };
  for (const c of %s) key(c);
  VA.run(25,null); VA.fn.mouse(1,7); VA.run(4,null); VA.fn.mouse(1,16);
  VA.run(37*50, null);
  VA.fn.joy(2,4); VA.run(4,null); VA.fn.joy(2,13); VA.run(3*50,null);
  window.playFor = sec => { for (let i = 0; i < sec*50/10; i++) {
    VA.fn.joy(2,4); VA.run(5,null); VA.fn.joy(2,13); VA.run(5,null); } };
}""" % (list(TRAINER_KEYS),)


# --- baze A6 a AMPROG.OBJ v chip RAM (zmereno 2026-09-08) ------------------
# A6 je bazovy registr globalu (fp@(N)) i skokove tabulky na zapornych
# offsetech; nastavuje jej zavadec jeste pred vstupem do AMPROG.OBJ (0xc72
# uz ho prvni instrukci pouziva), takze v disassembly neni videt.
#
# Zmereno takto: fp@(3530) je mapova pozice 16.16, kterou scroll task 0x3cd4
# snizuje presne o fp@(3526) = 0x4000 za VBL. Dva otisky chip RAM N snimku od
# sebe -> hledej longy, ktere klesly o N*0x4000, a filtruj tim, ze long tesne
# pred nimi je 0x4000. Zbyde jedina adresa; A6 = ta adresa - 3530.
# Baze AMPROG.OBJ se najde podle bajtu rutiny 0x5556 (61 00 f5 88 41 ed ...).
#
# Overeno dvema behy s ruznou delkou hry: obe daly stejne hodnoty.
A6_BASE = 0x17DC          # 6108
PROG_BASE = 0xEFC0        # 61376
FIND_A6_JS = """(frames) => {
  const H = VA.M.HEAPU8, p = VA.fn.chipPtr(), n = VA.fn.chipSize();
  const before = H.slice(p, p + n);
  VA.run(frames, null);
  const after = H.slice(p, p + n);
  const be = (a, i) => (a[i]<<24 | a[i+1]<<16 | a[i+2]<<8 | a[i+3]) >>> 0;
  const hits = [];
  for (let i = 0; i + 4 <= n; i += 2)
    if (((be(before, i) - be(after, i)) | 0) === frames * 0x4000 &&
        be(after, i - 4) === 0x4000) hits.push(i - 3530);
  return hits;
}"""
FIND_PROG_JS = """() => {
  const H = VA.M.HEAPU8, p = VA.fn.chipPtr(), n = VA.fn.chipSize();
  const sig = [0x61,0x00,0xf5,0x88,0x41,0xed,0x00,0x0c,0x29,0x48,0x00,0xa0];
  const out = [];
  outer: for (let i = 0; i + sig.length <= n; i += 2) {
    for (let k = 0; k < sig.length; k++) if (H[p+i+k] !== sig[k]) continue outer;
    out.push(i - 0x5556);
  }
  return out;
}"""


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
