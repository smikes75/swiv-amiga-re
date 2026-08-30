# Mezery mezi prepisem a originalem

Seznam toho, co v `game.html` chybi nebo nesedi. Kazda polozka nese
adresu, na ktere se to da v `AMPROG.OBJ` docist — stejne pravidlo jako
ve zbytku `docs/`: zadny odhad, jen misto v kodu.

Zdroj hlaseni: hrani prepisu proti originalu (2026-08-27).

## 1. Zvuky — chybi cely zvukovy engine

`game.html` prehrava **jediny** efekt: `BIGEXPL.SND` na ctyrech mistech.

Na disku jsou ale jen **dva** samply (`BIGEXPL.SND`, `SMART.SND`), takze
zbytek zvuku hra **negeneruje ze samplu** — dela je zvukovy engine
z dat v `AMPROG.OBJ`. Proto nesedi rozlet PROXMINE, plamenomet FLAME
a vetsina zasahu: nejde o spatne prirazeny sampl, ale o chybejici
kus enginu.

- **Rozsah:** neprepsany zvukovy engine (README ho vede jako castecne
  zmapovany).
- **Dusledek:** dokud engine nebude precteny, nelze zvuky doplnit
  "priblizne" bez porusení pravidla o nehadani.

## 2. TOWN boss (GOOSE) — PREPSANY 2026-08-27

`GOOSE.LIN` snimek 0 → `0xc78a`. Prepsano vcetne naletu, skladani ze
tri casti, palby (mireny granat + dve navadene) a kruhu bonusu; popis
je v [BEHAVIORS](BEHAVIORS.md), regrese v `tools/uitest.py`.
**TOWN tim ma 155/155 objektu na prepsanych korutinach.**

Zbyva u nej dvoje:

- ~~ctvrty potomek `0xcaac` = doprovod~~ — **uzavreno 2026-08-30**: je to
  pod zadokovany na `(0,+24)`, ktery se pak houpe na rameni 18 px
  (`0xcb14`–`0xcb76`); prepsano spolu s dokovanim `0xcb78`, odhozenim
  casti pri zasahu a blikanim/animaci tela, viz [BEHAVIORS](BEHAVIORS.md).
- ~~bodovy soucet po smrti~~ — **uzavreno 2026-08-30**: smycka `0xc950`
  neni skore, ale kontrolni soucet 27 329 slov programu pricteny k
  ukazateli na buffer mapy `fp@(3560)` (anti-tamper). Boss ma `d4 = 0`,
  tedy **0 bodu** je spravne; viz [TOWN-AUDIT](TOWN-AUDIT.md) 2.7.

## 3. Bonusovy TOKEN — PREPSANY 2026-08-27

`TOKEN.LIN` → `0x96d8`. Prepsano vcetne blikani, prepinani typu strelou
(`0x9780`) a vsech ctyr ucinku pri sebrani (`0x97c6`); tabulka viz
[BEHAVIORS](BEHAVIORS.md), regrese v `tools/uitest.py`.

**Hlasena ochranna bublina je bonus typu 3**: da hraci `+500` tiku
ochrany (`+108`, ~10 s) a 500 bodu. V prepisu uz funguje a bonus hrace
za zadnych okolnosti nezrani.

Pri tom se opravily dve veci jinde:

- `syms.json` vedl `0x653e` jako `anim_install`. Je to **instalator
  callbacku** (`+510`, bit 0 v `+508`); `0x6564` dela totez pro `+514`.
- `game.html` pocital stupen zbrane jako `weapon/5`. Tabulka `0x70c0`
  je bajtova a **indexuje se primo** hodnotou `+100`.

Zbyva:

- ~~zablesk u typu 4~~ — **uzavreno 2026-08-30**: je to smart bomba;
  `fp@(11168)` se za hry nezapisuje a z uvodni sekvence zustava **−4**
  (64 snimku doznivani). Smart bomba zabiji vse s aktivnim `+534`;
  prepsano v `game.html` (`smartBomb`), viz [BEHAVIORS](BEHAVIORS.md).
- ~~souhra `+98` s tabulkou `0x70c0`~~ — **uzavreno 2026-08-30**: tabulka
  se aplikuje jen pri (re)spawnu (`0x70c8`), bonusy plati do dalsiho
  spawnu. Prepsano (`applyWeaponTable`).

## 4. Hlaseni z 2026-08-30 — kolize, stit, hrac (PREPSANO)

Hloubkovy audit je v [TOWN-AUDIT](TOWN-AUDIT.md). Prepsano tehoz dne:

- kolize vrtulniku jen s tridou bit 1 (letci, MILL, GOOSE, HOMING, strepy,
  granaty); pozemni objekty ho uz nezabiji
- jadro miny = stit (`0x98c4`, `0x92a0`, orb `0x98f2`) a smart bomba
- hrac `0x9410`: 3 px/t, snimky 0..4, clamp, ochrana 200 s blikanim 8/8,
  respawn 100 snimku, start 2 strely, stin `(+16,+32)`
- HOMING sestrelitelna (1 HP, 7 bodu); hit flash u nepratel

GOOSE (dokovani `0xcb78`, pod `0xcaac`, odhozeni casti, HP od zastaveni,
blikani a anim tela, rotor, smrt bez bodu) prepsan tehoz dne. P0 auditu
je tim cely v `game.html`; otevrene zustavaji P1–P3.

## Co uz je vedomo jinde

Starsi seznam odchylek je v `MAPS.md` („Deliberately not rendered")
a tyka se statickych renderu, ne behu hry.
