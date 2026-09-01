# TOWN audit — co v prepisu nesedi s originalem (2026-08-30)

Hloubkovy pruzkum k hlaseni z hrani: „chovani objektu, hlavniho
nepritele a ochrannych bublin neni jako v originale". Nic z toho neni
odhad: kazda polozka nese adresu v `AMPROG.OBJ` (`work/prog.txt`) a
byla prectena z kodu.

**Stav 2026-08-31**: cely P0 (sekce 6, body 1–6) je prepsany, plus
rozjezd TOKENu z `0x96d8`. Renderer, HUD, zvukovy model a N+1 kolizni
scheduler doplnil `a1bfaa5` (Codex); zbyle mezery vede `GAPS.md`.
Kolizni jadro bylo docteno — sweep `0x6ec2` v `AMPROG.OBJ` (bezi jako
task s prioritou `0xffff`): **event word objektu = OR koliznich trid
vseho, ceho se dotkl**; zadna parovaci tabulka neexistuje. Sekce 2.1
tim prestava byt odvozena; jedina oprava je, ze vrtulnik posloucha jen
udalost 1 (`0x654c` instaluje pouze `+518`; `0x654a` je vedlejsi vstup,
ktery pridava i `+526` — ten hrac nevola). Na tabulku „kdo zabije
vrtulnik" to nema vliv.

## 0. Vizualni addendum — baseline, objektova paleta a COLOR07 (2026-09-01)

Uvodni PAM prikazy neposouvaji jen paletu: pred prvnim nepaletovym zaznamem
spotrebuji 96 y pixelu. `parsePam.lead` je proto pro TOWN 96 a start
viewportu je `3345 - 96 = 3249`, nikoli drivejsich 3345. Kontrolni snimek
`t17` uz odpovida `row=3229`, protoze od startu probehlo dalsich 20 px
scrollu.

Pixel-fit proti originalu dal pro TOWN COLOR00-09 objektu stabilni canvas
RGB12 radu:

`000 333 465 598 765 666 9A9 800 ED6 EEE`

Je aplikovana na vsech 13 TOWN PAM checkpointech, zatimco COLOR10-15 dal
nesou rasterovou paletu terenu. Jde o fitted kompenzaci canvas rendereru
z JEEPHELI, YELLOW, MEDTANK a GOOSE pixelu, **nikoli o dukaz konkretniho
obsahu nativnich HW registru**. Scope je zamerne jen TOWN; pro ostatni
levely se bez vlastniho mereni nic neodvozuje.

Commit `abc853e` prinesl spravny prvni fit a `lead`, ale jeho propagace
ukoncila override indexu, jakmile se raw PAM hodnota zmenila. Od `y=104`
tak COLOR00-09 tvorila smisenou paletu; v pozdnim checkpointu byly mimo
jine hodnoty `555/687/7BA/987/BCB/B30`, ktere nesedi GOOSE. Stabilni rada
je ted aplikovana i tam. Dlouhy vizualni audit to overil na `t100`,
`row=2199`, a `t130`, `row=1831`; druhy rez obsahuje GOOSE telo a casti
`#5/#6/#7/#10`, jejichz indexy konzistentne mapuji na barvy originalu.

Jedina casova vyjimka je nativni COLOR07 writer `0x2b3e..0x2b5a`.
Z aktualniho `g.tick` vezme `phase = (g.tick >>> 2) & 15`, v druhe pulce
ji zrcadli a zapise cervenou slozku `8 + (phase & 7)`. Vznikne 64-VBL
sekvence `8,9,A,B,C,D,E,F,F,E,D,C,B,A,9,8`, kazda hodnota po ctyrech
VBL. Gate z `0x28fe` zapis nepusti pri black fadu, takze se pouzije
standardne zcerna paleta; pri nulove cerne jde zapis primo do COLOR07 a
obchazi white fade. Runtime pouziva aktualni schedulerovy `g.tick`, ne
vedlejsi render-frame citac.

`tools/compare.py` meri nejen cely snimek, ale z trojice renderu
`whole`, `withoutHeli`, `terrain` odvodi disjunktni masky HELI (telo se
stinem), HUD a zbytek terenu. Vsechny varianty maji stejny tik a prvni-pass
stav, takze tvorba masky neposune hru. Startovni mereni pri `t=17`,
`row=3229` a toleranci 24/kanal je: **whole 22.5 %, terrain 21.3 %,
HUD 100.0 %, HELI 99.7 %**. HUD se po pouziti zmereneho prevodu skutecnych
registrovych slov do capture profilu shoduje ve vsech 639 pixelech masky;
opaque COLOR16 soucasne zustava oddeleny od blikajicich COLOR17-31. Drobny
zbytek HELI tvori dynamicky COLOR07 a profil prevodu, nikoli anchor nebo
stin.

## 1. Odpovedi na tri hlaseni z hrani

### 1.1 „Ochranna bublina me v prepisu zabije, v originale chrani"

Hlasena bublina **neni bonusovy TOKEN**. Je to **jadro miny**
(`MINE#9/#10`, ruzovy vir, korutina `0x9860`), ktere vyleti z miny po
zasahu. V originale je to **sebratelny stit**:

- jadro ma kolizni tridu **32** (`0x9864`), tj. jen „sestrelitelne";
  nema bit 1, takze do vrtulniku **nenarazi smrtelne**
- na kontakt s hracem ma vlastni handler `0x98c4` (instalovan pres
  `0x6564` do slotu `+514` i `+522`): kdyz hrac stit nema
  (`+106 == 0`), nastavi `+106 = -1`, pocka 10 snimku a jadro zmizi
- hracova smycka `0x92a0` pak pri `+106 < 0` zalozi **orb** `0x98f2`
  jako potomka hrace a nastavi `+106 = 500` tiku (`0x92c0`–`0x92cc`)
- orb: `MINE#9`/`MINE#10` stridave kazdy tik, `vz = ±2` (pohupuje se),
  sleduje hrace (bit 3 v `+367`), nema stin (bit 0), je imunni vuci
  smart bombe (`st +534`); zanikne, jakmile `+106` klesne na 0
  (`0x9940`)
- po dobu stitu se ochrana `+108` drzi na 100 (`0x92ac`) a po vyprseni
  stitu jeste 100 tiku dobiha — celkem **~600 tiku = 12 s**
- ma-li hrac stit uz aktivni a sebere dalsi jadro, misto stitu prijde
  **smart bomba** (`0x98ec` → `0x8852`, viz 2.3)
- sestreleni jadra (10 HP, `0x98b4`) da 30 bodu a **taky** spusti
  smart bombu

V `game.html` je jadro `minecore` v poli `hazards` a kolize s hracem
ho zabije (`step()`, blok „kolize hrace"). To je presne hlaseny rozdil.

### 1.2 „Hlavni nepritel — velka lod, ktera se par krat za level sklada"

V mape TOWN je **jediny** GOOSE (`ry 1284, x 158`, `build/spawns.json`;
`docs/OBJECTS.md`). Jeho korutina `0xc78a` konci bud smrti, nebo
odletem po 2000 ticich — **nevraci se**. Vicekrat za hru se GOOSE
sklada v dalsich urovnich (DESERT 4×, ICE 3×, SCIFI 2×, GRASS/RIVER
1×). V TOWN tedy prileti jednou, v 31 % urovne.

Co u nej v prepisu chybi nebo nesedi — cele v sekci 4.

### 1.3 „Chovani objektu a nepratel neni stejne"

Nejvetsi merene rozdily (podrobne v sekci 3 a 6):

1. **vrtulnik v originale nenarazi do pozemnich objektu** (mina, telo
   PROXMINE, vlak, plamen, POPUP, veze, tanky); prepis ho na mine,
   PROXMINE, vlaku a plameni zabiji
2. rychlost hrace je **3 px/tik** (`0x9476`: `+356 = 768`), prepis 2.2
3. **smart bomba** (bily zablesk) v originale **znici vsechny
   zranitelne objekty na obrazovce**; prepis ji nekresli ani nevyhodnocuje
4. **navadena strela je sestrelitelna** (1 HP, 7 bodu, `0x8578`); v
   prepisu strely hrace navadene strely ignoruji
5. kazdy zasah nepritele v originale **blikne bile** (hit flash,
   `0xa35a`) — v prepisu nic

## 2. Nove prectene mechaniky jadra (plati pro vsechny objekty)

### 2.1 Kolizni trida `+504` a sloty udalosti

`0xa2c6` d1 se uklada do `+504` (`0x6dce` → zaznam `+488`, slovo
`+16`). Bity tridy rozhoduji, ktere handlery `a2c6` nainstaluje
(`0xa2fe`–`0xa31e`) — **jen kdyz HP ≠ 0**:

| bit tridy | a2c6 instaluje | udalost (slot) | vyznam (potvrzeno sweep `0x6ec2`) |
|---|---|---|---|
| 5 (32) | `0xa362` do `+510` | bit 0 | sestrelitelne strelou hrace |
| 1 (2) | `0xa362` do `+514` | bit 3 | vzdusny objekt: kontakt s vrtulnikem |
| 2 (4) | `0xa362` do `+522` | bit 4 | pozemni objekt: kontakt s jeepem |

`0xa362` = damage handler: `−1 HP`, pri ≤0 smrt `0xa36a`, jinak zvuk
`0x5070(x)` a **hit-flash bit 1 v `+367`** (`0xa35a`).

Hrac: vrtulnik `0x9410` ma tridu `0x48` (bity 3, 6 = P1), jeep `0x9090`
tridu `0x50` (bity 4, 6) a pri skoku prepina na `0x48`. Vrtulnik
instaluje smrt `0x9306` do udalosti 1 i 2 (`0x654c`); jeep do udalosti
2 normalne a do udalosti 1 pri skoku. Tridy nepratel v TOWN:

| objekt (a2c6) | trida | HP | body | cost | zabije vrtulnik? |
|---|---|---|---|---|---|
| FODDERA `0x8080` | 34 | 1 | 12 | 10 | ano |
| YELLOW `0x86da` | 34 | (d3 jinde) | 35 | 10 | ano |
| BIRD `0x8648` | 34 | 2 | 55 | 10 | ano |
| MILL `0x79e2` | 34 | 10 | 70 | 15 | ano |
| GOOSE telo `0xc7ae` → `0xc854` | 0 → 34 | 25 | 0 | 100 | ano (od `0xc854`) |
| GOOSE casti `0xca26` | 34 | 0 | 0 | 10 | ano, nezranitelne |
| GOOSE pod `0xcabe` | 34 | 0 | 0 | 10 | ano, nezranitelne |
| HOMING `0x8578` | 38 | 1 | 7 | 5 | ano, **sestrelitelna** |
| PROXMINE strepy `0xaaac` | 38 | 1 | 5 | 5 | ano |
| kanonovy granat `0x7fb0`/`0x960e` | 6 | 0 | 0 | 3 | ano, nesestrelitelny |
| PROXMINE telo `0xa9f8` | 36 | 4 | 30 | 10 | **ne** |
| MINE `0x9b24` | 36 | 10 | 25 | 7 | **ne** |
| MINE jadro `0x986e` | 32 | 10 | 30 | 5 | **ne** (stit, 1.1) |
| TRAIN lokomotiva `0x9b8c` / vagon `0x9c32` | 36 | 10 / 2 | 75 / 50 | 15 | **ne** |
| FLAME `0xab20` / emitter `0xab86` | 36 | 3 / 0 | 40 / 0 | 10 / 1 | **ne** |
| FLAME puff `0xabe6` | 4 | 0 | 0 | 10 | **ne**, ani sestrelitelny |
| POPUP `0xa6c6` | 36 | 3 | 70 | 14 | **ne** |
| ROTOBASE `0x995c` | 36 | 4 | 35 | 10 | **ne** |
| CAMOGUN `0xac20` | 36 | 2 | 40 | 10 | **ne** |
| MEDTANK `0x9eec` | 32 | (d3 jinde) | 50 | 10 | **ne** |
| MEDTANK vez `0x9fba` | 0x8000 | 0 | 0 | 4 | ne |
| PLOP `0x8600` | 0x8000 | 0 | 0 | 1 | ne |
| TOKEN `0x96e6` | 32 | 0 | 0 | 5 | ne (sebrani `+514`) |

Sloupec „zabije vrtulnik" je potvrzeny sweep rutinou `0x6ec2`
(seznam serazeny podle x, zaznamy `+488`: `+8/+10` pozice, `+12/+14`
pulrozmery, `+16` trida, `+18` event word): pro kazdou dvojici
prekryvajicich se zaznamu se **trida jednoho ORne do event wordu
druheho** (`orw d7,a1@(18)` / `orw a1@(16),d6`); zaporna trida
(`0x8000`) dvojici nezaklada. Udalost = trida protejsku: vrtulnik
(trida `0x48`) posloucha bit 1 (`0x654c` → `+518`), jeep bit 2
(`0x6558` → `+526`), pri skoku bit 1; nepratele posluchaji bit 0
(strela hrace), bit 3 (trida vrtulniku) a bit 4 (trida jeepu); bity
6/7 nesou identitu hrace pro pripis bodu (`0xa36a`). Vyhodnoceni je
odlozene do VBL N+1 — viz `GAPS.md` sekce 4.

### 2.2 Tri slotove ukazatele `+534` / `+538` / `+542`

Vsechny tri jsou longy s ukazatelem na rutinu; `st` na prvni bajt je
udela zaporne = **vypnuto**, `sf` zase zapne. Housekeeping `0x6458`–`0x64b4`:

| slot | kdy se vola | vychozi | vyznam |
|---|---|---|---|
| `+542` | kazdy tik, kdyz `+308 == 0` (rodic zemrel; `0x60e0` ho nuluje) | `0x6144` da `0x6db4` = zabij se; `0x617a` da −1 | **sirotci handler**: potomci umiraji s rodicem, pokud si nenastavi jinak (TRAIN vagony `0x9c44` −1, GOOSE pod `0xa36a` = exploduje) |
| `+534` | kazdy tik, kdyz `fp@(169)` (smart bomba bezi) | `a2c6` na `0xa326` da `0xa36a` | **smart-bomb handler**: objekt zemre s body; `st +534` = imunita |
| `+538` | kazdy tik, kdyz je objekt mimo obraz o vic nez `−(+364)` | `0x617a` da `0x6db4` | **cull mimo obraz**; `st +538` = neculovat |

`+364` (vychozi −64) je tedy **okraj culovani**, ne priorita kresleni
(`0x6486`–`0x64ae`: `sx <= m`, `sx >= 320−m`, `sy <= m`, `sy >= 256−m`).
Objekty si ho meni (`0x820c` −90, `0x8410` −16, `clrw` = 0).

### 2.3 Smart bomba `0x8852` / `0x885a`

`0x8852` pouze zalozi priority100 korutinu; az `0x885a` na svem strictnim
creation-FIFO startu provede zvuk `0x4cb2`, `st fp@(169)`, `fp@(11166) = 256`
(plna bila), ceka 50 snimku, `sf fp@(169)`. Po tech 50 snimku kazdy
objekt s aktivnim `+534` zemre pres `0xa36a` (i s body). Imunni v TOWN:
GOOSE telo, casti i pod, TOKEN, orb stitu, hracova exploze.

TOKEN typ4 pred nim v tomtez pickup callbacku zalozi vlastni sound child
`0x564c`. Proto je nativni poradi prvni TOKEN nota a az potom ctyri SMART
requesty; nejpozdejsi SMART vrstva muze tuto notu preemptovat.

Doznivani bile: `fp@(11168)` se za hry nikde nezapisuje; posledni
zapisy jsou v uvodni sekvenci (`0xc9a`, `0x1028`: **−4**). Bila tedy
klesa o 4 za snimek = 64 snimku. Tim se uzavira otazka z `GAPS.md`.

Spousteci mista: TOKEN typ 4 (`0x985a`), sestreleni jadra miny
(`0x98ba`), sebrani jadra se stitem (`0x98ec`).

### 2.4 Hit flash

`0xa35a`: `orib #2,+367`. `0x63a4`: bit 1 → bit 4 v kreslicim zaznamu
(`+421`); housekeeping ho na `0x6452` kazdy tik maze. Objekt tedy
**jeden snimek po zasahu** kresli s jinym mintermem (bit 4 → `0x417c`).
Bit 2 v `+367` = „blikni, kdyz blikne rodic" (`0x63ac`).

### 2.5 Dekaly do mapy `0x898c`

Pri smrti (`0xa398`): je-li `+374 ≠ 0`, zalozi se `0x898c` s grafikou
`+374`, flagy `+397` bity 0 a 6 (bit 6 = kresli do mapove bitmapy
`fp@(264)`, `0x3eb8`), jeden snimek, pak zmizi. V TOWN: MINE nechava
`MINE#8` (`0x9b28`), MEDTANK (`0x9e28`, `0x9e78`, `0x9ef0`), POPUP
(`0xa6d6`), PROXMINE (`0xaa0a`), FLAME (`0xab30`) nechavaji
`EXPL1#0` (slovo 5). `game.html` ma `addDecal` jen pro MINE#8 a jedno
misto s EXPL1#0.

### 2.6 Refcount grafickych souboru `0x5eda` / `0x5efc`

Inline slovo za `bsr` je graficke slovo, z nej `& 511` = soubor.
`0x5eda` zvysi citac a **ceka**, dokud neni nacteno; `0x5efc` snizi.
Proto boss na `0xc78e` pina `TOKEN.LIN` (0x18) a na `0xc93c` ho pousti;
exploze pinuji EXPL1/EXPL2, hrac JEEPHELI. `a2c6` pina `+368` a `0xa336`
pousti.

### 2.7 Kontrolni soucet v bossovi (`0xc93c`–`0xc96c`)

`GAPS.md` vedl smycku `0xc950` jako „bodovy soucet". Neni to skore:
`lea 0xc78a; addal #-51082` = zacatek programu (0xc78a = 51082),
`d1 = 0x6ac0` → secte **27 329 slov** programu (yield kazdych 256) a
vysledek **pricte k `fp@(3560)`**, coz je ukazatel na buffer mapy
(`0x3826`). Anti-tamper: pri nezmenenem programu ma byt soucet 0.
Nad `SWIVFIX` je soucet `0x47e9`; jestli to crack nekde kompenzuje,
neni prectene. Pro prepis: **boss nedava zadne body** (`d4 = 0` na
`0xc7aa`), body jsou jen z TOKENu.

## 3. Hrac — vrtulnik `0x9410` (ne `0x9090`, to je jeep)

`0x7156`: P1 ma `+56 = 1` → `0x9410`; `+56 = 0` → jeep `0x9090`.

| vec | original | `game.html` |
|---|---|---|
| rychlost | **3 px/t** (`0x9476`) | 2.2 |
| pozice | `0x9046`: x 160, y scroll+192, hleda volne misto sondou `0x3dd4` po 8 px | 160 / 200 |
| clamp | x 4..316, y scroll+4..scroll+248 (`0x954c`) | 12..308 / 16..240 |
| snimky | `JEEPHELI#0..4` period **1** (`0x945a`), nezavisle na smeru | 1..4 po 2 ticich |
| vyska | `z = 32` (`0x941a`) → stin `(x+16, y+32)` (`0x6364`) | stin `(+16,+22)` |
| ochrana po spawnu | `+108 = 200` tiku (`0x9424`) | 120 |
| blikani ochrany | bit 3 `+108` → hit-flash (`0x92e4`): 8 tiku bile / 8 normalne | `inv > 40` bile, pak `tick & 4` |
| smrt | udalost 1/2 → `0x9306`: bez ochrany i stitu → exploze `0x88fc` (16 EXPL1 ve spirale po 2 ticich) | ano |
| respawn | citac zivotu `+68` (−4/zivot, start −16 = 4), cekani **100 snimku** (`0x714e`) | 1200 ms |
| start zbrane | `+100 = 2`, `+98 = 12` (`0x6fde`); pri spawnu tabulka `0x70c0` podle `+102/5` → `+98 = 11` | 1 strela |
| pocet strel | `= +100` (`0x8ad0`–`0x8b1e`: `subq #1` + `dbf`) → **2** na start | 1 |
| zbran | potomek `0x939c`: uhel 192, pali na bit 5 vstupu pres `0x8aa0` | — |
| extra zivot | 10 000, pak +30 000 (`0x7084`, `0x7116`) | shodne |
| stit | sekce 1.1 | chybi |

Tabulka `0x70c0` se aplikuje **jen pri (re)spawnu** (`0x70c8`):
`+100 = max(+100, tabulka)`, `+98 = tabulka`. Bonusy 2/4 prepisuji
`+98` primo a plati do dalsiho spawnu. Tim se uzavira druha otazka z
`GAPS.md` k TOKENu.

Poznamka: `BEHAVIORS.md` uvadi „start 1 strela (z videa)". Kod rika 2
(sude sily = pary `(−2,−4)(2,−4)`, ctyri px od sebe — na videu snadno
splynou). Pred zmenou prepisu stoji za to jeden snimek originalu.

Dvojity tap smeru / druhe tlacitko (`0x7246`, `0x71f2`) je **skok
jeepu** (`0x91e8`: 3.5 px/t, `vz = 1.81`, `az = −1/16`); vrtulniku se
netyka.

## 4. TOWN boss GOOSE `0xc78a` — nativni kontrakt (prepsano)

Tato sekce vznikla jako rozdilovy audit. Stavovy automat byl prepsan
2026-08-30 a jeho death/orphan/checksum scheduler 2026-09-01; aktualni
otevrene mezery jsou v [GAPS](GAPS.md).

Poradi v kodu:

1. `st fp@(163)`, pin TOKEN.LIN; `a2c6(GOOSE#0, 0, 0, 0, 0, 100)`;
   `st +534` (imunni), bit 4, `y += 288`, `x = 160`, `z = 32`,
   `+280 = 0`
2. **ctyri** potomci pres `0x6144`: pod `0xcaac`, boky `0xc9f0`/`0xc9ec`,
   vrsek `0xc9e2`; `+276 = 4` = pocet nezadokovanych
3. anim `0xc7fc`: `period 1, orflag 128, GOOSE#0, andflag 128, GOOSE#0,
   loop` = **blika kazdy snimek** behem naletu
4. `vy = −2` az `sy <= 72`; pak `vy = 0`, anim `0xc82e`:
   `andflag 128, period 10, GOOSE#0,#0,#1,#2,#3,#4,#5, end` (zustane na #5)
5. **`0xc842`: HP 25 a kolize (`+504 = 34`) uz tady** — boss jde trefit
   od chvile, kdy se zastavi, i kdyz casti jeste leti
6. `0x93e2`: rotor `JEEPHELI#5..8` jako overlay (druhy animator `+422`,
   `0x6c82`), flag 128 se stridave zapina — rotor je videt kazdy druhy snimek
7. `0xc85e`: ceka, dokud `+276 == 0` (vsechny ctyri casti zadokovaly)
8. boj `0xc87e` (v prepisu je): `+280 = 2000`, `+282 = 10`, `vy = 1`, …

Dokovani casti (`0xcb78`, spolecne pro vsechny ctyri):

- ulozi cilovy ofset (`+332/+336`) do `+284/+286`, `+340 = 1` do `+288`;
  `z = z rodice + 1`; **odpoji** se od rodice (`andib #-9`);
  `+356 = 512` (2 px/t), uhel 64 (dolu), **75 snimku leti rovne dolu**
  (`0xcbc2`)
- pak smycka: cil = pozice rodice + ofset; Manhattan `< 6` → hotovo;
  jinak otocka k cili max `((63 − dist) clamp ≥2) / 2` jednotek za tik,
  rychlost 2 px/t (`0xcbc6`–`0xcc14`)
- dojezd: jeden tik **dvojnasobnou rychlosti** (`0xcc16`), pak obnovi
  `+332/+336` = ofset, **zapne bit 3** (sleduje rodice; ofset se od ted
  pricita k pozici rodice kazdy tik) a `subq #1, rodic+276` (`0xcc52`)

Casti `0xc9e2`/`0xc9ec`/`0xc9f0` po zadokovani (`0xca5a`): kdyz ma
rodic **hit-flash bit 1**, ofsety se na ten tik **zdvojnasobi**
(`0xca66`), pak se vraceji po 4 px/tik (`0xca7a`). Kazdy zasah bosse
tedy casti vizualne odhodi a ony se sjedou zpet. Casti maji `HP 0` →
nezranitelne, ale trida 34 → **zabijou vrtulnik dotykem**. Sirotci
handler `0x6db4` → po smrti tela na vlastnim orphan resume zmizi bez
exploze a uvolni svuj cost10.

Ctvrty potomek `0xcaac` **neni doprovod na vlastni draze** (oprava
`GAPS.md`): je to **pod pod telem**. `GOOSE#8..11` period 8 (`0xcae2`),
zadokuje na ofset `(0, +24)`, pocka 20 yieldu, pak s bitem 3 stale
zapnutym: `+356 = 0x1200` (rameno 18 px), uhel 64 a stridave `±8`
jednotek v sestikrokovych zhoupnutich s nahodnymi pauzami 10–41 yieldu
(`0xcb20`–`0xcb76`); po kazdem kroku `+336 += 12`, takze visi ~30 px
pod telem a kyve se. Sirotci handler `0xa36a` → pri smrti tela
**exploduje** (0 bodu).

Smrt tela (`0xc986`): `0x60e0` odpoji deti, 2 nebo 3 kruhy TOKENu,
zvuk `0x8838`; `a36a` zaradi samostatny `0x894a` child s malym EXPL1,
dvojici BIGEXPL zadosti a `z=33`, 0 bodu. Escort radi vlastni `0x894a`
se `z=34` z posledni publikovane world pozice a az potom dobere snake RNG.
Pri HP1 masce `bit0|bit3` probehnou oba callbacky a daji kruhy 2+3, dve
parent exploze a jednu escort explozi. Spici body child dokonci delay a
publikuje jeden post-death creation field pred orphan cleanupem. Parent po
107 checksum yieldech uvolni cost100 presne v N+108 ve sve FIFO pozici.
Zasah (`0xc974`): `−1 HP`, `negl vx`, zvuk `0x8834`, hit flash. Odlet po
2000 ticich bez zasahu: 5 kruhu, `vy = −4`, `sf +538` → cull za horni
hranou; cull nema parent death efekt, ale escort orphan a checksum tail ano.

## 5. Exploze a efekty (pro spravne „vybuchy")

| korutina | kdo | co dela |
|---|---|---|
| `0x894a`/`0x8952` | vychozi `+376` | zvuk `0x4c58(x)`, pin EXPL1, `EXPL1#7..13` period 4, kill |
| `0x8876` | velke objekty | pin EXPL2, zvuk `0x4c3c`, `EXPL2#0..6` period 6; **kazdych 15 snimku** dalsi `0x8952` v nahodnem ofsetu ±31 px |
| `0x88ec` | — | 8 pufu ve spirale, rychlost 6 px/t |
| `0x88fc` | smrt hrace (`0x9314`) | zvuk `0x4c1c`, **16** pufu, uhel +100/kus, polomer +3 px/kus, po 2 ticich |

Exploze maji bit 0 v `+367` = **bez stinu** (`0x641a`); stin se kresli
jen pri `z ≠ 0` na `(x + z/2, y + z)` s klicem −1 (pod vsim).

## 6. Prioritizovany seznam rozdilu `game.html` ↔ original (TOWN)

Nasleduje historicke poradi implementace z auditu 2026-08-30, nikoli aktualni
seznam otevrenych chyb. P0 body a schedulerove dodatky GOOSE jsou uzavrene;
pro zbyvajici stav je autoritativni [GAPS](GAPS.md) a
[TOWN-PARITY](TOWN-PARITY.md).

### P0 — herni mechanika, hrac to vidi hned

1. **Kolize vrtulniku** jen s tridou bit 1 (sekce 2.1). Odebrat smrt na
   `mine`, `proxmine` (telo), `train`, `flame`, `minecore`; ponechat
   `mill`, `air`, strely, strepy, GOOSE casti/pod.
2. **Jadro miny = stit** (1.1): pickup, orb-potomek, `+106/+108`, smart
   bomba pri druhem sebrani i pri sestreleni.
3. **Smart bomba**: bily zablesk 256 → −4/snimek a smrt vsech objektu s
   aktivnim `+534` (vcetne bodu); imunity podle `st +534`.
4. **Hrac**: 3 px/t, snimky 0..4 period 1, clamp 4..316 / 4..248,
   ochrana 200 + blikani 8/8, respawn 100 snimku, start 2 strely, stin
   `(+16,+32)`.
5. **HOMING sestrelitelna** (1 HP, 7 bodu).
6. **GOOSE**: HP od `sy 72` (ne az po slozeni); dokovani podle `0xcb78`
   (75 snimku dolu, homing 2 px/t, dvojity krok, snap); pod `0xcaac`;
   odhozeni casti pri zasahu; blikani pri naletu; anim `0,0,1,2,3,4,5`
   period 10; rotor overlay; smrt: casti zmizi, pod exploduje, maly
   EXPL1, 0 bodu.

### P1 — vizualni, hrac to vidi pri kazdem zasahu

7. **Hit flash** jeden snimek po zasahu u vsech nepratel (2.4).
8. **Dekaly** pro vsechny objekty s `+374` (2.5), ne jen MINE.
9. Otevrene polozky rendereru z `CODEX-HANDOFF.md`: globalni BOB fronta
   `0x481a`, paleta radku pro dynamicke BOBy, HW sprity strel, HUD glyphy,
   stiny z `z`.

### P2 — chovani, mensi

10. `+364` = cull margin per objekt (2.2) misto pevnych hranic.
11. Sirotci handler `+542`: potomci umiraji s rodicem (napr. MEDTANK vez).
12. `0x8876` velka exploze s nahodnymi sub-pufy (kdo ji v TOWN pouziva
    je treba dohledat pres `+376` zapisy `0x7a42`, `0xa0ee`, `0xa7b6`…).

### P3 — mimo TOWN, jen pro uplnost

13. Prechod TOWN → DESERT je **plynuly** (zadny „level complete";
    `fp@(160)` nastavuje jen finalni boss `0xc116`); prepis konci na
    `scroll <= 0`.
14. Swap vozidla (`0xac78`, `fp@(3550..3558)`) v TOWN neni.

## 7. Errata k dokumentaci (neaplikovano, jen seznam)

- `BEHAVIORS.md` FODDERA: „powerup carrier selection … token counter"
  je spatne; `0x80c8`–`0x80f0` je **casovac jedine rany** (M1 3. iterace
  to uz ma spravne). Sekce se maji sjednotit.
- `BEHAVIORS.md` MINE jadro: chybi pickup/stit (1.1).
- `BEHAVIORS.md` zbran: „tier = weapon counter / 5" → tier = `+102 / 5`
  (pocet sebranych bonusu) a aplikuje se jen pri spawnu; „start 1"
  vs kod `+100 = 2`.
- `BEHAVIORS.md` GOOSE: „dokud se sklada, nema HP" → HP 25 od `0xc842`
  (po zastaveni, pred dokoncenim skladani); doplnit dokovani a pod.
- `ENGINE.md` `+364` „draw priority" → cull margin; `+376` „handler" →
  sablona korutiny smrti; `+534/+538/+542` → 2.2.
- `GAPS.md` bod 2: „bodovy soucet 0xc950" → kontrolni soucet (2.7);
  „ctvrty potomek = doprovod s hadovitou drahou" → pod pod telem (4).
- `GAPS.md` bod 3: krok doznivani = `fp@(11168) = −4`; `+98` vs tabulka
  vyreseno (3).
- `tools/syms.json`: `0x9410` = hrac vrtulnik, `0x9090` = jeep,
  `0x8e26` = druhy jeep (JEEPHELI#25+), `0x939c` = zbranovy potomek,
  `0x98c4` = pickup jadra, `0x98f2` = orb stitu, `0x885a` = smart
  bomba, `0x898c` = dekal, `0x88fc` = exploze hrace.

## 8. Navrzene poradi prace

1. Kolizni tridy + stit + smart bomba (P0 1–3) — jedna zmena kolizniho
   bloku v `step()` a dve nove male korutiny; regrese: vrtulnik prezije
   dotyk miny/vlaku/plamene, jadro da stit na 500 tiku, druhe jadro
   spusti zablesk, zablesk zabije FODDERA a nezabije TOKEN.
2. Hrac (P0 4) — konstanty; regrese na rychlost, snimky, respawn.
3. HOMING sestrelitelna (P0 5).
4. GOOSE dokovani + pod + odhozeni (P0 6); regrese na 75-snimkovy nalet,
   snap a pocet potomku 4.
5. Hit flash + dekaly (P1 7–8).
6. Renderer podle `TOWN-PARITY.md` (P1 9) — Codex.

## 9. Co zustava otevrene

- ~~kolizni jadro~~ — docteno 2026-08-31: sweep `0x6ec2` (v `AMPROG`,
  ne v loaderu) potvrzuje sekci 2.1; event = OR trid protejsku,
  vyhodnoceni v N+1 (`GAPS.md` sekce 4)
- vyznam bitu 7 kreslicich flagu (`0x416a`; „blikani" GOOSE a rotoru
  predpoklada „nekreslit", stejne jako dnesni rotor MILL v prepisu)
- kompenzace kontrolniho souctu v `SWIVFIX` (2.7)
- jestli `0x8876` (velka exploze) pouziva nektery TOWN objekt
