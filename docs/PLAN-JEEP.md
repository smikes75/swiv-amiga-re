# Plan: JEEP a druhy hrac

Posledni velka chybejici cast hry. Vrtulnik je hotovy, jeep existuje jen
jako prazdna pulka HUD. Tenhle dokument shrnuje, co uz je zmerene v
`work/prog.txt`, co presne chybi, a v jakych davkach to jde udelat.

Stav k 2026-09-10: **davka 1 hotova**, zbytek jeste ne. Vse nize je
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
| 2 | Korutina `0x9090`: pohyb po zemi, clamp `0x94f0`, kolize `0x9328`, rozmacknuti `0x9314` | 1–2 dny |
| 3 | Vez `0x89e8` a strelba jeepu; kolizni trida bit 2 na vsech pozemnich objektech | 1 den |
| 4 | Skok `0x91e8` vcetne zmeny kolizni tridy a gravitace | 0,5 dne |
| 5 | SWAP plosiny (`fp@(3548)`) a dopravnik (`0x9172`, `0xad98`) — dnes mrtve hooky | 0,5 dne |
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
