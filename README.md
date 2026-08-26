# SWIV — an Amiga floppy, fully decoded

Reverse engineering of **S.W.I.V.** (Storm / The Sales Curve, 1991) for
the Commodore Amiga: the disk format, the boot chain, all three
proprietary packers, every graphics format, and the level maps —
documented, re-implemented in portable tools, and verified against
real gameplay footage.

**Try it in your browser:** open the
[disk explorer](https://smikes75.github.io/swiv-amiga-re/) and insert
your own `.adf` image — everything is decoded client-side, nothing is
uploaded, and the page ships no game data.

Built with the same method as
[Captain Beeble](https://github.com/smikes75/captain-beeble-web)
(Atari 8-bit): first a complete, *measured* description of the
original — only then anything else.

## The disk image is not included

The game is copyrighted. This repository distributes **tools and
documentation only**; supply your own disk image and drop it next to
the tools. Everything below was measured against this image:

```
SWIVFIX.ADF   901,120 B
SHA-256       13d8beba136d433971379cc5eb6d6d7707e5cb7874c28301ba57583baa41cb5a
```

Other cracked images exist and will have different offsets — the
tools verify the catalogue rather than blindly trusting offsets, and
`check.py` tells you if your image is the verified one.

## Usage

**Browser:** open `index.html` (double-click works, it runs entirely
locally) and insert your `.adf`. Screens, 900+ sprite frames with
selectable palettes, all seven levels assembled from the map data,
a smooth fly-over mode, music metadata, and the file catalogue.

**Playable transcription:** open `game.html`, insert the same ADF,
press Space and choose TOWN. The TOWN runtime currently routes all 155
map objects; 154 use transcribed behaviour coroutines and the remaining
GOOSE placeholder is deliberately inert instead of inventing enemy fire.
The level fades in from black over 16 frames, as the engine's own fade
driver does — and the HUD stays lit through it, because the fade only
touches COLOR00-15.
Other levels are still research previews, not complete ports.

**Command line:**

```sh
python3 tools/check.py                     # verification contract: measures
                                           #   every claim in docs/ against the image
python3 tools/extract.py SWIVFIX.ADF out/  # unpack all 128 files
python3 tools/dispatch.py                  # extract the 73 gfx → coroutine routes
python3 tools/gfx.py raw ... cover.png     # decode a full screen to PNG
python3 tools/gfx.py sheets out/ sheets/   # sprite sheets for every .LIN
python3 tools/map.py                       # render all 7 levels as tall PNGs
python3 tools/uitest.py                    # Chromium runtime/behaviour regressions
```

Disassembly needs `m68k-elf-binutils` (`brew install m68k-elf-binutils`).

## What is documented

| | |
|---|---|
| bootblock & boot chain | ✅ three `DoIO` reads, linear offsets, **no copy protection** |
| crack layers vs. game | ✅ The Company / N.O.M.A.D layers identified and separated |
| packer A (boot) | ✅ disassembled & re-implemented (`tools/depack.py`) |
| packer B (Bytekiller) | ✅ verified by its own checksum |
| packer C (streaming) | ✅ the in-game format: alternating literal/match blocks, 1 KB ring |
| catalogue & file layout | ✅ all 128 files extracted, byte-exact |
| `.RAW` screens | ✅ 4 bitplanes + palette |
| `.LIN` sprites | ✅ logical frames, chained multi-part composites, signed anchors |
| `.PAM` level maps | ✅ tiles, object spawns, in-map palette script, layers, display window |
| verification | ✅ 37-check contract + frame-by-frame match against gameplay video |
| `AMPROG.OBJ` (55,668 B game code) | 🟨 partially mapped (73-route dispatch + 154/155 TOWN objects, map interpreter, sound, animations, bob drawer) |

Detailed write-ups live in [`docs/`](docs/):
[FORMAT](docs/FORMAT.md) · [LOADER](docs/LOADER.md) ·
[CATALOG](docs/CATALOG.md) · [GRAPHICS](docs/GRAPHICS.md) ·
[MAPS](docs/MAPS.md). Annotated disassembly of both boot-time
decrunchers is in [`src-asm/`](src-asm/).

## Layout

```
├── index.html           browser disk explorer (single file, no dependencies)
├── game.html            playable coroutine transcription (TOWN focus)
├── tools/
│   ├── check.py         verification contract (measures docs against the image)
│   ├── dispatch.py      AMPROG gfx → behaviour coroutine registry
│   ├── extract.py       catalogue + streaming packer C → all 128 files
│   ├── gfx.py           .RAW screens and .LIN sprites → PNG
│   ├── map.py           .PAM level maps → whole levels as PNG
│   ├── unboot.py        walks the boot chain, dumps every stage
│   ├── depack.py        packers A and B in Python
│   └── scan.py          brute-force scan for packed blocks
├── src-asm/             annotated disassembly of the decrunchers
└── docs/                the write-ups (format, loader, catalogue, graphics, maps)
```

Code comments are in Czech (the project's working language); all
documentation is English. The browser explorer speaks both.

## Want to do this for another Amiga game?

The method is the point of this repo. Roughly:

1. bootblock → entropy map → packer signatures (docs/FORMAT.md)
2. disassemble the boot chain, re-implement the packers, verify with
   whatever checksum the original carries
3. find the catalogue through the loader code, not by guessing
4. read the *interpreters* in the game code — data formats have many
   plausible readings, code has one
5. verify against real gameplay footage, not against your own eyes

Everything here is MIT; take the tools and go dig.

## A note on the content

This image is a crack: the original was broken by *The Company*, with
68020+/AGA fixes layered on by *N.O.M.A.D*. The docs identify which
bytes are the game and which are the crack — mixing them up costs
weeks. Game data © 1991 Storm / The Sales Curve Interactive; this
project is unaffiliated fan research and ships none of it.
