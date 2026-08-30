# The SWIV engine — how the game actually runs

Findings from reading `AMPROG.OBJ`. Every claim carries the address it
was read from. Symbol names live in `tools/syms.json`; the call graph
comes from `tools/xref.py`.

## Behaviours are coroutines (green threads)

The single most important architectural fact: **enemy behaviours are
written as linear programs** that yield. `jsr fp@(-1418)` (resident
loader) = *wait one frame* — it stores the coroutine context and
returns to the scheduler. On top of it:

| routine | meaning |
|---|---|
| `0x62d2` | yield one frame + housekeeping (inherits position from a parent object via `+308` when flag bit 3 of `+367` is set) |
| `0x62cc` | yield until "alive" tick |
| `0x629c` | wait `d0` frames (against the global tick `fp@(-66)`) |
| `0x62b8` | wait `d0` yields |
| `0x9afa` | wait until this object scrolls within −32 px of the screen |
| `0x9ac8` | same, preloading graphics while waiting |

A behaviour therefore reads like: *create visual → wait until on
screen → loop: aim, wait 4, fire, wait 60 → die.* This is why the
code region `0x7600–0xCC00` (~24 KB) looks like hundreds of tiny
routines — they are scripts, and they are exactly what we must
transcribe to make behaviours identical.

## The object

546-byte structs (`0x617a` alloc, `0x6160` clone-spawn, template
defaults at `0x61f4+`). Known fields:

| offset | meaning |
|---|---|
| +8/+12 | animation script pointer / current graphic |
| +276 | spawn TYPE, then reused as behaviour state |
| +308 | parent object (position inheritance) |
| +320/+324 | x / map-y |
| +328 | third position/depth coordinate |
| +332.. | velocity area (cleared on spawn) |
| +356 | misc param (e.g. countdown ×896 seen) |
| +358 | **angle, 0–255 = full circle** |
| +360 | hit points installed by `0xa2c6` from d3 |
| +362 | score value installed by `0xa2c6` from d4 |
| +368 | loaded graphic/file handle from `0xa2c6` d0 |
| +370 | active-budget cost installed by `0xa2c6` from d5 |
| +364 | off-screen cull margin (−64 default): `0x6486` kills via `+538` when `sx <= m`, `sx >= 320−m`, `sy <= m` or `sy >= 256−m`; objects override it (`0x820c` −90, `clrw` = 0) |
| +367 | flag bits (bit 3 = follow parent; bit 4 = compensate camera-scroll delta) |
| +376 | death-effect coroutine template spawned by `0xa36a` (default `0x894a` = small EXPL1 puff with panned sound) |
| +397 | flags (bit 0 inherited on spawn) |
| +486 | cleared on spawn |
| +508 | saved/restored around waits (`0x9ae8`) |
| +510..+530 | six collision/event callbacks (default no-op `0x6288`) |
| +534/+538/+542 | routine pointers; `st` on the first byte makes them negative = disabled, `sf` re-enables. `+534` = smart-bomb handler (called each tick while `fp@(169)`, `a2c6` sets `0xa36a`), `+538` = off-screen cull handler (default `0x6db4` = kill self), `+542` = orphan handler (called each tick when `+308 == 0`; `0x6144` sets `0x6db4`, `0x617a` sets −1) — see `0x6458`–`0x64b4` |

## Key utilities (by call count, `tools/xref.py`)

| addr | calls | role |
|---|---|---|
| `0xa2c6` | 122 | object visual init: d0 graphic, d1 timer, d2 anim offset, d4/d5 params; **blocks until on screen** |
| `0x629c` | 112 | wait N frames |
| `0x6c88` | 89 | attach animation sequencer |
| `0x883c` | 73 | random |
| `0x6178` | 60 | spawn child object |
| `0xa2a2` | 10 | formation spawner: d2 total members with (dx,dy,dtype) deltas |

`0xa2a2` does `subq #1,d2` and enters its `dbf` before the clone body:
it allocates `d2-1` children and the original coroutine becomes the last
member. Thus BIRD/FODDERA `d2=4` means four objects total, and YELLOW
`d2=6` means six, not one extra parent.

Airborne flag bit 4 is applied in housekeeping at `0x6434–0x644e`.
The camera y is saved before a yield and its delta is added back to object
y afterwards. Once active, these objects therefore change **screen y only
by their own velocity**; terrain scroll must not be added a second time.

## Aiming: angle → sprite frame

`+358` holds an 8-bit angle. Helpers quantize it into frame tables:

- `0xa252`: (angle+16) & 0xE0 → **8 directions** → word table → set graphic
- `0xa268`: (angle+8) & 0xF0 → **16 directions** → word table → set graphic
- `0xa27c` / `0xa290`: same but *add* the table offset to a base graphic word

The 16-direction shot sprites (BULLET frames) are selected by exactly
these helpers — the direction→frame mapping is whatever the table
passed in `a0` says, per object. Transcribing those tables gives the
authentic mapping; no guessing.

## What this changes about the reimplementation plan

Faithful behaviour = transcribing coroutine scripts, which is far more
tractable than untangling state machines: each enemy is a readable
linear program built from ~a dozen utility calls. The path to a
pixel-identical game is: name the utilities (done above), then
transcribe scripts one enemy at a time, verifying trajectories against
gameplay footage.

## Input, the player, and hardware sprites (phase-2 additions)

**Input.** The resident loader's VERTB handler polls devices into
a6-negative variables; `0x71ac` assembles a per-player byte from
`fp@(-31)` (directions, bits 4–7) and `fp@(-28)` (fire buttons).
Alternative sources `fp@(-44)/(-42)` (keyboard/second stick decode
tables live in the loader) are selected per player via the player
struct — **two player structs at `fp@(11176)` and `fp@(11356)`**
(180 B apart; +60 object ptr, +64/+66 input mode, +90..+98 input
state).

**Fire cadence** (`0x7266`): press-edge detection against the
previous frame, cooldown reloaded from player-struct `+98`, floored
at 10 ticks under a powerup condition, decremented by the global
frame delta.

**Hardware sprites confirmed**: the copper builder `0x5d86` writes
SPR0PTH.. (reg `0x120+`) for **8 sprite slots of 548 B each**.

**The copper event compiler** (`0x5dd4`): two sorted event queues
(`fp@(11106)`/`fp@(11120)`) are merged per frame into copper
`WAIT(line)` + `MOVE` pairs. Fades (`0x4a48`) are applied only to
registers `0x180–0x19F`; **writes to `0x1A0+` (sprite colours) pass
through unfaded** — the sprite palette is set through these queues at
level start and is immune to the level's palette script. (For the
remake, the effective sprite palette can be sampled from gameplay
footage until the init-time queue entries are transcribed.)

## The behaviour inventory (`tools/tasks.py`)

Scanning for `lea X(pc),a0` followed by a spawner call yields the
complete coroutine map: **116 spawn sites, 64 unique behaviour entry
points**, concentrated in `0x7000–0xB000`. This is the transcription
worklist for phase 3 — every enemy behaviour in the game is one of
these entries. `build/coroutines.json` holds the list.

Also read along the way:

- HUD copper events (`0x5b34`): BPLCON0 switches 5↔4 bitplanes around
  the HUD strip, and **COLOR16 changes per band: 0xAAE / 0xCCF /
  0x88D** — light steel-blues of the fifth HUD bitplane. Projectile
  sprite colours come separately from `0x2afc` (COLOR17–19).
- A level-select cheat handler reads raw keys at `0x20e4`.
- The title sequence (`0xf42+`) loads COVER.RAW with palette `0x2abc`
  and preloads REACTOR frames for the logo animation.
