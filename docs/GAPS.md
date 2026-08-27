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

## 3. Bonusovy TOKEN — neprepsany

`TOKEN.LIN` neni v dispatchi (nezaklada ho mapa, ale kod).
Korutina **`0x96d8`**:

- `a2c6(gfx 24 = TOKEN#0, coll 32, margin −16, hp 0, body 0, cost 5)`
- flag bity 0 a 4; x se orezava na 8–312, takze token neuteče z obrazu
- update `0x9780` prepina `+276` po **4 ticich** pres tabulku `0x97bc`
  = snimky `0x0218, 0x0418, 0x0618, 0x0818`, tedy **TOKEN#1..#4**
  → bonus **cykluje ctyri typy** a po 12 cyklech (`+280`) se zamkne
  na typ 4
- kolizni callback instalovany na `0x9734`

Sem patri hlasena **ochranna bublina**: hrac do ni naleti a v originale
ho urcitou dobu chrani, v prepisu misto toho vybuchne. Ktery ze ctyr
typu to je, se docte z kolizniho callbacku — **zatim neprecteno**.

**Stav:** bonusy uz **vznikaji** — boss je po smrti rozhazuje do kruhu
a v `game.html` se pohybuji i stridaji ctyri typy podle `0x9780`.
Chybi **ucinek pri sebrani**: kolizni callback `0x9734` neni precteny,
takze token na dotek nic nedela (a hrace rozhodne nezabiji).

**Dalsi krok:** precist callback na `0x9734` a ucinky vsech ctyr typu.
Tam patri hlasena ochranna bublina.

## Co uz je vedomo jinde

Starsi seznam odchylek je v `MAPS.md` („Deliberately not rendered")
a tyka se statickych renderu, ne behu hry.
