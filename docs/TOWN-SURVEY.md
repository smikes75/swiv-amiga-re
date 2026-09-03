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

- **MEDTANK**: prvni tank (zaznam img 3039, x 305, typ 1) v prepisu jede od
  x 352 na zapad (t33 x 238, t41 x 92, t49 x −54). Original v t33 na tomto
  radku tank nema, v t41 ma tank na (91,126) jako prepis, v t49 ma tank na
  (169,126), ktery v prepisu chybi. Kinematika/nacasovani tanku se lisi;
  chce zachyt po 1 s v t33..t57 a precist `0x9eca` znovu (typ z `+276`).
- **GOOSE**: v tomto behu prepis bosse zabil kontaktem chraneneho
  respawnuteho hrace (0xc974 ubira 1 HP za kazdy VBL dotyku, handler je
  nainstalovan i pro bit 3 pres `0x6566`), original prezil do timeoutu 2000
  VBL, protoze jeho hrac pod bossem nikdy nebyl (stred tela vs. hrac
  dy ≥ 20 > box 19). Kod sedi, ale stoji za cileny test s paskou joysticku
  (hrac drzeny pod bossem).
- **TRAIN**: t145 original bez vlaku, prepis dva vlaky mimo obraz; t137 oba
  s vlakem. Neprukazne.
- Mala staticka odchylka terenu 26×24 px na mape (293..319, 3029..3053),
  zrejme dekal; nizka priorita.

## Co delat dal (poradi)

1. Retezeni map (bod 1) — nejvetsi viditelny strukturalni rozdil a nutna
   podminka pro „hrat jako original".
2. Zachyt tanku po 1 s a oprava MEDTANK.
3. Vrstva vylepseni (interpolace poloh mezi tiky, subpixelovy scroll, volba
   50/60/120 Hz, skalovani), prepinac original/vylepseno.
4. Rozhodnout, zda modelovat zpomaleni scrollu pri zatezi.
