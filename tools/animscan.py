#!/usr/bin/env python3
"""Vytezi animacni skripty z AMPROG.OBJ.

Interpret (0x6cd6/0x6ce8) cte proud wordu: kladny word je graficke
slovo `snimek<<9 | soubor` (zobraz a cekej), word s bitem 15 je prikaz
- opcode v bitech 11-14 (tabulka 0x6d0c), argument v bitech 0-10:

  0 konec (vypnout)     3 nastav pocitadlo smycky   6 nastav periodu
  1 zabij objekt        4 nastav offset             7 OR priznaku
  2 smycka (dec+skok)   5 pricti offset             8 AND priznaku

Skript nelze najit podle referenci (jsou pc-relativni v kodu vsude
mozne), ale lze VALIDOVAT podle dat: graficka slova musi ukazovat na
existujici soubor a snimek. Skener projde AMPROG a hlasi bloky, kde
vsechna slova davaji smysl a sekvence konci koncovym prikazem.

    python3 tools/animscan.py > docs/ANIMS.md
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from map import Disk                      # noqa: E402

OPS = {0: "end", 1: "kill", 2: "loop", 3: "count", 4: "setofs",
       5: "addofs", 6: "period", 7: "orflag", 8: "andflag"}
TERMINAL = {0, 1, 2}


def scan(disk):
    prog = disk.prog
    nfiles = len(disk.order)
    counts = {}

    def valid_gfx(w):
        f = w & 0x1FF
        if f >= nfiles or not disk.order[f].endswith(".LIN"):
            return False
        if f not in counts:
            try:
                counts[f] = len(disk.frames(disk.order[f]))
            except Exception:
                counts[f] = 0
        return (w >> 9) < counts[f]

    found = []
    o = 0
    while o < len(prog) - 6:
        # Word bezprostredne za Bcc.W/BSR.W je displacement strojove
        # instrukce, ne prvni prikaz animace. Nahodou casto vypada jako
        # platny flag opcode (napr. POPUP 0xa6e6, GOOSE 0xc7fa) a posune
        # jinak spravny kandidat o dva bajty zpet.
        if o >= 2 and 0x60 <= prog[o - 2] <= 0x6F and prog[o - 1] == 0:
            o += 2
            continue
        # kandidat zacina grafickym slovem nebo prikazem "period"
        seq = []
        p = o
        gfx = cmds = 0
        files = set()
        while p < len(prog) - 1 and len(seq) < 96:
            w = (prog[p] << 8) | prog[p + 1]
            if w & 0x8000:
                op = (w >> 11) & 15
                if op not in OPS:
                    break
                seq.append(("cmd", op, w & 0x7FF))
                cmds += 1
                p += 2
                if op in TERMINAL:
                    break
                continue
            if not valid_gfx(w) or w == 0:
                break
            seq.append(("gfx", w >> 9, disk.order[w & 0x1FF]))
            files.add(w & 0x1FF)
            gfx += 1
            p += 2
        ok = (gfx >= 2 and cmds >= 1 and seq and seq[-1][0] == "cmd"
              and seq[-1][1] in TERMINAL and len(files) <= 2)
        if ok:
            found.append((o, seq))
            o = p + 2
        else:
            o += 2
    return found


def main():
    disk = Disk()
    found = scan(disk)
    print("# Animacni skripty vytezene z AMPROG.OBJ")
    print()
    print("%d kandidatu (validace: vsechna graficka slova ukazuji na" % len(found))
    print("existujici snimky, sekvence konci koncovym prikazem).")
    print()
    for o, seq in found:
        parts = []
        for it in seq:
            if it[0] == "gfx":
                parts.append("%s#%d" % (it[2].replace(".LIN", ""), it[1]))
            else:
                parts.append("%s(%d)" % (OPS[it[1]], it[2]))
        print("- `0x%05X`: %s" % (o, " ".join(parts)))


if __name__ == "__main__":
    main()
