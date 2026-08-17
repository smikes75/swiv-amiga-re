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
| +332.. | velocity area (cleared on spawn) |
| +356 | misc param (e.g. countdown ×896 seen) |
| +358 | **angle, 0–255 = full circle** |
| +360 | timer |
| +362/+368/+370 | visual params from `0xa2c6` (d4/d0/d5) |
| +364 | draw priority (−64 default) |
| +367 | flag bits (bit 3 = follow parent) |
| +376 | handler (default `0x894a`) |
| +397 | flags (bit 0 inherited on spawn) |
| +486 | cleared on spawn |
| +508 | saved/restored around waits (`0x9ae8`) |
| +510..+530 | six collision/event callbacks (default no-op `0x6288`) |
| +534/+538/+542 | routine slots / state markers (−1, `st`/`sf` toggles) |

## Key utilities (by call count, `tools/xref.py`)

| addr | calls | role |
|---|---|---|
| `0xa2c6` | 122 | object visual init: d0 graphic, d1 timer, d2 anim offset, d4/d5 params; **blocks until on screen** |
| `0x629c` | 112 | wait N frames |
| `0x6c88` | 89 | attach animation sequencer |
| `0x883c` | 73 | random |
| `0x6178` | 60 | spawn child object |
| `0xa2a2` | 10 | formation spawner: d2 clones with (dx,dy,dtype) deltas |

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
  0x88D** — the light steel-blues of the score text and shots.
- A level-select cheat handler reads raw keys at `0x20e4`.
- The title sequence (`0xf42+`) loads COVER.RAW with palette `0x2abc`
  and preloads REACTOR frames for the logo animation.
