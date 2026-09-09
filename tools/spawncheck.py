#!/usr/bin/env python3
"""Paty kontrakt: kazdy mapovy objekt se rodi presne na sve aktivacni marzi.

`0x9ac8` (volane z `a2c6`) drzi korutinu, dokud `y - D2 < kamera`, tedy pusti
ji pri `ys >= D2`. Ocekavany okamzik proto plyne primo z mapy jako
`ujeto = margin + zero - y` a neni k nemu potreba original ani emulator.

Ocekavani se pocita az v okamziku `taskStarted` (prah -256): nektera chovani
do te chvile jeste meni `y` nebo si urcuji vlastni marzi (`xevswarm` posune
rodici y o -27, `airplane` si nastavi 176, jeho dite 127). Paruje se pres
poradi vzniku, ne polohu - `tank` a `train` si `x` pri vzniku prepisou.

Zmereno 2026-09-09 na celem retezu sedmi map: 981 ocekavanych aktivaci,
z toho 980 presne na 0 px. Jedina vyjimka `inst5` je artefakt kontroly:
FINAL boss ceka na `g.inst1Factories > 0`, coz skript nuluje, aby obesel
scroll lock u DESERT tovarny (bez palby by ji hrac nezniicil).

    python3 tools/spawncheck.py            # cely retez map
    python3 tools/spawncheck.py 9000       # jen kus
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import objdiff                                       # noqa: E402

FULL = 27000            # cely retez TOWN..FINAL
ALLOWED = {"inst5"}     # viz hlavicka: ceka na aktivni instalaci


def main():
    dist = int(sys.argv[1]) if len(sys.argv) > 1 else FULL
    ok, late, missing, extra = objdiff.predict(dist)
    problems = []
    if late:
        problems.append(f"{late} objektu se rodi jinde, nez rika jejich marze")
    if extra:
        problems.append(f"{extra} aktivaci navic, ktere mapa necekala")
    if missing > len(ALLOWED):
        problems.append(f"{missing} objektu se nerodi vubec "
                        f"(povoleno {len(ALLOWED)}: {', '.join(sorted(ALLOWED))})")
    if problems:
        print("\nSPAWNCHECK SELHAL:")
        for p in problems:
            print("  - " + p)
        sys.exit(1)
    print(f"\nSPAWNCHECK OK: {ok} aktivaci presne na sve marzi "
          f"(+{missing} znama vyjimka)")


if __name__ == "__main__":
    main()
