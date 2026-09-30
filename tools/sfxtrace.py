#!/usr/bin/env python3
"""Zvukove efekty originalu stav po stavu: zapisy do Paula proti prepisu.

Zvukovy engine SWIV pise periody a hlasitosti primo do registru Paula
(`AUDxPER`, `AUDxVOL`), v 268bajtovych strukturach hlasu nejsou. Porovnani
pres zvuk (korelace nahravky) je proto neostre a nepozna, ktery efekt hraje.
Tenhle skript misto toho zaznamenava v harnessu vAmiga (patch
`tools/vamiga-regtrace.patch`) KAZDY zapis do `AUD0..AUD3` spolu s PC
instrukce, ktera ho provedla:

1. original se proveze hrou jako `tools/survey/zoneshot.py` (palba, kyvani
   doleva/doprava, kazdy snimek smaze bit 3 zamku instalace) az na zadane
   mapove pozice; zapisy se ukladaji do `build/vacmp/sfx/trace_<pozice>.json`;
2. zapisy se rozlozi na instance efektu: instance zacina zapisem `AUDxLCH`
   a PC teto instrukce urcuje rutinu (`0x4d10` = bomba `0x4d08` atd.);
   zapisy `VOL`/`PER` v tomtez IRQ tvori jeden stav, mezera k dalsimu stavu
   je jeho delka v IRQ (CIAB 204.8 Hz = 76,3 radku);
3. kazda instance se porovna s timeline, kterou pro tentyz efekt sklada
   prepis (`sfxBombTimeline()` ...): efektivni hlasitost Paula (bit 6 =
   64), perioda a delka stavu. Instance prerusena jinym efektem se srovna
   jen v delce, kterou stihla.

Efekty s nahodnou periodou (gejzir 0x536e, vybuchy BIGEXPL) se srovnavaji
jen ve strukture (hlasitost, delka, rozsah period). Sumove efekty maji
periodu i hlasitost deterministickou, jejich obsah vlny se tu nesrovnava.

Vysledek 2026-09-30 (zivoty drzene vacmp.LIVES, chipove rozvrzeni):
15 efektu a noty extra zivota, 9 495 instanci, 0 rozdilu - ale ctec mapy
originalu stal od 44189 (zacatek ICE, roztristena pamet), takze to platilo
jen pro TOWN az RIVER. Od zaplaty skenu pameti (vacmp.PATCH_SCAN_JS) jizda
projede az do FINAL; jizda vraci `ctec` a zaznam nese bazi AMPROG.
Casovani IRQ viz docs/SOUND.md: CIAB je jednorazovy, median 78,6 radku.

    python3 tools/sfxtrace.py                       # TOWN..FINAL, zaznam + srovnani
    python3 tools/sfxtrace.py --jen-rozbor          # jen srovnani ulozenych zaznamu
    python3 tools/sfxtrace.py 52000 48788           # vlastni cilove pozice
"""
import base64
import collections
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "survey"))
import vacmp                                        # noqa: E402
from playwright.sync_api import sync_playwright     # noqa: E402

OUT = os.path.join(ROOT, "build", "vacmp", "sfx")
LINES = 313                              # PAL bez prokladu: vpos 0..312
IRQ_NOM = 3464 / 709379 * 3546895 / 227  # radku na jmenovity CIAB IRQ (76,3)
IRQ = 78.6              # zmereny median: casovac je jednorazovy (viz rozbor)

# Jizda je spolecna s ostatnimi nastroji (vacmp.DRIVE_JS, s vyprostenim
# zablokovaneho zavadece); cfg.trace k ni prida zaznam registru Paula.


# Rutiny podle PC zapisu AUDxLCH, ktery instanci zaklada.
EFEKTY = {
    0x4c76: "vzorek BIGEXPL",
    0x4cd6: "vzorek SMART",
    0x4d10: "bomba XEVIOUS 0x4d08",
    0x4d82: "poklop PLAT 0x4d7a",
    0x4e66: "zasah 0x4e5e",
    0x4f58: "palba hrace 0x4f3e",
    0x5016: "stit MINE 0x500e",
    0x508a: "zasah 0x5070",
    0x50e6: "plamen 0x50d0",
    0x515a: "otevreni 0x5138",
    0x52a4: "HOMING 0x528a",
    0x52f0: "BLACKJET 0x52e8",
    0x53da: "kanon 0x53be",
    0x545e: "vejce/paprsek 0x5456",
    0x54d0: "_CORN 0x54c8",
    0x55c4: "ping XEVIOUS 0x55bc",
    0x5376: "gejzir 0x536e",
    0x567a: "nota TOKEN / zivot 0x5672",
}

REF_JS = """() => {
  const T = st => st.map(s => [s.volume, s.period, s.ticks]);
  const voice = { scratch: new Uint8Array(256) };
  return {
    bomba: T(sfxBombTimeline()), poklop: T(sfxHatchTimeline()),
    zasah150: T(sfxGooseHitTimeline(new Uint8Array(256), 150)),
    zasah400: T(sfxGooseHitTimeline(new Uint8Array(256), 400)),
    palba: T(sfxFireTimeline()), stit: T(sfxShieldBubbleTimeline()),
    hit: T(sfxHitTimeline()),
    plamen: T(sfxNoiseTimeline(voice, 'flame-puff').states),
    otevreni2500: T(sfxOpeningTimeline(2500, 50)),
    otevreni2227: T(sfxOpeningTimeline(2227, 90)),
    homing: T(sfxNoiseTimeline(voice, 'homing').states),
    jet: T(sfxNoiseTimeline(voice, 'jet').states),
    kanon: T(sfxNoiseTimeline(voice, 'cannon').states),
    vejce: T(sfxInstShotTimeline(20, 200)),
    paprsek: T(sfxInstShotTimeline(50, 500)),
    corn10000: T(sfxCornTimeline(10000)), corn11000: T(sfxCornTimeline(11000)),
    ping: T(sfxBoltPingTimeline()),
    gejzir: T(sfxGeyserTimeline(0)),
    ...Object.fromEntries([159, 212, 141, 424, 336, 266, 168, 133].map(p =>
      ['nota' + p, T(sfxTokenPickupTimeline(p))])),
  };
}"""


def eff(v):
    return 64 if v & 0x40 else v & 0x3f


def zaznam(targets):
    os.makedirs(OUT, exist_ok=True)
    srv, port = vacmp.serve(os.path.join(ROOT, "web"))
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(); page = br.new_page()
            page.set_default_timeout(3_600_000)
            page.goto(f"http://127.0.0.1:{port}/vacmp.html")
            page.wait_for_function("window.VA && window.VA.ready", timeout=60000)
            page.evaluate("([r, a]) => VA.boot(r, a)", [
                base64.b64encode(open(vacmp.ROM, "rb").read()).decode(),
                base64.b64encode(open(vacmp.ADF, "rb").read()).decode()])
            vacmp.prolog(page)
            for t in targets:
                r = page.evaluate(vacmp.DRIVE_JS, {"od": t, "limit": 120000,
                                                   "trace": True})
                # PC zapisu jsou absolutni; AMPROG lezi podle rozvrzeni jinde
                json.dump({"prog": r["prog"], "zapisy": r["out"]},
                          open(os.path.join(OUT, f"trace_{t}.json"), "w"))
                zas = "  ZASEKNUTO" if r["pos"] > t else ""
                print(f"  original: pozice {r['pos']} (cil {t}), {r['k']} snimku, "
                      f"{len(r['out'])} zapisu, vyprosteni {r['vyprosteni']}{zas}",
                      flush=True)
            br.close()
    finally:
        srv.shutdown()


def nacti_trace(cesta):
    """Vrati (zapisy, baze AMPROG); stary format byl jen seznam (chip 0xEFC0)."""
    d = json.load(open(cesta))
    if isinstance(d, dict):
        return d["zapisy"], d["prog"]
    return d, 0xEFC0


def instance(trace, prog):
    """Rozlozi zapisy na instance: start = AUDxLCH, dal VOL/PER/LEN kanalu."""
    otevrene, out, prev = {}, [], 0
    for k, vpos, hpos, reg, val, pc in trace:
        if not 0xa0 <= reg < 0xe0:
            continue
        pc -= prog
        ch, r = (reg - 0xa0) >> 4, reg & 0xf
        t = k * LINES + vpos + hpos / 227.0
        if t < prev - 50:        # zapis na prelomu snimku hlaseny s vpos 0
            t += LINES           # a jeste starym cislem kroku
        prev = t
        if r == 0:
            cur = {"ch": ch, "pc": pc, "t0": t, "w": []}
            otevrene[ch] = cur; out.append(cur)
        elif r in (4, 6, 8) and ch in otevrene:
            otevrene[ch]["w"].append((t, r, val, pc))
    return out


CLEANUP = 0x4c00         # 0x4bf2: AUDxVOL = 0, pak uz jen yield


def stavy(inst):
    """Skupiny VOL/PER ve stejnem IRQ -> [(vol, per, delka)]; konci cleanupem."""
    skup, vol, per, cleanup = [], None, None, False
    for t, r, v, pc in inst["w"]:
        if r == 4:
            continue
        if pc == CLEANUP:
            if skup:
                skup[-1].append(t)
            cleanup = True
            break
        if not (skup and t - skup[-1][0] < IRQ * 0.5):
            skup.append([t, vol, per])
        g = skup[-1]
        if r == 8:
            g[1] = vol = v
        else:
            g[2] = per = v
    res = []
    for i, g in enumerate(skup):
        konec = skup[i + 1][0] if i + 1 < len(skup) else (g[3] if len(g) > 3 else None)
        d = None if konec is None else round((konec - g[0]) / IRQ)
        if d != 0:               # zapis tesne pred cleanupem (_CORN 0x552e) nezni
            res.append([g[1], g[2], d])
    return res, cleanup


def vyber_ref(pc, st, ref):
    if not st or st[0][1] is None:
        return None
    p0 = st[0][1]
    return {
        0x4d10: "bomba", 0x4d82: "poklop", 0x4f58: "palba", 0x5016: "stit",
        0x508a: "hit", 0x50e6: "plamen", 0x52a4: "homing", 0x52f0: "jet",
        0x53da: "kanon", 0x55c4: "ping",
        0x4e66: "zasah150" if p0 == 150 else "zasah400",
        0x515a: "otevreni2500" if p0 == 10000 else "otevreni2227",
        0x545e: "vejce" if p0 == 220 else "paprsek",
        0x54d0: "corn10000" if p0 == 10000 else "corn11000",
        0x5376: "gejzir", 0x567a: "nota%d" % p0,
    }.get(pc)


def slouc(st):
    """Sousedni stavy se stejnou hlasitosti i periodou zni jako jeden."""
    out = []
    for v, p, d in st:
        if out and eff(out[-1][0]) == eff(v) and out[-1][1] & 0xffff == p & 0xffff:
            out[-1][2] = None if d is None or out[-1][2] is None else out[-1][2] + d
        else:
            out.append([v, p & 0xffff, d])
    return out


def porovnej(st, cleanup, refst, nahodna=False):
    """Vrati (shodnych stavu, prvni rozdil nebo None). U nahodne periody
    (gejzir: 127 + RNG & 127 za stav) se perioda jen overi v rozsahu."""
    if nahodna:
        st = [[v, 0 if 127 <= p <= 254 else p, d] for v, p, d in st]
        refst = [[v, 0, d] for v, p, d in refst]
    st, refst = slouc(st), slouc(refst)
    n = min(len(st), len(refst))
    for i in range(n):
        v, p, d = st[i]
        rv, rp, rd = refst[i]
        last = i == len(st) - 1
        # Jednorazovy CIAB se pod zatezi opozdi (interval 78,2 az 84 radku
        # proti medianu 78,6): dlouhy stav (drzeni otevreni 90 IRQ) smi
        # ujet o 4 %.
        if eff(v) != eff(rv) or p != rp or (d is not None and abs(d - rd) > rd * 4 // 100 and
                                            not (last and not cleanup)):
            return i, (i, (eff(v), p, d), (eff(rv), rp, rd))
    if cleanup and len(st) != len(refst):
        return n, (n, "orig %d stavu" % len(st), "prepis %d stavu" % len(refst))
    return n, None


def rozbor(soubory, ref):
    celkem = collections.defaultdict(lambda: [0, 0, 0, None])
    vzorky = collections.defaultdict(collections.Counter)
    for f in soubory:
        tr, prog = nacti_trace(f)
        for ins in instance(tr, prog):
            st, cleanup = stavy(ins)
            if ins["pc"] in (0x4c76, 0x4cd6):
                if st:
                    ln = next((v for _, r, v, _ in ins["w"] if r == 4), None)
                    vzorky[ins["pc"]][(st[0][1], ln)] += 1
                continue
            key = vyber_ref(ins["pc"], st, ref)
            if key is None or not st:
                continue
            if key not in ref:
                print("  neznama nota/efekt %s" % key); continue
            _, chyba = porovnej(st, cleanup, ref[key], key == "gejzir")
            c = celkem[key]
            c[0] += 1
            if cleanup:
                c[1] += 1
            if chyba:
                c[2] += 1
                if c[3] is None:
                    c[3] = (os.path.basename(f), chyba)
    spatne = 0
    print("\nefekt            instanci  uplnych  rozdilnych")
    for key, (n, upl, chyb, prvni) in sorted(celkem.items()):
        print(f"  {key:15s} {n:8d} {upl:8d} {chyb:10d}")
        if prvni:
            spatne += chyb
            print(f"      prvni rozdil ({prvni[0]}): stav {prvni[1][0]}: "
                  f"original {prvni[1][1]}, prepis {prvni[1][2]}")
    for pc, c in vzorky.items():
        print(f"\n{EFEKTY[pc]}: (perioda, AUDLEN) -> pocet")
        print("   ", ", ".join(f"{p}/{ln}: {k}" for (p, ln), k in sorted(c.items())))
    chybi = sorted(set(k for k in ref) - set(celkem))
    if chybi:
        print("\nv zaznamu nezaznely:", ", ".join(chybi))
    return spatne


def main():
    args = sys.argv[1:]
    if "--jen-rozbor" not in args:
        targets = [int(a) for a in args if a.isdigit()] or [52000, 48788, 45488, 42000, 37000, 32995]
        zaznam(targets)
    with sync_playwright() as pw:
        b = pw.chromium.launch(); p = b.new_page()
        p.goto("file://" + os.path.join(ROOT, "game.html"))
        ref = p.evaluate(REF_JS)
        b.close()
    soubory = sorted(glob.glob(os.path.join(OUT, "trace_*.json")))
    spatne = rozbor(soubory, ref)
    print("\nSFXTRACE OK" if not spatne else f"\nSFXTRACE: {spatne} instanci s rozdilem")
    sys.exit(1 if spatne else 0)


if __name__ == "__main__":
    main()
