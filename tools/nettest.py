#!/usr/bin/env python3
"""Sedmy kontrakt: dva prohlizece opravdu odehraji tutez hru po siti.

`tools/lockstep.py` dokazuje, ze simulace je prenositelna. Tenhle skript
overuje vrstvu NAD ni: rucni parovani, datovy kanal, vstupni zpozdeni a
detektor rozjezdu. Bezi v REALNEM CASE s normalnim `requestAnimationFrame`,
tedy presne tou cestou, kterou pujde skutecny hrac - ne pres stubnutou
smycku jako ostatni kontrakty.

Kdyz je k dispozici WebKit, hostitel bezi ve V8 a host v JavaScriptCore,
takze se zaroven meri, ze si rozumi dva RUZNE enginy.

    python3 tools/nettest.py
    python3 tools/nettest.py --sekundy 10
"""
import os
import sys
import time

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Vstupni skript: od tiku T drz tyhle klavesy. Kazda strana ma svuj,
# protoze po siti sedi u kazdeho stroje jeden hrac.
SCRIPT_HOST = [(0, "f"), (60, "lf"), (140, "rf"), (240, "uf")]
SCRIPT_GUEST = [(0, "f"), (40, "rf"), (120, "df"), (200, "lfj")]

DRIVER_JS = """([script]) => {
  // Vstup se nevklada klavesnici, ale primo do lokalniho umyslu - jde
  // o test site, ne odchytavani klaves. Hook bezi v rAF, tedy ve stejnem
  // rytmu jako hra.
  window.__log = [];
  const pump = () => {
    const g = state.g;
    if (g && NET.active) {
      let k = "";
      for (const [od, klavesy] of script) if (g.tick >= od) k = klavesy;
      const next = {};
      for (const c of k) next[c] = true;
      g.netLocal = next;
      window.__log.push([g.tick, netStateHash(g)]);
    }
    requestAnimationFrame(pump);
  };
  requestAnimationFrame(pump);
}"""


def open_page(pw, engine):
    b = getattr(pw, engine).launch()
    page = b.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto("file://" + os.path.join(ROOT, "game.html"))
    page.set_input_files("#fpick", os.path.join(ROOT, "SWIVFIX.ADF"))
    page.wait_for_selector("#titlewrap", state="visible", timeout=60000)
    return b, page, errs


def main():
    sekundy = 8
    if "--sekundy" in sys.argv:
        sekundy = int(sys.argv[sys.argv.index("--sekundy") + 1])

    with sync_playwright() as pw:
        engines = ["chromium", "chromium"]
        try:
            pw.webkit.executable_path and engines.__setitem__(1, "webkit")
        except Exception:
            pass
        ba, pa, ea = open_page(pw, engines[0])
        bb, pb, eb = open_page(pw, engines[1])
        try:
            print(f"hostitel: {engines[0]}, host: {engines[1]}")

            # --- rucni parovani, presne jak ho dela hrac ---------------
            pa.click("#nethost")
            pa.wait_for_function(
                "() => document.querySelector('#netout').value.length > 100",
                timeout=30000)
            offer = pa.evaluate("() => document.querySelector('#netout').value")
            print(f"  nabidka hostitele: {len(offer)} znaku")

            pb.click("#netjoin")
            pb.fill("#netin", offer)
            pb.click("#netgo")
            pb.wait_for_function(
                "() => document.querySelector('#netout').value.length > 100",
                timeout=30000)
            answer = pb.evaluate("() => document.querySelector('#netout').value")
            print(f"  odpoved hosta:     {len(answer)} znaku")

            pa.fill("#netin", answer)
            pa.click("#netgo")

            for page, kdo in ((pa, "hostitel"), (pb, "host")):
                page.wait_for_function("() => NET.active", timeout=30000)
            print("  spojeno, hra bezi")

            pa.evaluate(DRIVER_JS, [SCRIPT_HOST])
            pb.evaluate(DRIVER_JS, [SCRIPT_GUEST])
            time.sleep(sekundy)

            # Kontrola, ze jde opravdu o hru DVOU hracu: host se pripojil
            # jako jeep tim, ze drzi palbu (tryJoinJeep, stoji kredit).
            dvojice = [p.evaluate("() => ({ jeep: !!state.g.player2, "
                                  "hraci: state.g.players })")
                       for p in (pa, pb)]

            la = pa.evaluate("() => window.__log")
            lb = pb.evaluate("() => window.__log")
            stav = [p.evaluate("() => ({ tick: state.g.tick, "
                               "aktivni: NET.active, rozjezd: NET.desync, "
                               "ceka: NET.waiting })") for p in (pa, pb)]
            if ea or eb:
                sys.exit(f"chyby stranek: {(ea + eb)[:4]}")

            # --- detektor rozjezdu: musi umet SELHAT ------------------
            # Bez teto zkousky by prosel i detektor, ktery nic nehlida.
            # Posuneme hraci na jedne strane polohu a cekame, az si toho
            # porovnani otisku vsimne.
            print("  cisty beh hotov, zkousim detektor rozjezdu…")
            pa.evaluate("() => { state.g.player.x += 3; }")
            konec = time.time() + 8
            chyceno = False
            while time.time() < konec:
                chyceno = any(p.evaluate("() => NET.desync !== null")
                              for p in (pa, pb))
                if chyceno:
                    break
                time.sleep(0.25)
            detektor = {"chyceno": chyceno,
                        "tik": pa.evaluate("() => NET.desync")
                               or pb.evaluate("() => NET.desync")}
        finally:
            ba.close(); bb.close()

    print("  po cistem behu:")
    for s, d, kdo in zip(stav, dvojice, ("hostitel", "host")):
        print(f"    {kdo:9s} tik {s['tick']:5d}, spojeni "
              f"{'drzi' if s['aktivni'] else 'PADLO'}"
              f", rozjezd {s['rozjezd']}, jeep {d['jeep']}"
              f", hracu {d['hraci']}")
    if detektor["chyceno"]:
        print(f"  detektor rozjezdu pak zabral na umely "
              f"rozdil (tik {detektor['tik']})")

    problemy = []
    if not all(d["jeep"] and d["hraci"] == 2 for d in dvojice):
        problemy.append("host se nepripojil jako druhy hrac")
    if not detektor["chyceno"]:
        problemy.append("detektor rozjezdu NEZABRAL - umely rozdil stavu "
                        "proslo bez povsimnuti")
    if not all(s["aktivni"] for s in stav):
        problemy.append("spojeni behem hry padlo")
    if any(s["rozjezd"] is not None for s in stav):
        problemy.append("detektor ohlasil rozjezd simulaci")

    # Otisky tychz tiku se musi shodovat na obou stranach.
    ha = dict(la); hb = dict(lb)
    spolecne = sorted(set(ha) & set(hb))
    neshody = [t for t in spolecne if ha[t] != hb[t]]
    if len(spolecne) < 100:
        problemy.append(f"prilis malo spolecnych tiku ({len(spolecne)})")
    if neshody:
        problemy.append(f"{len(neshody)} tiku s ruznym stavem "
                        f"(prvni {neshody[0]})")

    print(f"  {len(spolecne)} spolecnych tiku, {len(neshody)} neshod")
    if problemy:
        print("\nNETTEST SELHAL:")
        for x in problemy:
            print("  - " + x)
        sys.exit(1)
    print(f"\nNETTEST OK: obe strany odehraly {len(spolecne)} tiku se "
          f"shodnym stavem")


if __name__ == "__main__":
    main()
