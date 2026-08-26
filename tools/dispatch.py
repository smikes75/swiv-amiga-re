#!/usr/bin/env python3
"""Vytezi tabulku gfx -> korutina z AMPROG.OBJ.

Mapa nese 16bitove graficke slovo ``frame << 9 | file`` a samostatny
TYP. Lookup na 0x758A vybira korutinu jen podle grafickeho slova; TYP
se zvolene korutine preda jako pocatecni stav objektu v poli +276.

    python3 tools/dispatch.py [AMPROG.OBJ] [build/dispatch.json]
"""

import json
import os
import sys


TABLE = 0x7462
ROUTINE_BASE = 0x75A4
NAME_TABLE_END = 0x537


def game_order(prog):
    """Vraceni interniho poradi souboru z hlavicky AMPROG.OBJ."""
    names = prog[4:NAME_TABLE_END].decode("latin1").split("\0")
    return [name.upper() for name in names if name]


def behavior_dispatch(prog):
    """Vraceni zaznamu tabulky s rozresenymi absolutnimi adresami."""
    if len(prog) < TABLE + 4:
        raise ValueError("AMPROG.OBJ je prilis kratky pro dispatch tabulku")

    order = game_order(prog)
    seen = set()
    rows = []
    for off in range(TABLE, len(prog) - 3, 4):
        gfx = int.from_bytes(prog[off:off + 2], "big")
        rel = int.from_bytes(prog[off + 2:off + 4], "big", signed=True)
        if gfx == 0:
            if rel != 0:
                raise ValueError("dispatch ma neplatny koncovy zaznam")
            return rows
        if gfx in seen:
            raise ValueError("dispatch obsahuje gfx 0x%04x dvakrat" % gfx)
        seen.add(gfx)

        file_id = gfx & 0x1FF
        if file_id >= len(order):
            raise ValueError("gfx 0x%04x odkazuje mimo tabulku souboru" % gfx)
        coroutine = ROUTINE_BASE + 2 * rel
        if not 0 <= coroutine < len(prog):
            raise ValueError("gfx 0x%04x ma korutinu mimo AMPROG" % gfx)
        rows.append({"file": order[file_id], "frame": gfx >> 9,
                     "gfx": gfx, "coroutine": coroutine})
    raise ValueError("dispatch tabulka nema koncovy zaznam")


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "build/files/001_AMPROG.OBJ"
    dst = sys.argv[2] if len(sys.argv) > 2 else "build/dispatch.json"
    with open(src, "rb") as f:
        rows = behavior_dispatch(f.read())
    serializable = [dict(row, coroutine=hex(row["coroutine"])) for row in rows]
    parent = os.path.dirname(dst)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)
        f.write("\n")
    print("%s: %d zaznamu" % (dst, len(rows)))


if __name__ == "__main__":
    main()
