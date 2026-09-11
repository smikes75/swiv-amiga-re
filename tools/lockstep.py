#!/usr/bin/env python3
"""Sesty kontrakt: simulace je bit po bitu stejna ve dvou JS enginech.

Lockstepova sitova hra posila jen vstupy a obe strany pocitaji tutez
simulaci. Staci jediny bit rozdilu a hry se rozejdou. Tenhle skript to
meri primo: tyz skriptovany beh v **Chromiu (V8)** a **WebKitu
(JavaScriptCore)**, po kazdem tiku otisk celeho stavu.

Proc to vubec muze vyjit: IEEE 754 zarucuje, ze `+ - * /` na doublech
daji na kazde platforme tentyz vysledek. Nezarucene jsou jen
transcendentni funkce (`Math.sin` a spol.), a ty v hernim kroku nejsou -
`SIN256` se pocita jednou pri nacteni a jeji hodnoty lezi 1,25e10 ulp od
nejblizsi hranice zaokrouhleni (nejhorsi je index 229, -157,49929), takze
zadny realny rozdil `Math.sin` je preklopit nemuze. PRNG `0x883c` je
celociselny.

    python3 tools/lockstep.py            # vsechny scenare
    python3 tools/lockstep.py --dump X   # otisky po tikach do X

Pri neshode skript vypise PRVNI tik, ve kterem se stav lisi, a ktera
polozka za to muze - to je presne to, co potrebuje ladeni rozjezdu.
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (jmeno, uroven, tiku, skript vstupu). Skript je seznam
# (od tiku, klavesy hrace 1, klavesy hrace 2); plati az do dalsi polozky.
SCENARIOS = [
    ("TOWN bez vstupu", 0, 400, [(0, "", "")]),
    ("TOWN palba a pohyb", 0, 600, [
        (0, "f", ""), (60, "lf", ""), (150, "rf", ""),
        (260, "uf", ""), (380, "df", "")]),
    ("TOWN dva hraci", 0, 600, [
        (0, "f", "f"), (40, "f", "rf"), (120, "lf", "dfj"),
        (260, "rf", "lf"), (400, "uf", "ufj")]),
    ("RIVER dva hraci a plosiny", 3, 4000, [
        (0, "f", "f"), (500, "rf", "rf"), (1500, "lf", "lfj")]),
]

# Otisk stavu. Cisla jdou pres Float64Array, takze se porovnavaji BITY,
# ne zaokrouhleny text - jinak by rozdil v posledni platne cifre propadl.
# Obaleno do bezparametrove funkce zamerne: `page.evaluate` s retezcem,
# ktery sam o sobe vyhodnoti na funkci, tu funkci ROVNOU ZAVOLA - bez
# obalu by se `__hash` spustila s `g = undefined`.
HASH_JS = """() => {
window.__hash = (g) => {
  const nums = [], ints = [];
  const num = v => nums.push(typeof v === 'number' ? v : NaN);
  const int = v => ints.push(v | 0);
  int(g.tick); num(g.scroll); int(g.score); int(g.lives);
  int(g.rngState); int(g.activeCost); int(g.levelPhase);
  int(g.jeepScore); int(g.jeepLives); int(g.difficulty);
  const player = p => {
    if (!p) { int(-1); return; }
    num(p.x); num(p.y); int(p.ang); int(p.alive ? 1 : 0);
    int(p.inv); int(p.cool); int(p.weapon); int(p.rank);
    num(p.z || 0); num(p.vz || 0); int(p.turret || 0);
    int(p.airborne ? 1 : 0); int(p.form === 'boat' ? 1 : 0);
  };
  player(g.player); player(g.player2);
  const list = (arr, f) => {
    int(arr ? arr.length : -1);
    for (const o of arr || []) f(o);
  };
  list(g.bullets, b => { num(b.x); num(b.y); num(b.vx); num(b.vy);
                         int(b.frame); int(b.owner || 1); });
  list(g.shots, s => { num(s.x); num(s.y); int(s.ang | 0); });
  list(g.air, a => { num(a.x); num(a.y); int(a.hp | 0);
                     int(a.alive ? 1 : 0); int(a.apos | 0); });
  list(g.hazards, h => { num(h.x); num(h.y); int(h.hp | 0);
                         int(h.alive ? 1 : 0); });
  list(g.tokens, k => { num(k.x); num(k.y); int(k.typ | 0); });
  list(g.booms, b => { num(b.x); num(b.y); int(b.t | 0); });
  // Mapove objekty: jen ty zive, ale i jejich poradi je soucast stavu.
  let n = 0;
  for (const s of g.spawns) if (s.born && s.alive) n++;
  int(n);
  for (const s of g.spawns) {
    if (!s.born || !s.alive) continue;
    num(s.x); num(s.y); int(s.hp | 0); int(s.st | 0); int(s.t | 0);
    int(s.fr | 0); int(s.bobOrdinal | 0);
  }
  // FNV-1a pres BYTY obou poli.
  const fb = new Uint8Array(new Float64Array(nums).buffer);
  const ib = new Uint8Array(new Int32Array(ints).buffer);
  let h = 0x811C9DC5;
  for (const arr of [fb, ib])
    for (const v of arr) h = Math.imul((h ^ v) >>> 0, 0x01000193) >>> 0;
  return h.toString(16).padStart(8, '0');
};
}"""

RUN_JS = """(cfg) => {
  startGame(cfg.level);
  const g = state.g;
  g.lives = 99999;                      // beh nesmi skoncit driv nez skript
  const otisky = [];
  let krok = 0;
  for (let t = 0; t < cfg.ticks; t++) {
    while (krok < cfg.script.length && cfg.script[krok][0] <= t) {
      const [, k1, k2] = cfg.script[krok++];
      g.keys = {}; g.keys2 = {};
      for (const c of k1) g.keys[c] = true;
      for (const c of k2) g.keys2[c] = true;
    }
    step(g);
    if (g.lives < 99999) g.lives = 99999;
    if (g.jeepLives < 1) g.jeepLives = 4;
    otisky.push(window.__hash(g));
  }
  return otisky;
}"""


def run(engine, scenario):
    name, level, ticks, script = scenario
    with sync_playwright() as pw:
        b = getattr(pw, engine).launch()
        try:
            page = b.new_page()
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            page.goto("file://" + os.path.join(ROOT, "game.html"))
            page.set_input_files("#fpick", os.path.join(ROOT, "SWIVFIX.ADF"))
            page.wait_for_selector("#titlewrap", state="visible",
                                   timeout=60000)
            page.evaluate("window.requestAnimationFrame = () => 0")
            page.keyboard.press(" ")
            page.wait_for_selector("#gamewrap", state="visible")
            page.evaluate(HASH_JS)
            out = page.evaluate(RUN_JS, {"level": level, "ticks": ticks,
                                         "script": script})
            if errs:
                raise SystemExit(f"{engine}: chyby stranky: {errs[:3]}")
            return out
        finally:
            b.close()


# Kontrola citlivosti otisku: kdyz se hraci posune `x` o JEDINY ulp
# (nejmensi reprezentovatelny rozdil v doublu), otisk se musi zmenit.
# Bez teto kontroly by prosel i otisk, ktery nic nemeri.
SENSITIVITY_JS = """() => {
  startGame(0);
  const g = state.g;
  for (let t = 0; t < 50; t++) step(g);
  const pred = window.__hash(g);
  const puvodni = g.player.x;
  // dalsi reprezentovatelny double smerem nahoru
  const buf = new DataView(new ArrayBuffer(8));
  buf.setFloat64(0, puvodni);
  const hi = buf.getUint32(0), lo = buf.getUint32(4);
  if (lo === 0xffffffff) { buf.setUint32(0, hi + 1); buf.setUint32(4, 0); }
  else buf.setUint32(4, lo + 1);
  g.player.x = buf.getFloat64(0);
  const po = window.__hash(g);
  const rozdil = g.player.x - puvodni;
  g.player.x = puvodni;
  return { pred, po, rozdil, zachyceno: pred !== po };
}"""


def selftest():
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        try:
            page = b.new_page()
            page.goto("file://" + os.path.join(ROOT, "game.html"))
            page.set_input_files("#fpick", os.path.join(ROOT, "SWIVFIX.ADF"))
            page.wait_for_selector("#titlewrap", state="visible",
                                   timeout=60000)
            page.evaluate("window.requestAnimationFrame = () => 0")
            page.keyboard.press(" ")
            page.wait_for_selector("#gamewrap", state="visible")
            page.evaluate(HASH_JS)
            return page.evaluate(SENSITIVITY_JS)
        finally:
            b.close()


def main():
    dump = None
    args = sys.argv[1:]
    if "--dump" in args:
        i = args.index("--dump"); dump = args[i + 1]; del args[i:i + 2]

    citlivost = selftest()
    if not citlivost["zachyceno"]:
        print("LOCKSTEP SELHAL: otisk nezachyti ani zmenu o jeden ulp - "
              "kontrakt by nic nemeril")
        sys.exit(1)
    print(f"  OK  otisk je citlivy na 1 ulp (posun o {citlivost['rozdil']:.3e} "
          f"px zmenil {citlivost['pred']} -> {citlivost['po']})")

    vysledky = {}
    selhalo = False
    for scenario in SCENARIOS:
        name = scenario[0]
        a = run("chromium", scenario)
        b = run("webkit", scenario)
        vysledky[name] = {"chromium": a, "webkit": b}
        if a == b:
            print(f"  OK  {name}: {len(a)} tiku bit po bitu shodnych "
                  f"(V8 i JavaScriptCore), otisk {a[-1]}")
            continue
        selhalo = True
        prvni = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y),
                     min(len(a), len(b)))
        print(f"  CHYBA  {name}: enginy se rozesly v tiku {prvni}")
        print(f"         chromium {a[prvni] if prvni < len(a) else '-'}, "
              f"webkit {b[prvni] if prvni < len(b) else '-'}")

    if dump:
        with open(dump, "w") as f:
            json.dump(vysledky, f, indent=1)
        print(f"otisky ulozeny do {dump}")

    if selhalo:
        print("\nLOCKSTEP SELHAL: simulace neni prenositelna mezi enginy")
        sys.exit(1)
    print("\nLOCKSTEP OK: simulace je bit po bitu stejna ve V8 i "
          "JavaScriptCore")


if __name__ == "__main__":
    main()
