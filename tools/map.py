#!/usr/bin/env python3
"""Renderer map urovni SWIV (.PAM) -> PNG.

Prepis interpretu z AMPROG.OBJ (rutiny 0x3652 a 0x3800, viz docs/MAPS.md):

Zaznam mapy jsou 4 bajty ctene jako big-endian long D:
  D == 0        konec mapy
  bit 31 = 1    prikaz: y -= bajt1; dolni word je BARVA (obsluha 0x4a04):
                dolni nibble = index barvy 0-15, hornich 12 bitu = RGB12.
                Uvodni davka prikazu = paleta urovne; dalsi v prubehu mapy
                jsou plynule prechody (zapad slunce nad rekou apod.)
  jinak         pole:  typ    = D & 15         (0 = dlazdice, jinak objekt)
                       lokal  = (D >> 4) & 255 (index do slovniku urovne)
                       dy     = (D >> 12) & 255 (posun scroll citace)
                       x      = (D >> 20)       (12 bitu; >=416 -> -512 a
                                                 snizeni vrstvy, viz 0x36cc)

Paleta: barvy 0-9 jsou spolecne (objekty), 10-15 teren. Prazdne pozadi
je BARVA 10 - engine maze pas do rovin 1 a 3 hodnotou -1 (0x34f2).

Slovnik urovne (tabulka 0x384c v AMPROG, 6 B na uroven: word ID pam
souboru 90+n, word offset slovniku, word rychlost scrollu) preklada
lokalni ID na graficke slovo `snimek<<9 | soubor` (dekoduje 0x48c0).

Scroll citac klesa; mapa se tedy stavi ODSPODU. Render akumuluje dy
a vysledek kresli shora dolu.

    python3 tools/map.py 0 build/maps/town.png     # uroven 0..6
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract import catalog, StreamC          # noqa: E402
from gfx import lin_frames, rgb12             # noqa: E402

from PIL import Image

LEVTAB = 0x384C          # tabulka urovni v AMPROG.OBJ
FIELD_W = 352            # sirka hriste (44 B radka v enginu)


class Disk:
    def __init__(self, path="SWIVFIX.ADF"):
        self.adf = open(path, "rb").read()
        self.files = catalog(self.adf)
        self.byname = {f[0]: f for f in self.files}
        self.cache = {}
        self.prog = self.load("AMPROG.OBJ")
        # poradi jmen ve vlastni tabulce hry (0x0004, jmena \0-oddelena;
        # bajt 0x0003 je posledni bajt uvodniho bra.w, ne jmeno)
        names = self.prog[4:0x537].split(b"\0")
        self.order = [n.decode().upper() for n in names if n]

    def load(self, name):
        if name not in self.cache:
            _, off, _, size = self.byname[name]
            self.cache[name] = StreamC(self.adf, off + 4).unpack(size)
        return self.cache[name]

    def frames(self, name):
        key = "F:" + name
        if key not in self.cache:
            self.cache[key] = lin_frames(self.load(name))
        return self.cache[key]


def be16(b, o): return (b[o] << 8) | b[o + 1]
def be32(b, o): return int.from_bytes(b[o:o + 4], "big")


def level_info(disk, lv):
    p = disk.prog
    fid = be16(p, LEVTAB + lv * 6)
    tab = LEVTAB + be16(p, LEVTAB + lv * 6 + 2)
    end = LEVTAB + be16(p, LEVTAB + (lv + 1) * 6 + 2) if lv < 6 else tab + 512
    dico = [be16(p, o) for o in range(tab, end, 2)]
    return disk.order[fid], dico


def parse(pam, dico):
    """Vrati (dlazdice, objekty, checkpointy palet, vyska); y roste dolu.

    Checkpoint je (y, paleta[16]) - snimek palety platny od dane vysky."""
    tiles, objs = [], []
    pal = [0] * 16
    checks = []
    y = 0
    for o in range(0, len(pam), 4):
        d = be32(pam, o)
        if d == 0:
            break
        if d & 0x80000000:
            y += (d >> 16) & 0xFF
            w = d & 0xFFFF
            pal = list(pal)
            pal[w & 15] = w >> 4
            if checks and checks[-1][0] == y:
                checks[-1] = (y, pal)
            else:
                checks.append((y, pal))
            continue
        typ = d & 15
        loc = (d >> 4) & 0xFF
        y += (d >> 12) & 0xFF
        x = d >> 20
        layer = 4
        while x >= 416:
            x -= 512
            layer -= 1
        rec = (y, x, dico[loc] if loc < len(dico) else 0, layer, typ)
        (tiles if typ == 0 else objs).append(rec)
    return tiles, objs, checks, y


def render(disk, lv, out, with_objects=True):
    pam_name, dico = level_info(disk, lv)
    tiles, objs, checks, height = parse(disk.load(pam_name), dico)
    H = height + 300

    def pal_at(y):
        cur = checks[0][1]
        for cy, p in checks:
            if cy > y:
                break
            cur = p
        return [rgb12(v) for v in cur]

    img = Image.new("RGB", (FIELD_W, H))
    px = img.load()
    # pozadi: barva 10 podle palety platne na danem radku
    row_pal = None
    for y in range(H):
        row_pal = pal_at(y)
        c = row_pal[10]
        for x in range(FIELD_W):
            px[x, y] = c

    def blit(x0, y0, gfx):
        pal = pal_at(y0)
        fname = disk.order[gfx & 0x1FF]
        frames = disk.frames(fname)
        fi = gfx >> 9
        if fi >= len(frames):
            return
        f = frames[fi]
        w, h, wd, data = f["w"], f["h"], (f["w"] + 15) // 16, f["data"]
        if len(data) < wd * 8 * h:
            return
        for y in range(h):
            ty = y0 + y
            if not 0 <= ty < H:
                continue
            row = [(data[(y * 4 + k) * wd * 2 + j * 2] << 8) |
                   data[(y * 4 + k) * wd * 2 + j * 2 + 1]
                   for k in range(4) for j in range(wd)]
            for x in range(w):
                tx = x0 + x
                if not 0 <= tx < FIELD_W:
                    continue
                j, b = divmod(x, 16)
                v = 0
                for k in range(4):
                    if row[k * wd + j] & (0x8000 >> b):
                        v |= 1 << k
                if v != f["trans"]:
                    px[tx, ty] = pal[v]

    # vrstvy odspodu (mensi layer driv), dlazdice pak objekty
    for y, x, gfx, layer, _ in sorted(tiles, key=lambda t: t[3]):
        blit(x + 17, y, gfx)
    nobj = 0
    if with_objects:
        for y, x, gfx, layer, typ in objs:
            blit(x + 17, y, gfx)
            nobj += 1
    img.save(out)
    print("%s: %d dlazdic, %d objektu, %d zmen palety, %d px -> %s"
          % (pam_name, len(tiles), nobj, len(checks), H, out))


def main():
    disk = Disk()
    if len(sys.argv) > 2:
        render(disk, int(sys.argv[1]), sys.argv[2])
    else:
        os.makedirs("build/maps", exist_ok=True)
        for lv in range(7):
            name = level_info(disk, lv)[0].split(".")[0].lower()
            render(disk, lv, "build/maps/%d_%s.png" % (lv, name))


if __name__ == "__main__":
    main()
