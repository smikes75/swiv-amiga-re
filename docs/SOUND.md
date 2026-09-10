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

## TOWN effects implemented locally

| event | native path | priority | implemented result |
|---|---|---:|---|
| one player volley | `0x8AA0 -> 0x4F3E` | 20 | 16-byte waveform, volume 32..1, period 1000 with `p += p>>4`; once even if the 30-slot projectile pool is full |
| non-lethal default hit | `0xA352 -> 0x5070` | 20 | 16-byte waveform, volume 64..4 by 4, period 200 with `p += p>>2` |
| POPUP/PROXMINE/FLAME opening | `0x5138` | 80 | two independent swept voices `(base=2500,hold=50)` and `(2227,90)` |
| each FLAME puff | `0xABD2 -> 0x50D0` | 40 | persistent-noise rise at period 500, then decay at period 1000; native pan input is zero |
| HOMING launch | `0x8566 -> 0x528A` | 80 | 64 fresh-noise states, period 320..257, volume 64..1 |
| cannon launch | `0x9606 -> 0x53BE` | 50 | 48 noise states, raw volume 96..2, changing sample length and signed period recurrence |
| standard death/explosion | `0x894A -> 0x4C58` | 50 | two `BIGEXPL.SND` voices, each with its own `period=592+(RNG&31)` |
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

## Effects outside TOWN

Ten further effects are transcribed from the same engine. All of them reach
`0x4C0C` (or hard-code both selectors) and run as ordinary voice coroutines.

| event | native path | priority | implemented result |
|---|---|---:|---|
| big death (`+376`) | `0x8880`, `0x88EC -> 0x4C3C` | 60 | two `BIGEXPL.SND` layers at period 768 and `769 + (0x883C & 7)`, both forced through the right selector; exactly one PRNG advance, taken between the two requests |
| XEVIOUS bomb start | `0x7F9E -> 0x4CF8 -> 0x4D08` | 30 | 48 triangle states, volume 48..1, period `250 + 3i + ((phase & 3) << 5)` with the same `BTST #2 / NOT.W` mask as the shield tone |
| PLAT turret hatch | `0xA530 -> 0x4D6A -> 0x4D7A` | 40 | 16 triangle states at fixed volume 48, period 800 down to 500 by 20 (`BGE`, so 500 still sounds) |
| installation hit | `0xB8CA -> 0x4E2E -> 0x4E5E` | 40 | the GOOSE-hit callback with `D2 = 400`: 64 fresh-noise states, volume 64..1, `p += p>>5`; forced left then right selector |
| BLACKJET arrival | `0x7AD8 -> 0x52D8 -> 0x52E8` | 70 | 32 rising noise states (volume 0..62, period 300) then 171 falling ones (period `300 + 2j`, volume `(512-3j) >> 3`), all two IRQ long |
| geyser eruption | `0xAFC4 -> 0x5350 -> 0x536E` | 200 + 60 + 60 | three voices; 127 states of the 128-byte sine from `0x6A82`, four IRQ each, volume 127..1, period `127 + (0x883C & 127)` per state |
| egg shot / walker pods | `0xA9AA`, `0xBB80 -> 0x5436 -> 0x5456` | 100 x2 | 48 pulse states, volume 48..1, period `D2 + (-1)^i * 20` with `D2 += D2>>5`; second layer delayed 8 IRQ by `0x544E` |
| factory / INST2 beam | `0xB8B8`, `0xBA4E -> 0x541E -> 0x5456` | 100 x2 | the same callback with `D1 = 50`, `D2 = 500`, which the `0x547E` test lengthens to 126 states |
| `_CORN` launch | `0x8244 -> 0x54AC -> 0x54C8` | 10000 x2 | two hard-panned voices, glide from 10000 (11000) down under 1500 by `p -= p>>8`, then 32 passes of 1500 <-> 1600 with volume 96 down to 3 in steps of 3 |
| XEVIOUS bolt ping | `0x7968 -> 0x55B0 -> 0x55BC` | 20 | one-word wave `0x7F81` at volume 64, periods 300, 500 and 700 for two IRQ each |
| extra life | `0x7128 -> 0x5600 -> 0x5618` | 120 | the TOKEN note generator `0x5672` driven by the six-entry table at `0x5606`: periods 424, 336, 266, 212, 168 and 133, five VBL apart |

`0x5600` and `0x5614` differ only in the note table they hand to the shared
tail at `0x5618`, so the extra-life chime and the TOKEN chime use one
priority-100 task, one selector capture and one note callback. The extra-life
pan comes from `D0` at `0x710C`, which is the signed low word of the score
long the threshold was just compared against.

The geyser is the only effect that reads the global PRNG once per state.
`sfxAdvanceGeyser` keeps those 127 reads on their native IRQs; the rendered
buffer draws its periods from a fork taken at the first state, because
WebAudio needs the whole buffer before the first sample. See docs/GAPS.md.

The `+376` big-death callback `0x8876` (and the eight-tail variant `0x88EC`)
uses `0x4C3C`, not the standard `0x4C58` of `0x894A`. The two differ in
priority, in period and in PRNG cost: `0x4C58` draws twice, `0x4C3C` once.
Until 2026-09-07 the browser played `0x4C58` for both.

`0x4F9E` and `0x523A` are complete voice routines with no reference anywhere
in `AMPROG.OBJ` and are deliberately not wired up. `0x51D4` (four noise
voices at periods 400, 480, 413 and 441, volume `counter >> 7`, endless loop
through the left selector) is called from `0xF94`, which is inside the
conditional post-game `CONGRAT2.RAW` branch `0xF42..0x1042` — not the loader,
as this file first stated. It waits for `fp@(12352)` and belongs to the
post-game flow that has no runtime scene yet (docs/GAPS.md section 8).

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

- The extra-life chime is connected, but from inside `awardScore()`. Natively
  the threshold is evaluated by the following live-player resume at `0x710C`,
  so its ordering against other tasks created in the same VBL is unverified.
- Nothing in the effect table is unhooked any more; what remains open is the
  exact CIA/beam phase behind the sub-millisecond onset differences already
  listed above. `0x4DC6` was the last routine still without a runtime caller,
  and it turned out to belong to the jeep: `0x920A` fires it at the start of
  the jump with `D0 = x`, so it pans with the vehicle.
- `AMHITUNE.MOD` is connected: the post-game statistics screen `0x0DA2`
  selects it through the engine's own `0x5EA` module switch when the score
  reached the table (`0xF0C -> 0x3040` sets `fp@(10798) = 2`), and otherwise
  returns to `AMTITUNE`.
- GOOSE hit renders each IRQ rewrite as an atomic 24-byte scratch snapshot;
  exact in-place DMA/CPU overlap needs the original beam and Paula pointer
  phase.
- GOOSE periods below 123 use the correct PAL average address-rate ceiling,
  but exact repeated-byte cadence remains dependent on unmeasured beam/DMA
  slot phase. **The boss-death synth `0x553A` is the only effect in the whole
  game that goes there**: `base - 4*counter` runs down to 72, and 26 of its
  128 states (both layers) sit between 72 and 122. The browser plays those
  states as a clean tone up to 927 cents below the requested pitch, because
  the renderer caps the address-advance rate; Paula instead re-outputs the
  last fetched word, which changes the timbre, not just the pitch. Every
  other transcribed effect stays above 123, so this approximation is
  confined to that one sound. Settling it needs a capture of the GOOSE boss
  death from the original - see docs/GAPS.md.
- `0x5580` writes AUDVOL once per state pair; `0x5594` negates the counter
  afterwards and the second half touches only AUDPER. Until 2026-09-08 the
  browser passed the negated counter through `sfxPaulaVolume`, which returns
  64 for every negative input, so every second state played at full volume
  and the effect never faded out.

Collision-driven TOWN effects now inherit the resident N+1 boundary: the
producing sweep is silent and the hit, pickup or death sound is submitted only
when the saved event is dispatched on the object's next resume. Integrated
tests cover TOKEN pickup, MINE core, cannon/HOMING contact and both GOOSE hit
and death paths.

`AMHITUNE.MOD` is connected as of 2026-09-07. The module is chosen by the
native mechanism at `0x5EA`: `fp@(10798)` holds the requested module (1 =
`AMTITUNE`, 2 = `AMHITUNE`) and the loader task swaps when it differs from
the loaded one. `0xF2A` computes `1 - fp@(3618)`, and `fp@(3618)` is set by
`0xF0C` -> `0x3040` when a player's score reaches the high-score table. So
the post-game statistics screen `0x0DA2` plays `AMHITUNE` after a qualifying
game and `AMTITUNE` otherwise. `0x51D4` still has no scene: it belongs to the
`CONGRAT2` branch, which needs the game to be completable.

SWIV's tracker music is title-screen music; the author states that it was
removed when gameplay data was loaded and that many in-game effects used
software synthesis. See the
[Ronald Pieket Weeserik interview](https://codetapper.com/amiga/interviews/ronald-pieket-weeserik/).
Accordingly, silence under the TOWN effects is the original music policy,
not a missing level-one module.
