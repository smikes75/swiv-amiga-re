# Codex handoff — TOWN local working tree

This file marks the state implemented by Codex on 2026-08-29/31. The latest
HUD/audio follow-up is intentionally local and uncommitted. Older committed
batches can still be found with `git log --grep='^codex:'`.

## Implemented

- Fast-forwarded the local baseline through the three existing commits ending
  at `3402838` (GAPS, GOOSE and TOKEN).
- Replaced the visible static TOWN background with indexed `.LIN`/`.PAM`
  rendering and the exact Copper palette for every scanline.
- Added exact RGB12 fade helpers, indexed chained-frame decoding and clipping.
- Switched the visible dynamic object path to the indexed global BOB queue:
  unsigned depth keys, stable enqueue ordering, shadow projection,
  cookie-copy, clear-to-index-0 and the special decal/prepass operations.
- Corrected ROTOBASE startup/direction/period, concurrent POPUP timing and
  closing `KILL`, the two-tick PLOP backend sequence, cannon-local animation,
  post-movement acceleration and the five-projectile limit.
- Corrected Python and browser animation scanners so a `BSR.W` displacement is
  not decoded as the first animation command.
- Extracted and verified the native 7-row HUD font and 352x8 fifth-bitplane
  mask. Runtime HUD content uses four initial lives, the independent `+102`
  TOKEN counter, weapon display, score x10 and native anchors. Set mask bits
  now reproduce the measured opaque COLOR16 result instead of the incorrect
  conventional `16|lower4` composition that made `HELI` and `PRESS FIRE`
  flash yellow/red.
- Added the four-voice Paula/CIAB scheduler, strict native priority/stereo
  allocation, persistent procedural-noise scratch and sound-IRQ PRNG
  perturbation. TOWN hooks cover player fire and hits, opening/flame effects,
  cannon, HOMING, standard explosions, player burst, four-layer `SMART.SND`,
  bound MINE shield activation, TOKEN pickup and GOOSE hit/death; see
  `SOUND.md` for the address-level contract and exclusions.
- Added the resident N+1 collision boundary: sweep-only pending masks,
  current-pulse SMART ordering, deferred player death/hit/pickup callbacks and
  the priority-`0xfffe` player-bolt cleanup. Exact field-transition fixtures
  cover the previously misleading cannon sound, TOKEN and GOOSE.

## Deliberately still open

- The raw original runtime capture is still the final acceptance oracle for
  complex BOB crossings, projected shadows and the hardware-sprite layer.
- Player bullets, cannon shells and PLOP tick 1 use the global hardware-sprite
  allocator and COLOR17-31 banks; HOMING remains a normal COLOR00-15 BOB.
  Black fade suppresses hardware-sprite enqueue and white fade leaves their
  colours unchanged.
- `AMPROG.OBJ` never writes COLOR20/24/28. Their inherited reset values require
  one measurement from a running original; `0x000` remains an explicit
  cold-boot policy for those otherwise undocumented sprite-bank slots. They no
  longer affect HUD text composition.
- Audio still lacks the remaining special/player-transition call-site map,
  including the known extra-life chime at `0x5600`.
- The browser does not yet interleave every priority-100 task continuation as
  a general coroutine scheduler; rare within-VBL RNG/audio arbitration cases
  still need a raw original trace, as documented in `GAPS.md`.
- Deterministic VAHeadless capture works, but the canonical `SWIVFIX.ADF` does
  not boot there yet, so a raw original-frame acceptance baseline is still
  unavailable.

## Verification

Run from the repository root:

```sh
python3 tools/check.py
python3 tools/uitest.py
python3 tools/hudscan.py SWIVFIX.ADF
python3 tools/hudscan.py build/files/001_AMPROG.OBJ
python3 tools/animscan.py | diff -u docs/ANIMS.md -
git diff --check
```

The UI suite also checks the HUD against hostile COLOR17-31 values and covers
the Paula allocator, CIAB timing, procedural timelines, RNG consumption,
SMART sample playback and the principal TOWN pickup/combat sound hooks.
