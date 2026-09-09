#!/usr/bin/env python3
"""Ctvrty kontrakt: porovnani ZIVYCH OBJEKTU originalu a prepisu.

Dosud se prepis overoval ctyrmi obrazkovymi checkpointy v TOWN
(tools/compare.py). Tenhle skript porovnava obsah: v pevnych bodech
mapy vytahne z obou stran seznam zivych objektu a spari je.

Original (harness vAmiga, tools/survey/vacmp.py + tasks_live.py):
  - fronta uloh: hlava A6-698, dalsi prvek na +4, priorita na +274
  - +368 gfx (a2c6 d0), +320 x, +324 y, +360 hp, +504 trida
  - +534 rozlisi, jestli uloha uz prosla a2c6 (jinak jsou pole smeti)
Prepis (game.html): g.spawns / g.air / g.hazards se stejnymi poli.

**Synchronizace pres ujety scroll, ne pres cas.** Obe strany scrolluji
0.25 px/VBL, ale start hry je jinde: original drzi zamek fp@(166) nekolik
set VBL, nez postavi terenni pruhy. Nulovym bodem je proto kamera v
okamziku, kdy se zamek uvolni; kontrolni bod je "ujeto D pixelu".

Parovani: gfx + poloha na obrazovce (x, y - kamera), tolerance TOL px.

    python3 tools/objdiff.py            # vsechny kontrolni body
    python3 tools/objdiff.py 500 1000   # vlastni vzdalenosti
"""
import base64
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "survey"))
import vacmp                                        # noqa: E402
from playwright.sync_api import sync_playwright     # noqa: E402

CHECKPOINTS = (300, 600, 900, 1200, 1500)   # ujete pixely mapy
TOL = 3                                     # tolerance polohy pri parovani
MARK = (0xa36a + vacmp.PROG_BASE) & 0xffff

ORIG_JS = """(cfg) => {
  const H = VA.M.HEAPU8, p = VA.fn.chipPtr(), n = VA.fn.chipSize();
  const L = a => (H[p+a]<<24|H[p+a+1]<<16|H[p+a+2]<<8|H[p+a+3])>>>0;
  const W = a => { const v = (H[p+a]<<8)|H[p+a+1]; return v > 0x7fff ? v-0x10000 : v; };
  const U = a => (H[p+a]<<8)|H[p+a+1];
  const cam = () => { let hi = L(cfg.a6 + 3530) >>> 16;
                      return hi > 0x7fff ? hi - 0x10000 : hi; };
  // rozjezd: drz palbu pulzovane a cekej, az se uvolni zamek scrollu
  let guard = 0;
  while (H[p + cfg.a6 + 166] !== 0 && guard++ < 3000) {
    VA.fn.joy(2, 4); VA.run(2, null); VA.fn.joy(2, 13); VA.run(2, null);
  }
  const zero = cam();
  const out = [];
  for (const dist of cfg.points) {
    let g2 = 0;
    while (zero - cam() < dist && g2++ < 20000) {
      VA.fn.joy(2, 4); VA.run(2, null); VA.fn.joy(2, 13); VA.run(2, null);
    }
    const c = cam(), tasks = [];
    let node = cfg.a6 - 698, g3 = 0;
    while (g3++ < 500) {
      const nx = L(node + 4);
      if (!nx || nx >= n || tasks.some(t => t.adr === nx)) break;
      if (W(nx + 274) === 100 && (L(nx + 534) & 0xffff) === cfg.mark)
        tasks.push({ adr: nx, gfx: U(nx + 368), x: W(nx + 320),
                     ys: W(nx + 324) - c, z: W(nx + 328),
                     hp: W(nx + 360), cls: U(nx + 504) });
      node = nx;
    }
    out.push({ dist, cam: c, ujeto: zero - c, tasks });
  }
  return { zero, points: out };
}"""

REMAKE_JS = """(cfg) => {
  startGame(0);
  const g = state.g;
  g.keys = {};
  const zero = scrollTop(g);
  const out = [];
  for (const dist of cfg.points) {
    let guard = 0;
    while (zero - scrollTop(g) < dist && guard++ < 40000) {
      g.keys.f = (guard & 4) < 2;          // pulzovana palba jako original
      step(g);
    }
    const c = scrollTop(g), tasks = [], pending = [];
    // Klony formaci (g.air) nemaji vlastni gfx - v originalu bezi pod gfx
    // sve mapove polozky (FODDERA 0x0404, YELLOW 0x0014, BIRD 0x0015).
    const KIND_GFX = { fod: 0x0404, yel: 0x0014, bird: 0x0015, jet: 0x0020 };
    const add = (o, kind) => {
      if (!o || o.dead) return;
      if (kind === "spawn" && (!o.born || !o.alive)) return;
      if (kind !== "spawn" && !o.alive) return;
      const gfx = o.gfx !== undefined ? o.gfx
                : KIND_GFX[o.kind] !== undefined ? KIND_GFX[o.kind] : -1;
      tasks.push({ gfx, x: Math.round(o.x),
                   ys: Math.round(o.y) - c, z: Math.round(o.z || 0),
                   hp: o.hp | 0, kind: kind + ":" + (o.kind || o.beh || "?") });
    };
    // Klony formaci a deti maji polohu zavislou na RNG a na tom, kde je
    // hrac; porovnavaji se az v druhem kroku. Tady jen mapove objekty,
    // ktere vznikaji deterministicky ze scrollu.
    for (const o of g.spawns) add(o, "spawn");
    // Diagnostika: mapove objekty, ktere jeste nebyly aktivovany. Bez nich
    // nelze odlisit "prepis objekt nema" od "prepis ho aktivuje pozdeji".
    for (const o of g.spawns) {
      if (o.born || o.dead || o.gfx === undefined) continue;
      pending.push({ gfx: o.gfx, x: Math.round(o.x),
                     ys: Math.round(o.y) - c, born: false });
    }
    out.push({ dist, cam: c, ujeto: zero - c, tasks, pending });
  }
  return { zero, points: out };
}"""


def original(points):
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
            res = page.evaluate(ORIG_JS, {"a6": vacmp.A6_BASE, "mark": MARK,
                                          "points": list(points)})
            browser.close()
    finally:
        srv.shutdown()
    return res


def remake(points):
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto("file://" + os.path.join(ROOT, "game.html"))
        page.set_input_files("#fpick", os.path.join(ROOT, "SWIVFIX.ADF"))
        page.wait_for_selector("#titlewrap", state="visible")
        page.evaluate("window.requestAnimationFrame = () => 0")
        page.keyboard.press(" ")
        page.wait_for_selector("#gamewrap", state="visible")
        res = page.evaluate(REMAKE_JS, {"points": list(points)})
        browser.close()
    return res


def map_gfx():
    with open(os.path.join(ROOT, "build", "dispatch.json")) as fh:
        return {int(d["gfx"]) for d in json.load(fh)}


def pair(a, b):
    """Spari objekty podle gfx a polohy; vrati (dvojice, jen_a, jen_b)."""
    left = list(a)
    rest = list(b)
    pairs = []
    for o in left[:]:
        best, bi = None, -1
        for i, r in enumerate(rest):
            if r["gfx"] != o["gfx"]:
                continue
            d = abs(r["x"] - o["x"]) + abs(r["ys"] - o["ys"])
            if best is None or d < best:
                best, bi = d, i
        if bi >= 0 and best <= TOL * 2:
            pairs.append((o, rest.pop(bi)))
            left.remove(o)
    return pairs, left, rest


def main():
    points = [int(x) for x in sys.argv[1:]] or list(CHECKPOINTS)
    print("originál ...", flush=True)
    o = original(points)
    print("prepis ...", flush=True)
    r = remake(points)
    print(f"\nnulovy bod: original cam {o['zero']}, prepis scroll {r['zero']}\n")
    total_pairs = total_only_o = total_only_r = total_bad = 0
    names = {int(d["gfx"]): "%s#%d" % (d["file"], d["frame"])
             for d in json.load(open(os.path.join(ROOT, "build", "dispatch.json")))}
    known = map_gfx()
    for po, pr in zip(o["points"], r["points"]):
        # klony formaci (FODDERA/YELLOW/BIRD) i deti maji polohu zavislou na
        # RNG a na hraci - v tomto kroku je vynechavame z obou stran
        FORMATION = {0x0404, 0x0014, 0x0015}
        ot = [t for t in po["tasks"]
              if t["gfx"] in known and t["gfx"] not in FORMATION]
        rt = [t for t in pr["tasks"]
              if t["gfx"] in known and t["gfx"] not in FORMATION]
        po = dict(po, tasks=ot); pr = dict(pr, tasks=rt)
        pairs, only_o, only_r = pair(po["tasks"], pr["tasks"])
        bad = [(x, y) for x, y in pairs
               if abs(x["x"] - y["x"]) > TOL or abs(x["ys"] - y["ys"]) > TOL]
        total_pairs += len(pairs); total_only_o += len(only_o)
        total_only_r += len(only_r); total_bad += len(bad)
        print(f"ujeto {po['dist']:5d} px: original {len(po['tasks']):3d} obj, "
              f"prepis {len(pr['tasks']):3d} obj -> spárováno {len(pairs):3d}, "
              f"jen v originále {len(only_o):2d}, jen v přepisu {len(only_r):2d}")
        for x in only_o[:8]:
            near = [q for q in pr.get("pending", [])
                    if q["gfx"] == x["gfx"] and abs(q["x"] - x["x"]) <= TOL]
            if near:
                q = min(near, key=lambda q: abs(q["ys"] - x["ys"]))
                note = (f"  (prepis ma, ale jeste neaktivoval: ys {q['ys']},"
                        f" rozdil {q['ys'] - x['ys']:+d} px)")
            else:
                note = "  (prepis nema vubec)"
            print(f"    {names.get(x['gfx'], hex(x['gfx'])):<20}"
                  f" x {x['x']:4d} ys {x['ys']:5d} hp {x['hp']:3d}{note}")
        for y in only_r[:6]:
            print(f"    NAVIC v prepisu: {names.get(y['gfx'], hex(y['gfx'])):<20}"
                  f" x {y['x']:4d} ys {y['ys']:5d} hp {y['hp']:3d} [{y['kind']}]")
    print(f"\ncelkem: spárováno {total_pairs}, jen originál {total_only_o}, "
          f"jen přepis {total_only_r}, posunutých {total_bad}")


if __name__ == "__main__":
    main()
