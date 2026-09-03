# Zadani: prepis chovani zony GRASS (uroven 3)

Zadani pro samostatnou praci (jiny model / jina session). Vysledek projde
revizi proti `AMPROG.OBJ`; vsechno, co nejde dolozit adresou v
`work/prog.txt`, se do prepisu nedava (fail-closed).

## 1. Cil a rozsah

V `game.html` prepsat vsech 11 druhu chovani, ktere GRASS.PAM pouziva a
ktere jeste nejsou v `IMPLEMENTED_BEHAVIORS` (97 objektu ze 132; 35 uz
bezi z TOWN/DESERT). Poradi podle cetnosti a prvniho vyskytu:

| ks | grafika (PAM) | gfx slovo | korutina | prvni radek `ry` | poznamka |
|---:|---|---|---|---:|---|
| 42 | VTOL.LIN#0 | 0x0023 | 0x8344 | 1862 | nejcastejsi objekt zony |
| 20 | XEVIOUS.LIN#5 | 0x0a2e | 0x791a | 113 | hned na zacatku; dekodovano castecne, viz 5.3 |
| 16 | XEVIOUS.LIN#9 | 0x122e | 0x7ed8 | 291 | |
| 5 | TRILO.LIN#4 | 0x0822 | 0x826a | 1190 | |
| 4 | _PLAT.LIN#10 | 0x1442 | 0xa3b8 | 1863 | |
| 3 | XEVIOUS.LIN#0 | 0x002e | 0xadf2 | 398 | |
| 3 | _PLAT.LIN#9 | 0x1242 | 0xa3b2 | 1928 | zrejme sdili kod s #10 (0xa3b2/0xa3b8) |
| 1 | JEEPHELI.LIN#23 | 0x2e00 | 0xac6a | 180 | marker/pad, srov. SWAP pad `0xacb6` |
| 1 | JEEPHELI.LIN#43 | 0x5600 | 0xad30 | 1063 | srov. `0xad02/0xad08` (SWAP#0/#1) |
| 1 | _CORN.LIN#7 | 0x0e41 | 0x820c | 1284 | dekodovano castecne, viz 5.3 |
| 1 | DADA.LIN#0 | 0x0059 | 0x7a2c | 1763 | |

Seznam se generuje z `build/spawns.json` + `build/dispatch.json`
(skript v sekci 6.1). Zony RIVER (11 druhu), ICE (10) a SCIFI (11) prijdou
na radu stejnym postupem; FINAL ma jediny objekt (zaverecny boss).

## 2. Pravidla

1. **Mereno, ne hadano.** Kazda konstanta v kodu i v dokumentaci nese
   adresu v `work/prog.txt` (`0x....`). Kdyz neco nejde dolozit, nechte
   objekt jako `unimplemented` (kresli se, nestrili) a zapiste to do
   `docs/GAPS.md`.
2. **Nic v cestach TOWN/DESERT nemenit** (spolecne helpery ano, ale jen
   rozsirenim, ne zmenou chovani). Kontrakty `python3 tools/compare.py`
   (4 checkpointy TOWN) a `python3 tools/uitest.py` musi byt zelene po
   kazde davce; **testy se neupravuji, aby prosly**.
3. Pracovni jazyk cestina bez diakritiky v kodu a docs (jako dosud).
4. Commit po kazde overene davce (2-4 chovani), zprava ve stylu
   `GRASS: VTOL (...), XEVIOUS#5 (...)`, push na origin.
5. Nespoustet vAmigu a nemenit baseline; overeni je simulacni (sekce 6).

## 3. Jak cist AMPROG.OBJ

### 3.1 Vypis disassembly

```python
python3 - <<'EOF'
import re
lo, hi = 0x8344, 0x8420          # rozsah korutiny
for line in open('work/prog.txt'):
    m = re.match(r'\s*([0-9a-f]+):', line)
    if m and lo <= int(m.group(1), 16) < hi: print(line.rstrip())
EOF
```

Korutina zacina zpravidla `a2c6` a konci `braw 0xa34c` (konec tasku).
Konec rozsahu poznate podle dalsi `movew #gfx,%d0 ... bsrw 0xa2c6` nebo
podle tabulky `build/coroutines.json`. **Pozor: disassembler sleje datova
slova do falesnych instrukci** (`orib #6,%d6`, `subb %d0,%d4` apod.).
Vsechno za `bsrw 0x6c88`/`0x6c82`/`0x6d76`/`0x5eda` jsou inline slova -
ctete je jako hex po dvou bajtech, ne jako instrukce (viz past 5.1).

### 3.2 Kostra objektu (a5 = zaznam)

`a2c6(d0 gfx, d1 trida, d2 aktivacni margin, d3 HP, d4 skore, d5 cost)`:
`+368 = gfx`, `+504 = trida`, ceka `0x9ac8(d2)` dokud `sy >= d2`, uzel
`0x6dce(d1)` + rozmery z hlavicky snimku `0x6d7c(d0)`, `+360 = HP`; pri
HP != 0 vychozi handlery `0xa362` (zasah boltem = HP-1, kontakt = HP-1).
Gfx slovo: `(index << 9) | id souboru`; jmena souboru podle id:

```python
python3 -c "
d=open('build/files/001_AMPROG.OBJ','rb').read()[4:0x537].decode('latin1').split('\0'); n=[x for x in d if x]
print([(hex(i), x) for i, x in enumerate(n) if x in ('vtol.lin','xevious.lin','trilo.lin','_plat.lin','dada.lin','_corn.lin')])"
```

Pole zaznamu (word/long na `%a5@(N)`):

| ofset | vyznam |
|---|---|
| +276 | typ z PAM (slovo); korutiny jej casto pouzivaji jako citac |
| +278/+280/+282 | volne scratch citace (krok otocky, pocet, pamet znamenka) |
| +308 | ukazatel na rodice (0 = sirotek) ; +312 = ukazatel na dite |
| +320/+324/+328 | x, y, z jako 16.16 long (mapove souradnice; bit4 = obrazovka) |
| +332/+336/+340 | vx, vy, vz 16.16 ; +344/+348/+352 ax, ay, az |
| +356 | rychlost pro `0x65f2` (256 = 1 px/t) ; +358 uhel (0 vpravo, 64 dolu, 128 vlevo, 192 nahoru, 256 = kruh) |
| +360 HP, +362 skore, +364 cull margin (vychozi -64, `0x6480`), +370 cost, +374 dekal (`0x898c`, 5 = EXPL1#0), +376 efekt smrti (vychozi `0x894a` oblacek, `0x8876` BIGEXPL) |
| +367 bity | 0 bez stinu, 1 flash, 2 blika s rodicem, 3 vazane dite (poloha rodice + (vx,vy,vz) jako ofset), 4 prisroubovano k obrazovce |
| +397 bity | 0 = pozemni/priorita kresleni (zatim jen prenaset), 6 = dekal |
| +504 | trida kolizi: bit1 smrtici kontakt (34/38/6), bit2 zasazitelny (36/38), bit15 bez sweepu; 0 = bez kolizi |
| +510/+514/+518/+522/+526/+530 | handlery pro bity 0/3/1/4/2/5 (`0x653e` bit0, `0x6566` bit3, `0x6564` bit3+4, `0x654a` bit1+2) |
| +534 smart handler, +538 cull handler (-1 = bez cullu), +542 sirotci handler (`0x6144` -> `0x6db4` = zemri tise, `0x6178/0x617a` -> -1) |

Housekeeping `0x62fe` (uvnitr kazdeho `0x62d2`): rychlost += zrychleni,
poloha += rychlost (x pocet ubehlych VBL), zaporne z -> 0 a vz = az = 0.
`movew #N, +336` zapisuje HORNI slovo = N px/t; `movel #X, +332` = X/65536.
`tstw +328` / `cmpiw #32, +328` testuji jen horni (cele) slovo.

### 3.3 Cekani a smycky

| volani | vyznam | v prepisu |
|---|---|---|
| `0x62d2` | yield 1 VBL s housekeepingem, Z = zije | jeden krok `step` |
| `0x629c(N)` | wait N tiku s housekeepingem | citac `s.t` |
| `0x62b8(N)` | totez (smycka pres 0x62d2) | citac |
| `0x62cc` | cekej do zabiti/cullu (pohyb bezi) | konecny stav |
| `0x9afa(N)` | cekej, dokud `sy >= N` | `if (s.sy >= N)` |
| `0x9ae8(N)` | totez s vynulovanou tridou +508 (bez kolizi) | HP 0 do te doby |
| `0x9ac8(N)` | raw varianta (a2c6 aktivace) | `margin` v born retezci |
| `0x5f22(N)`/`0x5f0a` | raw wait bez pohybu a bez cullu | `noCull` + citac bez pohybu |
| `0x5eda(6)`/`0x5efc(6)` | zamek zdroje 6 (nemodelovat) | - |

### 3.4 Pomocne rutiny

| adresa | vyznam | helper v game.html |
|---|---|---|
| `0x883c` | RNG 32 bit (volat presne tam, kde original) | `random32(g)` |
| `0x8822` | guard rozpoctu 160 (jen kdyz ho korutina vola) | `reserveCost(g, o)` (false = odmitnuto) |
| `0x65be(d0 x, d1 y, d2 max)` | uhel k cili (d2 = 0 bez omezeni) | `angTo(fx, fy, tx, ty)`, `turnToward` |
| `0x65f2` | rychlost z uhlu +358 a +356 | `angVel(ang, spd)` |
| `0x95ca` / `0x95c2(dx, dy)` | rovna kanonova strela v uhlu +358 | `fireCannonStraight(g, x, sy, ang)` |
| `0x95d2` | mireny kanon na hrace + PLOP | `fireCannonAimed(g, x, sy, vx, vy)` |
| `0x8530(dx, dy, uhel)` | homing strela + PLOP | `fireHoming(g, x, sy, ang, vx, vy)` |
| `0x85f0` | PLOP hlavne | `spawnPlop` |
| `0x6d7c(gfx)`, `0x6d76 .word gfx` | zmena snimku i hitboxu | `s.fr`, `s.nodeKey`, `s.nodeExt = null` |
| `0xa290(base)` / `0xa27c(base)` | smerovy snimek dir16 / dir8 z +358 | `dir16(ang)` |
| `0xa2a2(dx, dy, pocet, dtyp)` | formace kopii pres 0x6178 (pred a2c6!) | `spawnFormationCopies` ve `startMapObjectTask` |
| `0x6144(rutina)` | dite se stejnou polohou, +542 = tise zemri | hazard s `parent` |
| `0x6178/0x617a(rutina)` | kopie zaznamu, nezavisla | hazard / novy spawn zaznam |
| `0x6d96` | vynuluj rychlosti, zrychleni i +356 | `vx = vy = ... = 0` |
| `0x6c88` (vlastni) / `0x6c82` (sekundarni +422) | animace; skripty v `docs/ANIMS.md` podle adresy payloadu | `s.fr` + citac / `secondaryFile` |
| `0x93e2` | standardni rotor JEEPHELI#5..#8 (blika) | `rotorTick` jako MILL/TILT |
| `0x72ee` / `0x72a6` | poloha hrace (0x72a6: mrtvy = 96 + \|bajt tiku\|) | `g.player`, `playerAimX72a6` |
| `0x8876` | velky vybuch (EXPL2#0..#6 po 6 + oblacky po 15) | `queueTownExplosionTask(..., "big")` / `s.bigDeath` |
| `0x894a` | oblacek EXPL1#7..#13 | `queueTownExplosionTask` (vychozi) |
| `0x898c` | dekal do mapy | `addDecal(g, file, frame, x, y)` |
| `0xa36a` / `0xa35a` | smrt s kreditem / flash + zvuk zasahu | `killSpawnCredited`, `damageSpawn` |
| `0x8852` | bily zablesk = SMART pulz | `startWhiteFlash(g)` |
| `0x4c3c`, `0x541e`, `0x5436`, `0x4e2e`, `0x55b0` | zvuky (zatim jen zapsat do docs) | - |

Animator `0x6c88` opkody (slovo s bitem 15): `0xb0NN` perioda, `0x8000`
drz posledni snimek, `0x8800` zabij objekt, `0x9800` zacatek smycky,
`0x9000` skoc na zacatek smycky, `0xa000/0xa800` nastav/pricti +14
(nevidano). Kladne slovo = snimek (`gfx` format). Prvni snimek se
publikuje hned pri pripojeni, dalsi po periode.

## 4. Kam v game.html psat (kontrolni seznam)

Vzory: `egg`/`eggnest` (faze, deti jako hazardy, strela), `skyeye`
(formace, obrazovka, otocky, smerove snimky, `noCull`), `diagun`+`laser`
(zmena snimku i hitboxu, hazard s HP), `mama`+`mamabar`+`mamadrone`
(vazane dite, roj, sirotci), `factory` (0x9ae8, deti-spawny, vlastni
smrt), `jet0`/`jetfly` (novy spawn zaznam z korutiny), `truck`/`truckdrop`.

1. `IMPLEMENTED_BEHAVIORS`: `[0xGFX, { coroutine: 0xADDR, id: "..." }]`
   (musi sedet s `build/dispatch.json`, jinak zustane `unimplemented`).
2. `NODE_GRAPHIC`: klic = `beh` (nebo `nodeKey`/`kind` hazardu) -> `[soubor,
   snimek z a2c6 d0]`; hitbox se bere z hlavicky snimku. Pri zmene snimku
   pres `0x6d7c` menit `s.nodeKey` a nulovat `s.nodeExt`.
3. Aktivacni margin: retezec `let margin = -32; if (...)` v born bloku
   (hodnota a2c6 d2).
4. Kod PRED a2c6 (formace, deti `0x6144`, RNG) patri do
   `startMapObjectTask` (ctecka mapy 256 px nad oknem), ne do born.
5. Born blok: `s.cost/hp/scoreValue`, `accountCost` nebo `reserveCost`
   (jen kdyz korutina vola `0x8822`; odmitnuti = `releaseSpawnTask`),
   pocatecni faze `s.st`, `s.fr`, `s.z`, `s.scrollLocked` (bit4),
   `s.bigDeath` (+376 = 0x8876), `s.noCull` (+538 = -1).
6. Step blok (`else if (s.beh === "...")`): pohyb = housekeeping (nejdriv
   rychlost += zrychleni, pak poloha), potom logika. `s.sy` je uz
   spocitane. Ukoncene stavy pouze pohyb.
7. Kompozitor (`bob(...)`): objekty se stinem/z nebo rotorem potrebuji
   vlastni vetev (vzor `fish/goose7/skyeye`, `onerig`); jinak generic.
8. Smrtici kontakt (trida bit 1): pridat do obou seznamu (sweep
   `contactMill.add` a `dispatchTownContactEvent`); z oblacku smrti do
   `deathBoomZ`; dekal +374 = 5 do seznamu v `killSpawnCredited`.
9. Hazardy (deti): tovarnicka `spawnXxx(g, s)` + vetev v
   `advanceTownHazardField` (pole: `z`, `castShadow`, `lethal`, `noCull`,
   `armMargin`, `flashWithParent`, `rotor`, `seq/per`, `life`, `hp`,
   `scoreValue`, `cost`, `parent`); kontakt v `dispatchTownContactEvent`
   (hazard: `damageHazard` / `releaseHazard` / nic).
10. Novy spawn zaznam z korutiny (jako `spawnJetFly`/`spawnFactoryTank`):
    nutne `taskStarted: true` a `assignBobOrdinal`, jinak se nikdy nezrodi.
11. Strely: druh v `g.shots` (vzor `eggshot`: pohyb v hlavni smycce strel,
    kompozitor i legacy renderer, `NODE_GRAPHIC`).
12. Kontrola syntaxe po kazde uprave:

```bash
node -e "const fs=require('fs');const s=fs.readFileSync('game.html','utf8');
const re=/<script(?:[^>]*)>([\s\S]*?)<\/script>/g;let m;
while((m=re.exec(s))){if(!m[1].trim())continue;try{new Function(m[1]);console.log('ok')}catch(e){console.log('ERR',e.message)}}"
```

## 5. Pasti (skutecne chyby z prepisu DESERTu)

### 5.1 Cteni disassembly
- V anim skriptu `0x888c` se ztratilo slovo `0x0006` (EXPL2#0), protoze
  disassembler ukazal `orib #6,%d6`. Vzdy prepocitat bajty rucne a
  porovnat s `docs/ANIMS.md`.
- `movew #N, +336` na diteti `0x6144` neni rychlost, ale ofset k rodici
  (bit 3). `+367 |= 12/13` = vazane dite.
- `cmpiw #320; bhis` je porovnani BEZ znamenka (zaporne x = velke).
- `eorw` + `bpl/bmi` = test shody znamenek 16bitovych slov; v JS pouzit
  `signedWord` a `<< 16 >> 16`.
- `notw +276` prepina znamenko citace (PYRAMID: prvni strela vlevo).

### 5.2 Model prepisu
- Hazardy se krokuji PRED spawny; vazane dite proto polohuje rodic ve
  svem kroku (viz `mama`).
- Kopie formace vznikaji pri startu tasku (256 px nad oknem), kazda ma
  vlastni aktivaci; deti pres `0x6144` se aktivuji na VLASTNIM radku
  (`armMargin`).
- RNG se vola presne tam a tolikrat, kde original vola `0x883c`
  (i kdyz vysledek pri D = 0 nic nedela, napr. SKYEYEB).
- `0x8822` guard jen tam, kde je volany; jinak `accountCost` (muze
  prelezt 160).
- Objekty s `+538 = -1` potrebuji `noCull` a jeho zruseni ve spravne fazi.

### 5.3 Uz dekodovane kusy GRASS (overit, pak pouzit)
- `0x791a` (XEVIOUS#5): `a2c6(XEVIOUS#3 = 0x062e, 34, -16, HP 0, 0, cost
  13)`, `+367 |= 1`, z 32, handler bit 0 `0x7968` (= zvuk `0x55b0`
  podle x), `vy = 0.5` (long 0x8000), anim `0x794c` perioda 7 loop
  XEVIOUS#3..#8, `0x62cc`. Tedy neskodny driftujici objekt, ktery pri
  zasahu jen pipne (HP 0 = neznici se).
- `0x820c` (_CORN#7): `+364 = -90`, `a2c6(_CORN#7 = 0x0e41, 36, -80, HP 0,
  0, cost 25)`, z 0, `0x65a4` (?), wait `sy >= 80`, trida `+504 = 34`,
  `vz = 0.25` (0x4000), zvuk `0x54ac`, stoupani do z 32 ... (zbytek od
  `0x824e` dodekodovat).
- `0x77c6` (v dumpu SKYEYEB, gfx souboru 8 = EDGE.LIN) a `0x786e`
  (BUNNY.LIN, `sf fp@(3616)`) nejsou v GRASS, ale mohou byt v RIVER/ICE.

## 6. Overeni

### 6.1 Seznam zbyvajicich objektu zony

```python
python3 - <<'EOF'
import json, collections, re
sp = json.load(open('build/spawns.json'))['GRASS']; dp = json.load(open('build/dispatch.json'))
disp = {(d['file'], d['frame']): d for d in dp}
impl = set(int(m, 16) for m in re.findall(r'\[0x([0-9A-Fa-f]{4}), \{ coroutine', open('game.html').read()))
cnt = collections.Counter(); first = {}
for o in sp:
    d = disp.get((o['file'], o['frame'])); g = d['gfx'] if d else None
    if g in impl: continue
    k = (o['file'], o['frame'], d['coroutine'] if d else 'none', g); cnt[k] += 1; first[k] = min(first.get(k, 1e9), o['ry'])
for k, n in sorted(cnt.items(), key=lambda kv: -kv[1]): print(n, k, 'ry', first[k])
EOF
```

Snimky souboru: `build/sheets/<nnn>_<jmeno>.png`; rozmery a pocet snimku:

```python
python3 -c "
import sys, glob; sys.path.insert(0,'tools'); from gfx import lin_frames
for fn in glob.glob('build/files/*_VTOL.LIN'):
    fr = lin_frames(open(fn,'rb').read()); print(fn, [(i,f['w'],f['h']) for i,f in enumerate(fr)])"
```

### 6.2 Simulacni sonda

```bash
python3 tools/survey/behprobe.py 3 '{"vtol": [1, 60, 200, 400], "kill": {"vtol": 300}}' build/survey/grass 24000
```

Zona 3 = GRASS. Tik zrozeni ~ 4 x (radek mapy) od startu zony; v jedne
sonde lze dat vice chovani. Vystup: JSON radky (polohy, faze, hazardy,
strely, rozpocet) a PNG. Snimky slozte do montaze a prohlednete (zoom
3x na objekt), porovnejte se sheetem a s ocekavanim z disassembly
(poloha, faze, stin = z, strely). Pri `PAGEERROR` v logu opravit chybu.

```python
python3 - <<'EOF'
from PIL import Image, ImageDraw; import glob, os
names = sorted(glob.glob('build/survey/grass/*.png'))
ims = [Image.open(n).convert('RGB') for n in names]; w, h = ims[0].size; cols = 4
out = Image.new('RGB', (cols*w, ((len(ims)+cols-1)//cols)*(h+14)), 'black'); d = ImageDraw.Draw(out)
for i, (n, im) in enumerate(zip(names, ims)):
    x, y = (i % cols)*w, (i // cols)*(h+14); out.paste(im, (x, y+14)); d.text((x+2, y+1), os.path.basename(n), fill='white')
out.save('build/survey/grass/montage.png')
EOF
```

### 6.3 Kontrakty (po kazde davce, oba musi projit)

```bash
python3 tools/compare.py    # konci "compare exit"/OK a 4 checkpointy nad prahem
python3 tools/uitest.py     # konci "UI OK"
```

## 7. Dokumentace

- `docs/BEHAVIORS.md`: nova sekce `## GRASS` a pod ni `### JMENO (0xgfx →
  0xkorutina)` ve stejnem formatu jako DESERT: odrazky s `a2c6(...)`,
  waity, rychlosti, RNG, deti, smrt; posledni odrazka „Simulace:" s tiky
  a polohami ze sondy; adresa u kazdeho cisla.
- `docs/GAPS.md` sekce 9: radek s postupem (co hotovo, co zbyva, co se
  nemodeluje - zvuky, zamky).
- Neznamou rutinu (napr. `0x65a4`) dekodujte, nebo ji zapiste do GAPS
  jako otevrenou.

## 8. Co odevzdat k revizi

1. Commity na `main` (game.html, docs; pripadne tools), kontrakty zelene.
2. Pro kazde chovani tabulka: adresa korutiny, parametry a2c6, seznam
   waitu/faci s adresami, handlery (+510/+514/+542/+376), deti, RNG
   volani, co je nejiste. Staci v BEHAVIORS.md.
3. Vystupy sond (`build/survey/grass/*.png`, `montage.png`) a log.
4. Seznam veci, ktere se vedome nemodeluji (zvuky, zamky, neznamé rutiny).

Revize porovna kazdy zapsany udaj s `work/prog.txt` a prehraje sondu.
