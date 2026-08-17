# Formát .PAM — mapy úrovní

Poslední formát diskety. Rozluštěn čtením interpretu v `AMPROG.OBJ`
(rutiny `0x3652`, `0x3800`, `0x4a04`, `0x48c0`); renderer je
`tools/map.py`, tentýž kód v JS má záložka **Levels** ve `viewer.html`.
Obě implementace dávají **bit po bitu shodné** obrázky (kontrolní
součty pixelů v kontraktu).

## Tabulka úrovní (AMPROG.OBJ na `0x384C`)

7 záznamů po 6 B: `word` ID souboru mapy (90–96 = TOWN…FINAL v pořadí
vnitřní tabulky jmen na `0x0004`), `word` offset slovníku dlaždic
(relativně k `0x384C`), `word` rychlost scrollu.

**Slovník dlaždic** je pole wordů; mapa dlaždice adresuje 8bitovým
lokálním ID a slovník je překládá na **grafické slovo**
`snímek << 9 | soubor` — jediný formát odkazu na grafiku v celé hře
(dekóduje ho `0x48c0`: soubor = dolních 9 bitů, snímek = zbytek).

## Záznamy mapy

Proud 4bajtových záznamů čtených jako big-endian long `D`; hra jich
zpracuje tolik, kolik jich spadá do 256 px před okraj obrazu (`0x365e`).

| podmínka | význam |
|---|---|
| `D == 0` | konec mapy |
| bit 31 | **příkaz**: `y -= (D>>16) & 0xFF`; dolní word je barva (níže) |
| jinak | **pole**: viz rozklad |

Rozklad pole (`0x3674`):

```
typ    = D & 15          0 = dlaždice pozadí, jinak objekt (typ = chování)
lokál  = (D >> 4) & 255  index do slovníku úrovně
Δy     = (D >> 12) & 255 posun scroll čítače (mapa jede odspodu nahoru)
x      = D >> 20         12 bitů; hodnoty ≥ 416 opakovaně −512 a
                         snížení vrstvy — záporná x a kreslicí pořadí
```

**Pořadí kreslení.** Seznam aktivních dlaždic drží klíč
`(vrstva<<8)|pořadí` a řadí se sestupně (vkládání `0x4826`). Prakticky
ověřené pořadí proti skutečné hře (věž na startu TOWN, balvanová pole):
**koberce vespod** — vrstva 0 je „nejdalší pozadí" (řadí se jako 5),
pak vrstva 4, a detaily 3/2/1 navrch; v rámci vrstvy pořadí záznamů
mapy. Přesná mechanika, kterou engine dosahuje pozice vrstvy 0 na dně
(klíč `0|seq` je přitom nejmenší), zbývá dočíst — pravidlo je ale
ověřené na obou konfliktních místech i proti videu.

Objekty (`typ ≠ 0`) se nevkládají do bitmapy, ale **spawnují** —
`0x36fe` založí strukturu s pozicí (`a0@(320/324)`) a typem chování
(`a0@(276)`). Mapa tedy nese i rozmístění nepřátel a bonusů.

## Barevné příkazy: paleta žije v mapě

Dolní word příkazu (obsluha `0x4a04`):

```
index barvy = word & 15        cíl = COLOR00 + index
barva       = word >> 4        RGB12
```

Úvodní dávka příkazů v každé mapě nastaví **celou paletu úrovně**;
další příkazy v průběhu mapy barvy **plynule přelaďují** (engine je
interpoluje, `0x4a48`). Slavný západ slunce nad řekou není žádný
skript v kódu — **je zapsán přímo v datech mapy.**

Změřená struktura palet: barvy 0–9 jsou v úrovních 0–4 shodné
(objekty — jeep, vrtulník, exploze), 10–15 nese terén.

## Ukotvení: engine kreslí od kotvy, ne od rohu

Kreslič bobů (`0x3ef0`) odečítá od pozice **kotvu snímku** —
bajty +4/+5 hlavičky `.LIN`, které jsou **znaménkové** (diagonální
sekce ranveje mají kotvu mimo vlastní obdélník, např. −6). Bajty
+8/+9 nesou tentýž pár podruhé; u pár souborů (SKI) se páry liší
a který z nich runtime používá, rozhodne až přečtení konvertoru
hlaviček. Svislý směr: scroll čítač klesá, mapa se staví odspodu —
render klade start úrovně dolů a čte se nahoru, jak hra letí.

## Pozadí

Engine maže pás scrollovací bitmapy hodnotou `-1` do **rovin 1 a 3**
(`0x34f2`; řádka má 44 B = 352 px, rovina 44×320) — prázdno je barva
10. Struktura terénu (tečkovaná hlína, tráva, vlnky vody) NENÍ žádný
šumový trik: dělají ji **výplňové kompozity přímo z mapy** — čtyřdílné
řetězené pásy 128×64 px (viz GRAPHICS.md, řetězy), tři vedle sebe
pokryjí celou šířku hřiště. Dřívější domněnka o šumu v rovinách 0+2
byla mylná — vznikla z chybného číslování snímků, které výplně
posunulo na jinou grafiku.

## Čísla úrovní (proměřeno)

| # | mapa | dlaždic | objektů | změn palety | výška px |
|---|---|---|---|---|---|
| 0 | TOWN | 704 | 155 | 13 | 3 441 |
| 1 | DESERT | 965 | 274 | 22 | 5 872 |
| 2 | GRASS | 357 | 132 | 28 | 2 725 |
| 3 | RIVER | 911 | 212 | 19 | 4 127 |
| 4 | ICE | 796 | 367 | 31 | 5 315 |
| 5 | SCIFI | 1 794 | 356 | 24 | 5 632 |
| 6 | FINAL | 93 | 1 | 1 | 384 |

(výška = čistá výška mapy; render přidává 300 px rezervu na přesahy)

FINAL je krátký, protože finální aréna se opakuje smyčkou za běhu.

## Ověření proti záznamu skutečné hry

Render TOWN je konfrontovaný s uživatelovým videem z emulátoru:
korelace najde snímky videa v renderovaném pásu a f001–f009 zamykají
**monotónně s konzistentní rychlostí scrollu** (−48 px / 4 s); vizuální
srovnání zamčené pozice sedí struktura po struktuře (živé ploty,
ohrady, balvanová pole, plošiny). Rozdíly jsou jen dynamické entity
(exploze, pohyb nepřátel), které statická mapa nenese.

## Co záměrně nerenderujeme / známé odchylky

- interpolace barevných přechodů (render skáče po checkpointech)
- opakování FINAL arény
- typy chování objektů (kreslíme jen jejich grafiku na pozici spawnu)
- zrcadlící flagy dílů (bity 1–2) zatím neaplikujeme

Hřiště má 352 px (44B řádka), ale okno hry ukazuje 320 z nich
(bitmapa x 16..336; kreslič pouští x −32..320, `0x3f02`). Render
proto kreslí přímo viditelné okno — prvky zasahující do okrajů se
oříznou stejně, jako je ořezává hra. „Uříznuté" kusy u krajů plakátů
jsou tedy věrné: hráč je vidí stejně oříznuté.
