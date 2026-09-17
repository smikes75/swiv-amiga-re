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

### Proc rotor sam nestacil (2026-09-13, druhe kolo)

Hrac nahlasil, ze naklon nevidi. Zmereno pri zvetseni 4x, kolik bodu
displeje se zmeni:

| zmena | bodu |
|---|---:|
| naklon rotoru (plny vychyl) | 2 544 |
| vlastni zmena faze rotoru mezi tiky | 7 904 az 9 536 |
| zmizeni rotoru (faze bez nej) | 5 152 |

Efekt se tedy utopil ve vlastni animaci: rotor se kazdy tik promeni
tri az ctyrikrat vic, nez cim ho naklon posune, a `HELI_SEQUENCE`
ho navic pulku tiku nekresli vubec. **Stabilni plocha, na ktere je
zmena videt, je telo** - to se mezi tiky nemeni.

Telo se proto zacalo hybat taky. Prvni pokus bylo otoceni v rovine
obrazovky o 8 stupnu (naklon pak hnul 8 633 body misto 2 544, tedy
stejny rad jako vlastni animace) - hrac ho uz videl, ale cetl ho jako
zataceni. Nahrazeno uklonem, viz nize.

Pri tom se naslo, ze `heliTiltParts` vracelo null ve ctyrech fazich
z osmi (ty bez rotoru), takze se telo pulku tiku kreslilo rovne a stroj
pri letu do strany blikal. Kontrakt ted meri vsech osm fazi.

### Otoceni nahrazeno uklonem (2026-09-13, treti kolo)

Hrac natoceni **videl**, ale cetl ho jako ZATACENI, ne jako naklon.
Otoceni je proto pryc a naklon se kresli jinak.

Z pohledu shora je videt HORNI strana stroje, takze se pri uklonu o uhel
`a` kazdy bod posune do strany o `vyska_nad_podelnou_osou * sin(a)`.
Rozdil mezi castmi je to, co oko cte jako uklon:

| cast | posun pri plnem vychylu |
|---|---:|
| rotor (nejvys) | +4 px |
| trup | +1 px |
| stin | -1,5 px |

Trup se tedy od sve skutecne polohy vzdali nejvys o **jediny pixel** -
to je zamer, protoze sprite trupu je to, podle ceho hrac miri a uhyba.
Rozpeti mezi rotorem a stinem je pritom 5,5 px.

Posun stinu na opacnou stranu je **vedoma stylizace**: fyzikalne by se
stin kazde casti posunul stejne jako ta cast. Ciste fyzikalni varianta
ale dava jen rozdil rotor - trup (3 px) a ten se, jak uz vime, utopi ve
vlastni animaci rotoru.

Naklon dopredu a dozadu je tyz kod v ose y, bez dalsi prace.

### Objekty na zemi dostaly hloubku ostrosti

Hrac nahlasil, ze "objekty lezici nebo vznikajici na zemi jsou ostre
jako puvodne". Mel pravdu: rozostril se teren a objekty na nem zustaly
ostre, coz rozbijelo iluzi.

Kamera je zaostrena na rovinu, ve ktere leti hrac (`z` = 32), takze
mekkost je `1 - |z| / 32`. Primy odecet po BOB zaznamech:

| zaznam | z | mekkost |
|---|---:|---:|
| `tank-hull`, `trilo` | 0 | **1,00** |
| `tank-turret` | 1 | 0,97 |
| `player`, `mama`, `air-fod` | 32 | 0,00 |
| stiny (vsechny) | - | 0,00 |

Stinu se to netyka, ten uz ma vlastni rozostreni podle vysky
(`mekke stiny`). Cena pri sedmi pozemnich objektech na scene: 10,37 ->
10,42 ms na snimek v headless Chromiu, tedy pul procenta.

### Podpixelove sprity (2026-09-13, ctvrte kolo)

Hrac: "objekty na zemi jsou ok, ale naklon neni videt, a oproti scrollu
pozadi mi to prijde takove trhane".

Trhani nebylo rychlosti, ale **rozdilem mrizek**. Krok mezi snimky pri
60 Hz, mereno na pozemnim objektu a na nakreslenem scrollu:

| zoom | krok pozadi | krok objektu |
|---|---|---|
| 4x | -0,208 px (plynule) | 0,25 / 0,5 px |
| 6x | -0,208 px (plynule) | 0,333 / 0,5 px |

Teren se pri zapnutem `prolnuti pohybu` kresli na ZLOMKOVOU polohu
(dvoubodove svisle prolnuti), sprity se ale kvantovaly na 1/S px, tedy
na cely bod displeje. Objekty proto po plynule jedouci zemi podkluzovaly.

### Tady ma prevzorkovani smysl

Minule bylo zmereno, ze zvetseni nejblizsim sousedem samo o sobe nemeni
nic (0 rozdilnych bodu ze 147 456). To plati porad - ale jen dokud se
vzorkuje taky nejblizsim sousedem. Ve dvojici s VYHLAZOVANIM je to
najednou uzitecne: sprite se zvetsi na rozliseni displeje a teprve pak
se kresli na zlomkovou polohu, takze se michaji **body displeje, ne
herni pixely**. Vnitrek spritu zustane pixel po pixelu tvrdy a rozmaze
se jen okraj o jeden bod displeje.

`upscaledSprite()` drzi zvetseninu u zdrojoveho platna (`_upsc`), takze
se stavi jednou na kombinaci sprite + operace + paleta.
`drawSpriteDevice()` prepne na souradnice displeje, a kdyz poloha na bod
displeje padne presne, jde puvodni cestou bez michani.

Zmereno po zavedeni - rozkmit kroku spritu mezi snimky:

| zoom | podpixel vyp | podpixel zap |
|---|---:|---:|
| 4x | 0,25 px | **0** |
| 6x | 0,167 px | **0** |

Pozadi ma rozkmit 0 v obou pripadech, sprity se mu tedy vyrovnaly.

Vedlejsi ucinek: **naklon je konecne videt**. Posuny 1 / 4 / -1,5 px se
pri kvantovani na cely bod displeje zaokrouhlovaly skoro k nule; ted se
kresli tak, jak jsou.

### Co to stoji a co to nerozbije

Hloubka ostrosti se pro sprity presunula do souradnic displeje
(`blurDev` v bodech displeje misto `/ S` v uzivatelskych). Cena celkem:
10,24 -> 10,31 ms na snimek pri sedmi pozemnich objektech v headless
Chromiu.

`smoothtest` bezi nove v tom, co se nasazuje (podpixelove sprity
zapnute). Pri alfa = 1 vychazi poloha spritu na cely herni pixel, takze
se kresli bez michani a rovnost s klasickym snimkem plati dal - mimo
obdelniky spritu je rozdil **0 bodu**. Uvnitr obdelniku vzrostl ze 364
na 925 bodu, coz je presne ten mekky okraj.

### Vlnky na vode (2026-09-14)

Hrac: voda v originale stoji, nesla by animovat? Ano, a technikou,
kterou Amiga pouzivala - cyklovanim palety. Jen ne globalne.

Zmereno, ktere paletove indexy kresli vodni dlazdice `_LAKE.LIN`
v RIVERu (64 dlazdic, 276 480 px): **14 na 57 %, 15 na 20 %, 13 na
15 %**, tedy 92 % plochy tremi indexy. Jenze tytez indexy pouziva
i `_CLAY` (21 % svych pixelu) a `_JUNGLE` (7 %) - globalni cyklovani
palety by rozvlnilo i jil a dzungli.

Odtud **maska vodnich dlazdic** (`waterMask`), stavena v `renderMap`
stejne jako `foreLayer`: dlazdice z `WATER_TILES` masku nastavuji,
kazda dalsi dlazdice nad nimi ji rusi. Zmereno v RIVERu: 252 855 bodu
na radcich 13505..14336.

### Cyklovani palety je tady principialne neviditelne

Prvni verze prehazovala tri vodni indexy mezi sebou. Technicky bez
chyby - 53 081 zmenenych indexu, 0 mimo masku - a hrac presto nic
nevidel. Duvod se nasel az merenim BAREV techto indexu pres vsechny
vodni radky ve hre:

| uroven | tri vodni barvy | rozpeti pres kanaly |
|---|---|---:|
| RIVER | (1,5,6) (1,4,4) (1,3,3) | 6 ze 45 |
| ICE | (11,11,13) (10,10,12) (9,9,11) | 6 ze 45 |
| SCIFI | totez | 6 |

Jsou to SOUSEDNI ODSTINY jednoho prechodu, kterym je nakreslena vlnkova
textura - lisi se o jeden az dva kroky v kanalu. Prehazovat je nemuze
byt videt nikdy, at je maska sebepresnejsi. Tri kola se ladila maska
a pritom byl slepy misto jinde: sam efekt byl principialne neviditelny.

### Posouvani textury

Vlny v dlazdici uz nakreslene JSOU, takze se jen posouvaji. Pohyb oko
zachyti i pri nizkem kontrastu a nepribude ani jedna nova barva - jsou
to tytez pixely, jen jinde. Posun je trojuhelnikova vlna -2..+2 px podle
radku (`WATER_BAND` = 5) a casu (`WATER_SPEED` = 4 tiky na krok); cte se
jen z pixelu, ktery je taky voda, aby se od brehu nepritahla zem.

Zmereno na hladine: mezi snimky se meni 3 500 az 7 500 bodu.

**Pouceni: ze je efekt spravne spocitany, neznamena, ze je videt.**
U kazdeho vizualniho efektu se vyplati zmerit i JEHO AMPLITUDU v tom, co
uvidi oko - tady staci bylo podivat se na barvy driv, nez se tri kola
ladi maska.

### Co je voda: tri pokusy, kazdy se mylil jinak

Prvni verze urcovala vodu podle JMENA souboru (`_LAKE.LIN`). Hrac poslal
snimek z ICE, kde je pul obrazovky vody a nic se nevlni - `_ARCTIC.LIN`
jsem podle jmena povazoval za snih, pritom je to hlavni vodni plocha
ICE (130 dlazdic). Zaroven se maskoval `_LAKE#4/5/11`, coz je breh.

Druhy pokus: podil indexu 13/14/15 na plose ramecku. Vyresilo ICE, ale
v GRASS oznacilo za vodu hneda pole `_CORN#8` a `_GREEN#17`. Ty indexy
totiz nejsou "vodni" - jsou to jen paletove prihradky a jejich barva
zavisi na urovni I NA RADKU MAPY:

    indexy 13/14/15 uprostred mapy
    TOWN    (A,9,7) (4,5,3) (4,3,1)
    GRASS   (6,5,1) (4,3,0) (3,1,0)     hneda
    RIVER   (0,6,5) (3,5,5) (1,3,3)     tyrkysova

Treti pokus: podle BARVY (modra prevazi nad cervenou). Vyresilo GRASS,
ale v DESERTu oznacilo `_RIGS#9` (125 dlazdic) a v ICE i led
`_ARCTIC#0` - tam, kde je cela paleta studena, je modre skoro vse.

Treti pokus byl PRUNIK obojiho: index 13/14/15 a zaroven barva na tom
radku modrejsi nez cervena. Na papire to vypadalo ciste - TOWN, DESERT
a GRASS bez vody, RIVER `_LAKE`, ICE `_ARCTIC#5`. Hrac to pak zapnul ve
hre a napsal: **"to se vlni v ICE a je to snih a ne voda"**.

Mel pravdu. Snih je totiz taky "modrejsi nez cervenejsi": `_ARCTIC#5` ma
index 14 = (10,10,12). Vykresleno se spravnou paletou vedle sebe je to
hned videt:

| dlazdice | barva indexu 14 | co to je |
|---|---|---|
| `_ARCTIC#5` (ICE, SCIFI) | (10,10,12) na VSECH 168 dlazdicich | svetle modrobila se sikmymi smouhami = **snih** |
| `_LAKE#0` (RIVER) | (1,4,4) | tmave tyrkysova = **voda** |

V ICE tedy zadna voda neni, je to cele zamrzle. Jedina vodni plocha ve
hre je jezero v RIVERu.

### Zadne automaticke pravidlo

Tri pokusy, tri ruzne omyly. `WATER_TILES` je proto obycejny seznam
a udrzuje se tim, ze se na plochu nekdo **podiva** - to je jediny
postup, ktery zatim nesehnal. Kdyz pribude dalsi vodni plocha, patri tam
az po vizualnim overeni.

**Pouceni: jmeno souboru neni mereni - a barevna heuristika taky ne.**
U veci, ktera ma jmeno "arctic", pomohlo az vykreslit ji a kouknout se.

### Mereni, ktere si samo vyrobilo poplach

Prvni overeni pocitalo zmenene body na HOTOVEM PLATNE a vyslo z nej,
ze se mimo masku meni 5 211 bodu - tedy ze efekt leze, kam nema.
Nelezl. Do porovnani plaven mluvi pruhledny HUD (voda pod nim
prosvita, coz je spravne) a prepocet palety po radcich.

Rozhodlo az mereni na INDEXOVEM poli, kde zadna z techto vrstev
nefiguruje: **46 975 zmenenych indexu, z toho 0 mimo masku.**

Pouceni: kdyz se meri efekt, ktery pracuje s indexy, ma se merit na
indexech. Hotove pixely nesou navic vsechno, co se s nimi pak deje.
(A nulovou hladinu mereni je potreba zmerit driv, nez se cislo cte -
tady vysla 0, takze cisla byla duveryhodna, jen merila neco jineho,
nez jsem myslel.)

### Stopy jemnejsi

Razitko `#40..#43` je pres dvacet pixelu dlouhe, takze pri rozestupu
sedmi pixelu se prekryvalo trikrat a pas vychazel uplne plny - hrac to
mel za prilis vyrazne. `TRACK_STEP` je proto 16: stopa je porad
souvisla (razitko je delsi nez rozestup), ale o dost lehci.

### Naklon potreti: zuzeni misto posunu (2026-09-13)

Hrac naklon porad nevidel. Zive mereni ukazalo, ze **chyba to nebyla**:
`heliTilt` zapnuty, zadne JS chyby a `heliTiltX` vyjede na plnou
jednicku za dvacet snimku:

    prubeh: 0 -> 0,9 -> 0,99 -> 0,999 -> 1 -> 1 -> 1 -> 0,237 -> 0

(Pokles je tim, ze vrtulnik dojel k okraji obrazovky a prestal se hybat;
naklon jede z rychlosti, takze je to spravne.)

Z plneho vychylu ale vzesel posun 1 px na trupu, 4 px na rotoru a
-1,5 px na stinu - a **na posun o par pixelu oko pri pohybujicim se
obraze nereaguje**. Otoceni (prvni verze) videt bylo, protoze menilo
TVAR siluety. To je docela jina kategorie signalu.

Hlavnim signalem je proto ZUZENI. Naklonenou vec vidi kamera shora
kratsi napric osy naklonu; sirka se nasobi `1 - HELI_SQUASH * |vychyl|`
s `HELI_SQUASH` = 0,2:

| cast | pri plnem vychylu |
|---|---|
| trup | 17 -> 13,6 px |
| rotorovy disk | 32 -> 25,6 px |

Posuny rotoru a stinu zustavaji jako doplnek, hlavni praci dela zuzeni.

Dve veci, ktere to dela lepsim nez posun:

- **Zuzeni nehybe stredem**, takze na rozdil od posunu vubec nelze
  o poloze. Sprite trupu je to, podle ceho hrac miri a uhyba.
- Hladke je jen diky podpixelove ceste; bez ni by se zuzeni o necely
  pixel projevilo vypadavanim sloupcu.

Naklon dopredu a dozadu je tyz vzorec v ose y - stroj se zkrati svisle.

**Pouceni: posun neni signal, tvar ano.** Pri navrhu efektu na malem
spritu se vyplati ptat, jestli se meni silueta, ne o kolik pixelu se
neco hne.

### Stopy vozidel (2026-09-13)

Hrac se ptal, jestli by za tanky mohly zustavat stopy. Original je MA,
jen je skoro nikdy neni videt.

`0xad30` (`trackzone`) je mapovy objekt, ktery otevre pasmo 600 px
vysoke; uvnitr nej necha vez tanku (`0xa000`) stopu kazdych 20 tiku
a jeep (`0x9172`) kazde 3 tiky. Dekal je `JEEPHELI#40..#43` a snimek se
vybira vzorcem `((uhel + 16) & 0xE0) >> 5 & 3`.

Zmereno pres celou mapu, 6000 tiku na uroven:

| uroven | tanku | `trackzone` v mape | zona se otevrela | vzniklo stop |
|---|---:|---:|---|---:|
| TOWN | 65 | 1 | ne | 0 |
| DESERT | 47 | 1 | ne | 0 |
| GRASS | 25 | 1 | **ano, y 16359..16959** | **149** |
| RIVER | 14 | 0 | - | 0 |
| ICE | 3 | 0 | - | 0 |
| SCIFI | 3 | 0 | - | 0 |

V RIVERu, ICE ani SCIFI ten objekt v mape vubec neni.

Ctyri snimky dekalu: `#40` jsou dva vodorovne pasy nad sebou (jizda do
stran - pasy tanku jsou kolmo na smer), `#42` dva svisle vedle sebe
(nahoru dolu), `#41` a `#43` uhlopricky. Vsech 149 stop v GRASSu bylo
`#42`, tedy tanky jedouci svisle.

### Rozsireni

Volba `stopy vozidel` je pusti i mimo pasmo. Drzi se STRANOU SIMULACE:
seznam zije na `state`, ne na `g`, takze se nedostane do `netStateHash`
ani nesahne na RNG a dva hraci po siti muzou mit kazdy jine nastaveni.
Snimek se voli puvodnim vzorcem, jen uhel neni z veze, ale ze smeru
pohybu. Vozidla: `tank`, `flattank`, `juntank` a jeep; stopa po kazdych
sedmi ujetych pixelech, strop 3000.

Pri tom se doplnil **orez dekalu podle viditelnosti** v obou
vykreslovacich cestach. Dekaly maji `life: Infinity`, takze jich za
dlouhou hru muzou byt tisice a slepe blitovani vsech by stalo cas; plati
to i pro puvodni kratery a stopy min.

### Past, do ktere se slaplo podruhe

Prvni verze podpixelove cesty si drzela zvetseninu u KAZDEHO platna
spritu. `smoothSpriteCanvas` ale zaklada nove platno pro kazdou
kombinaci sprite + operace + paleta a u maskovanych spritu je v klici
jeste poloha, takze vznika nove kazdy snimek. Do pameti se tim sypala
dve platna na maskovany sprite a snimek: v dlouhem behu **425 ms na
snimek** misto jedne milisekundy.

V `smoothSpriteCanvas` je na presne tohle varovani uz z drivejska
("s novym platnem na kazdy maskovany sprite stalo dvanact objektu na
scene 90,9 ms na snimek misto 1,3 ms"). Stejna past o patro vys.

Opraveno jednim sdilenym platnem (`state.spriteScratch`). Nulova alokace
za behu.

### Nejdrazsi vec v obraze jsou mekke stiny

Pri hledani te regrese se zmerilo neco jineho. Tataz scena v RIVERu,
17 stinu a 18 letcu na obrazovce:

| | ms/snimek |
|---|---:|
| mekke stiny vyp | 28,3 |
| mekke stiny zap | **192,3** |

Tedy zhruba 9,6 ms na jeden stin - `ctx.filter = blur(...)` se vola na
kazdy stin zvlast pri kresleni. V ridke scene (7 pozemnich objektu,
0 letcu) to nestoji nic, proto to drivejsi mereni nechytilo.

Da se to opravit: rozostreni zavisi jen na vysce (`min(6, z/6)`) a `z`
nabyva par hodnot, takze staci predrozostreny stin zakesovat misto
filtrovani pri kazdem kresleni. Zatim NEUDELANO.

Cisla jsou z headless softwaroveho platna, na GPU to bude radove
levnejsi - informativni je pomer, ne absolutni hodnota.

### Prevzorkovat kvuli ROTACI? Merenim vyvraceno

(Kvuli podpixelovemu umisteni smysl ma - viz vyse. Tohle je o rotaci.)

Puvodni uvaha byla, ze otoceni potrebuje vyssi rozliseni spritu.
Nepotrebuje. Zmereno na platne: **rotace spritu 1:1 a rotace jeho
ctyrnasobne zvetseniny nejblizsim sousedem daji pixel po pixelu TOTEZ** -
0 rozdilnych bodu ze 147 456 pri 0, 3, 8 i 15 stupnich. Platno vzorkuje
az v rozliseni displeje, takze predem zvetsovat nema co pridat; pri
zvetseni 6x vychazi zrno rotace stejne tak jeden bod displeje.

Zmenu prinese teprve **chytry** zvetsovac (Scale2x, hq4x, xBRZ), ktery
hrany dopocitava, nebo zapnute vyhlazovani - to se od rotace 1:1 lisi
v 12 tisicich bodu ze 147 tisic, tedy 8 % plochy. Oboji by ale dalo
vrtulnik z jine hry nez zbytek obrazu, ktery zustava tvrdy pixel art.
Zavedeno proto neni.

### Plynulost pohybu: neni co zlepsit

Logika bezi 50 Hz a vrtulnik 3 px/tik, tedy 150 px/s; kresli se
s kvantem 1/S px. Krok nakreslene polohy mezi snimky:

| zvetseni | 60 Hz | 120 Hz | 144 Hz |
|---|---|---|---|
| 1x (S=1) | 2 a 3 px, rozptyl **1,0** | 1 a 2 px | 1 a 2 px |
| 2x | 2,5 px, rozptyl **0** | 1,0 a 1,5 px | 1,0 a 1,5 px |
| 4x | 2,5 px, rozptyl **0** | 1,25 px, rozptyl **0** | 1,0 a 1,25 px |
| 6x | 2,5 px, rozptyl **0** | 1,167 a 1,333 px | 1,0 a 1,167 px |

Na 60 Hz monitoru je od dvojnasobneho zvetseni pohyb **naprosto
rovnomerny**. Zbytkovy rozptyl na 120 a 144 Hz je 0,17 az 0,5 px a je
principialni: kvantum 1/S px je presne jeden bod displeje, jemneji uz
to bez vyhlazovani nejde.

Co pusobi netrhane neni poloha, ale to, ze stroj nema zadne zrychleni -
`+356` se nastavi na 768 naraz (`0x9476`). To je chovani originalu
a menit ho by byla zmena hratelnosti; vizualni doklouzani by navic
odpojilo sprite od zasahove plochy. Vahu pohybu proto dodava naklon,
ne zmena polohy.

### Kontrakt

`uitest.py` meri obe strany: pri nulovem naklonu nejvyse 2 zmenene pixely
(rozklad nesmi byt ztratovy), pri plnem aspon 100 ve **vsech osmi fazich**
(efekt nesmi byt jen deklarovany a nesmi blikat). Overeno negativni
kontrolou - po vynulovani posunu v `HELI_ROTOR_PART` kontrakt spadne na
`[0, 73, 0, 70, 0, 0, 0, 83]`, tedy presne na trech fazich, ktere
nenulovy posun potrebuji.

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

## Ovladace: proc nefungovaly na Windows (2026-09-15)

Hrac hlasil, ze mu joystick na Windows nejede. Pricina je prozaicka.

**`navigator.getGamepads()` vraci RIDKE pole**, kde index je slot
ovladace, ne poradi pripojeni. Na Windows ovladac bezne pristane na
indexu 1 az 3, zatimco nula je `null`. Kod cetl natvrdo `pads[0]`
a `pads[1]`, takze takovy ovladac hru neovladal vubec.

Dalsi dve veci selhavaly mimo standardni mapovani (na Windows bezne
u DirectInput zarizeni):

- **krizovy prepinac na ose 9** misto tlacitek 12..15. Kodovani je uhel:
  -1 nahoru a dal po smeru hodin po 2/7, klidova poloha lezi mimo
  interval <-1, 1>.
- **tlacitka na jinych cislech.** Palba brala jen 0/2/7; u ovladace
  s jinym rozlozenim neslo vystrelit. Ted bere jakekoli tlacitko mimo
  smerovy kriz, kdyz mapovani neni `standard`.

### Vyber ovladani

Lista `ovladani` da kazdemu slotu rozbalovatko (automaticky / jen
klavesnice / konkretni ovladac) a vedle **zivy vypis toho, co hra
z ovladace opravdu cte** - sipky, palba, skok a priznak nestandardniho
mapovani. To je tam zamerne: bez neho se vzdalena diagnostika
"joystick nefunguje" vest neda, protoze kazdy ovladac hlasi jina cisla.
Volba prezije reload.

### Kontrakt

`uitest.py` overuje pet pripadu: ovladac na indexu 2 (nuly `null`), hat
nahoru, hat v klidu (nesmi hlasit nic), palba na netypickem tlacitku
u nestandardniho mapovani a rucni prirazeni ovladace #3 slotu 1.

Pri psani toho testu jsem se sam chytil do pasti: pomocna funkce mela
`mapping: map || "standard"` a prazdny retezec je falsy, takze se
z nestandardniho ovladace stal standardni a pripad "palba" hlasil
nepravem chybu. Kod byl spravne, test ne - rozhodlo az prime volani
`readPad`.

## Volba palety: hardware vs dobovy monitor (2026-09-15)

Prevod ctyrbitove slozky na osmibitovou byl roztrouseny na **trinacti
mistech** jako `n * 17`. Prvni krok proto bylo svest ho do jedine funkce
`rgb4()`; bez toho by se volba palety nutne nekde roztrhla.

**`hardware` je vychozi a presne `n * 17`** - tak to delaji emulatory
i nase baseline snimky, takze na tom stoji vsechny kontrakty. Overeno
na vsech 4096 kombinacich: zadna odchylka.

**`dobovy monitor` NENI mereni.** Zadny Commodore 1084 tu neni. Stoji na
dvou publikovanych cislech:

- **gama** CRT ma podle ITU-R BT.1886 gamu kolem 2,4, sRGB displej 2,2.
  Tytez hodnoty proto na CRT vypadaly ve stredech tmavsi.
- **bily bod** spotrebni PAL monitory (vcetne rady 1084) bezne jely na
  9300 K misto D65 6500 K. Bila tedy byla CHLADNEJSI, ne teplejsi, jak se
  casto predpoklada.

Retezec je fyzikalne serazeny: dekodovat gamou CRT do linearniho svetla,
tam posunout bily bod, teprve pak zakodovat gamou sRGB. Prvni verze
posouvala bily bod az nad gamou, coz efekt prehanelo a bila se orezavala
(255 v modre). Pomery jsou normovane tak, aby nejvetsi byl 1, takze nic
nepretece.

Zmereno: meni 4094 ze 4096 kombinaci, nic mimo rozsah, cerna zustava
cerna, bila 224,234,255, stredni sed 136 -> 113,118,128.

### Past, do ktere se slaplo

`setMonitorMode()` se vola hned pri definici (radek ~590), ale `const
state` vznika az na radku 1079. Prvni verze do nej zapisovala a stranka
padala na "Cannot access 'state' before initialization" - titulek se
vubec neobjevil. Stav volby proto zije v modulovych promennych, ne na
`state`.


## Hrany spritu: tri rezimy a cena predzvetseni (2026-09-15)

Hrac: "sprity oproti pozadi vypadaji prilis hranate". Ma to tri priciny
a jen jedna sla resit:

- hloubka ostrosti zmekcuje **teren**, hrace ne - to je zamer toho
  modelu, pozadi je dal a ma byt mekci;
- pozadi je ditherovane, takze se pri zvetseni rozpadne do jemneho sumu
  a pusobi plynule, kdezto sprity maji velke jednolite plochy a ostry
  obrys;
- podpixelove sprity vyhladily **pohyb**, ne hrany.

**Oprava drivejsiho tvrzeni.** Rekl jsem, ze prevzorkovani nic neda. To
platilo pro ROTACI (zmereno: 0 rozdilnych bodu ze 147 456) a pro
PODPIXELOVE umisteni (limit je bod displeje). Na vzhled HRAN se to
nevztahuje - tam smysl ma a byl to presne hracuv pripad.

### Co se vybira

Rozbalovatko `sprsel` ma tri polohy, obe upravy stoji na tomtez:

- **bez uprav** (vychozi) - nejblizsi predloze;
- **Scale2x** (AdvMAME2x) zdvojnasobi mrizku a schody rozdeli na
  polovicni, hrany ale nechava tvrde: porad je to pixel art, jen
  jemnejsi. Pracuje na INDEXECH, ne na barvach, takze rovnost je presna
  a nezavisla na palete radku a vysledek se obarvi beznou cestou;
- **vyhlazeno** vezme TUTEZ dvojnasobnou mrizku a na displej ji dotahne
  bilinearne. Bilinearka primo z mrizky 1:1 by pri S = 6 byla kase,
  z dvojnasobne uz drzi tvar.

Maskovane pozemni objekty (`fore`) se nezvetsuji: maska se cte
v souradnicich 1:1 a preskalovat ji by znamenalo prepocitat celou
mapovou masku.

Zmereno na vyrezu 44x44 px kolem vrtulnika pri zvetseni 6 (264x264 bodu
displeje, 69 696 bodu celkem):

| dvojice | rozdilnych bodu |
|---|---|
| bez vs Scale2x | 4 513 (6,5 %) |
| bez vs vyhlazeno | 10 571 (15,2 %) |
| Scale2x vs vyhlazeno | 6 821 (9,8 %) |

### Dve pasti

**Prvni verze "vyhlazeno" byla BITOVE shodna s "bez"** - 0 rozdilnych
bodu z 69 696. Sprite se totiz pred kresbou predzvetsuje nejblizsim
sousedem a na displej se pak dotahuje v pomeru 1:1, takze bilinearka
nema co michat. V tomhle rezimu se predzvetseni proto vynechava.

**Vychozi hodnota chybela.** `state.spriteScale` byla `undefined`
a podminka znela `!== "bez"`, takze se Scale2x zapinal i tam, kde ma byt
vypnuty. Chytil to kontrakt naklonu vrtulniku: rozklad na telo a rotor
prestal sedet (8 bodu misto 0). Volba ma ted vychozi hodnotu primo na
`state`.

### Predzvetseni je nejdrazsi vec v podpixelove ceste

Cena jednoho snimku, uroven 3, zvetseni 5, 1000 tiku napred, prumer
z 20 snimku, headless Chromium (tedy softwarovy rasterizer - na stroji
s GPU budou cisla nizsi, pomer ale zustava):

| poloha | bez | Scale2x | vyhlazeno |
|---|---|---|---|
| cela (`frac` = 0) | 2,20 ms | 2,31 ms | 2,89 ms |
| podpixelova (`frac` = 0,37) | 40,39 ms | 46,60 ms | 6,18 ms |

Na cele poloze se kresli 1:1 bez michani a je to zadarmo. Na
podpixelove se dotahuje ZVETSENE platno bilinearne a to je drahe: cena
roste s velikosti zdrojove bitmapy. "Vyhlazeno" je 6,5x levnejsi presne
proto, ze predzvetseni vynechava a bilinearne se dotahuje male platno.

Zmereno, co predzvetseni vlastne kupuje: kdyz se vynecha uplne a kresli
se primo nejblizsim sousedem, klesne snimek z 50,00 na 8,46 ms a obraz
se lisi v 57 804 z 2 048 000 bodu (2,82 %, max odchylka 176). Kupuje si
tedy **vyhlazeny okraj jednotlivych spritovych pixelu** pri podpixelove
poloze - nic vic.

### Cache zvetsenych platen

Zvetsena platna se ted pamatuji, ale az od DRUHEHO vyskytu tehoz platna.
Maskovane sprity, ktere se hybou, maji kazdy snimek nove platno; kdyby
se cachovala hned, zakladalo by se pro ne kazdy snimek nove zvetsene
platno - do te pasti uz jsem jednou slapl a stalo to 425 ms na snimek.
Pri prvnim vyskytu se proto porad kresli do sdileneho scratche.

Zmereno: 50,00 -> 41,24 ms na podpixelove poloze a 35,95 -> 2,20 ms na
cele, obraz BITOVE stejny (0 rozdilnych bodu z 2 048 000).

### Kontrakt

`tools/uitest.py` meri, ze vsechny tri rezimy davaji **tri ruzne
obrazy** (kazda dvojice se lisi aspon v 1 % bodu vyrezu) a ze vychozi
hodnota je `bez`. Je to hlavne negativni kontrola: obe pasti vyse byly
"volba je potichu bez ucinku".

Treti past byla v samotnem kontraktu: `S` se cetlo z `cv.width` JESTE
PRED prvnim `frame()`, jenze zvetseni se na platno propise az v nem.
`S` vyslo 1, vyrez byl kus pozadi a kontrakt hlasil 0 rozdilnych bodu -
tedy "volba je bez ucinku" na kod, ktery byl v poradku.

## Revize renderu po Opusovi (Fable, 2026-09-17)

Prohlednuto 92 commitu od posledni revize (`14a69fb`); do hloubky
teren/vrstvy, paleta, ovladace, hrany spritu a JEEP (ten je v
`docs/BEHAVIORS.md`, "Revize JEEP"). Tri veci se musely opravit hned,
vsechny tri zmerene.

### Cache zvetsenin sezrala 256 MB

Vcerejsi cache (`UPSCALE_CACHE`, promoce od druheho vyskytu, bez meze)
zmerena pres fade na startu urovne pri zvetseni 6, 900 tiku, dva snimky
na tik: **2 171 zvetsenych platen, 256,1 MB** (malych platen 4 348).
Klic maleho platna nese celou paletu radku, takze kazdy krok fadu je
nova varianta, kazda se pouzije dvakrat a uz nikdy.

Oprava: promoce az od TRETIHO vyskytu (prechodne varianty ji nedosahnou)
a mez 64 platen v LRU (`UPSCALE_LRU`); vyhozene platno pocita znovu od
nuly, takze stridajici sada nad mez nemuze roztocit alokaci na kazdy
snimek. Zmereno tymz skriptem po oprave: **64 platen, maximum 10,0 MB**
(na konci 8,3 MB), 256 MB -> 10 MB.

### Paleta "dobovy monitor" stala trojnasobek snimku

`rgb4()` se vola na kazdy pixel terenu (81 920x za snimek) a s
`Math.pow` uvnitr `monitorRgb` to bylo: original 4,90 -> 14,78 ms,
vylepseno 6,43 -> 20,71 ms. Ted je 4 096 slov predpocitanych v
`RGB4_LUT` pri volbe rezimu; trojice jsou sdilene (volajici je nemeni -
proverena vsech 10 mist). Po oprave: original 4,75 / 5,02 ms, vylepseno
5,50 / 5,43 ms (puvodni / crt).

### Podpixelova cesta "bez" spadla ze 42 na 6 ms - a neni jasne proc

Tabulka A/B (frac 0,37, S = 5, uroven 3, 1 000 tiku napred, prumer
z 20 snimku, headless):

| varianta | bez | Scale2x | vyhlazeno |
|---|---|---|---|
| pred revizi `cf2a273` | 42,29 | 53,55 | 9,74 |
| jen tabulka palety (stara cache) | 43,25 | 50,36 | 7,47 |
| jen omezena LRU (paleta s `pow`) | 7,70 | 40,12 | 7,51 |
| obe (ted) | 5,71 | 31,20 | 5,69 |

Na cele poloze (frac 0) je vsechno 1,5 ms. Ze omezena LRU pomohla
o rad, kdyz ta stara po promoci vracela totez vlastni platno, neumim
vysvetlit bez dalsiho mereni - je to ukol D v `docs/ZADANI-RENDER.md`.
Scale2x zustava drahe (31 ms): pri S = 5 je zbytek 2,5, predzvetseni
je jen 2x a 1,25x dotahuje bilinearka z velkeho zdroje - ukol B.

### Co jsem zkontroloval a nemenil

- **Vrstvy** (`+397` bit 0, 28 mist; `0x371e andiw #511` a `0x63c8
  tstb fp@(155)` v dumpu sedi). Model "ostra nerovnost vrstev" je
  priznany proxy, dokumentace to rika. Bez zmeny.
- **Ovladace**: ridke pole, hat na ose 9, volba slotu a jeji ulozeni -
  cteni kodu bez nalezu. Nestandardni mapovani bere za palbu jakekoli
  tlacitko pod 12, takze "skok" (1/3/6) zaroven strili; vedome.
- **Vlnky**: cte i pise jen uvnitr masky `_LAKE`; render-only (`g.tick`
  jen cte). Bez zmeny.
- **compare.py**: rohatka je na `whole` - ukol C v zadani.
- **Nepodivane do hloubky**: zvuky mimo TOWN (`766facb`), post-game
  statistika (`110bdba`), harness vAmiga (`8df90f1`), aktivacni marze
  (`8936c5d`), MEDTANK/armed/nacteni pozice (`083e7bc`, `da15e55`,
  `63c888c`). Kontrakty jsou zelene, ale cisla proti dumpu jsem
  neprechazel.

### Uklid

Do `cf2a273` se omylem dostaly dva PNG z pokusu (`nn_*.png`, 1,9 MB) -
`git add -A` v korenu. Odstraneny; pravidlo je v zadani (sekce 2, bod 8).

## Vykon vylepseneho rezimu (Opus, 2026-09-17)

Zadani `docs/ZADANI-RENDER.md`. Prvni nalez je ale v samotnem MERENI,
takze cisla ze zadani neplati.

### Past c. 1: `g.frac = 0.37` neni podpixelovy snimek, ale 18 kroku

`g.frac` je v SEKUNDACH a `TICK = 0,02`. `frame()` ma `while (g.frac >=
TICK) { g.frac -= TICK; step(g); }`, takze `g.frac = 0.37` odsimuluje
**18 tiku na snimek** - a protoze `bobPrev` se plni jen pri `stepped ===
1`, je to navic snimek BEZ interpolace. Vsechna dosavadni cisla "frac
0,37" merila simulaci a vicekrokovy snimek, ne podpixelovy render.

Spravne: `g.frac = alfa * TICK` a pred tim jeden snimek s `g.frac =
TICK` (aby vznikl `bobPrev`). Kontrola: `g.tick` se behem mereni nesmi
zmenit a `g.bobPrev` musi existovat.

### Past c. 2: bez vynuceneho flushe se rasterizace vubec nemeri

Chromium kreslici prikazy do platna jen ZAZNAMENAVA a rastruje je az
pri flushi. `performance.now()` kolem `frame()` proto meri jen JS.
Zmereno v teze scene:

| | bez flushe | s `getImageData(0,0,1,1)` |
|---|---:|---:|
| stiny vyp | 1,43 ms | 33,58 ms |
| stiny zap | 1,44 ms | 243,77 ms |

### Skutecna cena (RIVER, zvetseni 5, 1 000 tiku, prumer z 20 snimku)

Softwarovy raster (headless), 17 stinu a 18 letcu na scene:

| varianta | alfa 0 | alfa 0,37 |
|---|---:|---:|
| stiny vyp, hrany "bez" | 24,27 ms | 33,37 ms |
| stiny vyp, Scale2x | 24,20 ms | 32,91 ms |
| stiny vyp, vyhlazeno | 24,97 ms | 34,05 ms |
| stiny vyp, hloubka ostrosti vyp | 4,56 ms | 8,65 ms |
| **stiny zap** | **234,67 ms** | **255,11 ms** |

Tedy: **Scale2x neni drahy** (ukol B zadani stal na spatnem mereni),
zato **hloubka ostrosti stoji 20 az 25 ms** a mekke stiny 210 ms.

### A. Predrozostrene stiny - HOTOVO

Rozostreni `min(6, z/6)` i zvetseni `1 + min(0,35, z/120)` zavisi jen na
`z`, takze se pocitaji jednou do vlastniho platna (klic: platno stinu,
ktere uz nese paletu radku, + `z` + zvetseni) a kresli se hotove.
Rezerva `3 * blur` na kazde strane, jinak by se mekky okraj orezal.
Mez je v BAJTECH (12 MB), ne v poctu polozek.

| | alfa 0 | alfa 0,37 |
|---|---:|---:|
| stiny vyp | 25,20 ms | 33,58 ms |
| stiny zap, stara cesta | 237,78 ms | 248,44 ms |
| **stiny zap, predrozostrene** | **26,35 ms** | **36,92 ms** |

Stiny tedy stoji 3,3 ms misto 215 ms; cil zadani byl "pod 40 ms".

Pamet (900 tiku pres fade na startu urovne, zvetseni 6, dva snimky na
tik): cache stinu 12,0 MB / 47 platen (drzi se na strope), zvetseniny
9,5 MB / 64. Fade cache neboli: klic nese paletu radku, takze pri zmene
palety se stin prerozostri - zmereno ale, ze to nevadi (start urovne
24,47 ms, ustalene 22,95 az 36,56 ms, bily zablesk 37,25 ms).

**Shoda obrazu.** Zadani chtelo max 2 urovne na bod; to nejde, protoze
hotovy stin se na zlomkovou polohu dotahuje bilinearne, kdezto driv se
rasterizoval primo. Zmereno (RIVER, 17 stinu): lisi se 4,5 az 5,2 %
bodu, nad dve urovne 0,02 az 0,12 %, max 5 (GPU raster) az 6
(softwarovy).

Nekolik desitek bodu se lisi vic a ty jdou za STAROU cestou: `ctx.filter`
na zlomkove poloze ve skalovanem kontextu nechava v Chromiu na jednom
radku svetly pruh. Zmereno na radku 1058: stara cesta 113 106 95 103,
nova 28 17 0 12 - a teren tam ma presne 28 17 0 12. Artefakt tedy mizi.

### A2. Opraven zdvojnaseny stin pri Scale2x

Platno stinu prochazi Scale2x stejne jako telo (stin nema masku `fore`),
takze pri volbe Scale2x nebo vyhlazeno je dvakrat vetsi - a kresba brala
`cv.width` rovnou jako herni pixely. Zmereno: sprite 32x32, platno
64x64, stin se kreslil dvojnasobny. Regrese z `cf2a273` (vcerejsi volba
hran spritu). Ted se deli `cv._k`.

### Blur pod ~0,75 px je v softwarovem rasteru NIC, na GPU ne

Zmereno na cisté scene (cerny ctverec na bile):

| blur | headless shell (software) | nove headless + GPU raster |
|---|---|---|
| 0,5 px | beze zmeny | rozostreno |
| 0,7 px | beze zmeny | rozostreno |
| 0,8 px | rozostreno | rozostreno |

Plyne z toho, ze `DOF_BLUR = 0,7` na spritech a `DOF_BLUR / S = 0,14` na
terenu se v NASICH merenich neprojevi, u hrace na GPU ano. Pozor pri
cteni starsich cisel: "sprity bez DOF blur" davaly 0 rozdilnych bodu, a
presto usetrily 12,8 ms - filtrova vrstva se plati i tam, kde Skia blur
zahodi. (Vizualni DOF terenu delá hlavne `imageSmoothingEnabled`, tedy
bilinearni zvetseni, ne ten blur.)

### B. Scale2x na podpixelove poloze - NENI CO OPRAVOVAT

Zadani vychazelo z cisla "31,2 ms proti 5,7 ms", ktere vzniklo spatnym
protokolem (18 kroku simulace na snimek, bez flushe). Spravne zmereno
(RIVER, alfa 0,37, 17 stinu, po oprave stinu):

| zvetseni | bez | Scale2x | vyhlazeno |
|---|---:|---:|---:|
| 4 | 24,61 ms | 23,71 ms | 23,59 ms |
| 5 | 37,40 ms | 37,90 ms | 37,99 ms |
| 6 | 77,53 ms | **56,31 ms** | 59,28 ms |
| 8 | 121,82 ms | 122,26 ms | 114,46 ms |

Scale2x je vsude stejny nebo levnejsi; pri zvetseni 6 dokonce o tretinu
(zbytek po predzvetseni je 3 misto 6, takze se dotahuje mensi obraz).
Kod se nemenil. Kontrakt v `uitest.py` ted meri POMER v temze behu:
zadny rezim nesmi stat vic nez dvojnasobek rezimu "bez".

### C. `compare.py`: zarazka na terenu; FINAL zbyva

Zarazka byla na `whole`, ktere nese i objekty a HUD - tedy sum toho, co
se zrovna hybe. Ted stoji na `terrain` (bez HUD a HELI), `whole` se
vypisuje jen diagnosticky. Prahy jsou tesne pod zmerenymi hodnotami:

| checkpoint | terrain | zarazka |
|---|---:|---:|
| start / wave / death / respawn | 99,9 / 99,0 / 98,2 / 99,9 | 99,8 / 98,9 / 98,1 / 99,8 |
| t26 / t28 / t30 | 94,0 / 96,7 / 94,8 | 93,9 / 96,6 / 94,7 |
| grass / river / ice / scifi | 92,9 / 93,3 / 88,9 / 95,3 | 92,8 / 93,2 / 88,8 / 95,2 |
| desert | 95,7 | 95,6 |

V hlavicce `compare.py` i v `docs/GAPS.md` je ted veta, co procento je
(podil bodu shodnych na +-8 urovni v JEDNOM snimku) a co neni (mira
vernosti prepisu).

**Checkpoint FINAL se nepodarilo poridit.** Zjistilo se, kde vubec lezi:
`FINAL.PAM` ma jen 384 radku a v retezu od urovne 5 zacina na radku 5600
z 5984, takze v mapovych pozicich je to uzke okno **35543..35191**
(odvozeno z checkpointu `scifi`: pozice 37000 = radek 4175). Drivejsi
pokus s pozici 32188 mířil UZ ZA konec retezu - proto tehdy original
dojel na pozici 0 a snimek ukazoval zaviraci obrazovku.

Snimek ale porizuje emulator a ten potrebuje Kickstart v `~/Documents`,
kam proces nesmi (`Operation not permitted`). Prikazy jsou pripravene
v komentari u `CHECKPOINTS` v `compare.py`.

### D. Scratch cesta zvetsenin - ZADNY ROZDIL, byla to chyba mereni

Zadani zadalo vysvetlit, proc omezena LRU srazila podpixelovou cestu ze
42 na 6 ms. Odpoved: **nesrazila**. Cela tabulka v zadani vznikla
protokolem s 18 kroky simulace na snimek a bez flushe, takze merila
simulaci a alokace v JS, ne kresleni. Znovu zmereno spravne (RIVER,
alfa 0,37, stiny vypnute, ms na snimek):

| varianta | bez | Scale2x | vyhlazeno |
|---|---:|---:|---:|
| pred revizi (`cf2a273`) | 37,02 | 33,99 | 34,24 |
| jen tabulka palety | 34,10 | 40,01 | 33,90 |
| jen omezena LRU | 33,95 | 33,47 | 33,53 |
| dnes | 35,98 | 34,19 | 33,85 |

Vsechno je v sumu (+-4 ms). Co cache doopravdy delaji:

| | alfa 0 | alfa 0,37 |
|---|---:|---:|
| cache zvetsenin (promoce od 3. vyskytu) | 23,38 ms | 34,04 ms |
| bez cache (vzdy sdileny scratch) | 26,15 ms | 34,50 ms |
| cache hned od 1. vyskytu | 23,94 ms | 34,42 ms |

Tedy ~2,7 ms na cele poloze a nic na podpixelove. **Cache zvetsenin
tedy zustava hlavne kvuli PAMETI** (drivejsi neomezena verze sezrala
256 MB), ne kvuli rychlosti; prah tri vyskytu proti jednomu je take
v sumu, drzi se kvuli prechodnym variantam pri fade.

### Co se nepovedlo: predrozostrit i hloubku ostrosti

`ctx.filter` se vola i na kazdy rozostreny sprite a stoji to 12,8 ms na
snimek (35,35 proti 22,55 ms) za CTYRI pozemni objekty. Zkusil jsem na
ne tutez cache jako na stiny - a je to **HORSI**: 88,9 ms proti 35,4 ms.
Neni to rozostrenim (varianta, ktera do cache kreslila BEZ filtru, dala
85,8 ms) ani mijenim cache (9 polozek, 1,24 MB, stabilne) ani lenivou
rasterizaci (vynucene cteni po stavbe nepomohlo). Drahe je samo kresleni
z tech ctyr platen: 4 volani a 68 500 bodu displeje na snimek. Proc, to
nevim - zustava to otevrene a filtr se u spritu kresli dal.

### Kde cas konci dnes (RIVER, zvetseni 5, alfa 0,37)

| | softwarovy raster | SwiftShader "GPU" raster |
|---|---:|---:|
| vse zapnute | 35,4 ms | 439,6 ms |
| mekke stiny vyp | 39,4 ms (sum) | 426,5 ms |
| hloubka ostrosti vyp | 9,5 ms | 40,5 ms |
| stiny bez predrozostreni | 265,2 ms | 3 124,5 ms |

Po oprave stinu je nejdrazsi vec v obraze **hloubka ostrosti** (asi 26
z 35 ms). Cisla jsou z emulovaneho rasteru, takze absolutni hodnoty pro
hrace neplati - drzi jen pomery.
