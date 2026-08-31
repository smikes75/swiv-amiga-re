# Native HUD format and reconstruction

This document describes the HUD as measured in `AMPROG.OBJ`. All addresses
are file offsets in the 55,668-byte object extracted from `SWIVFIX.ADF`.
The executable contract is:

```sh
python3 tools/hudscan.py SWIVFIX.ADF
python3 tools/hudscan.py build/files/001_AMPROG.OBJ
```

Both inputs must report the same font and mask hashes. The tool only reads
the input and does not write generated assets.

## Embedded 7-row font

The text renderer at `0x591C..0x59C2` folds lower-case input to upper case
and loads the glyph table with `lea 0xD384(pc),a0` at `0x59AE`. The lookup
formula is:

```
record = AMPROG.OBJ[0xD384 + ASCII * 16]
```

Drawable ASCII 32 through 94 therefore occupies `0xD584..0xD973`, the end
of the object: 63 records and 1,008 bytes. ASCII 95 (`_`) is a formatter
escape, not another drawable glyph. `CONTROL.LIN` is unrelated to this
font.

Each record is big-endian:

| record offset | size | meaning |
|---:|---:|---|
| `+0` | word | variable glyph width, at most 16 pixels |
| `+2` | 7 words | seven bitmap rows, top to bottom |

For a glyph of width `w`, local pixel `x` is set when
`row_word & (1 << (w - 1 - x))`. Text advances by `w + 1`, including the
one-pixel advance after the last glyph. The audited font-block SHA-256 is:

```
f9a3f735b03252759ff3d0eeb7c71cadb84eadce6fb0b077905f9c05842934db
```

Two printable slots carry HUD icons rather than their conventional shapes.
`[` (ASCII 91) is the life/heart icon and `*` (ASCII 42) is the weapon icon:

```
     [          *
   .##.##.    ...#...
   #######    ...#...
   #######    #######
   #######    .#####.
   .#####.    ..###..
   ..###..    .##.##.
   ...#...    .#...#.
```

## Fifth-bitplane buffer

Initialization at `0x5AC8` allocates two `0x160`-byte buffers:

| frame-base field | allocation | role |
|---:|---:|---|
| `fp+0xE10` | `0x5ACE..0x5AD8` | displayed HUD plane |
| `fp+0xE14` | `0x5ADC..0x5AE6` | HUD work plane |

Each is a monochrome **352 x 8** bitmap: 44 bytes per row and eight rows.
The leftmost pixel in each byte is bit 7. The specialized renderer at
`0x5AA4..0x5AC6` ORs the seven glyph rows into the work buffer at a stride
of 44 bytes. Row 7 remains clear. Routine `0x5902..0x591A` copies all 352
bytes from work to display and clears the work buffer. The copper setup at
`0x5CEA..0x5CFC` installs the display address in `BPL5PTH/BPL5PTL`; the
normal playfield builder at `0x5D64` supplies the other four planes.

The persistent HUD task starts at `0x259C` and is created from `0x0D12`.
It selects the one-bit renderer at `0x25A2`, rebuilds the work bitmap, then
copies, clears and waits for vertical blank at `0x25D8..0x25E4`.

## Text, anchors and initial mask

The general formatter parses `_xNNN` / `_yNNN` at `0x57D0..0x582A`,
alignment `_aN` at `0x5854..0x585E`, and flush `_n` at
`0x5864..0x586A`. `a0` centers, `a1` aligns left, and `a2` aligns right.
Measurement and rendering are at `0x5880..0x58E8`.

The normal HUD task uses these format strings:

| player | formatter | anchor | initial text | measured width | start x |
|---|---|---:|---|---:|---:|
| helicopter | `_x008_a1` (`0x26C2`) | left 8 | `HELI 4[ 2* 0000000` | 133 | 8 |
| jeep/inactive | `_x312_a2` (`0x26CB`) | right 312 | `PRESS FIRE` | 76 | 236 |

The strings are flushed separately with `_n`, but the specialized HUD path
ignores the normal renderer's y coordinate, so both occupy the same seven
physical rows. Rendering the two initial strings into a cleared 352 x 8
buffer gives exactly 638 set bits and this SHA-256 over the 352 raw bytes:

```
083735374ea183f35350e6bbd4cb97e6bb8202d81ae7f51621764093154cd894
```

The dynamic player string is assembled at `0x737E..0x73EA`. Player structs
start at `fp+11176` and `fp+11356` and are 180 bytes apart:

- the prefixes initialized at `0x6F46..0x6FA8` are `Heli ` and `Jeep `;
  the renderer displays them in upper case;
- lives are the signed word at player `+68`, initialized to `-16` at
  `0x707A`, and displayed as `(-value) >> 2`, hence the initial `4`, followed
  by `[` and a space;
- the independent pickup counter at `+102` increments for every collected
  TOKEN, saturates at 19, is divided by five and offset from ASCII `2`, then
  followed by the custom `*` glyph and a space; it is not weapon strength
  at `+100`;
- score is the longword at `+76`, printed as six zero-padded digits by
  `0x594E` / `0x5960..0x59A4`, followed by a literal `0` at `0x73A4`.
  The visible seven-digit score is therefore the internal score multiplied
  by ten, not merely `padStart(7)` applied to the internal value.

Alternative status text is assembled at `0x740C..0x743E`: `PRESS FIRE`
at `0x7440`, `PLEASE WAIT` at `0x744B`, and `NO CREDITS` at `0x7457`.
`GET READY!` is at `0x7400`; the pause message begins at `0x274A`.

## Copper bands and COLOR16..31

The fifth plane is enabled only for the HUD strip. Setup
`0x5B28..0x5B7C` emits the following logical raster events. The copper event
compiler at `0x5DD4` adds 44 at `0x5E1E`, so the corresponding hardware
WAIT lines are 52 through 59.

| logical line | hardware line | event | effective COLOR16 for a set HUD bit |
|---:|---:|---|---:|
| 8 | 52 | `BPLCON0 = 0x5200` (five planes) | `0xDDF` first pass, then `0x88D` |
| 9 | 53 | `COLOR16 = 0xAAE` | `0xAAE` |
| 10 | 54 | `COLOR16 = 0xCCF` | `0xCCF` |
| 11 | 55 | no change | `0xCCF` |
| 12 | 56 | no change | `0xCCF` |
| 13 | 57 | `COLOR16 = 0xAAE` | `0xAAE` |
| 14 | 58 | `COLOR16 = 0x88D` | `0x88D` |
| 15 | 59 | `BPLCON0 = 0x4200` (four planes) | fifth plane disabled |

The one-time initial `COLOR16 = 0xDDF` write is at `0x5B1E`, so the first
Copper pass uses `DDF, AAE, CCF, CCF, CCF, AAE, 88D`. The final `0x88D`
write persists into the next frame; the steady-state sequence is therefore
`88D, AAE, CCF, CCF, CCF, AAE, 88D`. Fade processing at
`0x5E4C..0x5E68` accepts only registers `COLOR00..COLOR15`
(`0x180 <= register < 0x1A0`), so neither HUD nor sprite colours fade.

The per-frame writer at `0x2AFC..0x2B60` supplies the hardware-sprite banks.
On a conventional five-bitplane decode these registers would also become
palette indices 17..31; seeing them in the score text is the known AGA failure,
not the intended OCS result:

| registers | value |
|---|---|
| COLOR17, 21, 25, 29 | `0xFFF` |
| COLOR18, 22, 26, 30 | `0x999`, or `0xFFF` while the flash flag is set |
| COLOR19 | phase-table entry `A[p]` |
| COLOR23 | phase-table entry `A[p+1]` |
| COLOR27 | phase-table entry `A[p+2]` |
| COLOR31 | phase-table entry `A[p+3]` |
| COLOR20, 24, 28 | never written by `AMPROG.OBJ`; retain inherited hardware state |

The phase is `uint16(frame_counter) & 15`. The table has 16 phase entries
plus three repeated tail entries so the `p+1..p+3` reads remain contiguous:

```
C00 FF0 FC0 800 F80 F00 C00 FF0 C80 FF0 F80 800 FF0 000 FF0 800
C00 FF0 FC0
```

The writer is skipped during a non-zero black fade, so COLOR17..31 retain
their preceding values for that interval. `COLOR20/24/28` are not set by the
game object, its relevant loader path or the Copper list. Their inherited
value remains relevant to transparent sprite-bank entries, but no longer
blocks the colour of a set HUD-mask pixel.

## Effective OCS mask result

The previous browser model used the conventional five-bitplane equation:

```
index = lower_four_playfield_bits | (hud_mask_bit << 4)
```

That is precisely what produced the yellow/red flicker in `HELI` and
`PRESS FIRE`: moving lower-plane pixels selected COLOR17..31. It is not the
effective output of the original OCS game. For every set bit in the HUD mask,
the measured result is an opaque row-coloured override:

```
mask = 0  -> preserve the four-plane playfield pixel
mask = 1  -> display COLOR16, independent of the lower nibble
```

This conclusion is stronger than a visual guess:

- `0x259C..0x25E4` keeps the specialized `0x5AA4` path selected and writes
  only the separate 352-byte BPL5 mask; it does not erase the lower planes.
- `0x5B4E..0x5B7A` changes only COLOR16, while the native raw frame shows the
  stable `88D/AAE/CCF` gradient over different underlying terrain pixels.
- The game's author describes a non-scrolling fifth plane plus a trick that
  masks the other four, and explicitly notes the red/yellow COLOR16..31
  artifacts when that trick fails on AGA in the
  [Ronald Pieket Weeserik interview](https://codetapper.com/amiga/interviews/ronald-pieket-weeserik/).
- The WHDLoad AGA repair replaces the trick with a sixth-plane mask and a
  uniform replacement colour bank, confirming the intended opaque result.

The exact physical OCS Denise mechanism is still undocumented; the project
therefore records this as a verified effective result, not as a claimed new
general bitplane rule. Hardware sprites remain above the HUD
(`BPLCON2 = 0x003F`), so composition order is software BOBs, effective HUD
mask, then hardware sprites.

## Runtime status (2026-08-30)

`game.html` now reads this embedded font directly from `AMPROG.OBJ`, rebuilds
the 352-byte mask and applies it on canvas rows 8..14 as the measured opaque
COLOR16 override. This removes both the former browser-font approximation and
the incorrect `16|lower4` flicker. The first/steady COLOR16 bands and shifted
COLOR17–31 sprite banks have browser fixtures; high sprite registers are
retained while black fade suppresses their writer. `COLOR20/24/28` still use
an explicit cold-boot zero policy for sprite-bank modelling only.
The shared TOWN hardware-sprite pass is composed afterwards and has separate
fixtures for all four banks, white-fade invariance and channel 0-over-7 pixel
priority, so a sprite/HUD overlap no longer depends on Canvas call-site order.

## Minimal parity tests

1. Verify the 1,008-byte font-block SHA-256 above.
2. Verify the seven rows of `[` and `*` and variable `width + 1` advances.
3. Test score values around decimal boundaries and confirm the appended zero.
4. Test lives `4` and a two-digit value.
5. Rebuild a fresh 352-byte mask and verify 638 bits and the mask SHA-256.
6. Verify right alignment ends at x=312 and no draw touches outside 352 x 8.
7. Test both the first-pass and steady-state COLOR16 row sequences.
8. Test phases 0/15/16/65535, the four shifted accent entries and flash
   changes only to COLOR18/22/26/30.
9. For lower nibbles `0,1,2,7,15`, verify mask 0 preserves the playfield and
   mask 1 always returns the row's COLOR16; moving terrain must not alter it.
10. Verify a playfield fade leaves COLOR16 unchanged and a hardware sprite
    remains above the HUD.
