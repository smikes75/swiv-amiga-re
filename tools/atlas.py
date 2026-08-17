#!/usr/bin/env python3
"""Atlas vsech spritu: kazdy .LIN x kazdy logicky snimek x paleta
urovne -> build/atlas.html (lokalni artefakt, obsahuje herni grafiku,
do repa NEpatri - build/ je v .gitignore).

    python3 tools/atlas.py
"""

import base64
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from map import Disk, level_info, parse   # noqa: E402
from gfx import frame_bbox, rgb12         # noqa: E402

from PIL import Image

LEVELS = ["TOWN", "DESERT", "GRASS", "RIVER", "ICE", "SCIFI", "FINAL"]


def render_frame(f, pal):
    bb = frame_bbox(f)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    if w <= 0 or h <= 0:
        return None
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for p in f["parts"]:
        wd = (p["w"] + 15) // 16
        if len(p["data"]) < wd * 8 * p["h"]:
            continue
        bx, by = -p["cx"] - bb[0], -p["cy"] - bb[1]
        for y in range(p["h"]):
            for x in range(p["w"]):
                j, b = divmod(x, 16)
                v = 0
                for k in range(4):
                    wv = (p["data"][(y * 4 + k) * wd * 2 + j * 2] << 8) | \
                         p["data"][(y * 4 + k) * wd * 2 + j * 2 + 1]
                    if wv & (0x8000 >> b):
                        v |= 1 << k
                if v != p["trans"]:
                    px[bx + x, by + y] = pal[v] + (255,)
    return img


def main():
    disk = Disk()
    pals = []
    for lv in range(7):
        pam, dico = level_info(disk, lv)
        checks = parse(disk.load(pam), dico)[2]
        pals.append([rgb12(v) for v in (checks[0][1] if checks else [0]*16)])

    html = ["""<!doctype html><meta charset=utf-8><title>SWIV sprite atlas</title>
<style>body{background:#223;color:#eee;font:13px monospace;padding:12px}
img{image-rendering:pixelated;vertical-align:bottom;background:#445;margin:1px}
h2{color:#fc0;margin:16px 0 4px}.f{display:inline-block;text-align:center;margin:2px}
.f small{display:block;color:#8ac}select{font:inherit}</style>
<h1>SWIV sprite atlas</h1>
<p>paleta: <select id=ps onchange="document.body.className='p'+this.value">"""]
    for i, n in enumerate(LEVELS):
        html.append('<option value=%d>%s</option>' % (i, n))
    html.append('</select> (skryvani: CSS)</p>')

    # pro uspornost: renderovat kazdy snimek jen v palete TOWN a SCIFI?
    # ne - v palete urovne, kde se soubor pouziva; default TOWN.
    for name in disk.order:
        if not name.endswith(".LIN"):
            continue
        try:
            frames = disk.frames(name)
        except Exception:
            continue
        html.append("<h2>%s (%d)</h2>" % (name, len(frames)))
        for i, f in enumerate(frames):
            img = render_frame(f, pals[0])
            if img is None:
                continue
            scale = 2 if max(img.size) < 64 else 1
            if scale > 1:
                img = img.resize((img.width*2, img.height*2), Image.NEAREST)
            buf = io.BytesIO()
            img.save(buf, "PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            html.append('<span class=f><img src="data:image/png;base64,%s">'
                        '<small>#%d</small></span>' % (b64, i))
    open("build/atlas.html", "w", encoding="utf-8").write("\n".join(html))
    print("build/atlas.html (%d kB)" %
          (os.path.getsize("build/atlas.html") // 1024))


if __name__ == "__main__":
    main()
