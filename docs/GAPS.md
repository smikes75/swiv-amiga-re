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

- **ctvrty potomek `0xcaac`** (GOOSE#8) neni cast tela — nesbiha se
  k rodici, ale leti vlastni hadovitou drahou (`0xcb14`: `+356 = 0x1200`,
  uhel 64, pak stridave `±8` po sesti krocich). Je to doprovod, ne kus
  bosse; **neprepsany**.
- **bodovy soucet po smrti**: vetev `0xc934` prochazi smyckou `0xc950`
  tabulku slov a pricita je do `fp@(3560)`. Tabulka neni prectena,
  takze boss zatim **nedava zadne body** — radsi nula nez vymyslene
  cislo.

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

- **zablesk u typu 4**: `0x8852` zalozi korutinu `0x885a`, ktera nastavi
  `fp@(11166) = 256` (plna bila) a po 50 snimcich skonci — **krok
  doznivani nikde nenastavuje**. Bez neho by obrazovka zustala bila,
  takze to neni prepsane; chybi najit, kdo `fp@(11168)` v tuto chvili
  drzi.
- **souhra `+98` s tabulkou `0x70c0`**: bonusy 2 a 4 prepisuji prodlevu
  palby primo, ale jestli ji zapis z tabulky pri zmene sily zase
  prebije, neni prectene. V prepisu ma bonus prednost.

## Co uz je vedomo jinde

Starsi seznam odchylek je v `MAPS.md` („Deliberately not rendered")
a tyka se statickych renderu, ne behu hry.
