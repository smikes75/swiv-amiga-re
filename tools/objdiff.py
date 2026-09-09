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

Skript ma tri rezimy:

  python3 tools/objdiff.py                 snimky v pevnych bodech (nejslabsi)
  python3 tools/objdiff.py --events 900    okamziky aktivace, original vs prepis
  python3 tools/objdiff.py --predict 1500  okamziky aktivace proti MAPE

**`--predict` je nejsilnejsi**, protoze nepotrebuje original: ocekavany
okamzik plyne primo z mapy jako `ujeto = margin + zero - y`. Nezavisi tedy
ani na RNG, ani na tom, jak hraje hrac. Overeno 2026-09-09: z 9 sparovanych
aktivaci na 1500 px sedi vsech 9 **presne** (0 px), coz potvrzuje opravu
marzi z tehoz dne.

**Co se musi vynechavat a proc:**
- *Formace* (`wave`, `yellow`, `bird`, `blackjet`, `fish`, `goose7`,
  `skyeye`, `skyeyea`) nastavuji `born` uz v `startMapObjectTask` na prahu
  -256, protoze mapovy zaznam je jen spoustec a kazdy klon si pak ceka na
  vlastni a2c6 prah. Jejich `born` tedy neni aktivace ve smyslu `a2c6`.
  Bez tohoto vyjmuti hlasi skript systematicky -208 px, coz je presne
  rozdil -256 a -48.
- *Klony a deti* v rezimu `--events`: jejich poloha zavisi na RNG a na
  hraci. Vetsina "chybi v prepisu" u FLAME jsou plameny, ktere prepis ma
  jako `hazards`, ne `spawns`.
- Obe strany bezi **bez palby**; kdyz se strili, objekty umiraji v jinych
  okamzicich a porovnani vzniku se v tom ztraci.

Parovani jde pres **poradi vzniku**, ne polohu: obe strany prochazeji mapu
odshora dolu, takze n-ty objekt daneho druhu v predikci je n-ty i ve
skutecnosti. Podle polohy to nejde - `tank` a `train` si `x` pri vzniku
prepisou, protoze vjizdeji z okraje obrazovky.

**Vysledek plneho skenu (2026-09-09): 980 z 981 aktivaci presne, 0 odchylek.**
Jedina neaktivovana je `inst5`, a to kvuli teto kontrole samotne: FINAL boss
ceka na `g.inst1Factories > 0` (bit 3 `fp@(166)`, aktivni instalace),
zatimco skript tuto promennou nuluje, aby obesel scroll lock u DESERT
tovarny - bez palby by ji hrac nezniicil a mapa by stala navzdy.

**Test bezi bez originalu i bez emulatoru**, takze se hodi jako rychly
kontrakt vedle compare/uitest/smoothtest.

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

# Rezim udalosti: misto snimku v pevnych bodech sledujeme OKAMZIK AKTIVACE
# kazdeho objektu. Ten je invariantni vuci pohybu - objekt se rodi na danem
# miste mapy, at uz pak jede kamkoli - a tim padne slabina parovani podle
# polohy. Krok je 4 VBL = presne 1 px scrollu.
EVENTS_ORIG_JS = """(cfg) => {
  const H = VA.M.HEAPU8, p = VA.fn.chipPtr(), n = VA.fn.chipSize();
  const L = a => (H[p+a]<<24|H[p+a+1]<<16|H[p+a+2]<<8|H[p+a+3])>>>0;
  const W = a => { const v = (H[p+a]<<8)|H[p+a+1]; return v > 0x7fff ? v-0x10000 : v; };
  const U = a => (H[p+a]<<8)|H[p+a+1];
  const cam = () => { let hi = L(cfg.a6 + 3530) >>> 16;
                      return hi > 0x7fff ? hi - 0x10000 : hi; };
  // Bez palby: kdyz obe strany strili, objekty umiraji v jinych okamzicich
  // a porovnani vzniku se v tom ztraci. Hrac tu jen sedi (trainer ma
  // nekonecne zivoty), takze se meri ciste chovani mapy.
  let guard = 0;
  while (H[p + cfg.a6 + 166] !== 0 && guard++ < 3000) VA.run(4, null);
  const zero = cam();
  const seen = new Set(), events = [];
  const scan = () => {
    const c = cam();
    let node = cfg.a6 - 698, g = 0;
    while (g++ < 500) {
      const nx = L(node + 4);
      if (!nx || nx >= n) break;
      if (W(nx + 274) === 100 && (L(nx + 534) & 0xffff) === cfg.mark &&
          !seen.has(nx)) {
        seen.add(nx);
        events.push({ ujeto: zero - c, gfx: U(nx + 368), x: W(nx + 320),
                      ys: W(nx + 324) - c, hp: W(nx + 360), cls: U(nx + 504) });
      }
      node = nx;
    }
  };
  scan();
  while (zero - cam() < cfg.dist) {
    VA.run(4, null);
    scan();
    // uvolnene adresy se recykluji; zapomen ty, ktere uz ve fronte nejsou
    if (events.length % 64 === 0) {
      const live = new Set();
      let node = cfg.a6 - 698, g = 0;
      while (g++ < 500) { const nx = L(node + 4);
        if (!nx || nx >= n || live.has(nx)) break; live.add(nx); node = nx; }
      for (const a of Array.from(seen)) if (!live.has(a)) seen.delete(a);
    }
  }
  return { zero, events };
}"""

EVENTS_REMAKE_JS = """(cfg) => {
  startGame(0);
  const g = state.g; g.keys = {};
  g.lives = 99;                       // protejsek traineru na strane originalu
  const zero = scrollTop(g);
  const seen = new Set(), events = [];
  let guard = 0;
  while (zero - scrollTop(g) < cfg.dist && guard++ < 60000) {
    step(g);
    const c = scrollTop(g);
    for (const s of g.spawns) {
      if (!s.born || seen.has(s)) continue;
      seen.add(s);
      events.push({ ujeto: zero - c, gfx: s.gfx, x: Math.round(s.x),
                    ys: Math.round(s.y) - c, hp: s.hp | 0, beh: s.beh });
    }
  }
  return { zero, events };
}"""

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


def events_original(dist):
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
            res = page.evaluate(EVENTS_ORIG_JS,
                                {"a6": vacmp.A6_BASE, "mark": MARK, "dist": dist})
            browser.close()
    finally:
        srv.shutdown()
    return res


def events_remake(dist):
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto("file://" + os.path.join(ROOT, "game.html"))
        page.set_input_files("#fpick", os.path.join(ROOT, "SWIVFIX.ADF"))
        page.wait_for_selector("#titlewrap", state="visible")
        page.evaluate("window.requestAnimationFrame = () => 0")
        page.keyboard.press(" ")
        page.wait_for_selector("#gamewrap", state="visible")
        res = page.evaluate(EVENTS_REMAKE_JS, {"dist": dist})
        browser.close()
    return res


def compare_events(dist):
    """Porovna okamziky aktivace. Parovani: stejne gfx a stejne x, v poradi."""
    print("original ...", flush=True)
    o = events_original(dist)
    print("prepis ...", flush=True)
    r = events_remake(dist)
    names = {int(d["gfx"]): "%s#%d" % (d["file"], d["frame"])
             for d in json.load(open(os.path.join(ROOT, "build", "dispatch.json")))}
    known = map_gfx()
    FORM = {0x0404, 0x0014, 0x0015}
    keep = lambda e: e["gfx"] in known and e["gfx"] not in FORM
    oe = [e for e in o["events"] if keep(e)]
    re_ = [e for e in r["events"] if keep(e)]
    print(f"\nujeto {dist} px: aktivaci original {len(oe)}, prepis {len(re_)}\n")
    rest = list(re_)
    shift, missing = [], []
    for e in oe:
        cand = [q for q in rest if q["gfx"] == e["gfx"] and abs(q["x"] - e["x"]) <= 2]
        if not cand:
            missing.append(e)
            continue
        q = min(cand, key=lambda q: abs(q["ujeto"] - e["ujeto"]))
        rest.remove(q)
        if abs(q["ujeto"] - e["ujeto"]) > 1:
            shift.append((e, q))
    print(f"sparovano {len(oe) - len(missing)}, chybi v prepisu {len(missing)}, "
          f"navic v prepisu {len(rest)}, jiny okamzik {len(shift)}")
    for e, q in shift[:15]:
        print(f"   POZDE/BRZY {names.get(e['gfx'], hex(e['gfx'])):<18}"
              f" x {e['x']:4d}: original pri {e['ujeto']:5d} px,"
              f" prepis pri {q['ujeto']:5d} px  ({q['ujeto'] - e['ujeto']:+d})")
    for e in missing[:10]:
        print(f"   CHYBI      {names.get(e['gfx'], hex(e['gfx'])):<18}"
              f" x {e['x']:4d} pri {e['ujeto']:5d} px")
    for q in rest[:10]:
        print(f"   NAVIC      {names.get(q['gfx'], hex(q['gfx'])):<18}"
              f" x {q['x']:4d} pri {q['ujeto']:5d} px  [{q.get('beh','?')}]")


PREDICT_JS = """(cfg) => {
  startGame(0);
  const g = state.g; g.keys = {}; g.lives = 99;
  const zero = scrollTop(g);
  // Ocekavany okamzik aktivace plyne primo z mapy: objekt se rodi pri
  // ys >= margin, tedy pri ujeto = margin + zero - y. Zadny beh k tomu
  // neni potreba - je to referencni hodnota, se kterou se pak porovna
  // skutecny prubeh.
  // Formace nastavuji born uz v startMapObjectTask (prah -256), protoze
  // mapovy zaznam je jen spoustec - klony si pak kazdy ceka na vlastni
  // a2c6 prah. Jejich "born" tedy neni aktivace ve smyslu a2c6 a do teto
  // kontroly nepatri.
  const SPOUSTECE = new Set(["wave", "yellow", "bird", "blackjet",
                             "fish", "goose7", "skyeye", "skyeyea"]);
  // Ocekavani se pocita az v okamziku, kdy objekt dostane ulohu
  // (`taskStarted`, prah -256). Nektera chovani totiz do te chvile jeste
  // meni `y` nebo si urcuji vlastni marzi: xevswarm posune rodici y o -27
  // (0x7ed8) a airplane si nastavi airMargin 176 (0x7978), zatimco jeho
  // dite ma 127 (0x797e). Kdyby se ocekavani bralo z mapove polohy pred
  // timto krokem, hlasil by skript prave tyhle dva druhy jako chybu.
  const want = [];
  const wantSeen = new Set();
  const noteWant = () => {
    for (const s of g.spawns) {
      if (!s.taskStarted || wantSeen.has(s)) continue;
      wantSeen.add(s);
      if (s.gfx === undefined || SPOUSTECE.has(s.beh) || s.formationChild) continue;
      const m = s.airMargin !== undefined ? s.airMargin
              : s.activationMargin !== undefined ? s.activationMargin
              : cfg.margins[s.beh];
      if (m === undefined) continue;
      want.push({ gfx: s.gfx, beh: s.beh, x: Math.round(s.x),
                  ocekavano: m + zero - Math.round(s.y) });
    }
  };
  const seen = new Set(), got = [];
  let guard = 0;
  while (zero - scrollTop(g) < cfg.dist && guard++ < 400000) {
    // Bez palby hrac nezniici instalace, ktere drzi scroll (0xb6ae ->
    // fp@(166) bit 3), a mapa by od DESERT tovarny stala navzdy. Pro
    // kontrolu aktivacnich marzi je zamek irelevantni, tak jej drzime
    // uvolneny; scroll tim jede konstantne jako v neblokovanem useku.
    g.inst1Factories = 0; g.levelEndHold = false;
    step(g);
    noteWant();
    const c = scrollTop(g);
    for (const s of g.spawns) {
      // spawnFormationCopies pridava klony do g.spawns pod stejnym `beh`;
      // v mape je pritom jedina polozka, takze by rozhazely parovani
      if (!s.born || seen.has(s) || SPOUSTECE.has(s.beh) ||
          s.formationChild) continue;
      seen.add(s);
      got.push({ gfx: s.gfx, beh: s.beh, x: Math.round(s.x),
                 ujeto: zero - c });
    }
  }
  return { zero, want: want.filter(w => w.ocekavano >= 0 &&
                                        w.ocekavano <= cfg.dist), got };
}"""


def static_margins():
    """Marze z game.html, klic je jmeno chovani (viz tools/margins.py)."""
    import subprocess
    out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "margins.py")],
                         capture_output=True, text=True).stdout
    m = {}
    for line in out.splitlines():
        f = line.split()
        if len(f) >= 4 and f[0].isidentifier():
            try:
                m[f[0]] = int(f[3])
            except ValueError:
                pass
    return m


def predict(dist):
    """Overi, ze prepis rodi mapove objekty presne tam, kde plyne z marze."""
    margins = static_margins()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto("file://" + os.path.join(ROOT, "game.html"))
        page.set_input_files("#fpick", os.path.join(ROOT, "SWIVFIX.ADF"))
        page.wait_for_selector("#titlewrap", state="visible")
        page.evaluate("window.requestAnimationFrame = () => 0")
        page.keyboard.press(" ")
        page.wait_for_selector("#gamewrap", state="visible")
        res = page.evaluate(PREDICT_JS, {"dist": dist, "margins": margins})
        browser.close()
    want, got = res["want"], res["got"]
    # Parovani pres PORADI, ne polohu: obe strany prochazeji mapu odshora
    # dolu, takze n-ty objekt daneho druhu v predikci je n-ty i ve
    # skutecnosti. Podle polohy to nejde - tank a train si `x` pri vzniku
    # prepisou (vjizdeji z okraje obrazovky).
    from collections import defaultdict
    byname = defaultdict(list)
    for q in got:
        byname[q["beh"]].append(q)
    ok = late = missing = 0
    nalezy = []
    for w in sorted(want, key=lambda w: w["ocekavano"]):
        queue = byname[w["beh"]]
        if not queue:
            missing += 1
            nalezy.append(("NEAKTIVOVAN", w, None, 0))
            continue
        q = queue.pop(0)
        d = q["ujeto"] - w["ocekavano"]
        if abs(d) <= 1:
            ok += 1
        else:
            late += 1
            nalezy.append(("JINDY", w, q, d))
    extra = sum(len(v) for v in byname.values())
    if os.environ.get("OBJDIFF_EXTRA"):
        from collections import Counter
        c = Counter(q["beh"] for v in byname.values() for q in v)
        print("   navic podle druhu:", dict(c.most_common(12)))
    for kind, w, q, d in nalezy[:20]:
        if kind == "NEAKTIVOVAN":
            print(f"   NEAKTIVOVAN  {w['beh']:<12} x {w['x']:4d}"
                  f"  cekano pri {w['ocekavano']:5d} px")
        else:
            print(f"   JINDY        {w['beh']:<12} x {w['x']:4d}"
                  f"  cekano {w['ocekavano']:5d}, aktivovan {q['ujeto']:5d}"
                  f"  ({d:+d} px)")
    print("")
    print(f"ujeto {dist} px: z mapy ocekavano {len(want)} aktivaci -> "
          f"presne {ok}, jindy {late}, vubec {missing}, navic {extra}")
    return ok, late, missing, extra


def main():
    if sys.argv[1:2] == ["--predict"]:
        predict(int(sys.argv[2]) if len(sys.argv) > 2 else 900)
        return
    if sys.argv[1:2] == ["--events"]:
        compare_events(int(sys.argv[2]) if len(sys.argv) > 2 else 900)
        return
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
