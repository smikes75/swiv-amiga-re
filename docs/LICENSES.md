# Licence tretich stran

Vlastni kod projektu (`game.html`, tools/, docs/) je dilo autora projektu.
Slozka `web/` a soubory `tools/build-wasm.sh`, `tools/vamiga-headless.patch`
a `tools/vamiga-wasm.patch` byly 2026-09-06 prevzaty z projektu Turrican
(`../Turrican-projekt`), kde vznikly a jsou zmerene. Pouzite cizi casti:

| cast | licence | jak pouzito |
|---|---|---|
| vAmiga - jadro emulatoru (`Core/`), Dirk W. Hoffmann, commit c59425d (5.0b2) | MPL-2.0 | prelozeno do `build/bin/VAHeadless` a `web/vamiga.wasm`; upravy souboru jadra jsou v `tools/vamiga-headless.patch` a `tools/vamiga-wasm.patch` (MPL vyzaduje zpristupnit zdroj upravenych souboru - splneno) |
| vAmiga - CPU Moira (`Core/CPU/Moira`) | MIT | soucast jadra |
| vAmiga - aplikace (GUI macOS) | GPL-3.0 | nepouzito |
| zlib | zlib | `-sUSE_ZLIB=1` (snapshoty jadra) |
| Emscripten | MIT / NCSA | prekladac do WebAssembly, runtime v `vamiga.js` |
| Playwright, Pillow | Apache-2.0, MIT-CMU | jen testy a nastroje |

Nic z herniho disku (Turrican II, Rainbow Arts / Factor 5) ani z Kickstartu
(Amiga / Cloanto) neni v repozitari; uzivatel pouziva vlastni kopie (cesty v
`local.conf`, symlinky `web/local/`, oboji ignorovane gitem). Patche hry se
delaji jen v RAM emulatoru, nikdy do obrazu disku.
