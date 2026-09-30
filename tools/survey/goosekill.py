#!/usr/bin/env python3
"""Smrt bosse GOOSE v originalu se zaznamem registru Pauly.

Bezobsluzna jizda (vacmp.DRIVE_JS) bosse jen mine - zamek scrollu mu
kazdy snimek smaze a GOOSE po 2000 ticich odleti. Tenhle skript dojede
k nemu (TOWN, pozice ~58 556), zamek necha byt, drzi vrtulnik uprostred
s plnou zbrani a strili, dokud uloha bosse (gfx 0x17) nezmizi (bez plne
zbrane boss po 2 000 ticich odleti se 4 HP). Zapisy do AUD0..AUD3 a
potvrzeni zvukoveho IRQ se ulozi jako build/vacmp/sfx/trace_goose.json
ve formatu tools/sfxtrace.py, ktery pak `--jen-rozbor` porovna i synth
smrti 0x553a (dve vrstvy, zaklad 200 a 202) proti sfxBossDeathTimeline.

    python3 tools/survey/goosekill.py
"""
import base64
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "survey"))
import vacmp                                        # noqa: E402
from playwright.sync_api import sync_playwright     # noqa: E402

OUT = os.path.join(ROOT, "build", "vacmp", "sfx", "trace_goose.json")

JS = """(cfg) => {
  const m = VA.mem(), lay = VA.layout(), A6 = lay.a6, U = m.U, W = m.W, L = m.L, H = m.H;
  const boss = () => { let node = A6 - 698, g = 0;
    while (g++ < 500) { const nx = L(node + 4); if (!nx || !m.platna(nx)) return 0;
      if (W(nx + 274) === 100 && U(nx + 368) === 0x17) return nx; node = nx; } return 0; };
  // dojet k bossovi jako jizda (zamek instalace mazat, zivoty drzet)
  (JIZDA)({ od: cfg.od, limit: 60000 });
  VA.fn.joy(2, 10);                                   // rovne, uprostred
  const out = [], dv = new DataView(H.buffer), size = VA.fn.regTraceEntrySize();
  const IRQPC = lay.prog + 0x4b08;
  let k = 0, videl = 0, hp = null, mrtev = -1;
  while (k++ < cfg.limit) {
    m.w16(A6 + 11176 + 68, 0xffd8);                  // zivoty
    m.w16(A6 + 11176 + 102, 15);                     // plna zbran (0x70d6: +102 / 5)
    VA.fn.joy(2, (k % 2) ? 4 : 13);                  // palba co dva snimky
    VA.fn.regTrace(1); VA.fn.step(); VA.fn.regTrace(0);
    const n = VA.fn.regTraceCount(), base = VA.fn.regTracePtr();
    for (let i = 0; i < n; i++) {
      const o = base + i * size, r = dv.getUint16(o, true), pc = dv.getUint32(o + 4, true);
      if ((r >= 0xa0 && r < 0xe0) || (r === 0x9c && pc === IRQPC))
        out.push([k, dv.getUint16(o + 10, true), dv.getUint16(o + 12, true), r, dv.getUint16(o + 2, true), pc]);
    }
    const b = boss();
    if (b) { videl = k; hp = W(b + 360); }
    else if (videl && k - videl > 300) { mrtev = videl; break; }   // zmizel a nevratil se
  }
  VA.fn.joy(2, 13);
  return { prog: lay.prog, zapisy: out, snimku: k, bossVidenNaposled: videl, hp, pos: U(A6 + 3530) };
}""".replace("(JIZDA)", "(" + vacmp.DRIVE_JS + ")")


def main():
    srv, port = vacmp.serve(os.path.join(ROOT, "web"))
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(); page = br.new_page()
            page.set_default_timeout(3_600_000)
            page.goto(f"http://127.0.0.1:{port}/vacmp.html")
            page.wait_for_function("window.VA && window.VA.ready", timeout=60000)
            page.evaluate("([r, a]) => VA.boot(r, a)", [
                base64.b64encode(open(vacmp.ROM, "rb").read()).decode(),
                base64.b64encode(open(vacmp.ADF, "rb").read()).decode()])
            vacmp.prolog(page)
            r = page.evaluate(JS, {"od": 58600, "limit": 8000})
            br.close()
    finally:
        srv.shutdown()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"prog": r["prog"], "zapisy": r["zapisy"]}, open(OUT, "w"))
    print("snimku %d, boss naposled viden %d, hp %s, pozice %d, zapisu %d -> %s" %
          (r["snimku"], r["bossVidenNaposled"], r["hp"], r["pos"], len(r["zapisy"]), OUT))


if __name__ == "__main__":
    main()
