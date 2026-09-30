#!/usr/bin/env python3
"""vacmp.py - original SWIVu ve WebAssembly (vAmiga) v prohlizeci.

Prvni krok srovnavaciho harnessu: jadro z web/vamiga.js se nabootuje se
SWIVFIX.ADF a Kickstartem, projede kanonickou vstupni sekvenci (stejnou jako
tools/baseline.sh) a v zadanem case ulozi snimek. Slouzi k overeni, ze beh
v prohlizeci je totozny s VAHeadless, a pozdeji ke cteni stavu hry z pameti
(VA.mem: chip i slow RAM; hra po zaplate skenu fixu lezi ve slow RAM, viz
PATCH_SCAN_JS a docs/LOADER.md).

    python3 tools/survey/vacmp.py 17 build/x_t17.raw

Sekvence (emulovane sekundy od zapnuti, 50 snimku = 1 s):
    32  mouse1 press left      pryc z cracktra
    40  mouse1 press left      MEGA TRAINER (vychozi volby = cista hra)
    85  joystick2 press 1      fire na kreditove obrazovce
    86  joystick2 unpress 1
Harness je **deterministicky** (dva behy daji tentyz obsah chip RAM i tentyz
pocet zvukovych vzorku), ale **neni snimek po snimku shodny s VAHeadless**:
vstup jde jinou cestou a hra ma RNG michany hodnotou VHPOSR z audio
preruseni, takze se behy brzy rozejdou. Harness proto slouzi jako **vlastni
reference** (obraz, chip RAM i zvuk z jednoho behu), ne jako nahrada
tools/baseline.sh.
"""
import base64
import functools
import http.server
import os
import socketserver
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def je_kick13(cesta):
    """256 kB, hlavicka 0x11114EF9 a verze 34 revize 5 na offsetu 12.

    Ve sbirce lezi vedle sebe overeny dump `[!]`, spatne `[b]`, overdumpy
    `[o]` (512 kB) i zasifrovane varianty, ktere by emulator nenabootoval.
    Kontroluje se proto obsah, ne jmeno."""
    try:
        with open(cesta, "rb") as f:
            d = f.read(16)
        if len(d) < 16 or d[:4] != b"\x11\x11\x4e\xf9":
            return False
        if int.from_bytes(d[12:14], "big") != 34:       # verze 1.3
            return False
        return os.path.getsize(cesta) == 262144
    except OSError:
        return False


def _najdi_rom():
    """Kickstart 1.3. Hleda se UVNITR projektu, protoze do ~/Documents
    proces v sandboxu nesmi (`Operation not permitted`) - a ROM do repa
    nepatri stejne jako disketa (`.gitignore`)."""
    env = os.environ.get("SWIV_KICKSTART")
    if env:
        return env
    # Sbirka `Kickstarts/` v projektu: vezmi overeny dump, jinak kterykoli
    # soubor, ktery projde kontrolou obsahu.
    sbirka = os.path.join(ROOT, "Kickstarts")
    if os.path.isdir(sbirka):
        jmena = sorted(os.listdir(sbirka))
        prednost = [j for j in jmena if "1.3" in j and "A500" in j and "[!]" in j]
        for j in prednost + jmena:
            cesta = os.path.join(sbirka, j)
            if je_kick13(cesta):
                return cesta
    kandidati = ["kick13.rom", "KICK13.ROM", "kickstart13.rom",
                 "Kickstart v1.3 rev 34.5 (1987)(Commodore)"
                 "(A500-A1000-A2000-CDTV)[!].rom"]
    def da_se_cist(cesta):
        # POZOR: `os.path.exists` na ~/Documents vraci True i tam, kde pak
        # cteni spadne na "Operation not permitted" - musi se zkusit otevrit.
        try:
            with open(cesta, "rb") as f:
                return len(f.read(4)) == 4
        except OSError:
            return False

    for jm in kandidati:
        cesta = os.path.join(ROOT, jm)
        if da_se_cist(cesta):
            return cesta
    # Puvodni misto ve sbirce FS-UAE - jen kdyz je opravdu citelne.
    fsuae = os.path.expanduser(
        "~/Documents/FS-UAE/Kickstarts/Kickstart v1.3 rev 34.5 (1987)"
        "(Commodore)(A500-A1000-A2000-CDTV)[!].rom")
    if da_se_cist(fsuae):
        return fsuae
    return os.path.join(ROOT, kandidati[0])          # sem ho polozit


ROM = _najdi_rom()
ADF = os.path.join(ROOT, "SWIVFIX.ADF")
FPS = 50                                        # PAL

# (sekunda od zapnuti, prikaz RetroShellu)
# Vstup se posila PRIMO pres GamePadAction (wasm_mouse/wasm_joystick), ne
# prikazem RetroShellu: retezce typu "mouse1 press left" se v tomto rezimu
# neprojevily a hra zustala viset na cracktru (zmereno 2026-09-07 - snimek
# v case 25 s po "fire" porad ukazoval text cracku).
#   (sekunda od zapnuti, ('mouse'|'joy'), port, akce stisk, akce uvolneni)
SEQUENCE = [(32, "mouse", 1, 7, 16),    # pryc z cracktra
            (40, "mouse", 1, 7, 16),    # MEGA TRAINER (vychozi volby)
            (85, "joy", 2, 4, 13)]      # fire na kreditove obrazovce
ZERO_AT = 85                            # cas na radce se pocita od fire
HOLD = 4                                # snimku mezi stiskem a uvolnenim


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve(root):
    """WebAssembly se z file:// nenacte (CORS), takze web/ servirujeme lokalne."""
    handler = functools.partial(_Quiet, directory=root)
    srv = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def playSequence(page, target):
    """Odsimuluje vstupni sekvenci az do `target` sekund od zapnuti."""
    now = 0
    for sec, dev, port, down, up in SEQUENCE:
        if sec > target:
            break
        if sec > now:
            page.evaluate("n => VA.run(n, null)", (sec - now) * FPS)
            now = sec
        page.evaluate("([d, p, a]) => (d === 'mouse' ? VA.fn.mouse : VA.fn.joy)(p, a)",
                      [dev, port, down])
        page.evaluate("n => VA.run(n, null)", HOLD)
        page.evaluate("([d, p, a]) => (d === 'mouse' ? VA.fn.mouse : VA.fn.joy)(p, a)",
                      [dev, port, up])
    return now


# Vstup do skutecne hry pres MEGA TRAINER: F1 nekonecne zivoty, F3 ponechani
# zbrani, F4 super zbrane (wasm_key, surove kody Amigy). Overeno snimkem -
# volby se prepnou na YES. Palba se musi pulzovat; drzene PRESS_FIRE hru
# nestrili. Pozor: pulzovana palba behem continue okna hned vhodi kredit a
# resetuje skore, takze "skore = 0" neznamena, ze hrac ve hre neni.
TRAINER_KEYS = (0x50, 0x52, 0x53)          # F1, F3, F4
JOY_UP, JOY_FIRE, JOY_RELEASE_FIRE = 0, 4, 13

# Rozvrzeni pameti: fix wrapper (N.O.M.A.D) ma v skenu pameti chybu (mez
# 0x80000 na 0x5019a), takze zavadec dostane jen 512 kB chip RAM a hra se
# pri delsi jizde zablokuje na roztristene pameti (RIVER 46159, docs/GAPS.md).
# Prolog proto sken zaplatuje (VA.patchFixScan): hra pak lezi ve slow RAM
# (A6 0xC016DC, AMPROG 0xC0A4C0 - presne kam miri trainer fixu) a chip RAM
# zustava grafice. SWIV_HARNESS_512K=1 zaplatu vypne (stare rozvrzeni
# A6 0x17DC, AMPROG 0xEFC0).
PATCH_SCAN_JS = ("" if os.environ.get("SWIV_HARNESS_512K")
                 else "VA.run(10*50, null); window.__scanPatched = VA.patchFixScan();")
PLAY_PROLOGUE = """() => {
  %s
  while (VA.frames < 32*50) VA.run(1, null);
  VA.fn.mouse(1,7); VA.run(4,null); VA.fn.mouse(1,16);
  VA.run(8*50, null);
  const key = c => { VA.fn.key(c,1); VA.run(6,null);
                     VA.fn.key(c,0); VA.run(6,null); };
  for (const c of %s) key(c);
  VA.run(25,null); VA.fn.mouse(1,7); VA.run(4,null); VA.fn.mouse(1,16);
  VA.run(37*50, null);
  VA.fn.joy(2,4); VA.run(4,null); VA.fn.joy(2,13); VA.run(3*50,null);
  window.playFor = sec => { for (let i = 0; i < sec*50/10; i++) {
    VA.fn.joy(2,4); VA.run(5,null); VA.fn.joy(2,13); VA.run(5,null); } };
}""" % (PATCH_SCAN_JS, list(TRAINER_KEYS))


def prolog(page):
    """Projede uvod do hry (PLAY_PROLOGUE) a zjisti rozvrzeni pameti."""
    page.evaluate(PLAY_PROLOGUE)
    return rozvrzeni(page)


def rozvrzeni(page):
    """Najde zavadec a AMPROG (VA.layout) a nastavi A6_BASE/PROG_BASE modulu,
    aby nastroje, ktere je ctou az za behu, dostaly skutecne hodnoty."""
    global A6_BASE, PROG_BASE
    lay = page.evaluate("() => VA.layout()")
    if not lay:
        raise RuntimeError("zavadec hry v pameti nenalezen")
    A6_BASE, PROG_BASE = lay["a6"], lay["prog"]
    return lay


def mark():
    """Marker +534 ulohy po a2c6 (spodni slovo navratove adresy 0xa36a)."""
    return (0xa36a + PROG_BASE) & 0xffff


# --- baze A6 a AMPROG.OBJ v chip RAM (zmereno 2026-09-08) ------------------
# A6 je bazovy registr globalu (fp@(N)) i skokove tabulky na zapornych
# offsetech; nastavuje jej zavadec jeste pred vstupem do AMPROG.OBJ (0xc72
# uz ho prvni instrukci pouziva), takze v disassembly neni videt.
#
# Zmereno takto: fp@(3530) je mapova pozice 16.16, kterou scroll task 0x3cd4
# snizuje presne o fp@(3526) = 0x4000 za VBL. Dva otisky chip RAM N snimku od
# sebe -> hledej longy, ktere klesly o N*0x4000, a filtruj tim, ze long tesne
# pred nimi je 0x4000. Zbyde jedina adresa; A6 = ta adresa - 3530.
# Baze AMPROG.OBJ se najde podle bajtu rutiny 0x5556 (61 00 f5 88 41 ed ...).
#
# Overeno dvema behy s ruznou delkou hry: obe daly stejne hodnoty.
# Vychozi hodnoty plati pro chip rozvrzeni (bez zaplaty skenu); `prolog`
# a `nacti_stav` je prepisou podle skutecneho stavu (VA.layout).
A6_BASE = 0x17DC          # 6108
PROG_BASE = 0xEFC0        # 61376
# Zivoty slotu 1: slovo +68 struktury fp@(11176) drzi -4 x zivoty (0x70a0
# pricte fp@(12524) = 4 za kazdy spawn, 0x711e ubere 4 za extra zivot).
# Jizdy harnessem ho kazdy snimek prepisuji na -40, jinak hrac bez rucniho
# hrani v RIVERu a ICE prijde o vsechny zivoty a mapa stoji na konci hry
# (drive mylne hlaseno jako "zamek ICE" a "zaseknuti RIVERu na 46159";
# F1 MEGA TRAINERU tomu nezabrani). Zmereno 2026-09-29: s timto drzenim
# originál dojede TOWN -> FINAL (32995) za 124 000 snimku.
LIVES = 11176 + 68
# Kusy JS pro jizdy: ocekavaji `m = VA.mem()` a `A6` v rozsahu.
KEEP_LIVES_JS = "m.w16(A6 + %d, 0xffd8);" % LIVES
# Sila zbrane: slovo +102 slotu = pocet sebranych TOKENu (0x70d6 deli peti
# a vybira radek tabulky 0x70c0). Bez silne zbrane bezobsluzna jizda nechava
# naziva prilis mnoho nepratel, jejich grafika zaplni pamet zavadece a ctec
# mapy (fp@(3586)) nebo stavitel terenu se zablokuje (viz DRIVE_JS).
WEAPON = 11176 + 102
KEEP_WEAPON_JS = "m.w16(A6 + %d, 15);" % WEAPON

# Jizda originalem (TOWN -> FINAL). Pri bezobsluzne jizde se muze v RIVERu
# na 46159 zablokovat zavadec: sest POPUPu (x 34..284, pozice 46214) proslo
# a2c6 a ceka na nahrani HOMING, mapa ceka na TRILO a zavadeci dosla pamet
# (A500 1 MB). Je to skutecne chovani originalu (prepis ho zamerne nema),
# ale zda nastane, zavisi na kazdem snimku vstupu - i dva snimky navic
# jinde ho vyvolaji. Jizda proto pri zablokovani (pozice stoji 1500 snimku,
# fp@(166) = 0) odsune objekty, ktere prosly a2c6 a jsou v obraze, 600 bodu
# pod obrazovku; cull `0x6480` je pak sam zrusi a uvolni pamet. Pocet
# zasahu vraci jako `vyprosteni`.
DRIVE_JS = """(cfg) => {
  const m = VA.mem(), lay = VA.layout(), A6 = lay.a6, H = m.H;
  const MARK = (0xa36a + lay.prog) & 0xffff, U = m.U, W = m.W, L = m.L;
  // cfg.souvisle: jizda jako trajdiff --od (bez cekani na zamek, citac
  // snimku pokracuje pres zastavky), takze zastavka na vypis prubeh nemeni.
  if (!cfg.souvisle && !window.__lockWait) { let guard = 0;
    while (m.rd(A6 + 166) !== 0 && guard++ < 3000) VA.run(4, null);
    window.__lockWait = 1; }
  VA.fn.warp(1);
  let k = cfg.souvisle ? (window.__jizdaK || 0) : 0;
  const k0 = k;
  let stoji = 0, posledni = U(A6 + 3530), vyprosteni = 0;
  // cfg.trace: zapisy do registru Paula (AUD0..AUD3) s PC a potvrzeni
  // zvukoveho IRQ (INTREQ z 0x4b08) - delka stavu se pak pocita v IRQ,
  // ne v case (jednorazovy CIAB se pod zatezi opozduje), tools/sfxtrace.py
  const out = [], dv = new DataView(H.buffer), IRQPC = lay.prog + 0x4b08,
        size = cfg.trace ? VA.fn.regTraceEntrySize() : 0;
  while (U(A6 + 3530) > cfg.od && k++ - k0 < cfg.limit) {
    m.w8(A6 + 166, m.rd(A6 + 166) & ~8);
    %s
    if (cfg.zbran) { %s }
    VA.fn.joy(2, (k %% 10) < 5 ? 4 : 13);
    if (k %% 120 === 0) VA.fn.joy(2, (k / 120) %% 2 ? 2 : 3);
    if (cfg.trace) {
      VA.fn.regTrace(1); VA.fn.step(); VA.fn.regTrace(0);
      const m = VA.fn.regTraceCount(), base = VA.fn.regTracePtr();
      for (let i = 0; i < m; i++) {
        const o = base + i * size, r = dv.getUint16(o, true), pc = dv.getUint32(o + 4, true);
        if ((r >= 0xa0 && r < 0xe0) || (r === 0x9c && pc === IRQPC))
          out.push([k, dv.getUint16(o + 10, true), dv.getUint16(o + 12, true),
                    r, dv.getUint16(o + 2, true), pc]);
      }
    } else VA.fn.step();
    const c = U(A6 + 3530);
    if (c !== posledni) { posledni = c; stoji = 0; continue; }
    if (++stoji < 1500 || m.rd(A6 + 166) || !cfg.vyprostit) continue;
    stoji = 0; vyprosteni++;
    let node = A6 - 698, g = 0; const seen = new Set();
    while (g++ < 800) {
      const nx = L(node + 4);
      if (!nx || !m.platna(nx) || seen.has(nx)) break;
      seen.add(nx); node = nx;
      if (W(nx + 274) !== 100 || (L(nx + 534) & 0xffff) !== MARK) continue;
      const sy = W(nx + 324) - c;
      if (sy < -80 || sy > 300) continue;
      m.w16(nx + 324, (c + 600) & 0xffff);
    }
  }
  if (cfg.souvisle) window.__jizdaK = k;
  return { pos: U(A6 + 3530), ctec: U(A6 + 3586), k: k - k0, vyprosteni, out,
           prog: lay.prog, a6: A6 };
}""" % (KEEP_LIVES_JS, KEEP_WEAPON_JS)


def nacti_stav(page, cesta):
    """Obnovi stav ulozeny v tools/hrat.py (snapshot jadra .vamiga) a zjisti
    jeho rozvrzeni pameti (stavy z doby pred zaplatou skenu jsou chipove)."""
    err = page.evaluate("(b) => VA.loadSnapshot(b)",
                        base64.b64encode(open(cesta, "rb").read()).decode())
    if err:
        raise RuntimeError(err)
    return rozvrzeni(page)


def jizda(page, cil, limit=120000):
    """Dojede na mapovou pozici `cil` (s vyprostenim zablokovaneho zavadece)."""
    return page.evaluate(DRIVE_JS, {"od": cil, "limit": limit})
FIND_A6_JS = """(frames) => {
  const H = VA.M.HEAPU8, p = VA.fn.chipPtr(), n = VA.fn.chipSize();
  const before = H.slice(p, p + n);
  VA.run(frames, null);
  const after = H.slice(p, p + n);
  const be = (a, i) => (a[i]<<24 | a[i+1]<<16 | a[i+2]<<8 | a[i+3]) >>> 0;
  const hits = [];
  for (let i = 0; i + 4 <= n; i += 2)
    if (((be(before, i) - be(after, i)) | 0) === frames * 0x4000 &&
        be(after, i - 4) === 0x4000) hits.push(i - 3530);
  return hits;
}"""
FIND_PROG_JS = """() => {
  const H = VA.M.HEAPU8, p = VA.fn.chipPtr(), n = VA.fn.chipSize();
  const sig = [0x61,0x00,0xf5,0x88,0x41,0xed,0x00,0x0c,0x29,0x48,0x00,0xa0];
  const out = [];
  outer: for (let i = 0; i + sig.length <= n; i += 2) {
    for (let k = 0; k < sig.length; k++) if (H[p+i+k] !== sig[k]) continue outer;
    out.push(i - 0x5556);
  }
  return out;
}"""


def grab(t_after_fire, out_raw, chip=None, headless=True):
    """Vrati (raw RGB24 716x285, volitelne kopii chip RAM) v case t po fire."""
    target = ZERO_AT + t_after_fire
    srv, port = serve(os.path.join(ROOT, "web"))
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=headless)
        page = b.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append("console: " + m.text)
                if m.type == "error" else None)
        page.goto(f"http://127.0.0.1:{port}/vacmp.html")
        page.wait_for_function("window.VA && window.VA.ready", timeout=60000)
        rom = base64.b64encode(open(ROM, "rb").read()).decode()
        adf = base64.b64encode(open(ADF, "rb").read()).decode()
        err = page.evaluate("([r, a]) => VA.boot(r, a)", [rom, adf])
        if err:
            b.close(); sys.exit("boot: " + err)
        now = playSequence(page, target)
        if target > now:
            e = page.evaluate("n => VA.run(n, null)", (target - now) * FPS)
            if e:
                b.close(); sys.exit(e)
        raw = base64.b64decode(page.evaluate("() => VA.frameRGB()"))
        ram = (base64.b64decode(page.evaluate("([o, n]) => VA.chip(o, n)", list(chip)))
               if chip else None)
        frames = page.evaluate("() => VA.frames")
        b.close()
    srv.shutdown()
    if errs:
        sys.exit("chyby stranky: " + "; ".join(errs))
    open(out_raw, "wb").write(raw)
    return raw, ram, frames


if __name__ == "__main__":
    t = int(sys.argv[1]); out = os.path.abspath(sys.argv[2])
    raw, _, fr = grab(t, out)
    print(f"ok t={t} snimku={fr} bajtu={len(raw)} -> {out}")
