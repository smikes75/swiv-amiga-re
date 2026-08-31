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
| P0 | deterministicky baseline | runtime pouziva port PRNG `0x883c`, CIAB-IRQ high-word perturbaci a rucni 50Hz tiky; nulovy VHPOS vstup je opakovatelny | VAHeadless 5.0b1 kanonicky ADF nenabootuje; chybi zachyceny VHPOS/input trace a manifest checkpointu | stejny vstup a HW trace vyrobi opakovane shodne snimky originalu i prepisu |
| P1 | rasterova paleta | produkcni viewport sklada mapu i dynamicke BOBy v indexech a RGB12 aplikuje az po slozeni pro kazdy scanline | `.PAM` prikazy meni barvy na presnem rasterovem radku | proti originalu zbyva kanonicky runtime capture, nikoli dalsi paletovy prepis |
| P1 | HUD | runtime sklada embedded 7-row font do 352x8 masky; set bit dela zmereny opaque COLOR16 override nezavisly na lower4 | maska/anchory/Copper radky i nepruhlednost maji fixture; fyzicky OCS Denise trik zustava undocumented | raw checkpoint potvrdi gradient a sprite-over-HUD ve slozite scene |
| P1 | poradi kresleni | jedna unsigned depth fronta podle `0x481a`, vcetne child ordinalu, equal-z stability a specialnich BOB operaci | regrese sklada prekryvajici se realne `.LIN` snimky a hlida poradi/hash | proti originalu zbyva checkpoint capture slozitych krizeni |
| P1 | stiny | indexovy subtractive shadow s projekci `(x+z/2,y+z)` a skutecnym per-object z | `0x6364..0x638c`; zadna RGBA alpha aproximace v produkcni ceste | proti originalu zbyva checkpoint capture |
| P2 | animace TOWN | podporovane TOWN tasky maji adresove overene sekvence, periody i resume hranice | tabulka nize a `tools/uitest.py` | rozsirit pouze pri nalezu nove odchylky z originalniho capture |
| P3 | zbyvajici chovani | 155/155 hlavnich rout; GOOSE/TOKEN/core/HOMING/POPUP, terrain-mask respawn, dynamic difficulty, cost accounting, N+1 collision hranice a generalized ordinary last-field cull jsou prepsane | map reader nema per-record yield; zbyva plne priority100 FIFO, SMART/event arbitration pres invalidaci, GOOSE per-child orphan/explosion poradi, TOKEN sound child FIFO a GOOSE/TRAIN checksum cost-delay tails | pending event masky, callbacky a spawn/RNG interleaving sedi s nativnim schedulerem |
| P4 | hudba a zvuk | bezi 4voice Paula/CIAB model; hlavni TOWN bojove efekty, `SMART.SND`, bound MINE shield, TOKEN pickup i GOOSE hit/death jsou napojene a collision zvuky respektuji N+1 | chybi zbyvajici special/player-transition call-sites a taskove FIFO poradi TOKEN/GOOSE explosion child efektu; viz [SOUND](SOUND.md) | cely TOWN od startu po bosse ma vsechny efekty, priority a RNG poradi z originalu; gameplay hudba je zdrojove ticho |

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

### Stav zvuku (2026-08-31)

Produkcni runtime uz nema jednorazovy `snd(...,8000)` fallback. Modeluje
ctyri persistentni Paula hlasy, CIAB tempo, strict priority guard, stereo-pair
preferenci s fallbackem, persistentni noise scratch i IRQ perturbaci gameplay
PRNG. Napojene jsou zvuky salvy hrace, defaultniho neletalniho zasahu,
kanonu, HOMINGu, POPUP/PROXMINE/FLAME openingu, kazdeho FLAME puffu,
dvouvrstve standardni exploze, ctyrvrstve exploze hrace a custom smrti
GOOSE i jeho neletalniho hitu s deferred IRQ seedem. White flash navic hraje
ctyrvrstvy `SMART.SND`, bound MINE bublina vlastni priority60 ton a kazdy
TOKEN pickup ctyri priority120 noty v rozestupu peti VBL. Presne adresy,
casy a exkluze jsou v [SOUND](SOUND.md).

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
zaznam i cost. Fresh PROXMINE/FLAME/TRAIN children pritom dostanou prvni
movement a `seq[0]` animacni publikaci uz v creation VBL; generic-cull childy
v nem vyhodnoti i bounds, TRAIN az na dalsim resume.
Generalized ordinary last-field mezera je uzavrena regresi;
otevrene zustava plne priority100 FIFO, presna SMART/event arbitration pres
invalidovanou generaci, GOOSE child orphan/explosion tasky, TOKEN sound child
FIFO a checksum cost-delay tails GOOSE parentu a TRAIN lokomotivy.

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
  uz ve stejnem resume publikuje prvni `-4 px` escape field

Obecny `scanAnims` je zatim inventarni pomucka, ne uplny runtime interpreter:
zahazuje `END/KILL`, flagy a offsety a sekvence bezpodminecne cykli. Pro TOWN
se pouziji jen rucne overene skutecne vstupy; dlouhodobym cilem je interpret
celeho prikazoveho formatu.

## Baseline a overovani

Kanonicky vstup je `SWIVFIX.ADF` se SHA-256 uvedenym v README. Pro stare H.264
zaznamy je pripustna tolerantni korelace/SSIM; komprese a snimani plochy
znemoznuji pixelovou shodu. Presny kontrakt zacina az raw framebufferem z
headless emulace. Aktualni `VAHeadless` opakovane vraci bitove shodny raw
RGB24 framebuffer 716x285, ale s `SWIVFIX.ADF` skonci na Kickstart obrazovce;
jiny kontrolni SWIV ADF ve stejne konfiguraci bootuje. Nastroj je tedy
deterministicky, kanonicky boot/crop vsak zatim neni vyreseny.

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
