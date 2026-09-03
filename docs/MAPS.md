# The .PAM format — level maps

The last format on the disk. Cracked by reading the interpreter in
`AMPROG.OBJ` (routines `0x3652`, `0x3800`, `0x4a04`, `0x48c0`); the
renderer is `tools/map.py`, and the same code in JS powers the
**Levels** tab of the browser explorer. Both implementations produce
**bit-identical** images (pixel checksums cross-checked).

## Level table (AMPROG.OBJ at `0x384C`)

7 entries of 6 B: `word` map file ID (90–96 = TOWN…FINAL in the order
of the internal name table at `0x0004`), `word` tile-dictionary offset
(relative to `0x384C`), `word` map-reader prefetch step — it lands in
`fp@(144)` (`0x381c`) and `0x35d4` adds it to the reader's lookahead
counter `fp@(3586)`; TOWN has `0xe1`. It is **not** the scroll speed:
that is the constant `0x4000` written to `fp@(3528)` at `0x1da6`
(0.25 px per VBL = 12.5 px/s, confirmed by baseline frames).

The **tile dictionary** is an array of words; the map addresses tiles
with an 8-bit local ID and the dictionary translates it to a
**graphic word** `frame << 9 | file` — the single graphics reference
format of the whole game (decoded by `0x48c0`: file = low 9 bits,
frame = the rest).

## Map records

A stream of 4-byte records read as a big-endian long `D`; the game
consumes only records that fall within 256 px ahead of the screen
edge (`0x365e`).

`game.html` proto oddeluje **task-start pri prefetchi** od viditelne
aktivace v `a2c6`: formace a nahodne aktivacni prahy vzniknou uz v prvni
fazi. Soucasny JS reader ale v jednom kroku projde vsechny prave zpusobile
zaznamy, zatimco nativni reader mezi zaznamy yielduje. Geometrie a faze
prefetche tedy sedi, presne mezitaskove RNG poradi pri soubehu vice zaznamu
zustava otevrene v `GAPS.md`.

| condition | meaning |
|---|---|
| `D == 0` | end of map |
| bit 31 | **command**: `y -= (D>>16) & 0xFF`; the low word is a colour (below) |
| otherwise | **placement**: see the field breakdown |

Field breakdown (`0x3674`):

```
type   = D & 15          0 = background tile, else object (routine parameter)
local  = (D >> 4) & 255  index into the level dictionary
Δy     = (D >> 12) & 255 scroll-counter step (the map runs bottom-up)
x      = D >> 20         12 bits; values ≥ 416 wrap by −512 and
                         decrement the layer — negative x and draw depth
```

Objects (`type ≠ 0`) are not drawn into the bitmap but **spawned** —
`0x36fe` creates a structure with position and stores `type` in `+276`.
The coroutine itself is selected separately by the full graphic word
(`frame << 9 | file`) through the table at `0x7462`; `type` is its
routine-specific initial parameter. The map therefore also carries enemy
and pickup placement.

**Draw order** (verified against real gameplay): **carpets at the
bottom** — layer 0 is "farthest background" (sorts as 5), then
layer 4, details 3/2/1 on top; **within a layer, reverse record
order** (the descending key `(layer<<8)|seq`: a later record goes
underneath, an earlier one on top) — exactly how the overlapping
instances that make up e.g. the hangar (3× `_RUNWAY#6` stepped
−38/+38) join seamlessly. This rule raised the video-match correlation
across the board (0.19→0.29) and fixed a former outlier. The mechanism
that puts layer 0 at the very bottom (its key `0|seq` is the smallest)
remains to be read from the engine.

Note: the mirror bits (part flags 1–2) turned out to be **unused** for
composite assembly — the hangar and the control tower join correctly
without mirroring; their actual meaning in the drawer (slots `0x3e70`)
remains to be read.

## Colour commands: the palette lives in the map

The low word of a command (handler `0x4a04`):

```
colour index = word & 15        target = COLOR00 + index
colour       = word >> 4        RGB12
```

The opening batch of commands in every map sets **the level's whole
palette**; further commands during the map change individual colours
at their raster line. Each command is a **discrete write**, not a
tween — the engine holds no interpolation state between checkpoints.
The smooth sunset over the river comes from the *density of commands
in the data* (RIVER: 19 changes over 4,127 px), so it is still true
that it is not code — **it is data in the map.**

`0x4a48` does **not** belong to this mechanism. It is the global
fade-to-black/white multiplier laid on top of the whole palette, with
its own two level variables and its own per-frame driver; see the
fade section in [BEHAVIORS](BEHAVIORS.md). An earlier version of this
document claimed the engine interpolated between checkpoints using
`0x4a48` — reading the routine disproved it.

Measured structure: colours 0–9 are identical across levels 0–4 (the
objects — jeep, helicopter, explosions), 10–15 carry the terrain.

## Background

The engine clears each strip of the scroll bitmap with `-1` in
**planes 1 and 3** (`0x34f2`; a row is 44 B = 352 px, a plane
44×320) — empty is colour 10. Terrain texture (speckled dirt, grass,
water ripples) is NOT a noise trick: it is made by **fill composites
straight from the map** — four-part chained 128×64 strips (see
GRAPHICS.md, chains), three of which cover the field's full width.

## The display window (measured from code, not guessed)

The playfield is 352 px (44 B rows); the game shows 320 of them:
copper list at `0x5D24` (`DIWSTRT 2C81`, `DIWSTOP 2CC1` = a standard
320×256 window; `DDFSTRT 38`, `DDFSTOP D0` = 40-byte fetch),
`BPLCON1 = 0`, and the bitplane pointer build at `0x5cc2` is
`base + (scroll mod 320) × 44` — **no horizontal offset**. The
modulo-4 skips 4 bytes at the **end** of each row, so the hidden
32 px margin is entirely **on the right** (playfield x 320…352). The
renders draw exactly the visible window; clipping at the edges matches
what the player sees.

## Terrain control planes and HELI respawn

Pruh mapy se na `0x34f2` maze do dvou ridicich rovin plnych jednicek.
Kazda fyzicka cast mapoveho `.LIN` s raw flagem `0x04` pak mintermem
`$0A = ~A & C` vyreze svou opaque masku z plane1; flag `0x02` dela
totez s plane0. Vizualni flag `0x10` tento zapis nepotlaci, proto jsou
napriklad `_STOP.LIN#3` casti s flagem `0x14` neviditelne prekazky.

HELI sonda `0x3dd4` pouziva minterm `$50 = A & ~C` mezi opaque maskou
`JEEPHELI#0` a plane1. `0x9046` pri startu/respawnu synchronne zkousi
16 sloupcu x 12 radku: x 160..280 po8, v kazdem y 192..104 po−8.
Prvni volne misto vyhraje; po 192 kolizich zustane nekontrolovany
fallback `(288,192)`. Runtime si proto predpocitava terrain plane oddelene
od viditelnych paletovych indexu.

## Measured level numbers

| # | map | tiles | objects | palette changes | map height px |
|---|---|---|---|---|---|
| 0 | TOWN | 704 | 155 | 13 | 3,441 |
| 1 | DESERT | 965 | 274 | 22 | 5,872 |
| 2 | GRASS | 357 | 132 | 28 | 2,725 |
| 3 | RIVER | 911 | 212 | 19 | 4,127 |
| 4 | ICE | 796 | 367 | 31 | 5,315 |
| 5 | SCIFI | 1,794 | 356 | 24 | 5,632 |
| 6 | FINAL | 93 | 1 | 1 | 384 |

(height = net map height; the renders add a 300 px margin for
overhangs; FINAL is short because the final arena loops at runtime)

## Verification against real gameplay

The TOWN render is checked against emulator gameplay footage: a
correlation matcher locates video frames in the rendered strip, the
found positions descend **monotonically at a constant scroll rate**
(−48 px / 4 s), and visual comparison of locked positions matches
structure for structure (hedges, compounds, boulder fields,
platforms). Remaining differences are dynamic entities (explosions,
moved enemies) which a static map by definition does not carry.

The footage value above is a coarse correlation measurement. Runtime code
at `0x1da6` writes `$4000` in 16.16 units, i.e. exactly **0.25 px/VBL =
12.5 px/s at 50 Hz**; the browser now uses this exact value.

## Deliberately not rendered / known deviations

- the global fade-to-black/white multiplier (`0x4a48`): the static
  renders always show the palette unfaded
- the FINAL arena's runtime looping
- object behaviour (only the spawn graphic at the spawn position)
- the drawer's mirror-flag slots (see above)
