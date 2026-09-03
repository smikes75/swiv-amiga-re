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

### JETS (0x001f → 0x9ca0, 0x021f → 0x9d1e)

- **JETS#0 `0x9ca0`:** `a2c6(JETS#0, 36, −32, HP 18, 90 bodu, cost 15)`;
  wait na radek 100 (`0x9afa`), `vx −0.5`, `vy +0.5` (mapove), wait na
  radek 288; pak dite `0x9cde` a konec tasku (`0xa34c`, bez vybuchu).
  Dite = vzlet: `a2c6(JETS#2, 34, 288, HP 2, 90 bodu, cost 15)`, raw wait
  100 (`0x5f22`: bez pohybu i cullu), `y = fp@(3542) + 288`, z 32,
  `vy −4`, `vx 0`, `0x62cc` — stroj proleti zdola nahoru 3.75 px/t na
  obrazovce. Prepis `spawnJetFly` (zaznam `jetfly`, `noCull` behem raw
  waitu).
- **JETS#1 `0x9d1e`:** `a2c6(JETS#1, 36, −32, HP 18, 90 bodu, cost 15)`,
  `+538 = −1`, `vx −0.25`, `vy +0.25`, wait 200, `0x6d96` (vynuluje
  rychlosti i zrychleni), `+538 = 0`, `0x62cc`. (`x += 100; x −= 100` je
  bez ucinku.)
- Simulace (`build/survey/d4/`): JETS#0 zrozen 13032 (x 267), sjizdi od
  radku 100, vzlet JETS#2 z x 141 v tiku ~13910.

### TRUCK (0x0024 → 0x9d64)

- `a2c6(TRUCK#0, 36, −48, HP 30, 50 bodu, cost 15)`, `+367 |= 1` (bez
  stinu), **`x = −48`** (bez ohledu na PAM), z 1, `vx 0.5`. Smycka
  `0x9d88`: wait 70, uhel `112 + (0x883c & 31)`, dite `0x9dc0`, `vx 0`,
  wait 20. Dite: `a2c6(TRUCK#1, 36, −16, HP 3, 10 bodu, cost 5)`, anim
  `0x9dd6` TRUCK#1..#3 perioda 4 loop, rychlost 512/256 = 2 px/t ve
  zdedenem uhlu, wait 20, pak `vx = vy = 0` (lezi) a `0x62cc`. Prepis:
  hazard `truckdrop` (`spawnTruckDrop`).

### _AIRPORT#14 (0x1c3c → 0x7970) — startujici letadla

- Nejprve `0x6178` kopie s aktivaci 127 (`0x797e`), rodic 176. Oba:
  `a2c6(_AIRPORT#14, 34, 176|127, HP 2, 25 bodu, cost 3)`, **`SF
  fp@(3615)`** (COLOR07 vypnout), `+397 |= 1`, z 12, `x −= 40`, `vx 0.5`,
  wait 80, anim `0x79ba` = _AIRPORT#15 (loop jednoho snimku), `+346 =
  0x1000` → ax = 0.0625 px/t², `0x62cc`.
- Simulace: dite zrozeno 12584 (x 8, sy 127), rodic pozdeji na 176;
  vx 1.19 po 90 tikach, 4.94 po 150.

### _RIGS#4 (0x083e → 0xb22a)

- `a2c6(_RIGS#4, 36, −16, HP 20, 40 bodu, cost 10)`, wait na radek 24,
  `+276 = 5`× { wait 20, uhel 64, `0x95c2(0, 8)` = rovna kanonova strela
  z (x, y + 8) dolu }, `0x62cc`. (`0x95c2` = `0x95ca` s ofsetem d0/d1.)

### _ONERIG (0x003d → 0x8166) — vrtulnikova plosina

- `a2c6(_ONERIG#0, 34, −16, HP 6, 45 bodu, cost 15)`, z 0, sekundarni
  rotor `0x6c82` (slot +422) JEEPHELI#5..#8 perioda 10 loop (pomaly,
  stale videt); wait na radek 64, `0x93e2` = standardni rotor (perioda 1,
  #5..#8 po dvou tikach, blika bitem 0x80), `vz 0.5` do `z ≥ 32`, `vz 0`,
  rychlost 0, uhel 192 (nahoru), krok `+276 = x < 160 ? 12 : −12`,
  `+278 = 20`× { wait 14, uhel += krok, `+356 < 768` ? `+356 += 288`
  (1.125 px/t) : mireny kanon `0x95d2`, `0x65f2` }, `0x62cc`.
- Simulace: zrozeni 13020 (x 51), zdvih od radku 64 (tik +330), spirala
  vpravo, rychlost 3.3 px/t v +480.

### INST1#9 (0x121c → 0xb954) a JEEPHELI#31 (0x3e00 → 0xacb6)

- INST1#9: `a2c6(INST1#9, 0, −24, HP 0, 0, cost 2)`, anim `0xb96a`
  INST1#9/#10 perioda 4 loop (blikajici svetlo), `0x62cc`.
- JEEPHELI#31 → `0xacb6`: `a2c6(SWAP#1, 0, −16, HP 0, 0, cost 10)`, `+534`
  vypnuto, `+397 |= 1`; po radku 32 zapise svou polohu do
  `fp@(3554)/(3556)`, vynuluje `fp@(3548..3551)` a ceka, dokud
  `fp@(3548)` nekdo nenastavi (logika jeepu; heli bez ucinku). Prepis
  kresli SWAP#1 staticky.

### Vazane deti (`0x6144`, `+367` bit 3) — zmereno na FLATTANK/MAMA

- `0x6144` zaklada dite s `+542 = 0x6db4` (sirotek umira bez vybuchu),
  `0x614a` totez s vlastnim zaznamem, `0x6178`/`0x617a` kopie s
  `+542 = −1` (nezavisle). V `0x62d2` (0x62da..0x62f8): ma-li objekt
  `+367` bit 3 a rodice `+308`, **zkopiruje x/y/z rodice a integruje
  presne jeden krok vlastni rychlosti** — `+332/+336` jsou tedy pevny
  ofset vuci rodici (vez MEDTANKu 0, vez FLATTANKu (0, +4), bar MAMA
  (0, −30)). Bit 2 (`0x63ac`): dite blika spolu s rodicem (`hitFlash`).
  Prepis: `turretDy`, hazard `mamabar` polohovany z kroku rodice.

### MAMA (0x0025 → 0x7baa) — miniboss s rojem

- `a2c6(MAMA#0, 34, −48, HP 70, 300 bodu, cost 35)`, `+367 |= 0x10`, z 32,
  rotor `0x93e2`, dite `0x6144(0x7be6)`, `vy = 0x6000/65536 = 0.375 px/t`
  (obrazovka), `0x62cc`. Smrt = bezny oblacek `0x894a` (z 33).
- **Bar `0x7be6`:** `a2c6(MAMA#1, 34, −48, HP 0, 0, 0)`, `+538 = −1`, rotor
  `0x93e2`, `+367 |= 12` (vazany, ofset (0, −30)); wait na radek 48,
  snimek MAMA#2 (`0x6d76`), wait 4, smycka { dron `0x6144(0x7c44)`, je-li
  `sy < 208` wait 4 a znovu }, MAMA#1, konec tasku (drony osiri).
- **Dron `0x7c44`:** `a2c6(MAMA#3, 34, −48, HP 1, 13 bodu, cost 9)` + guard
  `0x8822`, bit4, z 24, varianta `0x883c & 3`: anim `0x7d2e` #3,#4,#5,#4
  perioda 3 / `0x7d44` #6,#7,#8,#7 perioda 4 / `0x7d5a` #9,#10,#11,#10
  perioda 1 / `0x7d70` #12,#13,#14 perioda 3 (loop). `+276 = 0`, `+542 =
  0x7d84` (sirotek: `+276 = −1`), uhel 192, rychlost 640/256 = 2.5,
  `+282 = ~vx`. Smycka `0x7cac`: je-li `(slovo vx) ^ +282 < 0`: wait
  `+280 = (0x883c & 7) + 2`, krok 0; `d1 = 127 − sy`; je-li `d1 ^ (slovo
  vy) < 0`: `+282 = slovo vx`, krok +10, a je-li `(x − 160) ^ d1 >= 0`
  krok −10. Uhel += krok, `0x65f2`, wait `+280`; po sireni (`+276`)
  `0x6d96`, `vy = −2` (slovo), `+350 = 0x4000` (ay 0.25) a pad
  (`0x62cc`). Prepis `spawnMamaDrone`/`stepMamaDroneBody` (16bitova
  slova pres `signedWord`).
- Simulace (`build/survey/d5/`): zrozeni 13928 (x 88), bar od radku 48
  (tik +400) plni rozpocet (6 dronu pri cost 169), bar konci na radku
  208 (tik ~+760), drony padaji.

### INST1#14 (0x1c1c → 0xb6ce) — plosina s pistem a odpalovacem

- Rodic: dite `0x6144(0xb71c)` pred `a2c6(INST1#14, 0x8000, −60, HP 0, 0,
  cost 10)` (trida bit 15 = bez sweepu), `+367 |= 1`, z 2; smycka:
  snimek INST1#14/#15 podle bitu 1 celeho y pistu (`+312 → a0@(325)`).
- **Pist `0xb71c`** (nevazany, `+542 = 0x6db4`): `y += 57`,
  `a2c6(INST1#16 | #17 podle typ ≠ 1, 36, −48, HP 0, 0, cost 15)`, bez
  stinu, z 1; smycka: wait `150 + (0x883c & 60)`; je-li `fp@(140)` (pocet
  aktivnich tovaren INST1#11) 0 → znovu; jinak dite `0x6178(0xb7a6)`,
  27× { yield, y −= 1 }, wait 30, 27× { yield, y += 1 }.
- **Odpalovac `0xb7a6`:** `a2c6(INST1#3, 4, −32, HP 7, 70 bodu, cost 8)`,
  z 0, wait 70; smycka `0xb7c2`: `vy 0.5`, wait `50 + (0x883c & 63)`;
  bez tovarny wait 30; jinak `vy 0`, wait 10, uhel na hrace
  (`0x72ee`/`0x65be`), homing `0x8530(0, −4, uhel)`, wait 30.
- `fp@(140)` zvysuje `0xb6ae` (tovarna po radku 84); `0xb6ba` (snizeni)
  nema v `AMPROG.OBJ` zadneho volajiciho — pisty pracuji i po zniceni
  tovarny. Prepis `g.inst1Factories`.

### INST1#11 (0x161c → 0xb810) — tovarna na tanky

- Zamek `0x5eda(6)`, `a2c6(INST1#11, 38, −63, HP 90, 2500 bodu, cost 20)`,
  `+376 = 0xb97c`, handler `0xb8ca` pro bit 0 (`0x653e`) a bity 3+4
  (`0x6564`), z 16, `0x9ae8(84)` (do radku 84 bez kolizi), `0xb6ae`;
  smycka: wait 100, `+276−−`, je-li `(+276 & 3) == 0` dite
  `0x6178(0x9eca)` = MEDTANK typ 3 na `y = fp@(3542) − 16`, `x = 236 +
  (0x883c & 63)`; 3× `0xb8a6` { anim `0xb8aa` INST1#13, #12, #11 perioda
  5 (drzi), zvuk `0x541e(x)`, paprsek `0x617a(0xb906)`, wait 40 }.
- **Paprsek `0xb906`:** `a2c6(INST1#4, 6, −63, HP 0, 0, cost 20)`, z 0,
  `y += 118`, `x += 1`, anim `0xb92a` perioda 1 #4,#5,#6,#6,#7,#7,#8,#8 +
  kill (8 tiku), wait 5 (`0x62b8`), trida 0, `0x9b70` do konce animace —
  smrtici jen prvnich 5 tiku.
- **Zasah `0xb8ca`:** HP−1; > 0 → zvuk `0x4e2e` + `0xa35a`; jinak skore
  `+362` obema zivym hracum, je-li `fp@(140) <= 1` `0x8852` (bily
  zablesk = SMART pulz), `0xa36a`. **Smrt `0xb97c`:** `x += 2`, `+276 =
  INST1#2`, dite `0x8992` (zapis znicene tovarny do mapy), 4× { `0x8876`
  na (0,0), (48,−48), (−48,−48), (24,−32), raw wait 20 } = 16 velkych
  vybuchu, `0x6288`. Prepis `factoryDeath` (booms se zpozdenym startem
  `t = −1 − 20·kolo`), `addDecal(INST1#2)`, `startWhiteFlash`.
- Simulace: zrozeni 10540 (x 110), aktivace radek 84 (tik +590), tank
  z (289, −16) v +690, 3 paprsky po 40 ticich, 90 zasahu → 16 vybuchu.

## GRASS (prepsano 2026-09-03; overeno simulaci `build/survey/grass/`)

### Animator uzel nemeni (zmereno)

`0x6c88` uklada snimek do bloku animatoru (`%a0@(18)`), nikoli do `+368`;
kolizni rozmery (`+500/+502`) prepisuje jen `0x6d7c`. **Uzel objektu tedy
po celou dobu drzi snimek z `a2c6`** (nebo z posledniho explicitniho
`0x6d7c`), i kdyz animace kresli jine snimky. `NODE_GRAPHIC` proto vzdy
nese `a2c6` snimek.

### VTOL (0x0023 → 0x8344)

- `a2c6(VTOL#0, 36, −16, HP 8, 35 bodu, cost 10)` (bez `0x8822`), anim
  `0x0835a` VTOL#0/#1 perioda 4 loop, `+328 z = 0` (`clrl`), pak
  `0x9afa(16 + (0x883c & 31))` = ceka na nahodny radek 16..47.
- Vzlet: `+397 &= ~1` (neprepisuje se), `0x65ae` = maska udalosti
  `+508 &= ~16` (rusi kontakt tridy 36), `0x6566` zapne bit 3 s vychozim
  `0xa362`, `+504 = 34` (smrtici kontakt); `+340 vz = 0.5` a smycka
  `0x839e` do `z >= 32` (cele slovo), pak `vz 0`.
- Let: anim `0x083b4` VTOL#2, #3, #4 perioda 8 a `end(0)` = drzi #4;
  `+348 ay = 4096/65536 = 0.0625 px/t²` (bez bitu 4, tedy mapove
  souradnice) — stroj se rozjizdi dolu; po `0x9afa(192)` jeden mireny
  kanon `0x95d2` a `0x62cc`.
- Simulace: tri kusy zrozeny v tiku 5972 (x 163/198/233, sy −16),
  kazdy vzletne na svem nahodnem radku (v tiku +220 byl jeden ve
  fazi 2, druhy ve fazi 1 se z 14, treti jeste na zemi), 8 zasahu = smrt.

### XEVIOUS#5 (0x0a2e → 0x791a) — rotujici disk

- PAM kresli XEVIOUS#5, ale korutina vola `a2c6(XEVIOUS#3, 34, −16,
  HP 0, 0 bodu, cost 13)`; `+367 |= 1` (bez stinu), `+328 z = 32`,
  handler bitu 0 = `0x7968` (jen zvuk `0x55b0` podle x — **neprepsan**),
  `+336 vy = 0.5` (mapove, na obrazovce 0.75 px/t), anim `0x0794c`
  XEVIOUS#3..#8 perioda 7 loop, `0x62cc`.
- HP 0 znamena, ze `a2c6` **neinstaluje zadny vychozi handler**
  (`0xa2fc beqs`), takze objekt nelze znicit; vlastni handler bitu 0 ale
  uzel drzi, takze bolt hrace na nem zanikne. Prepis: `s.boltPing`
  (rozsirena podminka `collectBulletEvent` pro spawny) a v dispatchi
  navrat bez poskozeni. Trida 34 = smrtici kontakt.

### XEVIOUS#9 (0x122e → 0x7ed8) — roj s bombami

- `0x7ed8`: devet kopii `0x6178`, mezi nimi rodic `y -= 3` (rucne
  napsana `0xa2a2`), tedy deset kusu po 3 px nad sebou; rodic pak
  propadne do stejneho kodu.
- Kazdy: `a2c6(XEVIOUS#9, 34, −48, HP 1, 20 bodu, cost 10)` + guard
  `0x8822`, `+367 |= 16` (obrazovka), `x += (0x883c & 127) − 64` s
  odrazem (`<= 32` → +64, `> 288` → −64), `z = 32`, `vy = 2`.
- Po `0x9afa(40)`: `vy = 1`; `x >= 160` → `vx = 3` a anim `0x07f5e`
  (#12, #11, #10, #9 perioda 4 loop), jinak `vx = −2` a anim `0x07f7a`
  (#10, #11, #12, #9); pak jedna bomba `0x6178(0x7f9a)` a `0x62cc`.
- **Bomba `0x7f9a`:** zvuk `0x4cf8` (neprepsan), `a2c6(BULLET#3, 6, −16,
  HP 0, 0 bodu, cost 3)`, `0x6d96` (nuluje zdedene rychlosti),
  `+367 |= 17` (bez stinu + obrazovka), `+364 = 0` (cull margin 0), anim
  `0x07fc6` BULLET#3/#4 perioda 4 loop, rychlost `+356 = 512` = 2 px/t
  na hrace (`0x72ee` + `0x65be` bez omezeni) s rozptylem
  `(0x883c & 31) − 16`, a v kazdem tiku `z = (slovo y) >> 1` (logicky
  posuv). Trida 6 s HP 0 = smrtici kontakt bez handleru, tedy stejny
  model jako kanonovy granat (bolt hrace ji neznici).
- Simulace: prvni kus zrozen v tiku 128 (x 201), deset kusu po ~24
  ticich, kazdy odhodi jednu bombu na radku 40.

### BOB se skryva pres +397 bit 7 (zmereno)

`+397` je bajt priznaku animacniho bloku (`+380 + 17`). `0x481a` (vlozeni
do BOB fronty) zacina `btst #7,%a0@(21)` a pri nastavenem bitu zaznam
**nevlozi**. Animacni skripty proto pouzivaji `andflag(128)` /
`orflag(128)` jako „zobraz" / „skryj" (napr. hlaven XEVIOUS#0). Prepis:
`h.hidden` v kompozitoru hazardu.

### TRILO (0x0822 → 0x826a)

- PAM kresli TRILO#4, korutina vola `a2c6(TRILO#0, 36, −16, HP 4,
  35 bodu, cost 10)`, `+397 |= 1`, `z = 0`.
- `0x9afa(8)` → `+336 vy = 0.5` (mapove) → `0x9afa(64)` → anim `0x082a6`
  TRILO#1..#4 perioda 8 s `end(0)` (drzi #4) → wait 20 → `+397 &= ~1`,
  `0x65ae` (maska `+508 &= ~16`), `0x6566` s `0xa362`, `+504 = 34`
  (smrtici kontakt) → `vz 0.5` do `z >= 32` → `vz 0`, `+356 = 0`.
- Lovecka smycka (`0x82f4`, kazdych 10 tiku): uhel na hrace
  (`0x7312` + `0x65be` s d2 = 0 = absolutne); **je-li vysledek 160..224
  (bajt `+359`, bez znamenka), prepise se na 64** — tvor nikdy nemiri
  primo vzhuru; pak `+358 += ±16` podle znamenka slova `0x883c`; je-li
  `+356 < 768`, `+356 += 48`; `0x65f2`. Rychlost tedy roste po 0.1875
  px/t az na 3 px/t.
- Simulace: zrozeni 3284 (x 308), vzlet od radku 64, v tiku +320 uhel
  151 pri rychlosti 1.12 px/t.

### XEVIOUS#0 (0x002e → 0xadf2) — letoun se skriptem drahy

- `a2c6(XEVIOUS#0, 36, −16, HP 30, 95 bodu, cost 13)` (trida 36 = **neni**
  smrtici kontakt), po `0x9afa(64)` vazana hlaven `0x6144(0xae88)` a
  skript drahy podle `+276` z PAM: typ 1 → `0xae68`, typ 2 → `0xae72`,
  jinak `0xae7e`. Rychlost `+356 = 128` = 0.5 px/t.
- Skript je pole dvojic **[uhel, delka/2]** (`0xae36`): `+359 = bajt`,
  `0x65f2`, dalsi bajt × 2 = `0x629c`; bajt 255 = konec (`0x6d96` +
  `0x62cc`). Typ 1: 127(314), 112(20), 96(20), 81(20), 65(508) a dale
  pokracuje daty typu 2: 128(78), 144(20), 159(20), 175(20), 190(200),
  konec. Typ 2 zacina az u 128. Typ 3: 192(96), 208(20), 224(20),
  240(20), 0(508) — jeho tabulka konci bez 0xff, ale objekt do te doby
  odleti z obrazu (prepis po poslednim zaznamu jen leti dal).
- **Hlaven `0xae88`:** `a2c6(XEVIOUS#1, 0x8000 = bez sweepu, 0, HP 0,
  0 bodu, cost 3)`, `0x6d96`, `+367 |= 13` (bez stinu, blika s rodicem,
  vazane dite), `+340 vz = 1` = ofset nad rodicem. Smycka: anim
  `0x0aeb0` `andflag(128)` #1, #2, #2, #1 perioda 4 `orflag(128)`
  (viditelna 16 tiku), wait 8, bomba `0x6178(0x7f9a)` (stejna jako u
  XEVIOUS#9), wait 100.
- Simulace: zrozeni 116 (x 253), aktivace na radku 64, typ 1 leti vlevo
  0.5 px/t s hlavni na hrbete.

### _PLAT#9/#10 (0x1242/0x1442 → 0xa3b2/0xa3b8) — plosina se ctyrmi urovnemi

- Vstupni bod urcuje typ: `0xa3b2` (z #9) dela `st +276` (bajt 0xff),
  `0xa3b8` (z #10) `sf +276` (0) — **hodnota typu z PAM se prepise**.
  Podle nej i grafika: `+276 != 0` → _PLAT#9, jinak #10.
- Plosina: `a2c6(_PLAT#9|#10, 36, −16, HP 0, 0 bodu, cost 5)` (HP 0 =
  `a2c6` neinstaluje handlery, tedy nezasazitelna), `+397 |= 1`,
  `0x9afa(16)`, `+364 = −16`; smycka: wait 100, vozidlo
  `0x6144(0xa462)` (typ se kopiruje do ditete), zvuk `0x5138` (stejny
  jako otevirani FLAME), 18× { yield, `x += typ ? +1 : −1` }, wait 100,
  18× { yield, `x -= …` }, pak ceka (`0x62d2`), dokud `+312` (dite)
  neni nula, a opakuje.
- **Vozidlo `0xa462`:** `a2c6(_PLAT#18|#17, 36, −16, HP 10, 60 bodu,
  cost 10)`, `+397 |= 1`, vez `0x6144(0xa4d6)`, `x = 284 | 36`
  (absolutne), `y -= 2`, wait 50, `vx = −0.5 | +0.5`, wait 190, `vx = 0`,
  `0x62cc`.
- **Vez `0xa4d6`:** `a2c6(_PLAT#19, 0x8000, −16, HP 0, 0 bodu, cost 4)`,
  `+397 |= 1`, `+367 |= 12` (blika s rodicem + vazane dite),
  `+332 vx = ±11` = pevny ofset; wait 300, pak smycka { anim `0x0a512`
  #20, #21, #22, #22, #21, #20, #19 perioda 8 (drzi #19), wait 24, zvuk
  `0x4d6a` (**neprepsan**), strela `0x617a(0xa548)`, wait 120 }.
- **Strela `0xa548`:** `a2c6(_PLAT#23, 6, −16, HP 0, 0 bodu, cost 3)`,
  `+367 |= 1`, `+364 = 0`, anim `0x0a568` #23, #24, #25, #24 perioda 1
  loop, rychlost `+356 = 256` = 1 px/t na hrace (`0x7312` + `0x65be`),
  `0x62cc`.
- Simulace: obe varianty zrozeny 5976 (x 53 typ 0, x 267 typ 1); vozidlo
  vyjizdi z x 36 (resp. 284) a za 190 tiku ujede 95 px, vez ho sleduje
  s ofsetem ∓11 a po 300 ticich strili kazdych ~150 tiku.

### DADA (0x0059 → 0x7a2c)

- `a2c6(DADA#0, 34, −48, HP 12, 70 bodu, cost 15)`, `+376 = 0x88ec`,
  `+328 z = 32`, `+336 vy = 1` (slovo). Po `0x9afa(0)`: `+344 ax =
  ±2048/65536 = ±0.03125` (kladne, kdyz `x <= 160`, jinak zaporne, tedy
  ke stredu — nastavi se **jednou**, takze stroj stred prejede) a
  `+367 |= 16` (obrazovka).
- Smycka: wait `(14 − fp@(182)) × 2` tiku, pak **dve** navadene strely
  `0x8530(−22, 20, 64)` a `0x8530(+22, 20, 64)` (d0/d1 jsou ofsety od
  objektu, d2 absolutni uhel — zmereno na `0x8530`).
- **Smrt `0x88ec`:** zvuk `0x4c3c`, `0x6d96`, pak 8× { dite `0x8952`
  posunute o aktualni rychlost, `+358 += 100`, `+356 += 1536`, `0x65f2`,
  raw wait 2 } — tentyz kod jako smrt hrace `0x88fc`, jen 8 chvostu a
  krok rychlosti 6 px/t. Prepis: `spawnPlayerBurst(..., 8, 0x600, z+1)`.
- Simulace: zrozeni 5448 (x 34), po radku 0 zrychluje vpravo, v tiku +80
  vx 1.28 px/t.

### _CORN#7 (0x0e41 → 0x820c)

- `+364 = −90` **jeste pred** `a2c6(_CORN#7, 36, −80, HP 0, 0 bodu,
  cost 25)`; `z = 0`, `0x65a4` (maska `+508 &= ~24`). Po `0x9afa(80)`:
  `+504 = 34` (smrtici kontakt), `+340 vz = 0.25`, zvuk `0x54ac`
  (**neprepsan**), smycka do `z >= 32`, pak `vz = 0`, `+348 ay =
  2048/65536` a `0x62cc` — vez se zvedne a odleti dolu.
- HP 0 = `a2c6` neinstaluje handlery, takze je nezasazitelna.
- Simulace: zrozeni 3404 (x 99, sy −80), zvedani od radku 80 (tik +640),
  z 32 v tiku +800, pak zrychluje dolu a v +1000 je za okrajem.

### JEEPHELI#23 (0x2e00 → 0xac6a) — druha SWAP plosina

- `a2c6(SWAP#0, 0, −16, HP 0, 0 bodu, cost 10)`, `+534 = −1`,
  `+397 |= 1`; po `0x9afa(32)` zapise `fp@(3550) = x`, `fp@(3552) = y`,
  vynuluje `fp@(3554)` a ceka na `fp@(3548)` (logika jeepu). Druha
  varianta teze plosiny je `0xacb6` (JEEPHELI#31, SWAP#1, globaly
  `fp@(3554)/(3556)`).

### JEEPHELI#43 (0x5600 → 0xad30) — pasmo stop pasu

- **Nema `a2c6`**: jen `0x5ee0` (rezervace grafiky JEEPHELI#40) a
  `0x9ac8(0)`, takze se nic nekresli. Po aktivaci nastavi
  `fp@(150) = y`, `fp@(152) = y − 600`, `fp@(154) = −1` a drzi je,
  dokud `fp@(3530) + 256 >= fp@(152)`; pak `fp@(154) = 0` a konci.
- Uvnitr pasma nechavaji stopy: **vez tanku** (`0xa000` v `0x9faa`,
  tedy MEDTANK i FLATTANK) kazdych 20 tiku a **jeep** (`0x9172`)
  kazde 3 tiky. Dite `0xad98` ma `+397 |= 65` (bit 6 = dekal do mapy),
  `+367 |= 1`, smerovou grafiku `0xa252` z tabulky `0xade2`
  (JEEPHELI#40..#43 po osmi sektorech uhlu, s uhlem **rodice**), a
  vykresli se do obou mapovych stran (`y -= 320` mezi dvema fieldy).
- Prepis: `g.trackZone`, dekal v `stepTankTurret` (jeep se nemodeluje).
  Simulace: pasmo 16959..16359, tank typ 3 (uhel 64) klade JEEPHELI#42
  kazdych 10 px.

### Revize GRASS (2026-09-03, Fable po Opusovi)

Vsechny konstanty sekce porovnany s `work/prog.txt`, sondy prehrany.
Opraveno: DADA pricitala skore dvakrat (vlastni vetev smrti opakovala
`releaseSpawnTask` + `awardScore`); animator VTOL (`0x0835a`) se
zastavil behem zdvihu a animator veze _PLAT (`0x0a512`) behem wait 120 —
animator bezi nezavisle na cekani korutiny; `+364` u _PLAT (−16 po
radku 16, `0xa3e4`) a u strely `0xa548` (0) nebylo modelovano; stopa
pasu u FLATTANK vznika z polohy veze (+4). Navic opraven DESERT: strela
vejce `0xa9a0` ma masku `+508 = 0`, takze na kontaktu s hracem nezanika
(kanonovy granat `0x9632` naopak zapina bity 3+4 s `0x6db4`).

Vychozi hodnoty zaznamu tasku (`0x61ee..0x6238`): `+364 = −64`,
`+538 = 0x6db4`, `+542 = +534 = −1`, `+376 = 0x894a`, vsechny handlery
`+510..+530 = 0x6288`, `+508 = 0` (zadna povolena udalost), `+367 = 0`.
Objekt s HP 0 proto nereaguje na nic, dokud korutina sama nepovoli bity
(`0x653e`, `0x654a`, `0x6564`, `0x6566`).

Zname a prijate odchylky: vazane deti (hlaven XEVIOUS#0, vez _PLAT) se
polohuji v kroku hazardu, tedy o tik za rodicem (0.5 px pri 0.5 px/t).

## RIVER (prepsano 2026-09-03; overeno simulaci `build/survey/river/`)

### SKYEYEA (0x0009 → 0x75f8)

- Stejna formace jako SKYEYEB: `x = −16`, `+276 = 7`,
  `0xa2a2(−40, 0, 6, −1)` = sest kusu s poctem otacek 7..2.
- `a2c6(SKYEYEA#0, 34, **192**, HP 1, 30 bodu, cost 10)` — aktivace az na
  radku 192, tedy u spodniho okraje; `+538 = −1` (bez cullu),
  `+367 |= 16` (obrazovka), `z = 32`.
- `0x72a6` (poloha hrace 1): je-li **y hrace >= vlastniho** (bez
  znamenka), objekt prevezme jeho radek (`0x7638`) — nalet je tedy vzdy
  po rade hrace. Je-li **x hrace >= 160**, krok `+278 = −16` a uhel 0;
  jinak zrcadlo `x = 320 − x`, krok `+16` a uhel 128. Oproti SKYEYEB
  (`0x76ec`) jsou kroky prohozene, takze se toci na opacnou stranu.
- Rychlost `+356 = 768` = 3 px/t (SKYEYEB ma 896). Snimek se bere
  tabulkou `0x76cc` pres `0xa268` (16 polozek, index
  `((uhel + 8) & 240) >> 4`): polozka 0 = #8, polozky 8..15 = #0..#7;
  polozky 1..7 (`0x2200`) jsou pro pouzite uhly nedosazitelne.
  **`0x6d7c` meni i kolizni uzel**, proto `nodeKey` skyeyea0..8.
- Nalet konci, jakmile `144 < x < 176`; pak `+538 = 0`, wait 10 a
  `+276`× { wait 4, uhel += krok, `0x65f2`, novy snimek }. Na konci
  **jen pri obtiznosti >= 4** mireny kanon `0x95d2` (`0x76b0`), pak
  `0x62cc`.
- Simulace: sest kusu zrozeno v tiku 968 na radku hrace (192), nalet
  zprava 3 px/t, spirala po 4 ticich s uhly 144..240 a snimky #1..#7.

### HOVER (0x082a → 0xb466)

- `a2c6(HOVER#0, 36, −48, HP 10, 90 bodu, cost 15)`, `+376 = 0x88ec`
  (osm chvostu jako DADA), `+328 z = 2`, `+367 |= 1` (bez stinu), vazana
  sukne `0x6144(0xb512)`.
- Typ 1 (jediny v mape): `+336 vy = 1`, `+332 vx = +0.5`, a je-li
  `x >= 160`, `negl` → −0.5, tedy vzdy ke stredu.
- Po `0x9afa(100)`: anim `0x0b4c4` HOVER#1..#5 perioda 5 s `end(0)`
  (drzi #5), `+348 ay = −2048/65536` (brzdi klesani), wait 23, raketa
  `0x6178(0xb532)`, wait 25, `ay = +4096/65536`, wait 50, `vx = 0`,
  `ay = 0`, `0x62cc`.
- **Sukne `0xb512`:** `a2c6(HOVER#6, 36, −48, HP 0, 0 bodu, cost 0)`,
  `+367 |= 12` (blika s rodicem, vazane dite s nulovym ofsetem, protoze
  vznika jeste pred nastavenim rychlosti).
- **Raketa `0xb532`:** `a2c6(HOVER#7, 34, −48, HP 10, 50 bodu, cost 10)`,
  `+364 = −8`, `0x6d96`, `+340 vz = 1` do `z >= 32`, pak `vz = 0` a
  `+336 vy = 0.25`; po `0x9afa(224)` smycka `0xb57c`: uhel z bajtu
  `+276` (kladny bajt se neguje, zaporny se pouzije primo → 0, 240, 224,
  … 144, 128, 144, …), jeden rovny granat `0x95ca` a `0x629a` = wait 1.
  Strili tedy **kazdy tik** dokola, dokud ji nekdo nezastreli.
- Simulace: zrozeni 4048 (x 79.5), raketa v tiku +150, palba od radku
  224 s krokem uhlu 16 za tik.

### LAKESUB (0x0029 → 0xb34a) — ponorka

- `a2c6(LAKESUB#0, 36, 64, HP 6, 80 bodu, cost 17)`, anim `0x0b360`
  (perioda 6: #1, #2, #3, #4; pak perioda 12 smycka #5, #4) = vynoreni.
- Wait 40, vez `0x614a(0xb3a8)`, wait 70, anim `0x0b392` (perioda 6:
  #4, #3, #2, #1, **kill(0)**) = ponor. `0x8800` v animaci vola
  `fp@(-1414)`, tedy tiche zabiti bez skore a bez vybuchu.
- **Vez `0xb3a8`:** `a2c6(LAKESUB#0, 0, 0, HP 0, 0 bodu, cost 5)`,
  `0x6d96`, `+367 |= 13` (bez stinu, blika s rodicem, vazane dite),
  `+340 vz = 1` = ofset nad rodicem; anim `0x0b3ce` (perioda 6: #7, #8,
  #9, #10, #10, #9, #8, #7, #6, kill) — vez zije 54 tiku. Po wait 26
  zamiri na hrace (`0x7312` + `0x65be`) a v **jednom tiku** vypali pet
  strel `0x6178(0xb41a)` s krokem uhlu 51.
- **Strela `0xb41a`:** `a2c6(LAKESUB#11, 6, −16, HP 0, 0 bodu, cost 1)`,
  `+364 = 0`, `+356 = 384` = 1.5 px/t ve zdedenem uhlu, `z = 0`; v
  kazdem tiku, kdy je cele slovo `z` nulove: `+340 vz = 2`,
  `+352 az = −6144/65536` a cakanec `0x6178(0x9358)` — strela se odrazi
  po hladine (parabola ~43 tiku, vrchol z 21).
- Simulace: zrozeni 3980 na radku 64, vez v tiku +40, pet strel v tiku
  +66, ponor a tichy zanik v +180; odrazy s cakanci po ~43 ticich.

### JUNTANK#1 (0x022b → 0xa0d2) — tank s vazanou vezi

- `a2c6(JUNTANK#1, 36, −48, HP 15, 90 bodu, cost 18)`, `+397 |= 1`,
  `+376 = 0x88ec` (osm chvostu), vez `0x6144(0xa12e)`, `+336 vy = 0.25`
  a `+276 = 384`. Smycka `0xa108`: **je-li `+312` (dite) nula, `vy = 0`**
  — zniceni veze tank zastavi; jinak jede, dokud `+276` neklesne pod
  nulu, pak `vy = 0` a `0x62cc`.
- **Vez `0xa12e`:** `a2c6(JUNTANK#20, 36, −48, HP 12, 90 bodu, cost 10)`,
  `+538 = −1` (bez cullu), `+367 |= 13` (bez stinu, blika s rodicem,
  vazane dite s ofsetem `+332/+336/+340 = (−2, −18, +1)`), rychlost 0,
  uhel 64, `+276 = 100`. Kazdy tik `−−+276`; pri nule rovny granat
  `0x95ca` a `+276 = 50`; je-li `+276 <= 10`, mireni na hrace
  (`0x7312` + `0x65be` s limitem 16) a novy smerovy snimek `0xa27c`
  (zaklad JUNTANK#20, osm smeru → #20..#27, meni i uzel).
- Simulace: zrozeni 10260, jizda 0.25 px/t, prvni granat v tiku +100,
  dalsi po 50 ticich; po 384 ticich stoji.

### JUNTANK#2 (0x042b → 0xa592) — poklop s dronem

- `a2c6(JUNTANK#2, **0**, −32, HP 0, 0 bodu, cost 5)` — trida 0, tedy
  bez kolizi a nezasazitelny; `+397 |= 1`. Po `0x9afa(48)` smycka:
  anim `0x0a5b4` (perioda 4, #3..#8, drzi #8) = otevreni, wait 30, dron
  `0x6178(0xa60e)`, wait 50, anim `0x0a5e0` (#7..#2) = zavreni, wait 100;
  dalsi kolo jen dokud je `sy <= 192` (`0xa5f8`), jinak `0x62cc`.
- **Dron `0xa60e`:** `a2c6(JUNTANK#12, 34, −32, HP 4, 70 bodu, cost 10)`,
  `+364 = −10`, anim `0x0a630` (perioda 8: #9, #10, #11, #14, drzi #14),
  `+340 vz = 1` do `z >= 32`, pak `+397 &= ~1`, `vz = 0`, uhel 64 a
  rychlost `+356 = 768` = 3 px/t. Smycka `0xa672`: mireni na hrace s
  limitem **33** (`0x65be`), pak **zaokrouhleni uhlu na osminy**
  (`(uhel + 16) & 224`), `0x65f2`, smerovy snimek `0xa27c` (zaklad
  JUNTANK#12 → #12..#19) a `0x629c(+276)`, kde `+276` po kazdem kole
  roste o 1 (10, 11, 12, …) — korekce kurzu se postupne zpomaluji.
- Simulace: zrozeni 8744, otevreni na radku 48 (tik +330), dron v +360,
  zavreni v +400, dalsi kolo po 100 ticich.

### LAKEGUN#0 / #7 (0x0028 → 0xb26c, 0x0e28 → 0xb2dc) — pobrezni dela

- Obe varianty: `a2c6(LAKEGUN#0 | #7, 36, **100**, HP 4, 75 bodu,
  cost 10)` — aktivace az na radku 100; `+374 = 5` (dekal EXPL1#0).
- `#0` (`0xb26c`): anim `0x0b288` (perioda 6, #1..#6, drzi #6) = otevreni,
  wait 50, pak `+276 = 6`× { wait 30, navadena strela
  `0x8530(−8, 0, **128**)` = doleva }, pak anim `0x0b2c4` (#5..#1,
  **kill(0)**) — delo se zavre a tise zanikne bez skore.
- `#7` (`0xb2dc`): zrcadlo — snimky #8..#13, strela `0x8530(+8, 0, 0)`
  doprava, zaviraci anim `0x0b332` (#12..#8, kill).
- Simulace: zrozeni 4600 na radku 100, prvni strela v tiku +80, dalsi po
  30 ticich, po sesti se delo zavira (tik +260).

### INST2#2 (0x042c → 0xb9da) — instalace s paprskem a vlnami

- Zamek `0x5eda(6)` (nemodeluje se), `a2c6(INST2#2, 36, −32, HP 50,
  **2000 bodu**, cost 40), pak **`0x658a` = `+508 &= ~1`** — dokud je
  instalace zavrena, **bit 0 udalosti je vypnuty a bolt hrace ji
  nezasahne**; `+376 = 0x8876` (velky vybuch).
- `0x9afa(83)` pro typ 1, jinak `0x9afa(57)`; pak `0xb6ae`
  (`fp@(140)++`, tentyz citac jako tovarna INST1#11) a wait 100.
- Smycka `0xba1a`: dite `0x6178(0x8008)` = **spoustec vln**, anim
  `0x0ba26` (perioda 5, INST2#3..#6, drzi #6) = otevreni, wait 20,
  `0x653e(0xb8ca)` = **zapne bit 0 se stejnym handlerem jako tovarna**
  (2000 bodu, bily zablesk pri `fp@(140) <= 1`), wait 50; pak vnitrni
  smycka: zvuk `0x541e` (**neprepsan**), paprsek `0x617a(0xba9e)`,
  wait 20 a `0x883c` — **kladne slovo znamena dalsi paprsek**, jinak
  anim `0x0ba6e` (#5..#2) = zavreni, `0x658a` (opet nezranitelna) a
  wait `(4 − fp@(140)) × 32 + 20`.
- **Paprsek `0xba9e`:** `a2c6(INST2#8, 6, −63, HP 0, 0 bodu, cost 20)`,
  `+367 |= 1`, `z = 1`, `y += 105`, anim `0x0bac6` (perioda 1: #8..#12,
  kill), po `0x62b8(5)` trida 0 a `0x9b70` — smrtici jen prvnich pet
  tiku (stejny model jako paprsek tovarny `0xb906`).
- **Spoustec vln `0x8008`:** nema `a2c6`, tedy se nekresli;
  `clrw fp@(146)`, `0x6d96`, `y = fp@(3542) − 32`, `+276 = 1` a
  `(4 − fp@(140)) × 4`× { dite `0x8066`, **raw** wait 10 }. Protoze
  `fp@(146) = 0`, vola kazdy potomek vlastni `0x813a`, takze ma vlastni
  nahodne x i vx; `+276 = 1` mu da anim `0x080b0`
  (#2, #3, #2, #4, #2, #5, #2, #6) — je to tedy bezny FODDERA letec,
  jen po jednom kazdych 10 tiku.
- Simulace: tri instalace zrozeny 13980, aktivace na radcich 83/57,
  prvni otevreni v tiku +560, paprsek v +630 (x 157, sy 230), zavreni a
  dalsi kolo; 50 zasahu = smrt, bily zablesk jen pri posledni.

### INST2#0 (0x002c → 0xbae8) — bombardujici vez

- `a2c6(INST2#0, **32**, −16, HP 80, 100 bodu, cost 10)` — trida 32
  nema bit 1 ani 2, takze neni smrtici na dotek a kontakt ji nepoškodi;
  bolt ano (HP != 0 → `a2c6` nainstaluje `0xa362`).
- Smycka `0xbafa`: dokud `fp@(140) != 0` (tedy dokud zije aspon jedna
  instalace INST2#2), pet bomb `0x6178(0x7f9a)` — **tataz bomba jako u
  XEVIOUS#9** — po sedmi ticich; pak wait `fp@(140) × 128 + 1` a znovu.
- Simulace: dve veze zrozeny 13956; palba zacne, jakmile se instalace
  zaregistruji (tik ~14500), bomby miri na hrace s rozptylem ±16.
