# TOWN parity plan

Cilem je uzavrit TOWN jako referencni vertikalni rez: stejna grafika,
animace, chovani a zvuk jako original pri stejnem vstupu. Dalsi level se
nezacina, dokud neni tento kontrakt splneny. Kazda oprava musi mit bud adresu
v `AMPROG.OBJ`, nebo reprodukovatelny snimek originalu; vizualni odhad sam
o sobe nestaci.

## Co uz je uzavrene

- disk, boot chain, tri packery, katalog a formaty `.RAW`, `.LIN`, `.PAM`,
- dispatch grafika -> korutina se 73 polozkami,
- vsech 155 mapovych objektu TOWN ma prepsanou hlavni korutinu,
- fade `0x4a48` / `0x4a40` a driver `0x28b0`,
- zakladni zbran hrace, strely a chovani TOWN popsane v
  [BEHAVIORS](BEHAVIORS.md).

`155/155` neznamena pixelove hotovy level. Pocita hlavni mapove routy, ne
globalni renderer, pomocne potomky, vsechny animacni prikazy ani vsechny
specialni audio call-sites.

## Poradi prace

| priorita | oblast | dnesni stav | dukaz / otevrena prace | podminka uzavreni |
|---|---|---|---|---|
| P0 | deterministicky baseline | runtime pouziva port PRNG `0x883c`, CIAB-IRQ high-word perturbaci a rucni 50Hz tiky; `tools/baseline.sh` bootuje kanonicky ADF v headless vAmize a umi invulnerable capture | chybi zachyceny VHPOS/input trace a manifest vsech gameplay checkpointu | stejny vstup a HW trace vyrobi opakovane shodne snimky originalu i prepisu |
| P1 | rasterova paleta | produkcni viewport sklada mapu i dynamicke BOBy v indexech a RGB12 aplikuje az po slozeni pro kazdy scanline; TOWN ma stabilni fitted COLOR00-09 a nativni VBL prepis COLOR07 | `.PAM` prikazy meni terrain barvy na presnem rasterovem radku; objektovy fit drzi vsech 13 checkpointu a GOOSE audity t100/t130 | fitted slova nejsou tvrzeni o nativnich HW registrech; zbyva rozsirit raw checkpoint ratchet |
| P1 | HUD | runtime sklada embedded 7-row font do 352x8 masky; set bit dela zmereny opaque COLOR16 override nezavisly na lower4 | maska/anchory/Copper radky i nepruhlednost maji fixture; fyzicky OCS Denise trik zustava undocumented | raw checkpoint potvrdi gradient a sprite-over-HUD ve slozite scene |
| P1 | poradi kresleni | jedna unsigned depth fronta podle `0x481a`, vcetne child ordinalu, equal-z stability a specialnich BOB operaci | regrese sklada prekryvajici se realne `.LIN` snimky a hlida poradi/hash | proti originalu zbyva checkpoint capture slozitych krizeni |
| P1 | stiny | indexovy subtractive shadow s projekci `(x+z/2,y+z)` a skutecnym per-object z | `0x6364..0x638c`; zadna RGBA alpha aproximace v produkcni ceste | proti originalu zbyva checkpoint capture |
| P2 | animace TOWN | podporovane TOWN tasky maji adresove overene sekvence, periody i resume hranice | tabulka nize a `tools/uitest.py` | rozsirit pouze pri nalezu nove odchylky z originalniho capture |
| P3 | zbyvajici chovani | 155/155 hlavnich rout; SMART/event callbacky preziji generation invalidaci; MINE-core wait10; GOOSE scheduler, SMART deadline i TOKEN/SMART/explosion fresh children maji creation-order regrese | map reader nema per-record yield; zbyva obecna jednotna priority100 continuation/fresh-child fronta a TRAIN checksum tail | pending event masky, callbacky a spawn/RNG interleaving sedi s nativnim schedulerem |
| P4 | hudba a zvuk | bezi 4voice Paula/CIAB model; hlavni TOWN bojove efekty, `SMART.SND`, bound MINE shield, TOKEN pickup i GOOSE hit/death jsou napojene; TOKEN noty a fresh SMART/`0x894a` childy maji FIFO poradi | chybi zbyvajici special/player-transition call-sites a hardwarove A/B overeni nejnizsich GOOSE period; viz [SOUND](SOUND.md) | cely TOWN od startu po bosse ma vsechny efekty, priority a RNG poradi z originalu; gameplay hudba je zdrojove ticho |

### Stav zakladu rendereru (2026-08-29)

Indexova cesta uz neni jen pomocny experiment. Testovane stavebni bloky jsou:

- paletove nezavisly dekoder a blitter logickych `.LIN` snimku vcetne
  retezeni, signed anchoru, transparentnosti a orezani,
- kompilator 16 RGB12 barev pro kazdy vystupni scanline z raw `.PAM`
  checkpointu,
- presny nibble fade v poradi cerna -> bila.

Regrese hlida skutecnych 13 TOWN checkpointu, obe hranice palety v uvodnim
okne a dvoudilny `JEEPHELI.LIN#1`. `renderMap` dual-writeuje indexovou mapu
i historicky RGBA oracle. Produkcni `composeTownBobs` kazdy frame zkopiruje
indexovy viewport, provede decal prepass a celou dynamickou frontu, teprve
pak `colorizeIndexedField` aplikuje paletu a oba fade levely po radcich.
Zname okno pres hranici checkpointu ma proti spravnemu oracle 0 rozdilnych
bajtu; paleta stredu okna zustala jen v diagnosticke Canvas vetvi.

TOWN ma navic dve od palety terenu oddelene vrstvy barvoveho stavu:

- `parsePam` vraci `lead`, tedy pocet y pixelu spotrebovanych uvodni davkou
  PAM prikazu pred prvnim nepaletovym zaznamem. Pro TOWN je `lead = 96`;
  startovni radek se proto posunul z 3345 na
  `3345 - 96 = 3249`. Checkpoint `t17` na radku 3229 uz zachycuje
  dvacet pixelu nasledujiciho scrollu, neni to druhy startovni anchor.
- COLOR00-09 objektu pouzivaji v TOWN stabilni fitted canvas RGB12 radu
  `000 333 465 598 765 666 9A9 800 ED6 EEE` na vsech 13 PAM
  checkpointech. COLOR10-15 zustavaji scanline barvami terenu z PAM.
  Hodnoty vznikly pixel-fitem JEEPHELI/YELLOW/MEDTANK/GOOSE proti vystupu
  emulatoru; jsou kompenzaci rendereru, **ne tvrzenim, ze prave tato slova
  lezi v nativnich HW registrech**.

Prvni verze z commitu `abc853e` spravne vytezila `lead` i uvedeny fit,
ale nechavala pozdejsi PAM zapis stejneho indexu znovu vyhrat. Uz od
checkpointu `y=104` tim vznikla smesena COLOR00-09 a pozdni GOOSE dostal
barvy `555/687/7BA/987/BCB/B30`. Aktualni TOWN-only aplikace drzi fitted
desitku ve vsech checkpointech; mimo TOWN nic neprepisuje.

COLOR07 je z teto stabilni zakladni palety vedoma dynamicka vyjimka.
Nativni writer `0x2b3e..0x2b5a` ji v aktivnim levelu prepise kazdy VBL
cervenym RGB12 slovem: `phase = (g.tick >>> 2) & 15`, pri `phase & 8`
se `phase` bitove obrati a vysledek je `(8 + (phase & 7)) << 8`.
Cela 64-VBL perioda je
`8,9,A,B,C,D,E,F,F,E,D,C,B,A,9,8`, kazda hodnota drzi ctyri VBL, a faze
se bere z aktualniho `g.tick`, nikoli z poctu renderu. Volani podle
`0x28fe` bezi jen pri nulovem black fadu: pri black fadu se pouzije bezna
zcerna paleta. Protoze CPU zapis jde primo do COLOR07 az za paletovym
compilerem, pri nulove cerne naopak obchazi i pripadny white fade.

Vizualni audit dlouheho prujezdu potvrdil stejnou desitku v `t100` na
`row=2199` i v `t130` na `row=1831`. Druhy checkpoint obsahuje sestaveny
GOOSE; indexovane snimky tela a casti `#5/#6/#7/#10` davaji modalni barvy
originalu bez zlomu na `y=104`. Regrese navic hlida vsechny checkpointy,
64-VBL COLOR07 sekvenci, black-fade gate i white-fade bypass.

**D1 je zapnut v produkcnim runtime:** ciste helpery reprodukuji
unsigned depth klic a poradi fronty `0x481a`, projekci stinu z
`0x6364..0x638c`, cookie-copy `0x0FCA` i nepruhledny clear vsech bitplanu na
index 0 pres `0x0B0A`. Regrese sklada skutecne snimky FODDERA, MILL,
JEEPHELI a POPUP do indexoveho bufferu a hlida poradi i hash. Puvodni Canvas
pruchody jsou dostupne jen pres diagnosticky `legacyCanvasOverlay`.

HUD font, format a 352x8 maska jsou bitove uzavrene. Produkcni runtime ji
sklada na y8..14 jako zmereny nepruhledny COLOR16 override: set bit nesmi
zdedit lower4 ani blikajici COLOR17..31. Tim se odstranilo zlute/cervene
problikavani `HELI` a `PRESS FIRE`. Presny fyzicky OCS mechanismus zustava
undocumented, ale efekt potvrzuje raw frame, autoruv popis AGA selhani i
WHDLoad oprava. Nezname COLOR20/24/28 zustavaji jen cold-boot politikou
sprite-bank modelu, nikoli blockerem HUD textu.

Audit specialnich vrstev pred runtime switchem navic uzavrel, ze hracovy
BULLET#14, cannon a jediny publikovany PLOP frame BULLET#2 jsou HW sprity,
kdezto HOMING je bezny
BOB v COLOR00–15. Black fade HW sprite zaznamy vubec nezaradi; white fade je
nemeni. Produkcni TOWN pass uz sdili presne 64 zaznamu, radi actor tasky pred
30slotovy player pool, prideluje kanaly `0,7,6..1`, respektuje off-top skip,
linearni DMA reuse i prioritu nizsiho cisla kanalu a vybira COLOR17–31 banku
podle dvojice kanalu. Cannon pouziva depth snapshot z `0x96aa` pred vlastnim
pohybem. Spolu s efektivni HUD maskou jsou tak obe drive otevrene
rendererove vrstvy zapojene; raw porovnani s originalnim runtime zustava
prijimacim testem a neznamy zdedeny high-color stav se tyka jen nepopsanych
sprite-bank slotu.
Stateless decal prepass je pro vysledny viewport ekvivalent mapove mutaci,
`z` explozi i ctyrdilny GOOSE uz fronta nese. Pomocny `0xA0` save-under
prepass nema ve stateless indexovem framebufferu samostatny viditelny efekt.

### Stav zvuku (2026-09-01)

Produkcni runtime uz nema jednorazovy `snd(...,8000)` fallback. Modeluje
ctyri persistentni Paula hlasy, CIAB tempo, strict priority guard, stereo-pair
preferenci s fallbackem, persistentni noise scratch i IRQ perturbaci gameplay
PRNG. Napojene jsou zvuky salvy hrace, defaultniho neletalniho zasahu,
kanonu, HOMINGu, POPUP/PROXMINE/FLAME openingu, kazdeho FLAME puffu,
dvouvrstve standardni exploze, ctyrvrstve exploze hrace a custom smrti
GOOSE i jeho neletalniho hitu s deferred IRQ seedem. White flash navic hraje
ctyrvrstvy `SMART.SND`, bound MINE bublina vlastni priority60 ton a kazdy
TOKEN pickup ctyri priority120 noty v rozestupu peti VBL. Presne adresy,
casy a exkluze jsou v [SOUND](SOUND.md). Pickup pouze zalozi priority100
sound child; prvni note, dalsi resume i soubeh s fresh SMART/`0x894a` childy
se radi creation FIFO. Regrese navic hlida, ze uz existujici GOOSE callback
probehne pred nove zalozenym TOKEN childem a ze typ4 spusti TOKEN pred SMART.

TOWN jeste neni zvukove uzavren: zbyvajici special/player-transition
call-sites (zejmena extra-life `0x5600`) zustavaji otevrene. Collision-driven
zvuky uz zacinaji az s prislusnym callbackem v N+1. Samostatna gameplay hudba se
nedoplnuje, protoze original po titulku modul uvolnil a ve hre pouziva efekty.

### Stav last-field lifecycle (2026-08-31)

`a2c6` d2 je vstupni/activation margin, nikoli cull `+364`; ten alokator
inicializuje samostatne na −64. FLAME parent pouziva −8,
cannon/HOMING/PLOP/PROXMINE fragment 0, aktivni TOKEN −64 (burst ma cull
vypnuty), GOOSE parent zapina cull jen pri escape a jeho children jej maji
vypnuty. TRAIN konci primym testem `screenY >= 272`, ne callbackem `0x6480`;
test je ale az za navratem z posledniho publikovaneho `0x62d2` fieldu.

Producing VBL N provede pohyb a cull invalidaci, ale jeste publikuje a
collision-sweepuje posledni field. Resume N+1 zachovava poradi bit4 scroll
compensation, clear flash, orphan, SMART a event callbacku a az potom uvolni
zaznam i cost. Generation invalidace uvnitr SMART/bit0 nezastavi zbytek
masky: `SMART -> bit0 -> bit3` dobehne a cleanup je jen jeden. Sebrany
MINE core stejne provadi bit4 compensation pred kazdym resume sveho presneho
wait10. Fresh PROXMINE/FLAME/TRAIN children pritom dostanou prvni
movement a `seq[0]` animacni publikaci uz v creation VBL; generic-cull childy
v nem vyhodnoti i bounds, TRAIN az na dalsim resume.
Generalized ordinary last-field mezera je uzavrena regresi;
GOOSE child orphan/explosion tasky, SMART deadline a parent checksum N+108
jsou rovnez serazeny vlastnimi creation ordinaly. Otevrene zustava obecne
prokladani vsech kategorii do jedine priority100 continuation/fresh-child
fronty a TRAIN checksum/map-reader yield. TOKEN sound-child FIFO vcetne
fresh SMART/`0x894a` soubehu je uz uzavreno.

## Audit animaci TOWN

### Zdrojove podlozene

- FODDERA, YELLOW a BIRD,
- MINE vcetne jadra a PROXMINE vcetne strepu,
- FLAME vcetne emitteru a puffu,
- CAMOGUN a rotor MILL,
- TRAIN a korba/smerova vez MEDTANK jsou v odpovidajicich stavech staticke
  nebo vybirane smerem.

### Auditovane odchylky

- **ROTOBASE — uzavreno**: skripty `0x996a` / `0x9986` maji periodu 2;
  smer se pri aktivaci strida pres globalni `notw fp@(138)` na `0x9960`.
  Prepis i regrese uz nepouzivaji drivejsi periodu 4 ani paritu x a hlidaji
  i duplicitni pocatecni #4 dopredneho skriptu.
- **POPUP — uzavreno**: otevreni `0xa6e8` a zavreni `0xa72a` maji
  periodu 6; regrese hlida soubeh openingu s wait(50), celou osu t0–t162
  i skutecny `KILL` na konci closing skriptu.
- **PLOP — uzavreno**: same-priority FIFO child jeste ve spawn VBL projde
  prvnim `0x62d2`; animator countdown1 proto setup `PLOP#0` prepise pred
  enqueue a prvni a jediny publikovany field je HW `BULLET#2`. Dalsi resume
  provede `KILL`. Prvni pohyb navic zdedi parentovu rychlost.
- **kanonovy granat — uzavreno**: faze je stav kazdeho objektu prepinany
  na `0x96b4`, ne globalni parita herniho tiku; accel i straight cesta
  maji regresi vcetne same-VBL prvniho pohybu, pre-move depth, poradi
  pohyb -> akcelerace a budgetu strela+PLOP.
- **GOOSE — stavovy automat uzavren 2026-08-30**: blikani `0xc7fc`,
  prechod `0,0,1,2,3,4,5` period10 z `0xc82e`, rotor `0x93e2`, cekani na
  `+276 == 0` (`0xc85e`), dokovani `0xcb78`, pod/escort `0xcaac` s animaci
  `GOOSE#8..11` (`0xcae2`) a odhozeni casti `0xca5e` jsou v prepisu.
  Stavove fixture pokryvaji vsechny ctyri deti vcetne
  ingress/overshoot/snap; N+1 fixture navic hlidaji oddeleny producing
  field, hit-spread, smrt, zvuky a prvni field TOKEN child tasku. Timeout
  uz ve stejnem resume publikuje prvni `-4 px` escape field.
- **GOOSE — death scheduler uzavren 2026-09-01**: `a36a` radi `0x894a`
  jako fresh explosion task, parent a escort maji oddelene efekty a HP1
  maska `bit0|bit3` dava tokenove kruhy 2+3. Orphan fixture hlida cost10,
  posledni publikovanou pozici escortu, post-callback snake RNG 2/1/0 i
  jeden creation field opozdeneho body childa. Parent cost100 zustava do
  presneho N+108 checksum resume ve sve FIFO pozici; timeout nema parent
  explozi ani death synth.

Obecny `scanAnims` je zatim inventarni pomucka, ne uplny runtime interpreter:
zahazuje `END/KILL`, flagy a offsety a sekvence bezpodminecne cykli. Pro TOWN
se pouziji jen rucne overene skutecne vstupy; dlouhodobym cilem je interpret
celeho prikazoveho formatu.

## Baseline a overovani

Kanonicky vstup je `SWIVFIX.ADF` se SHA-256 uvedenym v README. Pro stare H.264
zaznamy je pripustna tolerantni korelace/SSIM; komprese a snimani plochy
znemoznuji pixelovou shodu. Presny kontrakt zacina az raw framebufferem z
headless emulace.

**Baseline UZAVREN (2026-08-31, `tools/baseline.sh`)**: kanonicky
`SWIVFIX.ADF` v headless vAmize (v5.0b1,
`/Users/mik/claude46/Amiga/reference/tools-bin/VAHeadless`, A500 OCS 1MB,
KS 1.3, warp ~15x) **bootuje** — drivejsi „skonci na Kickstart obrazovce"
bylo cracktro The Company, ktere ceka na klik mysi. Deterministicka
vstupni sekvence (emulovane sekundy od zapnuti):

| t | vstup | obrazovka pred nim |
|---:|---|---|
| 32 | `mouse1 press left` | cracktro (text The Company) |
| 40 | `mouse1 press left` | MEGA TRAINER (vychozi NO/NO/NO/NO, autofire 1 = cista hra) |
| 85 | `joystick2 press 1` + `unpress 1` | attract (kredity/hi-score/COVER) |
| ~101 | — | **start urovne TOWN** (fade z cerne; fire+17 uz bezi) |

Pro dlouhy vizualni audit pouzij
`SWIV_BASELINE_TRAINER=1 tools/baseline.sh <prefix> <sekundy...>`.
Skript pak na traineru pred startem prepne **F1 UNLIMITED LIVES** a
**F3 KEEP WEAPONS** na YES (overeno snimkem traineru po klavesach
80/82; volba „no collisions" v traineru neexistuje — drivejsi popis byl
chybny a hrac v tomto rezimu normalne umira). Meni to herni podminky
(zivoty, sila zbrane po smrti), proto je rezim urceny jen pro
prujezd/checkpointy celeho levelu, ne jako kanonicky cisty baseline.
`SWIV_BASELINE_UNLIMITED_LIVES=1` prepne pouze **F1 UNLIMITED LIVES**.
Trainer ma dale **F5/F6 MISSILES** (vychozi 1; F5 snizuje, F6 zvysuje)
a **F7/F8 AUTOFIRE RATE** (vychozi 1). **MISSILES je startovni sila
zbrane `+100`**: s vychozim 1 leti jedna strela, s MISSILES=3 tri na
x 156/160/164 (licha tabulka `0x8d46`) — zmereno snimky s drzenym fire.
Kod `0x6fde` sam zapisuje 2; trainer ho prepisuje, a protoze kanonicky
baseline bezi s vychozim trainerem, prepis startuje s 1.

Overene detaily: `mouse1 press` je press+release, `joystick2 press 1`
tlacitko **drzi** (uvolneni je `unpress 1`); smery jsou `pull
left/right/up/down` + `release x/y`, takze jde skriptovat cely input
tape. `wait N` je v emulovanych sekundach; `std::exception`, ktere
regression rezim u `wait` vypisuje, je kosmeticke — ceka se spravne.
`screenshot save` ulozi raw RGB24 716x285 a proces ukonci (jeden beh =
jeden snimek; determinismus dava serie opakovanym behem). Prvni snimky:
start ma velkou budovu vlevo nahore a diagonalni silnici; HUD originalu
po spawnu ukazuje **3 zivoty** (spotreba jednoho pri spawnu, `0x709a`),
ne 4; bile blikani spawn ochrany 8/8 je na snimcich videt.

### Prvni vytezky baseline (2026-09-01, opraveno 2026-09-03)

- **gamma profil emulatoru**: vAmiga (v5.0b1, vychozi monitor) neprevadi
  RGB12 linearne (`nibble*17`); Denise PixelEngine linearizuje CRT gammou
  2.8 a re-koduje 1/2.2. Zmereno na registrech znamych z kodu a dat (HUD
  COLOR16 `0x88D/0xAAE/0xCCF`, teren `0x653/0x542` z PAM, bila `0xfff`,
  sedi `0x555/0x888/0xbcb` z PAM ry=104): nibble 0..15 →
  `0 0 0 28 43 56 72 89 106 123 141 159 178 197 216 236`
  (`VAMIGA_LUT` v `tools/compare.py`). Prepis renderuje presne `n*17`;
  prevod je vec porovnani, ne palety.
- **objektova paleta COLOR01-09**: zapisuje ji sam PAM checkpointem na
  ry=104 hned za uvodni davkou (`1=555 2=687 3=7ba 4=987 6=bcb 7=b30`;
  `5=888 8=fe8 9=fff` ma uz hlavicka). Drivejsi „zmerena" tmavsi sada
  `333/465/598/765/666/9a9/800/ed6/eee` byla presne tato paleta
  posunuta gamma krivkou — artefakt mereni, ne engine override; z
  `game.html` je odstranena. COLOR07 navic kazdy VBL prepisuje CPU
  cervenym trojuhelnikem 8..15..8 (`0x2b3e`).
- **„sum" terenu neexistuje**: krapani je soucast kobercovych dlazdic
  (`_HOUSES#1` ma v datech smes indexu 10/11/12), zadny generator, zadne
  roviny 0/2 se sumem. Strip je kruhovy 320 radku (`0x341a`), pas se maze
  jen v rovinach 1 a 3 (`0x34f2`). Render z dlazdic je proti originalu
  pixelove presny; zdanlivy sum byla gamma krivka plus 1px posun radku.
- **start okna**: uvodni davka prikazu spotrebuje `parsed.lead` px
  (TOWN 96) a original je nikdy neukaze. Presny start je
  `3345 - 96 = 3249`; korelace snimku t16–t23 dala `3245 ± 8`.
- **HUD zivoty**: zobrazene cislo je pocet po spotrebe spawnu
  (`0x709a`) — 4 zivoty se ukazuji jako „3".
- **`tools/compare.py`** — treti kontrakt: snimek originalu vs prepis
  (prevedeny `VAMIGA_LUT`) na presne zmerenem radku mapy (start t17 =
  radek 3228), tolerance 8/kanal, ratchet jen roste. Stav statickeho
  checkpointu `start` (do 2026-09-03; od te doby simulace, viz nize):
  **celek 100.0 %, teren 100.0 %, HUD 100.0 %, HELI 99.7 %**;
  ratchet 99.0 %. Historie: 20.1 % (zavedeni) → 22.5 % (kalibrace) →
  76.8 % (LUT misto zapecene palety) → 99.2 % (radek 3228) → 100 %
  (linearni HUD/COLOR07).

### Druhe vytezky baseline — prvni FODDERA vlna (2026-09-03)

Checkpointy jsou od ted **simulace**: `startGame(0)` a `ticks` kroku
`step()` bez vstupu (baseline drzi joystick v klidu); `row` je zaroven
kontrola scrollu. Tape-zavisle vstupy dodava recept checkpointu: faze VBL
citace (`vblBase`) a RNG prvni vlny (`fodder.x/vx`).

- **kolizni box neni 8/8**: `0x6dce` sice instaluje uzel `+488` s extenty
  `+12/+14 = 8/8`, ale kazdy `a2c6` objekt jej hned prepise pres `0x6d7c`
  slovy `+16/+18` zaznamu snimku sveho d0, ktera loader `0x457e` plni
  **bajty 8/9 hlavicky dilu .LIN** (do ted „neznama" dvojice). FODDERA#2 =
  10/20, YELLOW#0 9/17, BIRD#0 11/19, MINE#0 12/14, MINE#9 (core) 14/14,
  POPUP#0 17/15, MEDTANK#0 12/11, ROTOBASE#4 15/16, TRAIN#0 29/25,
  PROXMINE#0 10/11, FLAME#0 14/11, CAMOGUN#0 10/13, MILL#0 13/14,
  TOKEN#0 10/10, HOMING#4 11/11, GOOSE#0 9/19 / #8 12/17. Hrac
  (`0x9430/0x9438` → `0x6dc8`), bolty (`0x8e72/0x90da`) a cannon
  (`0x960e`) zustavaji u 8/8. Sweep `0x6ec2` testuje **pozici** souseda
  proti **vlastnimu** boxu (inclusive) a tridy si zapisuji navzajem; uzel
  s tridou bit15 (PLOP, MEDTANK vez) sam nesweepuje. Dotyk dvou uzlu je
  tedy sjednoceni obou smeru (`nodesTouch`, tabulka `NODE_GRAPHIC`).
  Dukaz: t19 ma EXPL1#8 (smrt clena 0 kontaktem s chranenym hracem) na
  (157,176); s 8/8 vychazel #7 na (155,184), s 10/20 sedi.
- **uzel se plni pri resume** (`0x6430`, pred bit4 kompenzaci `0x6446`):
  sweep na konci VBL N porovnava pozice, ktere telo spocitalo v N−1 a
  ktere `0x642c` prave publikuje jako BOB; callback v N+1 uz cte o jeden
  pohyb novejsi `+320/+324`. Prepis si proto na konci sweepu uklada
  snapshot (`snapNode`, platny jen pro tick+1) a pristi sweep cte ten.
  Bez toho lezela exploze o 4 px (jeden tik pohybu FODDERA) vys.
- **faze rotoru**: t17 a t18 maji JEEPHELI#0, t19 #2 (index 3 skriptu
  `0,1,0,2,0,3,0,4`, perioda 1). Pri T19 = 184 (fit vlny, 98.5 % vs
  97.1 % pro 183) je `index = (T + 3) & 7`; startovni `heliAnimPos = 4`.
  Radek 3228 dovoluje T17 ∈ 81..84 (word = 3249 − ceil(T/4)), rotor #0
  vyzaduje liche T → T17 = 83, tj. `wait` vAmigy ma jitter jednoho
  snimku (odstup t17→t19 je 101).
- **faze HUD prompt/stav**: `0x740c` prepina po 128 VBL podle citace
  `fp@(-68)` od bootu; z PRESS FIRE (t17, t18, t19, t23) a JEEP (t20,
  t21) plyne faze pri startu urovne 172..199 mod 256 → `vblBase = 186`.
- **scroll word**: `fp@(3542)` je WORD; screen-y = world-y − floor(scroll)
  (`scrollTop`), bit4 kompenzace i camera delta boltu jsou celociselne
  (1000.0 → 999.75 uz je delta −1).
- Stav checkpointu: `start` (T=83) **99.9 % / teren 99.9 / HUD 100 /
  HELI 99.7** (ratchet 99.0); `wave` (T=184) **99.0 % / 99.0 / 100 /
  99.9** (ratchet 98.5). Historie `wave`: 97.6 (8/8, plovouci scroll) →
  97.7 (boxy z hlavicky) → 98.5 (uzel z resume) → 99.0 (HUD faze).
- **dalsi snimky**: t20 (T≈234) ukazuje smrt hrace (`0x88fc` spirala
  16× EXPL1, skore 360 = tri FODDERA), t21 spiralu dal, t23 (T≈384)
  bily obrys vrtulniku pri respawnu, zivoty 2, PRESS FIRE — kandidati
  na checkpointy `death` a `respawn`.

### Regionalni vizualni kontrakt (`tools/compare.py`, 2026-09-01)

`tools/compare.py` porovnava raw 320x256 vyrez originalu s prepisem na
presne zmerenem mapovem radku a drzi whole-frame minimum jako jednosmerny
ratchet. Pro kazdy checkpoint vytvori bez posunu scheduleru tri varianty
stejneho renderu: cely snimek, snimek bez HELI a snimek bez HELI i HUD.
Jejich rozdily tvori navzajem disjunktni masky:

- `HELI` = pixely zmenene odebranim hrace, vcetne tela a stinu,
- `HUD` = pixely zmenene vynulovanim HUD bitplane po odebrani hrace,
- `terrain` = zbytek bez HUD/HELI; `whole` obsahuje vsech 320x256 pixelu.

Aktualni checkpoint `start` (`t=17`, `row=3229`, tolerance 24 na kanal)
dava **whole 22.5 %, terrain 21.3 %, HUD 100.0 %, HELI 99.7 %**. HELI tak
ma v tomto kontrolovanem stavu presny anchor, fitted barvy i stin; nepatrny
zbytek je dynamicky COLOR07/capture profil. HUD se po kalibraci skutecnych
COLOR16 slov na zmereny headless-vAmiga vystup shoduje ve vsech 639
pixelech masky. Opaque COLOR16 reseni zaroven zustava oddelene od
blikajicich COLOR17-31 a je kryte samostatnou fixture.
Nizkou whole/terrain shodu stale dominantne tvori jina sumova textura
terenu; regionalni vypis zabranuje, aby tento znamy rozdil zakryl regresi
hrace nebo HUD.

Plan jednoho checkpointu:

1. zaznamenat vstup jako PAL tik + joystick/fire stav,
2. pustit original v deterministicke A500/OCS konfiguraci,
3. ulozit raw framebuffer a presne vyrezat 320x256,
4. v `game.html` vypnout RAF, prehrat stejny vstup po 50Hz ticich a cist
   pixely primo z `#game`,
5. vyhodnotit oddelene pozadi, paletu, HUD, objekty/animaci a efekty,
6. pripojit k oprave malou logickou regresi v `tools/uitest.py` a jeden
   vizualni checkpoint.

Nejprve staci checkpointy pro start/fade, prvni FODDERA vlnu, prvni POPUP,
ROTOBASE, FLAME/CAMOGUN, TOKEN a GOOSE. PRNG algoritmus je stabilni; cely
level ma smysl porovnat dlouhym zaznamem az po zachyceni VHPOS a input trace.

## Definition of done pro TOWN

- zadny stav `unimplemented`, `missing-dispatch` ani vedomy vizualni fallback,
- vsechny animace a pomocne objekty maji adresu zdroje a regresi,
- pixelove checkpointy jsou opakovatelne ze stejneho input tape,
- renderer zachovava rasterove palety, poradi, stiny, HUD a fade,
- pohyb, kolize, HP, body, dropy a casovani sedi s 68k kodem,
- hudba a zvuky sedi udalosti, casovanim, prioritou i kanalovou arbitrazi,
- `tools/check.py` a `tools/uitest.py` prochazeji bez chyb.
