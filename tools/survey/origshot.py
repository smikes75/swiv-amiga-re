#!/usr/bin/env python3
"""origshot.py - jeden snimek ORIGINALU v case T sekund od stisku FIRE.

Doplnek tools/baseline.sh pro dlouha mereni: sekvence je stejna, ale
volitelne zapne trainer F1 (unlimited lives) a hlavne se hodi spoustet
paralelne (jeden beh = jeden snimek).

Zjisteno pri M-mereni scroll locku (2026-09-06), prevzato z postupu
projektu Turrican (tools/shot.py):
  - `screenshot save` emulator UKONCI, takze vic snimku v jednom skriptu
    nefunguje: jeden beh = jeden cas;
  - "std::exception" u prikazu `wait` je kosmeticke, ceka se spravne;
  - `denise set FRAME_SKIPPING 0` je nutne, jinak Denise ve warpu prehazuje
    buffery jen kazdy 17. snimek a textura je az o 16 snimku starsi nez
    zadany cas. **Vychozi je zde vypnuto**, aby snimky zustaly srovnatelne
    s cache tools/compare.py (viz docs/GAPS.md).

    python3 tools/survey/origshot.py 600 build/x_t600.png [--lives] [--noskip]
"""
import os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HL = "/Users/mik/claude46/Amiga/reference/tools-bin/VAHeadless"
ROM = ("/Users/mik/Documents/FS-UAE/Kickstarts/"
       "Kickstart v1.3 rev 34.5 (1987)(Commodore)(A500-A1000-A2000-CDTV)[!].rom")
ADF = os.path.join(ROOT, "SWIVFIX.ADF")


def shoot(t, out, lives=False, frame_skipping_off=False):
    lines = [f'regression setup A500_OCS_1MB "{ROM}"', 'amiga set WARP_MODE ALWAYS']
    if frame_skipping_off:
        lines.append('denise set FRAME_SKIPPING 0')
    lines += [f'regression run "{ADF}"', 'wait 32', 'mouse1 press left', 'wait 8']
    if lives:                                   # F1 = UNLIMITED LIVES
        lines += ['keyboard press 80', 'wait 1', 'mouse1 press left', 'wait 44']
    else:
        lines += ['mouse1 press left', 'wait 45']
    lines += ['joystick2 press 1', 'wait 1', 'joystick2 unpress 1',
              f'wait {t}', f'screenshot save {out}']
    fd, path = tempfile.mkstemp(suffix='.retrosh')
    os.write(fd, ('\n'.join(lines) + '\n').encode()); os.close(fd)
    try:
        subprocess.run([HL, path], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=3600)
    finally:
        os.unlink(path)
    raw = out[:-4] + '.raw'
    if not os.path.exists(raw):
        return False
    from PIL import Image
    Image.frombytes('RGB', (716, 285), open(raw, 'rb').read()).save(out)
    return True


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    ok = shoot(int(a[0]), os.path.abspath(a[1]),
               lives='--lives' in sys.argv, frame_skipping_off='--noskip' in sys.argv)
    print('ok' if ok else 'CHYBI', a[0])
