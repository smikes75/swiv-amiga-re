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
poloha zmenila) s toleranci jednoho kola (TOL_XY 8 px, TOL_Z 5 px:
houpani na kolech 0x883c je nahodne). Mimo TOWN je vozidlo nesmrtelne
(slot +108) a vrtulnik na obou stranach strili, aby ctecka mapy necekala
na neprately (scroll by se rozesel).

    python3 tools/jeepdiff.py            # TOWN, 400 VBL od pripojeni
    python3 tools/jeepdiff.py --od 47700 --skript pady   # RIVER: plosiny
    python3 tools/jeepdiff.py --json build/jeepdiff.json

Lod (0x8e26) je nova uloha - jeep se v 0x94c2 ukonci a zalozi ji - takze
se sleduje uloha slotu 2 podle PC: 0x8e26..0x9046 lod, 0x9090..0x9600 jeep.
Scenar `pady` drzi "nahoru" (vozidlo u horniho okraje, plosiny prijizdeji
se scrollem) a mezi plosinami zkusi zataceni; zapisuje zmeny tvaru
(jeep <-> lod). Mimo TOWN je vozidlo na obou stranach nesmrtelne (slot
+108 drzene), jinak porovnani utopi smrti na nepratelich, kteri se lisi RNG.
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
# (od, do, klavesy) v ticich od zrozeni jeepu; klavesy l r u d f j
# skok = dvojity tuk smeru (0x7222): r, pusteni, r - kazdy stav < 5 tiku
SKRIPTY = {
    "town": [(0, 60, ""), (60, 100, "r"), (100, 140, "l"), (140, 180, "u"),
             (180, 220, "d"), (220, 260, "ru"), (260, 262, "r"), (262, 264, ""),
             (264, 330, "r"), (330, 400, "")],
    # RIVER: jede vpred, u lodi zkusi zatocit, pak zase vpred az k jeep plosine
    "pady": [(0, 60, ""), (60, 1500, "u"), (1500, 1540, "ul"), (1540, 1580, "ur"),
             (1580, 3600, "u")],
}
SKRIPT = SKRIPTY["town"]
TIKU = 400


def klavesy(t):
    for od, do_, k in SKRIPT:
        if od <= t < do_:
            return set(k)
    return set()


def vstupy():
    return [sorted(klavesy(t)) for t in range(TIKU)]

ORIG_JS = """(cfg) => {
  const m = VA.mem(), A6 = cfg.a6, U = m.U, W = m.W, L = m.L;
  const SLOT2 = A6 + 11356;
  const cam = () => W(A6 + 3530);
  // Vozidlo slotu 2: +276 = slot 2 (0x717e) a PC (+270 = navratova adresa
  // yieldu) v korutine jeepu 0x9046..0x9358 nebo lodi 0x8e26..0x9046 (lod
  // je nova uloha, jeep se v 0x94c2 ukonci). +276 = slot 2 maji i deti:
  // vez 0x89e8, brazda lodi 0x9358..0x939c (0x8efa/0x8f3e pres 0x6178,
  // stoji na miste) a delo lodi 0x939c - proto ty rozsahy.
  const najdi = () => { let node = A6 - 698, g = 0;
    while (g++ < 500) { const nx = L(node + 4); if (!nx || !m.platna(nx)) return null;
      const pc = L(nx + 270) - cfg.prog;
      if (L(nx + 276) === SLOT2 && W(nx + 274) === 100) {
        if (pc >= 0x9046 && pc < 0x9358) return [nx, "jeep"];   // vc. zrozeni 0x9046
        if (pc >= 0x8e26 && pc < 0x9046) return [nx, "boat"];
      }
      node = nx; } return null; };
  if (cfg.od) {                       // dojet (se strelbou vrtulniku), pak klid
    (JIZDA)({ od: cfg.od, limit: 200000 });
    VA.fn.joy(2, 13); VA.fn.joy(2, 10); VA.run(50, null);
  } else {
    let guard = 0;
    while (m.rd(A6 + 166) !== 0 && guard++ < 3000) VA.run(4, null);
    VA.run(60, null);
  }
  // pripojeni: fire na portu 1 (jeep), pulzovane
  let voz = null, k = 0;
  while (!voz && k++ < 400) { VA.fn.joy(1, (k % 10) < 5 ? 4 : 13); VA.run(1, null); voz = najdi(); }
  VA.fn.joy(1, 13);
  if (!voz) return { chyba: "jeep se nepripojil", typ2: W(SLOT2 + 66), slot54: m.rd(SLOT2 + 54), kredity: W(A6 + 12502) };
  const out = [];
  let drz = { x: 0, y: 0, f: false, j: false };
  // Scroll 0x3cbe stoji, kdyz ctecka mapy fp@(3538) nestaci (objekty ceka-
  // jici na pamet - vrtulnik je nestrili). DRIVE_JS to resi az po 1500
  // VBL; tady se nepratele, kteri prosli a2c6 a jsou v obraze, odsouvaji
  // 600 px pod obrazovku KAZDY VBL (mimo TOWN), aby ctecka nikdy necekala
  // a cas obou stran se nerozesel (s odsunem az po 6 VBL stani se kamera
  // rozesla o 27 px). Vozidlo je nesmrtelne, nepratele se stejne lisi RNG.
  // Prepis limit pameti nema.
  const MARK = (0xa36a + cfg.prog) & 0xffff;
  let stoji = 0, posledni = cam(), vyprosteni = 0;
  const vyprosti = () => { const c = cam(); let node = A6 - 698, g = 0; const seen = new Set();
    while (g++ < 800) { const nx = L(node + 4);
      if (!nx || !m.platna(nx) || seen.has(nx)) break;
      seen.add(nx); node = nx;
      if (W(nx + 274) !== 100 || (L(nx + 534) & 0xffff) !== MARK) continue;
      if (L(nx + 276) === SLOT2 || L(nx + 276) === A6 + 11176) continue;
      // znacky mapy (plosiny 0xac6a/0xacb6, pasmo stop 0xad30) nechat:
      // odsunuta plosina by se zaregistrovala 600 px pod obrazovkou
      const pc = L(nx + 270) - cfg.prog;
      if (pc >= 0xac6a && pc < 0xad98) continue;
      const sy = W(nx + 324) - c;
      if (sy < -80 || sy > 300) continue;
      m.w16(nx + 324, (c + 600) & 0xffff); } };
  for (let t = 0; t < cfg.tiku; t++) {
    const s = new Set(cfg.vstup[t]);
    const x = s.has("l") ? -1 : s.has("r") ? 1 : 0, y = s.has("u") ? -1 : s.has("d") ? 1 : 0;
    if (x !== drz.x) VA.fn.joy(1, x < 0 ? 2 : x > 0 ? 3 : 10);
    if (y !== drz.y) VA.fn.joy(1, y < 0 ? 0 : y > 0 ? 1 : 11);
    if (s.has("f") !== drz.f) VA.fn.joy(1, s.has("f") ? 4 : 13);
    if (s.has("j") !== drz.j) VA.fn.joy(1, s.has("j") ? 5 : 14);   // druhe tlacitko
    drz = { x, y, f: s.has("f"), j: s.has("j") };
    // vrtulnik dal strili (jako DRIVE_JS): bez palby ctecka mapy ceka na
    // nepratele (0xa36a) a scroll originalu stoji i 500 VBL, prepis ne
    VA.fn.joy(2, (t % 10) < 5 ? 4 : 13);
    m.w8(A6 + 166, m.rd(A6 + 166) & ~8);
    m.w16(A6 + 11176 + 68, 0xffd8); m.w16(SLOT2 + 68, 0xffd8);    // zivoty obou slotu
    // ochrana zije ve SLOTU (0x90ce: a0 = +276 slotu, +108 = 200; 0x9306
    // cte slot+108 | slot+106), ne v uloze vozidla
    if (cfg.nesmrtelny) m.w16(SLOT2 + 108, 100);
    VA.run(1, null);
    if (cfg.nesmrtelny) { vyprosteni++; vyprosti(); }
    else if (cam() !== posledni) { posledni = cam(); stoji = 0; }
    else if (++stoji >= 6 && m.rd(A6 + 166) === 0) { stoji = 0; vyprosteni++; vyprosti(); }
    voz = najdi();
    if (!voz) { out.push(null); continue; }
    const [a, tvar] = voz;
    // 6: PC v korutine, 7: fp@(3548) predano, 8/9: plosina A/B (y),
    // 10: strop fp@(3558), 11: slot +108
    out.push([W(a + 320), W(a + 324) - cam(), W(a + 328), U(a + 358), cam(), tvar,
              L(a + 270) - cfg.prog, m.rd(A6 + 3548), W(A6 + 3552), W(A6 + 3556),
              W(A6 + 3558), W(SLOT2 + 108)]);
  }
  return { zaznam: out, kredity: W(A6 + 12502), vyprosteni };
}""".replace("(JIZDA)", "(" + vacmp.DRIVE_JS + ")")

REMAKE_JS = """(cfg) => {
  startGame(0);
  const g = state.g; g.keys = {}; g.keys2 = {}; g.lives = 99;
  if (cfg.od) {                       // jako trajdiff --od: jen bit 3 zamku
    // vrtulnik jede jako DRIVE_JS originalu: palba pulzovane 5/5 VBL a
    // kazdych 120 VBL prehozeni drzene paky vlevo/vpravo; jinak zustane
    // stat uprostred, nepratele ho ostreluji a jejich vybuchy (BOBy
    // posledniho renderu) pak blokuji sondu zrozeni 0x9046.
    let guard = 0, smer = null;
    g.ignoreInstLock = true;
    while (Math.floor(g.scroll) > cfg.od - cfg.K && guard++ < 400000) {
      if (guard % 120 === 0) smer = (guard / 120) % 2 ? "l" : "r";
      g.keys = { f: (guard % 10) < 5 };
      if (smer) g.keys[smer] = true;
      step(g); g.lives = 99;
    }
    g.keys = {};
    for (let i = 0; i < 50; i++) { step(g); g.lives = 99; }
  } else for (let i = 0; i < 60; i++) step(g);
  g.keys2.f = true; step(g); g.keys2.f = false;
  const j = g.player2;
  if (!j) return { chyba: "jeep se nepripojil" };
  // Sonda 0x9046 zavisi na BOBech pod ni (nepratele se lisi RNG); kdyz se
  // zrozeni lisi od originalu, prepis se prenese na jeho misto, aby se
  // porovnavala jizda ze stejneho bodu. Sonda sama je overena v TOWN.
  let preneseno = null;
  if (cfg.zrozeni && (Math.round(j.x) !== cfg.zrozeni[0] || Math.round(j.y) !== cfg.zrozeni[1])) {
    preneseno = [Math.round(j.x), Math.round(j.y)];
    j.x = cfg.zrozeni[0]; j.y = cfg.zrozeni[1]; j.weaponX = j.x; j.weaponY = j.y;
  }
  const zaz = p => p && p.alive ? [Math.round(p.x), Math.round(p.y), +(p.z || 0).toFixed(2), p.turret | 0, Math.round(scrollTop(g)), p.form,
    0, g.padHandoff ? 255 : 0, g.padA ? g.padA.y : 0, g.padB ? g.padB.y : 0,
    Number.isFinite(g.jeepFloorY) ? g.jeepFloorY : 0, p.inv | 0] : null;
  // sonda zrozeni 0x9046 po sloupcich: ktere body (160, 192..104) blokuje teren a ktere BOBy
  const bobs = respawnBobField(g, null), sonda = [];
  for (let y = 192; y >= 104; y -= 8)
    sonda.push([y, heliTerrainBlocked(g, 160, y) ? 1 : 0, heliBobBlocked(g, 160, y, bobs) ? 1 : 0]);
  const out = [zaz(j)];
  for (let t = 1; t < cfg.tiku; t++) {
    g.keys = { f: (t % 10) < 5 };   // vrtulnik strili jako v originale
    g.keys2 = {};
    for (const k of cfg.vstup[t]) g.keys2[k] = true;
    if (cfg.nesmrtelny && g.player2) g.player2.inv = Math.max(g.player2.inv | 0, 100);
    step(g); g.jeepLives = 99; g.lives = 99;
    out.push(zaz(g.player2));
  }
  return { zaznam: out, sonda, preneseno };
}"""


def original(od):
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
                                          "tiku": TIKU, "vstup": vstupy(), "od": od,
                                          "nesmrtelny": bool(od)})
            br.close()
    finally:
        srv.shutdown()
    return res


def remake(od, zrozeni=None):
    with sync_playwright() as pw:
        b = pw.chromium.launch(); p = b.new_page()
        p.goto("file://" + os.path.join(ROOT, "game.html"))
        p.set_input_files("#fpick", os.path.join(ROOT, "SWIVFIX.ADF"))
        p.wait_for_selector("#titlewrap", state="visible")
        p.evaluate("window.requestAnimationFrame = () => 0")
        res = p.evaluate(REMAKE_JS, {"tiku": TIKU, "vstup": vstupy(), "od": od, "K": K,
                                     "nesmrtelny": bool(od), "zrozeni": zrozeni})
        b.close()
    return res


def udalosti(z):
    """Zmeny tvaru (jeep/lod) a smrti/zrozeni v zaznamu: [(tik, co, x, y)].
    Zmena plati, az kdyz novy stav drzi aspon 3 tiky (PC ulohy pri
    predani plosiny na chvili prochazi sdilenym kodem)."""
    out, prev, kand, od = [], None, None, 0
    for t, a in enumerate(z):
        tvar = a[5] if a else None
        if tvar != kand:
            kand, od = tvar, t
        if kand != prev and t - od >= 2:
            b = z[t]                  # z[od] muze byt smeti (nova uloha pred 0x9046)
            out.append((od, kand or "smrt", b[0] if b else None, b[1] if b else None))
            prev = kand
    return out


TOL_XY = 8     # dve kola po max. 4 px (lod ve skoku); planovac 0x62d2 hybe
TOL_Z = 5      # vozidlem jen jednou za kolo, prepis kazdy VBL
               # z: houpani na kolech je nahodne 0x883c (vrchol az 4,5 px)


def porovnej(o, r):
    """Original hybe vozidlem jen jednou za kolo planovace (2 a vice VBL),
    prepis kazdy VBL; porovnavaji se proto tiky, kdy original vozidlem
    pohnul (x, mapove y nebo z), s toleranci jednoho kola (TOL_XY/TOL_Z).
    Vypise prvni rozchod mimo toleranci v kazde fazi skriptu."""
    vst = vstupy()
    uo, ur = udalosti(o), udalosti(r)
    print("\nudalosti (tik, tvar, x, y): original", uo)
    print("                             prepis  ", ur)
    print("\n%-6s %-10s %-22s %-22s %s" % ("tik", "vstup", "original x,y,z", "prepis x,y,z", "rozdil"))
    faze_hlasena = set()
    spatne = tesne = kol = 0
    prev = None
    for t in range(TIKU):
        a, b = o[t], r[t]
        if a is None or b is None:
            if a is None and b is None:
                continue
            spatne += 1; prev = a; continue
        klic = (a[0], a[1] + a[4], a[2])
        zmena = prev is None or klic != prev
        prev = klic
        if not zmena:
            continue
        kol += 1
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        faze = next(i for i, (od, do_, _) in enumerate(SKRIPT) if od <= t < do_)
        if abs(dx) > TOL_XY or abs(dy) > TOL_XY or abs(dz) > TOL_Z or a[5] != b[5]:
            spatne += 1
            if faze not in faze_hlasena:
                faze_hlasena.add(faze)
                print("%-6d %-10s %-22s %-22s dx %+d dy %+d dz %+.1f %s" %
                      (t, "".join(vst[t]) or "-", a[:3], b[:3], dx, dy, dz,
                       "" if a[5] == b[5] else "tvar %s/%s" % (a[5], b[5])))
        elif abs(dx) > 1 or abs(dy) > 1 or abs(dz) > 1.5:
            tesne += 1
    # rozchod kamery: odchylka (cam originalu - scroll prepisu) od stavu
    # pri zrozeni, po slovech (cam je 16bit word)
    rozdil = [((a[4] - b[4]) + 32768) % 65536 - 32768 for a, b in zip(o, r) if a and b]
    kam = max((abs(d - rozdil[0]) for d in rozdil), default=0)
    print("\nkol originalu %d, z toho v toleranci kola %d, mimo %d; "
          "kamera se rozesla nejvyse o %d px" % (kol, tesne, spatne, kam))
    return spatne


def main():
    global SKRIPT, TIKU
    out = None
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
    od = int(sys.argv[sys.argv.index("--od") + 1]) if "--od" in sys.argv else 0
    if "--skript" in sys.argv:
        SKRIPT = SKRIPTY[sys.argv[sys.argv.index("--skript") + 1]]
    TIKU = SKRIPT[-1][1]
    print("original (harness vAmiga): jeep %s, %d VBL od zrozeni ..." %
          ("od pozice %d" % od if od else "v TOWN", TIKU), flush=True)
    o = original(od)
    if "chyba" in o:
        sys.exit("original: %s (%s)" % (o["chyba"], o))
    print("prepis ...", flush=True)
    r = remake(od, o["zaznam"][0][:2] if od else None)
    if "chyba" in r:
        sys.exit("prepis: " + r["chyba"])
    if out:
        json.dump({"skript": SKRIPT, "original": o, "prepis": r}, open(out, "w"))
    oz, rz = o["zaznam"], r["zaznam"]
    print("zrozeni: original", oz[0][:6], "prepis", rz[0][:6])
    if r.get("preneseno"):
        print("sonda zrozeni prepisu dala %s (BOB nepritele pod sondou, RNG); "
              "prepis prenesen na zrozeni originalu" % (r["preneseno"],))
        print("  sonda (y, teren, BOBy):", r["sonda"])
    kola = sum(1 for t in range(1, TIKU) if oz[t] and oz[t-1] and oz[t][:3] != oz[t-1][:3])
    print("original: poloha se zmenila v %d ticich z %d, vyprosteni scrollu %d" % (kola, TIKU, o.get("vyprosteni", 0)))
    spatne = porovnej(oz, rz)
    print("\nJEEPDIFF OK" if not spatne else "\nJEEPDIFF: %d rozdilu" % spatne)
    sys.exit(1 if spatne else 0)


if __name__ == "__main__":
    main()
