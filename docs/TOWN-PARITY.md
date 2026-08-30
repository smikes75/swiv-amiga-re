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
globalni renderer, pomocne potomky, vsechny animacni prikazy ani audio engine.

## Poradi prace

| priorita | oblast | dnesni stav | dukaz / otevrena prace | podminka uzavreni |
|---|---|---|---|---|
| P0 | deterministicky baseline | logiku umi `tools/uitest.py` tikat rucne; runtime stale pouziva `Math.random()` | headless capture je deterministicky, ale VAHeadless 5.0b1 kanonicky ADF nenabootuje; chybi vstupni zaznam a manifest checkpointu | stejny vstup vyrobi opakovane shodne snimky originalu i prepisu |
| P1 | rasterova paleta | staticke pozadi uz pouziva indexy a presnou paletu kazdeho scanline; dynamicke BOB objekty zatim paletu stredu okna | `.PAM` prikazy meni barvy na presnem rasterovem radku | kazdy vystupni radek vcetne dynamickych objektu pouzije paletu platnou na tomto radku |
| P1 | HUD | Canvas runtime uz ma presny obsah, x-anchory, 4 zivoty a skore x10; glyphy/barvy jeste ne | font, maska, format a raster jsou exaktne vytezeny; original pouziva patou bitovou rovinu a COLOR16–31, viz [HUD](HUD.md) | nativni glyphy, ikony, skore a barvy sedi s raw snimkem |
| P1 | poradi kresleni | samostatne pruchody mapa / hazards / air / exploze / strely | originalni fronta `0x481a` radi draw zaznamy podle klice | krizeni objektu ma stejnou okluzi jako original |
| P1 | stiny | cerna RGBA silueta, vetsinou posun `(+16,+22)` | `0x6364..0x638c`: projekce ze z-hloubky je `(x+z/2,y+z)`; TOWN letci maji `z=32` | geometrie i bitplanova operace jsou odvozene z kodu, bez alpha odhadu |
| P2 | animace TOWN | vetsina hlavnich sekvenci sedi, nekolik period a stavovych prechodu ne | tabulka nize | kazda sekvence ma overeny vstup, periodu, flagy a ukonceni |
| P3 | zbyvajici chovani | hlavni routy 155/155 | `GAPS.md`: GOOSE doprovod, body bosse, TOKEN flash/reload | zadny vedomy gameplay placeholder v TOWN |
| P4 | hudba a zvuk | prehrava se jen `BIGEXPL.SND` | chybi procedurarni engine, mapovani udalosti a arbitraz 4 kanalu | cely TOWN od startu po bosse ma hudbu i vsechny efekty z originalu |

### Stav zakladu rendereru (2026-08-29)

Indexova cesta uz neni jen pomocny experiment. Testovane stavebni bloky jsou:

- paletove nezavisly dekoder a blitter logickych `.LIN` snimku vcetne
  retezeni, signed anchoru, transparentnosti a orezani,
- kompilator 16 RGB12 barev pro kazdy vystupni scanline z raw `.PAM`
  checkpointu,
- presny nibble fade v poradi cerna -> bila.

Regrese hlida skutecnych 13 TOWN checkpointu, obe hranice palety v uvodnim
okne a dvoudilny `JEEPHELI.LIN#1`. `renderMap` dual-writeuje indexovou mapu
i historicky RGBA oracle a viditelne staticke pozadi se uz kazdy frame
barvi z `mapIndex` podle presne Copper palety radku. Zname okno pres hranici
checkpointu ma proti spravnemu oracle 0 rozdilnych bajtu; legacy cesta se v
nem lisila. Dalsi krok je stejne indexove slozeni dynamickych BOBu, aby
paleta stredu okna mohla zmizet uplne.

**D1 je pripraven bez prepnuti runtime:** ciste helpery uz reprodukuji
unsigned depth klic a poradi fronty `0x481a`, projekci stinu z
`0x6364..0x638c`, cookie-copy `0x0FCA` i nepruhledny clear vsech bitplanu na
index 0 pres `0x0B0A`. Regrese sklada skutecne snimky FODDERA, MILL,
JEEPHELI a POPUP do indexoveho bufferu a hlida poradi i hash. Viditelna cesta
stale pouziva puvodni Canvas pruchody; stiny a specialni BOB mintermy se
prepnou spolecne az po jejich uplnem auditu.

HUD font, format a 352x8 maska jsou bitove uzavrene. Plna RGB kompozice ma
jeden externi stavovy blocker: `AMPROG.OBJ` nikdy nezapisuje COLOR20/24/28,
takze jejich resetovou/zdedenou hodnotu je nutne jednou zmerit v bezicim
originalu. Do te doby se `0x000` smi pouzit jen jako explicitni cold-boot
politika, ne vydavat za hodnotu odvozenou z programu.

Audit specialnich vrstev pred runtime switchem navic uzavrel, ze hracovy
BULLET#14, cannon a druhy tik PLOP jsou HW sprity, kdezto HOMING je bezny
BOB v COLOR00–15. Black fade HW sprite zaznamy vubec nezaradi; white fade je
nemeni. Zbyva implementovat globalni sprite-bank allocator, mapovou mutaci
decalu, zachovani `z`/flag provenance explozi, kompletni ctyrdilny GOOSE a
overit pomocny `0xA0` prepass pro objektovy flag b0. Dokud tyto polozky
nemaji fixture, plny viditelny BOB switch zustava zamerne vypnuty.

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
- **PLOP — uzavreno**: `0x85f0` / `0x861e` ukaze jeden tik `PLOP#0`,
  druhy tik `BULLET#2` a pak objekt ukonci; prepis i regrese sedi.
- **kanonovy granat — uzavreno**: faze je stav kazdeho objektu prepinany
  na `0x96b4`, ne globalni parita herniho tiku; accel i straight cesta
  maji regresi vcetne poradi pohyb -> akcelerace a budgetu strela+PLOP.
- **GOOSE — uzavreno 2026-08-30**: blikani `0xc7fc`, prechod
  `0,0,1,2,3,4,5` s periodou 10 z `0xc82e`, rotor `0x93e2`, cekani na
  `+276 == 0` (`0xc85e`), dokovani `0xcb78`, pod `0xcaac` s animaci
  `GOOSE#8..11` (`0xcae2`) a odhozeni casti `0xca5e` jsou v prepisu;
  regrese v `tools/uitest.py`.

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
ROTOBASE, FLAME/CAMOGUN, TOKEN a GOOSE. Teprve po stabilizaci RNG ma smysl
porovnavat cely level jednim dlouhym zaznamem.

## Definition of done pro TOWN

- zadny stav `unimplemented`, `missing-dispatch` ani vedomy vizualni fallback,
- vsechny animace a pomocne objekty maji adresu zdroje a regresi,
- pixelove checkpointy jsou opakovatelne ze stejneho input tape,
- renderer zachovava rasterove palety, poradi, stiny, HUD a fade,
- pohyb, kolize, HP, body, dropy a casovani sedi s 68k kodem,
- hudba a zvuky sedi udalosti, casovanim, prioritou i kanalovou arbitrazi,
- `tools/check.py` a `tools/uitest.py` prochazeji bez chyb.
