# DESERT parity audit

Measured from `DESERT.PAM` and `AMPROG.OBJ` on 2026-09-02. This file tracks
the second native map (internal level index 1), not SCIFI (index 5).
Updated after integration on 2026-09-07: all 274 DESERT roots have routes;
the detailed fixtures below cover the earlier AIRMINE/BLACKJET/EGGS slice.

## Map and transition contract

- level-table record at `0x3852`: `005B 00C6 0060`
- 105 dictionary graphics, 965 tiles, 274 object roots, 22 palette
  checkpoints, 5,872 px net height and 96 px opening lead
- fixed scroll `$4000` = 0.25 px/VBL = 12.5 px/s at PAL 50 Hz
- the third table word `$0060` is a map-join/rebase offset, not speed
- the native map builder chains DESERT directly into GRASS; there is no
  `LEVEL COMPLETE` pause or reset of player/world state

The browser's direct level picker starts at local row 5,680 plus the height
offset of the remaining chained maps. A TOWN cold-start
rule formerly marked the first eleven DESERT objects as already missed:
eight MEDTANK, one GOOSE boss and two PROXMINE. Direct starts after TOWN now
arm this opening preload window, matching the state those objects would have
after a continuous TOWN → DESERT map join.

## Initial audited slice (2026-09-02)

Before DESERT work, 99/274 roots used ten already transcribed shared routes.
Adding all 48 `AIRMINE#0 → 0x75A8` roots and all seven
`BLACKJET#0 → 0x7A98` roots, then all three compound
`EGGS#12 → 0xA8E4` roots and all four `EGGS#2 → 0x8478` capsules, raises
exact coverage to **161/274 (58.8%)**, across 14 of 35 unique gfx/coroutine
routes. Each BLACKJET root expands to
5–10 actors according to difficulty, so the seven roots create at least 35
real enemies. Every EGGS root additionally owns three independently active
gun pods. The remaining 113 roots stay fail-closed: their real
sprite/known animation may be displayed, but no invented shooting or
movement is added. This was the initial slice: the remaining routes were
subsequently transcribed on 2026-09-03 through 06, see BEHAVIORS. The merged
engine uses the detailed local `eggs2`/`eggs12`/`blackjet` routines together
with the later full-game implementation and the measured collision snapshots.

Shared routes already exact in DESERT are FODDERA, MEDTANK, PROXMINE,
YELLOW, ROTOBASE, MINE, GOOSE#0, POPUP, BIRD and MILL. The four GOOSE#0
records at map-y 147, 1,457, 3,466 and 5,162 deliberately reuse the same
`0xC78A` assembly/death/token/audio implementation as TOWN.

## First DESERT-specific sequence

The opening block is:

| map-y | object | route | current state |
|---:|---|---:|---|
| 515 | BLACKJET#0 | `0x7A98` | **transcribed and tested** |
| 533 | EGGS#12 | `0xA8E4` | **transcribed and tested** |
| 628 | EGGS#2 | `0x8478` | **transcribed and tested** |
| 654 | TILT#0 | `0x7DE8` | transcribed; fixed-point steering and cannon inheritance |
| 745 | AIRMINE#0 | `0x75A8` | **transcribed and tested** |
| 766 | DESTRAIN#3 | `0xA1B0` | transcribed; typed entrance and fire |

AIRMINE, BLACKJET, EGGS#12 and EGGS#2 are documented in
[BEHAVIORS](BEHAVIORS.md). BLACKJET
now has its native 5–10 member layout, guarded activation, fixed-point
acceleration, BOB/shadow/death contract and priority-70 procedural sound.
EGGS#12 now overlays its baked EGGS#8 wreck with the root and three staged
gun pods, fires the native 37-projectile normal-scroll pattern and reproduces
the custom root/part orphan deaths and both sound routines. EGGS#2 keeps its
pre-arm class20 phase, opens over five ten-field frames, rises through 64
fixed-point fields and launches as a 15-HP class22 flyer; lethal damage emits
the native 16-shell ring before its standard explosion. The next
chronological route was `TILT#0 → 0x7DE8` at map-y 654, now integrated.
FISH (17 triggers → 102 actors), SKYEYEB (14 → 84) and GOOSE#7 (7 → 42)
are also implemented. Their complete native-frame parity remains to be measured.

## Major later set pieces

- `INST1` around map-y 3,051–3,110: HP90/2,500-point core plus side parts,
  spawned tanks, exhaust and a custom destruction sequence
- `JEEPHELI#31 → 0xACB6` at map-y 4,524 is a Jeep-to-boat SWAP marker, not
  an enemy; HELI is unchanged
- port half: FISH from 4,620, six-member GOOSE#7 formations from 4,666 and
  RIGS from 4,890
- DESERT completion must retain players, lives, score, weapons, tokens, RNG,
  difficulty, active tasks/projectiles and active-cost accounting into GRASS

Palette fitting is intentionally separate from behaviour coverage. Raw
DESERT capture at native fire+310 s was correlated unambiguously to browser
scroll/top row 5,426 (93.44% terrain match). Its raw checkpoint is
`000 555 687 7BA 987 888 BCB B30 FE8 FFF A85 974 864 664 443 332`.
PAM supplies the register values. The renderer uses linear RGB12; the single
vAmiga gamma LUT is applied only by the comparator. The earlier fitted
object-bank and per-level terrain overrides were measurement artifacts.

The CPU-driven COLOR07 red pulse is global, not TOWN-only. Level init enables
it; all four `_AIRPORT#14 → 0x7970` roots disable it synchronously at
map-reader prefetch, and the first of 17 `FISH#0 → 0xB1A8` roots enables it
again. These prefetch side effects and the AIRPORT/FISH actors are transcribed.

After applying the measured capture curve once to all colors in the
comparison, `tools/compare.py desert` reports **96.1% whole / 96.1%
terrain / 90.8% HUD / 94.1% HELI**, with a one-way whole ratchet of 95.5%.
Direct EGGS pixels additionally prove capture nibble 2 maps to zero:
raw `COLOR15=$332` is observed as RGB `(28,28,0)`.
The default fast compare still runs only TOWN; DESERT is explicit because a
fresh native baseline must emulate 310 seconds.
