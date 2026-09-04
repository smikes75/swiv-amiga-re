# Zadani: Turrican (Amiga) jako emulace s vlastnim vykreslovanim

Zadani pro samostatneho agenta v novem projektu. Vznika vedle hotoveho
projektu SWIV, ze ktereho prebira metodu, nastroje a dokumentaci. Cile
(slova zadavatele): **zachovani grafiky a presnosti originalu, maximalne
plynuly scrolling pri ruznych obnovovacich frekvencich, moznost vylepseni
obrazu, napriklad zobrazeni vetsi casti mapy a tim vyssi rozliseni.**

Pracovni jazyk cestina (v kodu a docs bez diakritiky), pravidlo
**„mereno, ne hadano"**: kazde tvrzeni o hre nese adresu v disassembly nebo
cislo snimku z emulatoru. Co nejde dolozit, se do kodu nedava a zapisuje
se jako otevrena otazka.

## 1. Rozhodnuti o architekture (uz je hotove, neotvirat znovu)

SWIV se prepisuje rucne do vlastniho enginu (`game.html`). Pro Turrican
je zvolena **jina cesta**, protoze cile jsou vernost a obraz, ne zmena
pravidel, a logika plosinovky je nekolikanasobne vetsi nez u shooteru:

1. **Herni logika bezi v emulatoru** (jadro vAmiga prelozene do WebAssembly
   nebo jiny 68000+OCS emulator schopny bezet v prohlizeci). Zadny prepis
   chovani nepratel, fyziky hrace ani bossu.
2. **Obraz emulatoru se nepouziva.** Vlastni renderer si po kazdem
   emulovanem VBL precte z RAM polohu kamery a tabulku objektu a kresli
   sam z extrahovane grafiky (dlazdice, sprity) v libovolnem rozliseni.
3. **Plynulost** = logika na pevnych 50 Hz, kresleni na frekvenci displeje
   s interpolaci mezi dvema poslednimi stavy (alfa = cas od posledniho
   VBL / 20 ms). Puvodni kamera se hybe po celych pixelech; pri
   zvetsenem vystupu se kresli i mezipolohy.
4. **Vetsi vyrez mapy** se dela ve dvou krocich: teren mimo puvodni okno
   z dat mapy (bez zasahu do hry), potom **cilene binarni patche
   konstant** (meze aktivace objektu a kamery), aby nepratele
   nevznikali na okraji stareho okna. Technika sirokouhlych hacku
   emulovanych her; patchuje se az po zmereni, kde konstanty jsou.
5. Zvuk zustava emulatoru (Paula).

Co se z SWIV **neprebira**: engine v `game.html`. Co se **prebira**: cely
postup cteni disassembly, nastroje pro zachyt snimku z headless vAmigy,
vzory kontraktu a sond, dokumentacni format.

## 2. Co lezi na tomto Macu a jak to volat

### 2.1 Projekt SWIV (predloha)

`/Users/mik/claude46/Amiga/SWIV-projekt/` (git, origin
`https://github.com/smikes75/swiv-amiga-re.git`). **Jen cist**, nemenit.

Precist na zacatku (v tomto poradi, cca 2 hodiny):

| soubor | proc |
|---|---|
| `docs/ZADANI-GRASS.md` sekce 2 az 7 | jak se cte disassembly, kostra objektu, cekani, pomocne rutiny, overeni, dokumentace - metoda, ktera se prenese 1:1 |
| `docs/ZADANI-RIVER.md` a `docs/ZADANI-ICE.md` sekce 2 | seznam skutecnych chyb pri prepisu (pasti) |
| `docs/ENGINE.md` | jak hluboko se popisuje zaznam objektu (+320 poloha 16.16, +332 rychlost, +504 trida...) - stejnou hloubku bude potrebovat renderer pro Turrican |
| `docs/LOADER.md`, `docs/FORMAT.md`, `docs/GRAPHICS.md`, `docs/MAPS.md` | jak se popisuje zavadec, packer, format spritu a map |
| `docs/TOWN-SURVEY.md` + `tools/survey/README.md` | jak se porovnava prepis s originalem po radcich mapy, ne po case |
| `docs/GAPS.md` | jak se vede seznam nemodelovanych veci |
| `tools/check.py` | vzor „kontraktu": jediny skript, ktery rika, co je dokazane |

Nastroje v `tools/` (Python 3, PIL, Playwright pro prohlizec):

| nastroj | prenositelnost |
|---|---|
| `tools/baseline.sh`, `tools/compare.py` | **vzor** pro deterministicke snimky originalu a pixelove porovnani (gamma tabulka `VAMIGA_LUT` v compare.py, raw format nize) |
| `tools/survey/behprobe.py`, `tools/uitest.py` | vzor Playwright sond a regresi v realnem Chromiu |
| `tools/survey/rows.py`, `montage.py`, `blobs.py` | korelace radku mapy, dvojice snimku, hledani objektu jako blobu - prenositelne po vymene cesty k mape |
| `tools/xref.py`, `tools/tasks.py` | graf volani a inventura `lea X(pc),a0` + volani zakladace nad vystupem objdump - prenositelne |
| `tools/scan.py`, `tools/unboot.py`, `tools/depack.py`, `tools/extract.py` | **postup** hledani zabalenych bloku a prochazeni zavadeciho retezce; samotne dekrunchery jsou SWIV-specificke |
| `tools/gfx.py`, `tools/map.py`, `tools/animscan.py`, `tools/dispatch.py`, `tools/spawns.py` | SWIV-specificke formaty; brat jako vzor struktury, ne kod |

Disassembler: `/opt/homebrew/bin/m68k-elf-objdump -D -b binary -m m68k:68000`
(viz `tools/tasks.py` radek 19). Vystup SWIV lezi ve `work/prog.txt`; pro
Turrican vznikne vlastni. Pozor na past ze SWIV: disassembler sleva
datova slova (animacni skripty, tabulky) do falesnych instrukci - vzdy
prepocitat bajty rucne.

### 2.2 Sdileny referencni adresar

`/Users/mik/claude46/Amiga/reference/` (README tamtez):

- `hw-docs/` Amiga Hardware Reference Manual: PDF s obrazky, OCR text pro
  grep, HTML zrcadlo `hrm-html/amigadev.elowar.com/read/ADCD_2.1/Hardware_Manual_guide/`
  (Copper node0047, Playfield node0061, Sprites node00AE/node00C4, Blitter
  node0118/node012B).
- `tools-bin/VAHeadless` - **headless vAmiga 5.0b1** (deterministicka,
  warp ~15x). Skript RetroShell jako argument:

```
regression setup A500_OCS_1MB "<Kickstart ROM>"
amiga set WARP_MODE ALWAYS
regression run "<ADF>"
wait 60                       # EMULOVANE sekundy od zapnuti
joystick2 press 1             # vstup: joystick2 press/unpress 1, pull up|down|left|right, release x|y
wait 1
joystick2 unpress 1
keyboard press 80             # F1 = 80
screenshot save out.png       # ulozi VZDY out.raw = RGB24 716x285, pak skonci
```

  Jeden beh = jeden snimek; serie casu = opakovane behy (deterministicky
  emulator, stejny cas = bitove stejny snimek). `tools-bin/adfshot.sh
  <adf> <prefix> <sekundy...>` to dela za tebe, `topng.py` prevede raw.
  Kickstart 1.3 lezi v `/Users/mik/Documents/FS-UAE/Kickstarts/` (viz
  cesta v `adfshot.sh`). Preklad VAHeadless ze zdroju vcetne pasti s
  libc++ je v `tools-bin/README.md`.
- `sources/` cizi 68k zdrojaky ke studiu (Unlicense/MIT), `demos/`,
  `music/`.

GUI `/Applications/vAmiga.app` ma DMA debugger (Copper zlute, Blitter
hnede, bitplany azurove) a ladici okna - hodi se pro prvni orientaci v
pameti. FS-UAE na tomto Macu ma znama uskali (save state prebiji ADF,
bezi o 20 % rychleji, `screencapture` posouva barvy) - pro mereni
pouzivat vAmigu.

### 2.3 Co musi dodat zadavatel

- ADF hry (Turrican I 1990 nebo Turrican II 1991, Factor 5 / Rainbow
  Arts; upresnit, ktery). **Herni data se do repozitare nedavaji**, jen
  cesta v `.gitignore`-ovanem konfigu; hrac prinese vlastni kopii.
- Souhlas s vytvorenim noveho repozitare, napr.
  `/Users/mik/claude46/Amiga/Turrican-projekt/` (+ GitHub podle uvazeni).

## 3. Postup po milnicich

Kazdy milnik konci commitem, zaznamem v docs a kontrolou kontraktu.
Neprechazet dal, dokud predchozi milnik neni zmereny.

### M0 - rozjezd (1 den)

1. Zalozit repozitar, `README.md` s cilem a architekturou, `docs/`,
   `tools/`, `build/` (ignorovany), `work/` (disassembly, ignorovane
   herni binarky).
2. Nabootovat ADF ve VAHeadless, snimky t = 5, 15, 30, 60 s. Zjistit,
   cim se projde intro/menu (mys, fire, klavesa) a **zapsat pevnou
   vstupni sekvenci** jako u SWIV (`tools/baseline.sh` je vzor).
3. Zjistit, zda hra ma cracktro nebo ochranu, ktera se projevi v
   headless rezimu.

### M1 - zavadec, packer, extrakce dat (3 az 5 dnu)

1. `scan.py`-postup: najit zabalene bloky na disku, projit zavadeci
   retezec (`unboot.py` je vzor), prepsat dekruncher do Pythonu, overit
   kontrolnimi soucty a tim, ze extrahovany hlavni program se da
   disassemblovat a obsahuje cekane rutiny.
2. Vystup: `tools/extract.py` (ADF → `build/files/`), `docs/LOADER.md`.
3. Disassembly hlavniho programu do `work/prog.txt`, `tools/xref.py`
   nad nim (graf volani).

### M2 - formaty dat: grafika a mapa (5 az 10 dnu)

1. Sprity a dlazdice: format, planarita, palety, animacni tabulky.
   Vystup `tools/gfx.py`, archy do `build/sheets/`, `docs/GRAPHICS.md`.
2. Mapa urovne: dlazdice, bloky, kolizni atributy, rozmery, kde lezi
   objekty. Vystup `tools/map.py` (cela uroven do PNG), `docs/MAPS.md`.
3. Kontrola proti snimkum z emulatoru: vyrez mapy vykresleny nasim
   nastrojem musi pixelove sedet na snimek originalu ve stejnem radku a
   sloupci (vzor `tools/compare.py`, ratchet shody v procentech).

### M3 - stav hry v RAM (5 az 10 dnu)

Tohle je jadro cele prace. Bez nej neni renderer.

1. Najit promenne kamery (x, y scrollu), zaznam hrace (poloha, stav,
   animace, smer), tabulku objektu (zaznam = ?, poloha, typ/grafika,
   snimek animace, priznaky viditelnosti), tabulku strel, HUD (zivoty,
   energie, skore, cas).
2. Metoda: disassembly hlavni smycky a VBL preruseni + **rozdilove
   snimky pameti**. VAHeadless neumi dump RAM primo; overit prikazy
   RetroShellu (`help`, sekce debug/mem); kdyz chybi, doplnit do
   headless buildu prikaz „dump RAM po N VBL do souboru" (zdroje a
   preklad podle `tools-bin/README.md`). Dva dumpy o jeden VBL pozdeji
   a rozdil ukaze, co se hybe.
3. Pro kazdou promennou: adresa, sirka, jednotka (pixely, 8.8, 16.16),
   kdy v ramci VBL se meni (pred/po vykresleni). Vystup `docs/STATE.md`
   ve stejne hloubce jako `docs/ENGINE.md` u SWIV.
4. Kontrakt: skript, ktery z dumpu RAM vykresli scenu nasim rendererem
   a porovna se snimkem emulatoru ze stejneho VBL. Cil shoda >= 98 %
   mimo HUD (SWIV ma 99 %).

### M4 - emulator v prohlizeci (5 az 10 dnu)

1. Zvolit jadro: prvni volba **vAmiga → WebAssembly** (projekt vAmigaWeb
   existuje; jinak vlastni preklad `Core/` pres Emscripten podle vzoru
   VAHeadless). Kriteria: bezi 50 Hz PAL v Web Workeru s realnym
   casovanim, umi vstup z klavesnice/gamepadu, **poskytuje cteni RAM po
   kazdem VBL** (callback nebo sdilena pamet), zvuk pres WebAudio,
   obraz emulatoru lze vypnout nebo ignorovat, uklada/nacita stav.
2. Kickstart a ADF dodava uzivatel pres file picker (jako `#fpick` v
   SWIV), nic se nesiri.
3. Kontrakt: emulator v prohlizeci dava stejny snimek jako VAHeadless
   ve stejnem emulovanem case (determinismus prenesen).

### M5 - renderer a plynulost (5 az 10 dnu)

1. Po kazdem VBL precist stav (M3) do JS struktury; kreslit v
   `requestAnimationFrame` s interpolaci mezi poslednimi dvema stavy,
   vystup v celociselnem nasobku 320x256 (2x, 3x) s mezipolohami.
2. Vyresit, co puvodni hra kresli mimo bitplany: HW sprity (hrac?),
   copperove barevne pruhy, paralaxa (pokud je) - cist z emulovanych
   registru nebo copper listu, ne odhadovat.
3. Rezimy: „original" (50 Hz, 1:1, zadna interpolace - kontrolni) a
   „vylepseno" (interpolace, skalovani). Prepinac jako u SWIV.
4. Kontrakt: rezim original pixelove sedi na emulator; rezim vylepseno
   se meri na plynulost (histogram delek snimku, zadne dvojite snimky
   pri 60/120 Hz).

### M6 - vetsi vyrez mapy (5 dnu + neurcito na patche)

1. Nejdriv jen teren: viewport 400x256 nebo 320x320 z dat mapy, HUD
   prekresleny mimo herni plochu. Zmerit, kde se objevuji nepratele
   (okraj puvodniho okna).
2. Najit v disassembly meze aktivace objektu a kamery (konstanty
   porovnavane s polohou kamery); navrhnout patch a overit ho v
   headless emulatoru (patch do RAM po nacteni, ne do ADF).
3. Zapsat, co patch meni v chovani (drivejsi probuzeni nepratel = jina
   obtiznost) - je to rozhodnuti zadavatele, ne technika.

## 4. Pravidla prace (shodna se SWIV)

- Kazde cislo s adresou (`0x....` v `work/prog.txt`) nebo s cislem snimku
  a casem z emulatoru. Neznamou rutinu zapsat do `docs/GAPS.md`, ne
  domyslet.
- Kontrakty (`tools/check.py`-vzor, porovnani snimku) bezi po kazde
  zmene a musi byt zelene; testy se neupravuji, aby prosly.
- Commit po kazdem milniku nebo overene davce, commit message cesky.
- Nic z herniho disku ani Kickstartu v repozitari.
- Kdyz se ukaze, ze vAmiga nejde rozumne prelozit do WASM nebo neposkytne
  RAM po VBL, **zastavit a napsat zadavateli** dve alternativy s odhadem:
  (a) jiny emulator s WASM, (b) minimalni vlastni 68000 + OCS emulace jen
  pro tuto hru. Neresit to potichu tydny.

## 5. Zname zdroje rizika

- **Prava**: hra i Kickstart patri jinym; projekt je engine/prehravac
  nad daty, ktera prinese hrac (model ScummVM).
- **Vykon WASM**: cela A500 v prohlizeci na 50 Hz je zvladnutelna
  (vAmigaWeb to dela), ale renderer musi bezet mimo hlavni vlakno
  emulatoru.
- **Copperove efekty**: Turrican pouziva barevne prechody a (v II) i
  paralaxu; renderer je musi brat z emulovaneho stavu, jinak obraz
  nebude „presny".
- **Ochrana/zavadec**: muze zpozdit M1; SWIV mel vlastni packer a slo
  to.
- **Kamera a aktivace pri sirokem oknu** (M6): jedina cast, kde se
  zasahuje do hry; drzet jako volitelny rezim.

## 6. Odevzdani

Po kazdem milniku: commit, docs, snimky/kontrakty v `build/` a kratka
zprava zadavateli: co je zmerene, co je otevrene, co se rozhodlo. Revize
probehne stejne jako u SWIV (kazde cislo proti disassembly, prehrani
kontraktu).
