#!/usr/bin/env python3
"""Projde zavadeci retezec SWIVFIX.ADF a vysype vsechny jeho clanky.

Bootblock nacte tri kusy z konce diskety, jeden z nich zavola a do druheho
skoci. Dva z nich jsou zabalene a nesou si vlastni rozbalovaci rutinu.
Cely popis je v docs/FORMAT.md; tenhle skript to jen provede a ulozi
vysledky do build/, aby se na ne dalo divat.

    python3 tools/unboot.py SWIVFIX.ADF
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from depack import unpack_a, unpack_b        # noqa: E402

# Presne hodnety, ktere bootblock nastavuje do IOStdReq pred kazdym DoIO.
# (io_Data = kam v RAM, io_Offset = odkud na disketach, io_Length = kolik)
# Obal na 0x50000 presouva tenhle usek jinam a spousti ho: je to
# vlastni zavadec hry. move.w #0x73f,d7 + move.l (a1)+,(a0)+ = 1856 longwordu.
LOADER_OFF, LOADER_LEN = 0x1D8, 1856 * 4

CHUNKS = [
    # jmeno      RAM        disk       delka   rozbalit  data od
    ("c50000", 0x50000, 0x0D9400, 0x2C00, None, None),
    ("c30000", 0x30000, 0x0D5E00, 0x0A00, "b",  0xA0),
    ("c70000", 0x70000, 0x0D6A00, 0x1600, "a",  0x128),
]


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "SWIVFIX.ADF"
    out = sys.argv[2] if len(sys.argv) > 2 else "build"
    data = open(src, "rb").read()
    if len(data) != 901120:
        sys.exit("%s neni DD ADF (901120 B), ma %d B" % (src, len(data)))
    if data[:4] != b"DOS\x00":
        sys.exit("chybi magic DOS\\0 v bootblocku")
    os.makedirs(out, exist_ok=True)

    print("%s: %d B, bootblock %s, podpis %s"
          % (src, len(data), data[:4].decode(), data[8:12].decode("latin1")))
    print()

    for name, ram, off, length, fmt, hdr in CHUNKS:
        raw = data[off:off + length]
        path = os.path.join(out, name + ".bin")
        open(path, "wb").write(raw)
        print("%-8s disk 0x%06X (sektor %4d) %6d B -> RAM 0x%05X"
              % (name, off, off // 512, length, ram))
        if fmt is None:
            print("         nezabaleno (vlastni zavadec hry)")
            continue
        blob, ok = (unpack_a if fmt == "a" else unpack_b)(raw, hdr)
        dst = {"b": 0x40000, "a": 0x60000}[fmt]
        upath = os.path.join(out, "u%05X.bin" % dst)
        open(upath, "wb").write(blob)
        print("         rutina %s (data od 0x%X): %d B -> %d B (%.1f%%) na 0x%05X, soucet %s"
              % (fmt.upper(), hdr, length - hdr - 8, len(blob),
                 100.0 * (length - hdr - 8) / len(blob), dst,
                 "OK" if ok else "NESEDI"))

    # Blok na 0x50000 je obal opravy N.O.M.A.D. Vlastni zavadec hry je
    # tech 7424 B, ktere si obal presune do fast (nebo chip) RAM a skoci
    # do nich - viz docs/LOADER.md.
    c50 = data[CHUNKS[0][2]:CHUNKS[0][2] + CHUNKS[0][3]]
    loader = c50[LOADER_OFF:LOADER_OFF + LOADER_LEN]
    open(os.path.join(out, "loader.bin"), "wb").write(loader)
    print()
    print("loader.bin: %d B z 0x50000+0x%X - vlastni zavadec hry,"
          % (len(loader), LOADER_OFF))
    print("            obal ho presune do fast RAM a skoci do nej")

    print()
    print("bootblock pak dela:  jsr 0x70000   (rozbali na 0x60000)")
    print("                     jmp 0x30000   (rozbali na 0x40000, rts do nej)")
    print("0x40000 zapatkuje trap #0 do zavadece a skoci na 0x50070.")


if __name__ == "__main__":
    main()
