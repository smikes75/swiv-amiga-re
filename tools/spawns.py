#!/usr/bin/env python3
"""Spawn tabulky vsech urovni -> docs/OBJECTS.md + build/spawns.json.

Z map (.PAM) vytezi vsechny objektove zaznamy: soubor, snimek, TYP
(= selektor chovani v enginu) a pocty. Zaklad pro dekompilaci
chovani: stejna grafika s ruznym typem = ruzne chovani.
"""

import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from map import Disk, level_info, parse   # noqa: E402

LEVELS = ["TOWN", "DESERT", "GRASS", "RIVER", "ICE", "SCIFI", "FINAL"]


def main():
    disk = Disk()
    out = {}
    md = ["# Objekty a typy chovani (vytezeno z map)", "",
          "TYP je index chovani v enginu - tataz grafika s jinym typem",
          "se chova jinak (MEDTANK ma v TOWN typy 1,2,3,4). Mapovani",
          "typ -> rutina zbyva precist z dispatche objektu.", ""]
    for lv in range(7):
        pam, dico = level_info(disk, lv)
        tiles, objs, checks, h = parse(disk.load(pam), dico)
        c = Counter()
        rows = []
        for y, x, gfx, layer, typ in objs:
            fn = disk.order[gfx & 0x1FF]
            c[(fn, gfx >> 9, typ)] += 1
            rows.append({"ry": y, "x": x, "file": fn, "frame": gfx >> 9,
                         "typ": typ})
        out[LEVELS[lv]] = rows
        md += ["## %d — %s (%d objektu)" % (lv, LEVELS[lv], len(objs)), "",
               "| soubor | snimek | typ | pocet |", "|---|---|---|---|"]
        for (fn, fi, typ), n in sorted(c.items(), key=lambda kv: -kv[1]):
            md.append("| %s | %d | %d | %d |" % (fn, fi, typ, n))
        md.append("")
        types = Counter(t for (_, _, t) in c)
        md.append("typy v urovni: %s" %
                  ", ".join("%d (%d druhu)" % (t, n)
                            for t, n in sorted(types.items())))
        md.append("")
    os.makedirs("build", exist_ok=True)
    json.dump(out, open("build/spawns.json", "w"), indent=1)
    open("docs/OBJECTS.md", "w", encoding="utf-8").write("\n".join(md))
    print("docs/OBJECTS.md + build/spawns.json")
    all_types = Counter()
    for rows in out.values():
        for r in rows:
            all_types[r["typ"]] += 1
    print("typy celkem:", dict(sorted(all_types.items())))


if __name__ == "__main__":
    main()
