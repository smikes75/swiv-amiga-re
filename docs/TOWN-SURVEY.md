# Pruchod celym TOWN vedle originalu (2026-09-03)

Cil: seznam viditelnych rozdilu za cely level, ne presnost na pixel.
Metoda: original v headless vAmize s trainerem F1 (neomezene zivoty), snimek
kazdych 8 s od fire (t17..t321, 40 behu), prepis odsimulovany bez vstupu se
stejnymi zivoty a porovnany ve **stejnem radku mapy** (radek originalu se
meri korelaci s renderem mapy, viz nize). Recept: `tools/survey/README.md`,
snimky a dvojice v `build/survey/`.

## Systemove nalezy

1. **Zony na sebe navazuji bez prerusni.** Od t≈289 sedi teren originalu na
   mapu DESERT (t297 78 %, t321 89 %), TOWN klesa na 60 %. Objekty DESERTu
   (nosic GOOSE#0 17×55 se slétajicimi dily, TILT, MEDTANK) jsou videt uz v
   t273 nad poslednim terenem TOWN, protoze ctecka mapy `0x365e` bezi 256 px
   pred oknem a po konci `TOWN.PAM` (`D == 0` → `st fp@(167)`, ctecka
   `0x35a2` skonci) pokracuje dalsim souborem z tabulky urovni `0x384c`.
   Smycka urovne `0x1db4` konci jen kdyz zadny hrac neni ve hre (`0x27de`),
   ne koncem mapy. **Prepis konci na `scroll <= 0` napisem LEVEL COMPLETE** —
   to v originale neexistuje. Napravou je retezeni map (TOWN → DESERT →
   GRASS → RIVER → ICE → SCIFI → FINAL) se slovnikem a paletou podle PAM.
   Domnenka „velka lod se sklada nekolikrat za level" je timto vysvetlena:
   druhy GOOSE v „TOWN" je prvni GOOSE DESERTu (DESERT.PAM ma 4× GOOSE#0).
2. **Scroll originalu neni konstantni.** Radky zmerene korelaci: t17 3198,
   t25 3101, t33 2999, t41 2901, t49 2803, t57 2706, t65 2608, t73 2528,
   t81 2448, t89 2351, t97 2255, t105 2157, t113 2059, t121 1957, t129 1859,
   t137 1766, t145 1668, t153 1570, t161 1468, t169 1370, t177 1275,
   t185 1184, t193 1098, t201 1001, t209 898, t217 800, t225 704, t233 640,
   t241 577, t249 476, t257 378, t265 283, t273 212. Bezny usek = 98 px za
   8 s (12.25 px/s), akcni useky (smrti, boss, hodne objektu) 64–80 px.
   Scroll se pricita jednou za iteraci hlavni smycky (`0x291e`: word
   `fp@(3542)` := `fp@(3530)` a `0x5f0a`), zatimco objekty integruji
   rychlost × pocet ubehlych VBL (`0x62fe`, `d7 = fp@(-76)`). A500 tedy pri
   zatezi zpomali scroll, ne pohyb objektu. Prepis bezi na pevnych 50 Hz:
   cely TOWN je o ~10 % kratsi a nabite sceny „rychlejsi". Rozhodnuti:
   pro rezim „vylepseno" je konstantni 50 Hz zamer; pro rezim „original" by
   bylo treba modelovat cenu snimku, coz presne nejde — zatim
   nedelame, jen dokumentujeme. Pro porovnavani snimku se vzdy zarovnava
   podle radku, ne podle casu.
3. **Kazdy zachyt je jiny beh.** RNG originalu je hardwarove (`VHPOSR`), vlny
   FODDERA lezi v kazdem behu jinde a smrti hrace se lisi. Rozdily v RNG
   objektech se proto nehodnoti.

## Objekty a chovani (co sedi a co ne)

Sedi: teren ve vsech 33 dvojicich (88–97 % mimo objekty), HUD, mapove
objekty na svych radcich (POPUP, FLAME, MINE, PROXMINE, CAMOGUN, ROTOBASE,
BIRD = cerne delty, MILL), exploze smrti, bily respawn, zive ploty a
pyramida na konci.

Nesedi nebo neoverene:

- ~~**MEDTANK**~~ — **sedi** (zabery po 1 s t34..t56, dvojice zarovnane
  na radek): typ-1 tank jede od x 352 na zapad shodne v obou (t36 (200,70)
  vs (202,74), t40 (120,125) vs (118,125), t42 (60,155) vs (66,151), v t48
  uz mimo obraz), typ-3 tank (165, 154→242) i plamenomet (95, 150) rovnez.
  Dřívější „rozdil" z 8s prochodu byl spatne prectený terenni blob
  26×24 px na x 306 a jiný beh (RNG smrti).
- ~~**GOOSE**~~ — **vyreseno tyz den**: prepis respawnoval hrace presne
  pod bossem a chraneny hrac mu kontaktem (0xc974 −1 HP za VBL, handler
  i pro bit 3 pres `0x6566`) sebral 25 HP za 25 VBL. Original tak nedela,
  protoze sonda respawnu `0x3dd4` testuje masku proti OBRAZOVCE vcetne
  BOBu, hrac se rodi o sloupec/radek dal a boss ztraci HP jen pri
  skutecnem doteku (2s zabery t275..t297). Prepis ted sklada BOBy do
  sondy (`respawnBobField`); zbytek je zavisly na historii (v simulaci
  prezije boss 3–4 cykly misto jednoho). Druhy mechanismus originalu se
  nemodeluje: novy task hrace se alokuje blokujicim `0x6162` (yield kazdy
  VBL, dokud loaderovy alokator `fp@(-1502)` nevyda 546 B), takze pri
  plne pameti (boss + casti + exploze) se respawn zpozdi — v baseline
  t281→t287 o ~4 s. Alokator lezi v loaderu, jeho heap a obsazeni grafikou
  nejsou v `AMPROG.OBJ`; bez emulace pameti to presne nejde.
- **TRAIN**: t145 original bez vlaku, prepis dva vlaky mimo obraz; t137 oba
  s vlakem. Neprukazne.
- Mala staticka odchylka terenu 26×24 px na mape (293..319, 3029..3053),
  zrejme dekal; nizka priorita.

## Co delat dal (poradi)

1. ~~Retezeni map (bod 1)~~ — hotovo tyz den (`parseMapChain`, viz
   GAPS 9); dvojice t273..t321 sedi na teren DESERTu i jeho prvni objekty.
2. ~~Zachyt tanku po 1 s a oprava MEDTANK~~ — sedi, nic k oprave.
3. Vrstva vylepseni (interpolace poloh mezi tiky, subpixelovy scroll, volba
   50/60/120 Hz, skalovani), prepinac original/vylepseno.
4. Rozhodnout, zda modelovat zpomaleni scrollu pri zatezi.
