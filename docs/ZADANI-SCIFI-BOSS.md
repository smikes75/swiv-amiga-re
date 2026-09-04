# Zadani: bossovy komplex SCIFI (uroven 6)

Navazuje na `docs/ZADANI-GRASS.md` (sekce 2 az 7 = metoda, plati beze
zmeny), `docs/ZADANI-RIVER.md` (sekce 2 = pasti z revize GRASS) a
`docs/ZADANI-ICE.md` (sekce 2 = pasti z revize RIVER). Tady je rozsah,
rozjezd a pasti navic z revize ICE/SCIFI (commit a8c814b). Vysledek
projde stejnou revizi (kazde cislo proti `work/prog.txt`, prehrani
sond).

## 1. Cil a rozsah

Po teto davce je SCIFI kompletni. **Zaverecny boss FINAL (INST5#0,
`0xc068`) do tohoto zadani nepatri**, dostane vlastni; co uz o nem vime,
je v priloze A. V SCIFI zbyva 24 objektu v sedmi druzich, ktere tvori
tri celky:

| celek | ks | grafika (PAM) | gfx slovo | korutina | a2c6 (trida, aktivace, HP, body, cost) | ry v mape | poznamka |
|---|---:|---|---|---|---|---|---|
| A geyzir | 8 | _LAVA.LIN#20 | 0x284c | 0xaf9c | 0x8000, 32, 0, 0, 0 | 1139..2428 | chrli kameny (dite `0xb014`: 38, −16, HP 1, 30 b., cost 10 + guard) |
| A lusk | 6 | ORB.LIN#0 | 0x0052 | 0xb084 | 0x8000, −16, 0, 0, 0 | 3084..5134 | 6 okvetnich listu (`0xb0b4`, cost 7) a z kazdeho koule (`0xb114`: 34, −32, HP 1, 70 b., cost 10) |
| B emitor dronu | 5 | INST3.LIN#12 | 0x1831 | 0xbd3a | 0x8000, 32, 0, 0, 0 | 137..179 | dron `0xbd7a`: 38, **16**, HP 1, 50 b., cost 10 |
| B kraci boss | 1 | INST3.LIN#3 | 0x0631 | 0xbb2e | 38, −32, **HP 300, 7500 b.**, cost 40 | 158 | prvni boss urovne; pody `0xbcce` (6, −63, cost 10) se zableskem `0xbd00` (0x8000, cost 4) |
| C letajici boss | 1 | INST4.LIN#6 | 0x0c32 | 0xbdd6 | 32, −48, HP 0 → **250**, **10000 b.**, cost 0 | 4580 (+512 pozdeji) | zranitelny az po aktivaci jadra |
| C jadro pevnosti | 1 | INST4.LIN#0 | 0x0032 | 0xbe6e | 38, −48, HP 0, 0, cost 60 | 5575 | bombarduje, po smrti bosse spusti finale a konec urovne |
| C veze | 2 | INST4.LIN#3 | 0x0632 | 0xbf42 | 38, −48, HP 0, 0, cost 60 | 5594 (x 86, 228) | vysouvaji se, navadene salvy `0x8530` |

`ry` roste s postupem urovne (BUNNY zacina na 869, pevnost 5575..5594
je konec SCIFI). Zona SCIFI je `behprobe.py 6`. Gfx slova a `typ`
doplnte skriptem ze sekce 6.1 zadani GRASS s klicem `'SCIFI'`.

Davky: **1 = A** (geyzir + lusk, nezavisle efekty), **2 = B** (boss +
emitory, svazane pres `fp@(140)`), **3 = C** (pevnost, svazana pres
`fp@(140)`, `fp@(3617)`, `fp@(148)`). Celek C obsahuje konec urovne,
proto az nakonec a s vyzkumem podle pasti 10.

## 2. Pasti navic (z revize ICE/SCIFI a z bossoveho kodu)

1. **Disassembler se rozjede za `0x5eda` a `0x5efc`** (zamek). Za volanim
   lezi inline slovo s cislem zamku a objdump je slepi s dalsi
   instrukci: `bb32: 0006 303c 0631 7226 74e0` je ve skutecnosti
   `.short 6; movew #0x0631,d0; moveq #38,d1; moveq #-32,d2`;
   `bbb0: 0006 6100 fb06` je `.short 6; bsrw 0xb6ba`; `be68: 0006 6000
   e4e0` je `.short 6; braw 0xa34c`. Vzdy si tuple `a2c6` a konec
   korutiny prectete rucne po slovech.
2. **`0xa36a` bez zasahu hrace = vybuch bez skore.** `0xa36a` pricte
   body jen pri bitu 6/7 v `+506` (kdo objekt trefil). Kamen dopadajici
   na zem (`0xb07c`) i drony po smrti bosse (`0xbdce`) volaji `0xa36a`
   samy: v prepisu tedy vybuch pres `+376` (vychozi `0x894a` oblacek,
   z + 1) a uvolneni, **ne** `killSpawnCredited`. Stejne bomba SEAPLANE.
3. **`fp@(140)` se v SCIFI i snizuje.** `0xb6ae` (+1, `fp@(166)` bit 3)
   vola kraci boss po `0x9ae8(80)` a jadro po `0x9afa(58)`; `0xb6ba`
   (−1, pri nule `0x5f38(20)` a bclr bitu 3) vola kraci boss pri smrti
   (`0xbbac`). `g.inst1Factories` dnes nikdo nesnizuje - doplnte, jinak
   drony nikdy nezemrou a emitory nikdy neprestanou. Cteni: emitory
   `0xbd4e`, drony `0xbdc8`, letajici boss `0xbe44`.
4. **HP 0 = zadny handler zasahu** (`0xa2fc`): jadro, veze i letajici
   boss do `0xbe4a` jsou pro strely pruhledni (bolt proleti, jako delo
   BOS). Letajici boss zranitelny az `+360 = 250` + `0x653e(0xb8ca)` +
   `0x6564` - stejny handler jako INST2 (blikani, okna nezranitelnosti,
   uz prepsano v `inst2`), prevezmete.
5. **`a2c6` d2 je aktivace** (znovu): dron ma d2 = **16**, tedy vznika
   az kdyz je emitor 16 px pod hornim okrajem; `+364` zustava −64,
   pokud korutina nezapise jinak (kamen nic, koule `−10` az po cekani,
   geyzir `0` hned).
6. **Zatres `+282` u kraciho bosse** (`0xbc46..0xbc5c`): posun y se
   pricte pred `0x62d2` a hned po nem odecte - je to jen kresleny ofset
   snimku, poloha (kolize, deti) se nemeni. Prepiste jako ofset pro
   kompozitor, ne jako pohyb.
7. **Rodicovska pole jsou prepsana ukazatelem:** `0xbc9c` uklada do
   `+276` (long, tedy `+276` i `+278`) adresu zaznamu hrace z `0x72ee`.
   Citace bosse jsou `+280` (skok), `+282` (zatres), `+284` (smer
   pochodu, `notw`). Nepouzivejte `typ` jako stavovou promennou.
8. **Rozpocet 160 bez guardu:** jadro a obe veze stoji 60 kazdy (180)
   a guard nevolaji, ale `a2c6` cost pricita vzdy (`0xa32a`). U pevnosti
   tedy propadne kazdy guardovany objekt (BUNNY, BOS, kamen) - verne,
   nedolad'ovat.
9. **Cekani `0x9ae8(N)`** = wait na radek N s vynulovanou tridou `+508`
   (bez kolizi, uz prepsano u tovarny); `0x9afa(N)` testuje pred
   yieldem a vraci hned, je-li splneno; `0x5f22(N)` je surovy wait bez
   kontroly smrti (`jsr fp@(-1418)` az za nim).
10. **Konec urovne dela jadro** (`0xbec4..0xbeda`): po `fp@(3617)`
    finale `0xbee0` (100 kol: sance na zablesk `fp@(11166) = r & 71` a
    velky vybuch `0x8876` na nahodne pozici roste s klesajicim citacem),
    pak `fp@(3530) −= 319`, `sf fp@(3615)` (COLOR07), `bset #1,fp@(166)`
    a `fp@(11166) = 256` (fade do bile). Nejdriv zjistete, kdo cte
    `fp@(166)` bit 1 a co dela `fp@(3530) −= 319` (grep v prog.txt),
    a jak dnes prepis navazuje mapy (`junctionRows`, `mapEnds` v
    game.html ~583 a ~6004). Viditelnou cast (vybuchy, zablesky, fade)
    prepiste, prechod na FINAL zapojte na stejne misto, kde je dnes -
    nic nevymyslet, kazdy krok s adresou.
11. **Zamek `0x5eda(6)`** drzi kraci boss, veze a (v FINAL) i dalsi -
    stejne jako u INST2 nemodelovat, jen zdokumentovat. Zjistete ale,
    kdo cte `fp@(166)` bit 3 (nastavuje `0xb6ae`) - pravdepodobne HUD
    nebo hudba.
12. **Deti z `0x6178` dedi `+276..+290`, `+356`, `+358`** v okamziku
    vzniku: koule dedi `typ` listu (rozestup 64 tiku), kamen dedi uhel
    geyziru (kumulovany), pod dedi polohu bosse (posunutou o ±19, +20
    jen na dobu volani, `0xbbba`).

## 3. Rozjezd (dekodovano Fable, overit a pouzit)

### A1 Geyzir `_LAVA#20` (`0xaf9c`)

- `sf fp@(155)` (zjistete, kdo cte - `0x63c8`; lusk ORB ji naopak
  nastavuje), `a2c6(_LAVA#20, 0x8000, 32, 0, 0, 0)`, `+364 = 0`.
- Smycka `0xafb8`: oblacek `0x6178(0x894a)`, zvuk `0x5350(x)` (bez
  prepisu, zapsat), pocet kamenu `+276 = (horni slovo fp@(11172) & 7)
  + 3` = 3..10 (**stav RNG jen cten, neposouva se**), pak pro kazdy
  kamen: `0x883c` → `uhel += (r & 31) + 128` (kumulovane, kameny se
  tedy stridaji zhruba vlevo/vpravo), dite `0x6178(0xb014)`, surovy
  wait `0x5f22(10 − zbyvajici pocet)` (prvni kamen hned, dalsi
  s rostoucim rozestupem 0..9); po davce `0x5f22(horni slovo fp@(11172)
  & 127)`, `0x6480` (cull s marginem 0), `jsr fp@(-1418)`, `beq` smycka.
- **Kamen `0xb014`:** `a2c6(_LAVA#20, 38, −16, HP 1, 30 b., cost 10)` +
  guard `0x8822`, anim `0x0b032` _LAVA#20/#21 perioda 8 loop, rychlost
  `(r & 127) + 320` (1.25..1.75 px/t) v zdedenem uhlu, `z = 1`,
  `vz = ((r & 0x1ffff) jako 16.16) + 2` = 2..4 px/t, `az = −6144/65536`,
  `0x62d2` dokud cele slovo z ≠ 0, pak `0xa36a` (past 2: oblacek, bez
  skore). Sestreleny da 30.

### A2 Lusk `ORB#0` (`0xb084`)

- `a2c6(ORB#0, 0x8000, −16, 0, 0, 0)`, `st fp@(155)`, sest deti
  `0x6178(0xb0b4)` s `+276 = 5, 4, ..., 0`, rodic hned konci
  (`0xa34c`) - ORB#0 se tedy prakticky nekresli, lusk tvori listy.
- **List `0xb0b4`:** gfx z tabulky `0xb108[typ]` = ORB#1..#6,
  `a2c6(gfx, 0x8000, −16, 0, 0, cost 7)`, `+367 |= 1`, `0x9afa(typ +
  64)` (listy se otevirai po radcich 64..69), `uhel = horni slovo
  fp@(11172)` (bez posunu), dite `0x6178(0xb114)`, `z = 32`, rychlost
  `1536` = 6 px/t, `0x65f2`, wait 15 (`0x629c`), konec. List odleti
  90 px a zmizi bez vybuchu.
- **Koule `0xb114`:** `x −= 4`, `y += 2`, `a2c6(ORB#7, 34, −32, HP 1,
  70 b., cost 10)`, surovy wait `0x5f22((typ + 1) × 64)` (koule
  vylezaji 64 tiku po sobe), `+364 = −10`, anim `0x0b144` ORB#15, #16,
  #17, #18, #13 perioda 8, drzi #13; wait 50; `z = 32`, rychlost 128 =
  0.5, uhel 192; smycka `0xb16a`: `0x7312` + `0x65be` limit 33, uhel
  zaokrouhlit `(a + 16) & 224` (osm smeru), `0x65f2`, snimek
  `0xa27c(ORB#7)` (osm smeru od #7), rychlost += 64 (0.25, **bez
  stropu**), wait 15, `beq` smycka.

### B1 Emitor dronu `INST3#12` (`0xbd3a`)

- `a2c6(INST3#12, 0x8000, 32, 0, 0, 0)`; smycka: je-li `fp@(140) ≠ 0`
  dron `0x6178(0xbd7a)`; surovy wait `50 + (0x883c & 127)`; `0x6480`
  (cull −64); `jsr fp@(-1418)`, `beq` smycka.
- **Dron `0xbd7a`:** `a2c6(INST3#12, 38, 16, HP 1, 50 b., cost 10)`,
  `z = 3`, `+367 |= 1`, anim `0x0bd9c` INST3#12/#13 perioda 1 loop,
  wait 50, rychlost 512 = 2 px/t, jednou `0x72ee` + `0x65be(d2 = 0)`
  (absolutne na hrace), `0x65f2`, pak `0x62d2` dokud `fp@(140) ≠ 0`;
  pri nule `0xa36a` (past 2).

### B2 Kraci boss `INST3#3` (`0xbb2e`)

- Zamek `0x5eda(6)`, `a2c6(INST3#3, 38, −32, HP 300, 7500 b., cost 40)`,
  `z = 4`, `0x653e(0xb8ca)` + `0x6564` (handler INST2), `+376 = 0x8876`
  (velky vybuch), `0x9ae8(80)`, `0xb6ae`.
- Cyklus `0xbb6e`: `0xbc60` pochod (`notw +284`; kladne: `vx = 3` dokud
  `x < 296`, zaporne: `vx = −3` dokud `x > 24`; pak `vx = 0`), `0xbc9c`
  dojezd (`vx = ±2` k x hrace, dokud `|dx| ≥ 24`), wait 4 (`0xbbde`),
  zvuk `0x5436(x)`, dva pody `0xbbba(+19, +20)` a `(−19, +20)`, skok:
  `y −= 16` a 16× { `y += 1`, krok }, wait 10, `beq` cyklus.
- **Krok `0xbbfa`** (kazdy tik kazdeho cekani bosse): `+282 = 0`; je-li
  `HP ≤ 50`: `0x883c`, `+282 = (r & 3) − 2`, a je-li `r & 15 == 0`
  bomba `0x6178(0x7f9a)` (XEVIOUS, uz `spawnXevBomb`) + oblacek
  `0x6178(0x894a)` na ofsetu `((r' & 31) − 15, (r' >> 16 & 31) − 15)`;
  pak past 6. Boss pod 50 HP se tedy trese, kouri a shazuje bomby.
- **Pod `0xbcce`:** `a2c6(INST3#7, 6, −63, HP 0, 0, cost 10)`, `z = 0`,
  zablesk `0x6178(0xbd00)`, `y += 20`, `vy = 6` px/t, `0x9b70` (cekani
  do smrti) - smrtici kontakt, nezranitelny, zmizi cullem −63.
- **Zablesk `0xbd00`:** `a2c6(INST3#8, 0x8000, −16, 0, 0, cost 4)`,
  `z = 33`, `+367 |= 1`, anim `0x0bd24` INST3#8..#11 perioda 1 + kill.
- Smrt (`0xbbac`): `0x5efc(6)`, `0xb6ba` (past 3), `0xa34c`; body a
  velky vybuch jdou pres handler `0xa362`/`+376`.

### C1 Letajici boss `INST4#6` (`0xbdd6`)

- `y −= 512` (objekt se posune o 512 radku **dal v urovni**, tedy na
  ry ≈ 5092; overte sondou znamenko v prepisu), zamek `0x5eda(6)`,
  `sf fp@(3617)`, `a2c6(INST4#6, 32, −48, HP 0, 10000 b., cost 0)`,
  `z = 24`, `+376 = 0x8876`, `+367 |= 16` (obrazovka), `vy = 0.5`,
  `0x9ae8(208)` (sjede bez kolizi na radek 208), `vy = −0.25` dokud
  `sy > 68`, `vy = 0`, pak `0x62d2` dokud `fp@(140) == 0`; potom
  `+360 = 250`, `0x653e(0xb8ca)`, `0x6564`, `0x62cc`; po smrti
  `st fp@(3617)`, `0x5efc(6)`.
- Trida 32 = zasahnutelny, bez smrticiho kontaktu.

### C2 Jadro `INST4#0` (`0xbe6e`)

- `a2c6(INST4#0, 38, −48, HP 0, 0, cost 60)`, `z = 25`, `+534 = −1`,
  `+367 |= 1`, `0x9afa(58)`, `0xb6ae`; smycka `0xbe9a`: 5× { bomba
  `0x6178(0x7f9a)`, wait 7 }, wait 50, dokud `fp@(3617) == 0`; pak
  finale `0xbee0` a konec urovne (past 10), `0xa34c`.
- Finale `0xbee0`: 100× { `0x883c`, `d = r & 127`; je-li `d ≥ citac`:
  `fp@(11166) = d & 71`, yield `0x5f20`, `fp@(11166) = 0`, a je-li
  `fp@(-76) < 5` velky vybuch `0x6178(0x8876)` na `(32 + (r >> 16 &
  255), scroll + 16 + (r & 63))`; yield `0x5f20`; citac−− }.

### C3 Veze `INST4#3` (`0xbf42`)

- Zamek `0x5eda(6)`, `a2c6(INST4#3, 38, −48, HP 0, 0, cost 60)`,
  `+534 = −1`, wait 250; cyklus `0xbf66`: 15× { `y −= 2`, yield }
  (vysunuti o 30 px nahoru po obrazovce), `sf fp@(148)`; je-li
  `fp@(3617) == 0`: { wait 200; `bset #0,fp@(148)`; byl-li bit uz
  nastaven, znovu } (handshake obou vezi - prepiste doslova, chovani
  zmerte sondou); 15× { `y += 2`, yield }; `0x883c & 1` → `d0 = 0 | 2`
  (d1 je smeti), salva `0xbfcc`; wait 10; `beq` cyklus.
- **Salva `0xbfcc`:** je-li `fp@(3617)` nastaven, nic. `0x883c`
  zaporne → sekvence A `0xc00e(1, 0, 1, 2)`, pak `0x883c & 3 ≠ 0` konec,
  jinak sekvence B `0xc00e(3, 4, 3, 2)` a `0x883c & 3 == 0` → znovu A.
  Kladne → rovnou B.
- **`0xc00e(i)`:** polozka tabulky `0xc040` (8 bajtu): gfx `0x6d7c`
  (INST4#1..#5 = natoceni hlavne), uhel d2, dva pary bajtu (dx, dy);
  pro kazdy par navadena strela `0x8530(dx, dy, uhel)` a wait 5
  (trik `bsrw 0xc024` na nasledujici instrukci = telo probehne
  dvakrat). Polozky: 0 = INST4#1, 106, (−15, 16), (−22, 4); 1 = #2,
  85, (−6, 21), (−18, 14); 2 = #3, 64, (8, 20), (−8, 20); 3 = #4, 43,
  (6, 21), (18, 14); 4 = #5, 22, (15, 16), (22, 4).

## 4. Postup a odevzdani

Davky A, B, C, po kazde: syntaxe, sonda (`behprobe.py 6`), montaz +
zoom, oba kontrakty, commit s push. U bosse B a C navic sonda s
castecnym poskozenim (vlastni skript: `damageSpawn` N×, ne `kill`), aby
byl videt rezim pod 50 HP a okna nezranitelnosti; u celku B zmerit, ze
drony po smrti bosse zmizi a emitory prestanou; u celku C cely prubeh
od prvniho bosse po fade (skore 10000, pocet vybuchu finale).
Dokumentace do `docs/BEHAVIORS.md` jako sekce `## SCIFI - bossovy
komplex` ve formatu GRASS/RIVER, radek postupu v `docs/GAPS.md` sekce 9.
Odevzdat podle sekce 8 zadani GRASS; navic neprepsane zvuky
(`0x5350`, `0x5436`, `fp@(11166)` zablesky) a histogram rozestupu u
geyziru, emitoru, jadra a vezi.

## Priloha A: co uz vime o FINAL (INST5#0, `0xc068`) - pro dalsi zadani

- Jediny objekt mapy 7 (ry 278, x 153). Korutina ceka surovym
  `0x5f0a` na `fp@(166)` bit 3 (kdo jej v FINAL nastavuje, neni znamo -
  v SCIFI je to `0xb6ae`), pak zamek `0x5eda` s inline slovem `0x0057`
  a `a2c6(d0 = 0?, 38, 0, HP 200, 20000 b., cost 0)` - tuple je za
  zamkem rozhozeny (past 1), d0 overit; `+534 = −1`, dvakrat fade
  bila/cerna (`fp@(11166)`/`fp@(11170)` = 256 stridave, `0x5f20`),
  cekani na `fp@(166)` bit 1, handler zasahu `0x653e(0xc124)`, ctyri
  samostatne tasky `0x6160`: `0xc1ca` (INST5#1..#6 nahodne blikani),
  `0xc228` (INST5#7..#11), `0xc280` (vypoustec s guardem, tabulka
  `0xc332`, deti `0xc342` z jineho souboru 0x57), `0xc5f8` (24 × 13
  kusu INST5#17 letici radialne 12 px/t, `0xc700`, a trosky INST5#13
  `0xc73c`); vsechny ctyri cekaji `jsr fp@(-1422)` na citac
  `fp@(12534)`; `+500/+502 = 32`, `+397 |= 128` (BOB skryty - telo
  kresli deti), smycka wait 100 do smrti.
- Handler `0xc124`: `0xb6aa`, HP−1; > 0: `fp@(11166) = 64` zablesk;
  jinak `fp@(12534)++`, `0x8852`, zamek 6, 12× { velky vybuch `0x8876`
  na nahodnem ofsetu (**obe nahodne slozky se prictou k x**, y nikdy -
  chyba originalu, prepsat verne), 4× otres `0xc1ba` (`fp@(3530) ∓ 3`)
  }, `fp@(142) = −1` a otres do `fp@(142) == 0`, `fp@(11260) =
  fp@(11440) = −1`, `bset #3,fp@(12353)`, `0xa36a`.
- Dalsi deti: `0xc3d6` (soubor 0x57 #0, 36, HP 5, 70 b., cost 15,
  bomby XEVIOUS kazdych 150 + r & 127), `0xc42c` (0x57 #4, 34, HP 5,
  70 b., lovec s nahodnym uhlem ±15 kazdych 8 tiku), `0xc49e` (0x57 #7,
  36, HP 5, 70 b., klicka `0xc4fa` s tabulkami `0xc560`, rezimy
  `0xc584` stoupani / `0xc5c0` klesani). Pred zadanim je treba zjistit
  soubor 0x57 (`build/dispatch.json` / PAM), `fp@(-1422)` a
  `fp@(12534)`.
