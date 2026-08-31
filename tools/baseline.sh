#!/bin/sh
# baseline.sh <prefix> <sekundy...> — deterministicke snimky ORIGINALU
# (SWIVFIX.ADF v headless vAmize, A500 OCS 1MB, KS 1.3, warp ~15x).
#
# Kanonicky ADF bootuje; drivejsi "nenabootuje" bylo cracktro The Company,
# ktere ceka na mys. Pevna vstupni sekvence (emulovane sekundy od zapnuti):
#   t=32  mouse1 press left   ... cracktro pryc
#   t=40  mouse1 press left   ... MEGA TRAINER (defaulty NO = cista hra)
#   t=85  joystick2 press 1   ... fire na kreditove obrazovce = start hry
#   t=86  joystick2 unpress 1
# Uroven TOWN zacina fade-inem ~17 s po fire (viz TOWN-PARITY.md).
#
# <sekundy> se pocitaji OD STISKU FIRE (t=85). Vystup <prefix>_tN.png
# a syrovy <prefix>_tN.raw (RGB24 716x285 vyrez textury emulatoru).
# Emulator je deterministicky: stejny cas = bitove stejny snimek.
set -e
D=$(cd "$(dirname "$0")/.." && pwd)
HL="/Users/mik/claude46/Amiga/reference/tools-bin/VAHeadless"
ROM="/Users/mik/Documents/FS-UAE/Kickstarts/Kickstart v1.3 rev 34.5 (1987)(Commodore)(A500-A1000-A2000-CDTV)[!].rom"
ADF="$D/SWIVFIX.ADF"
PRE="$1"; shift
for t in "$@"; do
  S=$(mktemp -t swivbase).retrosh
  {
    echo "regression setup A500_OCS_1MB \"$ROM\""
    echo "amiga set WARP_MODE ALWAYS"
    echo "regression run \"$ADF\""
    echo "wait 32"
    echo "mouse1 press left"
    echo "wait 8"
    echo "mouse1 press left"
    echo "wait 45"
    echo "joystick2 press 1"
    echo "wait 1"
    echo "joystick2 unpress 1"
    echo "wait $t"
    echo "screenshot save ${PRE}_t$t.png"
  } > "$S"
  "$HL" "$S" >/dev/null 2>&1
  rm -f "$S"
  python3 -c "
from PIL import Image
d = open('${PRE}_t$t.raw', 'rb').read()
Image.frombytes('RGB', (716, 285), d).save('${PRE}_t$t.png')"
done
ls -la ${PRE}_t*.png
