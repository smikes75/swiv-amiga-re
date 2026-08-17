#!/usr/bin/env python3
"""Inventura spawnu korutin v AMPROG: najde vsechna mista
`lea X(pc),a0` nasledovana volanim zakladace (task/child/anim...)
a vypise vstupni body chovani. Vysledek: build/coroutines.json.
"""

import json
import re
import subprocess
from collections import Counter

SPAWNERS = {0x60f8: 'task', 0x6144: 'anim_task', 0x614a: 'anim_task2',
            0x6178: 'child', 0x6160: 'clone', 0x653e: 'anim',
            0x6c88: 'seq', 0x6566: 'set_main'}


def main():
    dis = subprocess.run(
        ["m68k-elf-objdump", "-D", "-b", "binary", "-m", "m68k:68000",
         "build/files/001_AMPROG.OBJ"],
        capture_output=True, text=True).stdout.splitlines()
    pend = None
    out = []
    for ln in dis:
        m = re.match(r'^\s+([0-9a-f]+):\t\w+(?: \w+)*\s+lea %pc@\(0x([0-9a-f]+)\),%a0', ln)
        if m:
            pend = (int(m.group(1), 16), int(m.group(2), 16))
            continue
        m = re.match(r'^\s+([0-9a-f]+):\t.*\tbsrw?s? 0x([0-9a-f]+)', ln)
        if m and pend:
            tgt = int(m.group(2), 16)
            if tgt in SPAWNERS and int(m.group(1), 16) - pend[0] <= 6:
                out.append((pend[1], SPAWNERS[tgt], pend[0]))
            pend = None
            continue
        pend = None
    kinds = Counter(k for _, k, _ in out)
    ents = sorted(set(e for e, k, _ in out
                      if k in ('task', 'child', 'anim_task', 'anim_task2')))
    print("spawnu:", len(out), dict(kinds))
    print("vstupnich bodu chovani:", len(ents))
    json.dump([{'entry': hex(e), 'kind': k, 'site': hex(s)}
               for e, k, s in sorted(out)],
              open('build/coroutines.json', 'w'), indent=0)
    for e in ents:
        print("  0x%05x" % e)


if __name__ == "__main__":
    main()
