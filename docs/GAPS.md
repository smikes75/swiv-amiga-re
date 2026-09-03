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
- `AMHITUNE.MOD` decoder a regrese znaji, ale zadna runtime scena jej zatim
  nespousti ani na nej neprepina;
- podminene post-game obrazovky nejsou soucasti normalni attract smycky.
  Zejmena `0x0f42..0x1042` nacita `CONGRAT2.RAW`, paletu `0x2abc` a REACTOR
  tasky; spolu s `CONGRAT1`, high-score vstupem a navratem na titul patri do
  dosud otevreneho post-game toku.

## 9. Zony a tempo — RETEZENI MAP A ZPOMALENI SCROLLU OTEVRENE (2026-09-03)

Pruchod celym levelem (`TOWN-SURVEY.md`) ukazal dva systemove rozdily:

- Original po konci `TOWN.PAM` streamuje `DESERT.PAM` bez preruseni (teren
  DESERTu od t≈289, jeho objekty vcetne GOOSE nosice uz v t273). Prepis
  konci na `scroll <= 0` napisem LEVEL COMPLETE. Chybi retezeni map podle
  tabulky `0x384c` se slovnikem a paletou dalsiho PAM.
- Scroll originalu se pricita jednou za iteraci hlavni smycky (`0x291e`),
  objekty integruji rychlost × ubehle VBL (`0x62fe`); pri zatezi A500 scroll
  zpomali (64–98 px za 8 s misto 100). Prepis bezi konstantne 50 Hz.
  Rozhodnuti o modelovani zatim otevrene; porovnavani snimku se zarovnava
  podle radku mapy, ne casu.

Dilci: MEDTANK nacasovani/jizda (typ z `+276`), GOOSE kontaktni HP drain
(kod `0xc974`+`0x6566` sedi, chce test s paskou), TRAIN v t145.

## Co uz je vedomo jinde

Starsi seznam odchylek je v `MAPS.md` („Deliberately not rendered")
a tyka se statickych renderu, ne behu hry.
