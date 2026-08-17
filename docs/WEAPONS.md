# Weapons and projectiles (read from code, not guessed)

Phase-2 findings. Addresses refer to `AMPROG.OBJ`.

## Projectile object

A shot is a regular object (coroutine). Confirmed fields:

| offset | meaning |
|---|---|
| +332 / +336 | **velocity x / y** (added per tick) |
| +358 | angle (inherited from parent via +308) |
| +340 | per-tick flag (=1 → movement applied) |

## The 8-direction velocity table (`0x8a80`)

```
(-7, 0) (-5,-5) (0,-7) (5,-5) (7, 0) (5, 5) (0, 7) (-5, 5)
```

Straight shots fly at **7 px per 50 Hz tick**, diagonals at (5,5)
(≈7.07 — the classic integer approximation). The projectile behaviour
(`0x89ee`) reads the PARENT's angle (`+308 → +358`), quantizes it
`(angle+16) & 0xE0`, indexes this table for velocity and calls
`0xa27c` with base `0x1200` to pick the direction sprite — i.e.
**sprite frame = base + per-object direction table**, exactly as the
aiming helpers in ENGINE.md describe.

## Known weapon graphics in code

| address | graphic word | meaning |
|---|---|---|
| `0xa9ae` | `0x7001` = BULLET#56 | the tall bolt (player-shot sprite) |
| `0x8acc` | `0x1001` + dir·512 = BULLET#8–23 | 16-direction dart set |
| `0x9640` | `0x3001` = BULLET#24 | second 16-direction set base |
| `0x7fa2` | `0x0601` = BULLET#3 | spark |
| `0x4cb8` | `0x0401` = BULLET#2 | round ball |

## A composite enemy pattern, read end-to-end

At `0xa976`: a spawner waits until on screen, then repeatedly
(period 100 frames, 16 rounds) creates a child; the child at `0xaa9c`
builds a **ring of 6 sub-objects, each offset +42 angle units**
(6 × 42 ≈ 256 = a full circle) — the "orb that releases darts in a
ring". Behaviour scripts also carry **inline animation scripts**
(graphic-word sequences embedded right in the code, passed to the
sequencer `0x6c88`) — which is why the standalone scanner found only
part of them.

## Still to transcribe in phase 2

- the player weapon coroutine incl. upgrade levels and fire cadence
- the second/third direction tables (16-dir sets) word-for-word
- the hardware-sprite palette (COLOR17+) from the copper list


## Oprava (M1, 2026-08-18)

Drivejsi domnenka "0x7001 = BULLET#56 hracuv bolt (0xa9ae)" byla
mylna: `0xa9ae` je smyckovy spawner mapoveho objektu, ktery kazdych
100 tiku 16× pousti strelu dolu (vy=+6). Hracova zbran je dart system
`0x8aa0` — viz docs/BEHAVIORS.md, sekce "Zbran hrace".

Tabulka `0x8a80` (±7/±5 px/t) patri VYHRADNE jeep dartum (smer veze);
vrtulnikovy bolt leti 9 px/t z rozptylove tabulky `0x8b86`.
Nepratelske strely jsou kanonove granaty (akcelerace 0.5→10.5 px/t)
a navadene HOMING strely (3 px/t) — nikoli darty.
