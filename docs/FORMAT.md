# SWIVFIX.ADF — disk format, boot chain and the two boot-time packers

Everything below is **derived from the disk image itself**, not copied
from elsewhere. Every claim can be verified by a script in `tools/`.

## 1. What this is

`SWIVFIX.ADF` is a floppy image of **S.W.I.V.** (Storm / The Sales
Curve, 1991), a vertical scrolling shooter. Strings inside the
unpacked blocks state the provenance:

```
S.W.I.V from Storm/The Sales Curve
Original cracked by The Company
Fixed for 680x0 / AGA all current kicks and memory configs   ... N.O.M.A.D
```

This matters for planning: the image is **not an original** — it is a
crack with a further patch layer on top. The block unpacked to
`0x60000` (21,548 B) is that foreign layer (68020+/AGA patches plus a
text intro), **not game code**.

## 2. Bootblock

Sectors 0–1. Standard `DOS\0` magic and a valid checksum so Kickstart
boots it, but **the rootblock pointer field holds the signature
`YETI`** (offset 8) instead of the usual 880. Rootblock 880 is garbage
— **the disk has no AmigaDOS filesystem**; it is a linear image with a
custom loader.

The bootblock code starts at offset `0x0C`, calls `AllocAbs`, then
performs three `DoIO` reads on trackdisk. Crucially it uses **plain
linear byte offsets** — no MFM tricks, no custom track format:

| RAM | disk (byte) | sector | length | contents |
|---|---|---|---|---|
| `0x50000` | `0x0D9400` | 1738 | 11,264 B | game's own loader (unpacked) |
| `0x30000` | `0x0D5E00` | 1711 | 2,560 B | decruncher B + payload |
| `0x70000` | `0x0D6A00` | 1717 | 5,632 B | decruncher A + payload |

Then:

```
jsr  0x70000     ; decruncher A unpacks 21,548 B to 0x60000 and jumps there
jmp  0x30000     ; decruncher B unpacks 2,408 B to 0x40000, rts into it
```

The block at `0x40000` disables interrupts and DMA, patches vectors
and jumps to `0x50070` — into the game's own loader.

**There is no copy protection in this image.** That is the single
best piece of news in the whole survey.

## 3. Entropy: everything else is packed

| sectors | entropy | reading |
|---|---|---|
| 0–1663 | 7.3–7.8 | packed data (8.0 is the maximum) |
| 1664–1759 | 5.1 | loader and decrunchers, unpacked |

The image contains **not a single signature of a known packer** (PP20,
IMP!, RNC, ATN!) and no AmigaDOS hunk header. The game carries two
custom formats and its own unpack routines.

## 4. File catalogue

Sector 12 carries a catalogue with names: `AMDLS0.CAT`, `AMPROG.OBJ`,
`HS1.TX`, `TITUNE.MOD`, `BIGEXPL.SN` and fragments of others (`JEEP`,
`MEDTANK`, `FACES`, `SKYE`, `EGG`…). Fragments because the catalogue
itself is packed — an LZ match replaces a repeated substring with a
reference, so only part of each name survives raw inspection.

The `AM` prefix is a trace of **multi-platform development**: SWIV
also shipped on the Atari ST, and the tooling marked Amiga variants
`AM…`. The string `AMPROG.OBJ` also appears inside the loader at
`0x50000` (offset `0x76A`).

## 5. Format B — Bytekiller

The routine is 160 B (`src-asm/decrunch-b.asm`); the re-implementation
is `unpack_b()` in `tools/depack.py`.

Block header (8 B, read forwards):

```
+0  long   unpacked length
+4  long   packed stream length (from +8)
```

The stream is read **backwards from the end in longwords**, bits from
the low end of each longword, numbers assembled **MSB first**. Output
is also written backwards, from the end of the destination. Done when
the write pointer reaches the start.

Bit reading is the classic sentinel trick — the highest set bit of the
longword marks its end, so no bit counter is needed:

```
lsr.l  #1,d0      ; C = X = low bit
bne.s  done       ; longword not exhausted yet
move.l -(a0),d0   ; fetch next (X survives)
eor.l  d0,d5      ; checksum
roxr.l #1,d0      ; X -> bit31 as the new sentinel, new low bit -> C
```

Encoding:

| bits | meaning |
|---|---|
| `0 0` + 3 bits | 1–8 literals (8 bits each) |
| `0 1` + 8 bits | match, length 2, 8-bit offset |
| `1 00` + 9 bits | match, length 3, 9-bit offset |
| `1 01` + 10 bits | match, length 4, 10-bit offset |
| `1 10` + 8 + 12 bits | match, length 1–256, 12-bit offset |
| `1 11` + 8 bits | 9–264 literals |

Offsets count **forward from the current write position**
(`lea (a1,d2.l),a3` then `move.b -(a3),-(a1)`), because everything
runs backwards.

**A checksum for free.** The routine XORs every longword it reads into
`d5` and reads one extra at the end. A correctly unpacked block ends
with checksum 0 — ready-made verification, which `unpack_b()` returns.

## 6. Format A

The routine is 296 B (`src-asm/decrunch-a.asm`), re-implemented as
`unpack_a()`. Same 8-byte header, otherwise a different format:

- read **in words**, not longwords
- numbers taken **straight from the bottom of the shift register**
  (LSB first), masked via the table `0x0001, 0x0003, …, 0x3FFF`
- **no checksum**
- the stream ends with two extra fields: 4 B of initial register and
  2 B holding the count of valid bits in it
- the routine can **relocate the packed data** if output would
  overwrite it

Encoding:

| bits | meaning |
|---|---|
| `1` | one literal (8 bits) |
| `0` + length + offset | match |

Length — a unary prefix selects field width and base:

| prefix | field | length |
|---|---|---|
| `0` | 1 bit | 2–3 |
| `10` | 2 bits | 4–7 |
| `110` | 4 bits | 8–22 |
| `111` | 8 bits | 23–278 |

The value 22 is **stolen as an escape** for a long literal run (then
1 bit selects field width: `1` → 5 bits, `0` → 14 bits; count is
15 + value). Lengths above 22 shift down by one to keep the range
contiguous.

Offset:

| prefix | field | offset |
|---|---|---|
| `0` | 9 bits | 32–543 |
| `10` | 5 bits | 0–31 |
| `11` | 14 bits | 544–16,927 |

Splitting by offset magnitude is why A packs much better than B
(24.7% vs 99.3% on their own payloads).

## 7. What follows

Done: the disk is unprotected, the boot chain is trivial, both packers
are re-implemented and verified. The next stage — the game's own
loader, catalogue and the third (streaming) packer — is covered in
[LOADER.md](LOADER.md) and [CATALOG.md](CATALOG.md).
