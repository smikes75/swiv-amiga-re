# Catalogue, file format and the third packer (format C)

Derived by reading the game's own loader (`build/loader.bin`); the
re-implementation is `tools/extract.py`. With this the disk is
**completely open** — all 128 files can be extracted and unpacked.

## Layout of the file area

The loader addresses **byte offsets from the start of track 1**
(routine `0x864`: `divu #5632` + `addq #1` — 5,632 B = 11 sectors =
one track; track 0 belongs to the bootblock). Offset 0 of the file
area = disk byte 5,632.

```
+0        word      file count N (here 128)
+2        N × long  stored (packed) lengths
+2+4N     file 0, file 1, …  back to back, byte-aligned
```

A file is: `long` unpacked length + a format C stream. **Nothing is
sector-aligned** — which is why brute-force scanning could never find
the files.

File 0 (`AMDLS0.CAT`) is the **name table**: lines separated by `\n`,
line order = file indices. Name lookup (`0x1ec`) compares
case-insensitively. There can be several catalogues
(`AMDLS<n>.CAT`, volume "V0", "V1" — routine `0x71a` builds
`0x5630 + n`); SWIV has one.

## Format C — the streaming packer

The third and final packer on the disk (besides boot-time A and B).
It is designed to be **unpacked while reading from the track** — the
game never holds a packed file in memory.

- bits: per byte, MSB first; numbers MSB first
- **literals bypass the bit stream** — they are copied byte-aligned
  straight from the stream (speed); the bit reader's partial byte
  survives across them
- matches copy from a **1,024 B ring buffer** (10-bit offset) which
  every literal also feeds
- the stream **alternates literal and match blocks** (no "what comes
  next" bit — one bit saved per block); state starts with literals
- the length code (`0xb52`):

| bits | value |
|---|---|
| `0` | 0 |
| `1` + 2 bits | 1–3 (`11` = escape) |
| `11` + 2 bits | 4–6 (`11` = escape) |
| `1111` + **11 bits** | 0–2047 |

- literal block: length = code (0 = empty, just toggles)
- match block: **10-bit offset first**, then length = code + 2;
  values > 63 mean 0 (empty block)

**A trap that cost an hour:** the last code form is not a loop but a
**getbit unrolled eleven times** (`0xba2`–`0xc26`; register `d7` is
unused in it). Only the offset routine (`0xaee`) is a ten-bit loop.
Reading 10 bits instead of 11 decodes the first few literals correctly
and then falls apart silently.

## The read automaton (`0xa14`)

The game reads files in pieces (streaming); the automaton's state
lives in variables at the a6 base:

| variable | meaning |
|---|---|
| `-1100` | mode: 0 = literals, ≠0 = match (toggled by `not.w`) |
| `-1116` | bytes remaining in the current block |
| `-1106/-1104` | bit reader (bit count, partial byte) |
| `-1102` | ring buffer position |
| `-1098` | offset of the current match |
| `-1124` | ≠0: source is RAM (file already loaded), not disk |

`0x966` zeroes everything including the ring before each file. Note
`-1124`: already-loaded files are kept in a list and re-read **from
memory by the same automaton** — hence the dual source paths in
`0x8b2` and `0xb1e`.

## Disk contents (128 files, 835,001 B → 1,383,741 B)

| group | files | format |
|---|---|---|
| `AMPROG.OBJ` | **55,668 B — the complete game code** | 68000, starts with `bra` |
| `AMDLS0.CAT` | name table | `\n`-separated lines |
| `HS1–16.TXT` | default high scores (JOHN BOY, MARY ELLEN…) | text |
| `AMTITUNE/AMHITUNE.MOD` | title & hi-score music | ProTracker `M.K.` |
| `*.SND` | samples (BIGEXPL, SMART) | 8-bit PCM |
| `*.RAW` (9×) | full screens, **40,992 B** | 4 bitplanes 320×256 + 32 B palette |
| `*.LIN` (~90×) | object & terrain-section graphics | custom, see GRAPHICS.md |
| `*.PAM` (7×) | TOWN, DESERT, GRASS, RIVER, ICE, SCIFI, FINAL | level maps, see MAPS.md |

A leading underscore (`_HOUSES.LIN`, `_LAVA.LIN`…) marks scrolling
terrain sections; names without it are objects (JEEP, TRAIN, GOOSE…).
`INST1–5.LIN` map onto the five worlds, the seven `.PAM` onto the
levels.

## What this implies

`AMPROG.OBJ` is 55,668 B — including an embedded file name table right
after the initial `bra`, so roughly ~50 KB of actual code. For
comparison: Captain Beeble was 16,490 B. A full decompilation is
therefore a **~3× larger project than CPB** — but now that is a
number, not a guess.
