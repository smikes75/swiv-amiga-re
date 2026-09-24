#!/usr/bin/env python3
"""Paty druh porovnani: DRAHY objektu po aktivaci, original vs prepis.

`objdiff.py` overuje OKAMZIK aktivace (980 z 981 presne). Neovereno zustavalo,
co objekt dela POTOM - jestli leti stejne rychle, stejnym smerem a stejne
zataci. Tenhle skript sleduje kazdy objekt snimek po snimku od aktivace na
obou stranach a hlasi PRVNI tik, kde se drahy rozejdou.

Original: harness vAmiga (tools/survey/vacmp.py), zaznamy uloh v chip RAM:
  hlava fronty A6-698, dalsi +4, priorita +274 (objekty 100), +534 marker
  "uz prosla a2c6", +368 gfx, +320 x a +324 y (16.16, bere se horni slovo).
Prepis: g.spawns (mapove objekty) a g.air (klony formaci).

Obe strany bezi BEZ palby a bez vstupu (hrac sedi, trainer/lives drzi zivot),
takze se meri ciste chovani objektu. Parovani je stejne jako v
`objdiff --events`: gfx, x v okamziku aktivace (+-2 px) a nejblizsi okamzik.

Porovnava se v SOURADNICICH SVETA vuci okamziku aktivace:
  dx(t) = x(t),  dy(t) = y(t) - y(aktivace)
Svetova y neni zavisla na kamere, takze pripadne zpomaleni scrollu originalu
pri zatezi (GAPS) do porovnani nevstoupi.

Znamenko y: v obou implementacich mapa KLESA (g.scroll i fp@(3530)), takze
svetove y maji tentyz smysl a porovnavaji se primo.

    python3 tools/trajdiff.py              # TOWN, prvnich 900 px
    python3 tools/trajdiff.py 1500 --tiku 200
    python3 tools/trajdiff.py 2400 --json beh.json   # ulozit obe strany

Vysledek 2026-09-24 (2 400 px TOWN): tanky 15/16, plamen, vlak, mina a mlyn
sedi; vsech 5 CAMOGUN se rozejde v tiku 105 az 107. Pricina neni v CAMOGUN,
ale v planovaci: kolo originalu trva 2 az 5 VBL a smycka zakluzu pocita
KOLA. Rozbor a seznam 15 dotcenych chovani je v docs/GAPS.md, "Kadence
planovace".
"""
import base64
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "survey"))
import vacmp                                        # noqa: E402
from playwright.sync_api import sync_playwright     # noqa: E402

MARK = (0xa36a + vacmp.PROG_BASE) & 0xffff
TOL = 1                 # px; prepis pocita ve floatech, original 16.16

ORIG_JS = """(cfg) => {
  const H = VA.M.HEAPU8, p = VA.fn.chipPtr(), n = VA.fn.chipSize();
  const L = a => (H[p+a]<<24|H[p+a+1]<<16|H[p+a+2]<<8|H[p+a+3])>>>0;
  const W = a => { const v = (H[p+a]<<8)|H[p+a+1]; return v > 0x7fff ? v-0x10000 : v; };
  const U = a => (H[p+a]<<8)|H[p+a+1];
  const cam = () => { let hi = L(cfg.a6 + 3530) >>> 16;
                      return hi > 0x7fff ? hi - 0x10000 : hi; };
  let guard = 0;
  while (H[p + cfg.a6 + 166] !== 0 && guard++ < 3000) VA.run(4, null);
  const zero = cam();
  // adresa -> rozpracovana draha; po zmizeni z fronty se uzavre
  const live = new Map(), tracks = [], kamera = [];
  let vbl = 0;
  const scan = () => {
    const c = cam();
    const seen = new Set();
    let node = cfg.a6 - 698, g = 0;
    while (g++ < 500) {
      const nx = L(node + 4);
      if (!nx || nx >= n || seen.has(nx)) break;
      seen.add(nx);
      if (W(nx + 274) === 100 && (L(nx + 534) & 0xffff) === cfg.mark) {
        let t = live.get(nx);
        const gfx = U(nx + 368);
        // Adresa ulohy se po smrti objektu RECYKLUJE, a kdyz ji dalsi uloha
        // dostane mezi dvema skeny, pokracovala by stopa s cizim objektem
        // (videno: stopa "FODDERA" zacinajici uprostred obrazovky). Skok
        // polohy o vic nez 24 px za jeden VBL je proto novy objekt.
        if (t && t.s.length) {
          const [px, py] = t.s[t.s.length - 1];
          if (Math.abs(W(nx + 320) - px) > 24 || Math.abs(W(nx + 324) - py) > 24) {
            t.konec = vbl; live.delete(nx); t = null;
          }
        }
        if (!t) {
          t = { gfx0: gfx, born: vbl, ujeto: zero - c, x0: W(nx + 320),
                ys0: W(nx + 324) - c, s: [] };
          live.set(nx, t); tracks.push(t);
        }
        if (t.s.length < cfg.tiku)
          t.s.push([W(nx + 320), W(nx + 324), gfx, W(nx + 360)]);
      }
      node = nx;
    }
    for (const [a, t] of live) if (!seen.has(a)) { t.konec = vbl; live.delete(a); }
  };
  scan();
  while (zero - cam() < cfg.dist) {
    VA.run(1, null); vbl++;
    kamera.push(cam());
    scan();
  }
  return { zero, tracks, kamera };
}"""

REMAKE_JS = """(cfg) => {
  startGame(0);
  const g = state.g; g.keys = {}; g.lives = 99;
  const zero = scrollTop(g);
  const KIND_GFX = { fod: 0x0404, yel: 0x0014, bird: 0x0015, jet: 0x0020 };
  const live = new Map(), tracks = [];
  let tik = 0, guard = 0;
  const gfxOf = o => o.gfx !== undefined ? o.gfx
                   : KIND_GFX[o.kind] !== undefined ? KIND_GFX[o.kind] : -1;
  const scan = () => {
    const c = scrollTop(g);
    const seen = new Set();
    const vezmi = (o, druh) => {
      if (!o || o.dead || !o.alive) return;
      if (druh === "spawn" && !o.born) return;
      seen.add(o);
      let t = live.get(o);
      if (!t) {
        t = { gfx0: gfxOf(o), born: tik, ujeto: zero - c,
              x0: Math.floor(o.x), ys0: Math.floor(o.y) - c,
              beh: o.beh || o.kind || "?", s: [] };
        live.set(o, t); tracks.push(t);
      }
      if (t.s.length < cfg.tiku)
        t.s.push([Math.floor(o.x), Math.floor(o.y), gfxOf(o), o.hp | 0]);
    };
    for (const o of g.spawns) vezmi(o, "spawn");
    for (const o of g.air || []) vezmi(o, "air");
    for (const [o, t] of live) if (!seen.has(o)) { t.konec = tik; live.delete(o); }
  };
  scan();
  while (zero - scrollTop(g) < cfg.dist && guard++ < 400000) {
    step(g); tik++;
    g.lives = 99;
    scan();
  }
  return { zero, tracks };
}"""


def original(dist, tiku):
    srv, port = vacmp.serve(os.path.join(ROOT, "web"))
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch()
            page = br.new_page()
            page.set_default_timeout(1_800_000)
            page.goto(f"http://127.0.0.1:{port}/vacmp.html")
            page.wait_for_function("window.VA && window.VA.ready", timeout=60000)
            page.evaluate("([r, a]) => VA.boot(r, a)", [
                base64.b64encode(open(vacmp.ROM, "rb").read()).decode(),
                base64.b64encode(open(vacmp.ADF, "rb").read()).decode()])
            page.evaluate(vacmp.PLAY_PROLOGUE)
            res = page.evaluate(ORIG_JS, {"a6": vacmp.A6_BASE, "mark": MARK,
                                          "dist": dist, "tiku": tiku})
            br.close()
    finally:
        srv.shutdown()
    return res


def remake(dist, tiku):
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        page = br.new_page()
        page.set_default_timeout(1_800_000)
        page.goto("file://" + os.path.join(ROOT, "game.html"))
        page.set_input_files("#fpick", os.path.join(ROOT, "SWIVFIX.ADF"))
        page.wait_for_selector("#titlewrap", state="visible")
        page.evaluate("window.requestAnimationFrame = () => 0")
        res = page.evaluate(REMAKE_JS, {"dist": dist, "tiku": tiku})
        br.close()
    return res


def names():
    with open(os.path.join(ROOT, "build", "dispatch.json")) as fh:
        return {int(d["gfx"]): "%s#%d" % (d["file"], d["frame"])
                for d in json.load(fh)}


# Klony formaci maji x (a u FODDERA i vx) z RNG. RNG originalu navic
# perturbuje VHPOSR ze zvukoveho preruseni, takze se neda dorovnat - u nich
# se porovnava jen SVISLY pohyb.
FORMACE = {0x0404, 0x0014, 0x0015, 0x0020}


def rozchod(a, b):
    """Prvni OBNOVA originalu, kde se drahy lisi vic nez TOL, nebo None.

    Korutiny originalu se nebudi kazdy VBL: zmereno v TOWN, ze se poloha
    objektu meni po 2 VBL (4 386x), 3 (1 165x), 4 (574x) i 5 (97x), a jen
    8x po jednom - hlavni smycka trva dva a vic snimku a `0x62fe` pak
    integruje rychlost x ubehle VBL. Mezi obnovami je poloha originalu
    ZASTARALA, takze se porovnava jen ve VBL, kdy se zmenila. V nich je to
    presny integral a prepis (50 Hz) ma sedet na +-TOL.

    Porovnava se POSUN od aktivace v obou osach; puvodni polohu ohlasi
    `offset` zvlast, aby jednobodovy rozdil pri zrodu nezakryl pohyb."""
    return rozchod_s_posunem(a, b, 0)


def rozchod_s_posunem(a, b, k):
    """Jako `rozchod`, ale prepis se cte o `k` tiku pozdeji (k muze byt
    zaporne). Pocatek (posun 0) je u prepisu v tiku k."""
    jen_y = a["gfx0"] in FORMACE
    if k >= 0:
        if k >= len(b["s"]):
            return 0, (0, 0), (0, 0)
        x0a, y0a = a["s"][0][0], a["s"][0][1]
        x0b, y0b = b["s"][k][0], b["s"][k][1]
    else:
        if -k >= len(a["s"]):
            return 0, (0, 0), (0, 0)
        x0a, y0a = a["s"][-k][0], a["s"][-k][1]
        x0b, y0b = b["s"][0][0], b["s"][0][1]
    start = max(0, -k)
    for t in range(start, min(len(a["s"]), len(b["s"]) - k)):
        if t > start and a["s"][t][:2] == a["s"][t - 1][:2]:
            continue                        # original se v tomto VBL nehnul
        dxa, dya = a["s"][t][0] - x0a, a["s"][t][1] - y0a
        dxb, dyb = b["s"][t + k][0] - x0b, b["s"][t + k][1] - y0b
        # Tolerance = jeden tik pohybu prepisu (min. TOL). Original se obnovuje
        # po 2 az 5 VBL a jediny spolecny posun nepokryje zrychlujici objekt po
        # cely let (FODDERA pada koncem letu ~3 px/tik). Chyba RYCHLOSTI se
        # ale scita, takze ji tahle tolerance neschova.
        u = t + k
        vx = abs(b["s"][min(u + 1, len(b["s"]) - 1)][0] - b["s"][u][0])
        vy = abs(b["s"][min(u + 1, len(b["s"]) - 1)][1] - b["s"][u][1])
        if abs(dya - dyb) > max(TOL, vy) or \
           (not jen_y and abs(dxa - dxb) > max(TOL, vx)):
            return t, (dxa, dya), (dxb, dyb)
    return None


# Original objekt "ukaze" az pri prvni obnove po a2c6, tedy o 1 az ~4 VBL
# pozdeji nez skutecna aktivace; prepis v tiku aktivace. U rychlych objektu
# (YELLOW 2 px/VBL) to dela +-2 az 4 px, ktere nejsou chybou chovani.
# Proto se pro kazdy par hleda casovy posun v rozsahu kadence originalu.
POSUNY = range(-4, 5)


def nejlepsi(a, b):
    """(posun, rozchod) s nejpozdejsim rozchodem; pri shode mensi |posun|."""
    best = None
    for k in sorted(POSUNY, key=abs):
        d = rozchod_s_posunem(a, b, k)
        skore = 10 ** 9 if d is None else d[0]
        if best is None or skore > best[0]:
            best = (skore, k, d)
    return best[1], best[2]


def offset(a, b):
    """Rozdil polohy NA OBRAZOVCE v okamziku aktivace (prepis - original)."""
    return b["x0"] - a["x0"], b["ys0"] - a["ys0"]


def kadence(tracks):
    """Rozestupy mezi zmenami polohy v originalu (kolik VBL mezi obnovami)."""
    c = collections.Counter()
    for t in tracks:
        z = [i for i in range(1, len(t["s"])) if t["s"][i][:2] != t["s"][i - 1][:2]]
        for i in range(1, len(z)):
            c[z[i] - z[i - 1]] += 1
    return dict(sorted(c.items()))


def main():
    args = sys.argv[1:]
    tiku = 150
    if "--tiku" in args:
        i = args.index("--tiku"); tiku = int(args[i + 1]); del args[i:i + 2]
    ulozit = None
    if "--json" in args:
        i = args.index("--json"); ulozit = args[i + 1]; del args[i:i + 2]
    dist = int(args[0]) if args else 900

    print(f"original (harness vAmiga), {dist} px ...", flush=True)
    o = original(dist, tiku)
    print(f"prepis, {dist} px ...", flush=True)
    r = remake(dist, tiku)
    if ulozit:
        json.dump({"orig": o, "remake": r}, open(ulozit, "w"))

    kam = o["kamera"]
    kroky = collections.Counter(kam[i] - kam[i + 1] for i in range(len(kam) - 1))
    print(f"\nkamera originalu: {len(kam)} VBL na {dist} px "
          f"(idealne {4 * dist}), posuny za VBL {dict(kroky)}")
    print(f"kadence objektu originalu (VBL mezi obnovami polohy): "
          f"{kadence(o['tracks'])}")

    jm = names()
    zbyva = list(r["tracks"])
    pary, chybi = [], []
    for a in o["tracks"]:
        # Klony formaci maji x z RNG, takze se paruji jen podle okamziku
        # (vznikaji po 4 px scrollu, tolerance 2 px je jednoznacna).
        # Obe strany se musi rodit na teze vysce obrazovky (aktivacni marze);
        # stopa originalu, ktera zacina jinde, je recyklovana adresa nebo
        # objekt vznikly mimo mapu a do parovani nepatri.
        if a["gfx0"] in FORMACE:
            kand = [b for b in zbyva if b["gfx0"] == a["gfx0"]
                    and abs(b["ujeto"] - a["ujeto"]) <= 2
                    and abs(b["ys0"] - a["ys0"]) <= 3]
        else:
            kand = [b for b in zbyva if b["gfx0"] == a["gfx0"]
                    and abs(b["x0"] - a["x0"]) <= 2
                    and abs(b["ys0"] - a["ys0"]) <= 3]
        if not kand:
            chybi.append(a)
            continue
        b = min(kand, key=lambda b: abs(b["ujeto"] - a["ujeto"]))
        zbyva.remove(b)
        pary.append((a, b))

    shoda, rozesle = [], []
    posuny = collections.Counter()
    for a, b in pary:
        k, d = nejlepsi(a, b)
        posuny[k] += 1
        n = min(len(a["s"]), len(b["s"]))
        (shoda if d is None else rozesle).append((a, b, d, n))

    print(f"drah original {len(o['tracks'])}, prepis {len(r['tracks'])}, "
          f"sparovano {len(pary)}, bez paru v prepisu {len(chybi)}, "
          f"navic v prepisu {len(zbyva)}")
    print(f"shodne po celou spolecnou delku: {len(shoda)}, rozejdou se: "
          f"{len(rozesle)}")
    print(f"nejlepsi casovy posun prepisu (tiky): {dict(sorted(posuny.items()))}\n")

    po_druhu = collections.defaultdict(lambda: [0, 0, []])
    for a, b, d, n in shoda:
        po_druhu[b["beh"]][0] += 1
    for a, b, d, n in rozesle:
        po_druhu[b["beh"]][1] += 1
        po_druhu[b["beh"]][2].append(d[0])
    print("%-14s %6s %8s  %s" % ("chovani", "shoda", "rozchod", "tik rozchodu"))
    for beh, (s, rz, t) in sorted(po_druhu.items(), key=lambda kv: -kv[1][1]):
        print("%-14s %6d %8d  %s" % (beh, s, rz, sorted(t)[:12]))

    offs = collections.Counter(offset(a, b) for a, b in pary
                               if a["gfx0"] not in FORMACE)
    print(f"\nposun pri aktivaci (prepis - original, mimo formace): "
          f"{dict(offs.most_common(8))}")
    print("\nprvni rozchody (posun x, y od aktivace; original / prepis):")
    for a, b, d, n in sorted(rozesle, key=lambda q: q[0]["ujeto"])[:30]:
        t, (xa, ya), (xb, yb) = d
        print(f"  {jm.get(a['gfx0'], hex(a['gfx0'])):<18} {b['beh']:<12}"
              f" aktivace {a['ujeto']:5d} px  tik {t:3d}:"
              f" ({xa:4d},{ya:4d}) / ({xb:4d},{yb:4d})")
    for a in chybi[:10]:
        print(f"  CHYBI  {jm.get(a['gfx0'], hex(a['gfx0'])):<18}"
              f" x {a['x0']:4d} pri {a['ujeto']:5d} px")


if __name__ == "__main__":
    main()
