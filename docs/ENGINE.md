# The SWIV engine — how the game actually runs

Findings from reading `AMPROG.OBJ`. Every claim carries the address it
was read from. Symbol names live in `tools/syms.json`; the call graph
comes from `tools/xref.py`.

## Behaviours are coroutines (green threads)

The single most important architectural fact: **enemy behaviours are
written as linear programs** that yield. Drivejsi popis zaměnil dva
loader entry pointy: `jsr fp@(-1418)` je kontrola generace/abortu, nikoli
yield. Skutecny cooperative yield vede pres `0x5f0a` na
`fp@(-1438)` a uklada kontext do scheduleru. On top of it:

| routine | meaning |
|---|---|
| `0x62d2` | movement, cull a publikace BOB/collision node, pak `0x5f0a` yield; po resume bit4 scroll compensation, clear flash, orphan, SMART a event callbacky (inherits parent via `+308`, flag bit 3 of `+367`) |
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

Cull callback behem `0x62d2` nefunguje jako okamzity `return`: default
`0x6db4` zneplatni generaci tasku, ale bezici aktivace jeste projde
animatorem, enqueue `0x640c` a yieldem. VBL N tedy udela pohyb, cull
invalidation a jeste publikuje BOB/HW i collision node. Pri resume v N+1
nasleduje bit4 scroll compensation, smazani jednopolickoveho hit flash,
orphan, SMART a event callbacky v poradi bitu `0,3,4,1,2,5`; teprve potom
se zaznam i jeho cost uklidi. Loader kill tedy callbacky nezastavi: po
SMART smrti se jeste vyhodnoti cela ulozena event maska a fyzicky cleanup
probehe jen jednou. Posledni hranicni field proto zustava viditelny a
kolizni.

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
| +364 | off-screen cull margin, initialized by object allocation to −64; **neni to `a2c6` d2**. `0x6486` uses inclusive high-word comparisons and invokes `+538` when `sx <= m`, `sx >= 320−m`, `sy <= m` or `sy >= 256−m`; individual behaviours may override it |
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
| `0xa2c6` | 122 | visual/collision init: d0 graphic, d1 class flags, d2 **vstupni/activation margin**, d3 HP, d4 score, d5 cost; blocks until the d2 threshold but d2 does not overwrite cull `+364` |
| `0x629c` | 112 | wait N frames |
| `0x6c88` | 89 | attach animation sequencer |
| `0x883c` | 73 | random |
| `0x6178` | 60 | spawn child object |
| `0xa2a2` | 10 | formation spawner: d2 total members with (dx,dy,dtype) deltas |

`0xa2a2` does `subq #1,d2` and enters its `dbf` before the clone body:
it allocates `d2-1` children and the original coroutine becomes the last
member. Thus BIRD/FODDERA `d2=4` means four objects total, and YELLOW
`d2=6` means six, not one extra parent.

Cull policy in the TOWN transcription follows the independently initialized
`+364`: ordinary allocations keep −64, including TOKEN after its radial
burst. FLAME changes only its parent to −8; cannon, HOMING, PLOP and
PROXMINE fragments use 0. TOKEN disables culling during the burst and
re-enables the original −64 for its active phase. The GOOSE parent enables
its cull only during escape, while all four children keep it disabled. TRAIN
also keeps the generic callback disabled: its direct `screenY >= 272`
terminator is behaviour code, not `0x6480`. Because that test follows the
return from `0x62d2`, the field just published still survives and cleanup is
observed on the following resume.

Airborne flag bit 4 is applied in housekeeping at `0x6434–0x644e`.
The camera y is saved before a yield and its delta is added back to object
y afterwards. Once active, these objects therefore change **screen y only
by their own velocity**; terrain scroll must not be added a second time.
To plati i pro sebrane MINE core: pickup pouze prepne task do neviditelneho
`wait10`, ale kazde jeho resume nejprve provede bit4 scroll compensation.
Callback vstoupi do waitu v N+1, cost5 jeste drzi v N+10 a jednou jej
uvolni az resume N+11.

## Global difficulty, random state and active cost

`fp@(182)` is **dynamic difficulty D=0..10**, not player count. Routine
`0x1cd4..0x1d02` recomputes it after each scheduler pass:

```
D = min(10,
  (((P1.rank>>8) + (P2.rank>>8) + ((P1.power+P2.power)>>2)) >> 3)
  + max(levelPhase-1, 0))
```

Player rank (`+110`) grows once per live player task with signed saturation,
resets on death and gains 6000 on an extra life. Enemy tasks in the current
VBL therefore read the D produced at the end of the previous VBL. This value
controls FODDER count/shooters, YELLOW and MEDTANK HP, HOMING corrections,
GOOSE cadence, POPUP/PROXMINE activation and other scaling; actual
multiplayer count remains a separate variable.

`0x883c` is a 32-bit state machine, not a host-language random call. It
doubles the state, XORs `$1d872b41` when the add carried or produced zero,
SWAPs its 16-bit halves, then stores and returns that result. The sound CIAB IRQ
`0x4ac8..0x4acc` first adds `VHPOSR` with `ADD.W` to the **high** half of
the big-endian long, without carry into the low half. `game.html` ports both
operations and accepts a captured VHPOS trace; its default zero contribution
is deterministic but cannot claim the hardware's exact beam phase.

The total at `fp@(156)` is accounting, not a universal hard allocation
limit. Only call sites that explicitly invoke `0x8822` reject a task above
160 (TOWN FODDERA/YELLOW). Direct `a2c6` users such as MINE, PROXMINE,
TRAIN, FLAME, ROTO, MEDTANK/CAMOGUN, BIRD, MILL, POPUP, TOKEN and GOOSE
must be charged even when the total temporarily exceeds 160.

## Paula voices and the CIAB sound scheduler

`0x4a66` installs a roughly 204.8 Hz CIAB interrupt which resumes four
persistent sound coroutines in Paula order AUD3/AUD2/AUD1/AUD0. Requests use
`priority*4` guards, strict unsigned replacement and an x-selected stereo
pair with fallback to the opposite pair. Procedural waveforms, per-voice
noise scratch, exact event hooks and remaining TOWN effects are documented in
[SOUND](SOUND.md).

The two disk samples use that same allocator rather than a separate mixer:
`BIGEXPL.SND` supplies explosions and `SMART.SND` is submitted four times by
the white-flash task. TOKEN pickup is a two-level scheduler case: a 50 Hz
priority-100 task attempts notes at VBL 0/5/10/15, while each accepted note is
then advanced by its own 204.8 Hz sound coroutine. `0x5614` only captures the
TOKEN side and enqueues that task; it does not play the first note inline.
Equal-priority insertion is strict creation FIFO, including existing object
callbacks, fresh `0x894a` explosions and the separate SMART `0x885a` start.
For a type-4 TOKEN the pickup-sound child is therefore started before the
SMART child; the fourth SMART request may then preempt its first note.

The `0x56e6` noise polynomial is taken when the preceding `ADD.L` carries or
produces zero (`BHI` skips it only for clear carry and non-zero result). GOOSE
hit `0x4e46` also demonstrates why sound tasks remain live when muted: each
accepted voice seeds that scratch from gameplay RNG only after its initial
CIAB yield, while rejected or earlier-preempted requests consume no seed.

Procedural rendering preserves signed 16-bit period arithmetic internally and
converts the final Paula register word to unsigned only when producing audio.
Waveform address advance is capped at PAL's minimum DMA period 123 as a
WebAudio approximation of the hardware's previous-sample reuse. Exact
below-minimum cadence additionally depends on scanline DMA-slot phase and is
kept as an explicit measurement gap.

The scheduler is also why PRNG perturbation is not a once-per-VBL operation:
`0x4abc` reads `VHPOSR` on every sound interrupt. The browser accumulates the
exact rational CIAB rate inside each 50 Hz game step, leaving the default beam
word at zero until a hardware trace is available.

## Collision scheduling

Ordinary object tasks run at priority 100, the player projectile updater at
`0xfffe` and the collision sweep at `0xffff`. Consequently a collision found
at the end of VBL N is consumed by object callbacks on their resume in VBL
N+1; `0x62d2` has already published the normal N frame.

Collision node `+488` (list at `fp@(11058)`, sorted by x): `+8/+10`
position, `+12/+14` half-extents, `+16` class, `+18` event word. `0x6dce`
installs it with extents 8/8; every `0xa2c6` object immediately overrides
them via `0x6d7c` with words `+16/+18` of its d0 frame record, which the
loader `0x457e` fills from **bytes 8/9 of the .LIN part header** (FODDERA#2
= 10/20, MINE#0 = 12/14, POPUP#0 = 17/15 ...). The player (`0x6dc8`), its
bolts and the cannon keep 8/8. The sweep `0x6ec2` tests each neighbour's
*position* against the sweeping node's *own* box (inclusive) and ORs the
classes into both event words; a node whose class has bit 15 (PLOP, MEDTANK
turret) never sweeps itself. Node positions are copied from `+320/+324` at
task resume (`0x6430`, before the bit-4 scroll compensation `0x6446`), so
the sweep at the end of VBL N sees the positions the bodies computed in
VBL N−1 — exactly what `0x642c` published as BOBs — while the N+1 callback
reads coordinates one movement newer (measured: FODDERA death puff 4 px
below the contact position). The browser keeps a per-object snapshot
(`snapNode`/`nodePos`, valid for one tick) for the same effect and reads
box extents from the frame header (`NODE_GRAPHIC`, `nodesTouch`). Events coalesce as a
16-bit OR mask and callbacks dispatch in bit order `0,3,4,1,2,5`.
The browser now keeps that boundary: the producing step only records pending
bits and projectile consumption, while the next step clears the old hit flag,
checks the current SMART pulse and dispatches the saved event before the
object's next movement. A cull-invalidated ordinary node likewise keeps its
N publication/sweep, passes the saved N+1 bit4/flash/orphan/SMART/event
housekeeping, and is cleaned up only afterwards. Generation invalidation
uvnitr SMART nebo prvniho callbacku uz dalsi callbacky nepotlaci: poradi je
`SMART -> bit0 -> bit3` (obecne pak zbytek `4,1,2,5`) a stejny objekt muze
zdrojove projit vice death-effect/score callbacky, zatimco jeho zaznam a cost
se uvolni jen jednou. The player resumes before
input; consumed player bolts are removed by the relocated `0xfffe` updater
immediately before the
next sweep. Creation-order snapshots keep children spawned by an N+1 callback
out of housekeeping until their own following resume, while still allowing
their first field in the current scheduler pass. The same creation-VBL drain
now covers fresh PROXMINE fragments, FLAME emitter/puffs and TRAIN cars; an
attached animator publishes `seq[0]` before starting its full period. The
SMART `0x885a` wait50 deadline je rovnez priority-100 task a pulse shazuje ve
sve creation-order pozici mezi starsimi a mladsimi objekty.

GOOSE smrt pouziva stejny model: `a36a` pouze zaradi samostatny `0x894a`
child (EXPL1#7..13 period4 a dve BIGEXPL zadosti), parent nejprve unlinkne
deti a jejich `+542` callback se provede az na vlastnim resume. Escort pouzije
posledni publikovanou world pozici a az po enqueue sve exploze spotrebuje
zbyvajici snake RNG. Pozde startujici body child smi po smrti parentu dokoncit
delay, uctovat cost a publikovat jeden creation field; orphan jej uklidi az
pri dalsim resume. Parent drzi cost100 pres 107 checksum yieldu a uvolni jej
presne v N+108 ve sve FIFO pozici.

Remaining limitation is full callback/continuation interleaving across every
priority-100 category. Browser stale nema jednu univerzalni frontu pro vsechny
continuations a fresh children. TOKEN sound, SMART start and `0x894a` explosion
children uz ale sdileji creation-order drain a splatne dalsi TOKEN noty se
radi mezi existujici continuations. Otevrene jsou zejmena TRAIN
checksum/map-reader yield a vzacne same-VBL RNG/audio soubehy ostatnich
kategorii, jak sleduje `GAPS.md`.

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
previous frame, cooldown reloaded from player-struct `+98`; pri aktivnim
druhem hraci se pouzije `max(+98,10)`, jinak ulozena hodnota. Cooldown
se zmensuje o globalni frame delta.

**Hardware sprites confirmed**: the copper builder `0x5d86` writes
SPR0PTH.. (reg `0x120+`) for **8 sprite slots of 548 B each**.

The TOWN browser runtime now models the producer at `0x3d00/0x3d4e` as one
shared 64-record queue for the player projectile pool, cannon and the second
PLOP frame. Allocation uses the native remaining-count channel sequence,
skips negative VSTART before consuming a record, preserves linear per-channel
DMA blocking, maps channel pairs to the four COLOR17–31 banks and composites
channel 0 last. Player bolts retain the native 30-slot pool and receive both
their own velocity and camera delta in the spawn VBL; cannon depth is sampled
before its current `0x62d2` movement. Equal-priority FIFO insertion also lets
new cannon/HOMING/PLOP children run once in the spawning scheduler sweep:
cannon and HOMING already move, while the PLOP animator publishes BULLET#2
and kills it on the next resume. This implementation is scoped to the
transcribed TOWN producers; later-level producers still need their own audit.

### Player life, continue and closing phases

Browserova reprezentace `g.lives` je zasoba pred aktualnim spawnem, ne primo
cislo vypsane v HUD. Startovni `4` se formatuje jako `HELI 3`; interni `1`
je posledni aktivni `HELI 0`. Smrt nastavi player tasku `respawnT=100`, ale
nezastavi hlavni scheduler. Teprve po sto VBL se dekrementuje zasoba: kladny
vysledek znovu zalozi playera, nula otevre post-life automat.

Automat ma tyto pozorovatelne faze:

- `active/death wait`: mapa, vsechny enemy tasky i efekty bez preruseni bezi;
- `continue`: 300 VBL pri alespon jednom kreditu, jinak 100 VBL. Vstup fire
  je level-triggered, takze uz drzene tlacitko muze kredit spotrebovat v
  prvnim fieldu;
- prijeti kreditu resetuje pouze `lives/score/nextLife` na `4/0/10000`
  (a rank/collision mezistav). Playerova weapon power, TOKEN counter a mode
  preziji; nasledujici weapon-table aplikace smi power pouze clampnout dolu;
- `closing`: join je zavreny, credit word se obnovi na tri, TOWN
  per-VBL `COLOR07` writer je vypnut a `fadeBlack` roste po 16 na VBL,
  tedy z nuly do plne cerne za 16 VBL;
- `stats`: az zde se nastavi `g.over=true` a zastavi se svet. Smrt,
  100-VBL wait, continue i closing fade tedy nejsou game-over stop stavy.

Inactive HUD je soucast tohoto automatu. `tick & 0x80` strida dva 128-VBL
pulcy: prompt (`PRESS FIRE`, `NO CREDITS`, nebo `PLEASE WAIT`) a dynamicky
status. Nepripojeny P2 slot drzi `jeepLives=1`, takze statusova pulka je
`JEEP 0`. Browser ma presny phase/timing kontrakt, ale jeho `stats` kresba,
vsechny nativni statisticke citace a high-score/return-to-title tok jsou stale
samostatna otevrena rendererova a datova vrstva.

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
  0x88D**. A set mask bit has the measured effective OCS result COLOR16,
  independent of lower4; conventional `16|lower4` is the AGA failure.
  Projectile sprite colours come separately from `0x2afc` (COLOR17–19).
  Canvas prevod skutecnych COLOR16–31 slov pouziva z headless-vAmiga
  baseline zmerenou radu high nibblu `106,123,141,159,178,197,216,236`;
  fitted mapova paleta je od teto registrove cesty zamerne oddelena.
- A level-select cheat handler reads raw keys at `0x20e4`.
- The normal attract dispatcher starts at `0x0d64`. The browser follows its
  COVER -> Sales Curve -> HELI blueprint/scores -> JEEP blueprint/scores ->
  FACES loop from indexed disk assets and embedded program data. Blueprint
  page replacement, palette work and typewriter continuations retain their
  native order and are synchronized to the measured loader path.
  From the internal task spawn, BP2 is published after 51/45 VBL and the
  first HELI/JEEP text continuation after 63/57 VBL. The unchanged core then
  reaches BP1 swap at 190/186 and generation at 257/253 VBL. A separate
  score-loader handoff holds that final page until the first score field at
  382/335 VBL; measured BP2-to-score visibility is therefore 331/290 VBL.
  The first narrative worker field is primed to three/two words, while the
  specs worker publishes only its rule. Dense frames also show buffered
  palette publication rather than every intermediate write: BP1 holds the
  white-level-96 field before its endpoint, and the score fade collapses to
  the measured dark/black fields without changing those timing boundaries.
- `0x0f42` is not the title entry: it is the conditional post-game
  `CONGRAT2.RAW` branch. It selects palette `0x2abc` and starts the REACTOR
  animation tasks; that branch remains separate from the normal attract
  transcription.
