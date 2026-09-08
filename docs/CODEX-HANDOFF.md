# Codex handoff — integrated game and display controls

Updated 2026-09-07. Local snapshot `5802d80` preserves all uncommitted
DESERT work from the earlier checkout. Integration includes the 45 remote
commits through `0eb84db` (2026-09-06); neither source was discarded wholesale.

## Current result

### Local sound pass (2026-09-07, after motion work)

Selectively integrated XEVIOUS bomb/armour ping, PLAT hatch, installation
hit, factory/INST2 beam and walker pod audio from Claude's 766facb. Checked
0x4cf8..0x4e46, 0x541e..0x54ac and 0x55b0..0x564c against the local binary.
Preserved local BLACKJET, EGGS shot/root sound, guard cleanup and FIFO.
tools/soundtest.py adds independent full period/volume checks, IRQ/RNG/
preemption/hook tests and actual OfflineAudioContext stereo PCM checks.
No gain/filter retuning or claim of recording-level Amiga parity.
Geyser, CORN, extra life, general big-death integration and post-game music
remain open; details and exact scope are in docs/SOUND.md.

### Local fractional-motion update (2026-09-07)

Reviewed origin/main through 110bdba. Since the previous integration Claude
added fractional scroll, transparent HUD and optional background blending,
fractional BOB/HW projectile interpolation, zoom/focus refinements, eleven
sound effects, WASM input/audio work and post-game statistics/AMHITUNE.
Only presentation changes are selectively integrated here; this is not a
merge of the new sound/post-game branches. The previously stale online
preview was updated by the explicit publication below.

### Published Codex preview (2026-09-07)

User requested online Windows testing and another TOKEN pickup audio pass.
Commit `003f697af18a33b3a3c2f05896890d91cc897641` on origin/main updates ONLY
`game-codex.html`, preserving Claude's `game.html` and all other remote files.
It was prepared in detached worktree `/tmp/swiv-publish-LVSZOa` on top of
`110bdba`; the active local branch and its uncommitted work are unchanged.
Published HTML is byte-identical to the tested local game.html (SHA-256
`59c3604356bbd61da86535f0c12f58c3959ed9a8d9c0ab22106b69221f12c498`).
URL: https://smikes75.github.io/swiv-amiga-re/game-codex.html?v=003f697
No ADF, ROM, extracted assets or temporary diagnostic captures were uploaded.

Boss death now keeps positive volume 32..1 for both halves of each period
pair, as AUDVOL is not rewritten at the native counter's negation. TOKEN
uses a cached 4x/windowed-sinc resampler to reduce aliases, leaving the
original notes, envelopes, scratch state and task timing unchanged. This is
a targeted resampling improvement, not confirmed recorded-original parity.
Sound tests include independent boss/TOKEN state oracles, alias suppression
at 44.1/48/96 kHz and actual TOKEN OfflineAudioContext output at 44.1/48 kHz.
UI, all-seven-zone integration and display/120-Hz simulation tests pass.

Local game.html retains the Codex display controls and DESERT simulation,
audio and COLOR07 writers. BOB and scroll interpolation now uses fractional
endpoints. Hardware projectiles use stable task/slot keys PLUS source
identity, with explicit worldSpace support for local DESERT shots.
Snapshots are retained for every simulated tick, including catch-up frames;
mode changes discard stale history and large map jumps do not interpolate.
HUD is a transparent overlay. Optional Hladké pozadí vertically blends
neighboring terrain positions (softer appearance); sharp mode keeps the
4x backing grid and can still repeat physical pixels at small CSS zoom.
Actual Windows/120 Hz hardware still requires user testing.

The former integer-endpoint pixel test is no longer a motion oracle:
fractional endpoints intentionally differ inside sprite rectangles.
tools/smoothtest.py now checks structural pixels outside sprite bounds,
with the local current-VBL palette adjustment retained. Strict numeric and
render checks align the classic viewport to the same rounded coordinate
when SCIFI holds indefinitely at a fractional scroll value. Numeric and
render checks in tools/motiontest.py independently cover fractional BOBs,
12 distinct blended terrain images, world-space HW interpolation, recycled
slots, transparent HUD and adjacent-tick capture after catch-up.
Verified: motiontest, displaytest (DPR 1/1.25/1.5/2 and simulated 120 Hz),
combined TOWN/DESERT uitest, seven-zone integrationtest, structural smooth
checks in all seven zones at tick 2400 (0 pixels outside masks), and the
unchanged classic TOWN comparison floors (99.9/99.0/98.3/99.9 percent).

The original integrated baseline and its checks are recorded below.

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
