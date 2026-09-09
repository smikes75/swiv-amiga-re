#!/usr/bin/env python3
"""Staticka kontrola aktivacnich marzi: a2c6 d2 v AMPROG.OBJ vs game.html.

`0x9ac8` (volane z `a2c6`) ceka, dokud `y - margin < kamera`, tedy pusti
korutinu presne pri `ys >= margin`, kde margin je registr D2 pri volani
`a2c6`. Prepis tuto hodnotu drzi v `step()` jako `margin` a jako vychozi
pouziva -32; kdyz se hodnoty rozejdou, objekt se rodi jinde nez v originale.

Skript najde pro kazdou korutinu z build/dispatch.json prvni `bsrw 0xa2c6`
a zpetne dohleda posledni zapis do D2 (`moveq`/`movew`/`movel`). Vysledek
porovna s marzemi vypsanymi z game.html.

    python3 tools/margins.py
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROG = os.path.join(ROOT, "work", "prog.txt")


def load_lines():
    out = {}
    order = []
    for line in open(PROG):
        m = re.match(r"\s*([0-9a-f]+):\t[0-9a-f ]+\t(.*)", line)
        if not m:
            continue
        addr = int(m.group(1), 16)
        out[addr] = m.group(2).strip()
        order.append(addr)
    return out, order


def d2_before(lines, order, start, limit=40):
    """Posledni zapis do d2 pred prvnim bsrw 0xa2c6 od adresy start."""
    i = 0
    while order[i] < start:
        i += 1
    call = None
    for k in range(i, min(i + 200, len(order))):
        if "bsrw 0xa2c6" in lines[order[k]]:
            call = k
            break
    if call is None:
        return None, None
    # Zpetne hledani je platne jen v primem useku kodu. Kdyz mezi zapisem
    # do D2 a volanim a2c6 lezi skok nebo cil skoku, muze se sem vstoupit
    # jinudy (0x7970: rodic ma movew #176 a pres bras preskoci moveq #127,
    # coz je vstup ditete) - takovy vysledek hlasime jako nejisty.
    targets = set()
    for k in range(max(0, call - limit), call + 1):
        m = re.search(r"\b0x([0-9a-f]+)$", lines[order[k]])
        if m and re.match(r"(b\w+|jmp|jsr)\b", lines[order[k]]):
            targets.add(int(m.group(1), 16))
    for k in range(call - 1, max(0, call - limit), -1):
        addr, text = order[k], lines[order[k]]
        if addr in targets or re.match(r"(bra|jmp)\w*\b", text):
            return None, addr              # do useku se da vstoupit jinudy
        m = re.match(r"move[qwl] #(-?\d+),%d2$", text)
        if m:
            return int(m.group(1)), addr
        if re.match(r"(move|add|sub|and|or|eor|clr|not|neg|ext)\w*.*%d2$", text):
            return None, addr              # neco jineho plni d2
    return None, None


REMAKE_RE = re.compile(
    r'else if \(s\.beh === "(\w+)"\) margin = (-?\d+);')


def remake_margins():
    src = open(os.path.join(ROOT, "game.html")).read()
    block = src[src.index("let margin = -32;"):src.index("if (esy >= margin) fire = true;")]
    out = {}
    # skupina se spolecnym -48
    group = re.search(r'if \((s\.beh === "\w+"(?:\s*\|\|\s*\n?\s*s\.beh === "\w+")*)\)\s*\n\s*margin = (-?\d+);', block)
    if group:
        for name in re.findall(r'"(\w+)"', group.group(1)):
            out[name] = int(group.group(2))
    for name, value in REMAKE_RE.findall(block):
        out[name] = int(value)
    for name in re.findall(r'else if \(s\.beh === "(\w+)"\) \{', block):
        out[name] = "dynamicky"
    return out


def main():
    lines, order = load_lines()
    disp = json.load(open(os.path.join(ROOT, "build", "dispatch.json")))
    impl = {}
    src = open(os.path.join(ROOT, "game.html")).read()
    for m in re.finditer(r'\[0x([0-9A-Fa-f]+), \{ coroutine: 0x([0-9A-Fa-f]+), id: "(\w+)" \}\]', src):
        impl[int(m.group(2), 16)] = m.group(3)
    rm = remake_margins()
    rows, bad = [], []
    for d in disp:
        cor = int(d["coroutine"], 16)
        beh = impl.get(cor)
        if not beh:
            continue
        native, at = d2_before(lines, order, cor)
        mine = rm.get(beh, -32)
        rows.append((beh, d["file"], d["frame"], native, at, mine))
        if native is not None and isinstance(mine, int) and native != mine:
            bad.append(rows[-1])
    print(f"korutin s implementaci: {len(rows)}\n")
    print(f"{'chovani':<14}{'soubor':<16}{'a2c6 d2':>8}{'prepis':>10}   kde")
    for beh, f, fr, native, at, mine in sorted(rows):
        flag = ""
        if native is None:
            flag = "  (d2 nelze urcit staticky)"
        elif isinstance(mine, str):
            flag = "  (prepis pocita dynamicky)"
        elif native != mine:
            flag = "  <<< NESEDI"
        print(f"{beh:<14}{f:<16}{str(native):>8}{str(mine):>10}"
              f"   0x{at:04x}" % () if at else "", end="")
        print(flag)
    print(f"\nnesedi: {len(bad)}")
    for beh, f, fr, native, at, mine in bad:
        print(f"   {beh:<14} {f:<16} original {native:>5}, prepis {mine:>5}"
              f"  (rozdil {mine - native:+d} px)")


if __name__ == "__main__":
    main()
