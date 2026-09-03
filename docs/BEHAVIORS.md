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

### Vstupni margin neni cull margin

`a2c6` d2 urcuje pouze obrazovkovy prah aktivace. Nezapisuje se do `+364`:
alokace objektu tam nezavisle dava vychozi cull margin −64. FLAME parent jej
meni na −8; cannon, HOMING, PLOP a PROXMINE strepy na 0. TOKEN ma `+538`
behem radialniho burstu vypnuty a v aktivni fazi znovu pouziva −64. GOOSE
parent zapina cull jen pri escape a vsechny jeho children jej maji vypnuty.
TRAIN generic cull nepouziva; `screenY >= 272` je primy terminator korutiny,
nikoli callback `0x6480`. Test ale lezi az za navratem z `0x62d2`, takze
prave publikovany field zustane a terminator se provede pri dalsim resume.

Pri obycejnem `0x6480` cullu VBL N provede pohyb, zneplatni task a presto jej
jeste publikuje/renderuje i collision-sweepuje. Pri resume N+1 dobehne bit4
scroll compensation, clear hit flash, orphan, SMART a event callbacky a az
potom se zaznam a cost uklidi. Tento kontrakt plati pro generalizovane
air/hazard/spawn/TOKEN nody stejne jako pro margin-0 pomocne objekty.
Generation invalidace neni predcasny navrat: SMART smrt ani lethalni bit0
nepotlaci ulozeny bit3. Resume zachovava `SMART -> bit0 -> bit3` (pak
`4,1,2,5`) a fyzicky cleanup/cost release se provede pouze jednou.

## FODDERA — the air wave (`0x8008` spawner, `0x8066` member)

The wave generator we previously guessed is real, and works like
this:

- spawner positions itself 32 px **above the screen top** and sets
  type 1
- wave size: `(4 − difficulty) × 4` waves; each **member spawns 10
  frames apart** (`0x5f22` wait)
- an alternative entry (`0x8048`) uses the formation helper
  `0xa2a2` with deltas (dx=0, dy=−4, count=4, dtype=0) — a vertical
  column of **4 units, 5 when dynamic difficulty D≥2**
  (`fp@(182) ≥ 2`; toto pole neni pocet hracu)
- each member (`0x8066`): visual `0xa2c6(FODDERA#2, 34, −48, 1, 12,
  10)`, registers as hittable (`0x8822`), then attaches an **inline
  animation** depending on its state: rotor sequence (frames
  2,3,2,4,2,5,2,6 — the helicopter) or the jet sequence (frames 0,1)
  — one behaviour serves both FODDERA variants
- third position/depth coordinate `+328 = 32`; hit points are the
  `a2c6` d3 value (1 here), stored in `+360`
- **casovac jedine rany / shooter selection** (`0x80c8`–`0x80f0`): az
  po vlastnim `a2c6` se spotrebuje jeden random long. `(low&3)+D >= 5`
  rozhodne strelce; jinak dostane `+276 = −1` a nikdy nevystreli.
  `32+(high&63)` z tehoz cisla urci countdown. `SUB.W` vystreli pri
  podteceni, tedy za 33..96 VBL; nema visibility ani alive gate a pali
  pred vlastnim pohybem. Drivejsi poznamka o "powerup carrieru" byla
  chybna — clenove TOKENy neshazuji
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

- dynamic difficulty `D` v `fp@(182)` neni pocet hracu. Na konci
  scheduler passu se prepocita jako
  `min(10, (((rank1>>8)+(rank2>>8)+((power1+power2)>>2))>>3)
  + max(levelPhase-1,0))`; tasky tedy v aktualnim VBL vidi hodnotu z
  predchoziho VBL. Rank `+110` zivemu hraci roste po 110 za VBL,
  resetuje se po smrti a extra life prida 6000
- weapon tiers `0x70c0`: (power 2, cadence 11), (3,10), (4,10),
  (5,8); tier = `floor(pickup counter +102 / 5)`. `0x70c8` tabulku
  aplikuje jen pri startu/respawnu: silu omezi **dolů** na
  `min(+100, tier cap)` a `+98` vzdy prepise kadenci. Start `0x6fde`
  pred tabulkou nastavi power2/reload12, prvni hratelny stav je tedy
  power2/reload11. Pocet vypalenych boltu je `+100`
  (`0x8ad0`–`0x8b1e`), takze uz prvni salva ma dva
- extra life at 10,000 then every 30,000 (`0x7116`)
- lives stored as −4×count in the player struct `+68`; score `+76`,
  hi-score `+80`. Browser drzi ekvivalentni kladnou zasobu pred aktualnim
  spawnem: `g.lives=4` se zobrazi jako `HELI 3`, posledni aktivni stav
  `g.lives=1` jako `HELI 0`
- HELI start/respawn `0x9046` zkousi masku `JEEPHELI#0` v poradi
  x `160..280` po8, uvnitr y `192..104` po−8 proti terrain control
  plane1; prvni volne misto vyhraje. Je-li vsech 192 mist blokovanych,
  pouzije uz nekontrolovany fallback `(288,192)`
  **Sonda `0x3dd4` kresli masku v testovacim rezimu (zaznam +21 bit 7 →
  varianta `0x416a`) do bufferu `fp@(256)`, tj. do OBRAZOVKY** (bit 6 by
  mirila do stripu `fp@(264)`), a kolizi hlasi pres `fp@(162)` proti vsemu,
  co v ni je — terenu i BOBum posledniho renderu. GOOSE nad (160,192) proto
  respawn zablokuje a hrac vznikne o sloupec/radek dal; boss pak ztraci HP
  jen pri skutecnem doteku. Zmereno baseline t281..t289 (2026-09-03):
  po smrti pod bossem hrac 4 s neni na (160,192), boss prezije do timeoutu.
  Prepis: `respawnBobField` sklada aktualni BOBy bez vlastniho hrace.
- pohybova smycka clampuje starou pozici na x `4..316`, y `4..252`
  **pred** aplikaci vstupu; kardinalni krok muze proto v prave publikovanem
  framu dosahnout x `1..319` nebo y `1..255`
- projectiles: 8-direction velocity table `0x8a80` — straight ±7,
  diagonals (±5,±5) px/tick; sprite = base + per-object direction
  table. P1 ma residentni pool presne 30 slotu. HELI child `0x939c`
  pali z world snapshotu predchoziho resume; novy bolt proto v tomtez VBL
  dostane vlastni pohyb i opacnou deltu kamery, az pak jej updater culluje

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
   spin anim — v prepisu uzavreno): muzzle vektor rychlosti16 se pricte
   jen jako signed high word 16.16 po kazde ose (diagonala `+11`, ale `-12`),
   potom start 0.5 px/t a **+0.5 px/t kazdych 5 tiku, strop 10.5 px/t**;
   globalni citac `fp@(206)` se inicializuje na 4. Pouze aimed wrapper
   `0x95d2` kontroluje zapor a omezi se na **5**; prime `0x95ca` a
   `0x95c2/0x95ec` jsou nehlidane a mohou vytvorit sesty i dalsi kus.
   Vstupy: `0x95ca` = v aktualnim uhlu `+358`; `0x95d2` = snap na
   ulozeny player slot + PLOP zablesk; `0x95ec` =
   nemireny, konstantnich 5 px/t. Kazda strela ma vlastni fazi:
   `0x96b4` strida BULLET#(24+smer) / #(40+smer) kazdy tik. Zvyseni
   rychlosti se provede az **po** patem pohybu a plny petikusovy aimed
   limit preskoci granat i jeho PLOP. Cannon nema object flag bit4, je
   world-space a do screen-y se mu kazdy VBL promita kamera; HOMING je
   naopak screen-locked. Jeho HW depth `world-y >> 1` se na `0x96aa`
   ulozi pred aktualnim `0x62d2` pohybem, zatimco sprite pozice uz nese
   vysledek pohybu. Margin-0 cull u obou typu pouze zavola `0x6db4`:
   zneplatneny task v temze VBL jeste enqueueuje posledni viditelny a
   kolizni field a loader jej uklidi az pri pristim resume. Regrese navic
   hlida, ze cannon prekryvajici chranenou HELI je jeden field skutecne v
   HW fronte a teprve N+1 jej kontaktni callback odstrani.
2. **Navadena strela** (`0x8530/0x8566`, sprite HOMING#smer — soubor
   HOMING.LIN ma presne 16 snimku): 3 px/t (+356=768), kazdych
   8 tiku otocka k hraci max 14 jednotek (~20°), **2×(5+D)
   korekci**, pak rovne. Prvni z 20 primych pohybu probehne uz ve spawn
   VBL. Muzzle PLOP zdedi parentovu rychlost; setup `PLOP#0` animator
   prepise pred prvnim enqueue, takze je jeden field videt HW `BULLET#2`
   a dalsi resume jej prikazem `KILL` ukonci (`0x85f0/0x861e`).

### FODDERA vlna (dispatch 0x0404 → 0x8048)
- leader `0x813a`: **x = 32+rand&255** (mapove x se ignoruje),
  `vx = sign16(rand>>16)/32768`, `vy=0`; `+348=0x800` je zrychleni
  **1/32 px/t²**, ktere se vypne pri `vy >= 3 px/t`
- pri D<2 celkem **4 clenove**, pri D≥2 pet, s world-y offsety
  `0,-4,-8,-12`; zadny `wait(10)` — kazdy ceka na vlastni `sy>=-48`
- okraje `0x8100`: x<32 → ax += 1/32, x>288 → ax −= 1/32;
  rychlost tedy neskace okamzite na ±1
- clen muze vystrelit **jeden mireny kanonovy granat** (`0x95d2`),
  kdyz `(rand&3)+D>=5`; stejne cislo dava cooldown z high wordu
- anim period 1: heli rotor 2,3,2,4,2,5,2,6; jet 0,1 (dle typ)
- po aktivaci flag bit 4 kompenzuje camera-scroll (`0x6434`), takze
  screen-y roste jen o vlastni `vy`, nikoli jeste o rychlost mapy

### POPUP (0xa6ae)
`64+(rand&63)` je nahodny **vstupni margin `a2c6`**, nikoli casovac:
POPUP se aktivuje pri `sy>=64..127` a hned dostane HP3, 70 bodu a cost14
(bez 160-guardu). Pri D=0 se po `a2c6` hned uklidi; jinak na `0xa6e4`
pripoji opening 1–7 s **periodou 6** (`0xa6e8`) a soubezne zacne wait50.
Pak salva ×`((D>>1)+1)`: snimek8,
`NOT.W +276` a `0x8530(±6,20,64)` = HOMING **dolu**; TOWN typ1 dava
prvni ranu z `x−6`. Po kazde rane 5 tiku snimek8 a 20 tiku snimek7,
po cele salve pauza50 → pripoj closing
6..1 s **periodou 6** (`0xa72a`) → `KILL` objekt. Pro D=1 je casova osa
od pripojeni openingu: t0 frame 0, t1–42 opening, t50–54 frame 8,
t55–125 frame 7, t126–161 closing, t162 objekt zrusi.

### YELLOW vojak (0x86bc)
kolona **6** (world-y offsety `0,-8,…,-40`), kazdy clen ceka na
vlastni `sy>=-48` a pak sam losuje x = rand&63 +
**(hrac vlevo ? 256 : 0)** = protistrana. Zacina uhlem 64 a 2 px/t;
ihned a pak kazdych 15 tiku: je-li hrac niz (`py−24 >= y`), otocka
k `(px,py−16)` max 12, rychlost `((2*manhattan)&0x7ff)/256`, jinak
reset primo dolu. Anim period 1: `0,1,0,2,0,3,0,4`.
Stejne jako FODDERA nastavuje bit 4, proto je aktivni pohyb v
screen-space nezavisly na dalsim scrollu mapy. HP je `D+1`; pokud
neni aktivni hrac, `0x72a6` vraci pohyblivy fallback `(96+n,128+n)`,
kde `n=(tick&255)<128 ? tick&255 : 255-(tick&255)`.

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
  druhy zasah jej znici. Stejny custom handler obsluhuje i HELI kontakt,
  takze prezity naraz rovnez udela odskok a odvetnou ranu

### MINE (0x0011 → 0x9b16) a pohyblive jadro (0x9860)

- parent se aktivuje pri `sy>=-16`, je staticky a rotuje `MINE#0..7`
  po 2 ticich (HP10/25 bodu/cost7)
- zasah hracskym boltem pouziva custom callback `0x9b62`: parent se
  jednorazove otevre na `MINE#8` a vytvori prave jedno jadro; callback
  neodecita parent HP jako bezny damage handler. Jako pozemni trida je
  kontakt s vrtulnikem harmless a jadro pri pouhem kontaktu nevytvori
- jadro (`0x9860`): `MINE#9,#10` period1, 10 HP, 30 bodu, cost5,
  `vy=0.5`, `z=32`; ma airborne bit4, proto se na obrazovce posouva
  o 0.5 px/t bez pricteni scrollu terenu. Kolizni trida **32** je jen
  sestrelitelna, takze kontakt s vrtulnikem je harmless. Neletalni bolt
  nema bezny hit flash; lethalni `0x98b4` da 30 bodu a spusti smart/white
  flash
- kontakt je **pickup stitu**: handler `0x98c4` (sloty `+514`/`+522`)
  bez aktivniho stitu nastavi hraci `+106 = −1`; jadro pak 10 snimku
  stoji bez BOBu a zmizi. Pickup callback v N+1 vstoupi do `wait10`;
  resume N+2 az N+11 pred waitem stale udela bit4 scroll compensation,
  v N+10 cost5 jeste drzi a v N+11 jej uvolni prave jednou. Hracova
  smycka `0x92a0` zalozi cost5 child
  `0x98f2`, nastavi `+106 = 500` a child hned zahraje jediny priority60
  activation tone. Orb strida `MINE#9/#10` kazdy tik na `z = player±2`,
  nema stin a je imunni vuci smart bombe. Po dobu stitu se `+108` drzi
  na 100 (`0x92ac`) a po jeho vyprseni ochrana jeste 100 tiku dobiha,
  celkem tedy asi 600 tiku. Dalsi jadro aktivni stit neprodlouzi a misto
  toho spusti smart/white flash (`0x98ec`)

### PROXMINE (0x000f → 0xa9e0)

- nahodny aktivacni prah `sy=85+(rand&31)`; 4 HP, 30 bodu, cost10 bez
  160-guardu. Pri D=0 se po `a2c6` okamzite uklidi
- otevreni `PROXMINE#0..5`, period6, pak wait100 a proximity test
  kazdych 10 tiku; metriku tvori Manhattan vzdalenost k nejblizsimu
  zivemu hraci
- pri vzdalenosti `<=120` parent bez bodu zmizi a vytvori 6 strepu v
  uhlech `aim+21+42*k`, k=0..5; kazdy leti konstantne 2.5 px/t,
  ma 1 HP/5 bodu/cost5 a pouziva bud sekvenci #6..11 period2, nebo
  #12..15 period3. Kazdy child bez noveho RNG testuje bit31 aktualniho
  globalniho seedu; vsech sest cost5 tasku je bez 160-guardu
- nove children se jeste v creation VBL pohnou, publikuji prvni animacni
  snimek a vyhodnoti margin-0 cull; pripadny cleanup prijde az pri N+1 resume
- bolt strepu spusti default damage/5 bodu; kontakt s HELI ma vlastni
  `+514=0x6db4` a strepu pouze odstrani bez bodu, exploze a zvuku
- zniceni parenta ctyrmi bolty je bez proximity salvy a da 30 bodu

### TRAIN (0x0010 → 0x9b7e)

- aktivace `sy=100`; lokomotiva 10 HP/75 bodu/cost15, `y=mapY-2`
- smer urcuje mapove x: vlevo start `x=-48,vx=+1`, vpravo
  `x=368,vx=-1`; TYP 4/8 je pocet vagonu, tedy 5/9 dilu celkem
- vagony jsou po 48 px za predkem, nahodne `TRAIN#1/#2`, kazdy
  2 HP/50 bodu/cost15; bit14 SET znamena #1, clear #2. Lokomotiva i
  vagony se uctuji bez 160-guardu; po ztrate parentu zpomaluji `vx*=15/16`
- creation FIFO odvozuje kazdy dalsi vagon az od uz pohnuteho predchudce;
  pri levem vjezdu je prvni field lokomotiva `x=-47`, vagony `-94,-141,…`
- horizontalni offscreen se zamerne neculluje; souprava konci primym
  coroutine testem `screenY>=272`, nikoli deferred `0x6480` callbackem.
  Osiřely vagon kazdy VBL zpomaluje signed 16.16 operaci
  `rawVx -= rawVx>>4`; zlomky shozené aritmetickym shiftem se neuchovavaji

### MILL (0x0058 → 0x79d4)

- aktivace `sy=-48`, 10 HP/70 bodu/cost15, vlastni `vy=0.5`
- po dosazeni `sy=24` zapne airborne bit4 a pak kazdych 100 tiku
  vypusti osm accel cannon strel po 32 uholovych jednotkach
- RNG navrat se zahodi a testuje se bit4 high wordu noveho seedu
  (`seed&0x00100000`): zaklad salvy je 0 nebo16. Palba pouzije pozici
  pred vlastnim 0.5px pohybem deadline VBL; cela
  osmismerova sada tedy strida osy a mezismery, bez mireni na hrace

### FLAME (0x0013 → 0xab10)

- parent se aktivuje v `sy=128`, ma 3 HP/40 bodu/cost10 a otevira
  #0..4 period6; po ticku24 vytvori linked emitter na `x+12`
- emitter (cost1) loopuje period2 pres presnou 14prvkovou sekvenci
  `12,13,12,14,12,13,14,13,12,13,12,13,14,13`
- po 100 lok. ticich a potom kazdych 100 vypusti unlinked puff;
  ten leti doprava 2.5 px/t, animuje #5..11 period5 a po 35 ticich
  (87.5 px) zanika; 35. field se jeste publikuje, cleanup prijde v N+1
- emitter i puff dostanou prvni pohyb/animacni publikaci uz v creation VBL;
  `0x6c88` v nem ukaze `seq[0]` a plnou periodu pocita az od dalsiho resume
- smrt parentu ukonci linked emitter, uz vypustene puffy dojedou
- parent, emitter cost1 i kazdy puff cost10 vznikaji bez 160-guardu

### MEDTANK (0x9eca)

- parent `a2c6(MEDTANK#0,class,-16,D+1,50,10)` a turret child
  `a2c6(MEDTANK#4,0x8000,-16,0,0,4)` jsou oba bez 160-guardu.
  TOWN TYP1..4 pouzivaji class `$24`; raw bit3 by ji zmenil na `$20`
- typ→najezd: 1: x=352/uhel128; 2: x=−32/uhel0; 3: uhel64;
  4: parent je uz aktivni/cost10, ale raw `0x9ac8(288)` jej bez BOBu
  a collision nodu drzi do `sy>=288`, teprve pak uhel192 a
  turret/celkovy cost14.
  Default ma uhel64 a rychlost0. Typy1..4 jedou 0.5 px/VBL
- presny parent cyklus je drive300/stop100 trikrat, potom park;
  korba #0=E,#1=S,#2=W,#3=N
- turret ulozi globalni tick a pred **kazdym** cyklem ceka modulo-word
  elapsed `(12-D)*16`. Cil je aktivni player node bez y−8, pri smrti
  fallback `(160,192)`
- `0xa096` pocita `int8(target-current)`, pocet
  `(abs(diff)+8)>>4`, a udela presne N kroku ±16, po kazdem wait6.
  Zbytek se nesnapuje. Pak wait16, nehlidany accel `0x95ca`, wait8,
  stejnym zpusobem zpet k aktualnimu uhlu korby a novy cadence gate

### ROTOBASE (0x994e)
`a2c6(ROTO#4,0x24,-16,4,35,10)` je bez 160-guardu. Anim spin 4..11
ma **periodu 2**;
`notw fp@(138)` na `0x9960` voli
reverzni `0x9986` a dopredny `0x996a` skript stridave podle **globalniho
poradi aktivace** (z pocatecni nuly je prvni reverzni), nikoli podle x;
smer vpred zacina znovu snimkem 4, ktery uz nastavil `a2c6`, proto ma
pocatek `4,4,4,5,5,…`; reverzni zacina `4,11,11,10,10,…`;
smycka spotrebuje **jediny** RNG long: low byte je uhel a stejne
`low&127` dava wait `200..327`; pak 4× nehlidany granat po 90°.
Countdown bezi i mimo viewport az do bezneho cullu na `sy>=320`.

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
- `SUBQ #8,+324` odskoci 8 px **nahoru** a osm `ADDQ #1` kroku jej
  vrati dolu; world-y se v remaku neinvertuje

### Zbran hrace (0x8aa0 + tabulky 0x8b86/0x8dd6)
- HELI `0x9410` kresli `JEEPHELI#0,1,0,2,0,3,0,4` s periodou1,
  ma stin `(x+16,y+32)` a pri `inv&8` se vyplni indexem9. Child
  `0x939c` je neviditelny scheduler; `JEEPHELI#9..16` ani #25 nejsou
  dalsi cast vrtulniku (patri jeepu/lodi)
- vrtulnik i jeep pouzivaji stejny dart system; vrtulnik ma smer zamceny
  nahoru (dir 6), jeep otaci vezi (`0x93b2`, vychozi uhel 192)
- **9 px/t** (zmereno: rozestup salv 97 px = 9 px/t × kadence 11 ✓)
- pocet strel = sila `+100` (`0x8ad0`: `subq #1` + `dbf`). Kod na
  `0x6fde` zapisuje **2**, ale MEGA TRAINER cracku SWIVFIX (volba F5/F6
  MISSILES, vychozi **1**) startovni hodnotu prepise: baseline snimek
  s drzenym fire ukazuje jednu strelu (hires sloupce 320–323), s
  MISSILES=3 tri strely na x 156/160/164 = licha tabulka `0x8d46`.
  Puvodni „start 1 z videa" bylo tedy spravne pozorovani; prepis
  startuje s 1 a po `0x70c8` ma kadenci 11. Tabulka
  (2,11)(3,10)(4,10)(5,8) se podle `+102/5` pouzije jen pri (re)spawnu
  jako `power=min(power,cap)`; pri 2P je efektivni kadence
  `max(ulozena,10)` (`0x728a`)
- ofsety (dir 6): liche sily stred (0,−8) + pary (−4,0)(4,0)(−8,8)
  (8,8); sude pary (−2,−4)(2,−4)(−6,4)(6,4); fan varianta (priznak
  +104) misto ofsetu rozklada vektory (0,−9)(±1,−8)(±2,−7)
- max sila (>5): 8 strel do vsech smeru z tabulky `0x8dd6`
  (BULLET#8–15)
- sprite boltu BULLET#14 (nahoru): jehla barvy 1–2, kulicka barva 3
  strida zlutou/cervenou po salvach (z videa)

### Paleta spritu
Barvy 13–15 jsou copper registry — **globalni pro celou obrazovku**
(meni se paletovym skriptem mapy), objekt si barvy nenese s sebou.
Kreslime aktualni paletou okna.

### Fade palety (`0x4a48`, `0x4a40`, driver `0x28b0`)

Precteno z disassembly, nikoli zmereno v emulatoru.

**Skalovac `0x4a48` neni interpolator** — je bezstavovy. Bere slovo
RGB12 v d0 a uroven fadu 0–256 v d1 a vraci kazdy nibble vynasobeny
`(256 − d1) / 256`:

```
negw d1 ; addiw #256,d1      ; d1 = 256 - d1
rolw #8,d0  -> nibble R
rolw #4,d0  -> nibble G
rolw #4,d0  -> nibble B      ; 8+4+4 = 16, slovo vypadne zpet v poradi
per nibble:  d7 = (nibble * d1) >> 8
```

`0x4a40` je `notw d0` → `0x4a48` → `notw d0`, tedy tataz rampa, ale
k **bile**.

**Uroven** drzi dve globalni promenne, obe v rozsahu 0–256; obe se
testuji na nulu, takze 0 = zadny fade:

| promenna | smysl | aplikuje se v |
|---|---|---|
| `fp@(11170)` | fade do cerne → `0x4a48` | `0x5da8` (cela paleta), `0x5e58` (jedna udalost) |
| `fp@(11166)` | fade do bile → `0x4a40` | tamtez |

Aplikuji se **jen na registry `0x180`–`0x19F`** (`cmpiw #384` na
`0x5e4c` a `cmpiw #416` na `0x5e52`) — coz nezavisle potvrzuje, ze
barvy spritu od `0x1A0` prochazeji nedotcene.

**Casova osa je korutina `0x28b0`**, registrovana pres `fp@(-1470)`
s prioritou −1; jeji telo konci `bsrw 0x5f0a` (yield) a `bras 0x28b0`,
takze krokuje **jednou za snimek**:

- **cerna**: smer dava znamenko `fp@(142)`. Zaporne → `+16` za snimek
  az na 256, kladne → `−16` az na 0; na konci se `fp@(142)` sam
  vynuluje. Rozsah 0–256 krokem 16 = **presne 16 snimku**, tj. 0,32 s
  pri 50 Hz. Pozor na jeden snimek navic: `subiw #16` na `0x28b8` testuje
  prenos, takze pri kroku 16→0 jeste nepodtece a priznak spadne az
  **17. snimek**. Obraz je tedy hotovy po 16 snimcich, ale blokujici
  `0x2864`/`0x2868` se vrati o snimek pozdeji.
- **bila**: pricita **znamenkovy** krok `fp@(11168)` za snimek, strop
  256, zastavi se na nule. V kodu se vyskytuje krok `+16`, `−16`
  a `−4`, tedy 16 snimku (rychle) nebo 64 snimku (1,28 s, pomale
  doznivani).

**API:** `0x2864` = fade do cerne, `0x2868` = fade z cerne. Oba nastavi
`fp@(142)` a pak **blokuji** — yielduji, dokud driver priznak
nevynuluje; volajici tedy dostane rizeni az po dokoncenem fadu.
`0x2856` je pouzity obal: fade do cerne + zbourani obrazovky, volany
pred kazdou vymenou obrazovky.

**Start hry se odcernuje**: `0x3092` (po zalozeni hracskych korutin)
i `0x330a` volaji `0x2868`. Prechody mezi obrazovkami tedy jdou pres
cernou v 16 snimcich na kazdou stranu.

**Bily fade slouzi jako zablesk s doznivanim**: uvodni sekvence na
`0xfd2` nastavi krok `+16` a uroven 8, pocka na 256, pozdeji prepne
krok na `−16` a nakonec na `−4`. Nektera mista naopak nastavi
uroven primo a hned ji zase smazou (`0xc12e` = 64 pri zasahu bosse)
— to je jednosnimkovy zablesk, ne rampa.

### TOWN boss GOOSE (dispatch `0x0017` → `0xc78a`)

- **rodic je nosic**: pin TOKEN.LIN (`0xc78e`),
  `a2c6(GOOSE#0, coll 0, vstupni margin 0, hp 0, body 0, cost 100)` a `st +534`
  (imunita vuci smart bombe). Behem naletu nema HP ani kolizi
- flag bit 4 (`0xc7b6`) odpoji scroll; `0xc7bc` prenese objekt na
  `x = 160` a `mapY += 288`, takze naleti **zespodu** rychlosti
  `+336 = −2.0` px/t. Anim `0xc7fc` s periodou 1 jej kazdy druhy snimek
  skryje (`orflag 128` / `andflag 128`)
- **ctyri potomci** (`0x6144`, `+276 = 4` = pocet nezadokovanych):
  pod/escort `0xcaac` (GOOSE#8..11, period 8) miri na `(0,+24)`, dve
  GOOSE#6 na `(−16,−12)` a `(+16,−12)`, GOOSE#7 na `(0,−44)`.
  Pod startuje bez prodlevy; tri casti tela volaji `wait(rand&63)`, ktery
  i pro nulu udela jeden cooperative yield. RNG poradi je lazy:
  pod spawn-x → left/right/top delay → jejich spawn-x az po waitu.
  Kazde dite plati cost10 az pri vlastnim startu a vstupuje shora z
  `(32+rand&255,−24)`
- **dokovani `0xcb78`**: dite ulozi cilovy ofset do `+284/+286`, nastavi
  `z = rodic+1`, odpoji se od rodice, rychlost 2 px/t a uhel 64. Nejprve
  leti 75 tiku rovne dolu (`0xcbc2`), potom se kazdy tik nataci k
  pohyblivemu cili nejvyse o `((63 − dist) clamp ≥ 2) / 2` jednotek
  (`0xcbf6`–`0xcc08`). Pri Manhattan vzdalenosti `< 6` publikuje jeden
  jeste nepripojeny `2*v` overshoot frame (`0xcc16`); az dalsi resume jej
  snapne na ofset, zapne follow-parent bit 3 a snizi `rodic+276`
  (`0xcc52`). Boj zacne teprve po pripojeni vsech ctyr
- tri casti tela po zadokovani (`0xca5a`) pri parent hit-flashi zdvojnasobi
  cilovy ofset a uz v prvnim ticku jej kontrahuji o 4 px (`0xca5e`,
  `0xca7a`); pak se sjedou zpet. Maji HP 0, tridu 34, takze jsou
  nezranitelne, ale zabijeji vrtulnik; sirotci handler `0x6db4` je po
  smrti parentu odstrani
- pod `0xcaac` po snapu ceka 20 yieldu a opakuje hadovitou sekvenci s
  ramenem 18 px: 6×−8, wait20, 6×+8, wait20, wait10..41,
  6×+8, wait20, 6×−8, wait20, wait10..41 (`0xcb20`–`0xcb76`).
  Relativni ofset se kazdy tick nahrazuje, neakumuluje. Sirotci handler
  `0xa36a` jej pri smrti tela necha explodovat za 0 bodu
- `0xc826`: po dosazeni `screen y 72` parent zastavi a **uz tady** dostane
  `+360 = 25` HP a `+504 = 34` (`0xc842`–`0xc854`), takze je zranitelny
  behem cekani na deti. Posledni blikajici ingress frame zustane na y72;
  dalsi frame spusti unfold `0,0,1,2,3,4,5` s periodou 10 a subtractive
  rotor `JEEPHELI#5/off/#6/off/#7/off/#8/off` (`0x93e2`). `0xc85e` pak
  ceka na `+276 == 0`
- **pohyb v boji**: vodorovne zrychleni `1536/65536` px/t² k hraci,
  `vx` orezane na ⟨−2, 1⟩ (`0xc888`); svisle `screen y < 64` → `vy = 4`,
  `> 192` → `vy = −0.25`, mezi tim drzi (`0xc8b2`). Pri mrtvem hraci
  steering helper vraci x160. Ingress 72, volba smeru x, svisle hranice
  64/192 i palebna hranice 128 porovnavaji pouze signed high WORD 16.16;
  napr. `128.75` je pro `CMP.W #128` stale uvnitr palebne oblasti
- **palba** jen pri `screen y <= 128`, kadence `(12 − D) × 4`
  (`0xc8da`): mireny kanonovy granat `0x95d2` + **dve navadene strely**
  `0x8530` s ofsety `+6` uhel 0 a `−6` uhel 128. Vsechny tri vzniknou
  z pre-move x; teprve nasledny `0x62d2` posune telo. Po pripojeni
  posledniho childa probehne inicializace i prvni combat update v temze VBL;
  timer se ale z 2000 poprve snizi az po nasledujicim resume
- **zasah** (`0xc974`) se zpracuje az pri resume v N+1. Vsechny bolty
  stejneho ticku koaleskuji na `−1 HP` a vsechny zasazene bolty zmizi;
  player-contact parentu je samostatny event a muze ubrat druhe
  HP. Kontakt jen s childem parent HP nesnizi. Neletalni hit obrati `vx`,
  na jeden frame vyplni jen parent indexem9 a tri body casti rozhodi na
  dvojnasobny target uz s prvni 4px kontrakci. Escort se neroztahuje.
  `0xc97e -> 0x4e46` navic zkusi dva priority40 noise hlasy; jejich globalni
  RNG seed prijde az pri druhem CIAB resume, ne v hit callbacku
- **smrt** (`0xc986`): odpoji deti (`0x60e0`), vytvori kruhy TOKENu a
  zahraje custom dvojhlas `0x8838`. `a36a` pouze zaradi fresh priority100
  child z vychoziho `+376 = 0x894a`; teprve jeho resume spusti dve BIGEXPL
  zadosti a EXPL1#7..13 period4 se `z=33`. Escort ma vlastni orphan resume
  a radi druhy `0x894a` se `z=34`, takze parent/escort efekty nejsou inline
  ani sloucene. Boss ma `d4 = 0`, tedy dava **0 bodu**
- **orphan poradi**: tri body childy na prvnim resume po unlinku potichu
  uvolni svuj cost10. Escort exploze pouzije jeho posledni publikovanou
  world pozici; az po jejim enqueue dobere zbytek snake callbacku, tedy
  2 RNG ve stage0..3, 1 ve stage4..8 a 0 ve stage9. Dite, ktere jeste spi
  v nahodnem pre-`a2c6` delay, jej po smrti parentu dokonci, spotrebuje
  spawn RNG a cost10, publikuje jeden creation field a orphan cleanup
  provede az pri pristim resume
- **checksum tail** (`0xc950`): neni skore, ale kontrolni soucet programu.
  Parent proto po poslednim viditelnem fieldu zustava jako priority100 task,
  provede 107 yieldu a cost100 uvolni presne v N+108 ve sve FIFO pozici
- **bonusy** (`0xc9a0`): za kazdeho zijiciho hrace jeden kruh — pocet
  urcuje volajici, krok uhlu `256/pocet`, pocatecni uhel nahodny, kazdy
  bonus je korutina TOKEN `0x96d8`. Znicen → **2** kruhy (3, kdyz uz
  ubehla vetsina casu, unsigned `+280 <= 500`); casovac `+280 = 2000`
  podtece az po 2001 dekrementech. Nedotceny boss → **5** a timer0,
  skrabnuty → timer `0xffff`; oba pri timeout resume preskoci dalsi combat
  pohyb i palbu, rovnou publikuji prvni `vy=−4` escape field a culluji se
  na y≤−64. Pri HP1 a pending `bit0|bit3` se oba death callbacky provedou:
  prvni pouzije puvodni timer a dropne 2 na ziveho hrace, `0xc9a0` zapise
  timer0 a druhy proto dropne 3. Vysledek je **2+3 TOKENu**, dve parent
  exploze a jedna escort exploze. Pocet zivych hracu se vzorkuje v kazdem
  callbacku; player task proto muze stejnym kontaktem zemrit drive a druhy
  kruh nedostat. Timeout/cull nema parent explozi ani death synth, ale
  orphan escortu a parent checksum N+108 zustavaji

### Bonus TOKEN (`0x96d8`) a hracska pole

TOKEN neni v dispatchi — zaklada ho kod, v TOWN jedine boss.

- `a2c6(TOKEN#0, coll 32, vstupni margin −16, hp 0, body 0, cost 5)`, flag bity
  0 a 4, `st +534` (imunni vuci smart bombe), `st +538` (bez cullu);
  cost5 se uctuje bez 160-guardu
- **rozjezd**: po a2c6 vypne sebrani i zasah (`0x65a4`, `0x658a`), rodi
  se jako **typ 3** (`0x9704`) s 12 obehnutimi, `+356 = 320` = 1.25 px/t
  ve smeru kruhu z `0xc9a0` a k tomu `subqw #1,+336` = 1 px/t nahoru;
  tak leti **32 snimku** (`0x9722`) a nejde sebrat ani prepnout
- teprve pak (`0x9728`) nainstaluje `0x97c6` (sebrani) a `0x9780`
  (strela), zastavi, klesa 0.5 px/t (`+338 = 0x8000`), jednorazove oreze
  `x` na 8–312 (`0x9742`), vynuluje `vx`, nastavi `vy=0.5` a zapne
  bezny bounds cull (`sf +538`)
- hlavni smycka `0x9764` **strida kazdy snimek ikonu typu a TOKEN#0**,
  takze bonus blika; `+278` se zmensi jen v icon pulce. Po zasahu zacina4,
  proto dalsi zmena typu muze nastat nejdrive za 10 tiku
- **strela typ prepina** (callback `+510`, `0x9780`): bonus vyskoci
  o 8 px, `+276 = (+276+1) & 3`; po dvanacti obehnutich vsech ctyr
  (`+280`) nastavi typ4 a cooldown12; nejde o permanentni zamek. Z realneho
  startu typ3 je do typu4 potreba 45 prijatych zasahu
- ikony jsou tabulka `0x97bc` = TOKEN#1..#5, index je typ

**Sebrani** (callback `+514`, `0x97c6`) podle typu:

Pred vetvenim podle typu se zvysi statistika sebranych tokenu a `0x97ce`
zachyti x konkretniho TOKENu pro ctyrnotovy pickup zvuk `0x5614`: periody
159/212/159/141 v casech 0/5/10/15 VBL, priority120. `0x5614` nezahraje
prvni notu inline; zalozi priority100 child `0x564c`, ktery se radi strictne
podle creation order mezi ostatni tasky. Pak se vzdy zvysi
samostatny HUD citac `+102`; hodnota 20 se vrati na 19, takze saturuje.
Zobrazeny stupen je `2 + (+102 / 5)` a neni totozny se silou zbrane `+100`.

| typ | ucinek | zapis |
|---|---|---|
| 0 / 1 | prepne **rezim zbrane** na 0 / −1; kdyz uz hrac tento rezim mel, prida **+1 silu** (strop 5) | `+104`, `+100` |
| 2 | **rychlejsi palba**: prodleva −3, minimum 8 | `+98` |
| 3 | **ochrana +500 tiku** (~10 s pri 50 Hz) a **+500 bodu** | `+108`, `+76` |
| 4 | **plna sila**: sila 6 (nad bezny strop), prodleva 8, k tomu zablesk `0x8852` a ctyrvrstvy `SMART.SND` | `+100`, `+98` |

Typ 3 pouze pricita ochranu do `+108` 16bitovym `ADDI.W #500,+108` a
nevytvari graficky child. Viditelny oblouk je samostatny MINE core kontrakt:
pickup nastavi `+106 = −1`, bound MINE#9/#10 se 500 snimku strida na
`z = player±2` a kazdy aktivni tick nastavi `+108 = 100`; duplicate dobu
neprodlouzi. Pri prvnim zalozeni bound childa vola `0x98f2` jediny priority60
activation tone `0x4ffe`; duplicate, zastreleny core ani TOKEN typ3 tento ton
nevolaji.

**Smart bomba** (`0x8852` → korutina `0x885a`): `0x8852` pouze zalozi
priority100 child; az jeho FIFO start provede zvuk `0x4cb2`,
`st fp@(169)`, `fp@(11166) = 256` (plna bila), 50 snimku, `sf fp@(169)`.
U TOKENu typ4 vznikne nejprve pickup-sound child a teprve potom SMART child,
takze prvni nota 159 zazni pred ctyrmi SMART requesty (posledni ji muze
preemptovat).
Doznivani bile ridi `fp@(11168)`, ktere se za hry nikde nezapisuje —
posledni zapisy z uvodni sekvence (`0xc9a`, `0x1028`) nechaji **−4**,
tedy 64 snimku. Po dobu `fp@(169)` vola housekeeping `0x6468` slot
`+534` kazdeho objektu; bezne aktivni objekty vcetne granatu a HOMING
proto zemrou. Samotny pulse body nepridava; score dostane jen cil, kteremu
resident sweep v temze VBL uz frontoval player event. Imunni jsou objekty,
ktere udelaly `st +534`: GOOSE telo, casti i pod, TOKEN, orb stitu,
PLOP a hracova exploze. Kazdy trigger ma vlastni 50tikovy task a prvni
dobihajici deadline muze globalni pulse vypnout i pri novejsim triggeru.
Deadline task je sam priority100 a resumeuje ve svem creation-order miste:
objekty starsi nez deadline jeste vidi SMART aktivni, deadline jej shodi a
mladsi objekty uz jej ve stejnem VBL nevidi.
Spousti ji TOKEN typ 4 (`0x985a`), sestreleni jadra miny (`0x98ba`) a
sebrani jadra s uz aktivnim stitem (`0x98ec`).

### Hrac — vrtulnik (`0x9410`; `0x9090` je jeep)

`0x7156`: P1 ma `+56 = 1` → `0x9410`; `+56 = 0` → jeep `0x9090`.

- pin JEEPHELI, `z = 32` (`0x941a`) → stin `(x+16, y+32)` (`0x6364`)
- `+108 = 200` tiku ochrany po spawnu (`0x9424`); kolizni zaznam `0x0048`
  (P1) / `0x0088` (P2); bit 4 v `+367`; smrt `0x9306` v **udalosti 1**
  (`0x654c` instaluje jen `+518`) — event = trida protejsku (sweep
  `0x6ec2`), takze vrtulnik zabiji prave objekty s bitem 1 tridy
- zbran je potomek `0x939c`: uhel 192, pali na bit 5 vstupu pres `0x8aa0`
- anim `JEEPHELI#0..4` period 1 (`0x945a`), nezavisle na smeru
- rychlost `+356 = 768` = **3 px/t** (`0x9476`); smer z tabulky `0x959e`
  podle joystickoveho nibblu (`0x71ac`: bit0 nahoru, bit1 dolu, bit2
  vlevo, bit3 vpravo; `0xffff` = stoji): `[-, 192, 64, -, 128, 160, 96,
  64, 0, 224, 32, 0, -, 192, 64, -]`
- `0x954c` pred vstupem clampuje starou screen pozici na `x 4..316`,
  `y 4..252`; nasledujici kardinalni krok muze v publikovanem framu
  dosahnout `x 1..319` nebo `y 1..255`
- `0x92a0` kazdy tik: stit `+106` (viz MINE), pak `+108 -= tiky` a pri
  bitu 3 nastavi hit-flash bit 1 (`0x92e4`) — ochrana blika 8/8 tiku
- smrt `0x9306`: `+108` nebo `+106` nenulove → nic; jinak exploze
  `0x88fc` (16 EXPL1 ve spirale po 2 ticich) a konec objektu
- respawn: hracsky task `0x7090` ceka **100 snimku** (`0x714e`), zatimco
  svet i enemy scheduler dal bezi. Cekani zacina az kdyz rodic uvidi
  smazane `+54`: callback `0x9306` (tik D) jen zneplatni generaci, telo
  `+54` smaze pri dalsim resume (`0x8f74`, D+1) a starsi rodic to cte v
  D+2 — novy `0x9410` tedy vznika v **D+102** (baseline t22..t25). Pak spotrebuje zasobu `+68`
  (−4/zivot, start −16 = 4), zavola `0x70c8` (tabulka zbrane) a zalozi novy
  `0x9410`. Browserovy kladny ekvivalent zacina `lives=4/HUD 3`, dovoluje
  posledni aktivni `lives=1/HUD 0` a continue otevre az po dalsim pokusu,
  ktery skonci na nule. `0x9046` zkousi terrain masku v kandidatske mrizce
  popsane v Player systems; `(288,192)` je az fallback pri uplnem zablokovani
- continue okno je **300 VBL s kreditem, 100 VBL bez nej**. Fire je
  level-triggered, takze tlacitko drzene uz pri vstupu prijme continue v
  prvnim VBL. Kredit obnovi `lives=4`, `score=0`, `nextLife=10000`; weapon
  `+100`, TOKEN counter `+102` a mode `+104` preziji (nasledujici `0x70c8`
  smi power clampnout dolu a obnovi reload)
- po timeoutu se join uzavre, credit word se vrati na tri, TOWN prestane
  zapisovat pulzujici `COLOR07` a nasleduje 16-VBL fade do cerne. Browser
  nastavi `g.over` az pri vstupu do `stats`; death wait, continue i fade
  ponechavaji tasky sveta bezet. Pixelove presna nativni stats obrazovka,
  vsechny jeji citace a high-score tok jsou stale otevrene
- inactive HUD strida pres bit 7 ticku po 128 VBL prompt a dynamicky status.
  Podle faze je prompt `PRESS FIRE`, `NO CREDITS` nebo `PLEASE WAIT`;
  nepripojeny pravy slot ma `jeepLives=1`, a proto v dynamicke pulce
  zobrazuje `JEEP 0`
- dvojity tap smeru (`0x7246`) / druhe tlacitko je **skok jeepu**
  (`0x91e8`), vrtulniku se netyka

### Kolizni tridy (`+504`) — kdo zabije vrtulnik

`a2c6` d1 → `+504`; bit 5 = sestrelitelne (`+510` = `0xa362`), bit 1 =
vzdusny objekt: dotek s vrtulnikem (`+514` = `0xa362`), bit 2 = pozemni:
dotek s jeepem (`+522`). Handlery se instaluji jen pri `HP ≠ 0`. Vrtulnik
zabiji jen trida s bitem 1: letci (34), MILL (34), GOOSE telo od `0xc854`
(34), jeho casti a pod (34, HP 0 = nezranitelne), HOMING (38, 1 HP,
7 bodu — **sestrelitelna**), strepy PROXMINE (38), kanonovy granat (6).
Trida 36 (mina, PROXMINE, vlak, plamen, POPUP, ROTOBASE, CAMOGUN), 32
(MEDTANK, jadro miny, TOKEN) a 4 (puff plamene) vrtulnik neohrozi. Tabulka
vsech TOWN objektu a hranice „odvozeno" jsou v [TOWN-AUDIT](TOWN-AUDIT.md).
Dotek vzdy spusti damage handler objektu (`−1 HP`, hit flash), nezavisle
na ochrane hrace.

**Hit flash**: `0xa35a` nastavi bit 1 v `+367`, drawer `0x63a4` z nej
udela bit 4 kresliciho zaznamu a housekeeping `0x6452` ho kazdy tik maze
— objekt je jeden snimek po zasahu kresleny jinym mintermem.

Odtud plynou vyznamy hracskych poli: `+76` skore (long), `+98` prodleva
palby, `+100` sila zbrane, `+102` HUD citac vsech pickupu, `+104` rezim,
`+108` doba ochrany.
Tabulka zbrane `0x70c0` je **bajtova** — `02 0b / 03 0a / 04 0a / 05 08`,
tedy (strop sily, kadence) indexovane `floor(+102/5)`. Rutina `0x70c8`
ji aplikuje jen pri startu/respawnu a pouziva MIN clamp, ne upgrade.

### Triggery chovani
Objekty uvnitr uvodniho okna se NEaktivuji; korutiny jsou zakladany
map readerem uz asi **256 px pred obrazem** a jejich `a2c6` je pusti podle
vlastniho marginu. Pre-a2c6 RNG (FOD/YELLOW/BIRD clone, POPUP/PROX prah)
se tedy spotrebuje pri prefetchi, ne az u viditelne aktivace. FODDERA a
YELLOW pouzivaji −48, nikoli genericky wrapper −32. Browser tuto dvojici
fazi uz ma, ale vsechny ve stejnem tiku zpusobile mapove zaznamy zatim
startuje v jednom JS passu; nativni per-record yield poradi je otevrene.

### Dodatky (2. iterace M1)
- **Granat rotuje — v prepisu uzavreno**: telo strely (`0x96b4`)
  kazdy tik prohazuje
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
  Po vlastnim `a2c6` jeden random long urci `(low&3)+D>=5`; high word
  tehoz cisla dava 32..95. `SUB.W` pali az pri podteceni, tedy po
  33..96 VBL, bez sy/alive gate a pred vlastnim pohybem; pak uz nikdy.
- **fp@(-76)** = pocet hernich tiku za snimek (normalne 1) — cte ho
  i kadence hrace (0x7296). NENI to scroll.
- **Rotace veze tanku** (`0xa096` docteno): smycka — krok ±16
  jednotek (22.5°), prekresleni spritu (0xa290), 6 tiku pauza,
  `diff=EXT.W(low byte(target-current))`, pocet
  `(abs(diff)+8)>>4`. Vez se nesnapuje na raw remainder, vystreli az
  po wait16 a stejnym tempem se vraci ke korbe; pak znovu cely gate.
- **+336 < 3 → +348 se nemaze** (`0x80f4`): sekundarni sestup 0x800
  prezije jen pri pomalem primarnim vy; rychli padaci ho ztraceji.

## DESERT (prepsano 2026-09-03; overeni proti baseline t329..t369 probiha)

### AIRMINE (0x0012 → 0x75a8)

- `a2c6(AIRMINE#0, 34, −48, HP 3, 20 bodu, cost 7)`, z 32 se stinem, anim
  `0x75c4` AIRMINE#0/#1 perioda 7
- `vx = (slovo 0x883c >> 2) / 65536` (do ±0.125 px/t), vy 0 a bez bit4:
  drzi se mapy; `+340 = −0.1875` px/t se pred kazdym `wait(10)` obraci
  (`0x75e4..0x75ee`), z tedy kmita 32..33.9 a stin se houpe; smrt default
  `a36a`

### BLACKJET (0x0020 → 0x7a98)

- `a2a2(0, −4, D/2 + 5, 0)` klonu, kazdy `a2c6(BLACKJET#0, 34, −48, HP 1,
  25 bodu, cost 15)` s guardem `0x8822`, z 32
- po aktivaci vlastni `x = 32 + (0x883c & 255)`, zvuk `0x52d8`,
  `+350 = 0x1800` (ay = 3/32 px/t²), zadny dalsi pohyb (`0x62cc` ceka na
  smrt): strely padaji volnym padem

### TILT (0x0026 → 0x7de8)

- `a2c6(TILT#3, 34, −48, HP 2, 40 bodu, cost 12)`, bit4, z 32, rotor
  `0x93e2` (JEEPHELI#5..8 kazdy druhy snimek)
- vy 1 do `sy ≥ 64` (`0x9afa(64)`), pak vy 0, `ay = 0x800/65536`,
  `vx = ±4` (x ≥ 160 → −4, `+276` = smer), anim TILT#2,#1,#0 resp.
  #4,#5,#6 (perioda 6, `end(0)` drzi posledni) a mireny kanon `0x95d2`
- smycka `0x7e64`: `x < 64` → ax +0x3000/65536, pri zmene smeru anim
  #5..#0 a kanon; `x > 256` → ax −0x3000/65536, anim #1..#6 a kanon;
  rychlost neni omezena (po obratce ~4.06 px/t); s ay klesa a odejde
  cull −64 asi po 240 tikach

### DESTRAIN (0x0619 → 0xa1b0)

- `a2c6(DESTRAIN#3, 36, 0, HP 12, 65 bodu, cost 7)`, `+367` bit 0 (bez
  stinu); TYP z `+276`: 1 → x −32, vx +0.5, vy −0.5/32; 2 → x 352, vx
  −0.5; 3 → x −32, vx +0.5 (`0xa1c8..0xa20e`)
- smycka `0xa20e`: wait 50, anim DESTRAIN#4,#5,#6,#5,#4,#3 perioda 1
  (drzi #3), wait 10, homing `0x8530(+6,0,0)`, yield `0x629a`, homing
  `0x8530(−6,0,128)`; smrt default

### TINYTRUK (0x000b → 0xaedc)

- `a2c6(TINYTRUK#0, 36, 272, HP 8, 45 bodu, cost 10)`: aktivuje se az
  pod spodnim okrajem a jede nahoru `vy = −0.75` (na obrazovce −0.5 px/t);
  `+374 = 5` = dekal EXPL1#0; trida 32, po 100 ticich 36
- anim `0xaf04` #0,#1,#2 perioda 1 loop; po wait 100 sest salv po 20
  ticich (`0xaf48`, `d = min(3, D)`: bit 0 → homing (0,−2,192) + wait 8,
  bit 1 → homing (−4,2,160), wait 8, (4,2,224), wait 8); pak vy 0 a ceka
  na smrt (`0x62cc`). Pri D = 0 nestrili vubec

### EGGS — vejce (0x041d → 0x8478) a hnizdo (0x181d → 0xa8e4)

Velke ovalne „skorapky" na zemi jsou EGGS#0 (staticka grafika mapy);
objekt s chovanim je maly tvor EGGS#2 (24×38, hitbox z hlavicky 11/19),
ktery v nich sedi. Snimky overeny archem `build/sheets/080_eggs.png` a
zabery originalu t437..t447 (`build/survey/shoot/`).

- **Vejce `0x8478`:** `a2c6(EGGS#2, 32, −16, HP 0, 200 bodu, cost 13)`,
  `+328 z = 0`. Ceka na radek 128 (`0x9afa`), pak anim `0x0849e`
  (perioda 10: EGGS#3..#7, drzi #7 = tvor 19×19; docs/ANIMS.md) soubezne
  s wait 50 (`0x629c`); potom `+340 vz = 0x8000` (0.5 px/t) a smycka
  `0x62d2`, dokud `z < 32` (64 tiku). Pak `vz 0`, `HP 15`, handler
  `0x8510` pro bit 0 i bit 3 (`0x653e`/`0x6566`), trida 34 (smrtici
  kontakt), rychlost `+356 = 128` (0.5 px/t) smerem na
  `(96 + (0x883c & 127), fp@(3530))` = nahodny sloupec horniho okraje
  (`0x65be`/`0x65f2`), `0x62cc` do zabiti. Stin kruhovy (z 32) — v
  originale t437 vedle skorapky.
- **Smrt `0x8510`:** HP−1; pri > 0 jen `0xa35a` (flash + zvuk); pri 0 se
  `+358` vynuluje a 16× `0x95ca` (rovna kanonova strela) s krokem 16 v
  `+359` = uhly 0,16,…,240, pak `0xa36a` (200 bodu, oblacek `0x894a` v
  z 33). To je „hodne strel jako z tanku" po rozstreleni.
- **Hnizdo `0xa8e4`:** nejprve tri deti `0x614a` (kopie zaznamu rodice):
  `0xa92a` (−51,−13) EGGS#9, `0xa93c` (0,+65) EGGS#10, `0xa948`
  (+51,−13) EGGS#11; kazde `a2c6(…, 36, −20, HP 8, 75 bodu, cost 10)`,
  `+367 |= 4`, `+542 = 0xa36a` (sirotek po smrti hnizda umira s kreditem
  a oblackem). Dite ceka na radek 8 (`0x9afa`) a pak 16× { strela
  `0xa9a0` pres `0x6178`, wait 100 } a `0x62cc`. Rodic: zamek
  `0x5eda(6)` (nemodelovano), `a2c6(EGGS#12, 36, −32, HP 18, 75 bodu,
  cost 20)`, `+376 = 0x8876`, `0x62cc`.
- **Strela vejce `0xa9a0`:** dite zdedi polohu, `+324 += 16`, zvuk
  `0x5436(x)` (zatim bez prepisu), `a2c6(BULLET#56, 6, 0, HP 0, 0 bodu,
  cost 5)`, `+367 |= 1` (bez stinu), `z += 1`, PLOP `0x85f0`, `+336 vy =
  6` v mapovych souradnicich (na obrazovce 6.25 px/t), `0x62cc`; cull
  `0x6480` s marginem 0. Trida 6 = smrtici kontakt, HP 0 = bolt ji
  neznici.
- **Velky vybuch `0x8876`** (`+376` velkych objektu): zvuk `0x4c3c`, anim
  `0x888c` EXPL2#0..#6 perioda 6 + kill (42 tiku), `+367 |= 1`; kazdych
  15 tiku (`0x629c`) oblacek `0x8952` (EXPL1#7..#13 bez zvuku) na ofsetu
  `((0x883c & 63) − 31, (horni slovo & 63) − 31)` — jedno `0x883c` na
  oblacek, tedy t 0, 15, 30. Prepis: `queueTownExplosionTask(..., "big")`
  + `boom.puffs`.
- Prepis: `IMPLEMENTED_BEHAVIORS` egg/eggnest, hazard `eggchild`
  (nodeKey `eggchild9..11`), strela `eggshot`, `spawnEggChildren`,
  `fireEggShot`; simulace DESERT (`build/survey/egg/`): hnizdo zrozeno v
  tiku 592 se tremi detmi, prvni strela hned (spodni dite je uz na radku
  33), vejce zrozeno 1036, anim od radku 128 (tik 1612), stoupani
  1662..1726, 15 zasahu → 16 strel.

### DIAGUN — diagonalni delo (0x041a → 0xa76e, 0x081a → 0xa788)

- Typ podle grafiky z PAM (`+276`): `0xa76e` DIAGUN#2 klid / `+278` =
  DIAGUN#3 palba, uhel `+358 = 32` (vpravo dolu); `0xa788` DIAGUN#4 / #5,
  uhel 96 (vlevo dolu). Spolecne `0xa7a0`: zamek `0x5eda(6)`,
  `a2c6(+276, 36, −48, HP 7, 80 bodu, cost 18)`, `+376 = 0x8876`, wait
  100, `+280 = 15`× `0xa7e0` { `0x6d7c(+278)` = palebny snimek i hitbox z
  jeho hlavicky, laser `0xa804` pres `0x6178`, wait 5, `0x6d7c(+276)`
  zpet, wait 30 }, pak `0x62cc`.
- **Laser `0xa804`:** `a2c6(DIAGUN#6, 38, −48, HP 1, 6 bodu, cost 5)`,
  `+328 z = 33`, `+367 |= 1` (bez stinu), rychlost `+356 = 640` (2.5 px/t)
  ve zdedenem uhlu (`0x65f2`), potom `+320/+324 += 16×` rychlost
  (`0xa82c..0xa848`, tj. start 28 px diagonalne od dela), anim `0xa850`
  DIAGUN#6..#9 perioda 1 loop, `0x62cc`. Mapove souradnice, trida 38 =
  smrtici kontakt i zasazitelny (jeden bolt, 6 bodu, oblacek v z 33).
- Prepis: `IMPLEMENTED_BEHAVIORS` diagun (oba gfx), hazard `laser`
  (`spawnDiagunLaser`), `nodeKey` diagun2..5 podle aktualniho snimku.
  Simulace (`build/survey/dpy/`): zrozeni tik 4420 (x 84, sy −48), prvni
  laser 4519 na (114, 6) s v = (1.77, 1.77), druhy 4554, 7 zasahu → BIGEXPL.

### PYRAMID (0x0221 → 0xa866)

- Cihlova podstava je PYRAMID#0 (mapova grafika); objekt je poklop
  PYRAMID#1. Zamek `0x5eda(6)`, `a2c6(PYRAMID#1, 36, −32, HP 10, 75 bodu,
  cost 15)`, `0x9ae8(64)` = wait na radek 64 s vynulovanou tridou `+508`
  (do te doby bez kolizi; prepis drzi HP 0), `+376 = 0x8876`, anim
  `0xa890` PYRAMID#2..#8 perioda 8 a drzi (poklop se otevre za 48 tiku),
  wait 100, `(2 + fp@(182))`× { `notw +276` → x-ofset −6/+6 stridave
  (prvni −6, protoze `+276 = 0x0221` je kladne), homing `0x8530` na
  (x ± 6, y + 20, uhel 64), wait 20 }, `0x62cc`.
- Simulace: zrozeni tik 2484 (x 253), aktivace na radku 64 (tik 2868),
  poklop #8 v 2916, homing 2968 a 2988 (D = 0), 10 zasahu → BIGEXPL.

### Spolecne pomocne rutiny formaci a smeru

- **`0xa2a2(d0 dx, d1 dy, d2 pocet, d3 dtyp)`** = formace: DBF smycka
  `pocet−1`× { `0x6178` kopie aktualniho zaznamu rodice (vcetne `+276`
  typ), pak rodic `+320 += dx`, `+324 += dy`, `+276 += dtyp` }. Kopie
  pokracuji za volanim (uz neklonuji). Prepis `spawnFormationCopies` ve
  `startMapObjectTask` (ctecka mapy, 256 px nad oknem).
- **`0xa290(base)`** = `0x6d7c(base + dir16(+358))` (16 smeru, i hitbox z
  hlavicky snimku); **`0xa27c(base)`** = 8 smeru; `0xa268`/`0xa252` totez
  pres tabulku slov.
- **`0x72ee`** vraci polohu ziveho hrace (pri smrti posledni ulozenou);
  **`0x72a6`** polohu hrace 1, bez ziveho hrace `x = 96 + |dolni bajt
  fp@(-66)|` (`playerAimX72a6`).
- **`0x62fe`** housekeeping: rychlost += zrychleni, poloha += rychlost
  (× ubehle VBL), zaporne `z` se orizne na 0 a vynuluje vz i az.

### FISH (0x001e → 0xb1a8)

- Formace `0xa2a2(0, −5, 6, 0)` = sest ryb po 5 px nad sebou; `ST
  fp@(3615)` zapina COLOR07 (voda; prepis `g.townColor07Enabled`).
  Kazda: `a2c6(FISH#0, 34, −48, HP 1, 40 bodu, cost 10)` + guard `0x8822`;
  `z = 0x883c & 31`, `az = −4096/65536`, `vy = 2` (mapove), vx 0.
- Smycka `0xb1ec`: je-li cele slovo `z == 0`, novy skok `vz = 2`,
  `az = −0.0625` (parabola 63 tiku, vrchol 32) a cakanec `0x9358`
  (JEEPHELI#33..#37 perioda 4, 20 tiku, bez stinu, cull margin 0); typ 2
  navic `vx = (slovo 0x883c)/65536` a mireny kanon `0x95d2`. DESERT ma
  jen typ 1. Trida 34 = smrtici kontakt, jeden zasah.
- Simulace (`build/survey/d3/`): prvni ryba tik 16876 (x 57), dalsi po
  20 ticich; guard `0x8822` pri plnem rozpoctu nektere odmitne.

### GOOSE#7 (0x0e17 → 0x8794) — stremhlave stihacky

- Formace `0xa2a2(0, −8, 6, 0)`; kazda `a2c6(GOOSE#7, 34, −48, HP 2, 35
  bodu, cost 10)` + guard `0x8822`, `+367 |= 0x10` (obrazovka), z 32.
  Podle x hrace (`0x72ee`): `< 160` → start `x = 256 + (0x883c & 63)`,
  `vx = −0.5`; jinak `x = 0x883c & 63`, `vx = +0.5`. `vy = 1`, wait 50,
  `vy = 0.5`, wait 70, pak smycka `0x880e` { `+336 += 4` (slovo, tj.
  vy 4.5, 8.5, …), mireny kanon `0x95d2`, wait 20 }.
- Simulace: zrozeni 17060, prvni zaznam odmitnut guardem, dalsi
  startuji vlevo (x 27..61) a od tiku +130 pikuji.

### FLATTANK (0x0027 → 0x9e04)

- Nejprve dite `0x6144(0x9faa)` = stejny turret child jako MEDTANK
  (`+336 = 4` se v childu necte), pak `a2c6(FLATTANK#0, 36, −16, HP D+5,
  50 bodu, cost 12)`, `+374 = 5` (dekal EXPL1#0), `+397 |= 1`, anim
  `0x9e38` #0..#3 perioda 2 loop (pasy), uhel 64 a rychlost 32/256 =
  0.125 px/t dolu (`0x65f2`), `0x62cc`. Vez: gate `(12−D)<<4` bezi od
  startu tasku (256 px nad oknem), pri aktivaci je otevrena; prepis
  `spawnTankTurret`/`stepTankTurret` s `turretStartTick` posunutym zpet.
- Simulace: zrozeni 13168 (x 94), vez miri hned, prvni strela ~ +250.

### SKYEYEB (0x100a → 0x76ec) — letajici oci

- `x = −16`, `+276 = 7`, formace `0xa2a2(−40, 0, 6, −1)` = sest kusu po
  40 px vlevo za okrajem s poctem otacek 7, 6, 5, 4, 3, 2. Kazdy:
  `a2c6(SKYEYEB#0, 34, 24, HP 1, 30 bodu, cost 10)` (aktivace az na radku
  24), `+538 = −1` (zadny cull), `+367 |= 0x10`, z 32. Podle x hrace
  (`0x72a6`): `< 160` → zrcadlo `x = 320 − x`, krok `+278 = −16`, uhel
  128; jinak +16 a uhel 0. Rychlost 896/256 = 3.5 px/t, snimek
  `0xa290(SKYEYEB#0)` = dir16 (soubor ma #0..#8 = uhly 0..128).
- Nalet `0x7760`: pred kazdym yieldem, je-li `x <= 320` bez znamenka,
  jedno `0x883c` a mireny kanon jen pri `(slovo & 127) < D` (D = 0 nikdy);
  konec, jakmile `144 < x < 176`. Pak `+538 = 0`, wait 10 a `+276`×
  { wait 4, uhel += krok, `0x65f2`, `0xa290` } — spirala; nakonec `0x62cc`
  rovne ven.
- Simulace: zrozeni 12372 (x −212..−12, sy 24), stred po ~50 tiku,
  otacky po 4 ticich, konecne uhly 112..32.
