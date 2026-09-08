#!/usr/bin/env python3
"""Hleda v nahravce z harnessu podpis zvukoveho efektu, ktery strida dve
periody po pevnem poctu IRQ - typicky synth smrti bosse 0x5556.

Okno je jeden stav efektu (0x4ab6 = 3 IRQ pri 204.8 Hz = 14.6 ms), skore je
korelace dominantni frekvence (z prechodu nulou) se stridavym vzorem
+1,-1,+1,-1. Kalibrace: nas vlastni render 0x5556 dava 0.877, nejlepsi
kandidat ve 240 s skutecne hry 0.40 (a ten je na 0-717 Hz, tedy palba).

  python3 tools/survey/sfxfind.py zaznam.wav [t0_zaznamu_v_s]
  python3 tools/survey/sfxfind.py --ref build/sfx-boss/boss-death-SPRAVNE.wav
"""
import array, math, sys, wave

STATE = 3 / 204.8


def windows(path, state=STATE):
    w = wave.open(path)
    sr, ch = w.getframerate(), w.getnchannels()
    n = int(round(state * sr))
    out = []
    while True:
        b = w.readframes(n)
        if len(b) < n * 2 * ch:
            return out, sr
        a = array.array("h")
        a.frombytes(b)
        a = a[::ch]
        ss = sum(v * v for v in a)
        zc = prev = 0
        prev = a[0]
        for v in a:
            if (prev < 0) != (v < 0):
                zc += 1
            prev = v
        out.append((math.sqrt(ss / len(a)) / 32768, zc * sr / (2 * len(a))))


def altscore(wins, i, length):
    seg = [f for _, f in wins[i:i + length]]
    if len(seg) < length:
        return 0.0
    mean = sum(seg) / length
    d = [f - mean for f in seg]
    num = sum(d[k] * (1 if k % 2 == 0 else -1) for k in range(length))
    den = math.sqrt(sum(v * v for v in d) * length) or 1e-9
    return abs(num) / den


def main():
    args = sys.argv[1:]
    ref = args and args[0] == "--ref"
    if ref:
        args = args[1:]
    path = args[0]
    t0 = float(args[1]) if len(args) > 1 else 0.0
    wins, _ = windows(path)
    length = 64                                  # 64 stavu = 0.94 s
    if ref or len(wins) <= length + 2:
        print("referencni skore %.3f  (f %.0f-%.0f Hz, %d oken)" %
              (altscore(wins, 0, min(length, len(wins))),
               min(f for _, f in wins), max(f for _, f in wins), len(wins)))
        return
    bg = sorted(r for r, _ in wins)[len(wins) // 2]
    best = []
    for i in range(len(wins) - length):
        loud = sum(r for r, _ in wins[i:i + length]) / length
        if loud < bg * 1.2:
            continue
        best.append((altscore(wins, i, length), i, loud))
    best.sort(reverse=True)
    print("%s: %.1f s, pozadi RMS %.5f, kandidatu %d" %
          (path, len(wins) * STATE, bg, len(best)))
    for sc, i, loud in best[:6]:
        seg = wins[i:i + length]
        print("   skore %.3f  t %7.2f s  RMS %.4f  f %.0f-%.0f Hz" %
              (sc, t0 + i * STATE, loud,
               min(f for _, f in seg), max(f for _, f in seg)))
    if not best:
        print("   nic nad prahem hlasitosti")


if __name__ == "__main__":
    main()
