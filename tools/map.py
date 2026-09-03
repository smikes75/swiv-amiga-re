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

Paleta: barvy 0-9 jsou spolecne (objekty; PAM je zapisuje checkpointem
hned za uvodni davkou, v TOWN na ry 104), 10-15 teren. "Krapani" terenu
NENI zadny sumovy generator: je to soucast kobercovych dlazdic (napr.
_HOUSES#1 ma v datech smes indexu 10/11/12) a render z dlazdic je proti
snimkum originalu pixelove presny (tools/compare.py, teren 100 %).
Drivejsi domnenka o sumu v rovinach 0/2 vznikla z gamma krivky emulatoru
(nibble 5 se ve vAmize zobrazi jako 56, ne 85) a 1px posunu radku.
Engine maze pas stripu do rovin 1 a 3 hodnotou -1 (0x34f2, strip je
kruhovy 320 radku, 0x341a).

Slovnik urovne (tabulka 0x384c v AMPROG, 6 B na uroven: word ID pam
souboru 90+n, word offset slovniku, word krok map-readeru -> fp@(144),
0x35d4: fp@(3586) += fp@(144); rychlost scrollu je konstantni 0x4000
z 0x1da6 = 0.25 px/VBL) preklada
lokalni ID na graficke slovo `snimek<<9 | soubor` (dekoduje 0x48c0).

Scroll citac klesa; mapa se tedy stavi ODSPODU a soucasti kresleni je
odecteni STREDU snimku (cx, cy z hlavicky .LIN) - engine to dela na
0x3ef0 pro dlazdice i objekty. Render proto klade zacatek urovne DOLU
(jako plakat: cte se odspodu nahoru, jak hra scrolluje) a kazdy snimek
kotvi za stred.

    python3 tools/map.py 0 build/maps/town.png     # uroven 0..6
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract import catalog, StreamC          # noqa: E402
from gfx import lin_frames, rgb12             # noqa: E402

from PIL import Image

LEVTAB = 0x384C          # tabulka urovni v AMPROG.OBJ
FIELD_W = 320            # viditelne okno (hriste je 352, okraje hra neukazuje)


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


# Hriste ma 352 px (44B radka), okno hry ukazuje 320: bitplane
# pointer = zacatek radky bez posunu (0x5cc2), BPLCON1=0, fetch 40 B
# a modulo 4 preskoci 4 bajty na KONCI radky - cely skryty okraj je
# tedy VPRAVO (hriste x 320..352). Viditelne okno = hriste x 0..320.
XOFF = 0
MARGIN = 160             # rezerva nad korunou mapy (presahy vysokych dlazdic)


def render(disk, lv, out, with_objects=True):
    pam_name, dico = level_info(disk, lv)
    tiles, objs, checks, height = parse(disk.load(pam_name), dico)
    H = height + 2 * MARGIN

    def ry_of(img_y):
        return height + MARGIN - img_y

    def pal_at_ry(ry):
        cur = checks[0][1] if checks else [0] * 16
        for cy, p in checks:
            if cy > ry:
                break
            cur = p
        return [rgb12(v) for v in cur]

    img = Image.new("RGB", (FIELD_W, H))
    px = img.load()
    # pozadi: plocha barva 10 (roviny 1+3 = -1); texturu zeme delaji
    # vyplnove kompozity primo z mapy
    for y in range(H):
        c = pal_at_ry(ry_of(y))[10]
        for x in range(FIELD_W):
            px[x, y] = c

    def blit(rx, ry, gfx):
        pal = pal_at_ry(ry)
        fname = disk.order[gfx & 0x1FF]
        frames = disk.frames(fname)
        fi = gfx >> 9
        if fi >= len(frames):
            return
        if frames[fi]["parts"][0]["flags"] & 0x10:
            return                      # bit 4 = znacka editoru, hra nekresli
        for f in frames[fi]["parts"]:
            blit_part(rx, ry, f, pal)

    def blit_part(rx, ry, f, pal):
        w, h, wd, data = f["w"], f["h"], (f["w"] + 15) // 16, f["data"]
        if len(data) < wd * 8 * h:
            return
        # kazdy dil kotvi za svou kotvu na teze pozici (0x3e5a/0x3ef0)
        x0 = rx - f["cx"] + XOFF
        y0 = (height + MARGIN - ry) - f["cy"]
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

    # poradi kresleni (overeno proti realne hre): koberce vespod -
    # vrstva 0 je "nejdalsi pozadi" (0 -> 5), pak 4, detaily 3/2/1
    # navrch. UVNITR vrstvy obracene poradi zaznamu (sestupny klic
    # (vrstva<<8)|seq): pozdejsi zaznam vespod, drivejsi navrch -
    # tak na sebe navazuji prekryvne instance (hangar z _RUNWAY#6).
    order = sorted(enumerate(tiles),
                   key=lambda it: (-(5 if it[1][3] == 0 else it[1][3]), -it[0]))
    for _, (y, x, gfx, layer, _t) in order:
        blit(x, y, gfx)
    nobj = 0
    if with_objects:
        for y, x, gfx, layer, typ in objs:
            blit(x, y, gfx)
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
