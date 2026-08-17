# Behaviour transcriptions

Facts read from the behaviour coroutines in `AMPROG.OBJ`. Addresses
included so every claim can be re-checked.

## Representation: positions and velocities are 16.16 fixed point

Object position fields `+320` (x) and `+324` (y) are **longs**; the
high word is the pixel coordinate (that is why all drawing/logic code
reads them with word accesses on a big-endian 68000). Velocity longs
live at `+332/+336`; word-sized writes there set whole pixels per
tick. A terrain-checked mover exists at `0x9322`: velocity ×2 is
added, a background-collision probe runs, and the move is undone on
hit (used by ground vehicles).

## FODDERA — the air wave (`0x8008` spawner, `0x8066` member)

The wave generator we previously guessed is real, and works like
this:

- spawner positions itself 32 px **above the screen top** and sets
  type 1
- wave size: `(4 − difficulty) × 4` waves; each **member spawns 10
  frames apart** (`0x5f22` wait)
- an alternative entry (`0x8048`) uses the formation helper
  `0xa2a2` with deltas (dx=0, dy=−4, count=4, dtype=0) — a vertical
  column of **4 units, 5 when two players are active**
  (`fp@(182) ≥ 2`)
- each member (`0x8066`): visual `0xa2c6(FODDERA#2, 34, −48, 1, 12,
  10)`, registers as hittable (`0x8822`), then attaches an **inline
  animation** depending on its state: rotor sequence (frames
  2,3,2,4,2,5,2,6 — the helicopter) or the jet sequence (frames 0,1)
  — one behaviour serves both FODDERA variants
- hit points/flash field `+328 = 32`
- **powerup carrier selection**: `random & 3 + player count ≥ 5` →
  the member's `+276` becomes a token counter (32..95) — with two
  players, carriers are more frequent
- edge handling: `x < 32` → x-velocity `+0x800` (fixed), `x > 288` →
  `−0x800`; when `+336 ≥ 3` the y-velocity accumulator `+348` is
  cleared

Still open: the exact per-tick magnitude of the fixed-point velocity
for airborne units (the ×2 terrain mover is the ground-vehicle path),
the parked-FODDERA (map spawn) coroutine, and the `0x813a` side call.

## Player systems (read earlier, summarized)

- weapon tiers `0x70c0`: (power 2, cadence 11), (3,10), (4,10),
  (5,8); tier = weapon counter / 5
- extra life at 10,000 then every 30,000 (`0x7116`)
- lives stored as −4×count in the player struct `+68`; score `+76`,
  hi-score `+80`
- projectiles: 8-direction velocity table `0x8a80` — straight ±7,
  diagonals (±5,±5) px/tick; sprite = base + per-object direction
  table
