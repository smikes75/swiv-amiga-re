#!/bin/sh
# build-wasm.sh - preklad jadra vAmiga (master, viz VAMIGA_REF) do WebAssembly
# s patchi projektu. Vysledek: web/vamiga.js + web/vamiga.wasm (ignorovane).
#
# Prevzato 2026-09-06 z projektu Turrican (../Turrican-projekt), kde vzniklo
# a je zmerene (docs/WEB.md tamtez). Jadro je herne agnosticke: bere Kickstart
# a ADF z pameti. Licence tretich stran viz docs/LICENSES.md.
# Potrebuje emcc (brew install emscripten) a cmake.
#   tools/build-wasm.sh [cesta k existujicim zdrojum jadra]
set -e
D=$(cd "$(dirname "$0")/.." && pwd)
SRC=${1:-$D/build/vamiga-src}
VAMIGA_REF=c59425d   # vAmiga 5.0b2 (2026-09-01), stejny zdroj jako build/bin/VAHeadless; patche sedi na tento commit
if [ ! -d "$SRC/Core" ]; then
  git init -q "$SRC"
  # GitHub nedovoluje melky fetch libovolneho SHA (uploadpack.allowReachableSHA1InWant
  # je vypnuty), takze pri neuspechu stahujeme cely repozitar a checkoutujeme commit.
  if git -C "$SRC" fetch --depth 1 https://github.com/dirkwhoffmann/vAmiga.git "$VAMIGA_REF" 2>/dev/null; then
    git -C "$SRC" checkout -q FETCH_HEAD
  else
    git -C "$SRC" remote add origin https://github.com/dirkwhoffmann/vAmiga.git 2>/dev/null || true
    git -C "$SRC" fetch -q origin
    git -C "$SRC" checkout -q "$VAMIGA_REF"
  fi
  git -C "$SRC" apply "$D/tools/vamiga-headless.patch"
  git -C "$SRC" apply "$D/tools/vamiga-wasm.patch"
fi
grep -q stepFrame "$SRC/Core/Infrastructure/Emulator.h" || git -C "$SRC" apply "$D/tools/vamiga-wasm.patch"
emcmake cmake -S "$D/web" -B "$D/build/wasm" -DVAMIGA_CORE="$SRC/Core" -DCMAKE_BUILD_TYPE=Release
cmake --build "$D/build/wasm" --target vamiga -j8
cp "$D/build/wasm/vamiga.js" "$D/build/wasm/vamiga.wasm" "$D/web/"
ls -la "$D/web/vamiga.js" "$D/web/vamiga.wasm"
