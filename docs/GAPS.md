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

## 2. TOWN boss (GOOSE) — zalozeny, ale inertni

`GOOSE.LIN` snimek 0, gfx `0x0017` → korutina **`0xc78a`**. V TOWN je
presne jeden. Dnes je to zamerne necinny placeholder.

Korutina je pritom cela citelna:

| adresa | co dela |
|---|---|
| `0xc7a0` | `a2c6(gfx 23, coll 0, margin 0, hp 0, body 0, cost 100)` — rodic je bez HP, je to nosic |
| `0xc7b6` | flag bit 4 = airborne (kompenzuje scroll, jako FODDERA/BIRD) |
| `0xc7bc` | start 288 px pod obrazem, x = 160 (stred), `+328 = 32` |
| `0xc7d2`–`0xc7ee` | **ctyri `bsrw 0x6144`** — casti `0xcaac`, `0xc9f0`, `0xc9ec`, `0xc9e2` se pripoji za letu |
| `0xc80a` | `+336 = -2`, tedy nalet |
| `0xc818`–`0xc824` | leti, dokud `mapY − scroll > 72`; pak zastavi |
| `0xc842` | **teprve ted `+360 = 25` HP** — dokud se sklada, je nesmrtelny |
| `0xc848` | callback `0xc974` pres `0x653e` |
| `0xc934` | vetev pri predcasnem konci |

Rizene rakety: `HOMING.LIN`, telo navadene strely uz popsane
(`0x8530` / `0x8566`, viz BEHAVIORS.md).

**Dalsi krok:** prepsat `0xc78a` vcetne ctyr casti a `0xc974`.

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

**Dalsi krok:** precist callback na `0x9734` a ucinky vsech ctyr typu.

## Co uz je vedomo jinde

Starsi seznam odchylek je v `MAPS.md` („Deliberately not rendered")
a tyka se statickych renderu, ne behu hry.
