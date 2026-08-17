# The loader: crack layers vs. the game

The block loaded to `0x50000` (11,264 B) **is not the game's loader**,
although it looks like one. It is the wrapper of the *N.O.M.A.D* fix,
and the real loader sits inside it. Miss this and you spend a week
annotating foreign code.

## Layers

```
bootblock
 └─ 0x70000  decruncher A ──► 0x60000   crack layer: 68020+/AGA patches, intro
 └─ 0x30000  decruncher B ──► 0x40000   patch installer
                              └─ copies 106 B to address 0x90
                              └─ copies a 256 B TRAP #0 handler to 0x7FF00
                              └─ writes 0x4E40 (trap #0) into the loader at 0x50764
                              └─ jmp 0x50070
      0x50000+0x70            fix wrapper: AGA reset, RAM scan
                              └─ moves 7,424 B (from +0x1D8) into fast RAM
                                 └─ **the game's own loader**
```

`tools/unboot.py` dumps the inner loader as `build/loader.bin`.

## The fix wrapper (`0x50000`, offsets within the block)

| offset | what it does |
|---|---|
| `0x00` | `BPLCON0/1/2/3/4` and `FMODE` back to ECS state — **AGA reset** |
| `0x70` | entry point (jumped to from `0x40000`) |
| `0x84` | installs a `TRAP #1` vector and traps into supervisor mode |
| `0x126` | scans memory in 512 KB steps via `TypeOfMem`, builds a table |
| `0x1AE` | finds a block of a given type in that table |
| `0xE8` | `AllocAbs` 11,264 B — reserves the regions the bootblock used |

The memory table has ten-byte entries `(word type, long start, long
length)` terminated by `0x8001`. It looks for **type 5**
(`MEMF_PUBLIC|MEMF_FAST`), falls back to **type 3** (chip), and
`reset`s if neither exists. That is the advertised support for "all
current memory configs".

## Where the game loads

The `TRAP #0` handler at `0x7FF00` assembles its patch routine **at
runtime** at address `0x8`, then writes into the already-loaded game:

```
a1 = 0x16000                  ; or 0xC11500 when a6 >= 0xC00000
byte 0x4A  -> a1@(100)
byte 0x4A  -> a1@(10148)
word 0x601A -> a1@(154)
```

So **the game code sits at `0x16000`** and the fix patches three
places. The trap fires right after `AMPROG.OBJ` is loaded — the only
moment when the game is in memory but not yet running.

## The game's own loader (`build/loader.bin`, 7,424 B)

Offsets below are within that block.

| offset | what it is |
|---|---|
| `0xE6` | `lea 0x16DC(pc),a6` — **variable base**; the whole loader is a6-relative |
| `0xF6` | own `TRAP #1` vector, supervisor entry, own stack |
| `0x108` | `a4 = 0xDFF000`, `DMACON = 0x8200`, `INTENA = 0xC000` |
| `0x142` | own VERTB handler on vector `0x6C` |
| `0xCFE`, `0xD0E` | allocator (two variants) |
| `0x696` | **open file by name** → returns length |
| `0xA14` | **file read** — streaming, buffered, state in variables |
| `0x592` | the string `AMPROG.OBJ` |
| `0x4CF`, `0xCA4`, `0x196C` | character tables (digits, hex, alphabet) |

The game boots itself with this sequence (offset `0x55C`):

```
lea  AMPROG.OBJ(pc),a0
bsr  0x696          ; open, d0 = length
bsr  0xCFE          ; allocate, a0 = destination
bsr  0xA14          ; read
bsr  0x6B6          ; close
...                 ; clear 32 KB of variables
jmp  0xBE           ; absolute 0xBE = the trampoline the fix planted
```

The disk is read **directly through the hardware**, not via
`trackdisk.device`: `0xBFD100` (CIA-B PRB) drives the motor, drive
select and head stepping; `0xBFE001` (CIA-A PRA) is polled for
`/RDY`, `/TK0` and `/CHNG`.

## A negative result worth recording

Scanning the whole disk for the packers' 8-byte header
(`tools/scan.py`, 512 B step) found **zero** candidates. Files are
not stored as standalone packed blocks — the layout is held by the
catalogue and the loader reads it as a stream.

That matters: **the route to the data is the catalogue, not header
hunting.** See [CATALOG.md](CATALOG.md).
