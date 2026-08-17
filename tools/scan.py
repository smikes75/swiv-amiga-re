#!/usr/bin/env python3
"""Prohleda obraz diskety na zabalene bloky obou formatu.

Oba packery maji stejnou 8B hlavicku (delka rozbalenych / delka proudu),
takze se da projit disketa a zkusit rozbalit na kazdem kandidatovi.
Format B ma vlastni XOR soucet - u nej je nalez jisty. Format A soucet
nema, tam je dukazem to, ze rozbaleni probehne bez preteceni a spotrebuje
proud, ktery odpovida hlavicce.

    python3 tools/scan.py SWIVFIX.ADF [krok]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from depack import unpack_a, unpack_b        # noqa: E402


def plausible(data, off):
    if off + 8 > len(data):
        return False
    size = int.from_bytes(data[off:off + 4], "big")
    packed = int.from_bytes(data[off + 4:off + 8], "big")
    if not (64 <= size <= 1 << 20):
        return False
    if not (16 <= packed <= len(data) - off - 8):
        return False
    return packed <= size * 4          # packer, ktery nafoukne 4x, neexistuje


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "SWIVFIX.ADF"
    step = int(sys.argv[2]) if len(sys.argv) > 2 else 512
    data = open(src, "rb").read()

    cands = [o for o in range(0, len(data) - 8, step) if plausible(data, o)]
    print("%s: %d kandidatu s pravdepodobnou hlavickou (krok %d B)"
          % (src, len(cands), step))

    hits = []
    for off in cands:
        for name, fn in (("B", unpack_b), ("A", unpack_a)):
            try:
                blob, ok = fn(data, off)
            except Exception:
                continue
            if not ok:
                continue
            hits.append((off, name, len(blob), blob))
            print("  0x%06X sektor %4d  format %s  -> %7d B  %s"
                  % (off, off // 512, name, len(blob),
                     blob[:16].hex()))
            break

    print("\ncelkem %d bloku" % len(hits))
    if hits and len(sys.argv) > 3:
        out = sys.argv[3]
        os.makedirs(out, exist_ok=True)
        for off, name, n, blob in hits:
            open(os.path.join(out, "s%04d_%s.bin" % (off // 512, name)), "wb").write(blob)
        print("ulozeno do %s/" % out)


if __name__ == "__main__":
    main()
