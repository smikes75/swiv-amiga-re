# Plan: JEEP a druhy hrac

Posledni velka chybejici cast hry. Vrtulnik je hotovy, jeep existuje jen
jako prazdna pulka HUD. Tenhle dokument shrnuje, co uz je zmerene v
`work/prog.txt`, co presne chybi, a v jakych davkach to jde udelat.

Stav k 2026-09-10: **davky 1-5 hotove**, zbyva 6. Vse nize je
odecteno z disassembly, ne odhadnuto.

## 1. Jak original oddeluje oba hrace

Sloty se zakladaji v `0x6f46` a jsou dva:

| slot        | `+58` | `+56` | `+66` | jmeno    | vstup |
|-------------|-------|-------|-------|----------|-------|
| `fp@(11176)`| 0     | 1     | 1     | `Heli`   | `0x2160` |
| `fp@(11356)`| 1     | 0     | 2     | `Jeep`   | `0x21b4` |

- `+56` je **vozidlo** a zapisuje se jen tady (`0x6f94`). Slot 1 je tedy
  vzdy vrtulnik, slot 2 vzdy jeep — hrat jeepa sam jde jen tak, ze se
  pripoji druhy slot.
- `+60` ukazuje na druhy slot, `+46` na cteni ovladace, `+66` je typ
  ovladace (dispatch `0x7184`: 0 → `0x7218`, 1 → `0x721e`, 2 → `0x71ac`).
- `+40` drzi jmeno pro tabulku skore; `0x6fb0` pred nej lepi `Lazy `,
  vychozi zapisy jsou tedy `Lazy Heli` a `Lazy Jeep`.
- `0x7156` podle `+56` zaklada bud `0x9410` (vrtulnik), nebo `0x9090`
  (jeep). Zbytek rodicovskeho tasku `0x7090` (zivoty, zbran, respawn,
  continue) je **spolecny** — uz ho mame.

## 2. Korutina jeepu `0x9090`

Cela je citelna, konstanty jsou zmerene:

- grafika `JEEPHELI#23` (`0x2e00` do `0x6d7c`), spawn pres spolecne `0x9046`
- `+108 = 200` tiku ochrany, `+358 = 192` vychozi uhel veze, `+280 = 1`,
  `+282 = 15`
- **rychlost `+356 = 640`** = 2,5 px/t (vrtulnik ma 768 = 3 px/t)
- smer ze **stejne** tabulky `0x959e` pres `0x958a` jako vrtulnik
- dite = vez `0x89e8` (`0x6144`), otaci se — narozdil od vrtulniku, ktery
  ma smer zamceny nahoru
- clamp `0x94f0` (vlastni, vrtulnik ma `0x954c`): `x` na 4..316, `y`
  nejmene `fp@(3558)`, a do pasu `fp@(3542)+4 .. fp@(3542)+248`. Kdyz je
  po clampu na `0x3dd4` **i** `0x3dce` teren, vola `0x9314` = rozmacknuti
  (exploze `0x88fc`) — jeep umira i tim, ze ho scroll pritlaci k terenu
- kolize s terenem `0x9328`: zdvojnasobi rychlost `+332/+336`, priplacne
  ji k `x/y`, sahne na masku `0x3dd4` a zase to odecte — tedy pohled
  o krok dopredu, ne test aktualni polohy
- `0x9172`: pasmo dopravniku — kdyz `fp@(154)` a `y` lezi mezi `fp@(150)`
  a `fp@(152)`, odecita `fp@(-76)` od `+280` a spousti `0xad98`
- `0x90a0`: kdyz `fp@(3552) − fp@(3542) < 240`, jeep se prenese na
  SWAP plosinu (`fp@(3550)/(3552)`) a nastavi `fp@(3548)` — to je presne
  ten hook, ktery dnes v prepisu lezi ladem u `swappad`/`swappad0`

### Skok `0x91e8` (druhe tlacitko nebo bit 6 vstupu)

- `+504`: zhasne bit 4, rozsviti bit 3 — **ve vzduchu se meni kolizni
  trida**, pozemni objekty jeep netrefi
- `+356 = 896` (3,5 px/t, rychleji nez po zemi)
- `+340 = 0x0001d000` stoupani, `+352 = −4096` gravitace na tik
- uhel veze `+358` se pres skok **zachova** (ulozi se na zasobnik na
  `0x9228` a vrati na `0x9250`), rizeni pritom smer meni
- dopad: `+340 = 0xa000`, `+352 = −4096`, `+504 |= 16`
- zvuk `0x4dc6` s `d0 = x` (panorama podle polohy)

## 3. Co k tomu chybi mimo korutinu

- **pripojeni druheho slotu** — dnes ma prepis jednoho hrace natvrdo
- **HUD**: prava pulka uz umi neaktivni stav (`JEEP 0`, prompty
  `PRESS FIRE` / `NO CREDITS` / `PLEASE WAIT`), ale ne aktivni slot
- **kolizni trida bit 2** (`+522`) — pozemni objekty, ktere zabiji jeep.
  Dnes se vyhodnocuje jen bit 1 (vzdusne proti vrtulniku)
- **dva vstupy v prohlizeci** — v originale dva joysticky; tady je to
  otevrena otazka (viz nize)

## 4. Davky

| # | obsah | odhad |
|---|---|---|
| 1 | ~~Druhy slot: `0x6f46` tabulka, `+56` dispatch v `0x7156`, pripojeni pres fire, HUD aktivni pulka~~ **hotovo** | 1 den |
| 2 | ~~Korutina `0x9090`: pohyb po zemi, clamp `0x94f0`, kolize `0x9328`, rozmacknuti `0x9314`~~ **hotovo (soucast davky 1)** | 1–2 dny |
| 3 | ~~Vez `0x89e8` a strelba jeepu; kolizni trida bit 2~~ **hotovo** | 1 den |
| 4 | ~~Skok `0x91e8` vcetne zmeny kolizni tridy a gravitace~~ **hotovo** | 0,5 dne |
| 5 | ~~SWAP plosiny (`fp@(3548)`) a dopravnik (`0x9172`, `0xad98`)~~ **hotovo — ukazalo se, ze k tomu patri cela druha podoba vozidla, lod `0x8e26`** | 0,5 dne (podceneno) |
| 6 | Dva hraci naraz: skore, zivoty, respawn a continue na obou slotech | 1 den |

## 5. Otevrene otazky

- **Vstup pro dva hrace.** Original ma dva joysticky. V prohlizeci
  pripada v uvahu rozdelena klavesnice (sipky + WASD) nebo Gamepad API.
  Neni to otazka vernosti, ale ergonomie — rozhodne uzivatel.
- **Kolizni trida bit 2.** `a2c6` d1 ji uz nese u vsech objektu, takze
  data mame; jde jen o to zapojit druhou vetev vyhodnoceni.

## 6. Co presne je v davce 1

- `PLAYER_SLOTS` podle `0x6f46` vcetne `+56`/`+66`/jmen
- pripojeni slotu 2 na fire za kredit (`tryJoinJeep`), `g.players = 2`
- aktivni prava pulka HUD pres spolecne `hudStatusTextFor`
- jeep se rodi pres `0x9046`, **ale se zapnutym BOBem vrtulniku** -
  `respawnBobField` skryva jen toho hrace, ktery se prave rodi. Diky tomu
  jeep nevznikne na vrtulniku (zmereno: 160/152 proti 160/192)
- pohyb tabulkou `0x959e` rychlosti `+356 = 640`: 2,5 px/t kardinalne,
  181*640/65536 = 1,767578 px/t diagonalne (kontrakt v `tools/uitest.py`)
- clamp `0x94f0` vcetne stropu `fp@(3558)` (`g.jeepFloorY`)
- kolize `0x9328` pohledem o krok dopredu a rozmacknuti `0x9314`
- smrt a respawn po 100 VBL, `g.jeepLives`
- bonusy bosse `0xc9a2` uz pocitaji oba zijici hrace

**Rozdeleni klaves** (neni v originale, ten ma dva joysticky): sipky +
mezernik = slot 1, WASD + levy shift = slot 2. Dokud slot 2 nehraje,
ovladaji WASD dal slot 1, aby se hrani o samote nezmenilo.

## 7. Co presne je v davce 3

**Vez `0x89e8`.** Vazane dite (`0x6144`, `+367 |= 13`), ktere `0x62d2`
polohuje na rodice plus jeden krok vlastni rychlosti - `+332/+336` z
tabulky `0x8a80` je tedy pevny ofset. Ofset miri OPACNE nez hlaven
(zaklad vezicky vzadu), coz sedi se stredy snimku `JEEPHELI#9..#16`:
#9 ma `ox -4` pri sirce 19 (hlaven doprava), #15 `oy -13` pri vysce 20
(hlaven nahoru).

Klicova mechanika je na `0x8a32`: testuje se **bit 7** vstupu, coz podle
`0x7272` neni pulz palby, ale SYROVY stav tlacitka (bit 5 je az kadenci
hradlovany pulz). S drzenou palbou se proto vez neotaci a jen strili;
po pusteni zase sleduje paku. Kdyz je paka na stredu, vez si vezme uhel
rodice (`0x8a3e`), tedy posledni smer jizdy.

**Palba ve vsech osmi smerech.** `0x8b86` je osm smerovych podtabulek
pro `0x8aa0`, kazda s peti zaznamy pro lichou silu a ctyrmi pro sudou;
zaznam je `(vx, vy, dx, dy)`. Rezim `+104` pouzije rychlost sveho
zaznamu, rezim 0 rychlost PRVNIHO zaznamu LICHE tabulky i pro sudou silu
(`0x8ae6` ji cte pred posunem, `0x8b28` ji drzi po celou salvu). Snimek
strely je `((d2 << 4) + 0x1001) >> 9`, tedy 8..15 podle smeru.

Tabulka je vytezena z AMPROG.OBJ a **reprodukuje presne ty hodnoty, ktere
v prepisu drive staly rucne opsane pro smer nahoru** (usti `(0,-8)`,
`(-4,0)`, `(4,0)`, `(-8,8)`, `(8,8)`, spread `(0,-9)`, `(-1,-8)`, ...)
i radial `0x8dd6`. Vrtulnik ted jde stejnou rutinou s uhlem zamcenym na
192, takze mu z ni vzdy vyjde tentyz smer 6 a snimek 14.

**Kolizni trida bit 2 (`+522`).** `a2c6` d1 → `+504`: bit 1 = vzdusny
(zabije vrtulnik), bit 2 = pozemni (zabije jeep), bit 5 = sestrelitelne.
Trida 34 ohrozuje jen vrtulnik, 36 jen jeep, 38 oba, 32 ani jednoho.
Tabulka `A2C6_CLASS` ma 69 chovani, z toho 37 s bitem 2; sest chovani,
u kterych se konzervativni parser zastavi na cili skoku, je docteno
rucne z binarky (inst2 36, inst3 38, inst4turret 38, inst5 38, plat 36,
tank 36). Trida `0x8000` (geyser, orb, piston, inst3emit) nema ani jeden
z bitu - kontakt resi vlastnimi hazardy.

Sweep jeepu je zamerne SAMOSTATNY, aby cesta vrtulniku zustala presne ta,
na ktere stoji `compare.py`. Vrtulnik proto porad pouziva svuj rucne
overeny seznam chovani, ne tuhle tabulku.

## 8. Co presne je v davce 4

Skok se ukazal bohatsi, nez rikal puvodni rozpis:

- **Automaticky spoustec.** `+282` neni jen timeout: `0x91c4` ho drzi na
  15, dokud jeep NENI zablokovany. Kdyz do prekazky tlaci, `0x9136` ho
  ubira a po patnacti ticich jeep sam vyskoci. Stani na miste dava 5
  (`0x91a0`). Rucni skok je bit 6 vstupu.
- **Prohozeni kolizni tridy, ne jen jeji vypnuti.** `+504` bit 4 -> bit 3
  vymeni handler: `0x654c` da `+518` (udalost 1 = vzdusne objekty),
  `0x6558` zpatky `+522` (udalost 2 = pozemni). Ve vzduchu tedy jeep
  prehopne tank, ale muze do nej narazit letec.
- **Vyska `+328`** se integruje v `0x62d2`: rychlost += zrychleni, pak
  poloha += rychlost, a pri podteceni pod nulu se vsechny tri longy
  vynuluji naraz. Zmereno: skok trva **58 tiku** a ma vrchol **27,3 px**.
- **Chveni na zemi.** `0x9154` losuje jen DOLNI slovo `+340`, tedy
  zlomek rychlosti, a drzi gravitaci. Jeep se tim chveje o 0 az ~4 px a
  **spotrebovava jedno cteni PRNG za tik**. Protoze `z` posouva jen stin
  (`0x6364`), je to videt jako poskakovani stinu pod vozem.

Klavesa skoku je `q` (slot 2). U ovladace typu 2 ma i original
samostatnou klavesu (`0x71ac` sklada bit 6 z `fp@(-28)`), u joysticku je
to druhe tlacitko nebo dvojity tap smeru.

## 9. Co presne je v davce 5

Rozpis rikal "SWAP plosiny a dopravnik, 0,5 dne". Byl **spatne**: plosiny
nejsou dekorace, ktera by neco odemykala, ale **prepinac mezi dvema
podobami vozidla**. Slot 2 ma vedle jeepu jeste lod `0x8e26`.

- **Dvojice plosin.** `0xac6a` (SWAP#0, A) a `0xacb6` (SWAP#1, B) zapisou
  po radku 32 svou polohu do sve dvojice globalu a vynuluji tu druhou;
  plati vzdy jen pozdejsi. Pak cekaji na `fp@(3548)` a teprve pak zapisou
  `fp@(3558)` = strop pro `0x94f0`.
- **Prepnuti** `0x94c2`/`0x94d0` kazdy tik: `y - 64 <= protejsi plosina`
  -> `0x6160` zalozi druhy tvar, `0x6db4` ukonci tenhle. Novy tvar jde
  pres `0x9046` a `0x90a0`/`0x8e38` jej prenese na jeho plosinu.
  **Zmereno v RIVERu**: lod vznikne na `x = 270`, jeep zpatky na
  `x = 303` — presne souradnice plosin z mapy.
- **Lod** ma rychlost 768 (3 px/t proti 2,5), grafiku `#31`/`#25`,
  **dojezd** (`0x8f22` ubira osminu rychlosti misto nulovani), brazdu
  `0x9358` kazdy ctvrty tik za jizdy a kazdy sestnacty VBL pri stani,
  a **vetsi houpani** (zlomek od `0x8000`, gravitace `-3072`).
  Vez, skok i kolize s terenem jsou spolecne.
- **Stopy jeepu** v pasmu `0xad30` jsou tentyz dekal jako u veze tanku,
  jen po trech ticich misto po dvaceti.

V prepisu jsou oba tvary jednim objektem s `form: "jeep" | "boat"`.
Original misto toho ukonci jednu ulohu a zalozi druhou, ale stav, na
kterem zalezi (zbran, zivoty, skore), stejne zije v rodici `+276`.
