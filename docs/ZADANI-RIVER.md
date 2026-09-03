# Zadani: prepis chovani zony RIVER (uroven 4)

Navazuje na `docs/ZADANI-GRASS.md`: **sekce 2 az 7 tamtez plati beze zmeny**
(pravidla, cteni disassembly, pole zaznamu, pomocne rutiny, kam v
`game.html` psat, overeni, dokumentace). Tady je jen rozsah, hotova
predpraca a pasti navic z revize GRASS. Vysledek projde stejnou revizi
(kazde cislo proti `work/prog.txt`, prehrani sond).

## 1. Cil a rozsah

Prepsat vsech 9 druhu chovani, ktere RIVER.PAM pouziva a jeste nejsou v
`IMPLEMENTED_BEHAVIORS` (39 objektu z 212; ostatnich 173 uz bezi z
TOWN/DESERT/GRASS). Poradi podle cetnosti:

| ks | grafika (PAM) | gfx slovo | korutina | prvni `ry` | typ z PAM | poznamka |
|---:|---|---|---|---:|---|---|
| 10 | SKYEYEA.LIN#0 | 0x0009 | 0x75f8 | 243 | 1 | soubor id 9 = `skyeyea.lin`; sousedi s SKYEYEB `0x76ec`, cekejte podobnou formaci |
| 8 | HOVER.LIN#4 | 0x082a | 0xb466 | 1317 | 1 | |
| 7 | LAKESUB.LIN#0 | 0x0029 | 0xb34a | 1188 | 1 | ponorka; pravdepodobne pracuje s COLOR07 (voda, `fp@(3615)`) jako FISH |
| 3 | JUNTANK.LIN#2 | 0x042b | 0xa592 | 2475 | 1 | dekodovano castecne, viz 3 |
| 3 | JUNTANK.LIN#1 | 0x022b | 0xa0d2 | 2870 | 1 | dekodovano castecne, viz 3 |
| 3 | INST2.LIN#2 | 0x042c | 0xb9da | 3784 | 1, 2, 3 | zacina zamkem `0x5eda(6)`; tri ruzne typy |
| 2 | LAKEGUN.LIN#0 | 0x0028 | 0xb26c | 1307 | 1 | dekodovano castecne, viz 3 |
| 2 | INST2.LIN#0 | 0x002c | 0xbae8 | 3762 | 1, 2 | |
| 1 | LAKEGUN.LIN#7 | 0x0e28 | 0xb2dc | 1500 | 1 | |

Seznam vznikne skriptem ze sekce 6.1 zadani GRASS s klicem `'RIVER'`
(pridejte i vypis `typ`, protoze tri objekty maji vice typu). Zona
RIVER je v seznamu urovni index 4 (`behprobe.py 4 ...`).

## 2. Pasti navic (z revize GRASS - skutecne chyby)

1. **Vlastni vetev smrti** v `killSpawnCredited` se pise **az za**
   spolecne `releaseSpawnTask` + `awardScore`; neopakovat je (DADA
   pricitala skore dvakrat). Pouzijte vzor `factory`/`dada` po revizi.
2. **Animator bezi nezavisle na cekani korutiny.** Skript pripojeny
   `0x6c88` postupuje kazdy tik bez ohledu na to, ve kterem `0x629c`
   nebo smycce korutina prave je. Snimky se posouvaji ve vsech fazich,
   dokud skript neskonci (`end`) nebo se nesmycku (`loop`). VTOL pri
   zdvihu a vez _PLAT behem wait 120 zamrzly - chyba.
3. **Kazdy zapis do `+364`** (cull margin) modelovat, vcetne tech po
   aktivaci: `_PLAT` −16 (`0xa3e4`), `_CORN` −90 (`0x820c`, jeste pred
   `a2c6`), strely 0. Vychozi je −64 (`0x61ee`). Kdo to vynecha, meni
   dobu zivota objektu za okrajem.
4. **Vychozi zaznam tasku (`0x61ee..0x6238`):** `+364 = −64`, `+538 =
   0x6db4` (cull = zemri), `+542 = +534 = −1`, `+376 = 0x894a`, vsechny
   handlery `+510..+530 = 0x6288`, **`+508 = 0`**, `+367 = 0`. Objekt s
   HP 0 tedy nereaguje na bolt ani kontakt, dokud korutina sama nepovoli
   bity (`0x653e` bit 0, `0x654a` bity 1+2, `0x6564` bity 3+4, `0x6566`
   bit 3, `0x6572` bit 4). Kanonovy granat `0x9632` zapina 3+4 s
   `0x6db4` (na kontaktu zanikne); strela vejce a bomby XEVIOUS nic
   (preziji). Pro strely v `g.shots` viz vetev `eggshot` v
   `dispatchTownContactEvent`.
5. **Trida `+504`:** bit 1 = smrtici kontakt (34, 38, 6), bit 2 = udalost
   bit 4 s vychozim `0xa362` (36, 38), bit 15 = bez sweepu (0x8000).
   Trida 36 **neni** smrtici (XEVIOUS#0 byl chvili spatne v seznamu).
   Zmena tridy uprostred korutiny (`+504 = 34` po vzletu) = `s.lethal`.
6. **Hazardy se krokuji pred spawny.** Vazane dite (`+367` bit 3)
   polohovane v kroku hazardu je o tik za rodicem. U rychlych rodicu
   (nad ~1 px/t) polohujte dite z kroku rodice (vzor `mama` → `mamabar`).
7. **Uzel = snimek z `a2c6`** (nebo posledniho `0x6d7c`); animator uzel
   nemeni. `NODE_GRAPHIC` proto nese `a2c6` snimek, ne PAM snimek
   (XEVIOUS#5 z PAM je #5, uzel #3).
8. **`+397`** je bajt priznaku animatoru (`+380 + 17`): bit 7 = BOB se
   nevlozi do fronty (`0x481a`), skripty jej prepinaji `andflag(128)`
   / `orflag(128)`. Bit 0 (`orib #1,%a5@(397)`) se zatim neprepisuje.
9. **Formace pres `0x6178` v rucni smycce** (XEVIOUS#9: 9 kopii, mezi nimi
   `y -= 3`) je totez co `spawnFormationCopies(g, s, 10, 0, −3, 0)`.
10. Objekt **bez `a2c6`** (JEEPHELI#43: jen `0x5ee0` + `0x9ac8`) se
    nekresli - `s.hidden = true`, cost 0, HP 0.
11. Pri vkladani vetvi do `advanceTownHazardField` pozor na **dva
    retezce if/else** - vetev vlozena do druheho retezce se nikdy
    nespusti, kdyz prvni retezec konci `return` (stalo se u `platveh`).
    Po kazde nove vetvi overit sondou, ze se stav opravdu meni.

## 3. Uz dekodovane kusy RIVER (overit, pak pouzit)

- `0xa0d2` (JUNTANK#1): `a2c6(JUNTANK#1 = 0x022b, 36, −48, HP 15, 90
  bodu, cost 18)` - zbytek od `0xa0e0` dodekodovat (sousedi s DESTRAIN
  `0xa1b0`, kterym konci).
- `0xa592` (JUNTANK#2): `a2c6(JUNTANK#2 = 0x042b, 0, −32, HP 0, 0 bodu,
  cost 5)`, `+397 |= 1`, `0x9afa(48)`, anim `0x0a5b4` = period(4)
  JUNTANK#3, #4, #5, #6, #7, #8 ... (viz `docs/ANIMS.md`), zbytek od
  `0xa5c0` dodekodovat. Trida 0 = dekorace bez kolizi.
- `0xb26c` (LAKEGUN#0): `a2c6(LAKEGUN#0 = 0x0028, 36, **100**, HP 4, 75
  bodu, cost 10)` - aktivace az na radku 100, `+374 = 5` (dekal
  EXPL1#0), anim `0x0b288` period(6) LAKEGUN#1..#6, wait 50, `+276 = 6`,
  wait 30, `moveq #−8` ... zbytek od `0xb2ae`.
- `0xb2dc` (LAKEGUN#7) lezi hned za tim; `0xb34a` (LAKESUB) nasleduje.
- `0xb9da` (INST2#2): zacina `0x5eda(6)` (zamek, nemodelovat) a
  `a2c6(...)` - inline slovo za `bsrw 0x5eda` je `0x0006`, ne kod.
- `0x75f8` (SKYEYEA#0) lezi mezi AIRMINE `0x75a8` a SKYEYEB `0x76ec`;
  SKYEYEB je prepsan (`skyeye`), porovnejte a sdilejte kod, kde sedi.
- FISH (`0xb1a8`) zapina `fp@(3615)` = COLOR07 pro vodu; LAKESUB a
  LAKEGUN mohou delat totez - hledejte `st/sf %fp@(3615)`.

## 4. Postup a odevzdani

Davky po 2 az 4 chovanich, po kazde: syntaxe, sonda (`tools/survey/
behprobe.py 4 ...`), montaz + zoom, oba kontrakty, commit s push.
Dokumentace do `docs/BEHAVIORS.md` jako sekce `## RIVER` ve formatu
GRASS, radek postupu v `docs/GAPS.md` sekce 9. Odevzdat podle sekce 8
zadani GRASS; navic uvest, ktere zvuky (`0x4c..`, `0x51..`, `0x53..`,
`0x54..`, `0x55..`) se vedome neprepisuji.
