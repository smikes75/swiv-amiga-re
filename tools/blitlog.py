#!/usr/bin/env python3
"""Logger blitteru: slozi z trace zapisu jednotlive blit operace.

Blitter se programuje po registrech a spousti zapisem do `BLTSIZE`, takze
jedna operace je "stav registru v okamziku zapisu do $058". Skript stav drzi
a pri kazdem `BLTSIZE` vyda radek: minterm, zapnute zdroje, rozmer, moduly,
ukazatele a **PC**, ktere operaci spustilo.

Herne agnosticky - potrebuje jen harness s `tools/vamiga-regtrace.patch`.

    python3 tools/blitlog.py [snimku]     # vychozi 6
"""
import base64
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "survey"))
import vacmp                                        # noqa: E402
from playwright.sync_api import sync_playwright     # noqa: E402

MINTERM = {0xf0: "D = A            (kopie)",
           0xca: "D = A?B:C        (cookie-cut, klasicky BOB)",
           0x0a: "D = C & ~A       (vymaskovani)",
           0xa0: "D = A & C",
           0xfc: "D = A | B",
           0x00: "D = 0            (mazani)"}


def collect(frames):
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
            page.evaluate("() => playFor(20)")
            tr = page.evaluate("""(n) => { VA.regTrace(true); VA.run(n, null);
                VA.regTrace(false); return VA.regTraceRead(); }""", frames)
            browser.close()
    finally:
        srv.shutdown()
    return tr


def blits_from(trace):
    st, out = {}, []
    for e in trace:
        r, v = e["reg"], e["value"]
        if not (0x040 <= r <= 0x066):
            continue
        if r != 0x058:
            st[r] = v
            continue
        w = (v & 0x3f) or 64
        out.append({"pc": e["pc"], "w": w, "h": v >> 6,
                    "con0": st.get(0x040, 0), "con1": st.get(0x042, 0),
                    "amod": st.get(0x064, 0), "bmod": st.get(0x062, 0),
                    "cmod": st.get(0x060, 0), "dmod": st.get(0x066, 0),
                    "apt": (st.get(0x050, 0) << 16) | st.get(0x052, 0),
                    "dpt": (st.get(0x054, 0) << 16) | st.get(0x056, 0)})
    return out


def main():
    frames = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    blits = blits_from(collect(frames))
    print("blit operaci za %d snimku: %d  (%.0f na snimek)" %
          (frames, len(blits), len(blits) / max(1, frames)))
    print("\nmintermy:")
    for m, k in Counter(b["con0"] & 0xff for b in blits).most_common():
        print("   0x%02x  %5dx   %s" % (m, k, MINTERM.get(m, "")))
    print("\nzapnute zdroje (BLTCON0 bity 11..8 = A B C D):")
    for s, k in Counter((b["con0"] >> 8) & 0xf for b in blits).most_common():
        lbl = "".join(n for bit, n in ((8, "A"), (4, "B"), (2, "C"), (1, "D")) if s & bit)
        print("   %-4s %5dx" % (lbl, k))
    print("\nodkud se spousti:")
    for pc, k in Counter(b["pc"] for b in blits).most_common():
        off = pc - vacmp.PROG_BASE
        kde = "AMPROG +0x%04x" % off if 0 <= off < 55668 else "0x%06x" % pc
        print("   %-18s %5dx" % (kde, k))
    print("\nnejcastejsi rozmery:")
    for (w, h), k in Counter((b["w"], b["h"]) for b in blits).most_common(8):
        print("   %3d slov x %3d radku = %3d x %3d px   %4dx" % (w, h, w * 16, h, k))


if __name__ == "__main__":
    main()
