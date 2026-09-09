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
