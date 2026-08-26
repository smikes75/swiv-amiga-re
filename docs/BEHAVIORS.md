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
- third position/depth coordinate `+328 = 32`; hit points are the
  `a2c6` d3 value (1 here), stored in `+360`
- **powerup carrier selection**: `random & 3 + player count ≥ 5` →
  the member's `+276` becomes a token counter (32..95) — with two
  players, carriers are more frequent
- edge handling: `x < 32` → x-velocity `+0x800` (fixed), `x > 288` →
  `−0x800`; when `+336 ≥ 3` the y-velocity accumulator `+348` is
  cleared

The two entry points must not be mixed: `0x8008` is a hangar stream
whose members start ten ticks apart. Map objects dispatch to `0x8048`,
which clones a complete formation immediately and gives its members
world-y offsets of −4 px. Every member then waits independently in
`a2c6` for its own `sy >= −48` threshold. The generic integrator at
`0x62d2` adds acceleration to velocity and then velocity to position;
therefore `+348 = 0x800` means `1/32 px/t²`, not a constant speed.

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
  `vx = sign16(rand>>16)/32768`, `vy=0`; `+348=0x800` je zrychleni
  **1/32 px/t²**, ktere se vypne pri `vy >= 3 px/t`
- v 1P celkem **4 clenove** (5 pri 2P) s world-y offsety
  `0,-4,-8,-12`; zadny `wait(10)` — kazdy ceka na vlastni `sy>=-48`
- okraje `0x8100`: x<32 → ax += 1/32, x>288 → ax −= 1/32;
  rychlost tedy neskace okamzite na ±1
- clen muze vystrelit **jeden mireny kanonovy granat** (`0x95d2`),
  jen kdyz `rand&3 + pocet_hracu >= 5`; v 1P je to nemozne
- anim period 1: heli rotor 2,3,2,4,2,5,2,6; jet 0,1 (dle typ)
- po aktivaci flag bit 4 kompenzuje camera-scroll (`0x6434`), takze
  screen-y roste jen o vlastni `vy`, nikoli jeste o rychlost mapy

### POPUP (0xa6ae)
cekej 64+rand&63 → otevirej snimky 1–7 → (hittable, +504=32) →
pauza 50 → salva ×(hraci/2+1): snimek 8, `0x8530(±6 stridave, 20,
64)` = homing **dolu**, 5 tiku, snimek 7, 20 tiku → pauza 50 →
zavri 6..1 → konec (inertni)

### YELLOW vojak (0x86bc)
kolona **6** (world-y offsety `0,-8,…,-40`), kazdy clen ceka na
vlastni `sy>=-48` a pak sam losuje x = rand&63 +
**(hrac vlevo ? 256 : 0)** = protistrana. Zacina uhlem 64 a 2 px/t;
ihned a pak kazdych 15 tiku: je-li hrac niz (`py−24 >= y`), otocka
k `(px,py−16)` max 12, rychlost `((2*manhattan)&0x7ff)/256`, jinak
reset primo dolu. Anim period 1: `0,1,0,2,0,3,0,4`.
Stejne jako FODDERA nastavuje bit 4, proto je aktivni pohyb v
screen-space nezavisly na dalsim scrollu mapy.

### BIRD (dispatch 0x0015 → 0x862e)

- `a2a2(32,-4,4,0)` znamena **4 celkove cleny** na
  `(x+32i,y-4i)`, i=0..3; zadna prodleva ani zavislost na TYP
- kazdy sam ceka na `sy>=-48`, ma 2 HP, 55 bodu a cost10; BIRD jako
  vyjimka nevola budget guard `0x8822`
- pri aktivaci jeden RNG: `vy=1+(rand&0x7fff)/65536`, `vx=0`; bit4
  rusi deltu scrollu, takze screen-y roste presne o tuto rychlost
- anim period4: `0,1,2,3,2,1`
- nema casovanou palbu; prvni zasah ubere HP, odskoci o 6 px nahoru a
  vystreli accel cannon uhlem `56+(rand&15)` bez PLOP/budget checku;
  druhy zasah jej znici

### MINE (0x0011 → 0x9b16) a pohyblive jadro (0x9860)

- parent se aktivuje pri `sy>=-16`, je staticky a rotuje `MINE#0..7`
  po 2 ticich (HP10/25 bodu/cost7)
- zasah nebo kontakt pouziva custom callback `0x9b62`: parent se
  jednorazove otevre na `MINE#8` a vytvori prave jedno jadro; callback
  neodecita parent HP jako bezny damage handler
- jadro: `MINE#9,#10` period1, 10 HP, 30 bodu, cost5, `vy=0.5`; ma
  airborne bit4, proto se na obrazovce posouva o 0.5 px/t bez pricteni
  scrollu terenu

### PROXMINE (0x000f → 0xa9e0)

- nahodny aktivacni prah `sy=85+(rand&31)`; 4 HP, 30 bodu, cost10
- otevreni `PROXMINE#0..5`, period6, pak wait100 a proximity test
  kazdych 10 tiku; metriku tvori Manhattan vzdalenost k nejblizsimu
  zivemu hraci
- pri vzdalenosti `<=120` parent bez bodu zmizi a vytvori 6 strepu v
  uhlech `aim+21+42*k`, k=0..5; kazdy leti konstantne 2.5 px/t,
  ma 1 HP/5 bodu/cost5 a pouziva bud sekvenci #6..11 period2, nebo
  #12..15 period3
- zniceni parenta ctyrmi bolty je bez proximity salvy a da 30 bodu

### TRAIN (0x0010 → 0x9b7e)

- aktivace `sy=100`; lokomotiva 10 HP/75 bodu/cost15, `y=mapY-2`
- smer urcuje mapove x: vlevo start `x=-48,vx=+1`, vpravo
  `x=368,vx=-1`; TYP 4/8 je pocet vagonu, tedy 5/9 dilu celkem
- vagony jsou po 48 px za predkem, nahodne `TRAIN#1/#2`, kazdy
  2 HP/50 bodu/cost15; po ztrate parentu zpomaluji `vx*=15/16`
- horizontalni offscreen se zamerne neculluje; souprava konci pri
  `screenY>=272`

### MILL (0x0058 → 0x79d4)

- aktivace `sy=-48`, 10 HP/70 bodu/cost15, vlastni `vy=0.5`
- po dosazeni `sy=24` zapne airborne bit4 a pak kazdych 100 tiku
  vypusti osm accel cannon strel po 32 uholovych jednotkach
- zaklad salvy je 0 nebo16 podle bitu aktualniho PRNG stavu; cela
  osmismerova sada tedy strida osy a mezismery, bez mireni na hrace

### FLAME (0x0013 → 0xab10)

- parent se aktivuje v `sy=128`, ma 3 HP/40 bodu/cost10 a otevira
  #0..4 period6; po ticku24 vytvori linked emitter na `x+12`
- emitter (cost1) loopuje period2 pres presnou 14prvkovou sekvenci
  `12,13,12,14,12,13,14,13,12,13,12,13,14,13`
- po 100 lok. ticich a potom kazdych 100 vypusti unlinked puff;
  ten leti doprava 2.5 px/t, animuje #5..11 period5 a po 35 ticich
  (87.5 px) zanika
- smrt parentu ukonci linked emitter, uz vypustene puffy dojedou

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

### CAMOGUN (0xac12)
- dispatch je `gfx 0x0016` → `0xac12`; mapove TYPy 1/2 rutina necte
  a pri prvni rane `+276` prepise recoil citacem 8, takze obe veze v
  kazde dvojici maji shodne chovani
- `a2c6(CAMOGUN#0, 0x24, -16, 2, 40, 10)`: aktivace 16 px nad
  obrazem, **2 HP**, 40 bodu, active-budget cost 10
- opakuje: cekej 100 tiku → uhel 64 (dolu) → `0x95c2` vystreli
  **nemireny granat konstantnich 5 px/t** bez PLOP a bez kontroly
  budgetu → recoil 8 px behem 8 tiku → znovu cekej 100
- inline animace na `0xac48` je `period(3), CAMOGUN#1, #0, end`;
  stary zaznam od `0xac46` chybne povazoval displacement instrukce
  `bsr.w 0x6c88` za prikaz animace; `0x62d2` tikne animator pred
  cooperative yieldem, takze viditelnych osm recoil framu je
  `#1,#1,#1,#0,#0,#0,#0,#0`
- v obrazkovych souradnicich remaku (opacnych k mapovemu y) recoil
  skoci o 8 px dolu a osm tiku se vraci po 1 px nahoru

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
Objekty uvnitr uvodniho okna se NEaktivuji; korutiny jsou zakladany
pred obrazem a jejich `a2c6` je pusti podle vlastniho marginu. FODDERA
a YELLOW pouzivaji −48, nikoli genericky wrapper −32.

### Dodatky (2. iterace M1)
- **Granat rotuje**: telo strely (`0x96b4`) kazdy tik prohazuje
  graficke slovo mezi 24+smer a 40+smer (+0x2000 = +16 snimku);
  BULLET 24–39 a 40–55 jsou dve faze rotace.
- **Kazda 4. vlna FODDERA se rozptyluje**: `0x806c` — kdyz
  (citac vln fp@(146) & 3)==0, kazdy clen si vola `0x813a` sam
  (vlastni nahodne x). Ostatni vlny drzi spolecne x leadera.
- **Hangar** INST2#2 → `0xb9da` (hp 2000, anim otevreni INST2 3–6):
  po najeti na obrazovku spusti `0x8008` = **proud 16 clenu po
  10 ticich** z vlastniho x (y = horni okraj −32). Na TOWN zadny
  neni (60× FODDERA#2 trigger); hangary jsou na dalsich urovnich.
- Klonovaci utilita `0xa2a2(dx,dy,n,dtyp)`: spawnuje na navratove
  adrese volajiciho; MEZI klony posouva sebe o (dx,dy) a +276 o dtyp.
- `0xa2c6` d2 = margin pro cekani na obrazovku (`0x9ac8`), d3 = HP
  (`+360`), d4 = body (`+362`) a d5 = active-budget cost (`+370`).

### Dodatky (3. iterace M1)
- **Palba clenu vlny** (`0x80c8`): vychozi +276 = −1 (nikdy nestrili).
  Strelcem se clen stava jen kdyz `rand&3 + pocet_hracu >= 5` —
  **v 1P hre tedy clenove vln NIKDY nestrili** (2P: ~25 %). Strelec
  vystreli JEDNOU (0x95d2) po 32+rand&63 ticich; pak citac pretece
  a dalsi rana nikdy neprijde.
- **fp@(-76)** = pocet hernich tiku za snimek (normalne 1) — cte ho
  i kadence hrace (0x7296). NENI to scroll.
- **Rotace veze tanku** (`0xa096` docteno): smycka — krok ±16
  jednotek (22.5°), prekresleni spritu (0xa290), 6 tiku pauza,
  dokud neni zamereno; pocet kroku = (|rozdil|+8)>>4. Vez se tedy
  VIDITELNE otaci na hrace, vystreli az po zamereni, a stejnym
  tempem se vraci ke smeru korby.
- **+336 < 3 → +348 se nemaze** (`0x80f4`): sekundarni sestup 0x800
  prezije jen pri pomalem primarnim vy; rychli padaci ho ztraceji.
