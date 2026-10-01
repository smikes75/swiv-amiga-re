#!/usr/bin/env python3
"""Navadena strela (0x8530/0x8566) proti originalu: kdy a o kolik zataci.

Original (harness vAmiga): po dojeti na pozici (DRIVE_JS) vrtulnik stoji,
je nesmrtelny (slot +108) a kazdy VBL se ctou ulohy s PC v 0x8566..0x85f0
(korutina strely): x, y na obrazovce, uhel +358, cil +276 (slot 1/2),
+397 bit 0 (kresleni za popredim, dedi se z nosice 0x626a), obtiznost
fp@(182) a rank slotu 1 (+110).

Prepis: startGame(0), stejna jizda, vrtulnik stoji a je nesmrtelny;
obtiznost se kazdy tik PRIPNE na hodnotu originalu (jako v trajdiff),
aby se merila logika strely, ne rozjezd obtiznosti - ten se hlasi zvlast
z ranku (D = ((rank >> 8) >> 3) pro jednoho hrace se zbrani 1).

Strely se paruji podle tiku zrozeni a mista; u kazde dvojice se porovna
rozvrh zatacek (tik od zrozeni, zmena uhlu), delka zivota a bit popredi.

    python3 tools/homingdiff.py --od 58400 --tiku 6000     # TOWN, POPUPy
    python3 tools/homingdiff.py --od 58400 --json build/homingdiff.json
"""
import base64
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "survey"))
import vacmp  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

K = 32826               # radek retezu prepisu = mapova pozice - K

ORIG_JS = """(cfg) => {
  const m = VA.mem(), A6 = cfg.a6, U = m.U, W = m.W, L = m.L;
  const SLOT1 = A6 + 11176, SLOT2 = A6 + 11356;
  const cam = () => W(A6 + 3530);
  if (cfg.od) {
    (JIZDA)({ od: cfg.od, limit: 200000 });
    VA.fn.joy(2, 13); VA.fn.joy(2, 10); VA.run(50, null);
  } else {
    let guard = 0;
    while (m.rd(A6 + 166) !== 0 && guard++ < 3000) VA.run(4, null);
    VA.run(60, null);
  }
  const out = [];
  let znam = new Map();
  for (let t = 0; t < cfg.tiku; t++) {
    m.w8(A6 + 166, m.rd(A6 + 166) & ~8);
    m.w16(SLOT1 + 68, 0xffd8);
    m.w16(SLOT1 + 108, 100);                 // nesmrtelny (0x9306 cte slot)
    VA.run(1, null);
    // Seznam uloh je kruhovy - projit jednou (seen). +270 je navratova
    // adresa yieldu jen ve fazi rovneho letu (0x85b6); v korekcni smycce
    // tam lezi vrchol zasobniku s citacem, takze strela se pozna podle
    // PC jen pri zrozeni a dal se SLEDUJE PODLE ADRESY, dokud nezmizi
    // (nebo se adresa nepouzije pro novou strelu: PC zrozeni + skok).
    const strely = [], ulohy = [], seen = new Set();
    let node = A6 - 698, g = 0;
    while (g++ < 800) { const nx = L(node + 4); if (!nx || !m.platna(nx) || seen.has(nx)) break;
      seen.add(nx); node = nx;
      if (W(nx + 274) !== 100) continue;
      const pc = L(nx + 270) - cfg.prog, x = W(nx + 320), y = W(nx + 324) - cam();
      const zrozeni = pc >= 0x8566 && pc <= 0x85b6, stara = znam.get(nx);
      const nova = zrozeni && (!stara || Math.abs(stara[0] - x) > 24 || Math.abs(stara[1] - y) > 24);
      if (nova || stara) {
        const cil = L(nx + 276);
        strely.push([nova ? nx + "/" + t : stara[2], x, y, U(nx + 358),
                     cil === SLOT1 ? 1 : cil === SLOT2 ? 2 : 0,
                     m.rd(nx + 397) & 1, m.rd(nx + 367), pc, nova ? 1 : 0]);
        znam.set(nx, [x, y, nova ? nx + "/" + t : stara[2]]);
      } else ulohy.push([nx, x, y, pc]);
    }
    for (const a of [...znam.keys()]) if (!seen.has(a) || !strely.some(s => znam.get(a) && s[0] === znam.get(a)[2])) znam.delete(a);
    // nosice: pri zrozeni strely ulohy do 24 px od ni (PC = rutina nosice)
    const nove = strely.filter(s => s[8]).map(s => [s[1], s[2],
      ulohy.filter(u => Math.abs(u[1] - s[1]) <= 24 && Math.abs(u[2] - s[2]) <= 24).map(u => [u[1], u[2], u[3]])]);
    out.push({ cam: cam(), D: W(A6 + 182), rank: W(SLOT1 + 110),
               heli: [W(SLOT1 + 70), W(SLOT1 + 72) - cam()], strely, nosice: nove });
  }
  return { zaznam: out };
}""".replace("(JIZDA)", "(" + vacmp.DRIVE_JS + ")")

REMAKE_JS = """(cfg) => {
  startGame(0);
  const g = state.g; g.keys = {}; g.keys2 = {}; g.lives = 99;
  if (cfg.od) {
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
  const out = [];
  let znam = new Set();
  // vrtulnik tam, kde stoji v originale (nosice, napr. boss 0xc882, ho
  // sleduji a odtud pali - jinak by strely vznikaly jinde)
  if (cfg.heli) { g.player.x = cfg.heli[0]; g.player.y = cfg.heli[1]; g.player.weaponX = g.player.x; g.player.weaponY = g.player.y; }
  // obtiznost pripnuta na original (tik po tiku), jako trajdiff
  window.updateDifficulty = gg => { gg.difficulty = cfg.D[Math.min(out.length, cfg.D.length - 1)]; };
  for (let t = 0; t < cfg.tiku; t++) {
    if (g.player) g.player.inv = Math.max(g.player.inv | 0, 100);
    step(g); g.lives = 99;
    const strely = (g.shots || []).filter(s => s.kind === "hom").map(s =>
      [s.bobOrdinal, Math.round(s.x), Math.round(s.y), s.ang & 255, s.corr | 0, s.lead | 0, s.groundBit ? 1 : 0]);
    const st = scrollTop(g);
    const nove = strely.filter(s => !znam.has(s[0])).map(s => [s[1], s[2],
      (g.spawns || []).filter(o => o.born && o.alive && Math.abs(o.x - s[1]) <= 24 && Math.abs(o.y - st - s[2]) <= 24)
        .map(o => [Math.round(o.x), Math.round(o.y - st), o.beh])]);
    znam = new Set(strely.map(s => s[0]));
    out.push({ cam: Math.round(scrollTop(g)), D: g.difficulty | 0, rank: g.player.rank | 0,
               heli: [Math.round(g.player.x), Math.round(g.player.y)], strely, nosice: nove });
  }
  return { zaznam: out };
}"""


def original(od, tiku):
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
            vacmp.prolog(page)
            res = page.evaluate(ORIG_JS, {"a6": vacmp.A6_BASE, "prog": vacmp.PROG_BASE,
                                          "tiku": tiku, "od": od})
            br.close()
    finally:
        srv.shutdown()
    return res


def remake(od, tiku, D, heli=None):
    with sync_playwright() as pw:
        b = pw.chromium.launch(); p = b.new_page()
        p.goto("file://" + os.path.join(ROOT, "game.html"))
        p.set_input_files("#fpick", os.path.join(ROOT, "SWIVFIX.ADF"))
        p.wait_for_selector("#titlewrap", state="visible")
        p.evaluate("window.requestAnimationFrame = () => 0")
        res = p.evaluate(REMAKE_JS, {"tiku": tiku, "od": od, "K": K, "D": D, "heli": heli})
        b.close()
    return res


def strely(zaznam):
    """Slozi drahy strel: {klic: [(tik, x, y, uhel, ...), ...]}.
    Klic = (tik zrozeni, adresa/ordinal); adresa ulohy se po smrti muze
    pouzit znovu, proto se nova draha zaklada, kdyz zaznam v minulem
    tiku chybel."""
    out, ziva = {}, {}
    for t, z in enumerate(zaznam):
        videne = set()
        for s in z["strely"]:
            ident = s[0]
            if ident in videne:
                continue
            videne.add(ident)
            if ident not in ziva:
                ziva[ident] = (t, str(ident))
                out[ziva[ident]] = []
            out[ziva[ident]].append((t,) + tuple(s[1:]))
        for ident in list(ziva):
            if ident not in videne:
                del ziva[ident]
    return out


def zatacky(draha):
    """[(tik od zrozeni, zmena uhlu)] - kazda zmena +358."""
    out, t0, prev = [], draha[0][0], draha[0][3]
    for z in draha[1:]:
        if z[3] != prev:
            d = ((z[3] - prev + 128) & 255) - 128
            out.append((z[0] - t0, d))
            prev = z[3]
    return out


def porovnej(o, r):
    so, sr = strely(o["zaznam"]), strely(r["zaznam"])
    print("strel: original %d, prepis %d" % (len(so), len(sr)))
    for jm, z in (("original", o), ("prepis", r)):
        nos = [(t, n) for t, zz in enumerate(z["zaznam"]) for n in zz.get("nosice", [])]
        print("nosice %s (tik, strela x,y, ulohy do 24 px [x, y, pc/beh]):" % jm)
        for t, n in nos[:24]:
            print("   %5d  %3d,%3d  %s" % (t, n[0], n[1], [(u[0], u[1], ("%x" % u[2]) if isinstance(u[2], int) else u[2]) for u in n[2]]))
    volne = dict(sr)
    pary, bez = [], []
    for ko, do in sorted(so.items()):
        t0, x0, y0, a0 = do[0][0], do[0][1], do[0][2], do[0][3]
        nej = None
        for kr, dr in volne.items():
            t1, x1, y1, a1 = dr[0][0], dr[0][1], dr[0][2], dr[0][3]
            cena = abs(t1 - t0) + abs(x1 - x0) + abs(y1 - y0)
            if abs(t1 - t0) <= 6 and abs(x1 - x0) <= 12 and abs(y1 - y0) <= 12 and (nej is None or cena < nej[0]):
                nej = (cena, kr)
        if nej:
            pary.append((ko, nej[1])); del volne[nej[1]]
        else:
            bez.append(ko)
    print("sparovano %d, bez paru v prepisu %d, navic v prepisu %d\n" % (len(pary), len(bez), len(volne)))
    print("%-5s %-14s %-4s %-5s %-5s %-6s  %s" % ("tik", "zrozeni x,y,uh", "cil", "zivot", "zivot", "pop.", "zatacky (tik od zrozeni: zmena uhlu)"))
    print("%-5s %-14s %-4s %-5s %-5s %-6s  %s" % ("", "", "", "orig", "prep", "o/p", "original | prepis"))
    shodne = 0
    for ko, kr in pary:
        do, dr = so[ko], sr[kr]
        zo, zr = zatacky(do), zatacky(dr)
        # lod/PLOP: original ma navic prvni tik(y) bez zmeny; sedi, kdyz
        # tik kazde zatacky lezi do 3 VBL a zmena uhlu do 2 jednotek
        sedi = len(zo) == len(zr) and all(abs(a[0] - b[0]) <= 3 and abs(a[1] - b[1]) <= 2 for a, b in zip(zo, zr))
        shodne += sedi
        fmt = lambda z: " ".join("%d:%+d" % p for p in z) or "-"
        print("%-5d %-14s %-4s %-5d %-5d %d/%d    %s | %s%s" % (
            do[0][0], "%d,%d,%d" % (do[0][1], do[0][2], do[0][3]),
            "s%d" % do[0][4], len(do), len(dr), do[0][5], dr[0][6],
            fmt(zo), fmt(zr), "" if sedi else "   <-- ROZDIL"))
    for ko in bez:
        do = so[ko]
        print("%-5d %-14s %-4s %-5d %-5s        %s | (chybi v prepisu)" % (
            do[0][0], "%d,%d,%d" % (do[0][1], do[0][2], do[0][3]), "s%d" % do[0][4], len(do), "-", " ".join("%d:%+d" % p for p in zatacky(do))))
    for kr, dr in volne.items():
        print("%-5d %-14s %-4s %-5s %-5d        (chybi v originale) | %s" % (
            dr[0][0], "%d,%d,%d" % (dr[0][1], dr[0][2], dr[0][3]), "-", "-", len(dr), " ".join("%d:%+d" % p for p in zatacky(dr))))
    # rozjezd obtiznosti: original fp@(182) vs prepis z ranku
    zo = [(t, z["D"]) for t, z in enumerate(o["zaznam"])]
    zmeny_o = [(t, d) for i, (t, d) in enumerate(zo) if i == 0 or d != zo[i - 1][1]]
    zr = [(t, ((((z["rank"] & 0xffff) ^ 0x8000) - 0x8000) >> 8) >> 3) for t, z in enumerate(r["zaznam"])]
    zmeny_r = [(t, d) for i, (t, d) in enumerate(zr) if i == 0 or d != zr[i - 1][1]]
    print("\nobtiznost fp@(182) originalu (tik: D):", zmeny_o[:12])
    print("obtiznost prepisu z ranku (tik: D):   ", zmeny_r[:12],
          "  rank orig/prepis na konci: %d / %d" % (o["zaznam"][-1]["rank"], r["zaznam"][-1]["rank"]))
    print("vrtulnik: original %s, prepis %s" % (o["zaznam"][-1]["heli"], r["zaznam"][-1]["heli"]))
    print("\nHOMINGDIFF %s: %d z %d sparovanych strel se stejnym rozvrhem zatacek" % (
        "OK" if shodne == len(pary) and not bez and not volne else "ROZDILY", shodne, len(pary)))
    return shodne == len(pary) and not bez and not volne


def main():
    out = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
    od = int(sys.argv[sys.argv.index("--od") + 1]) if "--od" in sys.argv else 0
    tiku = int(sys.argv[sys.argv.index("--tiku") + 1]) if "--tiku" in sys.argv else 6000
    print("original (harness vAmiga): %s, %d VBL ..." % ("od pozice %d" % od if od else "TOWN od zacatku", tiku), flush=True)
    o = original(od, tiku)
    print("prepis (obtiznost pripnuta na original) ...", flush=True)
    r = remake(od, tiku, [z["D"] for z in o["zaznam"]], o["zaznam"][0]["heli"])
    if out:
        json.dump({"original": o, "prepis": r}, open(out, "w"))
    ok = porovnej(o, r)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
