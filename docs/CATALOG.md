# Katalog, formát souborů a třetí packer (formát C)

Rozbor rutin vlastního zavaděče hry (`build/loader.bin`); přepis je
`tools/extract.py`. Tímhle je disketa **kompletně otevřená** — všech
128 souborů jde vysypat a rozbalit.

## Rozvržení souborové oblasti

Zavaděč adresuje **bajtové offsety od začátku stopy 1** (rutina `0x864`:
`divu #5632` + `addq #1` — 5632 B = 11 sektorů = jedna stopa; stopa 0
patří bootblocku). Offset 0 souborové oblasti = bajt 5632 diskety.

```
+0        word      počet souborů N (tady 128)
+2        N × long  uložené (zabalené) délky
+2+4N     soubor 0, soubor 1, …  těsně za sebou, bajtově zarovnané
```

Soubor: `long` rozbalená délka + proud formátu C. **Nic není zarovnané
na sektory** — proto scan.py nic nenašel a najít nemohl.

Soubor 0 (`AMDLS0.CAT`) je **tabulka jmen**: řádky oddělené `\n`,
pořadí řádků = indexy souborů. Hledání jména (`0x1ec`) porovnává
case-insensitive. Katalogů může být víc (`AMDLS<n>.CAT`, svazek „V0",
„V1" — rutina `0x71a` skládá `0x5630 + n`); SWIV má jeden.

## Formát C — proudový packer

Třetí a poslední packer na disketě (vedle A a B z bootovacího řetězu).
Je navržený tak, aby šel **rozbalovat přímo při čtení ze stopy** — hra
nikdy nedrží zabalený soubor v paměti.

- bity: po bajtech, MSB napřed; čísla MSB napřed
- **literály jdou mimo bitový proud** — kopírují se bajtově zarovnané
  přímo z proudu (rychlost); rozpracovaný bajt bitové čtečky je přežívá
- zápasy se kopírují z **kruhového bufferu 1024 B** (offset 10 bitů),
  do kterého se zapisuje i každý literál
- proud **střídá bloky literálů a zápasů** (žádný bit „co následuje" —
  ušetřený bit na každém bloku); stav začíná blokem literálů
- délkový kód (`0x5b2`):

| bity | hodnota |
|---|---|
| `0` | 0 |
| `1` + 2 bity | 1–3 (00→1 … 10→3), `11` = únik |
| `11` + 2 bity | 4–6, `11` = únik |
| `1111` + **11 bitů** | 0–2047 |

- blok literálů: délka = kód (0 = prázdný, jen přepne)
- blok zápasu: **offset 10 bitů napřed**, pak délka = kód + 2;
  hodnoty > 63 znamenají 0 (prázdný blok)

**Past, která stála hodinu:** poslední forma kódu není smyčka, ale
**jedenáctkrát ručně rozbalený getbit** (`0xba2`–`0xc26`; registr `d7`
se v ní nepoužívá). Desetibitová je jen rutina offsetu (`0xaee`), která
smyčku má. Při čtení 10 bitů místo 11 dekóduje prvních pár literálů
správně a pak se to tiše rozpadne.

## Čtecí automat (`0xa14`)

Hra čte soubory po kouscích (streaming); stav automatu žije
v proměnných u báze a6:

| proměnná | význam |
|---|---|
| `-1100` | režim: 0 = literály, ≠0 = zápas (přepíná `not.w`) |
| `-1116` | kolik bajtů zbývá v rozečteném bloku |
| `-1106/-1104` | bitová čtečka (počet bitů, rozpracovaný bajt) |
| `-1102` | pozice v kruhovém bufferu |
| `-1098` | offset rozečteného zápasu |
| `-1124` | ≠0: zdroj je RAM (soubor už v paměti), ne disketa |

`0x966` před každým souborem všechno vynuluje včetně bufferu.
Za zmínku stojí `-1124`: už načtené soubory se drží v seznamu a čtou
se **z paměti stejným automatem** — proto má `0x8b2` i `0xb1e` dvě
větve zdroje.

## Obsah diskety (128 souborů, 835 001 B → 1 383 741 B)

| skupina | soubory | formát |
|---|---|---|
| `AMPROG.OBJ` | **55 668 B — kompletní kód hry** | 68000, začíná `bra` |
| `AMDLS0.CAT` | tabulka jmen | řádky `\n` |
| `HS1–16.TXT` | výchozí highscore (JOHN BOY, MARY ELLEN…) | text |
| `AMTITUNE/AMHITUNE.MOD` | hudba titulků a highscore | ProTracker `M.K.` |
| `*.SND` | samply (BIGEXPL, SMART) | 8bit PCM |
| `*.RAW` (9×) | celoobrazovkové obrázky, **40 992 B** | 4 bitplany 320×256 + 32 B palety |
| `*.LIN` (~100×) | grafika objektů a sekcí levelů | vlastní, další krok |
| `*.PAM` (7×) | TOWN, DESERT, GRASS, RIVER, ICE, SCIFI, FINAL | mapy levelů, vlastní |

Podtržítko na začátku jména (`_HOUSES.LIN`, `_LAVA.LIN`…) značí sekce
scrollujícího podkladu; bez podtržítka jsou objekty (JEEP, TRAIN,
GOOSE…). `INST1–5.LIN` sedí na pět světů, `.PAM` na sedm úrovní.

## Co z toho plyne

`AMPROG.OBJ` má 55 668 B — mezi tím je i vestavěná tabulka jmen souborů
(hned za úvodním `bra`), takže čistého kódu bude ~50 KB. Pro srovnání:
Captain Beeble měl 16 490 B. Je to tedy **~3× větší projekt než CPB**,
horní polovina toho, co jsme čekali, ale konečně je to číslo, ne odhad.
