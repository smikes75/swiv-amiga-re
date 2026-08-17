# Grafické formáty: .RAW a .LIN

Dekodér je `tools/gfx.py`. Všechno níže je ověřeno okem na výstupu
a kontrolami v `tools/check.py`.

## .RAW — celoobrazovkové obrázky (9 souborů, vždy 40 992 B)

```
40 960 B   4 bitplany 320×256, SEKVENČNĚ za sebou (10 240 B na rovinu)
    32 B   paleta 16 × RGB12 big-endian, NA KONCI souboru
```

Obsah: COVER (titulka), HELIBP1/2 + JEEPBP1/2 (modely stroje pro intro),
MUSHROOM, FACES (tváře autorů + maskot), CONGRAT1/2 (dohrání).
Náhledy v `docs/img/`.

## .LIN — sady snímků objektů (~100 souborů)

```
+0   word   počet snímků
na každý snímek:
+0   word   délka dat = ceil(š/16)·2 · 4 · v
+2   byte   šířka v pixelech
+3   byte   výška
+4   byte   střed x        +5  byte  střed y
+6   byte   PRŮHLEDNÁ BARVA (index 0–15)
+7   byte   ?
+8   word   ?  (u většiny znovu střed)
+10  data   řádky prokládaně [p0 p1 p2 p3], na rovinu ceil(š/16) wordů
```

Klíčové zjištění: **snímky nemají masku a nejsou ořezané** — jsou to
plné obdélníky 4rovinných dat a průhlednost určuje **index barvy
z hlavičky**. Hra si masky zjevně staví při nahrávání (jeden index →
`BLTAFWM`-styl maska se generuje OR-em rovin XOR průhledná).

Důkaz je statistický: modus barvy okrajových pixelů == bajt +6
u naprosté většiny snímků napříč soubory (HOMING 16/16, MAMA 15/15,
INSECTS 30/30…). Výjimky jsou vysvětlitelné obsahem: LAKEGUN stojí na
vodě, okraj má vodní barvu, průhledná je 7.

Průhledný index **není konstantní ani v rámci souboru** (MINE.LIN má
snímky s 10 i 14) — proto je v hlavičce každého snímku.

Soubory s podtržítkem (`_HOUSES`, `_LAVA`, …) jsou touž strukturou,
ale obsahem sekce scrollujícího podkladu; `INST1–5.LIN` nesou графику
instalací (základen) pěti světů.

## Palety

`.LIN` paletu nenese. Herní palety leží v `AMPROG.OBJ` — blok
16wordových RGB12 palet od `0x299C`; ta na `0x29BC` je **bit po bitu
totožná** s paletou COVER.RAW, což blok potvrzuje. Party úrovní:
`0x29DC`, `0x29FC`, `0x2A1C`, `0x2A7C`, `0x2AB4`, `0x2ADC`… — přesné
párování paleta↔úroveň vypadne až z disassembly / z `.PAM`.

Náhledové archy (`tools/gfx.py sheets`) proto používají paletu
`0x29DC` pro všechno; odstíny jsou orientační, tvary přesné.

## Co zbývá

- `.PAM` (7 souborů) — mapy úrovní; struktura `80 NN`-wordů vypadá
  jako proud příkazů, ne bitmapa. Další krok.
- `CONTROL.LIN`, `REACTOR.LIN`, `INST2BIT.LIN` — nejsou standardní
  `.LIN` (INST2BIT podle jména 2rovinný?), ověřit.
- významy bajtů +7 a +8/+9 hlavičky.
