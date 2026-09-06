# Co ze sesterskeho projektu (Turrican) muze byt uzitecne pro SWIV

Zapsano 2026-09-06 z `Turrican-projekt/` (viz tam `docs/RECOMP.md`). Vsechna
cisla nize jsou **zmerena na `build/files/001_AMPROG.OBJ`**, ne odhadnuta;
postup je u kazdeho uveden, aby se dal prepocitat.

Nic z toho neni navrh, jak SWIV prepsat jinak. SWIV ma prepis rucne psany v
JS a to je pro nej spravna cesta - 155/155 korutin je hotova prace, ktera se
zahazovat nema. Nize jsou tri veci, ktere by k ni mohly pridat **dukaz**,
a jedna, kterou naopak Turrican potrebuje od SWIVu.

## 1. Overeni po jednom volani, bajt po bajtu

Dnesni `tools/compare.py` porovnava **cele snimky** proti headless vAmize s
rackou a seznamem znamych zbytkovych rozdilu ("sumova textura terenu, faze
animaci"). To je dobra celkova pojistka, ale slabe rozliseni: kdyz se
korutina splete o jedno pole, snimek to nemusi ukazat.

Turrican pouziva jemnejsi metodu (`tools/recomp_test.py`):

1. `break at $ADR N` na **volajici instrukci** a `break at $NAVRAT N` na
   navratove adrese pri stejnem poradovem pruchodu -> ohraniceni **prave
   jednoho volani**; mezi obema zastavenimi nebezel zadny jiny kod hry,
2. u obou se ulozi **cela chip RAM (512 KB) + D0-D7/A0-A7/CCR**
   (`VAHL_ONSTOP` -> `r cpu` + `mem save bin`, VAHeadless s `-v`),
3. porovna se kazdy registr, priznak a **kazda adresa, kam nas kod zapsal**;
   zvlast se vypisou adresy, ktere se v emulatoru zmenily, ale nas kod je
   nezapsal ("cizi zapisy" = preruseni, blitter, jina rutina).

Pro SWIV to znamena: misto "snimek sedi nad prahem" se da rict **"korutina
FODDERA pri tomto volani zapsala presne tato pole s temito hodnotami, stejne
jako original"**. Prekazka je jedna a je to prace, ne vyzkum: JS prepis ma
vlastni reprezentaci stavu, takze se musi namapovat na offsety zaznamu
(`+320`, `+324`, `+332`, `+364`, `+538`, ...) - ty uz `docs/BEHAVIORS.md` ma
zdokumentovane.

Hotove nastroje k prevzeti: `Turrican-projekt/tools/bpstate.py` (stav na
breakpointu; funguje na jakekoli hre) a `tools/recomp_test.py` (porovnani).

## 2. Rekompilat jako spustitelna reference k rucne psanemu JS

`Turrican-projekt/tools/recomp.py` preklada kod 68000 do C: jedna rutina =
jedna funkce, registry v kontextu, pamet v poli se zaznamem zapisu, na
neznamou instrukci **tvrde spadne** (tichy preklad neceho jineho by byl
horsi nez zadny). `--auto ADRESA` najde telo grafem toku vcetne volanych
rutin, takze data ulozena mezi kodem se nectou jako instrukce.

Zkouska na AMPROG.OBJ (koreny: vstup `0xc74` + 73 korutin z
`build/dispatch.json` + 122 symbolu z `tools/syms.json`):

| | |
|---|---|
| nalezeno rutin | **330** (8 074 instrukci) |
| neznamych slov | **27 = 0,33 %** (`exg`, `movep`, data mezi kodem) |
| absolutni pristupy mimo RAM | **16 custom + 4 CIA** |
| neprimych skoku/volani | **208** |

Dekoder tedy na SWIVu funguje skoro uplne, jak je. K cemu by to bylo: mit
vedle rucne psane korutiny **strojovy preklad te same korutiny**, pustit oba
nad stejnym vstupnim stavem a porovnat zaznam objektu. Chyby v prepisu se
najdou bez emulatoru ve smycce a da se to projet pres tisice stavu. Pri 155
rucne psanych korutinach je tohle podle mereni nejvetsi mozna vyhra.

### Co jsem kvuli SWIVu musel do nastroje doplnit

- **A6 tu neni `$dff000`** (v Turricanu je), ale baze globalu; posuny
  -1530 az +12534. Konvence se predava zvenci (`scan68k.py --a6`).
- **Neprima volani pres zapornou bazi A6 jsou skokova tabulka zavadece** -
  presne ta, kterou mate pojmenovanou v `syms.json` `loader_jumptable`
  (`-1418 ldr_wait_a`, `-1438 ldr_wait_b`, `-1502 ldr_alloc_d`, ...).
  `recomp.py` proto dostal prepinac **`--stub An:POSUN:JMENO`**: takove
  volani se prelozi na volani stubu doplneneho zvenci.

Se stuby se prelozi 2 ze 73 korutin. Zbytek konci na `jsr (a0)`, kde
ukazatel pochazi **ze zaznamu objektu** - napr. `movea.l (542,a5),a0`
na `0x6464` v rutine `0x62d2` (event callback). To neni prekazka dekoderu,
ale dispatch: vyresi se tabulkou pres vsechny prelozene vstupy. **Turrican
ma stejny vzor** (`[0x198]` rutina podurovne, chovani objektu na `(34,a5)`),
jen 22x misto 208x - SWIV na nem stavi cely scheduler korutin.

## 3. Objektivni mira uplnosti prepisu

`docs/TOWN-PARITY.md` poctive rika, ze "155/155 neznamena pixelove hotovy
level - pocita hlavni mapove routy, ne globalni renderer, pomocne potomky,
vsechny animacni prikazy ani vsechny specialni audio call-sites".

`Turrican-projekt/tools/scan68k.py` umi presne tohle zmerit: projde graf
toku od zadanych korenu a rekne, ktere **dosazitelne** rutiny existuji.
Na AMPROGu naslo **330 rutin, z toho 141 nema jmeno v `syms.json`**;
nejvetsi nepojmenovane jsou `0x6178` (64 instrukci), `0x3f58` (59),
`0x4c1c` (44), `0x4cb2` (44), `0x64b6` (41). Nektere z nich uz nejspis
prepsane jsou (jen bez jmena), ale ten seznam je levny zpusob, jak najit
kod, o kterem prepis nevi.

## 4. Opacnym smerem: co Turrican potrebuje od SWIVu

**Model Pauly.** SWIV uz ma v `game.html` ctyrhlasy model s CIAB
schedulerem (`priority*4` guard, strict `>`, stereo-pair preference s
fallbackem, persistentni `0x56e6` noise scratch, VHPOS perturbace PRNG) -
viz `docs/SOUND.md`. Turrican zvuk zatim nemeril vubec (5 rutin, 24
pristupu na registry Pauly) a az na nej dojde, zacne se tam, ne od nuly.
Zapsano v `Turrican-projekt/docs/GAPS.md`.

## Co si z toho vzit prakticky

Nejlevnejsi prvni krok, pokud by o to byl zajem: vybrat **jednu** korutinu z
`dispatch.json`, ohranicit jedno jeji volani breakpointy podle bodu 1 a
porovnat pole zaznamu objektu proti rucnimu JS prepisu. Je to prace na
odpoledne a odpovi to na otazku, jestli ta jemna metoda u SWIVu drzi -
drive nez se do ni cokoli velkeho investuje.

**Past, kterou znam a stoji za zminku i mimo rekompilaci**: v dekoderu 68000
musi test na `MOVEM` vyloucit adresni rezim 0/1, jinak se `ext.w` (`0x4880`)
dekoduje jako `movem` a od toho mista se rozjedou hranice instrukci. Chyba
je ticha - disassembly vypada verohodne, jen je posunuta.
