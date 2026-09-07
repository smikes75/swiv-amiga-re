"""Simulacni sonda chovani: spusti game.html v headless Chromiu, vybere zonu,
bezi bez vstupu s neomezenymi zivoty a pro zadane behaviour id loguje
zrozeni, stav v zadanych ofsetech od zrozeni a uklada snimky.

Pouziti:
  python3 tools/survey/behprobe.py LEVEL 'SPEC' [OUTDIR] [MAXTICK]
    LEVEL   index zony 1..7 (1 = TOWN, 2 = DESERT, 3 = GRASS, ...)
    SPEC    JSON: {"beh": [ofsety tiku od zrozeni], ...}, napr.
            '{"vtol": [1, 60, 200], "trilo": [1, 100]}'
    OUTDIR  vychozi build/survey/probe
    MAXTICK vychozi 20000 (4 tiky = 1 radek mapy)

Volitelne v SPEC klic "kill": {"beh": ofset} -> v danem ofsetu od zrozeni
zavola damageSpawn tolikrat, dokud objekt zije (test smrti/vybuchu), a
ulozi snimky +3 a +25 tiku po zabiti.

Vystup: radky JSON na stdout (zrozeni, stav, hazardy/strely v danem tiku)
a PNG OUTDIR/<beh>_<ofset>_t<tik>.png. Montaz: tools/survey/montage.py
neni pro tyto snimky; slozte je napr. PIL (viz docs/ZADANI-GRASS.md).
"""
import base64
import json
import os
import sys

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
level = int(sys.argv[1])
spec = json.loads(sys.argv[2])
out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(ROOT, "build", "survey", "probe")
maxtick = int(sys.argv[4]) if len(sys.argv) > 4 else 20000
os.makedirs(out, exist_ok=True)
kill = spec.pop("kill", {})

JS = """([spec, kill, maxtick]) => {
  const g = state.g; g.lives = 100000;
  const shots = [], log = [];
  const snap = (name) => { const now = performance.now(); g.last = now; frame(now);
    shots.push([name, document.querySelector('#game').toDataURL('image/png')]); };
  const top = () => scrollTop(g);
  const round = v => Number.isFinite(v) ? Math.round(v * 100) / 100 : v;
  const dump = s => ({ x: round(s.x), sy: round(s.y - top()), st: s.st, fr: s.fr, hp: s.hp, t: s.t,
                       z: round(s.z), ang: s.ang, vx: round(s.vx), vy: round(s.vy), typ: s.typ,
                       alive: s.alive, noCull: s.noCull, lock: s.scrollLocked });
  const born = {}, killed = {};
  for (let t = 0; t < maxtick; t++) {
    step(g);
    for (const beh of Object.keys(spec)) {
      const list = g.spawns.filter(s => s.beh === beh && s.born);
      if (!list.length) continue;
      if (born[beh] === undefined) { born[beh] = t; log.push({ beh, event: 'born', t, objs: list.map(dump) }); }
      const k = t - born[beh];
      if (spec[beh].includes(k)) {
        snap(beh + '_' + k + '_t' + t);
        log.push({ beh, k, t, objs: g.spawns.filter(s => s.beh === beh && s.born && s.alive).map(dump),
                   hazards: g.hazards.filter(h => h.alive).map(h => [h.kind, round(h.x), round(h.y - top()), h.st, h.apos, h.hp]),
                   shots: g.shots.filter(s => !s.dead).map(s => [s.kind, round(s.x), round(s.y)]),
                   booms: g.booms.length, cost: g.activeCost, score: g.score });
      }
      if (kill[beh] !== undefined && k === kill[beh] && !killed[beh]) {
        const s = list.find(o => o.alive);
        if (s) { let n = 0; while (s.alive && n < 500) { damageSpawn(g, s); n++; }
                 killed[beh] = t; log.push({ beh, event: 'killed', t, hits: n, booms: g.booms.map(b => [b.kind, b.t]) }); }
      }
      if (killed[beh] !== undefined && [3, 25].includes(t - killed[beh])) snap(beh + '_dead' + (t - killed[beh]) + '_t' + t);
    }
    const all = Object.keys(spec).every(b => born[b] !== undefined);
    const last = all ? Math.max(...Object.values(born)) : 0;
    const maxK = Math.max(...Object.values(spec).flat(), ...Object.values(kill).map(v => v + 30));
    if (all && t > last + maxK + 5) break;
  }
  return { log, shots, tick: g.tick, born };
}"""

with sync_playwright() as pw:
    b = pw.chromium.launch(); page = b.new_page()
    page.on("pageerror", lambda e: print("PAGEERROR", e))
    page.goto("file://" + os.path.join(ROOT, "game.html"))
    page.set_input_files("#fpick", os.path.join(ROOT, "SWIVFIX.ADF"))
    page.wait_for_selector("#titlewrap", state="visible")
    page.wait_for_selector("#levelpick", state="visible")
    page.evaluate("window.requestAnimationFrame = () => 0")
    page.click("#levelbtns a:nth-child(%d)" % level)
    page.wait_for_selector("#gamewrap", state="visible")
    res = page.evaluate(JS, [spec, kill, maxtick])
    for name, data in res["shots"]:
        open(os.path.join(out, name + ".png"), "wb").write(base64.b64decode(data.split(",", 1)[1]))
    for l in res["log"]:
        print(json.dumps(l))
    print("tick", res["tick"], "born", res["born"], "frames", len(res["shots"]), "->", out)
    b.close()
