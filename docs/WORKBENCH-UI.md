# Lista ve stylu Workbenche (game.html) - stav pro vydani

Zapsano 2026-10-20 podle zadani uzivatele: hrac vidi jen zakladni nastaveni,
vse anglicky, ladici funkce jen s `?debug`. Lista je ciste prezentace -
nesmi menit simulaci, RNG, kolize, sitovy protokol ani casovani 50 Hz.
Kontrakt: `tools/wbtest.py` (plus `uitest.py`, `smoothtest.py`, `nettest.py`).

## Menu

| Menu (id) | Obsah |
|---|---|
| Project (`mnu-proj`) | Insert disk, Restart zone (R), pozice 1-10 (save / load / delete, S / L), odkaz na repo |
| Display (`mnu-obraz`) | original / enhanced (E), velikost (fit, 2-6x, posuvnik 0-12 v bodech displeje), CRT off / fine / strong, knofliky brightness / contrast / saturation / blur, reset picture, Full screen (F) |
| Game (`mnu-hra`) | start od zony (`#levelbtns button`) |
| Controls (`mnu-ovl`) | gamepad hrace 1 a 2 (`padsel0/1`), zivy stav (`padinfo`), prehled klaves |
| Network (`mnu-sit`) | hra ve dvou po siti (beze zmeny, jen anglicky) |
| Debug (`mnu-dbg`, jen `?debug`) | pul zony zpet/vpred, End sequence (C), zivoty, rychlost scrollu, zbran + / rozptyl, paleta hardware / period monitor, jednotlive efekty vylepseneho rezimu, mereni snimku |

Menu Efekty zmizelo: vylepseny rezim je pro hrace pevna sada vychozich
efektu (hloubka ostrosti plna, mekke stiny, prolnuti scrollu, vlnky, stopy,
podpixelove sprity, rotor jako disk; naklon vrtulniku a hrany spritu
vypnute). Jednotlive prepinace jsou v Debug.

## Klavesy

E original <-> enhanced (CRT, velikost ani knofliky nemeni; v liste se na
2,5 s ukaze rezim), P pauza, S ulozit do dalsi pozice, L seznam pozic,
R restart zony (jen ve hre, ne pri sitove hre), F cela obrazovka, Esc zavre
menu. C (skok na zaverecnou sekvenci) jen s `?debug`. Klavesa O zrusena.
Klavesy se ignoruji pri psani do policek a s modifikatory.

## Knofliky obrazu

CSS `filter` nad platny `#game` a `#title`: `brightness(b%) contrast(c%)
saturate(s%) blur(r)`, rozsahy 50-150 / 50-150 / 0-200 / 0-100.
Rozmazani `r = blur/100 * 0,8 * (sirka platna v CSS px / 320)`, tedy nanejvys
0,8 bodu hry pri kazdem zvetseni; prepocet pri zmene velikosti v renderu.
Pri vychozich hodnotach (100/100/100/0) filtr neni vubec - obraz je bit po
bitu stejny jako drive. Paleta zustava hardware (`n*17`), na ni stoji
kontrakty; prepnuti palety by navic restartovalo zonu (`renderMap` barvi
pri stavbe), knofliky se projevi hned. Puvod: stejne knofliky ma Turrican II
(`Turrican2-claude/web/native.html`).

## Ulozena nastaveni (localStorage, per prohlizec)

| klic | obsah | cte se |
|---|---|---|
| `swivZoom` | 0-12 (bodu displeje, 0 = fit) | vzdy |
| `swivCrt` | `vyp` / `jemne` / `vyrazne` | vzdy |
| `swivMode` | `fx` / `orig` | vzdy |
| `swivPicture` | `{bright, contrast, sat, blur}` | vzdy; reset ho smaze |
| `swivPad0`, `swivPad1` | volba ovladace | vzdy |
| `swivMonitor`, `swivDof`, `swivSprite` | paleta a efekty | jen s `?debug` (hrac ma vychozi) |
| `swiv.save.0..9`, `swiv.save.next` | ulozene pozice | vzdy, format beze zmeny |

Opravena stara chyba: `setMonitorMode("puvodni")` pri startu prepisoval
`swivMonitor` driv, nez se precetl, takze volba palety nikdy neprezila
reload. Ukladani je ted jen v obsluze vyberu.

## Vztah k zadani wb-shell

`amiga-re-kit/WB-SHELL-SWIV.md` (2026-10-20) pocita se sdilenou vrstvou
`wb-shell 1.0` z Turricanu. Uzivatel rozhodl upravit SWIV samostatne a hned.
Odchylky od toho kontraktu: anglicke popisky, bez panelu Efekty a bez volby
palety pro hrace (oboje v Debug), Debug jen s `?debug`, id prvku zustala
puvodni (mapa v zadani §3 plati). Pri pozdejsim prevzeti shellu pozor:
vsechny nastroje SWIV oteviraji `game.html` pres `file://`, kde Chromium
nenacte `<script type="module">` s importem - shell by musel byt vlozen do
souboru, nebo by nastroje musely jit pres lokalni HTTP server.
