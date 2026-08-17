#!/usr/bin/env python3
"""Overovaci kontrakt projektu - jedina pravda o tom, co je dokazane.

Kazde tvrzeni z docs/ ma tady radek, ktery ho zmeri. Kdyz kontrakt
prochazi, dokumentace neni nazor, ale zapis mereni.

    python3 tools/check.py [SWIVFIX.ADF]
"""

import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from depack import unpack_a, unpack_b        # noqa: E402
from unboot import CHUNKS, LOADER_OFF, LOADER_LEN   # noqa: E402

# Vsechna cisla nize jsou premerena z tohoto obrazu. Jiny crack bude mit
# jine offsety - kontrakt to ohlasi, misto aby mlcky meril nesmysly.
ADF_SHA = "13d8beba136d433971379cc5eb6d6d7707e5cb7874c28301ba57583baa41cb5a"

FAILS = []


def check(name, ok, detail=""):
    print("  %s %s%s" % ("OK " if ok else "FAIL", name,
                         ("  (%s)" % detail) if detail else ""))
    if not ok:
        FAILS.append(name)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "SWIVFIX.ADF"
    if not os.path.exists(src):
        sys.exit("%s neexistuje - obraz diskety si dodej sam, viz README" % src)
    data = open(src, "rb").read()

    print("obraz:")
    sha = hashlib.sha256(data).hexdigest()
    if sha != ADF_SHA:
        print("  POZOR: jiny obraz nez ten premereny (SHA %s...)" % sha[:16])
        print("  Kontrakt plati jen pro overeny SWIVFIX.ADF; koncim.")
        sys.exit(1)
    check("SHA-256 souhlasi s README", True)
    check("velikost DD ADF", len(data) == 901120, "%d B" % len(data))
    check("bootblock magic DOS\\0", data[:4] == b"DOS\x00")
    check("podpis YETI misto rootblocku", data[8:12] == b"YETI")

    def bootsum(b):
        s = 0
        for i in range(0, 1024, 4):
            v = int.from_bytes(b[i:i + 4], "big") if i != 4 else 0
            s += v
            if s > 0xFFFFFFFF:
                s = (s & 0xFFFFFFFF) + 1
        return (~s) & 0xFFFFFFFF
    check("kontrolni soucet bootblocku",
          bootsum(data[:1024]) == int.from_bytes(data[4:8], "big"))

    print("dekrunchery:")
    raws = {}
    for name, ram, off, length, fmt, hdr in CHUNKS:
        raws[name] = data[off:off + length]

    b_out, b_ok = unpack_b(raws["c30000"], 0xA0)
    check("format B: vlastni XOR soucet", b_ok)
    check("format B: delka 2408 B", len(b_out) == 2408)
    check("format B: zacina platnym kodem (lea pc)",
          b_out[:2] == b"\x49\xfa")
    check("format B: nese zaplatu trap #0 a DSKLEN",
          b"\x00\xdf\xf0\x24" in b_out)

    a_out, _ = unpack_a(raws["c70000"], 0x128)
    check("format A: delka 21548 B", len(a_out) == 21548)
    check("format A: retezec puvodu (Storm/Sales Curve)",
          b"S.W.I.V from Storm/The Sales Curve" in a_out)
    check("format A: podpis opravy N.O.M.A.D",
          b"N.O.M.A.D" in a_out)

    print("zavadec hry:")
    loader = raws["c50000"][LOADER_OFF:LOADER_OFF + LOADER_LEN]
    check("delka 7424 B", len(loader) == LOADER_LEN)
    check("retezec AMPROG.OBJ na 0x592",
          loader[0x592:0x59C] == b"AMPROG.OBJ")
    check("baze promennych: lea 0x16DC(pc),a6 na 0xE6",
          loader[0xE6:0xEA] == b"\x4d\xfa\x15\xf4")
    check("cte disk primo pres CIA-B PRB",
          b"\x00\xbf\xd1\x00" in loader)
    check("zadny trackdisk: v zavadeci neni exec jsr -456",
          b"\x4e\xae\xfe\x38" not in loader)

    print("katalog a soubory (docs/CATALOG.md):")
    from extract import catalog, StreamC
    files = catalog(data)
    check("128 souboru", len(files) == 128)
    check("soubor 0 je AMDLS0.CAT", files[0][0] == "AMDLS0.CAT")
    check("soubor 1 je AMPROG.OBJ", files[1][0] == "AMPROG.OBJ")
    check("AMPROG.OBJ: 55668 B rozbaleno", files[1][3] == 55668)
    check("soubory tesne za sebou (offsety konzistentni)",
          all(files[i][1] + files[i][2] == files[i + 1][1]
              for i in range(len(files) - 1)))
    hs = StreamC(data, files[2][1] + 4).unpack(files[2][3])
    check("HS1.TXT zacina JOHN BOY", hs.startswith(b"JOHN BOY"))
    mod = StreamC(data, files[18][1] + 4).unpack(files[18][3])
    check("AMTITUNE.MOD: ProTracker M.K., nazev swiv-title",
          mod[1080:1084] == b"M.K." and mod.startswith(b"swiv-title"))
    prog = StreamC(data, files[1][1] + 4).unpack(files[1][3])
    check("AMPROG.OBJ zacina bra.w", prog[:2] == b"\x60\x00")
    raw = [f for f in files if f[0].endswith(".RAW")]
    check("vsech 9 .RAW ma 40992 B (4 roviny 320x256 + paleta)",
          len(raw) == 9 and all(f[3] == 40992 for f in raw))

    print("negativni nalezy (drzi docs/LOADER.md poctive):")
    from scan import plausible
    cands = [o for o in range(0, len(data) - 8, 512) if plausible(data, o)]
    check("zadne samostatne zabalene bloky po sektorech", len(cands) == 0,
          "%d kandidatu" % len(cands))

    print()
    if FAILS:
        sys.exit("KONTRAKT NEPROSEL: " + ", ".join(FAILS))
    print("kontrakt: OK - dokumentace odpovida obrazu")


if __name__ == "__main__":
    main()
