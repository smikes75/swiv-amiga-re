#!/usr/bin/env python3
"""Disassembler copper listu. Herne agnosticky.

Copper zna tri instrukce, kazda dve slova:
  MOVE  ($0RR, data)   bit0 prvniho slova = 0; RR je offset custom registru
  WAIT  (VP/HP, mask)  bit0 = 1, bit0 druheho slova = 0
  SKIP  (VP/HP, mask)  bit0 = 1, bit0 druheho slova = 1
Konec listu je WAIT $FFFF,$FFFE.

    python3 tools/copper.py               # vytahne z beziciho originalu
    python3 tools/copper.py soubor.bin    # rozebere ulozeny list
"""
import os
import sys

REG = {0x02: "DMACONR", 0x04: "VPOSR", 0x06: "VHPOSR", 0x1c: "INTENAR",
       0x08e: "DIWSTRT", 0x090: "DIWSTOP", 0x092: "DDFSTRT", 0x094: "DDFSTOP",
       0x096: "DMACON", 0x098: "CLXCON", 0x09a: "INTENA", 0x09c: "INTREQ",
       0x100: "BPLCON0", 0x102: "BPLCON1", 0x104: "BPLCON2",
       0x108: "BPL1MOD", 0x10a: "BPL2MOD", 0x088: "COPJMP1", 0x08a: "COPJMP2",
       0x080: "COP1LCH", 0x082: "COP1LCL", 0x084: "COP2LCH", 0x086: "COP2LCL"}


def regname(r):
    if r in REG:
        return REG[r]
    if 0x0e0 <= r < 0x100:
        return "BPL%dPT%s" % ((r - 0x0e0) // 4 + 1, "HL"[(r >> 1) & 1])
    if 0x110 <= r < 0x120:
        return "BPL%dDAT" % ((r - 0x110) // 2 + 1)
    if 0x120 <= r < 0x140:
        return "SPR%dPT%s" % ((r - 0x120) // 4, "HL"[(r >> 1) & 1])
    if 0x140 <= r < 0x180:
        n, k = (r - 0x140) // 8, ((r - 0x140) // 2) % 4
        return "SPR%d%s" % (n, ["POS", "CTL", "DATA", "DATB"][k])
    if 0x180 <= r < 0x1c0:
        return "COLOR%02d" % ((r - 0x180) // 2)
    if 0x0a0 <= r < 0x0e0:
        return "AUD%d%s" % ((r - 0x0a0) // 16,
                            ["LCH", "LCL", "LEN", "PER", "VOL", "DAT"][((r - 0x0a0) % 16) // 2])
    return "$%03X" % r


def disassemble(data, base=0, limit=4096):
    """Vrati seznam radku (adresa, text). Konci na WAIT $FFFF,$FFFE."""
    out = []
    for i in range(0, min(len(data) - 3, limit * 4), 4):
        w1 = (data[i] << 8) | data[i + 1]
        w2 = (data[i + 2] << 8) | data[i + 3]
        addr = base + i
        if w1 & 1:
            vp, hp = (w1 >> 8) & 0xff, w1 & 0xfe
            kind = "SKIP" if (w2 & 1) else "WAIT"
            if w1 == 0xffff and w2 == 0xfffe:
                out.append((addr, "END   (WAIT $FFFF,$FFFE)"))
                break
            out.append((addr, "%-5s VP=%3d HP=%3d  mask=$%04X" %
                        (kind, vp, hp, w2 & 0xfffe)))
        else:
            r = w1 & 0x1fe
            out.append((addr, "MOVE  %-9s <- $%04X" % (regname(r), w2)))
    return out


def from_original():
    """Vytahne aktivni copper list z beziciho originalu pres harness."""
    import base64
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(root, "tools", "survey"))
    import vacmp
    from playwright.sync_api import sync_playwright
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
            page.evaluate("() => playFor(20)")
            # COP1LC precteme z trace: posledni zapis do 0x080/0x082
            info = page.evaluate("""() => {
              VA.regTrace(true); VA.run(2, null); VA.regTrace(false);
              const t = VA.regTraceRead();
              let hi = null, lo = null;
              for (const e of t) {
                if (e.reg === 0x080) hi = e.value;
                if (e.reg === 0x082) lo = e.value;
              }
              return { hi, lo };
            }""")
            if info["hi"] is None:
                # copper se uz nepreprogramovava; vezmeme hodnotu z registru
                info = page.evaluate("""() => {
                  VA.fn.shell('regs'); VA.run(1, null);
                  return { hi: null, lo: null, text: VA.fn.shellText().slice(-600) };
                }""")
            addr = ((info["hi"] or 0) << 16) | (info["lo"] or 0)
            data = base64.b64decode(page.evaluate("([o, n]) => VA.chip(o, n)",
                                                  [addr, 4096])) if addr else b""
            browser.close()
    finally:
        srv.shutdown()
    return addr, data


def main():
    if len(sys.argv) > 1:
        data = open(sys.argv[1], "rb").read()
        base = 0
    else:
        base, data = from_original()
        if not data:
            sys.exit("copper list se nepodarilo najit (COP1LC nebyl prepsan)")
        print("COP1LC = $%06X" % base)
    for addr, text in disassemble(data, base):
        print("  $%06X  %s" % (addr, text))


if __name__ == "__main__":
    main()
