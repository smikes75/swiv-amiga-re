# Plan: rozklicovat grafickou vrstvu

Stav k 2026-09-09. Cilem projektu neni emulator, ale (1) kompletni
disassembling a pochopeni hry, (2) nastroje pouzitelne i pro jine tituly a
(3) identicka rekonstrukce novymi technologiemi, ktera se pak da vylepsit
(plynulejsi scroll, nez umel puvodni HW, 2,5D nebo 3D efekty).

Tenhle dokument rika, co k tomu jeste chybi a v jakem poradi to udelat.

## Co uz mame

| oblast | stav |
|---|---|
| herni logika | 1497 objektu v 73 druzich, vsechny prepsane z konkretnich adres |
| planovac uloh | fronta `A6-698`, zaznam 308 B, PC na `+270`, marker inicializace `+534` |
| zvuk | cely engine az na uroven Pauliných registru, vcetne CIAB scheduleru |
| formaty dat | `.LIN`, `.PAM`, `.RAW`, komprese - overeno proti pameti behu bajt po bajtu |
| aktivace objektu | 980 z 981 presne na 0 px (`tools/spawncheck.py`) |
| dokumentace cipu | Amiga HRM 3. vydani v `reference/hw-docs/` (PDF + text + HTML) |

## Co chybi a proc je to zasadni

**Herni kod nekresli.** Zmereno: na ktere hardwarove registry `AMPROG.OBJ`
vubec sahá:

| podsystem | dotceno |
|---|---|
| blitter (`BLTCON`..`BLTSIZE`) | **0 z 14** |
| bitplany (`BPLCON`, `BPLxPT`, `DDF`, `DIW`) | **0 z 26** |
| copper (`COP1LC`, `COPJMP`) | **0 z 6** |
| hardwarove sprity (`SPRxPT/POS/CTL`) | **0 z 48** |
| Paula (`AUD0-3`) | vsechny |
| palety | 3 z 32 (`COLOR00`, `COLOR16`) |

Grafiku tedy dela nekdo jiny. Kandidati, ktere uz mame zmerene:
- **API knihovna zavadece**: 33 vstupu skokove tabulky na zapornych
  offsetech od `A6`, kod v `0x6e4..0x1052` (2414 B). Prosli jsme ji -
  planovac, alokace pameti, nacitani souboru, **zadny pristup k HW**.
- **`work/loader.bin`** (7424 B): jen `INTENA`/`INTREQ`.
- **`work/boot.bin`** (1024 B): nic.

Zbyvaji dve moznosti, ktere se musi rozhodnout merenim, ne dohadem:
copper list se nastavi jednou pri bootu a dal se meni jen data v RAM, nebo
je grafiky kod v casti pameti, kterou jsme jeste neprohledali (hledani
podle absolutnich adres `0xdffXXX` ho nenajde, kdyz pouziva bazovy registr).

**Nas renderer je proto funkcni nahrada, ne transkripce.** Kresli sprity do
canvasu tak, aby vysledek odpovidal, ale nedela to, co dela hardware. Proto
`compare.py` meri shodu obrazku (98-99 %) misto shody registru a proto v
`GAPS.md` stoji vety jako "presny fyzicky OCS Denise trik zustava
undocumented".

Pro cile projektu to znamena:
- **disassembling** neni kompletni - chybi prave tahle vrstva;
- **nastroje** resi logiku (baze A6, cteni uloh, parovani aktivaci), na
  grafiku nemame nic, a pritom u jine hry je to prvni, co potkate;
- **vylepseni** se bez toho navrhuji naslepo: k 2,5D efektu je potreba vedet,
  ktery pixel je bitplan terenu, ktery BOB a ktery hardwarovy sprite, kde je
  copper split a co drzi paletu.

## Faze 1: najit grafiky kod (1-2 dny)

Grepovani selhalo, protoze kod nejspis pouziva bazovy registr. Merit se
tedy musi za behu.

1. **Zapisy do registru pres vAmigu.** Rozsirit `web/glue.cpp` o hook na
   zapis do custom registru (vAmiga ma `pokeCustom`); zaznamenat pro kazdy
   zapis registr, hodnotu a **PC**. Tim vypadne presna mapa "kdo pise do
   `BLTSIZE`, `COP1LC`, `BPLxPT`, `SPRxPT`".
2. **Trasa jednoho snimku.** Pro jeden VBL ulozit poradi vsech zapisu.
   Z toho je videt struktura snimku: kde konci copper setup, kde zacina
   kresleni objektu, kolik blit operaci pripada na BOB.
3. **Vystup**: `docs/CHIPSET.md` s mapou "adresa kodu -> co dela".

Riziko: vAmiga muze mit zapisy schovane v inline funkcich; pak je potreba
misto hooku pouzit DMA debugger, ktery uz jadro ma.

## Faze 2: display (2-3 dny)

1. **Copper list**: najit ho v pameti (`COP1LC`), rozebrat instrukce
   (`MOVE`, `WAIT`, `SKIP`) a popsat, co presne dela na kazdem radku -
   palety, `BPLCON0` prepinani 5/4 bitplanu u HUD, sprite DMA.
2. **Bitplany**: kde lezi, jak jsou modulovany (`BPL1MOD`/`BPL2MOD`), jak
   funguje scroll (`BPLCON1` jemny posun vs. ukazatel).
3. **Vystup**: model displeje, ktery umime **odsimulovat na papire** -
   z obsahu pameti spocitat, co bude na obrazovce, bez emulatoru.

Tohle je klic k plynulejsimu scrollu: az bude jasne, jak original
kombinuje hruby posun ukazatele a jemny `BPLCON1`, da se rict, co je
puvodni omezeni a co se da rozsirit.

## Faze 3: kresleni objektu (2-3 dny)

1. **Blitter**: jake operace hra pouziva (cookie-cut maskovani, minterm,
   masky prvniho/posledniho slova), jak vypada BOB fronta v pameti a jak
   se restauruje pozadi.
2. **Hardwarove sprity**: potvrdit nas allocator (`0x3d00/0x3d4e`) proti
   skutecnym `SPRxPT` zapisum.
3. **Vystup**: presny model "co je bitplan, co BOB, co sprite" pro kazdy
   pixel snimku. Tim se `compare.py` posune od shody obrazku ke shode
   vrstev.

## Faze 4: nastroje pro jine hry (1-2 dny)

Zobecnit, co v predchozich fazich vznikne:
- **register tracer** (faze 1) je uz z podstaty univerzalni;
- **copper disassembler** - vstup je ukazatel, vystup citelny vypis;
- **blit logger** - kazda operace jako radek s minterm, velikosti a
  ukazateli;
- **layer splitter** - z jednoho snimku udela vrstvy (pozadi / BOB /
  sprity), coz je presne to, co u nove hry potrebujete nejdriv.

Vsechno patri do `tools/` vedle `objdiff.py` a `margins.py` a nema zadnou
vazbu na SWIV.

## Faze 5: co to odemkne

- **Plynuly scroll nad ramec HW**: dnes interpolujeme az v rendereru
  ("vylepseno"). S modelem z faze 2 pujde rict, ktera cast je logika
  (0,25 px/VBL, nemenit) a ktera jen zobrazeni (menit lze).
- **2,5D a 3D**: potrebuje vrstvy z faze 3. Teprve az bude jasne, ze
  konkretni pixel je teren a jiny BOB, da se terenu dat hloubka nebo
  objektum stin do prostoru.
- **Vyssi rozliseni a barevna hloubka**: paleta je dnes 16 registru s
  copper splity; model z faze 2 rekne, ktere splity jsou nutne a ktere jsou
  jen obchazeni limitu OCS.

## Odhad celkem

Faze 1-3 jsou **5-8 dnu** soustredene prace a jsou na sobe zavisle. Faze 4
je 1-2 dny navic a da se udelat az potom. Faze 5 uz neni analyza, ale
vyvoj - jeji rozsah zavisi na tom, co se rozhodnete pridat.

Nejmensi smysluplny krok je **faze 1**: sama o sobe rekne, jestli je
grafika v kodu, ktery jeste neznáme, nebo v copper listu nastavenem pri
bootu. To je jedina otevrena otazka, ktera brani napsat presnejsi plan.
