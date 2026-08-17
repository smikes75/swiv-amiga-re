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

**Measured trajectory** (frame-by-frame tracking of the original
footage, 25 fps, ~5 s of descent): the wave descends **straight down
at ~0.7 px/tick screen-space with no horizontal weaving at all** —
x stays constant for the whole pass. Members trail ~9 px apart, which
matches the 10-frame member stagger from `0x8008`. Column x is random
per wave, matching `0x813a` (x = 32 + rand·255). Code and footage
confirm each other; the open item is only the engine's fixed-point
velocity scale (`+348 = 0x800` ↔ 0.7 px/t implies the integrator
scales by ~×23, not yet located).

## Player systems (read earlier, summarized)

- weapon tiers `0x70c0`: (power 2, cadence 11), (3,10), (4,10),
  (5,8); tier = weapon counter / 5
- extra life at 10,000 then every 30,000 (`0x7116`)
- lives stored as −4×count in the player struct `+68`; score `+76`,
  hi-score `+80`
- projectiles: 8-direction velocity table `0x8a80` — straight ±7,
  diagonals (±5,±5) px/tick; sprite = base + per-object direction
  table

## M1: TOWN start set — kompletni transkripce (2026-08-18)

### Uhlovy system (kotva vseho)
- uhel 0..255: **0 = vychod, 64 = jih (dolu), 128 = zapad, 192 = sever**
  — overeno MEDTANK typ 2 (spawn x=−32, uhel 0, jede doprava, `0x9f4c`)
- `0x6a6a` sin tabulka, jednotka 256; `0x65f2`: rychlost px/tick =
  `+356`/256, vektor → `+332/+336`
- `0x65be(x, y, max)` = otoc `+358` k cili, max jednotek za volani
  (0 = snap); `0x6610` = atan2
- 16smerovy snimek spritu = `(uhel+8)>>4` (`0xa290`), frame 0 = E

### Nepratelske strely — dva typy
1. **Kanonovy granat** (`0x95fe/0x9602`, sprite BULLET#24+smer,
   spin anim): okamzity krok 16 px z hlavne, start 0.5 px/t,
   **+0.5 px/t kazdych 5 tiku, strop 10.5 px/t**; globalni budget
   poctu granatu `fp@(206)`. Vstupy: `0x95ca` = v aktualnim uhlu
   `+358`; `0x95d2` = snap na hrace + PLOP zablesk; `0x95ec` =
   nemireny, konstantnich 5 px/t.
2. **Navadena strela** (`0x8530/0x8566`, sprite HOMING#smer — soubor
   HOMING.LIN ma presne 16 snimku): 3 px/t (+356=768), kazdych
   8 tiku otocka k hraci max 14 jednotek (~20°), **2×(5+hraci)
   korekci** (1P: 12), pak rovne. Muzzle flash PLOP#0 (`0x85f0`).

### FODDERA vlna (dispatch 0x0404 → 0x8048)
- leader `0x813a`: **x = 32+rand&255** (mapove x se ignoruje),
  vx = rand ±1 px/t, `+348=0x800` = **1.0 px/t dolu** (zmereno
  z videa: 52 px/s @ 50 Hz ⇒ jednotka +344/+348 je 1/2048 px/t)
- 4 klony (5 pri 2P) po **10 ticich** ⇒ rozestup 10 px (zmereno 9)
- okraje `0x8100`: x<32 → vx=+1, x>288 → vx=−1
- clenove strili **mirene kanonove granaty** (`0x95d2` @ `0x812c`)
  na osobni citac (dekrementovany scrollem — kadence orientacni)
- anim: heli rotor 2,3,2,4,2,5,2,6; jet 0,1 (dle typ)

### POPUP (0xa6ae)
cekej 64+rand&63 → otevirej snimky 1–7 → (hittable, +504=32) →
pauza 50 → salva ×(hraci/2+1): snimek 8, `0x8530(±6 stridave, 20,
64)` = homing **dolu**, 5 tiku, snimek 7, 20 tiku → pauza 50 →
zavri 6..1 → konec (inertni)

### YELLOW vojak (0x86bc)
kolona 7 (klony dy=−8), spawn x = rand&63 + **(hrac vlevo ? 256 : 0)**
= protistrana; beh uhlem 64, 2 px/t (+356=512); kazdych 15 tiku:
je-li hrac niz (py−24 > y): otocka k (px, py−16) max 12, rychlost =
manhattan/128 px/t (strop 8); jinak reset primo dolu. Anim 0–4.

### MEDTANK (0x9eca)
typ→najezd: 1: x=352 uhel 128 (zprava); 2: x=−32 uhel 0 (zleva);
3: uhel 64 (dolu); 4: uhel 192 (nahoru, ceka na 0x9ac8); jinak stoji.
Rychlost **0.5 px/t** (+356=128); cyklus 300 tiku jed / 100 stuj, 3×,
pak parkuje. Korba = snimek (uhel>>6): 0=E,1=S,2=W,3=N.
**Vez** = dite `0x9faa` (snimek 4+16smer, sleduje korbu): kazdych
(12−hraci)·16 = 176 tiku (1P): krok k hraci max 16 jednotek,
`0x95ca` vystrel, krok zpet ke korbe.

### ROTOBASE (0x994e)
anim spin 4..11 (smer stridave per instance, `notw fp@(138)`);
smycka: nahodny uhel, cekej 200+rand&127, **4× granat po 90°**
(`0x99b2`: fire, +64, fire, +64, fire, +64, fire).

### Zbran hrace (0x8aa0 + tabulky 0x8b86/0x8dd6)
- vrtulnik i jeep = stejny dart system; vrtulnik ma smer zamceny
  nahoru (dir 6), jeep otaci vezi (`0x93b2`, vychozi uhel 192)
- **9 px/t** (zmereno: rozestup salv 97 px = 9 px/t × kadence 11 ✓)
- pocet strel = sila; start **1**; tabulka 0x70c0 (2,11)(3,10)(4,10)
  (5,8) plati pro powerupy; kadence floor 10 (`0x728a`)
- ofsety (dir 6): liche sily stred (0,−8) + pary (−4,0)(4,0)(−8,8)
  (8,8); sude pary (−2,−4)(2,−4)(−6,4)(6,4); fan varianta (priznak
  +104) misto ofsetu rozklada vektory (0,−9)(±1,−8)(±2,−7)
- max sila (>5): 8 strel do vsech smeru z tabulky `0x8dd6`
  (BULLET#8–15)
- sprite boltu BULLET#14 (nahoru): jehla barvy 1–2, kulicka barva 3
  strida zlutou/cervenou po salvach (z videa)

### Paleta spritu
Barvy 13–15 jsou copper registry — **globalni pro celou obrazovku**
(meni se fade skriptem mezi sekcemi), objekt si barvy nenese s sebou.
Kreslime aktualni paletou okna; presna casova osa fadu = otevreny ukol.

### Triggery chovani
Objekty uvnitr uvodniho okna se NEaktivuji; korutiny startuji az kdyz
radek mapy vjede shora do obrazu (prvni vlna ~2 s po startu — video
22.35 st06→st08).
