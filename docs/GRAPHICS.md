# Graphics formats: .RAW and .LIN

The decoder is `tools/gfx.py`. Everything below is verified by eye on
the output and by checks in `tools/check.py`.

## .RAW — full screens (9 files, always 40,992 B)

```
40,960 B   4 bitplanes 320×256, stored SEQUENTIALLY (10,240 B per plane)
    32 B   palette, 16 × RGB12 big-endian, AT THE END of the file
```

Contents: COVER (title), HELIBP1/2 + JEEPBP1/2 (vehicle blueprints for
the intro), MUSHROOM, FACES (the developers + mascot), CONGRAT1/2
(completion screens). Decode them with
`python3 tools/gfx.py raw <file> out.png` or view them in the browser
explorer.

## .LIN — object frame sets (~90 files)

```
+0   word   count of LOGICAL frames (chained parts are not counted!)
per physical part:
+0   word   data length = ceil(w/16)·2 · 4 · h
+2   byte   width in pixels
+3   byte   height
+4   byte   anchor x (SIGNED — composite parts anchor outside their box)
+5   byte   anchor y (signed)
+6   byte   TRANSPARENT COLOUR (index 0–15)
+7   byte   flags: bit 0 = chain, bits 1–2 = mirror
+8   byte   w2  +9  byte  h2 (secondary dimensions for the runtime)
+10  data   rows interleaved [p0 p1 p2 p3], ceil(w/16) words per plane
```

**Chains (flag bit 0).** A part with bit 0 set continues into the next
physical part of the same logical frame; the drawer (`0x3e5a`) paints
the whole chain at one position, each part by its own anchor. This is
how wide composites are built: four-part 128 px ground-texture strips,
the diagonal runway, buildings. Verified on all 91 files: the header
count equals the number of logical groups and the stream ends
byte-exact — which finally made CONTROL, REACTOR and SKI parse too.

The header→runtime-struct conversion is done by `0x457e`/`0x45b2`
(anchors sign-extended with `ext.w`, flags copied to +26); the mask is
generated at load time by `0x4678` using a routine table at `0x46d2`
indexed by the transparent colour — which is why no masks exist in the
files.

**Transparency** is the colour index from the header (per part, not
constant even within one file). Proven statistically: the mode of the
border pixels equals byte +6 for the overwhelming majority of frames;
exceptions (LAKEGUN stands on water) are explained by content.

## Palettes

`.LIN` carries no palette. Screen palettes live in `AMPROG.OBJ` (block
of 16-word RGB12 palettes from `0x299C`; the one at `0x29BC` is
bit-identical to the COVER.RAW palette, which confirms the block).
**Level palettes are not here — they live inside the maps**, including
mid-level fades; see [MAPS.md](MAPS.md).

Preview sheets (`tools/gfx.py sheets`) therefore use one palette for
everything; hues are approximate, shapes exact. The browser explorer
lets you switch palettes per sheet.
