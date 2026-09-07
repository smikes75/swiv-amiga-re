# SWIV sound engine and TOWN event map

Addresses refer to the verified 55,668-byte `AMPROG.OBJ`. This is a direct
transcription contract, not a list of approximate WebAudio replacements.

## Runtime architecture

`0x4A66` programs CIAB timer A with latch `0x0D88` and installs interrupt
`0x4ABC`. With the PAL E-clock this advances the sound scheduler at about
204.8 Hz, independently of the 50 Hz game step. The interrupt also performs
the `ADD.W VHPOSR` perturbation of the global PRNG before resuming the four
sound coroutines.

The four 268-byte voice structures map, in memory order, to Paula channels
`AUD3, AUD2, AUD1, AUD0`. A request stores `priority * 4` as its guard. Every
sound IRQ decrements a non-zero guard; a new request is accepted only when
its guard is strictly greater than the selected old guard. Equal priority is
therefore rejected.

Position chooses a preferred stereo pair, not a hard limit:

| signed x | first pair | fallback pair |
|---:|---|---|
| `< 160` | structs 0/3 = AUD3/AUD0 | structs 1/2 = AUD2/AUD1 |
| `>= 160` | structs 1/2 = AUD2/AUD1 | structs 0/3 = AUD3/AUD0 |

Within each pair the lower guard wins; a tie keeps the first structure.
`0x4B8C/0x4BB4` fall through to the opposite selector only if the preferred
pair rejects the request.

Procedural voices keep a private 256-byte scratch area. Generator `0x56E6`
starts with the complemented first long, shifts/XORs polynomial `0x1D872B41`,
swaps words and writes big-endian longs back into that same persistent
scratch. Its `BHI` skips the XOR only when carry and zero are both clear, so
a doubled zero also takes the polynomial branch. The cold-zero first 32 bytes
are:

```
d4bfe278efb1b4f842b1c2e485c88563218716162c2c430e861c58589bf111bf
```

## Gameplay effects implemented locally

| event | native path | priority | implemented result |
|---|---|---:|---|
| one player volley | `0x8AA0 -> 0x4F3E` | 20 | 16-byte waveform, volume 32..1, period 1000 with `p += p>>4`; once even if the 30-slot projectile pool is full |
| non-lethal default hit | `0xA352 -> 0x5070` | 20 | 16-byte waveform, volume 64..4 by 4, period 200 with `p += p>>2` |
| POPUP/PROXMINE/FLAME opening | `0x5138` | 80 | two independent swept voices `(base=2500,hold=50)` and `(2227,90)` |
| each FLAME puff | `0xABD2 -> 0x50D0` | 40 | persistent-noise rise at period 500, then decay at period 1000; native pan input is zero |
| HOMING launch | `0x8566 -> 0x528A` | 80 | 64 fresh-noise states, period 320..257, volume 64..1 |
| cannon launch | `0x9606 -> 0x53BE` | 50 | 48 noise states, raw volume 96..2, changing sample length and signed period recurrence |
| DESERT EGGS#2 lethal ring | `0x8510 -> 16x 0x95CA` | 50 | sixteen cannon requests at angles 0,16,…,240 in one fresh-task FIFO; ordinary non-lethal `0x852A` hit is deliberately silent |
| DESERT BLACKJET activation | `0x7AD8 -> 0x52D8` | 70 | 203 64-byte fresh-noise states; 32-step volume rise at period 300, then 171-step decay while period rises 300..640; every state lasts two CIAB IRQs |
| each DESERT EGGS pod shot | `0xA9A0 -> 0x5436` | 100 | two panned 8-byte square-wave layers, volume 48..1; second layer is delayed eight CIAB IRQs |
| DESERT EGGS#12 root death | `0x8876 -> 0x4C3C` | 60 | two right-preferred `BIGEXPL.SND` layers at periods 768 and `769+(RNG&7)`; exactly one RNG even on rejection; callback clears the voice guard on IRQ 4 while DMA keeps playing |
| standard death/explosion | `0x894A -> 0x4C58` | 50 | two `BIGEXPL.SND` voices, each with its own `period=592+(RNG&31)`; the same IRQ-4 callback releases both guards without truncating DMA |
| player burst | `0x9306 -> 0x88FC -> 0x4C1C` | 100 | four fixed `BIGEXPL.SND` requests at periods 1024, 1032, 1152 and 1160 |
| white/smart flash | `0x885A -> 0x4CB2` | 127 | four `SMART.SND` layers at periods 1040, 1025, 1010 and 996 |
| bound MINE shield starts | `0x98F2 -> 0x4FFE` | 60 | one 48-state tone, volume 48..1, period cycle 150/150/154/158/162/162/158/154 |
| each TOKEN pickup | `0x97CE -> 0x5614 -> 0x5672` | 120 | four-note procedural chime at periods 159, 212, 159 and 141, spaced five VBL apart |
| GOOSE non-lethal hit | `0xC97E -> 0x8834 -> 0x4E46` | 40 | two stereo-preferred 24-byte noise voices, volume 64..1 and period 150..950 |
| GOOSE death synth | `0xC998 -> 0x8838 -> 0x553A` | 100 | left/right-preferred procedural pair, followed by the normal two-layer explosion |

The standard explosion's double execution is intentional. `BSR.W` at
`0x4C5A` has `0x4C5E` as both target and return PC, so the body runs once as
a subroutine and once again by fall-through. It advances global RNG exactly
twice before allocation, including when muted or when all voices reject it.
For each accepted layer callback `0x4C72` clears the allocator guard on IRQ4;
the already-latched Paula DMA sample continues playing and is stopped only
if that now-free channel is subsequently preempted.

EGGS#2 queues all sixteen `0x95CA` children before it queues its standard
explosion. Their fresh priority-100 starts therefore run shell0…shell15,
then `0x894A`. All requests use priority 50, but their concrete acceptance is
not a pure VBL property: asynchronous CIAB IRQs can lower a guard between two
fresh-task starts and also perturb the global seed through VHPOSR. The browser
keeps a deterministic no-intermediate-IRQ policy until a beam/IRQ trace is
available; the exact request order and the explosion's two gameplay RNG calls
are independent of that policy. If SMART is already pending, its older
explosion child starts before the ring instead; the shared creation-ordinal
FIFO preserves both cases.

BLACKJET requests its sound only after its cost guard accepts the actor and
after the same single RNG call that chooses x. Its callback first yields,
then rewrites 16 scratch longs per state. State starts are IRQ 1, 3, 5…405
and cleanup is IRQ 408. The priority-70 guard reaches zero at IRQ 280 while
the callback can continue to completion; a later accepted request may
therefore preempt that tail exactly as on the native four-voice scheduler.

Each EGGS pod queues its projectile as a fresh priority-100 task. Existing
left/right pod continuations therefore enqueue both shot tasks before either
shot creates its one-field PLOP: BOB ordinal order is shot-L, shot-R,
PLOP-L, PLOP-R, and the active-cost steps are 5, 10, 11, 12. Each PLOP
releases its cost1 on its own N+1 priority-100 resume, before any younger
spawn guard. `0x5436` reads the signed shooter x and submits two
priority-100 voices. Its waveform is `7f 80 7f 80 7f 7f 80 80`; 48 states
use volume 48..1 and alternating period `acc±20`, with
`acc += ASR.W(acc,5)` from 200. The first periods are 220/186/232/198 and
the last are 688/750/732/795/779. The first layer is audible on IRQ2 and
cleans up on IRQ50; the second starts on IRQ10 and cleans up on IRQ58. No
RNG is read. Simultaneous sides of the x95 root allocate
AUD3,AUD0,AUD2,AUD1; the x261/x318 roots mirror that to AUD2,AUD1,AUD3,AUD0.

The root's custom `0x8876` death is deliberately not `sfxBigExplosion`.
Its first priority-60 request uses period768, its second period
`769+(RNG&7)`; both ignore root x and prefer AUD2/AUD1. Only the second
period reads RNG. Three visual puffs at t=0/15/30 each consume one further
RNG but are silent, so the isolated root effect advances RNG exactly four
times. Both accepted raw voices release their guards on IRQ4 without
truncating DMA. The t15/t30 waits retain the root task's creation ordinal;
if its EXPL2 main is culled, later puffs and their RNG reads are cancelled,
while a cull first reached on an exact puff deadline happens after that puff.
Orphaned pods subsequently run ordinary `0x894A` and each consume their own
two RNG values.

`SMART.SND` is the original 8,280-byte signed 8-bit mono sample, not a
browser replacement. `0x4CB2` sends it through the right-preferred selector
four times; on empty voices the request order is AUD2, AUD1, AUD3, AUD0. Each
voice starts DMA on IRQ 2. The sample finishes before its priority-127 guard
reaches zero on IRQ 508; the native coroutine then remains over a silent
one-word reload until cleanup on IRQ 65539. Every `0x8852` trigger retries all
four layers even while another white-flash task is active.

The visible MINE shield and TOKEN type 3 are separate protection mechanisms.
The first MINE-core pickup sets player field `+106=-1`; only the subsequently
created bound child at `0x98F2` plays the shield tone, once, from the player's
current x position at child start. A duplicate active core and a shot core do
not play this tone. Every actual TOKEN pickup, of any type, instead captures
the TOKEN x position and enqueues a priority-100 child; the pickup callback
itself produces no audio. That child runs notes at VBL offsets 0, 5, 10 and
15 and resumes in strict creation order among existing object tasks. Shooting
a TOKEN, dropping it, or culling it is silent. Each note has 64 two-IRQ states
and cleanup on IRQ 130; scratch rewrites remain live so later noise effects
inherit the same per-voice bytes as on the Amiga.

Direct PC/audio captures put the first non-zero TOKEN state at 28.9975 ms
after pickup; the browser path is 28.9926 ms. The GOOSE synth begins near
9.50 ms natively and 9.77 ms in the browser. Its two accepted BIGEXPL layers
start at 19.617/19.673 ms natively and about 18.976 ms locally; the remaining
sub-millisecond difference is deliberately left to the future scanline/CIA
phase model instead of being hidden by an event-specific fixed delay.

`0x8852` likewise enqueues the separate priority-100 `0x885A` SMART child.
Fresh TOKEN, SMART and `0x894A` explosion children share one creation-order
drain. A type-4 pickup creates TOKEN first and SMART second, so the initial
period-159 request precedes the four SMART requests; their fourth layer can
preempt that TOKEN voice.

GOOSE hit is deliberately not panned from the boss x coordinate. `0x4E46`
first requests selector `0x4BB4`, then `0x4B8C`; each retains the normal
opposite-pair fallback. An accepted callback initially yields, and only on
its second CIAB resume calls global RNG once, seeds its private scratch and
starts 64 local `0x56E6` states. The short loop branch returns to `0x4E7C`,
after the RNG call. A rejected layer, or one preempted before that resume,
therefore consumes no RNG. Cleanup is on IRQ 66.

Current event hooks preserve the native exclusions:

- default non-lethal HIT is used for ordinary spawn, non-BIRD air and hazard
  callbacks; a lethal callback plays the explosion without an extra HIT;
- BIRD non-lethal damage is silent, MINE core's non-lethal hit is silent and
  GOOSE uses a separate custom hit;
- rejected aimed cannon launches are silent, while direct cannon spawns are
  audible;
- PROXMINE at difficulty zero is removed before its opening sound;
- standard explosions are attached to MINE/PROXMINE detonation, normal
  lethal callbacks, HOMING destruction, smart-pulse victims and the orphaned
  GOOSE escort rather than blindly to every visual `spawnBoom`.

The HOMING routine inherits an unresolved D0 at its sound call. The browser
uses explicit deterministic pan value zero until that register provenance is
closed; it does not claim that the missile's x coordinate is native.

## Attract music and verified A500 output path

The browser loads `AMTITUNE.MOD` from the inserted disk, starts it after the
COVER fade, keeps it alive across the normal attract loop and stops it in
`startGame()` before TOWN begins. Its ProTracker path uses the period and
vibrato tables, per-nibble `4xy` memory, hard Paula LRRL stereo and the effect
set exercised by the disk modules rather than a pre-rendered replacement.

Both that module and the four TOWN effect voices feed one shared post-mix
A500 output path. The verified order is gain `0.2048`, the fixed one-pole
low-pass at approximately 4.421 kHz, then the fixed one-pole high-pass at
approximately 5.13 Hz. These stages belong after the Paula channel sum, not
on each voice independently. The power-LED two-pole low-pass at approximately
3.091 kHz is disabled after boot in SWIV and must not be inserted into either
the attract or level-one path.

## Browser timing model and tests

`game.html` keeps the logical four-voice state alive even without an
`AudioContext`. A procedural callback first yields, writes its first audible
state on the second CIAB resume and clears its guard through `0x4BF2` one
resume after the final audible wait. WebAudio buffers use Paula's unsigned
16-bit period even where the original `ASR.W` recurrence makes the working
value negative. Waveform address advance is capped at the PAL DMA minimum
period 123: this is a WebAudio approximation of the previous-sample reuse
that occurs when Paula cannot fetch the next byte. It removes the incorrect
ultrasonic waveform walk in the low-period half of the GOOSE death synth;
an exact reuse pattern still needs scanline DMA-slot phase.

`tools/uitest.py` checks:

- left allocation `[AUD3,AUD0,AUD2,AUD1,reject]` and the mirrored right order;
- strict guard comparison, pair fallback and per-IRQ guard decay;
- exact FIRE, HIT, opening, HOMING, cannon, FLAME and GOOSE state counts;
- exact BLACKJET 203-state/two-IRQ volume-period sweep, scratch rewrite count,
  guard/RNG activation gate and cleanup IRQ;
- exact EGGS shot waveform, all 48 periods, IRQ50/58 lifetimes, signed-x
  stereo allocation and shot/shot/PLOP/PLOP creation FIFO;
- EGGS root periods/channels plus its one audio and three puff RNG advances;
- all four SMART sample periods/channels, raw length, guard/tail and WebAudio
  pitch/start time;
- the bound-shield 48-state tone and TOKEN four-note VBL scheduler, including
  its zero-audio enqueue, creation FIFO against existing GOOSE callbacks,
  SMART/`0x894A` children, per-IRQ scratch writes and cleanup;
- deferred GOOSE-hit RNG in voice-structure order, including reject and
  pre-second-IRQ preemption cases;
- PAL period-below-123 effective address-rate clamp in the GOOSE renderer;
- cold and persistent `0x56E6` scratch bytes;
- exact rational CIAB accumulation (511 IRQs in 125 browser VBLs from phase 0);
- two BIGEXPL RNG advances even with four blocked voices;
- the player four-layer periods and the principal TOWN gameplay hooks.

## Still open

- Remaining special/player-transition effects outside the TOWN hooks listed
  above still need their exact call-site map; the six-note extra-life chime at
  `0x5600` is known but not yet connected to the browser's score threshold.
  It uses periods 424/336/266/212/168/133 at offsets 0/5/10/15/20/25 VBL,
  priority 120 and a stereo selector derived from the signed low score word;
  the threshold itself belongs to the following live-player resume, not to
  `awardScore()`.
- Sounds belonging only to later levels, apart from the transcribed DESERT
  BLACKJET and EGGS routines, remain outside the current slice.
- `AMHITUNE.MOD` is decoded and included in the effect-census tests, but no
  runtime scene currently starts it or switches to it. Its native
  high-score/post-game call site remains to be connected.
- GOOSE hit renders each IRQ rewrite as an atomic 24-byte scratch snapshot;
  exact in-place DMA/CPU overlap needs the original beam and Paula pointer
  phase.
- GOOSE periods below 123 use the correct PAL average address-rate ceiling,
  but exact repeated-byte cadence remains dependent on unmeasured beam/DMA
  slot phase.

Collision-driven TOWN effects now inherit the resident N+1 boundary: the
producing sweep is silent and the hit, pickup or death sound is submitted only
when the saved event is dispatched on the object's next resume. Integrated
tests cover TOKEN pickup, MINE core, cannon/HOMING contact and both GOOSE hit
and death paths.

SWIV's tracker music is title-screen music; the author states that it was
removed when gameplay data was loaded and that many in-game effects used
software synthesis. See the
[Ronald Pieket Weeserik interview](https://codetapper.com/amiga/interviews/ronald-pieket-weeserik/).
Accordingly, silence under the TOWN effects is the original music policy,
not a missing level-one module.
