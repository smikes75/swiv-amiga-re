# Zadani: vykon a kontrakty vylepseneho rezimu (pro Opuse)

Navazuje na revizi z 2026-09-17 (`docs/CHIPSET.md`, sekce "Revize
renderu po Opusovi"). Tohle NENI prepis chovani z disassembly, takze
metoda ze `ZADANI-GRASS.md` (sekce 2 az 7) tu neplati; plati pravidla
v sekci 2. Vysledek projde stejnou revizi: kazde cislo se premeri.

## 1. Cil a rozsah

Ctyri ukoly, kazdy samostatny commit, v tomto poradi:

| # | ukol | zmerene ted | cil |
|---|---|---|---|
| A | mekke stiny: predrozostrit a cachovat | 28,3 -> 192,3 ms pri 17 stinech (~9,6 ms na stin, `ctx.filter` na kazdy stin zvlast) | pod 40 ms v teze scene, obraz do 2 urovni od dnesniho |
| B | Scale2x na podpixelove poloze | 31,2 ms proti 5,7 ms u "bez" a "vyhlazeno" | pod 10 ms, tvrde hrany zustanou |
| C | `compare.py`: rohatka na `terrain`, checkpoint FINAL | rohatka je na `whole` (nese sum objektu a HUD), FINAL nema checkpoint (6 ze 7 zon) | rohatka na `terrain`, 7 ze 7 zon |
| D | scratch cesta zvetsenin: proc je draha | A/B nize; mechanismus neni izolovany | zmerit a vysvetlit, pripadne zrusit scratch |

Co do zadani NEPATRI: zmena vychoziho vzhledu (odstraneni predzvetseni
u "bez" meni 2,82 % bodu - to je hracovo rozhodnuti), nove efekty,
cokoli v simulaci (`g`, RNG, `netStateHash`).

## 2. Pravidla (z revize; kazde stalo cas)

1. **Merit, ne hadat.** Kazde tvrzeni v commitu i v CHIPSET.md nese
   cislo a jak vzniklo. Mereni = Playwright, headless Chromium, `frame(0)`
   s `g.frac = 0.37` (podpixelova poloha, 4 z 5 snimku pri 60 Hz) a
   `g.frac = 0` zvlast, prumer z 20 snimku po zahrivacim behu, KAZDA
   varianta v nove zalozce. Vzor: `scratchpad/sprperf2.py` z revize
   (v CHIPSET.md je opsany). Cisla jsou ze softwaroveho rasterizeru -
   informativni je pomer, ne absolutni hodnota, a pis to tak.
2. **Stav renderu zije na `state`, nikdy na `g`.** `g` je simulace,
   jde do `netStateHash` a lockstepu. Kazda nova volba `state.*` MUSI
   mit vychozi hodnotu v `const state = {...}` - `undefined` uz jednou
   zapnul Scale2x vsude (`!== "bez"`).
3. **Zadna cache bez meze a bez mereni pameti.** Maskovane sprity maji
   kazdy snimek nove platno; klic platna nese celou paletu radku, takze
   fade plodi varianty. Dve pasti z revize: 425 ms na snimek (platno na
   kazdy sprite) a 256 MB (zvetseniny bez meze). Kazdou cache zmer
   skriptem typu `upmem.py` (900 tiku pres fade na startu urovne,
   zvetseni 6, dva snimky na tik) a napis maximum v MB.
4. **`ctx.filter` je drahy** - volej ho na predrozostreny obraz, ne
   pri kazdem kresleni.
5. **Vizualni kontrola: `g.player.inv = 0`.** `inv = 99999` ma bit 3
   a spousti bily zablesk (`BOB_FILL_INDEX9`); vrtulnik je pak bila
   silueta. Zivoty drz pres `g.lives = 99999`.
6. **`S` cti az po prvnim `frame()`** - zvetseni se na platno propise
   az v nem. Kontrakt, ktery cetl `cv.width` driv, meril kus pozadi.
7. **Mer na indexech, kdyz jde o indexy.** Hotove pixely maji v sobe
   pruhledny HUD a prepocet palety po radcich (falesny poplach 5 211
   bodu u vlnek).
8. **Nic ze scratchpadu do repozitare.** Skripty pisi PNG do
   scratchpadu absolutni cestou; `git add -A` v korenu uz jednou
   pribalilo 1,9 MB pokusnych obrazku. Pred commitem `git status`.
9. **Kontrakty zelene pred kazdym commitem:** `check`, `uitest`,
   `smoothtest`, `compare` (klasicka cesta zustava BITOVE stejna),
   `lockstep`, `nettest`, `spawncheck`, `margins`. Kdyz kontrakt zmenis,
   napis do nej PROC (adresa nebo mereni), ne jen nove cislo.
10. **Dokumentace:** kazdy ukol dostane v `docs/CHIPSET.md` sekci s
    tabulkou pred/po a s tim, co se nepovedlo. Cestina bez diakritiky
    v kodu a docs.

## 3. Ukoly

### A. Mekke stiny (`renderSmoothField`, `state.softShadows`)

Dnes: rozostreni `min(6, z/6)` px se aplikuje `ctx.filter = blur(...)`
na kazdy stin pri kazdem kresleni. Zmereno v RIVERu, 17 stinu a 18
letcu: 28,3 ms bez / 192,3 ms s (CHIPSET "Nejdrazsi vec v obraze jsou
mekke stiny").

Navrh: rozostreni zavisi jen na `z` (par hodnot) a na snimku stinu.
Predrozostrit jednou do vlastniho platna (klic snimek + zaokrouhlene
rozostreni na 0,5 px) a kreslit hotove; cache s mezi a s merenim
pameti (pravidlo 3). Pozor na okraj: rozostrene platno musi byt o
`3 * blur` vetsi na kazde strane, jinak se stin orizne.

Kontrakt do `tools/uitest.py`: tataz scena s cache a bez ni (docasne
vypnuti pres `state.*`), rozdil hotovych pixelu max 2 urovne na kanal
(bilinearni interpolace mezi kroky 0,5 px) a pocet rozdilnych bodu
vypsany; plus cas na snimek do CHIPSET.

### B. Scale2x na podpixelove poloze

Dnes: pri zvetseni S = 5 a Scale2x (k = 2) je zbytek 2,5, `upscaledSprite`
predzvetsi jen 2x a zbyvajicich 1,25x dotahuje bilinearka z velkeho
zdroje - to je tech 31 ms (bez: 5,7; vyhlazeno: 5,7). Pri S = 4 nebo 6
je zbytek cely a problem zmizi - zmer to nejdriv (S = 4, 5, 6, 8), aby
tabulka rekla, kde presne to boli.

Navrh: kdyz zbytek neni cely, kreslit z dvojnasobne mrizky primo
nejblizsim sousedem (`imageSmoothingEnabled = false`) na zlomkovou
polohu - rezim ma mit tvrde hrany, takze bilinearka tu nic nekupuje.
Zmer cas i pocet rozdilnych bodu proti dnesku (vyrez 44x44 kolem
vrtulnika jako v kontraktu hran) a rozhodni podle cisel.

Kontrakt: rozsirit kontrakt "hrany spritu" o cas: kazdy rezim na
`frac = 0.37` pod 2x cenou rezimu "bez" (pomer, ne absolutni ms).

### C. `compare.py`: rohatka na `terrain` a checkpoint FINAL

Dnes je rohatka na `whole`, ktere obsahuje objekty a HUD, takze
procento kolisa s tim, co se zrovna hybe, a cte se jako "vernost".
`terrain` (bez HUD a HELI) je ta cast, ktera ma byt bitove presna.

1. Rohatka na `terrain`; `whole` jen vypisovat. Prahy nastav tesne pod
   dnesni hodnoty `terrain` (v `compare.py` je tabulka).
2. FINAL: najdi radek s clenitym terenem (GAPS "Zarovnani zonoveho
   snimku potrebuje CLENITY teren", 2026-09-11 - postup i past jsou
   tam) a pridej checkpoint. Original z vAmiga harnessu
   (`tools/survey/origshot.py`, jedna snimek na beh).
3. Do hlavicky `compare.py` napis jednou vetou, co procento JE a co
   NENI.

### D. Scratch cesta zvetsenin

A/B z revize (frac 0,37, S = 5, uroven 3, ms na snimek):

| varianta | bez | Scale2x | vyhlazeno |
|---|---|---|---|
| pred revizi (WeakMap, promoce od 2. vyskytu) | 42,29 | 53,55 | 9,74 |
| jen tabulka palety (stara cache) | 43,25 | 50,36 | 7,47 |
| jen omezena LRU cache (paleta s `pow`) | 7,70 | 40,12 | 7,51 |
| obe (dnes) | 5,71 | 31,20 | 5,69 |

Tedy: LRU srazila "bez" ze 42 na 6-8 ms, ale NENI jasne proc - obe
verze vraceji po promoci vlastni platno presne velikosti. Podezreni:
kresleni ze SDILENEHO scratche (velke platno, zdrojovy vyrez) je v
Skia drahe a ve stare verzi se z nej kreslilo casteji, nez se zdalo.
Zmer: pocet kresleni ze scratche vs. z cache na snimek v obou verzich
(citac na `state`), a cenu jednoho kresleni z obou zdroju. Podle
vysledku bud scratch zrusit (kreslit male platno primo, kdyz neni
promoce), nebo napsat, proc zustava.

## 4. Vystup

- Ctyri commity (A, B, C, D) s cisly v textu, kazdy po zelenych
  kontraktech; `git push` az po vsech.
- `docs/CHIPSET.md`: sekce "Vykon vylepseneho rezimu (Opus, datum)" s
  tabulkami pred/po a s tim, co se nepovedlo nebo zustalo otevrene.
- `docs/GAPS.md`: jedna veta k C (co procento znamena).
- Na konci zprava pro Fable: tabulka vsech merenych cisel a seznam
  toho, co jsi NEUDELAL a proc - to je stejne dulezite jako to, co ano.
