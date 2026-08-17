#!/usr/bin/env python3
"""Graf volani AMPROG.OBJ: kdo koho vola (bsr/jsr) a kdo na koho miri
pres lea (data i kod). Vstupem je disassembly z objdump.

    python3 tools/xref.py [--top N] [--callers 0xADDR] [--callees 0xADDR]
"""

import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SYMS = json.load(open(os.path.join(HERE, "syms.json")))
NAME = {int(k, 16): v for k, v in SYMS["code"].items()}


def disasm():
    out = subprocess.run(
        ["m68k-elf-objdump", "-D", "-b", "binary", "-m", "m68k:68000",
         "build/files/001_AMPROG.OBJ"],
        capture_output=True, text=True).stdout
    return out.splitlines()


def build():
    calls = defaultdict(set)      # cil -> {volajici}
    leas = defaultdict(set)       # cil -> {misto}
    cur = None
    for ln in disasm():
        m = re.match(r"^\s+([0-9a-f]+):\t", ln)
        if not m:
            continue
        addr = int(m.group(1), 16)
        cur = addr
        m2 = re.search(r"\tbsr[sw]?\s+0x([0-9a-f]+)", ln)
        if m2:
            calls[int(m2.group(1), 16)].add(cur)
            continue
        m2 = re.search(r"\tjsr\s+0x([0-9a-f]+)", ln)
        if m2:
            calls[int(m2.group(1), 16)].add(cur)
            continue
        m2 = re.search(r"lea\s+%pc@\(0x([0-9a-f]+)\)", ln)
        if m2:
            leas[int(m2.group(1), 16)].add(cur)
    return calls, leas


def nm(a):
    return NAME.get(a, "") and "%s(0x%x)" % (NAME[a], a) or "0x%x" % a


def main():
    calls, leas = build()
    args = sys.argv[1:]
    if "--callers" in args:
        t = int(args[args.index("--callers") + 1], 16)
        for c in sorted(calls.get(t, []) | leas.get(t, [])):
            print("  0x%05x" % c)
        return
    top = int(args[args.index("--top") + 1]) if "--top" in args else 40
    cnt = Counter({a: len(s) for a, s in calls.items()})
    print("nejvolanejsi rutiny (sdilene utility):")
    for a, n in cnt.most_common(top):
        print("  %3dx  %s" % (n, nm(a)))
    print("\nnejodkazovanejsi data (lea):")
    lcnt = Counter({a: len(s) for a, s in leas.items()})
    for a, n in lcnt.most_common(15):
        print("  %3dx  %s" % (n, nm(a)))


if __name__ == "__main__":
    main()
