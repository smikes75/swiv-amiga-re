#!/usr/bin/env python3
"""Jeep (slot 2) proti originalu: stejna sekvence vstupu, poloha po VBL.

Vrtulnik ma drahy overene trajdiffem a snimky; jeep byl do 2026-09-30
prepsany jen z disassembly (docs/PLAN-JEEP.md). Tenhle skript ho ridi
STEJNYM skriptem vstupu na obou stranach a po kazdem VBL zapise x, y na
obrazovce a vysku z (skok).

Original (harness vAmiga): slot 2 ma vychozi ovladac klavesnici (typ 2);
na obrazovce pred startem prepne F6 (raw 0x55) slot 2 na joystick v portu 1
(0x2110, tabulka 0x2152). Pripojeni = fire na portu 1 (0x7090 -> 0x7156
zalozi ulohu 0x9090 a do jejiho +276 ulozi ukazatel na slot fp@(11356);
totez ma i vez 0x89e8, proto se telo pozna jeste podle PC v 0x9090..0x9600).
Skok z joysticku je dvojity tuk smeru (0x7222 -> bit 6 -> 0x91e8).
Prepis: g.keys2 (l/r/u/d/f/j), player2.

Poloha originalu se obnovuje jednou za kolo planovace (2 az 5 VBL),
prepis kazdy tik; porovnava se proto po kolech originalu (tik, kdy se
poloha zmenila) s toleranci 1 px.

    python3 tools/jeepdiff.py            # TOWN, 400 VBL od pripojeni
    python3 tools/jeepdiff.py --json build/jeepdiff.json
"""
import base64
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "survey"))
import vacmp                                        # noqa: E402
from playwright.sync_api import sync_playwright     # noqa: E402

TIKU = 400
# (od, do, klavesy) v ticich od zrozeni jeepu; klavesy l r u d f j
# skok = dvojity tuk smeru (0x7222): r, pusteni, r - kazdy stav < 5 tiku
SKRIPT = [(0, 60, ""), (60, 100, "r"), (100, 140, "l"), (140, 180, "u"),
          (180, 220, "d"), (220, 260, "ru"), (260, 262, "r"), (262, 264, ""),
          (264, 330, "r"), (330, 400, "")]


def klavesy(t):
    for od, do_, k in SKRIPT:
        if od <= t < do_:
            return set(k)
    return set()


VSTUP = [sorted(klavesy(t)) for t in range(TIKU)]

ORIG_JS = """(cfg) => {
  const m = VA.mem(), A6 = cfg.a6, U = m.U, W = m.W, L = m.L;
  const SLOT2 = A6 + 11356;
  const cam = () => W(A6 + 3530);
  // Telo jeepu: +276 = slot 2 (0x717e) a PC v korutine 0x9090..0x9600.
  // Vez 0x89e8 ma +276 = slot 2 taky (0x9104) a sedi 8 px pod telem.
  const najdi = () => { let node = A6 - 698, g = 0;
    while (g++ < 500) { const nx = L(node + 4); if (!nx || !m.platna(nx)) return 0;
      const pc = L(nx + 270) - cfg.prog;
      if (L(nx + 276) === SLOT2 && W(nx + 274) === 100 && pc >= 0x9090 && pc < 0x9600) return nx;
      node = nx; } return 0; };
  let guard = 0;
  while (m.rd(A6 + 166) !== 0 && guard++ < 3000) VA.run(4, null);
  VA.run(60, null);
  // pripojeni: fire na portu 1 (jeep), pulzovane
  let jeep = 0, k = 0;
  while (!jeep && k++ < 400) { VA.fn.joy(1, (k % 10) < 5 ? 4 : 13); VA.run(1, null); jeep = najdi(); }
  VA.fn.joy(1, 13);
  if (!jeep) return { chyba: "jeep se nepripojil", typ2: W(SLOT2 + 66), slot54: m.rd(SLOT2 + 54), kredity: W(A6 + 12502) };
  const out = [];
  let drz = { x: 0, y: 0, f: false, j: false };
  for (let t = 0; t < cfg.tiku; t++) {
    const s = new Set(cfg.vstup[t]);
    const x = s.has("l") ? -1 : s.has("r") ? 1 : 0, y = s.has("u") ? -1 : s.has("d") ? 1 : 0;
    if (x !== drz.x) VA.fn.joy(1, x < 0 ? 2 : x > 0 ? 3 : 10);
    if (y !== drz.y) VA.fn.joy(1, y < 0 ? 0 : y > 0 ? 1 : 11);
    if (s.has("f") !== drz.f) VA.fn.joy(1, s.has("f") ? 4 : 13);
    if (s.has("j") !== drz.j) VA.fn.joy(1, s.has("j") ? 5 : 14);   // druhe tlacitko
    drz = { x, y, f: s.has("f"), j: s.has("j") };
    m.w8(A6 + 166, m.rd(A6 + 166) & ~8);
    VA.run(1, null);
    if (!najdi()) { out.push(null); continue; }
    out.push([W(jeep + 320), W(jeep + 324) - cam(), W(jeep + 328), U(jeep + 358), cam()]);
  }
  return { zaznam: out, kredity: W(A6 + 12502) };
}"""

REMAKE_JS = """(cfg) => {
  startGame(0);
  const g = state.g; g.keys = {}; g.keys2 = {}; g.lives = 99;
  for (let i = 0; i < 60; i++) step(g);
  g.keys2.f = true; step(g); g.keys2.f = false;
  const j = g.player2;
  if (!j) return { chyba: "jeep se nepripojil" };
  const out = [[Math.round(j.x), Math.round(j.y), +(j.z || 0).toFixed(2), j.dir | 0]];
  for (let t = 1; t < cfg.tiku; t++) {
    g.keys2 = {};
    for (const k of cfg.vstup[t]) g.keys2[k] = true;
    step(g); g.jeepLives = 99;
    const p = g.player2;
    out.push(p ? [Math.round(p.x), Math.round(p.y), +(p.z || 0).toFixed(2), p.dir | 0] : null);
  }
  return { zaznam: out };
}"""


def original():
    srv, port = vacmp.serve(os.path.join(ROOT, "web"))
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(); page = br.new_page()
            page.set_default_timeout(1_800_000)
            page.goto(f"http://127.0.0.1:{port}/vacmp.html")
            page.wait_for_function("window.VA && window.VA.ready", timeout=60000)
            page.evaluate("([r, a]) => VA.boot(r, a)", [
                base64.b64encode(open(vacmp.ROM, "rb").read()).decode(),
                base64.b64encode(open(vacmp.ADF, "rb").read()).decode()])
            # F6 = slot 2 na joystick v portu 1. Vyber se ujme jen ve smycce
            # obrazovky "select controls" (0x1fde), ktera se v attractu
            # strida s jinymi, proto se F6 tiskne kazdych 5 s (po traineru,
            # aby mu nepreplo volbu).
            prolog = vacmp.PLAY_PROLOGUE.replace(
                "VA.run(37*50, null);",
                "for (let i = 0; i < 7; i++) { VA.run(5*50, null); key(0x55); }"
                " VA.run(2*50 - 7*12, null);")
            page.evaluate(prolog)
            vacmp.rozvrzeni(page)
            res = page.evaluate(ORIG_JS, {"a6": vacmp.A6_BASE, "prog": vacmp.PROG_BASE,
                                          "tiku": TIKU, "vstup": VSTUP})
            br.close()
    finally:
        srv.shutdown()
    return res


def remake():
    with sync_playwright() as pw:
        b = pw.chromium.launch(); p = b.new_page()
        p.goto("file://" + os.path.join(ROOT, "game.html"))
        p.set_input_files("#fpick", os.path.join(ROOT, "SWIVFIX.ADF"))
        p.wait_for_selector("#titlewrap", state="visible")
        p.evaluate("window.requestAnimationFrame = () => 0")
        res = p.evaluate(REMAKE_JS, {"tiku": TIKU, "vstup": VSTUP})
        b.close()
    return res


def porovnej(o, r):
    """Original se hybe po kolech: porovnavaji se tiky, kdy se jeho poloha
    zmenila (a prvni), s toleranci 1 px; vypise prvni rozchod v kazde fazi."""
    print("\n%-6s %-10s %-22s %-22s %s" % ("tik", "vstup", "original x,y,z", "prepis x,y,z", "rozdil"))
    faze_hlasena = set()
    spatne = 0
    prev = None
    for t in range(TIKU):
        a, b = o[t], r[t]
        if a is None or b is None:
            if a is None and b is None:
                continue
            print("%-6d %-10s %-22s %-22s %s" % (t, "".join(VSTUP[t]), a, b, "jen jedna strana"))
            spatne += 1; prev = a; continue
        zmena = prev is None or a[:3] != prev[:3]
        prev = a
        if not zmena:
            continue
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        faze = next(i for i, (od, do_, _) in enumerate(SKRIPT) if od <= t < do_)
        if abs(dx) > 1 or abs(dy) > 1 or abs(dz) > 1.5:
            spatne += 1
            if faze not in faze_hlasena:
                faze_hlasena.add(faze)
                print("%-6d %-10s %-22s %-22s dx %+d dy %+d dz %+.1f" %
                      (t, "".join(VSTUP[t]) or "-", a[:3], b[:3], dx, dy, dz))
    return spatne


def main():
    out = None
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
    print("original (harness vAmiga): jeep v TOWN, %d VBL od zrozeni ..." % TIKU, flush=True)
    o = original()
    if "chyba" in o:
        sys.exit("original: %s (%s)" % (o["chyba"], o))
    print("prepis ...", flush=True)
    r = remake()
    if "chyba" in r:
        sys.exit("prepis: " + r["chyba"])
    if out:
        json.dump({"skript": SKRIPT, "original": o, "prepis": r}, open(out, "w"))
    oz, rz = o["zaznam"], r["zaznam"]
    print("zrozeni: original", oz[0], "prepis", rz[0])
    kola = sum(1 for t in range(1, TIKU) if oz[t] and oz[t-1] and oz[t][:3] != oz[t-1][:3])
    print("original: poloha se zmenila v %d ticich z %d" % (kola, TIKU))
    spatne = porovnej(oz, rz)
    print("\nJEEPDIFF OK" if not spatne else "\nJEEPDIFF: %d rozdilu" % spatne)
    sys.exit(1 if spatne else 0)


if __name__ == "__main__":
    main()
