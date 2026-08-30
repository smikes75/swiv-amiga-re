# Codex handoff — TOWN graphics and animation batch

This file marks the changes implemented by Codex on 2026-08-29/30. The
corresponding Git commit uses the `codex:` prefix so another agent can find
the complete batch with `git log --grep='^codex:'`.

## Implemented

- Fast-forwarded the local baseline through the three existing commits ending
  at `3402838` (GAPS, GOOSE and TOKEN).
- Replaced the visible static TOWN background with indexed `.LIN`/`.PAM`
  rendering and the exact Copper palette for every scanline.
- Added exact RGB12 fade helpers, indexed chained-frame decoding and clipping.
- Added the tested D1 foundation for the native BOB queue: unsigned depth
  keys, stable enqueue ordering, shadow projection, cookie-copy and
  clear-to-index-0 operations. This foundation is not yet the visible dynamic
  object path.
- Corrected ROTOBASE startup/direction/period, concurrent POPUP timing and
  closing `KILL`, the two-tick PLOP backend sequence, cannon-local animation,
  post-movement acceleration and the five-projectile limit.
- Corrected Python and browser animation scanners so a `BSR.W` displacement is
  not decoded as the first animation command.
- Extracted and verified the native 7-row HUD font and 352x8 fifth-bitplane
  mask. Runtime HUD content now uses four initial lives, the independent
  `+102` TOKEN counter, weapon display, score x10 and native left/right text
  anchors. Canvas glyphs and final COLOR16-31 composition remain open.

## Deliberately still open

- Dynamic objects still use the old Canvas passes. Do not patch shadows or the
  MILL rotor independently; switch them together through the indexed global
  BOB queue described in `TOWN-PARITY.md`.
- Complete the render metadata/provenance for effects, explosions, the fourth
  GOOSE child and the object-flag `0xA0` prepass before the runtime switch.
- Player bullets, cannon shells and PLOP tick 1 are hardware sprites sharing
  COLOR17-31. They need a global four-bank allocator; HOMING is a normal BOB
  and must use Copper COLOR00-15.
- A non-zero black fade suppresses hardware-sprite enqueue; white fade does
  not alter hardware-sprite colours. The current Canvas placement is marked as
  an approximation until the allocator is implemented.
- `AMPROG.OBJ` never writes COLOR20/24/28. Their inherited reset values require
  one measurement from a running original; `0x000` may only be an explicit
  cold-boot policy meanwhile.
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

At handoff these report 43/43 data checks, `UI OK`, matching HUD contracts,
no animation-documentation diff and no whitespace errors.

