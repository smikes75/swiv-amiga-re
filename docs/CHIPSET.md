# Graficka vrstva: kdo sahá na hardware

Zmereno 2026-09-09 hookem na `Memory::pokeCustom16` ve vAmize (patch
`tools/vamiga-regtrace.patch`, expozice `wasm_regtrace*`, cteni
`VA.regTraceRead()` v `web/vacmp.html`). Kazdy zaznam nese registr,
hodnotu, **PC instrukce**, priznak CPU/Agnus a rastrovou pozici.

## Zasadni oprava predchoziho zaveru

Hledani podle absolutnich adres `0xdffXXX` v disassembly naslo v
`AMPROG.OBJ` jen Paulu a dve barvy, z cehoz jsme usoudili, ze grafika je
mimo herni kod. **Bylo to spatne.** Blitter, bitplany, sprity i copper
programuje `AMPROG.OBJ` sam - jen pres **bazovy registr** (`a4` = `0xdff000`,
zapisy typu `movew %d0,%a4@(88)` = `BLTSIZE`), takze je grep podle
absolutnich adres nenajde.

## Mapa: co kde lezi (offsety v `AMPROG.OBJ`)

| oblast | offsety | co dela |
|---|---|---|
| blit rutina A | `0x40e0`..`0x4158` | `BLTCON0/1`, masky `BLTAFWM/ALWM`, moduly, ukazatele `A/B/C/D`, spusteni `BLTSIZE` na `0x4158` |
| blit rutina B | `0x41f0`..`0x4218` | smycka pres seznam; moduly `BLTAMOD/DMOD` z dat, spusteni na `0x4218` |
| cekani na blitter | `0x41a4` | test `DMACONR` bit 13 (`0x40ec`), pri zaneprazdneni `st fp@(162)` |
| bitplany | `0x445c`, `0x44a0`, `0x593a`, `0x593e` | `BPLxPT`, `BPLCON0` |
| copper | `0x5d4e` | `COP1LC` |
| sprity | `0x5d76`..`0x5dce` | `SPRxPT`, `SPRxPOS/CTL` - to je allocator, ktery `GAPS.md` zna jako `0x3d00/0x3d4e` |
| Paula | `0x6f8`..`0x77e`, `0x4ac2` | `AUD0-3`, jedine misto s absolutni adresou |

## Objem prace za snimek

Trasa peti snimku bezne hry (TOWN, ~20 s od startu):

| | pocet |
|---|---|
| zapisu do custom registru celkem | 2427 |
| z toho CPU | 2190 |
| z toho Agnus (copper) | 237 |
| spustenych blit operaci (`BLTSIZE`) | 236, tedy **~47 na snimek** |
| zapisu do bitplanovych registru | 122 z 46 mist kodu |

Blity se spousti ze tri mist: `0x4218` (120x), `0x4158` (104x) a `0x404c`
(12x) - odpovida to trem druhum operaci (pravdepodobne restaurace pozadi,
kresleni BOBu a jeste jedna zvlastni cesta).

## Co z toho plyne pro plan

Faze 1 z `docs/PLAN-GRAFIKA.md` je tim **splnena**: graficky kod nemusime
hledat v neznamych castech pameti, je v `AMPROG.OBJ` a mame jeho adresy.
Zbyva jej precist (faze 2 a 3) - to uz je bezna transkripce ze zname
adresy, stejna prace jako u chovani objektu.

Nastroj sam je herne agnosticky: u jineho titulu rekne totez za jeden beh.


# Faze 2: display (2026-09-09)

Nastroj `tools/copper.py` vytahne z beziciho originalu aktivni copper list
(`COP1LC`) a rozebere jej. Je herne agnosticky - bez argumentu cte original
pres harness, s argumentem rozebere ulozeny soubor.

## Copper list SWIV (TOWN, 85 instrukci)

```
$0071D8  MOVE  INTREQ  <- $8010
         MOVE  BPL1PT  <- $02C1EC     ctyri bitplany hry,
         MOVE  BPL2PT  <- $02F8EC     krok 0x3700 = 14080 B
         MOVE  BPL3PT  <- $032FEC
         MOVE  BPL4PT  <- $0366EC
         MOVE  SPR0PT..SPR7PT         osm hardwarovych spritu
         MOVE  COLOR00..COLOR15       paleta hry
         MOVE  BPL5PT  <- $0000 48D8  paty bitplan (HUD)
         MOVE  DMACON  <- $8120
         MOVE  BPLCON0 <- $4200       4 bitplany
         MOVE  BPLCON1 <- $0000       zadny jemny posun
         MOVE  BPLCON2 <- $003F
         MOVE  BPL1MOD <- $0004       radek 44 B, zobrazi se 40 B
         MOVE  BPL2MOD <- $0004
         MOVE  DIWSTRT <- $2C81 / DIWSTOP <- $2CC1
         MOVE  DDFSTRT <- $0038 / DDFSTOP <- $00D0
WAIT VP=44   COLOR13/14/15 (horni okraj)
WAIT VP=52   BPLCON0 <- $5200         **prepnuti na 5 bitplanu = HUD**
WAIT VP=53   COLOR16 <- $0AAE
WAIT VP=54   COLOR16 <- $0CCF         gradient HUD radku
WAIT VP=57   COLOR16 <- $0AAE
WAIT VP=58   COLOR16 <- $088D
WAIT VP=59   BPLCON0 <- $4200         zpet na 4 bitplany
WAIT VP=134  COLOR13/14/15 (jina sada)
WAIT VP=197  BPL1..4PT <- $02A538 ..  **prepnuti bitmapy pro spodni cast**
END
```

Tim je overeno, co `docs/HUD.md` odvodil z obrazku: patek bitplanu je
skutecne jen v pasu HUD (`VP=52..59`) a `COLOR16` v nem meni ctyri hodnoty.

## Scroll: hruby posun ukazatele, zadny jemny

Zmereno po ctyrech VBL (= 1 px kamery):

| VBL | `BPL1PT` | kamera | zmena |
|---|---|---|---|
| 0 | `$02C1EC` | -6169 | |
| 4 | `$02C1C0` | -6170 | **-44 B** za -1 px |
| 8 | `$02C194` | -6171 | -44 B |
| 12 | `$02C168` | -6172 | -44 B |

**Jeden pixel scrollu = posun ukazatele o presne jeden radek bitmapy
(44 B).** `BPLCON1` zustava `$0000`, takze zadny jemny posun se nepouziva -
u svisleho scrollu to ani nejde, `BPLCON1` posouva vodorovne.

Zapisuji `BPLxPT` mista `AMPROG +0x415e`, `+0x4162`, `+0x4482`, `+0x48c0`,
`+0x5abe` a `+0x5912`.

## Co z toho plyne pro vylepseni

**Svisly scroll originalu je po celych pixelech z principu.** Amiga umi
jemny posun jen vodorovne (`BPLCON1`); svisle se musi bud posunout ukazatel
o cely radek, nebo bitmapu prekreslit. SWIV proto scrolluje 0,25 px/VBL tak,
ze kazdy ctvrty VBL posune ukazatel o radek - a mezi tim obraz **stoji**.

Nas "plynuly rezim" tedy nedela nic, co by original delal jinak; dela neco,
co puvodni hardware neumel. To je legitimni vylepseni a ted je i podlozene:
logika (0,25 px/VBL) zustava, meni se jen zobrazeni.

Stejne tak vetsi barevna hloubka: paleta je 16 registru se ctyrmi copper
splity, ktere jsou obchazenim limitu OCS, ne hernim zamerem.


# Faze 3: kresleni objektu (2026-09-09)

`tools/blitlog.py` slozi z trace jednotlive blit operace: blitter se
programuje po registrech a spousti zapisem do `BLTSIZE`, takze jedna
operace je "stav registru v okamziku toho zapisu". Skript vyda minterm,
zapnute zdroje, rozmer, moduly, ukazatele a PC.

## Co SWIV s blitterem dela

Zmereno na ctyrech snimcich bezne hry (TOWN, ~20 s od startu):
**236 operaci, tedy 59 na snimek**, ve trech druzich:

| minterm | zdroje | pocet | odkud | vyznam |
|---|---|---:|---|---|
| `0xF0` | `AD` | 120 | `AMPROG +0x4218` | `D = A`, cista kopie |
| `0xCA` | `ABCD` | 56 | `AMPROG +0x4158` | `D = A?B:C`, **cookie-cut** - klasicky BOB s maskou |
| `0x0A` | `ACD` | 48 | `AMPROG +0x4158` | `D = C & ~A`, vymaskovani |
| `0xA0` | `AD` | 12 | `AMPROG +0x404c` | `D = A & C` |

To je ucebnicovy BOB systém se **zalohou pozadi**: kopie `0xF0` ulozi a
vrati pozadi, `0xCA` nakresli sprite pres masku, `0x0A` vymaskuje. Ctvrta
cesta (`+0x404c`) je zvlastni a jeste nema jmeno.

Rozmery odpovidaji spritum hry: nejcasteji 32x32 (76x), 48x33, 48x34 a
male 16x4 a 16x7 (strely a jiskry).

Blit rutina si drzi `a4 = 0xdff000` a zapisuje pres nej; smycka na
`+0x415e` posouva ukazatel o `0x3700` = 14080 B, tedy o cely bitplan -
kazda operace se opakuje pro vsechny ctyri roviny.

## Tim je hotova mapa "co je ktery pixel"

- **teren** = ctyri bitplany na `$02C1EC` (krok 14080 B), scroll posunem
  ukazatele o 44 B na pixel;
- **HUD** = paty bitplan na `$000048D8`, zapnuty jen v pasu `VP=52..59`;
- **BOB** = to, co vznikne blitem `0xCA` z `AMPROG +0x4158`;
- **hardwarove sprity** = osm kanalu nastavenych v copper listu, spravuje
  je `AMPROG +0x5d76..0x5dce`.

Pro 2,5D nebo 3D efekty to znamena, ze vrstvy jsou oddelitelne uz na urovni
dat: teren je bitmapa, objekty jsou seznam blitu se znamou pozici a
velikosti, strely jsou sprite kanaly. Neni potreba nic odhadovat z obrazu.


# Faze 4: nastroje (2026-09-09)

Z fazi 1-3 vznikly ctyri nastroje a zadny neni vazany na SWIV:

| nastroj | co dela |
|---|---|
| `tools/vamiga-regtrace.patch` | hook na `Memory::pokeCustom16`; kazdy zapis do custom registru s PC, zdrojem (CPU/Agnus) a rastrovou pozici |
| `tools/copper.py` | disassembler copper listu - cte zivy original nebo soubor |
| `tools/blitlog.py` | slozi z trace jednotlive blit operace: minterm, zdroje, rozmer, moduly, ukazatele, PC |
| `tools/layers.py` | slozi snimek primo z chip RAM podle copper listu, bez emulatoru |

U jineho titulu reknou prvni tri totez za jeden beh. `layers.py` je zatim
rozpracovany - viz nize.

## `layers.py`: 99 % shody, model displeje overen

Snimek slozeny **primo z chip RAM podle copper listu, bez emulatoru a bez
herniho kodu**, souhlasi se snimkem emulatoru na **99,0 %** pixelu
(81073 z 81920, tolerance 20 na kanal).

Tim je cela analyza z fazi 1-3 overena prakticky: kdyz z ukazatelu, palet,
splitu a modulu slozime obraz a ten sedi, znamena to, ze model displeje je
spravny.

Cesta k tomu cislu stala za ctyri opravy, vsechny v nastroji, zadna v
pochopeni hardwaru:

| oprava | shoda |
|---|---|
| vychozi stav | 21 % |
| gamma `VAMIGA_LUT` misto `nibble * 17` | 33 % |
| spravny vyrez textury `(62, 18)` | 73 % |
| adresovani po copper splitu | **99 %** |

Posledni oprava je ta zajimava: `BPLxPT` nastavene splitem plati **od toho
radku**, ne od zacatku obrazu. Pocitat adresu z absolutniho `y` znamenalo
cist dolni pulku obrazu o `y_splitu * 44` bajtu vedle. Rozdilova mapa to
ukazala okamzite - horni polovina cerna (shoda), dolni cervena.

Sprity jsou doplnene podle HRM (`SPRxPOS`/`SPRxCTL`, dve datova slova na
radek). Barvy `COLOR17-31` copper list nenastavuje, zapisuje je CPU primo
(`0x2afc`), takze se berou z trace. Kresli jen 76 pixelu - v SWIV jsou
sprity vyhradne strely, vrtulnik i nepratele jsou BOBy.

**Vyvracena hypoteza.** Rozdil jsem nejdriv pripisoval casovemu posunu, ze
se bitplany ctou po dobehnuti snimku. Zmereno pres `wasm_step_line` na `VP`
0, 44, 150, 260 a 300: shoda vsude 20-21 %, tedy na okamziku cteni nezavisi.
Chyba byla v barvach, vyrezu a adresovani.


# Faze 5: prvni vylepseni nad ramec hardwaru (2026-09-10)

## Mekke stiny podle vysky

Hra uz stin podle vysky odsazuje - `bobShadowAnchor` je `x + z/2, y + z`,
tedy jednoducha 2,5D projekce. Co Amiga neumela, je **mekkost a
pruhlednost**: blitter zna jen plnou masku, stin se kresli jako pevny
paletovy index 0.

Volitelne (`mekke stiny` v panelu, jen v plynulem rezimu) se tataz vyska
promitne i do rozostreni a pruhlednosti:

```
blur  = min(6, z / 6)          px
alpha = max(0.25, 0.75 - z/90)
grow  = 1 + min(0.35, z / 120)
```

Zadna nova data k tomu nebyla potreba - `z` uz vozi kazdy stinovy zaznam,
protoze jej hra pouziva k odsazeni. Efekt je vychozene **vypnuty**, takze
kontrakty `compare.py`, `smoothtest.py` a `uitest.py` zustavaji zelene.

Je to zaroven ukazka, k cemu byla analyza dobra: vrstvy jsou oddelene
(stin je zaznam `kind: "shadow"`, ne pixely v terenu), takze se da sahnout
prave na nej a nic jineho nezmenit.


## Svetlo shora

Druhe volitelne vylepseni: BOB objektu se ztmavuje smerem dolu, sila podle
tehoz `z`, ktere rídi stin (`min(0.45, 0.12 + z/160)`). Objekt u zeme je
tim plochy, letec ma vyraznou horni hranu.

Amiga to neumela z principu: kazdy pixel BOBu je paletovy index a blitter
s nim nepocita, takze stinovani by znamenalo mit kazdy objekt nakresleny
vickrat v ruznych odstinech - a paleta ma 16 mist.

Prvni verze hranu take **rozsvecovala** (`k = 1 + lit*(0.5-t)*2`), jenze
svetle barvy pretekly na 255 a bily vrtulnik hrace se slil do siluety. Ted
se jen ztmavuje (`k = 1 - lit*t`), takze se nic neztrati.

Obe vylepseni jsou vychozene vypnuta a plati jen v plynulem rezimu.


## Hloubka ostrosti

Kamera je nad hrou zaostrena na rovinu objektu, takze teren pod nimi je
mirne mekci (`blur(0.7 / S)` pred kreslenim terenu, pak `filter = none`
pro objekty). Amiga nic takoveho neumela: obraz je slozeny z pevnych
bitplanu a zadny filtr mezi nimi a monitorem neexistuje.

**Zmereny dopad efektu na obraz** (zmrazena hra, TOWN):

| efekt | zmenenych pixelu | vyrazne |
|---|---|---|
| hloubka ostrosti | **32,9 %** | 8,9 % |
| mekke stiny | 4,3 % | 2,5 % |
| barevna hloubka | 2,7 % | 2,7 % |
| svetlo shora | 2,5 % | 2,2 % |
| hladke pozadi | 1,7 % | 1,6 % |

Cislo je duvod, proc si uzivatel prvnich ctyr efektu nevsiml: sahaji na
objekty nebo hrany, ktere zabiraji pár procent obrazovky. Hloubka ostrosti
je prvni, ktera se dotkne terenu, tedy 90 % obrazu.

Pouceni pro dalsi efekty: **nejdriv zmerit, jakou plochu efekt zasahne**,
teprve potom jej nabizet jako viditelne vylepseni.

## Co z efektu zustalo (po zpetne vazbe 2026-09-10)

Uzivatel prosel vsech pet a rozhodl:

| efekt | verdikt |
|---|---|
| hloubka ostrosti | videt, hezke - **zustava** |
| mekke stiny | videt, hezke - **zustava** |
| prolnuti pohybu | neni vizualni efekt, pomahá plynulosti pri malem zvetseni - **zustava** s presnejsim popiskem |
| svetlo shora | "vypada divne" - **odstraneno** |
| barevna hloubka | rozdil neni videt - **odstraneno** |

Odstranene efekty jsou pryc i z kodu, ne jen z UI: `litObjects` a
`deepColor` vcetne modulace barev v `smoothSpriteCanvas` a interpolace v
`compileCopperPaletteLines`. Nechavat prepinace, ktere nic nedelaji, je
horsi nez efekt nemit.

Proc svetlo shora nefungovalo: lineárni ztmavovani spritu smerem dolu
funguje na velkych plochach, ale sprity v SWIV maji 16 az 48 pixelu na
vysku a jsou kreslene s tvrdou paletou. Gradient pres tak malou plochu
vypada jako spina, ne jako svetlo. Skutecne nasvíceni by potrebovalo znat
normalu povrchu, kterou z indexoveho spritu neziskame.

## Naklon vrtulniku (2026-09-13)

Sesty efekt vylepseneho rezimu. Zadani znelo "slo by prevzorkovat
a zvetsit rozliseni vrtulniku a tim umoznit animaci naklonu?". Odpoved
je ano, ale ukazalo se, ze na tenhle konkretni efekt prevzorkovani
potreba neni.

### Tri ruzne naklony, ktere se pletou dohromady

Na spritu 17x32 pri 10 stupnich:

| co | posun |
|---|---:|
| roll (naklon do strany, fyzikalne spravny) | 17 * (1-cos 10) = **0,26 px** |
| pitch (nos dolu pri rozjezdu) | 32 * (1-cos 10) = **0,5 px** |
| otoceni v rovine obrazovky | 16 * sin 10 = **2,8 px** |

Prvni dva jsou pod rozlisenim spritu, treti ne. Otoceni trupu by tedy
opravdu chtelo vyssi rozliseni - a poskodilo by pixel art.

### Rotor je oddelitelny BEZ ZTRATY

`JEEPHELI.LIN` obsahuje telo i rotor zvlast:

- `#0` = cele telo, 306 neprusvitnych pixelu, sedm barev
- `#5`..`#8` = samotne listy rotoru; cely snimek ma **jediny index 7**,
  protoze se kresli sekundarni cestou `0x0B0A`, ktera barvu zdroje
  ignoruje a zapisuje barvu 0. Je to maska, ne obrazek.
- ve slozenem snimku `#1`..`#4` jsou tytez pixely barvou 0

Slozeni `telo #0 + rotor #(4+i)` s pevnym posunem dava puvodni snimek:

| slozeny | rotor | posun | chybnych pixelu |
|---|---|---|---:|
| `#1` | `#5` | (+1, +1) | 1 ze 448 |
| `#2` | `#6` | (+1, +1) | **0** ze 429 |
| `#3` | `#7` | (0, 0) | **0** ze 406 |
| `#4` | `#8` | (+2, +2) | **0** ze 403 |

Zmereno i na hotovem obraze (zoom 1, vsech osm fazi animace): pri nulovem
naklonu se rozlozeny vrtulnik lisi od slozeneho o **0 pixelu v sedmi
fazich z osmi**, ve fazi 1 o dva (telo a jeho stin, kazdy o jeden bod).

### Co se naklani

Sklapi se **jen rotorovy disk**. Je to jednobarevna plocha, takze na nem
neni zadna kresba, kterou by preskalovani poskodilo - proto zadny
prevzorkovavac. Telo zustava pixel po pixelu nedotcene.

Disk lezi nad podelnou osou, kolem ktere se stroj naklani, takze se pri
naklonu o uhel `a`:

    hub vychyli vodorovne o  HELI_TILT_HUB * sin(a)   = 1,1 px
    disk zkrati v ose        cos(a)                   = 0,8 px na 32 px

Uhel se bere z **vlastniho pohybu hrace po obrazovce**, ne z posuvu mapy -
jinak by stroj trvale visel nosem dopredu. Plny vychyl odpovida plne
rychlosti vrtulniku, tedy `+356` = 768 v 16.16 = 3 px/tik (`0x9476`).

`HELI_TILT_MAX` je 13 stupnu. Zkouseno az do 22, kde uz to vypada, ze se
rotor od stroje odpojil.

Naklon se nabira exponencialne s konstantou ctyri tiky (80 ms) a krokuje
se **po ticich, ne po snimcich**, aby nezavisel na obnovovaci frekvenci
monitoru. Zmereno pri drzene klavese: 0 -> 0,25 -> 0,44 -> 0,58 -> ... ->
0,98 za ctrnact tiku, po pusteni zpet pod 0,02.

Je to ciste zobrazovaci stav na `state`, ne na `g`: do simulace ani do
`netStateHash` se nedostane, takze lockstep i sitovy kontrakt zustavaji
nedotcene.

### Kontrakt

`uitest.py` meri obe strany: pri nulovem naklonu nejvyse 2 zmenene pixely
(rozklad nesmi byt ztratovy), pri plnem aspon 100 (efekt nesmi byt jen
deklarovany). Overeno negativni kontrolou - po vynulovani posunu
v `HELI_ROTOR_PART` kontrakt spadne na `[0, 73, 0, 70, 0, 0, 0, 83]`,
tedy presne na trech fazich, ktere nenulovy posun potrebuji.

## Blitovaci rada `0x3e0c`..`0x4218` - prectena (2026-09-11)

Posledni neprectena cast enginu. Podnetem bylo hracske pozorovani, ze
v originale jezdi tanky **pod** porostem.

### Rozvrh

`0x3e0c` dostane BOB zaznam v `a0`, jeho grafiku vyhleda `0x48c0` do `a1`
a podle **priznakoveho bajtu `+21`** slozi do `fp@(236..248)` ukazatele
na ctyri rutiny. Pak `0x3ef0`..`0x3fca` spocita geometrii (orez na
`-32..320`, svisly orez proti `+16`/`+18`, shift `x & 15`, modulo 44 B na
radek, adresu v bitmape) a na `0x3fcc` se provedou **tri pruchody**:

    3fcc:  a1 = fp@(256)        ; baze obrazovky
    3fd0:  jsr fp@(248)         ; 1. pruchod
    3fd6:  jsr fp@(244)         ; 2. pruchod
    3fdc:  jmp fp@(240)         ; 3. pruchod = vlastni kresba

### Bity `+21`

| bit | rutina | vyznam |
|---:|---|---|
| 0 | `0x3fe2` | `BLTAPT` maska, `BLTCPT` obrazovka, `BLTDPT` `fp@(252)` (scratch 2002 B), minterm `0xA0` = A AND C → **ulozeni pozadi pod BOBem** |
| 1 | `0x4068` | tyz tvar s mintermem `0x0A` = NOT A AND C |
| 2 | `0x40a8` | **kolizni test**: minterm `0x50`, rovina podle `fp@(161)`; po `0x41a4` cte bit 13 stavu a nastavi `fp@(162)` |
| 3 | `0x405a` | jako 1, ale s posunem o rovinu (`+14080`) |
| 4 | `0x417c` | **zablesk**: roviny `0xFA, 0x0A, 0x0A, 0xFA` = plne barva **9** |
| 5 | `0x4174` | **stin**: vsechny ctyri roviny `0x0A` = vymaz na barvu 0 |
| 6 | `0x4100` | cil `fp@(264)` = **strip** misto `fp@(256)` = obrazovka |
| 7 | `0x416a` | `rts` - **nekresli vubec** (pouziva se s bitem 2 na ciste mereni kolize) |

### Vlastni kresba `0x4112`

Ctyrikrat (`dbf %d6` od 3) - jednou na kazdou bitplane - vezme slovo
BLTCON0 z tabulky vybrane `fp@(236)` a posune se o `+14080` na dalsi
rovinu. Tabulky:

    0x416c  0fca 0fca 0fca 0fca   USEA|USEB|USEC|USED, minterm 0xCA
    0x4174  0b0a 0b0a 0b0a 0b0a   USEA|USEC|USED,      minterm 0x0A
    0x417c  0bfa 0b0a 0b0a 0bfa   roviny 0 a 3 nastavit, 1 a 2 vymazat

`0xCA` je `(A AND B) OR (NOT A AND C)`, tedy cookie-cut. **Tim je
potvrzen model, na kterem stoji prepis**: bezny BOB = cookie-cut, stin =
vymaz na 0, zasahovy zablesk = plna barva 9 (v prepisu `BOB_FILL_INDEX9`).

### Fronty

`0x481a` vklada do seznamu **BOBu** `fp@(208)`, `0x4814` do seznamu
**dlazdic** `fp@(3564)`. Oba tridi vlozenim podle klice `+8`. Dlazdice
maji `+8 = (vrstva << 8) + poradi` a `+21 = 64` (bit 6 = do stripu);
`0x3480` seznam prochazi a blituje je do stripu, jak se mapa staveji.
`0x4874` prochazi seznam BOBu a kazdy da `0x3e0c`.

`0x4184` zapisuje do fronty obnovy: `(velikost, modulo, adresa)` s
citacem v `a1@(16)` a ukazatelem v `a1@(18)`.

### Co tim JESTE neni vysvetleno

**Prekryti objektu terenem.** Do seznamu dlazdic vklada jedine misto
(`0x36ea`, tvorba dlazdice), takze objekt se do nej nikdy nedostane, a
bit 6 (kresba do stripu) maji jen tri mista - `0x8992` (dekal `0x898c`),
`0x27c8` a `0xc716`. Zadnou cestou z teto rady tedy BOB za teren nejde,
a presto to original dela (viz `docs/GAPS.md`).

Zbyva projit **mechanismus obnovy** (`0x4184`, `0x4068`, `0x405a`) a jeho
souhru se stavitelem stripu `0x3422`/`0x34c6`.

### Prekryti objektu terenem - ZMERENO ZIVE, stale nevysvetleno

Aby nezustalo u dojmu ze snimku, je to zmerene. Snimek originalu
`build/zone/z_p45488.raw` (RIVER, horni radek 12663) obsahuje FLATTANK
na `x = 22`, `ry 2688`, tedy obrazovkove `x 8..38`, `y 22..65`. Proti
nemu se postavila **cista terenni vrstva prepisu** na tomtez radku
(`tools/align.py --snimek`, rezim bez objektu):

    obdelnik tanku 31x44 = 1364 px
      original ma TEREN (shodny s nasi terenni vrstvou): 1072 px (79 %)
      original ma neco jineho (tank):                     292 px (21 %)

Tank je tedy pod porostem, ne nad nim. Prekryvaji ho dve velke dlazdice,
ktere na nej obe doslapnou celou plochou:

    _JUNGLE#3  ry 2687 x 24  vrstva 2  ->  obrazovkove x -7..57, y -20..104
    _JUNGLE#2  ry 2702 x  8  vrstva 1  ->  obrazovkove x -23..41, y -35..89

**Zadna cesta z prectene blitovaci rady to nevysvetluje.** Objekt se do
seznamu dlazdic nedostane (jediny vkladajici `0x36ea` je tvorba
dlazdice), bit 6 maji jen tri mista (`0x8992` dekal, `0x27c8`, `0xc716`)
a tvorba objektu `0x3780` priznakovy bajt naopak NULUJE (`clrb
a0@(397)`), takze si bity nastavuje az korutina.

**Dalsi krok, ktery to rozhodne:** precist za behu originalu seznam BOBu
`fp@(208)` a u zaznamu toho FLATTANKu podivat se na jeho `+8` (klic
trideni) a `+21` (priznaky). Harness na to je - `tools/survey/tasks_live.py`
uz cte zive zaznamy uloh z chip RAM, staci ho rozsirit o tenhle seznam.
Ukaze se bud bit, ktery jsme neprecetli, nebo klic trideni, ktery objekt
posle pred dlazdice.


## Zivy odecet seznamu BOBu (2026-09-11)

`tools/survey/boblist.py` dojede v originalu na zadanou mapovou pozici a
precte z chip RAM obousmerne vazany seznam `fp@(208)` (BOBy), seznam
`fp@(3564)` (dlazdice) a okolni globaly. Vysledky na pozici 45488 (RIVER,
misto s prekrytymi tanky):

### Tri bitmapy, ne jedna

    fp@(256) obrazovka  popis 0018e8  bitmapa 01c938  radek 45489
    fp@(260) druhy      popis 001d26  bitmapa 02a538  radek 45489
    fp@(264) strip      popis 002164  bitmapa 038138  radek 45440

Rozestupy jsou presne `0xDC00` = 56320 B = ctyri roviny po 14080 B.
Prvni dve maji **tentyz radek** a nenulove citace obnovy (109 a 108),
treti je o 49 radku napred a citac ma nulovy. Je to tedy **dvojite
bufferovana obrazovka plus treti, prave staveny strip**.

### Zaznamy

23 BOBu, trideno sestupne podle klice `+8`:

| klic | gfx | co to je | `+21` |
|---:|---|---|---|
| 65535 | `0x1009` x5 | stiny letky | `0x21` = bit 0 + bit 5 (stin) |
| 32767 | `0x0027`/`0x0227`/`0x0427` | **tela FLATTANKu** | `0x01` |
| 32766 | `0x1003`/`0x0803`/`0x1a03` | jejich veze (MEDTANK.LIN) | `0x01` |
| 32735 | `0x1009` x5 | tela letky | `0x00` |
| 10010 | `0x1c01` | strela hrace | `0x00` |

84 dlazdic s klici 3556..3621 a `+21 = 0x40` (bit 6 = do stripu), presne
jak rika staticke cteni.

**Tank ma priznaky `0x01`, tedy jen bit 0 (ulozeni pozadi).** Zadny bit,
ktery by znamenal "kresli me pod teren", a jeho klic `32767` je radove
jinde nez klice dlazdic - seznamy jsou stejne oddelene.

### Zmereno poradne (a oprava drivejsich cisel)

Predchozi mereni (79 %, pak 75 %) byla **znehodnocena**:

1. **FLATTANK se pohybuje.** `+356 = 32` je 32/65536 px za tik; zaznam
   bezel 61631 snimku, coz je **30,1 px driftu**. Tank byl tedy o 30
   radku jinde, nez rikala mapa, a meril jsem vedle. Zivy odecet dal jeho
   skutecnou polohu (`x = 22`, radek 45560, tj. obrazovkove `y = 72`) a
   nezavisle hledani nejlepsi shody spritu ji potvrdilo (`y = 71`).
2. **Fade po skoku.** Nas srovnavaci render mel po `jumpMap` jeste
   nedobehly fade-in, takze byl tmavy a barvy nesedely.

Po oprave obojiho, nas render proti originalu na TEMZE miste a s
dobehlym fadem:

    neprusvitne pixely spritu FLATTANK#1 = 1330 px
      oba ukazuji tank:            904 px (68 %)
      u nas tank, u originalu ne:  426 px (32 %)

**Prekryti je tedy realne a ma asi tretinu spritu** - v obraze je to
zarostly levy pas a leva cast korby. Veze se to netyka: tu prepis kresli
spravne (`MEDTANK.LIN` snimky 4..19), coz zivy odecet take potvrdil.

### Stav

Mechanismus zustava nevysvetleny. Vyloucene je:

- klic trideni (seznamy BOBu a dlazdic jsou oddelene, klice radove jine),
- priznakove bity BOB zaznamu (tank ma jen `0x01`),
- zamena snimku (vsechny ctyri snimky FLATTANKu jsou skoro totozne),
- chybejici vez (kreslime ji),
- blikani pri rotaci bufferu (osm snimku po sobe je identickych).


## VYRESENO: objekty maji vrstvu a schovavaji se za dlazdice (2026-09-12)

Hrac ukazal, ze uz **v TOWN** jsou stromy kresleny pres budovy i pres
objekty. To dalo chybejici kousek.

**Mapa nese vrstvu i u objektu.** Parser ji cetl uz drive (`x >= 416`
snizuje vrstvu), ale prepis ji u objektu zahazoval. V TOWN maji objekty
vrstvy 1 (51x), 2 (59x) a 3 (45x); dlazdice `_DEADTRE` jsou promichane
ve vrstvach 1 az 4 s domy `_HOUSES` ve vrstvach 0 az 4. Dlazdice s NIZSIM
cislem lezi bliz divakovi, takze strom ve vrstve 1 prekryva dum ve
vrstve 3 - **a stejne tak objekt ve vrstve 2 nebo 3**.

V RIVERu to sedi na pozorovany pripad: FLATTANK ma vrstvu 2 a lezi pod
`_JUNGLE#2` (vrstva 1) a `_JUNGLE#3` (vrstva 2).

### Prepis (model zpresnen 2026-09-12 po druhem hracskem testu)

Prvni verze maskovala podle VRSTVY OBJEKTU z mapy. Hrac nahlasil divny
prekryv u vyjizdejiciho vlaku a u zavor - a prava pricina byla, ze tu
vrstvu ma jen mapovy zaznam. Deti a za behu vznikle casti ji nemaji,
takze u slozeneho objektu sla jedna cast pod porost a druha ne.

Zmereno proti originalu (FLATTANK v RIVERu, pozice 45488, poloha
nezavisle dohledana hledanim nejlepsi shody spritu):

    bez masky                              904 / 1330 =  68 %
    podle vrstvy objektu z mapy (byla 2)  1129 / 1330 =  85 %
    jen vrstva 1 prekryva                 1330 / 1330 = 100 %
    OSTRA nerovnost proti vrstve objektu  1330 / 1330 = 100 %
    prah 3 nebo 4                          648 / 1330 =  49 %

Prvni vyklad toho stoprocentniho vysledku byl **"popredi je jen vrstva
1"** - a byl SPATNE. V TOWN je ve vrstve 1 jen sest stromu ze ctyriceti
dvou, takze to maskovani prakticky vyplo a hrac hned nahlasil, ze tanky
zase jezdi pres stromy.

Spravne vysvetleni teze namerene stovky: tank ma vrstvu **2** a dlazdice
`_JUNGLE#3` **teze vrstvy 2** ho neprekryva, zatimco `_JUNGLE#2` ve
vrstve **1** ano. Nerovnost je tedy **OSTRA**:

    dlazdice prekryva objekt  <=>  vrstva dlazdice < vrstva objektu

To dava obe veci naraz: na referencnim tanku 100 % a v TOWN zustava
maskovani zive - z 291 vzorku objektu ve vrstve je 97 zakrytych vic nez
z desetiny, nejvic zakryty je z 59 %. S variantou "jen vrstva 1" by to
bylo 25 z 291.

Popredi jsou vrstvy 1 az 3. Vrstva 0 ne - razeni dlazdic ji dava
prioritu 5, tedy uplne dozadu; vrstva 4 je zem pod vsim.

**Kdo se maskuje, rika `+397` bit 0** - originalni priznak, ktery
nastavuje 28 mist v AMPROG.OBJ. Je **per uloha**, takze si ho nastavuji
i deti: `train` ma dve mista (lokomotiva `0x9b90`, vagon `0x9c4a`),
`tank` dve (korba `0x9f00`, vez `0x9fc8`), `plat` tri, `junhatch` a
`flame` po dvou, `swappad` dve. Mimo dispatch tabulku jeste dekal
`0x898c`, vez jeepu `0x89ee`, lod `0x8e88`, jeep `0x90f0` a cakance
`0x937a`. Slozeny objekt je tim maskovany cely.

Vsech 28 mist je prirazeno ke korutine, ve ktere lezi, a tim i k nasemu
kodu - cela tabulka je v `docs/GAPS.md`. Casti slozenych objektu jsou u
nas hazardy bez mapoveho zaznamu, takze vrstvu dedi po rodici
(`inheritedLayer`). Strely a stopy, ktere bit 0 taky maji, zamerne
nemaskujeme: odletuji pryc od strelce a vrstva rodice je jen zastupna
hodnota.

### Poctive priznani: vrstvu objektu original zahazuje

Ostra nerovnost potrebuje vrstvu OBJEKTU, a tu original z mapy **necte**.
V dekoderu je to videt cerne na bilem - objektova vetev `0x36fe`:

    371e:  0240 01ff   andiw #511,%d0      ; x na devet bitu, vrstva pryc
    3774:  3140 0140   movew %d0,%a0@(320) ; ulozi se jen x
    3780:  4228 018d   clrb  %a0@(397)     ; priznak masky se pri vzniku nuluje

Dlazdicova vetev `0x36c2` naproti tomu vrstvu z tehoz pole vytahne
(`while x >= 416: x -= 512; vrstva--`) a da ji do tridiciho klice `+8`.

Ta data ale v mape jsou a nesou signal - objektu s vrstvou 4 (tedy bez
zadneho 512-bloku) je napric vsemi sedmi urovnemi jen dvanact z 1497:

    uroven   objektu   vrstva 4 / 3 / 2 / 1
    TOWN        155       0 /  45 /  59 /  51
    DESERT      274       2 /  56 /  49 / 167
    GRASS       132       0 /  61 /   7 /  64
    RIVER       212       6 /  51 /  37 / 118
    ICE         367       3 /  79 /  35 / 250
    SCIFI       356       1 /  22 /  41 / 292
    BOSS          1       0 /   1 /   0 /   0

Editor tedy vrstvu u objektu vyplnoval, i kdyz ji hra pri dekodovani
zahodila. **Nase pravidlo je proto zastupne, ne mechanismus originalu**:
reprodukuje obraz (100 % na referencnim tanku), protoze designer objekty
umistoval konzistentne s okolnim porostem, ale cesta, kterou se hloubka
dostane do kresleni v originalu, zustava nenalezena. Kdyby se nasla,
tohle pravidlo se ma nahradit - ne doplnit.

Vsech dvanact checkpointu `compare.py` zustalo beze zmeny - v TOWN na
nich zadny objekt pod popredovou dlazdici neni, takze to tam nic
nezhorsilo ani nezlepsilo.

### Co z toho plyne pro blitovaci radu

Statickym ctenim rady `0x3e0c`..`0x4218` se mechanismus najit nedal a
ted je jasne proc: **neni v ni**. Poradi urcuje klic `+8` a vrstva se do
nej musi dostat driv, uz pri zakladani BOB zaznamu. Kde presne, zustava
otevrene - ale pro obraz uz to neni potreba, protoze vysledek je zmereny
a odpovida.
