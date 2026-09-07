# Codex handoff — integrated game and display controls

Updated 2026-09-07. Local snapshot `5802d80` preserves all uncommitted
DESERT work from the earlier checkout. Integration includes the 45 remote
commits through `0eb84db` (2026-09-06); neither source was discarded wholesale.

## Current result

- All seven chained zones and 1,497 map-object routes / 73 distinct pairs.
- Native PAM RGB12 colors and the later TOWN collision-position snapshots.
  Emulator gamma is applied only in `tools/compare.py`, once.
- Retained detailed local AIRMINE, BLACKJET, TILT, EGGS#2 and EGGS#12
  implementations, fresh-child FIFO, cannon/PLOP inheritance, explosion
  lifecycle and DESERT sound regressions. BOS guns use the same updated
  EGGS projectile call with a world-space origin.
- Display presets 1×/2×/3×, fit to window and 0.5×–6× slider (0.05× step).
  Default 2×, clamped to available space. Requested zoom is saved locally;
  resizing back restores it. Slider keyboard input does not control HELI.
- Smooth rendering remains optional with 50 Hz logic. Its 4× internal
  resolution is independent of display zoom. The native-pixel test explicitly
  sets `state.smoothRenderScale=1`.
- Direct-start map transitions use a relative `junctionIndex` and absolute
  `levelPhase`; player state is retained. Direct FINAL supplies the SCIFI
  installation hold required for its boss, lights, insects and body to start.

## Verified

- `python3 tools/check.py`: disk/data/dispatch contract.
- `python3 tools/uitest.py`: complete combined TOWN + local DESERT fixtures.
- `python3 tools/displaytest.py`: zoom presets/slider/fit, saved fractional
  size, keyboard focus, viewports 390–1920 CSS pixels, DPI 1/1.25/1.5/2,
  and identical simulation for 600 display frames at simulated 120 Hz.
- `python3 tools/integrationtest.py`: three sampled windows × 1200 ticks
  per zone TOWN–SCIFI, both renderers; FINAL active boss window and death;
  every loaded-chain junction before/at/after its threshold. This is runtime
  smoke coverage, not native-frame parity of all enemies.
- `tools/compare.py`: TOWN start 99.9%, wave 99.0%, death 98.3%, respawn
  99.9%, with original ratchet floors unchanged. The death HUD mask now
  follows the actual inactive-slot text and measures 100%.
- `tools/compare.py desert`: preserved static renderer checkpoint 96.1%,
  floor 95.5%, original tolerance 24/channel. TOWN uses 8/channel.
- Smooth frame oracle exercised on TOWN, DESERT, ICE, SCIFI and active FINAL.
  Previous-position comparison uses current VBL palette and allows changed
  animation/decal appearance; current-position endpoint must match exactly.
- Windows/physical 120 Hz hardware was not available here. DPI and timing
  cases were exercised in Chromium on macOS.

## Next substantial work

1. Align VAHeadless and WASM captures using actual Agnus frame counts,
   not seconds; locate A6 and inspect native task records. The existing
   `DENISE_FRAME_SKIPPING` caveat in GAPS still applies.
2. Establish native gameplay checkpoints for later enemies/bosses. Full
   dispatch coverage must not be described as pixel-perfect game parity.
3. Remaining special sound hooks (including factory/laser and extra life),
   exact inter-task CIAB arbitration, post-game/high-score screens and
   native two-player/JEEP start branches.
4. Native A500 load-dependent scroll and allocation-delayed respawn remain
   documented approximations; no speculative timing model was added.

Existing historical audits describe intermediate states and sometimes old
names. Use README and this handoff for current scope, SOUND for retained
audio contracts, and dated measurement sections for their evidence.
