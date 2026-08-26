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
    from dispatch import behavior_dispatch
    dispatch = behavior_dispatch(prog)
    routes = {row["gfx"]: row["coroutine"] for row in dispatch}
    known_routes = {
        0x0404: 0x8048, 0x0014: 0x86BC, 0x0015: 0x862E,
        0x000E: 0xA6AE, 0x0011: 0x9B16, 0x000F: 0xA9E0,
        0x0010: 0x9B7E, 0x0058: 0x79D4, 0x0003: 0x9ECA, 0x180D: 0x994E,
        0x0013: 0xAB10, 0x0016: 0xAC12,
    }
    check("dispatch: 73 unikatnich gfx + zname rutiny TOWN",
          len(dispatch) == 73 and len(routes) == 73 and
          all(routes.get(gfx) == routine
              for gfx, routine in known_routes.items()))
    raw = [f for f in files if f[0].endswith(".RAW")]
    check("vsech 9 .RAW ma 40992 B (4 roviny 320x256 + paleta)",
          len(raw) == 9 and all(f[3] == 40992 for f in raw))

    print("grafika (docs/GRAPHICS.md):")
    import io
    cover = StreamC(data, files[32][1] + 4).unpack(files[32][3])
    pal = [int.from_bytes(cover[len(cover) - 32 + 2 * i:][:2], "big")
           for i in range(16)]
    check("COVER.RAW: paleta na konci je RGB12", all(v <= 0xFFF for v in pal))
    prog_pal = [int.from_bytes(prog[0x29BC + 2 * i:0x29BE + 2 * i], "big")
                for i in range(16)]
    check("paleta COVER == paleta v AMPROG.OBJ na 0x29BC", pal == prog_pal)
    import gfx
    lin_ok = lin_total = 0
    trans_hit = trans_all = 0
    for name, off, stored, size in files:
        if not name.endswith(".LIN"):
            continue
        blob = StreamC(data, off + 4).unpack(size)
        frames = gfx.lin_frames(blob)
        cnt_hdr = int.from_bytes(blob[:2], "big")
        p2 = 2 + sum(10 + len(pt["data"]) for f in frames for pt in f["parts"])
        lin_total += 1
        if len(frames) == cnt_hdr and p2 == len(blob):
            lin_ok += 1
        for f in frames:
            for pt in f["parts"]:
                wd = (pt["w"] + 15) // 16
                if pt["w"] and len(pt["data"]) == wd * 2 * 4 * pt["h"]:
                    trans_all += 1
    check("hlavicka = pocet LOGICKYCH snimku a proud konci presne",
          lin_ok == lin_total, "%d/%d" % (lin_ok, lin_total))
    check("geometrie dilu sedi na ceil(w/16)*2*4*h",
          trans_all > 900, "%d dilu" % trans_all)

    print("mapy urovni (docs/MAPS.md):")
    import map as swivmap
    disk = swivmap.Disk(src)
    stats = []
    object_gfx = []
    for lv in range(7):
        pam_name, dico = swivmap.level_info(disk, lv)
        tiles, objs, chk, h = swivmap.parse(disk.load(pam_name), dico)
        stats.append((pam_name, len(tiles), len(objs), h))
        object_gfx.extend(obj[2] for obj in objs)
    check("poradi map TOWN..FINAL podle tabulky 0x384C",
          [s0[0] for s0 in stats] == ["TOWN.PAM", "DESERT.PAM", "GRASS.PAM",
           "RIVER.PAM", "ICE.PAM", "SCIFI.PAM", "FINAL.PAM"])
    check("TOWN: 704 dlazdic, 155 objektu, vyska mapy 3441 px",
          stats[0][1:] == (704, 155, 3441))
    check("SCIFI je nejhustsi (1794 dlazdic)",
          stats[5][1] == 1794 and stats[5][1] == max(s0[1] for s0 in stats))
    g = swivmap.parse(disk.load("GRASS.PAM"), swivmap.level_info(disk, 2)[1])
    first_pal = g[2][0][1] if g[2] else []
    check("paleta GRASS z hlavicky mapy: barva 10 je zelena 0x366",
          len(first_pal) == 16 and any(p[1] == 0x366 for p in [(0, first_pal[10])]))
    check("dispatch pokryva vsech 1497 mapovych objektu",
          len(object_gfx) == 1497 and all(gfx in routes for gfx in object_gfx))

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
