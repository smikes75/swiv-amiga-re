#!/usr/bin/env python3
"""Porovna vsech sest parametru `a2c6` v prepisu proti AMPROG.OBJ.

`a2c6(d0 gfx, d1 trida, d2 marze, d3 HP, d4 skore, d5 cost)` je jediny vstup
kazdeho objektu, takze staci precist sest registru pred volanim a porovnat
je s tim, co drzi `game.html`. Marze uz kontroluje `tools/margins.py`; tady
jde o zbyle ctyri (trida, HP, skore, cost).

Parser je stejne konzervativni jako v `margins.py`: kdyz mezi zapisem do
registru a volanim lezi skok nebo cil skoku, hodnotu neuvadi misto toho, aby
hadal. Dopredne hledani `a2c6` navic konci na konci rutiny (nepodmineny
prechod, za kterym uz nelezi zadny cil skoku ani `lea %pc@` vstupni bod) -
bez toho se `a2c6` z NASLEDUJICI rutiny pripsala teto. Takhle hlasil
`trackzone` (0xad30, ktera zadne `a2c6` nema - jen 0x5ee0 a 0x9ac8(0))
cizich (30, 95, 13). Volitelny druhy soubor umozni porovnat dve verze
prepisu mezi sebou.

Zbylych sest hlaseni je zamernych a vysvetlenych primo ve vystupu.

    python3 tools/a2c6check.py [game-codex.html]
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROG = os.path.join(ROOT, "work", "prog.txt")
REGS = {"d1": "trida", "d3": "hp", "d4": "skore", "d5": "cost"}


def load_lines():
    out, order = {}, []
    for line in open(PROG):
        m = re.match(r"\s*([0-9a-f]+):\t[0-9a-f ]+\t(.*)", line)
        if m:
            a = int(m.group(1), 16)
            out[a] = m.group(2).strip()
            order.append(a)
    return out, order


def regs_before(lines, order, start, limit=60):
    """Konstanty v D1/D3/D4/D5 pred prvnim `bsrw 0xa2c6` od `start`."""
    i = 0
    while i < len(order) and order[i] < start:
        i += 1
    # Dopredny sken musi skoncit na konci rutiny, jinak se `a2c6` nalezena
    # az v NASLEDUJICI rutine pripise teto (napr. `trackzone` 0xad30, ktera
    # zadnou nema - jen 0x5ee0 a 0x9ac8). Konec = nepodmineny prechod,
    # za kterym uz nelezi zadny cil skoku videny v dosud prectenem kusu.
    call = None
    seen_targets = set()
    for k in range(i, min(i + 240, len(order))):
        text = lines[order[k]]
        if "bsrw 0xa2c6" in text:
            call = k
            break
        m = re.search(r"\b0x([0-9a-f]+)$", text)
        if m and re.match(r"(b\w+|jmp|jsr)\b", text):
            seen_targets.add(int(m.group(1), 16))
        # `lea %pc@(0x...),%aN` je take vstupni bod - tak se predava telo
        # korutiny do 0x6178 (napr. `airplane` 0x7970 -> 0x797e).
        m = re.match(r"lea %pc@\(0x([0-9a-f]+)\)", text)
        if m:
            seen_targets.add(int(m.group(1), 16))
        if re.match(r"(bra\w*|jmp|rts)\b", text):
            nxt = order[k + 1] if k + 1 < len(order) else None
            if nxt is None or nxt not in seen_targets:
                return None                       # rutina skoncila
    if call is None:
        return None
    targets = set()
    for k in range(max(0, call - limit), call + 1):
        t = lines[order[k]]
        m = re.search(r"\b0x([0-9a-f]+)$", t)
        if m and re.match(r"(b\w+|jmp|jsr)\b", t):
            targets.add(int(m.group(1), 16))
    found = {}
    for k in range(call - 1, max(0, call - limit), -1):
        addr, text = order[k], lines[order[k]]
        if addr in targets or re.match(r"(bra|jmp)\w*\b", text):
            break
        m = re.match(r"move[qwl] #(-?\d+),%(d[1345])$", text)
        if m and m.group(2) not in found:
            found[m.group(2)] = int(m.group(1))
            continue
        # HP nekterych chovani neni konstanta, ale `fp@(182) + N`, kde
        # `fp@(182)` je obtiznost (`0x1cd4`, klap na 10). Bez tohoto
        # rozliseni skript hlasil neshodu u `tank`, `flattank` a
        # `yellow`, prestoze je prepis ma spravne jako `N + difficulty`.
        m = re.match(r"movew %fp@\(182\),%(d[1345])$", text)
        if m and m.group(1) not in found:
            nxt = lines[order[k + 1]] if k + 1 < len(order) else ""
            mm = re.match(r"addqw #(\d+),%" + m.group(1) + "$", nxt)
            found[m.group(1)] = ("obtiznost", int(mm.group(1)) if mm else 0)
    return found


def remake_values(path):
    """Z `game.html`: pro kazde `beh` hodnoty cost/hp/scoreValue."""
    src = open(path).read()
    impl = {}
    for m in re.finditer(r'\[0x[0-9A-Fa-f]+, \{ coroutine: 0x([0-9A-Fa-f]+), id: "(\w+)" \}\]', src):
        impl[m.group(2)] = int(m.group(1), 16)
    def scan(chunk):
        got = {}
        # Rozhoduje PRVNI prirazeni do `s.hp` v bloku - jinak by se
        # vzalo HP nasledujiciho chovani (blok je 1400 znaku a pretece).
        # HP zavisle na obtiznosti se pise dvema zpusoby:
        # `s.hp = 5 + (g.difficulty | 0)` i `s.hp = (g.difficulty || 0) + 1`.
        hm = re.search(r"s\.hp = ([^;]+);", chunk)
        if hm:
            expr = hm.group(1)
            dm = re.match(r"(?:(\d+) \+ )?\(g\.difficulty[^)]*\)"
                          r"(?: \+ (\d+))?$", expr.strip())
            if dm:
                got["hp"] = ("obtiznost", int(dm.group(1) or dm.group(2) or 0))
        for key, field in (("cost", r"s\.cost = (-?\d+)"),
                           ("hp", r"s\.hp = (-?\d+)"),
                           ("armedHp", r"s\.armedHp = (-?\d+)"),
                           ("skore", r"s\.scoreValue = (-?\d+)")):
            if key in got:
                continue
            mm = re.search(field, chunk)
            if mm:
                got[key] = int(mm.group(1))
        return got

    vals = {}
    for beh in impl:
        for m in re.finditer(r's\.beh === "%s"' % re.escape(beh), src):
            chunk = src[m.end():m.end() + 1400]
            # nektera chovani maji inicializaci v samostatne funkci
            # (`initMill(g, s)`), tak se za ni jde
            fn = re.search(r"\b(init[A-Z]\w*)\(g, s\)", chunk[:400])
            if fn:
                f = re.search(r"function %s\([^)]*\) \{" % fn.group(1), src)
                if f:
                    chunk = src[f.end():f.end() + 900]
            got = scan(chunk)
            if got.get("cost") is not None or got.get("skore") is not None:
                vals.setdefault(beh, got)
                break
    return vals, impl


def main():
    other = sys.argv[1] if len(sys.argv) > 1 else None
    lines, order = load_lines()
    ours, impl = remake_values(os.path.join(ROOT, "game.html"))
    theirs = remake_values(other)[0] if other else {}
    bad = []
    print("%-14s %-22s %-22s" % ("chovani", "AMPROG (hp/skore/cost)", "prepis"))
    for beh, cor in sorted(impl.items()):
        native = regs_before(lines, order, cor)
        if not native:
            continue
        want = (native.get("d3"), native.get("d4"), native.get("d5"))
        if want == (None, None, None):
            continue
        have = ours.get(beh)
        if not have:
            continue
        got = (have.get("hp"), have.get("skore"), have.get("cost"))
        # Objekty, ktere po a2c6 cekaji na `0x9ae8`, drzi v prepisu HP 0 a
        # skutecnou hodnotu v `armedHp`. Nechavame to hlasit jako rozdil -
        # je to zamerny model a clovek to musi posoudit, ne skript.
        mism = [i for i in range(3)
                if want[i] is not None and got[i] is not None and want[i] != got[i]]
        popis = lambda v: ("obtiznost+%d" % v[1]) if isinstance(v, tuple) \
            else str(v)
        line = "%-14s %-22s %-22s" % (
            beh, "(" + ", ".join(popis(v) for v in want) + ")",
            "(" + ", ".join(popis(v) for v in got) + ")")
        if mism:
            bad.append((beh, want, got))
            line += "  <<< NESEDI"
        if other and beh in theirs:
            t = theirs[beh]
            tv = (t.get("hp"), t.get("skore"), t.get("cost"))
            if tv != got:
                line += "   codex " + str(tv)
        print(line)
    print("\nnesedi: %d" % len(bad))
    print("Pozor: rozdil u chovani s `armedHp` (factory, inst3, pyramid,")
    print("piston, inst4*) je zamerny - a2c6 hodnotu dostane, ale prepis ji")
    print("objektu prida az pri probuzeni. Stejne tak `bird`/`wave`/`yellow`,")
    print("kde inicializace neni v bloku `s.beh === ...`, ale ve formaci.")
    popis = lambda v: ("obtiznost+%d" % v[1]) if isinstance(v, tuple) \
        else str(v)
    for beh, want, got in bad:
        print("   %-14s AMPROG (%s), prepis (%s)" %
              (beh, ", ".join(popis(v) for v in want),
               ", ".join(popis(v) for v in got)))


if __name__ == "__main__":
    main()
