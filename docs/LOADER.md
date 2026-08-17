# Zavaděč: co je oprava cracku a co je hra

Blok načtený na `0x50000` (11 264 B) **není zavaděč hry**, jak to na první
pohled vypadá. Je to obal opravy *N.O.M.A.D* a vlastní zavaděč hry je až
uvnitř něj. Kdo si toho nevšimne, anotuje týden cizí kód.

## Vrstvy

```
bootblock
 └─ 0x70000  dekrunčer A ──► 0x60000   vrstva cracku: záplaty 68020+/AGA, intro
 └─ 0x30000  dekrunčer B ──► 0x40000   instalátor záplat
                              └─ kopíruje 106 B na adresu 0x90
                              └─ kopíruje 256 B obsluhy TRAP #0 na 0x7FF00
                              └─ píše 0x4E40 (trap #0) na 0x50764
                              └─ jmp 0x50070
      0x50000+0x70            obal opravy: AGA reset, hledání RAM
                              └─ přesune 7424 B (z +0x1D8) do fast RAM
                                 └─ **vlastní zavaděč hry**
```

Nástroj `tools/unboot.py` vysype i ten vnitřní zavaděč jako `build/loader.bin`.

## Obal opravy (`0x50000`, offsety uvnitř bloku)

| offset | co dělá |
|---|---|
| `0x00` | `BPLCON0/1/2/3/4` a `FMODE` zpět do stavu ECS — **AGA reset** |
| `0x70` | vstupní bod (skáče se sem z `0x40000`) |
| `0x84` | nastaví vektor `TRAP #1` a trapem se dostane do supervisoru |
| `0x126` | projde paměť po 512 KB, `TypeOfMem` na každý blok, postaví tabulku |
| `0x1AE` | najde v té tabulce blok daného typu |
| `0xE8` | `AllocAbs` 11 264 B — rezervuje oblasti, které použil bootblock |

Tabulka paměti má desetibajtové záznamy `(word typ, long začátek, long
délka)` a končí `0x8001`. Hledá se **typ 5** (`MEMF_PUBLIC|MEMF_FAST`),
při neúspěchu **typ 3** (`MEMF_PUBLIC|MEMF_CHIP`); když není ani jedno,
`reset`. To je právě ta inzerovaná podpora „all current memory configs".

## Kam se hra načte

Obsluha `TRAP #0` na `0x7FF00` skládá záplatovací rutinu **za běhu** na
adrese `0x8` a pak píše do už načteného kódu hry:

```
a1 = 0x16000                  ; a 0xC11500, když je a6 >= 0xC00000
byte 0x4A -> a1@(100)
byte 0x4A -> a1@(10148)
word 0x601A -> a1@(154)
```

Takže **kód hry sedí na `0x16000`** a oprava mu přepisuje tři místa.
Trap se spouští hned po načtení `AMPROG.OBJ`, tedy ve chvíli, kdy je hra
v paměti a ještě neběží.

## Vlastní zavaděč hry (`build/loader.bin`, 7424 B)

Offsety níže jsou uvnitř toho bloku.

| offset | co to je |
|---|---|
| `0xE6` | `lea 0x16DC(pc),a6` — **báze proměnných**; celý zavaděč je a6-relativní |
| `0xF6` | vlastní vektor `TRAP #1`, přechod do supervisoru, vlastní zásobník |
| `0x108` | `a4 = 0xDFF000`, `DMACON = 0x8200`, `INTENA = 0xC000` |
| `0x142` | vlastní obsluha VERTB na vektoru `0x6C`, pak `INTENA = 0x8020` |
| `0xCFE`, `0xD0E` | alokátor (dvě varianty) |
| `0x696` | **otevření souboru podle jména** → vrací délku |
| `0xA14` | **čtení souboru** — proudové, s bufferem a stavem v proměnných |
| `0x592` | řetězec `AMPROG.OBJ` |
| `0x4CF`, `0xCA4`, `0x196C` | znakové tabulky (číslice, hex, abeceda) |

Sekvence, kterou se hra zavede (offset `0x55C`):

```
lea  AMPROG.OBJ(pc),a0
bsr  0x696          ; otevřít, d0 = délka
move.l d0,-1406(a6)
bsr  0xCFE          ; alokovat, a0 = kam
bsr  0xA14          ; načíst
bsr  0x6B6          ; zavřít
bsr  0x17FC
...                 ; vynulovat 32 KB proměnných
jmp  0xBE           ; absolutní 0xBE = trampolína, kterou tam dal fix
```

Disk se čte **přímo hardwarem**, ne přes `trackdisk.device`:
`0xBFD100` (CIA-B PRB) drží motor, výběr jednotky a krokování hlavy,
`0xBFE001` (CIA-A PRA) se čte na `/RDY`, `/TK0` a `/CHNG`.

## Negativní nález, který stojí za zápis

Prohledání celé diskety na osmibajtovou hlavičku obou packerů
(`tools/scan.py`, krok 512 B) našlo **nula** kandidátů. Soubory tedy
nejsou na disketě uložené jako samostatné zabalené bloky s hlavičkou —
rozvržení drží katalog a zavaděč je čte proudově.

To je důležité: **cesta ke datům nevede zkratkou přes hledání hlaviček,
ale přes rozbor katalogu.**

## Další krok

Rozebrat `0x696` (jak se jméno hledá v katalogu) a `0xA14`/`0xA94`
(jak se čte, jak vypadá buffer, kde je mapa sektorů). Teprve to dá
rozvržení diskety a s ním všechny soubory.
