# Mezery mezi prepisem a originalem

Seznam toho, co v `game.html` chybi nebo nesedi. Kazda polozka nese
adresu, na ktere se to da v `AMPROG.OBJ` docist — stejne pravidlo jako
ve zbytku `docs/`: zadny odhad, jen misto v kodu.

Zdroj hlaseni: hrani prepisu proti originalu, prubezne aktualizovano
2026-09-01.

## 1. Zvuky — TOWN ENGINE, GOOSE HIT A TOKEN FIFO PREPSANY; CALL-SITES ZBYVAJI

`game.html` uz modeluje ctyri persistentni Paula hlasy a CIAB scheduler
`0x4a66..0x4bf2`: `priority*4` guard, strict `>`, stereo-pair preferenci
s fallbackem, persistentni `0x56e6` noise scratch i VHPOS perturbaci PRNG.
Browser nema hostitelske "prehraj tento wav" aproximace pro procedurarni
efekty; z presnych waveformu a period sklada player fire, default HIT,
opening, FLAME puff, HOMING a cannon.

`BIGEXPL.SND` ma zdrojove spravne Paula periody. Standardni `0x4c58` jej
spousti dvakrat a spotrebuje dva RNG longy i pri rejectu, player death child
`0x4c1c` zkusi ctyri fixed vrstvy. Custom dvouhlas smrti GOOSE `0x553a` je
take prepsany. Neletalni GOOSE hit `0x4e46` zaklada dva priority40 hlasy;
kazdy prijaty hlas se seeduje globalnim RNG az pri druhem CIAB resume a pak
64 stavu pokracuje lokalnim `0x56e6`. Reject nebo preempce pred seedem RNG
nespotrebuje. Event hooky a exkluze popisuje [SOUND](SOUND.md).

White flash uz pousti kanonicky 8,280B `SMART.SND` ctyrikrat pres
`0x885a -> 0x4cb2`, priority127 a periody 1040/1025/1010/996. Napojeny je i
jednorazovy activation tone bound MINE bubliny `0x98f2 -> 0x4ffe` a obecny
ctyrnotovy TOKEN pickup `0x97ce -> 0x5614`; jeho noty se zkouseji v odstupech
0/5/10/15 VBL a zachovavaji pan podle x konkretniho TOKENu. `0x5614` uz
nezahraje prvni notu inline: zalozi priority100 child a ten startuje ve
strictnim creation FIFO. Stejna fronta radi fresh TOKEN, SMART `0x885a` a
`0x894a` explosion childy; splatne dalsi noty se vraceji do FIFO mezi
existujici continuations. Typ4 proto nativne zkusi prvni TOKEN notu pred
ctyrmi SMART vrstvami.

Otevrene zustava:

- zbyvajici specialni/player-transition call-sites. Extra life potrebuje
  presunout threshold kontrolu z okamziteho `awardScore()` na dalsi player
  resume a napojit sestinotovy efekt `0x5600` (424/336/266/212/168/133,
  priority120, rozestup 5 VBL);
- efekty specificke pro pozdejsi levely.

Gameplay hudba v TOWN neni mezera: original drzi tracker modul na titulku a
pri startu hry jej uvolni; samotny level je postaveny na zvukovych efektech.

## 2. TOWN boss (GOOSE) — STAV A DEATH SCHEDULER UZAVREN 2026-09-01

`GOOSE.LIN` snimek 0 → `0xc78a`. Prepsan je blikajici nalet, unfold
`0,0,1,2,3,4,5`, rotor, tri casti tela i ctvrty escort, jejich samostatny
ingress/overshoot/snap, cekani na vsechny ctyri deti, boj, kontakt, timeout,
smrt a kruhy TOKENu. Popis je v [BEHAVIORS](BEHAVIORS.md), presna regrese
v `tools/uitest.py`.
**TOWN tim ma 155/155 objektu na prepsanych korutinach.**

`0xc950` neni bodovy soucet, ale integritni/anti-tamper smycka. GOOSE tedy
spravne nedava body. Resident sweep pouziva dvoufazovy snapshot: kladne
uzly maji symetrickych ±8 a bit15 projektil ma vuci kladnemu cili na obou
osach inkluzivne `−8..+8`; eventy se pred callbacky koaleskuji po bitech.
Od 2026-08-31 se zasah, kontakt i smrt provedou az pri resume parent tasku
v N+1; regrese zvlaste hlida neletalni hit-spread i lethalni death synth,
BIGEXPL, unlink a prvni radialni pohyb novych TOKEN child tasku. Od
2026-09-01 uz `a36a` nespousti efekt inline: radi samostatny `0x894a`
priority100 child, jehoz BIGEXPL RNG prijde az po navratu z aktualniho
callbacku. Parent a escort tak maji vlastni explosion tasky.

Pri HP1 a pending masce `bit0|bit3` se callbacky neslouci do jedne smrti:
prvni smrt vytvori 2 TOKENy na ziveho hrace a vynuluje timer, druha proto
vytvori 3, tedy presne kruhy **2+3**, dve parent exploze a jednu pozdejsi
escort explozi. Unlink pouze nuluje parent pointery. Tri body childy na svem
orphan resume potichu uvolni cost10; escort pouzije posledni publikovanou
world pozici, zaradi `0x894a` se `z=34` a teprve potom spotrebuje 2/1/0 RNG
podle sve snake faze. Child, ktery v okamziku smrti jeste spi pred vlastnim
`a2c6`, dokonci delay, spotrebuje startovni RNG/cost, publikuje jeden
post-death creation field a zanikne az na pristim orphan resume.

Parent po unlinku zustava budgetovany pres presne 107 checksum yieldu a
cost100 uvolni v N+108 ve sve creation-order FIFO pozici. Timeout/cull sdili
stejny orphan a checksum tail, ale nema parent death efekt ani death synth.
Ingress stop, horizontalni steering, svisle hranice a palebny gate ted navic
porovnavaji signed high WORD 16.16 presne jako `0xc818`, `0xc887`, `0xc8b2`
a `0xc8ce`; desetinne hodnoty `.75` uz neposouvaji GOOSE o jeden field.

Drive otevrene otazky jsou tim uzavrene:

- ~~ctvrty potomek `0xcaac` = doprovod~~ — **uzavreno 2026-08-30**: je to
  pod zadokovany na `(0,+24)`, ktery se pak houpe na rameni 18 px
  (`0xcb14`–`0xcb76`); prepsano spolu s dokovanim `0xcb78`, odhozenim
  casti pri zasahu a blikanim/animaci tela, viz [BEHAVIORS](BEHAVIORS.md).
- ~~bodovy soucet po smrti~~ — **uzavreno 2026-08-30**: smycka `0xc950`
  neni skore, ale kontrolni soucet 27 329 slov programu pricteny k
  ukazateli na buffer mapy `fp@(3560)` (anti-tamper). Boss ma `d4 = 0`,
  tedy **0 bodu** je spravne; viz [TOWN-AUDIT](TOWN-AUDIT.md) 2.7.

## 3. TOKEN, MINE core a ochrany — STAVOVE CHOVANI UZAVRENO 2026-08-30

`TOKEN.LIN` → `0x96d8` ma 32tikovy radialni burst, start typu 3, presny
dvoutikovy icon/blank cyklus, hit cooldown, docasny typ 4 a cost5 bez
160-guardu. Typ 3 pouze pricte 500 do player `+108` a 500 bodu; sam zadny
oblouk nevytvari.

Viditelna bublina je vystreleny `MINE#9/#10` core `0x9860`. Pickup nastavi
`+106=-1`, zalozi samostatny cost5 child a 500 snimku jej strida pred/za
hracem pres `z=+2/-2`; po celou dobu prepisuje `+108` na 100. Duplicate
ochranu neprodlouzi a spusti white flash. Core je harmless pickup, ale ma
10 HP, 30 bodu a po prvnim sebrani drzi neviditelny wait10 do cleanupu.
Pickup callback v N+1 vstoupi do cooperative `wait10`; pri resume N+2 az
N+11 se pred waitem stale provede airborne bit4 scroll compensation, v N+10
je cost5 jeste drzen a cleanup probehne presne jednou v N+11.
Prvni start childa hraje jediny priority60 ton `0x4ffe`; duplicate ani
zastreleny core tento activation tone nemaji. Kazdy sebrany TOKEN vsech typu
naopak spousti vlastni priority120 ctyrnotovy efekt `0x5614`.

Pri tom se opravily dve veci jinde:

- `syms.json` vedl `0x653e` jako `anim_install`. Je to **instalator
  callbacku** (`+510`, bit 0 v `+508`); `0x6564` dela totez pro `+514`.
- starsi popis pocital stupen zbrane jako `weapon/5`. Tabulka `0x70c0`
  se indexuje `floor(+102/5)` a pri (re)spawnu dela
  `power=min(power,cap)`, kadenci vzdy prepise

White flash `0x8852/0x885a` je prepsany vcetne `256,-4` (64 snimku),
50tikoveho `fp@(169)` smart pulse a prekryvajicich se tasku: kazdy trigger
ma vlastni deadline a ktery-koli z nich muze globalni pulse shodit. Deadline
je priority100 task a shodi globalni flag presne ve sve creation-order pozici
mezi starsimi a mladsimi objekty. Pulse
bez bodu odstrani bezne objekty; score dostane jen cil, kteremu uz sweep v
tomtez VBL frontoval player event. Player, TOKEN, bound bubble, PLOP a cela
GOOSE skupina jsou imunni.

Drive otevrene detaily jsou tim take uzavrene:

- ~~zablesk u typu 4~~ — **uzavreno 2026-08-30**: je to smart bomba;
  `fp@(11168)` se za hry nezapisuje a z uvodni sekvence zustava **−4**
  (64 snimku doznivani). Smart bomba zabiji vse s aktivnim `+534`;
  prepsano v `game.html` (`smartBomb`), viz [BEHAVIORS](BEHAVIORS.md).
- ~~souhra `+98` s tabulkou `0x70c0`~~ — **uzavreno 2026-08-30**: tabulka
  se aplikuje jen pri (re)spawnu (`0x70c8`), bonusy plati do dalsiho
  spawnu. Prepsano (`applyWeaponTable`).

### Hlaseni z 2026-08-30 — kolize, stit, hrac (prepsano)

Hloubkovy audit je v [TOWN-AUDIT](TOWN-AUDIT.md). Prepsano tehoz dne:

- kolize vrtulniku jen s tridou bit 1 (letci, MILL, GOOSE, HOMING, strepy,
  granaty); pozemni objekty ho uz nezabiji
- jadro miny = stit (`0x98c4`, `0x92a0`, orb `0x98f2`) a smart bomba
- hrac `0x9410`: 3 px/t, snimky 0..4, clamp, ochrana 200 s blikanim 8/8,
  respawn 100 snimku, start 1 strela (MEGA TRAINER MISSILES=1 prepise
  `0x6fde`; zmereno baseline), stin `(+16,+32)`
- HOMING sestrelitelna (1 HP, 7 bodu); hit flash u nepratel

GOOSE (dokovani `0xcb78`, pod `0xcaac`, odhozeni casti, HP od zastaveni,
blikani a anim tela, rotor, smrt bez bodu) prepsan tehoz dne. P0 auditu
je tim cely v `game.html`; zbyle mechanicke parity jsou vypsane dale.

Lokalni stavy TOKEN/core, GOOSE i hrace a jejich N+1 callback hranice jsou
timto zdrojove popsane.

## 4. Scheduler kolizi a last-field cull — POZOROVATELNA HRANICE UZAVRENA 2026-08-31

Original radi bezne objektove tasky na prioritu 100, updater hracskych
HW projektilu na `0xfffe` a resident collision sweep `0x6ec2` na `0xffff`.
Sweep na konci VBL N pouze ORne event word; objekt jej zpracuje po svem
dalsim resume ve VBL N+1 (`0x62d2`/`0x64b6`) v poradi bitu
`0,3,4,1,2,5`.

Doplneno 2026-09-03 (baseline t19): kolizni boxy nejsou 8/8, ale bajty
8/9 hlavicky .LIN snimku z `a2c6` d0 (`0x6d7c`), a sweep cte pozice uzlu
z RESUME (`0x6430`), tedy o jeden pohyb starsi nez callback v N+1. Viz
`ENGINE.md` „Collision scheduling" a `TOWN-PARITY.md` „Druhe vytezky".
Otevrene: zda animator hrace startuje 4 VBL pred scrollem nebo scroll
4 VBL po nem (zmerena jen faze `index = (T+3)&7`; kandidat je tyz retez
`0x7090 -> 0x70c8 -> 0x7156` jako u respawnu), presna hodnota `vblBase`
(okno 172..199) a tik smrti v baseline (blikani po respawnu dava D = 212,
prepis umira v 211 — jeden tik v nejistote fitu prvni vlny). Vsechno chce
vzorkovani po snimcich, ktere RetroShell `wait` v sekundach nedava; navic
kazdy zachyt je samostatny beh s jitterem nekolika snimku.

Browser sweep ted stejne pouze ORuje pending masku do kazdeho zasazeneho
nodu a oznaci player bolty ke spotrebovani. Na zacatku N+1 existujici tasky
resumeuji v creation poradi: nejprve se smaze stary hit flag, pak se cte
**aktualni** SMART pulse a nakonec se dispatchuji bity 0 a 3. Player task
zpracuje svou lethal masku pred vstupem, pohybem a palbou; player projectile
updater je presunut na prioritu `0xfffe`, kde spotrebovane bolty odstrani
pred jejich dalsim pohybem. Child zalozeny callbackem neni ve vstupnim
snapshotu, ale jeste v N+1 projde svou prvni publikaci.

Loader kill meni generation word, neni to navrat z `0x64b6`. Browser proto
po SMART smrti ani po lethalnim bit0 callbacku nezahodi zbytek ulozene masky:
provede `SMART -> bit0 -> bit3` (a dalsi nativni sloty `4,1,2,5`) a zaznam/cost
uklidi fyzicky jen jednou. Regrese zahrnuje HOMING, bezny air cil, TOKEN,
BIRD, GOOSE, MINE a PROXMINE. SMART deadline task se stejne radi podle
creation ordinalu, takze starsi objekty jej jeste vidi a mladsi uz ne.

Regrese pokryva dva bolty/jeden cil, jeden bolt/dva cile, aktivni i burst
TOKEN, MINE core, player kontakt, SMART attribution, prefire MEDTANK,
jeden viditelny cannon field pri kontaktu s HELI, TOKEN pickup a oba GOOSE
hit/death prechody. Zvlastni fixture hlida i to, ze BIRD cannon zalozeny
callbackem dostane jen jeden prvni pohyb, a ze GOOSE timeout propadne do
prvniho `-4 px` escape fieldu bez mezery. Tim je uzavrena pozorovatelna
N/N+1 hranice pro prepsane TOWN nody i jejich collision-driven audio.

Generalizovan je take obycejny `0x6480` last-field lifecycle. `a2c6` d2 je
pouze vstupni/activation margin; cull `+364` dostane pri alokaci vlastni
vychozi hodnotu −64. FLAME parent ji meni na −8, cannon/HOMING/PLOP a
PROXMINE strepy na 0. TOKEN ma cull behem 32tikoveho burstu vypnuty a po
aktivaci znovu pouziva −64. GOOSE ho zapina jen parentu pri escape, jeho
ctyri children jej maji vypnuty. TRAIN `screenY >= 272` je prime ukonceni
korutiny, nikoli `0x6480`; test ale nasleduje az po navratu z publikovaneho
fieldu, takze jeho zaznam take zmizi az pri dalsim resume.

Pro bezny cull se ve VBL N nejprve provede pohyb a invalidace, ale objekt se
jeste vykresli a vstoupi do collision sweepu. V N+1 dobehne bit4 scroll
compensation, clear hit flash, orphan, SMART a event callbacky; zaznam a cost
se uklidi az potom. Fixture pokryvaji ordinary air/hazard/spawn, aktivni i
burst TOKEN a margin-0 projektil/pomocne nody. Drive obecna mezera, kdy se tyto
nody filtrovaly pred poslednim renderem a sweepem, je tim uzavrena. Fresh
PROXMINE fragment, FLAME emitter/puff i TRAIN vagon navic v creation VBL
provedou prvni pohyb a `seq[0]` publikaci; `0x6480` childy v nem vyhodnoti i
bounds, zatimco TRAIN prime `screenY` vetveni ceka na dalsi resume.

Stale nejde o obecny emulator 68k coroutine scheduleru: po housekeeping
passu browser pokracuje kategoriemi `shots/air/hazards/spawns/tokens`, ne
jednim prokladanym FIFO seznamem vsech continuation bodu. Geometrie,
callback order a fresh-child fieldy jsou testovane, ale vzacna kombinace,
kde callback jednoho tasku a nasledna continuation jineho tasku soutezi o
RNG nebo audio hlas uvnitr stejneho VBL, zustava k porovnani s raw trace.

Konkretni dusledky, ktere zustavaji dalsim mechanickym blokem:

- presne prokladani vsech priority100 callbacku, kategorialnich continuation
  bodu a fresh-child startu jednim univerzalnim FIFO seznamem. SMART/event
  invalidace, SMART deadline, GOOSE child orphany/explosion childy a parent
  checksum uz maji vlastni creation-order body; to ale jeste nedokazuje
  obecnou frontu pro vsechny typy tasku;
- TRAIN lokomotiva prochazi priblizne 53 checksum yieldy (vagony ne), ale
  jeho presny continuation tail/cost release je stale aproximace. GOOSE
  parentovych 107 yieldu a release N+108 uz ma presnou regresi;
- map-reader stale yielduje po zaznamu jen v originalu, takze creation-order
  mezi soucasne zpusobilymi mapovymi tasky muze posunout RNG i fresh childy.

## 5. Map-reader a hardwarovy RNG — PORADI JE JEN HRUBE PRESNE

`0x365e` zaklada object tasky zhruba 256 px pred hornim okrajem. Prepis uz
oddeluje tento task-start od pozdejsiho `a2c6` marginu a spotrebuje
pre-`a2c6` RNG ve spravne fazi. V jednom JS kroku vsak zalozi vsechny prave
zpusobile zaznamy; nativni reader mezi zaznamy yielduje, takze pri shode vice
triggeru muze byt presne mezitaskove RNG poradi jeste jine.

PRNG `0x883c` i CIAB-IRQ `ADD.W VHPOSR` (`0x4ac8`) jsou bitove prepsane.
Vychozi browserova hodnota VHPOSR je ale zamerne nula. Bez zachyceneho
VHPOSR/input trace a funkcniho raw checkpointu originalu nelze tvrdit, ze
dlouhy beh pouziva stejny seed a stejne snimky jako Amiga.

## 6. Renderer — TOWN HW SPRITY A NORMALNI HUD UZAVRENY, ZBYVA RAW CHECKPOINT

Player bolt, kanonovy granat a publikovany PLOP frame BULLET#2 patri do osmi hardwarovych
sprite slotu (`0x5d86`), ne do globalni BOB fronty. TOWN runtime uz ma jeden
`0x3d00/0x3d4e` allocator pro vsechny tri zdroje: 64 zaznamu, presne poradi
kanalu, off-top skip pred spotrebou, linearni DMA reuse, kanalovou prioritu,
ctyri posunute COLOR17–31 banky a 30slotovy P1 pool. Black fade frontu
potlaci, white fade high registry nemeni. Nativni HUD font, 352x8 pata
bitplane a row COLOR16 jsou pod touto vrstvou.

Set HUD bit je podle originalniho raw frame nepruhledny COLOR16 override,
nezavisly na lower4; naivni `16|lower4` byla AGA chyba zpusobujici blikani
`HELI/PRESS FIRE`. Presny fyzicky OCS Denise trik zustava undocumented, ale
vysledna kompozice ma regresi. COLOR20/24/28 `AMPROG.OBJ` stale nezapisuje,
jejich cold-boot `0x000` je vsak otevrena politika jen pro nepopsane
sprite-bank sloty, ne blocker HUD barvy. Finalni RGB/DMA checkpoint porad
potrebuje raw mereni beziciho originalu. Allocator je zatim tvrzeni o TOWN
podporovanych tridach, ne automaticky o objektech dalsich levelu. Podrobnosti
jsou v `TOWN-PARITY.md` a `HUD.md`.

Browser drzi interni zasobu `lives=4` pred aktualnim player spawnem a HUD
zobrazuje `lives-1`: prvni stabilni gameplay field je proto `HELI 3`,
posledni skutecne aktivni vrtulnik `HELI 0`. Continue se otevre az po smrti
tohoto stroje a nasledujicim dekrementu zasoby na nulu.

## 7. Death/continue HUD — MECHANIKA UZAVRENA, STATS OBRAZOVKA OTEVRENA

Browserovy player task po smrti ceka presne 100 simulacnich VBL. `step()` se
po tuto dobu nezastavi: mapa, nepratele, efekty i scheduler dal bezi. Bez
dalsiho zivota vstoupi do `playerPhase="continue"`: s dostupnym kreditem na
300 VBL, bez kreditu na 100 VBL. Fire test `0x702c` je level-triggered, takze
tlacitko drzene uz pri vstupu vezme kredit hned v prvnim continue VBL.

Prijaty continue ubere jeden kredit, nastavi `lives=4`, `score=0` a
`nextLife=10000` a zalozi novy `HELI 3`. Pole zbrane `+100`, citac TOKENu
`+102` a mode `+104` preziji; bezny `0x70c8` muze pouze omezit power dolu
podle tieru a znovu nastavit reload. Continue ani cekani nema `g.over=true`.

Inactive renderer `0x740c` uz neni natvrdo `PRESS FIRE`. Bit 7 globalniho
VBL strida po 128 snimcich prompt a dynamicky status (cely cyklus 256):
`PRESS FIRE` s kreditem, `NO CREDITS` bez nej a po uzavreni joinu
`PLEASE WAIT`. Nepripojeny pravy slot ma interni `jeepLives=1`, proto jeho
dynamicka pulka ukazuje `JEEP 0`. V posledni sekvenci se tedy oba sloty
stridaji mezi `PLEASE WAIT` a `HELI 0`/`JEEP 0`.

Po timeoutu browser uzavre join, obnovi loaderovou hodnotu tri kredity,
vypne TOWN CPU writer pulzujiciho `COLOR07` a spusti fade do cerne po 16 VBL
(`+16` do 256). Svet bezi i behem fadu; `g.over` se nastavi az pri vstupu do
`playerPhase="stats"` na plne cerne. Regrese hlida hranice 99/100,
299/300, oba 128-VBL HUD pulcy, drzeny fire, zachovani vybavy, COLOR07 i
15/16. fade field.

Otevrena zustava az cilova podoba cerne statisticke stranky
`0x0da2..0x0e3e`: pixelove presny font/layout, uplne a nativne inkrementovane
citace `BULLETS FIRED`, `ENEMIES DESTROYED`, `ENEMIES ESCAPED`,
`TOKENS PICKED UP`, vypocet `PERCENTAGE COMPLETED`, high-score update/vstup
jmena a casovany navrat na titul. Soucasny Canvas panel zachovava spravnou
fazovou hranici, ale je zamerne jen placeholder a nema kompletni statisticky
tok.

## 8. Attract/title — HLAVNI SMYCKA PREPSANA, VSTUPY A POST-GAME VETVE OTEVRENE

Normalni attract dispatcher `0x0d64` uz v browseru prochazi poradi COVER,
Sales Curve, HELI blueprint a score table, JEEP blueprint a score table a
FACES. Obrazovky zustavaji indexove az do finalni kompozice; texty a mini-font
se ctou z `AMPROG.OBJ`, score jmena z `HS1..16.TXT` a paletove/Copper zmeny z
nativnich tabulek. Blueprint zachovava poradi BP2, loaderem prekryteho
typewriteru, paletovych tasku, BP1 merge a zaverecneho fadu. Jeho casovani je
navazane na zmereny nativni loader a continuation body, ne na rychlost
dekodovani souboru v browseru. BP2 reveal a prvni text jsou na 51/63 VBL pro
HELI a 45/57 VBL pro JEEP; spawn-to-generation jadro zustava 257/253 VBL.
Samostatny `MUSHROOM.RAW`/score handoff konci na 382/335 VBL, takze skutecne
viditelny BP2-to-score interval je 331/290 VBL. Stejny embedded HUD renderer
se prepina podle bitu 7 VBL a `AMTITUNE.MOD` bezi od konce COVER fadu do
startu hry.

Otevrene zustava:

- volba konkretniho `HS1..16.TXT` pouziva pri zalozeni attractu
  `Math.random()`, ne sdileny nativni PRNG/VHPOS stav;
- fire/click vzdy spusti jednoplayerovy HELI TOWN. Nativni rozliseni
  P1/P2, JEEP a kreditove startovaci vetve zatim prepsane neni; `L` je pouze
  browserovy vyvojarsky level picker;
- fire/click vzdy spusti jednoplayerovy HELI TOWN (viz vyse); obrazovka volby
  ovladani `0x1f5e` ("Press function keys to select controls") prepsana neni;
- `0x0f42..0x1042` (zaverecna sekvence) je prepsana **castecne** - viz nize;
- zapis do tabulky skore `0x2fe8` meni jen model tabulky, ne jeji obrazovku:
  nativne po nem jeste bezi `0x3062`, ktery vykresli jmeno hrace ze zaznamu
  (`+40`). Jmena bere hra z `AMDLS0.CAT` / `HS*.TXT`, hrac je nezadava.

### Post-game statistika `0x0da2` - PREPSANA (2026-09-07)

Obrazovka po konci hry uz neni zastupny text. Kresli ji nativni formatovany
text (`0x5934`) z retezcu `0x0e50` / `0x0e6d` (titulek podle bitu 3
`fp@(12353)`) a `0x0e8f` (popisky), paletou `0x2a1c` a peti cisly zarovnanymi
vpravo na x=230 s krokem 16 px (`0xe40`/`0xe48`). Citace maji v celem
`AMPROG.OBJ` po jedinem miste: `0x6014` (vystrelene strely, az po nalezeni
volneho slotu z tricetiprvkoveho poolu), `0xa2e4` (nepratele, kteri se
skutecne objevili - hned po `0x9ac8`) a `0xa36a` (zniceni). "Enemies escaped"
je jejich rozdil.

**`fp@(12490)` ("Tokens picked up") se v originale nikde nezvysuje**, takze
tam vzdy stoji nula; prepis to drzi.

Procenta `0xe06` pocitaji `(0xe9c0 - fp@(3534)) * 100 / 26817` v unsigned
word aritmetice. `fp@(3530)` je mapova pozice 16.16, kterou scroll task
`0x3cd4` snizuje a `0x1e0e` ji na konci hry odlozi do `fp@(3534)`; konstanta
`0xe9c0` je tedy jeji hodnota pri startu hry a citatel je ujeta vzdalenost.
Deleni 26817 odpovida souctu vysek vsech sedmi map minus prekryvy junkci
(hrube 27496 - 6x225). Dohrana hra ma podle `0xe18` natvrdo 100.
**Neovereno na originalu**: pocatecni hodnotu `fp@(3530)` jsme odvodili z
konstanty ve vzorci, ne zmerili; az harness dokaze dohrat do game over,
staci porovnat jedno cislo.

Modul se prepina nativnim mechanismem `0x5ea`: `fp@(10798)` = 1 (AMTITUNE)
nebo 2 (AMHITUNE) a loader task pri rozdilu prehodi. `0xf2a` pocita
`1 - fp@(3618)`, kde `fp@(3618)` nastavuje `0xf0c` -> `0x3040` = "skore
hrace neni mensi nez skore navazane polozky tabulky". Vychozi tabulka je
sedm longu na `0x33fe` (70000..10000; radek `0x33ba` za ne jeste prilepi
znak '0', proto attract ukazuje 700000..100000). Tyz priznak podle `0xe2a`
urcuje, jestli obrazovka drzi 400 VBL (`0x5f22`) nebo pet sekund s moznosti
prerusit palbou (`0x27ec`).

Model navazane polozky (`+4 -> +40`) je zjednoduseny na "nejnizsi zaznam
tabulky" - nativni vazba zaznamu hrace na konkretni radek zatim prepsana
neni.

## 9. Zony a tempo — RETEZENI MAP A ZPOMALENI SCROLLU OTEVRENE (2026-09-03)

Pruchod celym levelem (`TOWN-SURVEY.md`) ukazal dva systemove rozdily:

- ~~Original po konci `TOWN.PAM` streamuje `DESERT.PAM` bez preruseni~~ —
  **uzavreno 2026-09-03**: `parseMapChain` retezi vsech sedm PAM podle
  tabulky `0x384c` (mezera = treti slovo, paleta se nenuluje, dalsi mapa
  prekresli prekryv), `g.rowOffset` drzi radky TOWN pro checkpointy a
  testy, `g.levelPhase` roste jako `fp@(184)` (ctecka 256 px nad oknem).
  Dvojice t273..t321 sedi na teren DESERTu. LEVEL COMPLETE zbyva jen na
  konci FINAL. Chovani DESERTu se prepisuje podle cetnosti: hotovo AIRMINE
  (48), BLACKJET (7), TILT (11), DESTRAIN (3), TINYTRUK (7), EGGS vejce +
  hnizdo + strela + velky vybuch `0x8876` (7), DIAGUN + laser (6),
  PYRAMID (4), FISH (17), SKYEYEB (14), FLATTANK (9), GOOSE#7 (7),
  _ONERIG (11), JETS (6), _AIRPORT (4), _RIGS (4), TRUCK (1), INST1#9
  (2), JEEPHELI#31 = SWAP pad (1), MAMA + roj (3), INST1#14 pist +
  odpalovac (2), INST1#11 tovarna + paprsek (1) — **vsechna chovani
  DESERTu prepsana** (viz BEHAVIORS „DESERT"). GRASS podle
  `docs/ZADANI-GRASS.md`: hotovo VTOL (42), XEVIOUS#5 (20), XEVIOUS#9 +
  bomba (16), TRILO (5), _PLAT#9/#10 s vozidlem, vezi a strelou (7),
  XEVIOUS#0 s hlavni (3), DADA (1), _CORN#7 (1), druha SWAP plosina (1)
  a pasmo stop pasu JEEPHELI#43 (1) — **vsechna chovani GRASS prepsana a zrevidovana** (BEHAVIORS „Revize GRASS"); RIVER podle
  `docs/ZADANI-RIVER.md`: hotovo SKYEYEA (10), HOVER se sukni a raketou
  (8), LAKESUB s vezi a odrazivou strelou (7), JUNTANK#1 s vezi (3), JUNTANK#2 s dronem (3), LAKEGUN#0/#7 (3);
  INST2#2 s paprskem a vlnami (3) a INST2#0 (2) — **vsechna chovani
  RIVER prepsana**; ICE podle `docs/ZADANI-ICE.md`: hotovo EDGE (18),
  SEAPLANE s bombou (13), SKI (4), BOS s delem (1 + 27 v SCIFI) —
  **vsechna chovani ICE prepsana** a ze SCIFI bezni nepratele BUNNY
  (74), FROG (12), TAP se strelou (11), revize Fable 2026-09-04 (tri
  opravy: EDGE wait 5 i po sedme otocce, bomba SEAPLANE bez cull −16,
  FROG +364 = −16); zbyva ze SCIFI bossovy komplex (24 objektu v 7
  druzich, zadani `docs/ZADANI-SCIFI-BOSS.md`: hotova davka A =
  geyzir _LAVA#20 s kameny (8) a lusk ORB#0 s listy a koulemi (6),
  davka B = kraci boss INST3#3 s pody a zablesky (1) a emitory dronu
  INST3#12 (5), davka C = pevnost INST4#6 (1), INST4#0 s finale a
  koncem urovne (1) a dve veze INST4#3 - **vsechna chovani SCIFI
  prepsana**; pri davce C se navic domodeloval scroll lock z
  `fp@(166)` bitu 3 (mapa stoji, dokud zije instalace) a snizovani
  `fp@(140)` u tovarny, INST2#2 i INST3#3); zbyva jen zaverecny boss
  FINAL a zaverecny boss FINAL
  (INST5#0) - **prepsan cely** (rodic, handler s koncem hry, dve svetla,
  vypoustec hmyzu s nosicem a tremi utocniky, telo z 13 prstencu po 24
  kusech). Tim je **prepsano vsech 1497 objektu ve 73 druzich**.
  Overeno zatim jen
  simulaci a archy snimku; porovnani s baseline vAmigy po objektech
  (jako u TOWN) zbyva. Zvuky mimo TOWN jsou od 2026-09-07 prepsane
  (`0x4cf8`, `0x4d6a`, `0x4e2e`, `0x52d8`, `0x5350`, `0x5436`, `0x541e`,
  `0x54ac`, `0x55b0`, `0x5600`) - viz docs/SOUND.md.
- **Perioda geyziru 0x5350 se v prohlizeci losuje z forku PRNG.** Nativni
  callback `0x536e` cte `0x883c` na kazdem ze 127 stavu, tedy jednou za
  ctyri zvukova IRQ. Pocet cteni i jejich IRQ prepis dodrzuje (dynamicky
  hlas `sfxAdvanceGeyser`), ale WebAudio potrebuje cely buffer dopredu,
  takze zbylych 126 period vznikne z kopie PRNG odebrane pri prvnim stavu.
  Rozdeleni i pocet sedi, konkretni posloupnost se lisi, jakmile mezi
  zvukova IRQ zasahne herni kod. Presny prubeh potrebuje per-stav
  streamovani bufferu (nebo ScriptProcessor), coz zatim nedelame.
- **Extra zivot `0x5600` se zatim spousti v `awardScore()`.** Nativne prah
  vyhodnocuje az nasledujici resume ziveho hrace (`0x710c`), takze poradi
  vuci jinym taskum ve stejnem VBL neni overene.
- Scroll originalu se pricita jednou za iteraci hlavni smycky (`0x291e`),
  objekty integruji rychlost × ubehle VBL (`0x62fe`); pri zatezi A500 scroll
  zpomali (64–98 px za 8 s misto 100). Prepis bezi konstantne 50 Hz.
  Rozhodnuti o modelovani zatim otevrene; porovnavani snimku se zarovnava
  podle radku mapy, ne casu.

Dilci: TRAIN v t145 (neprukazne); MEDTANK sedi (1s zabery). GOOSE
kontaktni HP drain je vyresen sondou respawnu proti BOBum (`0x3dd4` kresli
do obrazovky `fp@(256)`, viz BEHAVIORS); zustava nemodelovane zpozdeni
respawnu pri plne pameti (`0x6162` ceka na 546 B z loaderoveho alokatoru
`fp@(-1502)`, jehoz heap neni v AMPROG).

## Co uz je vedomo jinde

Starsi seznam odchylek je v `MAPS.md` („Deliberately not rendered")
a tyka se statickych renderu, ne behu hry.

## Baseline snimky a DENISE_FRAME_SKIPPING (zmereno 2026-09-06)

`tools/baseline.sh` nenastavuje `denise set FRAME_SKIPPING 0`. Ve warp
rezimu Denise prehazuje buffery jen kazdy 17. snimek, takze ulozena
textura muze byt az o 16 snimku (0,32 s) starsi nez zadany cas. Zmereno
na checkpointu t=17: snimek s `FRAME_SKIPPING 0` se od dnesni cache
`build/baseline/orig_t17.raw` lisi ve **181 428 z 612 180 bajtu**
(cache se shoduje s variantou bez nastaveni).

Neni to samo o sobe chyba: radky mapy pro checkpointy `tools/compare.py`
byly zmereny z tychz snimku, takze system je vnitrne konzistentni.
Zapnuti volby by ale znamenalo **premerit vsechny checkpointy a znovu
usadit zarazku prahu**, proto se to nedela mimochodem. Az se bude stavet
porovnani po objektech (vAmiga ve WebAssembly), zacne se rovnou
s `FRAME_SKIPPING 0`. Postup a pasti prevzaty z projektu Turrican
(`tools/shot.py`): `screenshot save` emulator ukonci (jeden beh = jeden
cas) a "std::exception" u `wait` je kosmeticke.

## Harness s vAmigou ve WebAssembly (2026-09-06)

Jadro vAmiga prelozene do WebAssembly bezi v prohlizeci i pro SWIV:
`tools/build-wasm.sh` (prevzato z projektu Turrican) prelozi
`web/vamiga.js` + `.wasm`, stranka `web/vacmp.html` je bezobsluzna a
`tools/survey/vacmp.py` ji ridi pres Playwright - nabootuje SWIVFIX.ADF
s Kickstartem, projede vstupni sekvenci a ulozi snimek (716x285 RGB24,
stejny vyrez jako VAHeadless) nebo kus chip RAM. Jeden snimek v case
t=17 s trva 14 s.

**Opraveno 2026-09-07: harness se nikdy nedostal do hry.** Vstup se
posilal jako retezce do RetroShellu (`mouse1 press left`) a ty nedelaly
nic, takze emulace stala na cracktru. Vsechna drivejsi mereni zarovnani
tim porovnavala tmu s tmou - i ta "shoda 0,21 % v case t=17". Vstup nyni
jde primo pres `VA.fn.mouse` / `VA.fn.joy` (GamePadAction 4 fire, 7 press
left, 13 release fire, 16 release left) s podrzenim 4 snimku; sekvence je
32 s cracktro, 40 s MEGA TRAINER, 85 s fire na kreditove obrazovce.
Harness ukazuje skutecnou hru v TOWN uz od t=21 a je deterministicky
(dva behy = stejne MD5 chip RAM i stejny pocet vzorku).

**Zvuk z harnessu.** `VA.audio()` / `VA.runAudio(n)` vraci float vzorky.
Objevi se az po `VA.fn.warp(0)` - ve warpu je zvuk potlaceny - a jejich
spicka je zhruba 1 % plneho rozsahu (0,014 pri titulni hudbe, 0,034 pri
strelbe). Konfigurace vAmigy je pritom normalni (VOL0-3 100 %, VOLL/VOLR
100 %, ASR false, SAMPLING_METHOD NONE), takze jde o vnitrni meritko
jadra, ne o chybu prenosu; dynamika mezi ticho/hudba/strelba sedi.
Referencni nahravky se proto normalizuji (`build/vacmp/sfx/*.wav`).

Zarovnani casu s VAHeadless zustava otevrene, ale uz vime, ze **nejde
jen o posun**: obe strany bezi jinou vstupni cestou a globalni PRNG hry
navic perturbuje `VHPOSR` ze zvukoveho preruseni. Nez se harness pouzije
k porovnavani po objektech, musi se cas merit primo (`wasm_agnus_frame`
uz existuje, na strane VAHeadless je potreba prikaz RetroShellu).
Take je potreba najit bazi A6, aby se daly cist zaznamy uloh z chip RAM.

## Zvuk smrti bosse `0x553a` pod DMA minimem Pauly (2026-09-08)

Uzivatel po poslechu obou variant rekl, ze ani jedna nezni verne, a mereni
mu dalo za pravdu. Rutina pocita periodu jako `base +- 4*citac`, takze pro
base 200/202 klesa az na **72**, zatimco jeden audio kanal dostane jedno
slovo na radek, tedy hranice periody je kolem 114-124. **26 ze 128 stavu**
(obe vrstvy) lezi mezi 72 a 122.

- Nas render clampuje rychlost posunu adresy na periodu 123, takze prehraje
  celou osmibajtovou vlnu ciste, jen o **927 centu niz**, nez rutina zada.
- Paula misto toho DAC krokuje dal na pozadovane rychlosti, ale DMA nestiha
  dodat nove slovo, takze se posledni opakuje - meni se timbre, ne jen vyska.

Prosli jsme vsechny prepsane efekty: **zadny jiny pod 123 nejde** (nejblize
je geyzir 0x5350 se 127..254). Aproximace je tedy uzce ohranicena na tento
jediny zvuk.

**Pokus o mereni na originalu (neuspesny, ale nastroje zustavaji).** Harness
umi projit MEGA TRAINER (klavesy F1 nekonecne zivoty, F3 zbrane, F4 super
zbrane pres `wasm_key`), pulzovat palbu a nahravat zvuk pri `warp(0)`
rychlosti asi 7x realtime (240 s hry za 36 s). Detektor podpisu je
zkalibrovany: okno 14,6 ms = jeden stav, korelace dominantni frekvence se
stridavym vzorem; **nas render dava 0,877**, nejlepsi kandidat ve 240 s
skutecne hry 0,40 (a ten je na 0-717 Hz, tedy palba, ne synth). GOOSE boss
se objevuje kolem 75 s hry, ale skriptovany hrac ho nezabije.

**Baze A6 nalezena 2026-09-08: `0x17DC` (6108) v chip RAM**, AMPROG.OBJ je
nahran na `0xEFC0`. Postup i konstanty jsou v `tools/survey/vacmp.py`
(`A6_BASE`, `PROG_BASE`, `FIND_A6_JS`, `FIND_PROG_JS`); dva behy s ruznou
delkou hry daly stejne hodnoty. Metoda: `fp@(3530)` je mapova pozice 16.16,
kterou scroll task `0x3cd4` snizuje presne o `fp@(3526)` = `0x4000` za VBL,
takze dva otisky chip RAM N snimku od sebe daji jedinou adresu, ktera klesla
o `N*0x4000` a ma pred sebou long `0x4000`.

Tim padly dve otevrene veci naraz:
- `fp@(12490)` ("Tokens picked up") je na originalu v obou behach **nula**,
  presne jak rikala disassembly - statisticka obrazovka to drzi spravne;
- `fp@(3530)` bylo po 20 s hry `0xE7E5` a po 50 s `0xE66E`, tedy rozdil 359
  radku za 30 s = 12,0 px/s. Zpetna extrapolace k nule sedi na `0xE9C0`,
  cimz je **potvrzena konstanta ve vzorci na procenta** - drive jen odvozena.

**Dekodovani ADF overeno proti pameti originalu (2026-09-08).** Produkcni
cesta `unpackFile(adf, f) = unpackC(adf, f.off + 4, f.size)` da bajty, ktere
se v chip RAM shoduji **bajt po bajtu**: `BIGEXPL.SND` (8486 B) na `0x4CB38`
a `SMART.SND` (8280 B) na `0x4EC60`. Vzorek vybuchu, ktery hraje pri smrti
bosse, tedy spravny je. (`AMTITUNE.MOD` se za behu hry v pameti nenajde -
titulni hudba se pri nacteni hernich dat zahodi, jak rika docs/SOUND.md.)

**Uzavreno 2026-09-09 podle HRM: prah 123 i zpusob modelovani jsou spravne.**
Hardware Reference Manual (3. vydani, kapitola o zvuku) rika doslova: *"If
the period value is below 124, ... the audio DMA will not have had enough
time to retrieve the next data sample and the previous sample will be
reused"* a *"for PAL systems, a value of at least 123 ticks/sample must be
written into the period register"*. `PAULA_PAL_MIN_DMA_PERIOD = 123` je tedy
primo z dokumentace, ne odhad.

Overeny je tim i **zpusob** modelovani. Pri opakovani vzorku postoupi index
ve vlne jen tehdy, kdyz DMA stihne dodat, tedy nejvyse jednou za 123 tiku;
trajektorie indexu je `min(k, floor(k*perioda/123))`, coz je matematicky
totez, co dela nas clamp rychlosti posunu adresy. Lisi se jen jemna
struktura schodu, ktera lezi nad slysitelnym pasmem.

**Mezikrok, ktery se timto rusi.** Prvni cista nahravka `0x553a` z originalu
(spustena prepsanim displacementu volani `0x8aa4` na `0x553a`, aby efekt sel
nativni cestou vcetne zastaveni DMA v `0x4bca`) vypadala, jako by nejkratsi
zahrane periody byly 114-126, a z toho vzniklo tvrzeni, ze nas prah je o 130
centu moc vysoko. Bylo to spatne dvakrat: 227/2 = 113,5 neni skutecny
rozpocet DMA, a hlavne odhad periody z prechodu nulou na roztresenem prubehu
nemeri zakladni frekvenci. Byl to artefakt meridla, ne nalez o hardwaru.

Porovnani stav po stavu navic neni ciste z jineho duvodu: `0x553a` posila
obe vrstvy pres oba selektory a druha muze po rejectu propadnout do teze
dvojice, takze se v jednom kanale sectou dva tony s periodami 200 a 202.

Rozdil, ktery uzivatel slysel, tedy podle vseho nepochazi z chovani pod
periodou 123. Prvni porovnani dostal jako **samotny synth**, zatimco ve hre
na nej hned nasedaji dve vrstvy BIGEXPL (`build/sfx-boss/boss-death-REMAKE-CELY.wav`).
Nahravka ze skutecne Amigy zustava vitana jako kontrola, ale uz na ni nevisi
zadna konkretni konstanta.

Zbyva zmerit zvuk `0x553a`. Prve pokusy: instalace pozadavku primo do
hlasove struktury (`fp@(10786)`, ctyri po 268 B) zafunguje, ale zacatek
efektu vyjde potichu, protoze se preskoci zastaveni DMA z `0x4bca` a novy
AUDxLC se nezalatchuje. Cista cesta je **prepsat displacement volani
`0x8aa4` (zvuk palby) na `0x553a`** - jeden vystrel pak spusti synth
nativni cestou. Prvni trasa takto porizena ukazuje, ze original v prvni
tretine efektu hraje periody kolem **130-150**, zatimco nas render tam
clampuje na konstantnich 123; pozadovanych 74 nehraje ani jeden. Presne
cislo potrebuje cistsi nahravku (bez ostatnich efektu) a lepsi odhad
frekvence nez pocitani prechodu nulou.

## Rozliseni typu zivych uloh - VYRESENO (2026-09-09)

`tools/survey/tasks_live.py` priradi kazde zive uloze chovani podle PC na
`+270` a nove i pozna, jestli uz prosla `a2c6`, tedy jestli jsou `+360 hp` a
`+504 trida` platne.

**Marker:** `a2c6` na `0xa326` zapise `movel #0xa36a, +534` (handler smart
pulzu). Smart-immune se pak dodela zapisem jen do **horni** poloviny -
`movew #-1, +534` (`0x8604`) nebo `st +534` (12 mist) - protoze `0x6468`
testuje znamenko celeho longu. Spodni slovo tedy zustava `0xa36a` i u immune
objektu a je to spolehlivy priznak inicializace.

Overeno na peti kontrolnich bodech (20..100 s hry, 198 uloh): oznacene ulohy
maji vyhradne platne tridy a hp 0..3, neoznacene maji tridy typu 8191, 21064
a hp -27862. `+504` je pritom **bitove pole**, ne vycet - vedle znamych 4,
34, 36 se bezne objevuji i 32 a 72.

**Znamy limit:** blok o 308 B se recykluje, a kdyz ho dostane uloha, ktera
`a2c6` nevola, zustane v `+534` marker po predchozim uzivateli; zridka se tak
`anim_task` pripise "inicializovano". Pro mapove objekty to nevadi (ty `a2c6`
volaji vzdy), u efektovych uloh se na priznak spolehat nelze.

## Aktivacni marze: 18 chovani opraveno (2026-09-09)

`0x9ac8` (volane z `a2c6`) drzi korutinu, dokud `y - D2 < kamera` unsigned,
tedy pusti ji presne pri `ys >= D2`, kde `D2` je registr pri volani `a2c6`.
Prepis tuto hodnotu drzi v `step()` jako `margin`, ale mel ji vypsanou jen
u casti chovani - zbytek bral vychozich -32.

`tools/margins.py` porovnal obe strany staticky a nasel **18 rozdilu**;
u peti (tank, roto, mine, camogun, rig) jsem hodnotu overil primo v
disassembly (`moveq #-16,%d2`). Vetsina se rodila o **16 px driv**, nez ma,
coz je pri 12,5 px/s asi 1,3 s. Opraveno, `margins.py` hlasi 0 rozdilu,
compare/smoothtest/uitest zustavaji zelene (parita TOWN 99,9 / 99,0 / 98,3
/ 99,9 %).

Parser je zamerne konzervativni: kdyz mezi zapisem do `D2` a volanim `a2c6`
lezi skok nebo cil skoku, hlasi "nelze urcit staticky" misto falesneho
nalezu. Hned to zabralo u `0x7970`, kde rodic ma `movew #176` a pres `bras`
preskoci `moveq #127`, coz je vstup ditete - naivni zpetne hledani by
ohlasilo chybu tam, kde zadna neni.

**Rezim `--predict`: oprava marzi potvrzena proti mape.** Parovani podle
polohy selhavalo u pohyblivych objektu, tak `objdiff.py` dostal dva dalsi
rezimy. `--events` porovnava **okamziky aktivace** (invariantni vuci pohybu,
krok 4 VBL = 1 px) a `--predict` je pocita **primo z mapy** jako
`ujeto = margin + zero - y`, tedy uplne bez originalu a bez RNG. Z devíti
sparovanych aktivaci na useku 1500 px sedi vsech devet **presne na 0 px**.

Pri ladeni se ukazaly tri veci, ktere se musi vynechat, jinak nastroj hlasi
falesne nalezy:
- **Formace** (`wave`, `yellow`, `bird`, `blackjet`, `fish`, `goose7`,
  `skyeye`, `skyeyea`) nastavuji `born` uz v `startMapObjectTask` na prahu
  -256, protoze mapovy zaznam je jen spoustec; kazdy klon si pak ceka na
  vlastni a2c6 prah. Bez vyjmuti hlasi skript systematicky **-208 px**, coz
  je presne rozdil -256 a -48 - vypadalo to jako velky nalez a neni to nic.
- **Deti**: vetsina "chybi v prepisu" u FLAME jsou plameny, ktere prepis ma
  jako `hazards`, ne `spawns`. Kontrola proti `build/spawns.json` ukazala,
  ze FLAME je v mape jen na x 95, 75, 100 a 118 - hlasene x 112, 117 a 231
  tam nejsou, takze slo o deti.
- **Palba**: kdyz obe strany strili, objekty umiraji v jinych okamzicich.
  Harness proto bezi bez palby.

**Plny sken vsech sedmi zon (2026-09-09): 980 z 981 aktivaci presne, nula
odchylek.** Parovani jde pres poradi vzniku, ne polohu (`tank` a `train` si
`x` pri vzniku prepisou, protoze vjizdeji z okraje). Jedina neaktivovana je
`inst5` a je to artefakt kontroly: FINAL boss ceka na `g.inst1Factories > 0`
(bit 3 `fp@(166)`), zatimco skript tuto promennou nuluje, aby obesel scroll
lock u DESERT tovarny - bez palby by ji hrac nezniicil a mapa by stala.

Pri dolazovani se ukazalo, ze ocekavani se **musi pocitat az v okamziku
`taskStarted`** (prah -256), ne z mapove polohy: nektera chovani do te chvile
jeste meni `y` nebo si urcuji vlastni marzi - `xevswarm` posune rodici `y` o
-27 (`0x7ed8`) a `airplane` si nastavi 176 (`0x7978`), zatimco jeho dite ma
127 (`0x797e`). Naivni predikce z mapy hlasila prave tyhle dva druhy jako
chybu (+208 a +27 px), pritom prepis je mel spravne; hodnoty jsou overene v
disassembly. `margins.py` u `airplane` schvalne hlasi "nelze urcit staticky",
protoze rodic pres `bras` preskoci hodnotu ditete.

Test bezi bez originalu i bez emulatoru, takze se hodi jako rychly kontrakt
vedle compare/uitest/smoothtest.

## Zaverecna sekvence `0x0f42` - prepsana struktura, animace zbyva (2026-09-09)

Vola se z attract dispatcheru na `0xd90`, tedy **jeste pred statistikou**
`0x0da2`, a jen kdyz je nastaven bit 3 `fp@(12353)`.

Prepsano: obe obrazovky (`CONGRAT2.RAW`, pak `CONGRAT1.RAW`), palety
`0x2abc` a `0x2adc`, fade z cerne, bila mezifaze, zaverecny text `0x1058`
a zvuk `0x51d4` (ctyri hlasy priority 127 na periodach 400, 480, 413 a 441;
hlasitost je `citac >> 7`, takze nabiha velmi pomalu). Tim je **posledni
nepripojeny zvuk ve hre pripojen**.

**REACTOR animace prepsana 2026-09-10.** Prvni faze uz neni staticky obrazek:
reaktor (REACTOR#13 na 102,126), emitor, ktery po 6 VBL vypousti dvacet
castic s nahodnou sadou snimku (#27-30, #31-34, #35-38 z `docs/ANIMS.md`), a
raketa, ktera po nich startuje z (99,130), stoupá `x += 1/16, y -= 3/16` a
prehraje `0x012F0` (#12 dolu na #1) a `0x0131C` (#0 nahoru na #12).

Puvodni popis uloh (zustava jako reference):
- `0x13ea` staticky dil na (102, 126), z 1, gfx `0x1a55`, `+367 |= 1`;
- `0x134e` na (99, 130) s anim `0x1c55`, ktery pres `0x137c` vytvori dvacet
  deti `0x1412` s rozestupem 6 VBL, pak `0x1398` vypusti raketu `0x12d2`
  (x += 1, y -= 3, z = 2, `fp@(11164)` 4092 -> 4095, dve dlouhe anim davky).
Druha faze pridava emitory `0x125e` (dva `0x14a2` s parametry 98/156/30 a
98/130/44), tres mapove pozice `0x122a` a kruhy `0x11d4` (jedenact volani
`0x1222` na polomerech 56..184, kresli je Bresenham `0x14f0`).

Misto teto animace drzi prepis **zmerenou delku jejiho skriptu** (20x6 + 80
VBL), takze casovani sceny sedi, ale obrazovka je staticka. Kontrakt v
`tools/uitest.py` hlida poradi i delku fazi (199 / 415 / 1415 VBL), zvuk,
text a palety.

## Pauza na klavesu P - zmerena, ale mimo AMPROG.OBJ (2026-09-09)

Uzivatel upozornil, ze hra ma pauzu na `P`. Overeno v harnessu primo:
mapa se posouva 25 px za 100 VBL, po stisku `P` **0 px**, po druhem stisku
zase 25. Je to tedy prepinac; mezernik s tim nedela nic (`Esc` naopak
zpusobi skok mapy o tisice pixelu, coz jsme dal nezkoumali).

**Kod ale nelezi v `AMPROG.OBJ`.** Ten cte klavesnici jedine v
level-select cheatu `0x20e4`, ktery bere `fp@(-1)` a prijima jen kody
`0x50..0x59` (F1-F10) a `0x5f` (HELP). Otisk chip RAM pred a po stisku `P`
ukazuje zmeny kolem `fp@(-1260)`, tedy v knihovne zavadece na zapornych
offsetech od A6.

Nelze proto rozhodnout, jestli je pauza puvodni funkce Sales Curve, nebo
pridavek crackeru - zavadec je soucasti teto diskety a cistou verzi k
porovnani nemame. Prepis ji ma (mrazi jen logiku, render bezi dal a v
panelu svitit "PAUZA"), s touto poznamkou v kodu.

## Junkce map a `levelPhase` (nalezeno pri revizi 2026-09-06)

`g.levelPhase` se inicializuje cislem urovne (`lv`), ale `g.junctionRows`
se stavi jen pro nactenou retezovou mapu (pri startu ze zony 6 ma jedinou
polozku `[768]`). Smycka `levelPhase < junctionRows.length` se proto pri
primem startu z vyberu nikdy nespusti a prechod map se nedetekuje;
jediny, kdo to dnes cte, je obtiznost (`0x35d4`, `fp@(184)`). Pri startu
z TOWN indexy sedi. Opravit az spolu s porovnanim po objektech, kdy bude
zmereno, kde presne original pocita konec mapy.

## Plynuly rezim ("vylepseno") - tri opravy po hlaseni z hrani (2026-09-06)

Hlaseno: zadne podstatne zlepseni, obcas problikne artefakt, chybi
kratery po tancich. Zmereno sondou (DESERT po sestreleni tanku, TOWN
900 snimku pri 60 Hz vcetne simulovaneho skrtnuti displeje):

- **Kratery a vsechny dekaly chybely.** `renderSmoothField` barvil holy
  `g.mapIndex`; klasicka cesta dela v `composeTownBobs` prepass dekalu
  (`0x898c` zapisuje do mapy). Ted se barvi okno mapy s tymz prepassem
  pres `colorizeIndexedField` s absolutni Copper paletou. Chybely tak i
  stopy min a cele telo bosse FINAL (312 dekalu).
- **Probliknuti = spatne sparovani mezi tiky.** `bob()` ukladal creation
  ordinal jen do fronty `pending`, ne do `spec`, takze kazdy kresleny
  zaznam (i hrac) dostal pozicni serial fronty. Pri kazdem prichodu nebo
  odchodu objektu se klice posunuly a sprite se na jeden snimek
  interpoloval z cizi polohy - zmereno 21 z 900 snimku, skoky az 70 px.
  Ordinal je ted ve spec; zaznam bez nej se neparuje a kresli se na
  aktualni poloze (zadna interpolace je lepsi nez spatna). Po oprave
  0 skoku z 900 snimku.
- **Skrtnuti displeje.** Pri dvou a vice ticich v jednom snimku byl
  `bobPrev` o tik starsi, nez alfa predpoklada; ted se v takovem snimku
  neinterpoluje.

Co zustava: teren se v originale posouva 1 px za 4 tiky (12,5 px/s),
takze jeho vyhlazeni je na 60 Hz nenapadne - videt je hlavne na rychlych
objektech a na vlastnim stroji. HW sprity (hrac, strely) jdou stejnou
frontou jako BOBy, interpoluji se tedy take. Kontrakt `tools/compare.py`
se tyka jen klasicke cesty; pro plynulou zatim zadny neni.

Sjednoceno (tez 2026-09-06): teren se drive extrapoloval o tik dopredu,
objekty interpolovaly o tik dozadu. Ted jde **oboji dozadu** z hodnot
predchoziho tiku (`g.scrollPrev` ze zacatku `step()`) k aktualnim.

**Scroll se pritom interpoluje ZLOMKOVE, rohy spritu z celych cisel.**
Prvni verze zaokrouhlovala oba konce dolu, aby snimek pri alfa = 0 a 1
presne sedel s klasickym; jenze mapa se posouva **0,25 radku za tik**,
takze mezi celociselnymi konci stala tri tiky a pak skocila o cely pixel
- tedy presne to cukani, ktere ma plynuly rezim odstranit (zmereno pri
testu na 120 Hz: 3 snimky stoji, 3 se posouvaji, 6 stoji). Ted se scroll
interpoluje ze zlomkove hodnoty a kvantuje na 1/S px, sprity od nej
odcitaji tentyz zlomkovy scroll (takze se vuci zemi neplavou) a jejich
vlastni rohy zustavaji cele, jako v klasickem blitu. Zmereno pri zoomu
3x (S = 3): 37 ruznych poloh pozadi za sekundu, krok vzdy 1/3 px, pri
120 Hz pauza 2 az 4 snimky mezi kroky (rovnomerne), pri 60 Hz 0 az 2.

Skok scrollu o vic nez 4 radky (konec SCIFI, −319) se neinterpoluje, bez
`bobPrev` se kresli aktualni tik. Vzhled spritu (snimek animace, zablesk
zasahu) je vzdy z aktualniho tiku. `g.smoothScrollF` drzi skutecne
pouzitou hodnotu pro diagnostiku.

**Kontrakt `tools/smoothtest.py`** (S = 1, bez HUD): plynuly snimek se
pri alfa → 1 rovna klasickemu snimku aktualniho tiku a pri alfa = 0
klasickemu snimku predchoziho tiku - mimo obdelniky spritu, kterym se
mezi tiky zmenil snimek animace. Protoze scroll je zlomkovy, splynou
snimky jen v tiku s celociselnym scrollem (kazdy ctvrty), takze se
kazdy konec intervalu zarovnava zvlast, a to krokovanim pres render()
(jinak by se neaktualizovalo parovani poloh). Zmereno: mimo masku
nejvyse 150 px
(zarazka; SCIFI tik 9000 dava 103 px na hranach prekryvu letících kamenu
se stinem a BOSu orezaneho hornim okrajem, ICE 31 px). Kontrakt zaroven odhalil, ze
kopie formaci (0x6178 pres `Object.assign`) dedily `bobOrdinal` rodice a
v plynulem rezimu se parovaly navzajem - ted dostavaji vlastni poradi
vzniku. Cena
sjednoceni: obraz je za logikou o jeden tik (20 ms); klasicky rezim
ukazuje aktualni tik hned. Na 120 Hz plynuly rezim odstrani
nepravidelny rytmus 2-3-2-3 opakovanych snimku.

## Velikost herniho pole (zoom, 2026-09-07)

Hlaseno pri testu na 120Hz monitoru pod Windows: herni pole je moc velke
a neslo nastavit. Zvetseni se pocitalo jen z okna (`fit`) a jeste se
nasobilo **1,5**, takze na 1920x1080 vyslo 1440x1152 px - vic, nez se do
okna vejde - a hlavne **neceločíselne**: cast hernich pixelu byla na
obrazovce o bod sirsi nez zbytek a rolujici teren delal vlnky.

Ted `viewScale()`:

- nasobek se pocita ve **skutecnych bodech displeje** (`devicePixelRatio`;
  na Windows se skalovanim 125 % je 1,25), ne v CSS pixelech, takze
  vychazi cely i pri systemovem skalovani;
- posuvnik `#zoombox` v testovaci liste: 0 = auto, dal 1x az na nejvetsi
  nasobek, ktery se do okna vejde (max se prepocitava pri resize);
  volba se uklada do `localStorage` (`swivZoom`);
- vnitrni platno je 320*S (S = nadvzorkovani plynuleho rezimu) a S se
  voli jako nejvetsi delitel nasobku **do osmi**, tedy zpravidla
  S = nasobek: krok kvantovani je pak presne jeden bod displeje a platno
  se uz nezvetsuje (pomer 1). Auto bere nejvetsi nasobek, ktery se vejde.

Zmereno na ctyrech kombinacich (dpr 1 / 1,25 / 1,5 / 2): pomer
sirka v bodech displeje / sirka platna vyjde vzdy cele cislo. Klasicka
cesta ma S = 1 vzdy, takze kontrakty `compare.py` a `smoothtest.py`
(ktere ctou platno 320 px) plati dal.

Vyrez zustava 320x256; zobrazeni vetsi casti mapy je samostatna vec
(viz `docs/ZADANI-TURRICAN.md`, kde se resi pro jinou hru).

## "Sev" v obraze pri plynulem rezimu (nahlaseno 2026-09-07, opraveno)

Hlaseno pri testu na 120 Hz: *"vzdycky v jedne ctvrtine je v obraze takovy
sev"*. Zmereno a je to **kvantovani pohybu pozadi**, ne prostorovy sev.

Mapa se posouva 0,25 px za tik. Puvodne se S (nadvzorkovani) volilo jako
nejvetsi delitel nasobku **do ctyr**, takze pri zoomu 3x vyslo S = 3 a
krok kvantovani 1/3 px byl **vetsi nez posun za tik**. Sonda: kroky
pozadi za tik pri 3x byly `{0: 4, 0.333: 11}` - **jeden tik ze ctyr stal
uplne**, presne ta "ctvrtina". Pri 2x `{0: 8, 0.5: 7}`, tedy kazdy druhy.
Pri 6x vychazelo S = 3 (delitel), takze taky 2, 2, 2, 0 bodu.

Oprava: strop S zvednut na 8, takze S = nasobek a krok kvantovani je
jeden bod displeje. Pozadi pak ujede `nasobek / 4` bodu za tik:

| zoom | S | kroky za tik | pozadi |
|---:|---:|---|---|
| 2x | 2 | 0 / 0,5 | stoji kazdy druhy tik |
| 3x | 3 | 0 / 0,333 | stoji jeden ze ctyr |
| 4x | 4 | 0,25 | **rovnomerne** (1 bod) |
| 5x | 5 | 0,2 / 0,4 | strida 1 a 2 body |
| 6x | 6 | 0,167 / 0,333 | strida 1 a 2 body |
| 7x | 7 | 0,143 / 0,286 | strida 1 a 2 body |
| 8x | 8 | 0,25 | **rovnomerne** (2 body) |

Od 4x vys uz zadny tik nestoji. Pod 4x ujede tik min nez jeden bod
displeje a cast tiku stat musi - to je mez pixeloveho rastru, ne chyba
prepisu; label to hlasi jako "pozadi skace". Cena zvednuti stropu je
pamet platna (pri 8x 2560x2048); teren se barvi v rozliseni mapy, takze
na S nezavisi, roste jen rasterizace spritu na GPU.

## Vodorovny sev na radku 16 (nahlaseno 2026-09-07, opraveno)

Zadavatel upresnil, ze "sev" je **prostorovy** - vodorovna cara v horni
casti obrazu. Zmereno (zoom 4x, porovnani snimku pri alfa 0 a 1, po
obrazovkovych radcich): **radky 0-15 se neposouvaly vubec, od radku 16
dolu ano**.

Pricina: `renderSmoothField` kopirovalo prvnich 16 radku z klasickeho
snimku (`g.mapFrame`), aby melo HUD. Klasicky snimek ma ale teren na
celociselnem `top`, ne na interpolovanem `scrollF`, takze pod HUDem teren
stal, zatimco zbytek obrazu se posouval subpixelove - na radku 16 vznikla
nehybna hrana. Textura HUDu je ridka (jen tahy pisma), takze teren pod ni
prosvita a hrana byla videt.

Oprava: `hudOverlayCanvas()` sklada HUD do **pruhledneho** platna
(stejna smycka jako `compositeHudPlane`, pozadi s alfa 0) a plynula cesta
ho kresli pres interpolovany teren na `HUD_SCREEN_Y`. Po oprave nema
zadny radek detail bez pohybu.

## Volitelne prolnuti pozadi ("hladke pozadi")

Zaskrtavatko v testovaci liste (`state.blendBg`, vychozi vypnuto).
Pri zapnutem se scroll **nekvantuje** na bod displeje a teren se kresli
dvakrat pres sebe - na dolni bod plne a na dalsi s alfou podle zlomkove
casti. Vodorovne zustava obraz ostry, svisle se michaji nejvyse dva
sousedni body.

Zmereno (kroky pozadi za tik, 16 tiku):

| zoom | bez prolnuti | s prolnutim |
|---:|---|---|
| 2x | 0 / 0,5 (stoji kazdy druhy) | 0,25 rovnomerne |
| 3x | 0 / 0,333 (stoji jeden ze ctyr) | 0,25 rovnomerne |
| 4x | 0,25 rovnomerne | 0,25 rovnomerne |
| 5x az 7x | strida dva kroky | 0,25 rovnomerne |
| 8x | 0,25 rovnomerne | 0,25 rovnomerne |

Je to **vedoma odchylka od originalu** (Amiga michat radky neumi), proto
opt-in: hodi se, kdyz se do okna vejde jen 2x nebo 3x, kde jinak cast
tiku stoji. Kontrakt `tools/smoothtest.py` meri vychozi cestu (bez
prolnuti); pro prolnutou zatim kontrakt neni.

## Harvest z `game-codex.html`: aktivace pres high word (2026-09-10)

Codex upozornoval, ze `0x9ad6` porovnava **samostatne WORDy** objektu a
kamery (`cmpw`), kdezto prepis pocital floatovy rozdil, a ze to muze
aktivovat task o 1 az 3 VBL pozdeji.

**Zmereno pred prevzetim:** ze 453 aktivaci klonu formaci v TOWN by se ani
jedna nerozhodla jinak - klony maji pri vzniku celociselne `y` a `scrollTop`
uz je `floor`. Zlomkove `y` v prepisu ovsem existuje (air 14,6 %, spawn
10,4 %, strely 79,7 % vzorku), takze situace, kdy by se rozdil projevil,
teoreticky nastat muze.

Prevzato tedy proto, ze **disassembly to tak dela**, ne kvuli merenemu
dopadu - ten je nulovy. `airMemberAtMargin` v `activateAirMember`. Vsech pet
kontraktu zustava zelenych.

Zbytek Codexova souboru (model `worldSpace` pro strely, prepracovane EGG a
TILT, `mapObjectArmedAtStart`) je 58 funkci a chce revizi objekt po objektu
proti disassembly - samostatna davka, ne harvest jedne zmeny.

## Prevzato z `game-codex.html` (2026-09-07)

Codex publikoval `game-codex.html` - odbocku z `game.html` z predchoziho
dne (ma jeste celociselne konce scrollu i sev na radku 16, oboji uz je
v `game.html` opravene). Slucovat cely soubor by byl krok zpet; prevzaty
jsou tyto veci:

- **Cisteni klaves pri ztrate fokusu** (`window blur -> g.keys = {}`).
  Prepnuti okna s drzenou sipkou nechalo klavesu "zmacknutou" a stroj
  odjel sam. Skutecna chyba, kterou jsme nemeli.
- **Zmerena vyska okoli platna** (`chromeHeight()`) misto natvrdo zadane
  rezervy 170 px: scita se poloha platna a skutecne `offsetHeight`
  testovaci listy, radku velikosti a paticky. Zmereno 139 px, tedy o 31
  px vic pro hru; hlavne se to ale samo prizpusobi, kdyz ovladacich
  prvku pribude (nase 170 uz bylo po pridani posuvniku spatne).
- **Tlacitka "do okna", 2x, 3x, 4x** vedle posuvniku, se stavem
  v `aria-pressed`.
- **`state.zoom` je prani, ne oriznuta hodnota**: male okno ho jen
  docasne omezi a po zvetseni se vrati (zmereno: prani 3x, v malem okne
  se pouzije 1x, po zvetseni zase 3x). Drive se ulozena hodnota orezala
  natrvalo.
- Pristupnost: `tabindex` a popisek na platne, fokus na platno pri
  kliknuti, obrysy pri ovladani klavesnici.

**Neprevzato a proc:**

- Codex drzi nadvzorkovani pevne na 4 nezavisle na zvetseni. Krok 1/4 px
  pak presne sedi na 0,25 px za tik, takze pozadi nezastavi na zadnem
  zvetseni - elegantni. Cena je ostrost: platno 1280 px se pri zoomu 3x
  zmensuje na 960 (pomer 0,75) a sloupce pixelu prestanou byt stejne
  siroke. Nase cesta drzi presnou mrizku (pomer vzdy cely) a
  nerovnomernost pod 4x resi volitelnym prolnutim. Obe reseni jsou
  legitimni, jen jinde na kompromisu ostrost/plynulost.
- Plynuly posuvnik 0,5x az 6x po 0,05: neceločíselne zvetseni pixelartu
  dela ruzne siroke pixely, coz je presne to, co jsme odstranovali.

## Strely (HW sprity) se neinterpolovaly (nahlaseno 2026-09-07, opraveno)

Po vyhlazeni pozadi zustaly strely znatelne mene plynule. Zmereno:
`hwSpriteCandidate` pocita kotvu z `positionWord(source.x/y)`, tedy
celociselnou polohu tiku, a `drawTownHardwareSprites` ji kreslila
**bez jakekoli interpolace** - hracovy bolty, cannon a PLOP tedy skakaly
po 50 Hz, zatimco teren i BOBy uz jely plynule. Na 120 Hz to byl
nejnapadnejsi rozdil v obraze.

Oprava: HW sprity jdou stejnou cestou jako BOBy. Polohy tiku se
zaznamenaji jednou (`g.hwCur`/`g.hwPrev`, klic `kind#ordinal` u cannon a
PLOP, `kind#s<slot>` u boltu z poolu 0x6028), paruje se jen se sousednim
tikem a u boltu se navic overuje totoznost zdroje, protoze **slot v poolu
se po uvolneni znovu obsadi** a jinak by novy bolt zdedil polohu stareho.
Kotva se prepocita na svet (`kotva + top` prislusneho tiku), interpoluje
a odecte se interpolovany scroll.

Zmereno na jednom boltu pri zoomu 4x uvnitr jednoho tiku (alfa 0 →
0,999): y 150,5 → 148,25 → 146 → 144 → 141,75, tedy kroky po ~2,25 px
kvantovane na 1/4 px. Drive byla hodnota po celý tik konstantni.

**Zbyva (dalsi krok):** kotvy jsou v kazdem tiku zaokrouhlene dolu na
cele pixely (`positionWord`, resp. `Math.floor` u BOBu), takze
interpolace jede mezi zaokrouhlenymi konci. U pomaleho objektu to dela
nerovnomernou rychlost - zmereno na letci YELLOW s 0,615 px za tik:
skutecne polohy 101,073 → 101,688 → 102,303 → 102,919, po zaokrouhleni
101, 101, 102, 102, tedy kroky 0, 1, 0, 1. Je to tataz trida chyby jako
drive u pozadi; naprava je interpolovat ze zlomkovych poloh a kontrakt
zarovnat na tiky, kde poloha vyjde cela.

## Zlomkove polohy spritu (2026-09-07, druhy krok po strelach)

Kotvy objektu se v kazdem tiku zaokrouhlovaly dolu na cele pixely
(`Math.floor` u BOBu, `positionWord` u HW spritu) a interpolace jela mezi
temito zaokrouhlenymi konci. Objekt pomalejsi nez pixel za tik proto
stridal stani a skok - zmereno na letci YELLOW s 0,615 px/tik: skutecne
polohy 101,073 → 101,688 → 102,303 → 102,919, po zaokrouhleni 101, 101,
102, 102.

Ted se interpoluje ze zlomkovych poloh a kvantuje se az vysledek.
Zmereno na temze letci pri zoomu 4x uvnitr jednoho tiku (alfa 0 →
0,999): kreslena x 72 → 72,25 → 72,25 → 72,5 → 72,5 → 72,75, tedy
rovnomerny posun po 1/4 px misto jednoho skoku.

**Kvantuje se na NEJBLIZSI bod displeje, ne dolu.** Kvantovani dolu (jako
68k high-word) tu nejde pouzit: interpolace konci tesne pod cilovou
polohou, takze objekt lezici na celem pixelu by pri alfa → 1 spadl o
pixel zpet. Dusledkem je, ze sprite muze byt v plynulem rezimu az o pul
bodu jinde nez v klasickem snimku. Je to **vedoma cena za plynuly pohyb**
- klasicka cesta zustava verna originalu (ten polohu orezava, protoze
cte horni slovo 16.16) a kontrakt `tools/compare.py` se tyka jen ji.

**Kontrakt `tools/smoothtest.py` proto zmenil masku:** drive pokryvala
jen sprity se zmenenou animaci a mimo ne se nesmelo lisit nic. Ted
pokryva obdelniky **vsech** spritu obou tiku (vcetne HW spritu, ktere
nejdou pres `composeTownBobs`), rozsirene o 3 px. Mimo ne je zarazka 4 px
na ojedinele pixely obrysu. Kontrakt uz tedy nehlida polohu spritu, ale
porad chyta to, kvuli cemu vznikl - zamrzly pas, sev HUDu, chybejici
dekaly, spatne parovani -, protoze ty jsou o dva rady vetsi. Pri padu
vypise souradnice prvnich dvanacti bodu mimo masku.

Zmereno ve vsech sedmi zonach: mimo masku 0 az 1 px.

