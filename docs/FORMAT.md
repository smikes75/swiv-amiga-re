# SWIVFIX.ADF — formát diskety, zaváděcí řetěz a oba packery

Vše níže je **odvozeno z obrazu diskety**, ne opsáno odjinud. Každé tvrzení
jde ověřit skriptem v `tools/`.

## 1. Co to je

`SWIVFIX.ADF` je disketa hry **S.W.I.V.** (Storm / The Sales Curve, 1991),
vertikální scrollovací střílečka. Řetězce v rozbaleném bloku na `0x60000`
uvádějí původ:

```
S.W.I.V from Storm/The Sales Curve
Original cracked by The Company
Fixed for 680x0 / AGA all current kicks and memory configs   ... N.O.M.A.D
```

To je důležité pro plánování: obraz **není originál**, je to crack s další
vrstvou oprav navrch. Blok na `0x60000` (21 548 B) je tahle cizí vrstva —
záplaty pro 68020+/AGA plus textové intro — **ne kód hry**.

## 2. Bootblock

Sektory 0–1. Standardní `DOS\0` a platný kontrolní součet, aby to Kickstart
zavedl, ale **na místě ukazatele na rootblock je podpis `YETI`** (offset 8)
místo obvyklé 880. Rootblock 880 je smetí — **disketa nemá AmigaDOS
souborový systém**, je to lineární obraz s vlastním zavaděčem.

Kód bootblocku začíná na offsetu `0x0C`, dělá `AllocAbs` a pak tři čtení
přes `DoIO` na trackdisk. Podstatné je, že používá **obyčejný lineární
bajtový offset** — žádné MFM triky, žádný vlastní formát stopy:

| RAM | disk (bajt) | sektor | délka | co to je |
|---|---|---|---|---|
| `0x50000` | `0x0D9400` | 1738 | 11 264 B | vlastní zavaděč hry (nezabalený) |
| `0x30000` | `0x0D5E00` | 1711 | 2 560 B | dekrunčer B + náklad |
| `0x70000` | `0x0D6A00` | 1717 | 5 632 B | dekrunčer A + náklad |

Pak:

```
jsr  0x70000     ; dekrunčer A rozbalí 21 548 B na 0x60000 a skočí tam
jmp  0x30000     ; dekrunčer B rozbalí 2 408 B na 0x40000, rts do něj
```

Blok na `0x40000` vypne přerušení a DMA, přepíše vektory a skočí na
`0x50070` — do vlastního zavaděče hry.

**Ochrana proti kopírování v tomhle obrazu není žádná.** To je největší
jednotlivá dobrá zpráva celého průzkumu.

## 3. Entropie: všechno ostatní je zabalené

| sektory | entropie | výklad |
|---|---|---|
| 0–1663 | 7,3–7,8 | zabalená data (maximum je 8) |
| 1664–1759 | 5,1 | zavaděč a dekrunčery, nezabalené |

V celém obrazu **není jediná signatura známého packeru** (PP20, IMP!,
RNC, ATN!) ani jediná hlavička AmigaDOS hunku. Hra si veze vlastní dva
formáty a vlastní rozbalovací rutiny.

## 4. Katalog souborů

Sektor 12 nese katalog se jmény: `AMDLS0.CAT`, `AMPROG.OBJ`, `HS1.TX`,
`TITUNE.MOD`, `BIGEXPL.SN` a fragmenty dalších (`JEEP`, `MEDTANK`,
`FACES`, `SKYE`, `AIR`, `EGG`…). Fragmenty proto, že i katalog je zabalený —
LZ zápas nahradí opakovaný podřetězec odkazem, takže ze jména přežije jen
kus.

Předpona `AM` je stopa po **vývoji pro víc platforem**: SWIV vyšel i na
Atari ST a nástroje označovaly amigovské varianty souborů `AM…`. Řetězec
`AMPROG.OBJ` je i v zavaděči na `0x50000` (offset `0x76A`).

## 5. Formát B — Bytekiller

Rutina má 160 B (`src-asm/decrunch-b.asm`), přepis v `tools/depack.py`
jako `unpack_b()`.

Hlavička bloku (8 B, čte se dopředu):

```
+0  long   délka rozbalených dat
+4  long   délka zabaleného proudu (od +8)
```

Proud se čte **pozpátku od konce po longwordech**, bity zevnitř longwordu
**od nejnižšího**, čísla se skládají **nejvyšším bitem napřed**. Zapisuje
se taky pozpátku, od konce cílového bloku. Hotovo, když se ukazatel zápisu
dostane na začátek.

Čtení bitu je klasický trik s zarážkou — nejvyšší nastavený bit longwordu
slouží jako značka konce, takže se nemusí počítat:

```
lsr.l  #1,d0      ; C = X = spodní bit
bne.s  hotovo     ; longword ještě není vyčerpaný
move.l -(a0),d0   ; dobrat další, X zůstává
eor.l  d0,d5      ; kontrolní součet
roxr.l #1,d0      ; X -> bit31 jako nová zarážka, nový spodní bit -> C
```

Kódování:

| bity | význam |
|---|---|
| `0 0` + 3 bity | 1–8 literálů (každý 8 bitů) |
| `0 1` + 8 bitů | zápas délky 2, offset 8 bitů |
| `1 00` + 9 bitů | zápas délky 3, offset 9 bitů |
| `1 01` + 10 bitů | zápas délky 4, offset 10 bitů |
| `1 10` + 8 + 12 bitů | zápas délky 1–256, offset 12 bitů |
| `1 11` + 8 bitů | 9–264 literálů |

Offset se počítá **od aktuální pozice zápisu dopředu** (`lea (a1,d2.l),a3`,
pak `move.b -(a3),-(a1)`), protože se jede pozpátku.

**Kontrolní součet zdarma.** Rutina XORuje všechny přečtené longwordy do
`d5` a na konci přečte ještě jeden navíc. Správně rozbalený blok skončí
součtem 0 — to je hotová verifikace, kterou `unpack_b()` vrací.

## 6. Formát A

Rutina má 296 B (`src-asm/decrunch-a.asm`), přepis jako `unpack_a()`.
Stejná 8bajtová hlavička, ale jinak je to jiný formát:

- čte se **po wordech**, ne longwordech
- čísla se berou **přímo ze spodku registru** (nejnižší bit napřed), maskou
  z tabulky `0x0001, 0x0003, 0x0007, …, 0x3FFF`
- **nemá kontrolní součet**
- proud končí dvěma poli navíc: 4 B počátečního registru a 2 B s počtem
  platných bitů v něm
- rutina umí **přesunout zabalená data**, pokud by si je výstup přepsal

Kódování:

| bity | význam |
|---|---|
| `1` | jeden literál (8 bitů) |
| `0` + délka + offset | zápas |

Délka — unární prefix vybírá šířku pole i bázi:

| prefix | pole | délka |
|---|---|---|
| `0` | 1 bit | 2–3 |
| `10` | 2 bity | 4–7 |
| `110` | 4 bity | 8–22 |
| `111` | 8 bitů | 23–278 |

Hodnota 22 je **ukradená jako úniková značka** pro dlouhý běh literálů
(pak následuje 1 bit volby šířky: `1` → 5 bitů, `0` → 14 bitů, a počet je
15 + hodnota). Kvůli té díře se všechny délky nad 22 o jedničku sníží,
takže řada zůstane souvislá.

Offset:

| prefix | pole | offset |
|---|---|---|
| `0` | 9 bitů | 32–543 |
| `10` | 5 bitů | 0–31 |
| `11` | 14 bitů | 544–16 927 |

Rozdělení podle velikosti offsetu je to, proč A balí výrazně líp než B
(24,7 % proti 99,3 % na jejich vlastních nákladech — i když ty náklady
jsou různé, poměr o formátu něco vypovídá).

## 7. Co z toho plyne pro projekt

Hotovo:

- disketa je nechráněná a zavaděč triviální
- oba packery jsou rozebrané a přepsané, obojí ověřené (B kontrolním
  součtem, A tím, že z něj vypadne platný 68k kód a čitelné řetězce)

Další krok je vlastní zavaděč hry na `0x50000` — ten drží klíč k tomu, jak
se čte katalog a kde na disketě leží jednotlivé soubory. Teprve až budou
soubory venku, půjde říct, **kolik je v `AMPROG.OBJ` skutečně kódu** — a
tím pádem jestli má reimplementace smysl.
