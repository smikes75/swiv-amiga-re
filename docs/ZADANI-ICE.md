# Zadani: prepis chovani zony ICE a beznych nepratel SCIFI (urovne 5 a 6)

Navazuje na `docs/ZADANI-GRASS.md` (sekce 2 az 7 = metoda, plati beze
zmeny) a `docs/ZADANI-RIVER.md` (sekce 2 = pasti z revize GRASS). Tady je
rozsah, rozjezd a pasti navic z revize RIVER. Vysledek projde stejnou
revizi (kazde cislo proti `work/prog.txt`, prehrani sond).

## 1. Cil a rozsah

Dve zony v jednom zadani, protoze ICE ma po sdilenych objektech uz jen
ctyri druhy. **Bossovy komplex SCIFI (INST3#3, INST4#0/#3/#6, efekty
_LAVA#20, ORB#0, INST3#12) a FINAL (INST5#0) do tohoto zadani nepatri**,
dostanou vlastni. Poradi podle cetnosti:

| zona | ks | grafika (PAM) | gfx slovo | korutina | HP | body | cost | poznamka |
|---|---:|---|---|---|---:|---:|---:|---|
| ICE | 18 | EDGE.LIN#0 | 0x0008 | 0x77c6 | 1 | 50 | 10 | dekodovano cele, viz 3 |
| ICE | 13 | SEAPLANE.LIN#0 | ? | 0xb59c | 8 | 45 | 20 | lezi hned za raketou HOVER `0xb532` |
| ICE | 4 | SKI.LIN#0 | 0x0030 | 0x9e60 | 4 | 15 | 10 | dekodovano cele, viz 3 |
| ICE+SCIFI | 1+27 | BOS.LIN#0 | ? | 0x7aea | 4 | 100 | 35 | lezi za DADA `0x7a2c`; cost 35 pri HP 4 = cekejte deti |
| SCIFI | 74 | BUNNY.LIN#2 | 0x044f | 0x786e | 1 | 90 | 10 | nejcastejsi objekt hry; dekodovano castecne, viz 3 |
| SCIFI | 12 | FROG.LIN#0 | 0x0053 | 0x83dc | 1 | 55 | 10 | lezi mezi VTOL `0x8344` a EGG `0x8478` |
| SCIFI | 11 | TAP.LIN#0 | ? | 0x99e0 | 8 | 60 | 10 | lezi za ROTOBASE `0x994e` |

Gfx slova a `typ` doplnte skriptem ze sekce 6.1 zadani GRASS s klici
`'ICE'` a `'SCIFI'`. Zona ICE je `behprobe.py 5`, SCIFI `behprobe.py 6`.
Po teto davce zbyde v SCIFI 20 objektu bossoveho komplexu a FINAL.

## 2. Pasti navic (z revize RIVER - skutecne chyby)

1. **Kazde cekani ve smycce**, i to za vnitrni smyckou. INST2#0 dela
   `5× { bomba, wait 7 }` a potom `wait fp@(140) × 128 + 1`; prepis
   druhe cekani vynechal a bombardoval desetkrat casteji. Prepiste
   smycku jako stavovy automat se vsemi `0x629c` v poradi, pak sondou
   zmerte rozestupy (histogram tiku mezi udalostmi).
2. **Propad za smyckou.** `bras`/propad do kodu ditete (`0x8046` →
   `0x8066`) znamena, ze rodic sam bezi jako dalsi dite: spoustec vln
   dava 4 + 1 letcu, ne 4. Vzdy dokoncete cteni az po `braw 0xa34c` /
   `0x6288`.
3. **Stiny hazardu.** Kompozitor kresli hazardum stin jen s
   `castShadow: true`. Kazdy objekt bez `+367` bitu 0 a s nenulovym `z`
   ho v originale ma (raketa HOVER, dron, odrazova strela). Pri kazdem
   novem hazardu rozhodnout vyslovne.
4. **`a2c6` d2 je aktivace, ne `+364`.** Cull margin je vychozich −64,
   dokud korutina nezapise `+364` (`movew #N,%a5@(364)`).
5. **Globaly, ktere korutina nuluje nebo cte**, zrcadlit: `fp@(146)`
   (`g.waveSeq`, rozptyl vln FODDERA), `fp@(140)` (`g.inst1Factories`),
   `fp@(3615)` (COLOR07), `fp@(3616)` (SKI a BUNNY ji nastavuji /
   nuluji - zjistete, kdo ji cte; grep `fp@(3616)`).
6. **Prvni iterace smycky bez cekani.** Kdyz smycka zacina akci a cekani
   je az na konci (`0xa672`), prvni akce probehne hned, ne po cekani.
7. Dedeni pri `0x6178`/`0x6144`: dite dostane polohu, rychlosti,
   zrychleni, `+356`, `+358` a `+276..+290` rodice **v okamziku vzniku**;
   `+367`, `+508`, `+364`, handlery se resetuji (`0x61c4..0x6238`).

## 3. Rozjezd (overit, pak pouzit)

- **EDGE `0x77c6`:** `x = fp@(11172) < 0 ? 256 : 64` (globalni prepinac
  strany - zjistete, kdo `fp@(11172)` meni), formace `0xa2a2(0, −4, 6,
  0)`, `a2c6(EDGE#0 = 0x0008, 34, −48, HP 1, 50 bodu, cost 10)`,
  `+367 |= 0x10`, z 32, rychlost `+356 = 768`, uhel 64, snimek
  `0xa27c(8)` (osm smeru, zaklad EDGE#0), `0x9afa(32)`; je-li
  `fp@(182) >= 4` mireny kanon; `0x9afa(156)`; pak 7× { uhel += (x > 160
  ? −32 : +32), `0x65f2`, `0xa27c`, wait 5 }, mireny kanon `0x95d2`,
  `0x62cc`. Sdili strukturu se SKYEYEA/SKYEYEB (`skyeye`).
- **SKI `0x9e60`:** `st fp@(3616)`, `a2c6(SKI#0 = 0x0030, 36, 190, HP 4,
  15 bodu, cost 10)` (aktivace az na radku 190), `+374 = 5`, uhel 32,
  `x −= 32`, `vx = 2`, `vy = −2` (slova), `ax = −1536/65536`,
  `ay = +1536/65536`; smycka `0x62d2`, dokud cele slovo `vx` neni nula
  (~85 tiku), pak `0x6d96` (stop) a { `0x95ca`, wait 10 } do zabiti.
  Sanky vjedou zdola, zabrzdi a strili rovne v uhlu 32.
- **BUNNY `0x786e`:** `sf fp@(3616)`, formace `0xa2a2(−48, 6, 3, 1)`
  (tri kusy, `+276` roste), `a2c6(BUNNY#0 = 0x004f, 34, −48, HP 1, 90
  bodu, cost 10)` + guard `0x8822`, `+367 |= 0x10`, z 32, rychlost 640,
  uhel `64 − (+276 << 4)`, `0x65f2`, snimek pres tabulku `0x78fa`
  (`0xa268`, 16 polozek: BUNNY#0..#4 na indexech 2..6, jinde 0x2200 =
  nedosazitelne), wait 70, pak 2× `0x78d6` { uhel += 16, `+356 += 128`,
  `0x65f2`, snimek, mireny kanon, wait 8 }, `0x62cc`. Pozor: PAM kresli
  BUNNY#2, korutina vola `a2c6` s BUNNY#0 (uzel #0).
- **FROG `0x83dc`:** `a2c6(FROG#0 = 0x0053, 36, −8, HP 1, 55 bodu, cost
  10)`, anim `0x083f2` (docs/ANIMS.md), z 0, `0x9afa(8)`, `+364 = −16`,
  uhel 64, rychlost `+356 = 384`, dal od `0x8422` dodekodovat.
- SEAPLANE `0xb59c`, TAP `0x99e0` a BOS `0x7aea` nejsou dekodovane.
- Pro ICE ocekavejte praci s vodou/ledem: hledejte `fp@(3615)` (COLOR07)
  a `0x9358` (cakanec), pro SCIFI `fp@(3616)`.

## 4. Postup a odevzdani

Davky po 2 az 4 chovanich, po kazde: syntaxe, sonda, montaz + zoom, oba
kontrakty, commit s push. Dokumentace do `docs/BEHAVIORS.md` jako sekce
`## ICE` a `## SCIFI` ve formatu GRASS/RIVER, radek postupu v
`docs/GAPS.md` sekce 9. Odevzdat podle sekce 8 zadani GRASS; navic
uvest neprepsane zvuky a **histogram rozestupu** u kazdeho objektu,
ktery strili v serii.
