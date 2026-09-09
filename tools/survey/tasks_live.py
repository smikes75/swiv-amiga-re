#!/usr/bin/env python3
"""Vypise zive ulohy originalu z chip RAM (pres harness vacmp).

Planovac je v knihovne zavadece, ne v AMPROG.OBJ: skokova tabulka lezi na
zapornych offsetech od A6 a obsahuje BRA.W po ctyrech bajtech. Rozlusteno
2026-09-09 z pameti behu:

    A6-1474 -> 0x1030   zalozeni ulohy (a2 = hlava fronty A6-698,  SR 0x2200)
    A6-1470 -> 0x1052   druha varianta (a2 = hlava fronty A6-1006, SR 0x2300)
    A6-1494 -> 0x0e0e   alokace pameti
    A6-1446 -> 0x0f84   ukonceni ulohy

Zaznam ulohy je alokovan po 308 bajtech (0x1066 movew #308), dalsi prvek
seznamu je na +4 a priorita na +274. Herni objekty bezi s prioritou 100.

    python3 tools/survey/tasks_live.py [sekund_hry]
"""
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vacmp                                            # noqa: E402
from playwright.sync_api import sync_playwright         # noqa: E402

PC = 270                    # aktualni PC korutiny (overeno 2026-09-09)
HEAD_MAIN = -698            # hlava hlavni fronty vuci A6
HEAD_ALT = -1006
NEXT = 4                    # odkaz na dalsi ulohu
PRIO = 274

# Offsety poli herniho objektu (a5 v korutinach AMPROG.OBJ).
# Pozor: tyto offsety plati pro plnohodnotne objekty (a5 v korutinach
# AMPROG.OBJ). Deti a efektove ulohy maji jine rozlozeni - u nich vychazi
# napr. trida 8191 nebo hp -27862, coz jsou cizi data, ne skutecne hodnoty.
# Rozliseni podle typu ulohy zatim otevrene, viz docs/GAPS.md.
FIELDS = {"x": 320, "y": 324, "z": 328, "vx": 332, "vy": 336,
          "hp": 360, "cull": 364, "flags": 367, "trida": 504}

WALK_JS = """(cfg) => {
  const H = VA.M.HEAPU8, p = VA.fn.chipPtr(), n = VA.fn.chipSize();
  const L = a => (H[p+a]<<24|H[p+a+1]<<16|H[p+a+2]<<8|H[p+a+3])>>>0;
  const W = a => { const v = (H[p+a]<<8)|H[p+a+1];
                   return v > 0x7fff ? v - 0x10000 : v; };
  const out = [];
  let node = cfg.a6 + cfg.head, guard = 0;
  while (guard++ < 500) {
    const nx = L(node + cfg.next);
    if (!nx || nx >= n) break;
    if (out.some(t => t.adr === nx)) break;
    const rec = { adr: nx, prio: W(nx + cfg.prio), pc: L(nx + cfg.pc) };
    for (const [k, off] of Object.entries(cfg.fields)) rec[k] = W(nx + off);
    out.push(rec);
    node = nx;
  }
  return out;
}"""


def live_tasks(page, head=HEAD_MAIN):
    return page.evaluate(WALK_JS, {"a6": vacmp.A6_BASE, "head": head,
                                   "next": NEXT, "prio": PRIO, "pc": PC,
                                   "fields": FIELDS})


def behaviour_index(root):
    """Vstupni body korutin -> jmeno; PC ulohy patri nejblizsimu pod nim."""
    import json
    ent = {}
    with open(os.path.join(root, "build", "dispatch.json")) as fh:
        for d in json.load(fh):
            ent[int(d["coroutine"], 16)] = "%s#%d" % (d["file"], d["frame"])
    with open(os.path.join(root, "build", "coroutines.json")) as fh:
        for c in json.load(fh):
            ent.setdefault(int(c["entry"], 16), "%s@%s" % (c["kind"], c["entry"]))
    return ent


def behaviour_of(ent, starts, pc_abs):
    import bisect
    pc = pc_abs - vacmp.PROG_BASE
    i = bisect.bisect_right(starts, pc) - 1
    return ent[starts[i]] if i >= 0 else "?"


def main():
    seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 45
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    srv, port = vacmp.serve(os.path.join(root, "web"))
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
            page.evaluate(f"() => playFor({seconds})")
            tasks = live_tasks(page)
            browser.close()
    finally:
        srv.shutdown()
    ent = behaviour_index(root)
    starts = sorted(ent)
    objects = [t for t in tasks if t["prio"] == 100]
    print(f"uloh celkem {len(tasks)}, z toho priorita 100: {len(objects)}")
    for t in objects:
        print("  0x%05x  %-22s x %4d  y %7d  z %3d  hp %5d  trida %6d" %
              (t["adr"], behaviour_of(ent, starts, t["pc"]),
               t["x"], t["y"], t["z"], t["hp"], t["trida"]))


if __name__ == "__main__":
    main()
