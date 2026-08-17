#!/usr/bin/env python3
"""Dekoder grafickych souboru SWIV -> PNG.

.RAW (40992 B): celoobrazovkovy obrazek 320x256, 4 bitplany po 10240 B
SEKVENCNE za sebou (ne prokladane po radcich), na konci paleta
16x RGB12 big-endian. Overeno okem na vsech deviti souborech.

.LIN: sada snimku (bobu). word pocet, pak na kazdy snimek:

    +0  word  delka dat = ceil(w/16)*2 * 4 * h
    +2  byte  sirka v pixelech       +3  byte  vyska
    +4  byte  stred x                +5  byte  stred y
    +6  byte  PRUHLEDNA BARVA        +7  byte  ?
    +8  word  ?  (u vetsiny znovu stred)
    +10 data: radky prokladane [p0 p1 p2 p3] po ceil(w/16) wordech

Zadna maska - snimky jsou plne obdelniky a pruhlednost urcuje index
z hlavicky (hra si masku evidentne vyrabi po nacteni). Overeno
korelaci: modus barvy okraje == bajt +6 u naproste vetsiny snimku
(vyjimky typu LAKEGUN stoji na vode a okraj maji vodni).

Palety leva hra v AMPROG.OBJ (0x299C + dalsich 8); pro nahledy se bere
prvni herni (0x29DC), takze odstiny jsou orientacni.

    python3 tools/gfx.py raw build/files/032_COVER.RAW docs/img/cover.png
    python3 tools/gfx.py lin build/files/053_GOOSE.LIN work/goose.png
    python3 tools/gfx.py sheets build/files build/sheets
"""

import glob
import math
import os
import sys

from PIL import Image

BACK = (34, 34, 44)                  # podklad archu (mimo paletu hry)

W, H = 320, 256
PLANES = 4
ROW = W // 8


def rgb12(v):
    return tuple(((v >> s) & 0xF) * 17 for s in (8, 4, 0))


def raw_image(data, interleaved=False):
    # pozor na zaporne rezy: pro i=15 by [-2:0] byl prazdny
    base = len(data) - 32
    pal = [rgb12(int.from_bytes(data[base + 2 * i:base + 2 * i + 2], "big"))
           for i in range(16)]
    planes = data
    img = Image.new("P", (W, H))
    img.putpalette([c for col in pal for c in col])
    px = img.load()
    for y in range(H):
        for xb in range(ROW):
            bs = []
            for p in range(PLANES):
                if interleaved:
                    base = (y * PLANES + p) * ROW
                else:
                    base = p * ROW * H + y * ROW
                bs.append(planes[base + xb])
            for bit in range(8):
                v = 0
                for p in range(PLANES):
                    if bs[p] & (0x80 >> bit):
                        v |= 1 << p
                px[xb * 8 + bit, y] = v
    return img


def lin_frames(data):
    """Rozlozi .LIN na snimky; toleruje ocasni data (SKI.LIN)."""
    cnt = int.from_bytes(data[:2], "big")
    p = 2
    out = []
    for _ in range(cnt):
        if p + 10 > len(data):
            break
        dsz = int.from_bytes(data[p:p + 2], "big")
        w, h = data[p + 2], data[p + 3]
        sx = data[p + 4] - 256 if data[p + 4] > 127 else data[p + 4]
        sy = data[p + 5] - 256 if data[p + 5] > 127 else data[p + 5]
        out.append({"w": w, "h": h, "cx": sx, "cy": sy,
                    "trans": data[p + 6], "data": data[p + 10:p + 10 + dsz]})
        p += 10 + dsz
    return out


def default_pal():
    """Prvni herni paleta z AMPROG.OBJ, jinak stupne sedi."""
    try:
        prog = open("build/files/001_AMPROG.OBJ", "rb").read()
        return [rgb12(int.from_bytes(prog[0x29DC + 2 * i:0x29DE + 2 * i], "big"))
                for i in range(16)]
    except OSError:
        return [(i * 17, i * 17, i * 17) for i in range(16)]


def lin_sheet(frames, pal, cols=8, scale=2):
    frames = [f for f in frames if f["w"] and f["h"]]
    if not frames:
        return None
    cw = max(f["w"] for f in frames) + 2
    ch = max(f["h"] for f in frames) + 2
    rows = math.ceil(len(frames) / cols)
    img = Image.new("RGB", (cols * cw, rows * ch), BACK)
    px = img.load()
    for i, f in enumerate(frames):
        w, h, wd = f["w"], f["h"], (f["w"] + 15) // 16
        data = f["data"]
        if len(data) < wd * 2 * 4 * h:
            continue
        ox, oy = (i % cols) * cw + 1, (i // cols) * ch + 1
        for y in range(h):
            row = [int.from_bytes(data[(y * 4 + k) * wd * 2 + j * 2:
                                       (y * 4 + k) * wd * 2 + j * 2 + 2], "big")
                   for k in range(4) for j in range(wd)]
            for x in range(w):
                j, b = divmod(x, 16)
                v = 0
                for k in range(4):
                    if row[k * wd + j] & (0x8000 >> b):
                        v |= 1 << k
                if v != f["trans"]:
                    px[ox + x, oy + y] = pal[v]
    return img.resize((img.width * scale, img.height * scale), Image.NEAREST)


def main():
    kind, src, dst = sys.argv[1:4]
    if kind == "raw":
        data = open(src, "rb").read()
        inter = len(sys.argv) > 4 and sys.argv[4] == "i"
        raw_image(data, inter).save(dst)
        print("%s -> %s (%s)" % (src, dst, "prokladane" if inter else "sekvencni"))
    elif kind == "lin":
        img = lin_sheet(lin_frames(open(src, "rb").read()), default_pal())
        img.save(dst)
        print("%s -> %s" % (src, dst))
    elif kind == "sheets":
        pal = default_pal()
        os.makedirs(dst, exist_ok=True)
        n = 0
        for fn in sorted(glob.glob(os.path.join(src, "*.LIN"))):
            img = lin_sheet(lin_frames(open(fn, "rb").read()), pal)
            if img is None:
                continue
            base = os.path.basename(fn).rsplit(".", 1)[0].lower()
            img.save(os.path.join(dst, base + ".png"))
            n += 1
        print("%d archu do %s/" % (n, dst))
    else:
        sys.exit("neznamy druh: " + kind)


if __name__ == "__main__":
    main()
