#!/usr/bin/env python3
"""Extraktor souboru ze SWIVFIX.ADF - prepis cteciho automatu zavadece.

Disketa nema filesystem; ma katalog a soubory ulozene proudove za sebou
(bajtove, ne sektorove zarovnane - proto je nenasel scan.py). Vsechno
nize je prepis rutin z build/loader.bin, viz docs/CATALOG.md:

  0x71a  nacteni katalogu       0x7d6  otevreni souboru podle indexu
  0x1ec  hledani jmena          0xa14  cteci automat (format C)

Rozvrzeni (offsety od zacatku souborove oblasti = stopa 1 = disk 5632):

  +0            word   pocet souboru N
  +2            N longu  ulozene delky
  +2+4*N        soubor 0, soubor 1, ... tesne za sebou

Soubor: long rozbalena delka + proud formatu C. Soubor 0 je tabulka
jmen (radky oddelene \n, poradi = indexy).

Format C je treti packer na diskete - proudovy, aby sel rozbalovat
primo pri cteni ze stopy: stridave bloky literalu a zapasu pres 1KB
kruhovy buffer. Literaly se kopiruji BAJTOVE ZAROVNANE primo z proudu
(rychlost); bitova cteci drzi rozpracovany bajt pres ne.

    python3 tools/extract.py SWIVFIX.ADF build/files
"""

import os
import sys

TRACK = 5632                    # 11 sektoru; zavadec: divu #5632 + addq #1
BASE = TRACK                    # souborova oblast zacina na stope 1


class StreamC:
    """Cteci automat formatu C (rutiny 0x966/0xa14/0xb52/0xaee/0xb1e)."""

    def __init__(self, data, pos):
        self.data = data
        self.pos = pos          # bajtovy proud (literal + doplnovani bitu)
        self.d6 = 0             # rozpracovany bajt, MSB napred
        self.d5 = 0             # kolik bitu v nem zbyva

    def byte(self):
        b = self.data[self.pos]
        self.pos += 1
        return b

    def bit(self):
        self.d5 -= 1
        if self.d5 < 0:         # dbf: 0 -> -1 = dosly, dobrat
            self.d6 = self.byte()
            self.d5 = 7
        b = (self.d6 >> 7) & 1
        self.d6 = (self.d6 << 1) & 0xFF
        return b

    def bits(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | self.bit()
        return v

    def code(self):
        """Delkovy kod (0xb52): 0 | 1xx: 1-3 | 111xx: 4-6 | 11111+11b: 0-2047.

        Pozor: posledni forma neni smycka, ale JEDENACTKRAT rozbaleny
        getbit (0xba2..0xc26) - snadno se splete s desetibitovym
        offsetem (0xaee), ktery smycka je."""
        if not self.bit():
            return 0
        v = self.bits(2) + 1
        if v != 4:
            return v
        v = (1 << 2) | self.bits(2)
        if v != 7:
            return v
        return self.bits(11)

    def unpack(self, size):
        """Rozbali size bajtu (0xa14). Kazdy soubor zacina cistym stavem."""
        out = bytearray()
        ring = bytearray(1024)
        rpos = 0
        literal = True          # ~V_MODE (-1100): zacina se literaly
        rem = 0                 # zbytek bloku (-1116)
        off = 0
        while len(out) < size:
            if rem == 0:
                if literal:
                    rem = self.code()
                else:
                    off = self.bits(10)         # offset PRED delkou (0xa58)
                    n = self.code() + 2         # 0xb10
                    rem = n if n <= 63 else 0
            take = min(size - len(out), rem)
            flip = rem <= size - len(out)       # blok se timhle dobere
            if literal:
                for _ in range(take):
                    b = self.byte()             # bajtove zarovnane!
                    out.append(b)
                    ring[rpos] = b
                    rpos = (rpos + 1) & 1023
            else:
                src = (rpos - off) & 1023
                for _ in range(take):
                    b = ring[src]
                    out.append(b)
                    ring[rpos] = b
                    src = (src + 1) & 1023
                    rpos = (rpos + 1) & 1023
            rem -= take
            if flip:
                literal = not literal
        return bytes(out)


def catalog(data):
    """Vrati [(jmeno, disk_offset, ulozeno, rozbaleno)] pro vsechny soubory."""
    cnt = int.from_bytes(data[BASE:BASE + 2], "big")
    lens = [int.from_bytes(data[BASE + 2 + 4 * i:BASE + 6 + 4 * i], "big")
            for i in range(cnt)]
    offs = []
    p = BASE + 2 + 4 * cnt
    for n in lens:
        offs.append(p)
        p += n

    def unpacked(i):
        return int.from_bytes(data[offs[i]:offs[i] + 4], "big")

    # soubor 0 = tabulka jmen, radky \n, poradi = indexy
    names_blob = StreamC(data, offs[0] + 4).unpack(unpacked(0))
    names = names_blob.decode("latin1").split("\n")
    if len(names) < cnt:
        names += ["FILE%03d" % i for i in range(len(names), cnt)]
    return [(names[i].strip() or "FILE%03d" % i, offs[i], lens[i], unpacked(i))
            for i in range(cnt)]


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "SWIVFIX.ADF"
    out = sys.argv[2] if len(sys.argv) > 2 else None
    data = open(src, "rb").read()
    files = catalog(data)
    total_p = total_u = 0
    for i, (name, off, stored, size) in enumerate(files):
        total_p += stored
        total_u += size
        line = "%3d  %-14s disk 0x%06X  %6d -> %7d B" % (i, name, off, stored, size)
        if out:
            blob = StreamC(data, off + 4).unpack(size)
            safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
            os.makedirs(out, exist_ok=True)
            open(os.path.join(out, "%03d_%s" % (i, safe)), "wb").write(blob)
            line += "  ok"
        print(line)
    print("\n%d souboru, %d B zabaleno -> %d B rozbaleno (%.1f%%)"
          % (len(files), total_p, total_u, 100.0 * total_p / max(total_u, 1)))


if __name__ == "__main__":
    main()
