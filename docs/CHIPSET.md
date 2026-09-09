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
