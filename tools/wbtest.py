#!/usr/bin/env python3
"""Kontrakt listy (Workbench menu) a nastaveni obrazu pro hrace.

Lista je jen prezentace: nic z ni nesmi sahnout na simulaci. Tenhle test
overuje, co hrac vidi a co klavesy delaji:

  - menu Project / Display / Effects / Game / Controls / Network, vse
    anglicky; Effects ma pro hrace jen stopy vozidel (ulozene), v originalu
    sede;
    menu Debug jen s `?debug` v adrese,
  - E prepina original <-> vylepseno oboje smery a NEMENI CRT; O nedela nic,
  - knofliky jas / kontrast / sytost / rozmazani jsou CSS filtr nad
    platnem; pri vychozich hodnotach zadny filtr (obraz bit po bitu stejny),
    rozmazani = 0,8 bodu hry pri 100 %, reset, ulozeni pres reload,
  - stara ulozena paleta a efekty (swivMonitor, swivDof) plati jen s ?debug,
  - C (skok na konec) jen s ?debug, R restartuje zonu, F celou obrazovku,
  - na sirce 480 a 380 px je kazdy titulek i otevreny panel cely v okne.

    python3 tools/wbtest.py
"""
import os
import re
import sys

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "game.html")
ADF = os.path.join(ROOT, "SWIVFIX.ADF")
CESKE = re.compile("[áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]")

chyby = []


def expect(ok, msg):
    if not ok:
        chyby.append(msg)
        print("FAIL", msg)


def otevri(page, query=""):
    page.goto(URL + query)
    page.set_input_files("#fpick", ADF)
    page.wait_for_selector("#titlewrap", state="visible")


def start_zone(page, zone=1):
    page.click("#mnu-hra .wbtitle")
    page.click(f"#levelbtns button:nth-child({zone})")
    page.wait_for_selector("#gamewrap", state="visible")


def slider(page, sel, value):
    page.evaluate("""([s, v]) => { const el = document.querySelector(s);
        el.value = String(v); el.dispatchEvent(new Event('input', { bubbles: true })); }""",
                  [sel, value])


with sync_playwright() as pw:
    b = pw.chromium.launch()
    page = b.new_page(viewport={"width": 1280, "height": 900})
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))

    # --- hrac: bez ?debug ---------------------------------------------
    page.goto(URL)
    page.evaluate("localStorage.clear()")
    otevri(page)
    titulky = page.evaluate("""() => [...document.querySelectorAll('#wbbar .wbmenu')]
        .filter(m => !m.hidden).map(m => m.querySelector('.wbtitle').textContent)""")
    expect(titulky == ["Project", "Display", "Effects", "Game", "Controls", "Network"],
           "menu hrace: %r" % titulky)
    expect(page.evaluate("document.getElementById('mnu-dbg').hidden"),
           "menu Debug je videt bez ?debug")
    texty = page.evaluate("""() => document.getElementById('wbbar').textContent +
        document.getElementById('intro').textContent +
        document.getElementById('loadreq').textContent""")
    ceske = sorted(set(CESKE.findall(texty)))
    expect(not ceske, "cesky text v liste/uvodu: %r" % ceske)

    start_zone(page, 1)
    st = lambda: page.evaluate("({ smooth: !!state.smooth, crt: state.crtMode, "
                               "fx: document.getElementById('modefx').checked, "
                               "filter: document.getElementById('game').style.filter })")
    s0 = st()
    expect(s0["smooth"] is False and s0["fx"] is False, "vychozi rezim neni original: %r" % s0)
    expect(s0["filter"] == "", "vychozi knofliky davaji filtr: %r" % s0["filter"])
    page.focus("#game")
    page.keyboard.press("e")
    s1 = st()
    expect(s1["smooth"] is True and s1["fx"] is True, "E nezapnulo vylepseno: %r" % s1)
    expect(s1["crt"] == s0["crt"], "E zmenilo CRT: %r -> %r" % (s0["crt"], s1["crt"]))
    page.click("#mnu-obraz .wbtitle")
    page.select_option("#crtsel", "jemne")
    page.keyboard.press("Escape")
    page.focus("#game")
    page.keyboard.press("e")
    s2 = st()
    expect(s2["smooth"] is False and s2["crt"] == "jemne",
           "druhe E nevratilo original nebo zmenilo CRT: %r" % s2)
    page.keyboard.press("o")
    expect(st()["smooth"] is False, "O porad prepina rezim")

    # Effects: stopy vozidel, sede v originalu, volba prezije reload
    ghost = lambda: page.evaluate("document.getElementById('mnu-fx').classList.contains('ghost')")
    expect(ghost(), "menu Effects neni v originalu sede")
    page.keyboard.press("e")
    expect(not ghost() and page.evaluate("state.vehicleTracks === true"),
           "vylepseno: Effects sede nebo stopy vypnute")
    page.click("#mnu-fx .wbtitle")
    page.click("#stopychk")
    page.keyboard.press("Escape")
    expect(page.evaluate("state.vehicleTracks === false"), "odskrtnuti stopy nevypnulo")
    page.focus("#game")
    page.keyboard.press("e")

    # knofliky monitoru
    slider(page, "#dispbright", 120)
    slider(page, "#dispsat", 40)
    f = st()["filter"]
    expect("brightness(120%)" in f and "saturate(40%)" in f and "contrast" not in f,
           "filtr jasu/sytosti: %r" % f)
    slider(page, "#dispblur", 50)
    blur = page.evaluate("""() => { const cv = document.getElementById('game');
        const m = /blur\\(([0-9.]+)px\\)/.exec(cv.style.filter);
        return [m ? +m[1] : -1, parseFloat(cv.style.width)]; }""")
    expect(abs(blur[0] - 0.5 * 0.8 * blur[1] / 320) < 0.002,
           "rozmazani neodpovida 0,8 bodu hry: %r" % blur)
    expect(page.evaluate("document.getElementById('dispbrightval').textContent") == "120%",
           "popisek jasu se neaktualizoval")
    # ulozeni pres reload
    otevri(page)
    expect(page.evaluate("document.getElementById('dispbright').value") == "120",
           "jas se po reloadu neobnovil")
    expect(page.evaluate("!document.getElementById('stopychk').checked"),
           "vypnute stopy se po reloadu neobnovily")
    expect("brightness(120%)" in page.evaluate("document.getElementById('title').style.filter"),
           "knofliky neplati na titulni obrazovce")
    page.click("#mnu-obraz .wbtitle")
    page.click("#dispreset")
    expect(page.evaluate("document.getElementById('title').style.filter") == "",
           "reset nevratil obraz bez filtru")
    expect(page.evaluate("localStorage.getItem('swivPicture')") is None,
           "reset nesmazal ulozene knofliky")
    expect(page.evaluate("document.getElementById('mnu-obraz').classList.contains('open')"),
           "reset zavrel menu")

    # C bez ?debug nic, R restart, F cela obrazovka
    start_zone(page, 2)
    page.evaluate("state.g._znacka = 1")
    page.focus("#game")
    page.keyboard.press("c")
    expect(page.evaluate("!state.g.over"), "C bez ?debug ukoncilo hru")
    page.keyboard.press("r")
    expect(page.evaluate("state.g && !state.g._znacka && state.g.lv === 1"),
           "R nerestartovalo zonu")
    page.evaluate("""() => { window._fs = 0;
        document.documentElement.requestFullscreen = () => { window._fs++; return Promise.resolve(); }; }""")
    page.keyboard.press("f")
    expect(page.evaluate("window._fs") == 1, "F nezadalo celou obrazovku")

    # stara ulozena paleta a efekty plati jen v ladeni
    page.evaluate("localStorage.setItem('swivMonitor', 'crt'); localStorage.setItem('swivDof', 'vyp')")
    otevri(page)
    expect(page.evaluate("MONITOR_MODE") == "puvodni", "hrac zdedil ulozenou paletu crt")
    expect(page.evaluate("state.dofLevel") == "plna", "hrac zdedil ulozeny efekt dof=vyp")

    # --- ladeni: ?debug ------------------------------------------------
    otevri(page, "?debug")
    expect(not page.evaluate("document.getElementById('mnu-dbg').hidden"),
           "menu Debug neni videt s ?debug")
    expect(page.evaluate("MONITOR_MODE") == "crt", "?debug neobnovil ulozenou paletu")
    expect(page.evaluate("state.dofLevel") == "vyp", "?debug neobnovil ulozeny efekt")
    page.evaluate("localStorage.removeItem('swivMonitor'); localStorage.removeItem('swivDof')")
    start_zone(page, 1)
    page.focus("#game")
    page.keyboard.press("c")
    expect(page.evaluate("state.g.over && state.g.won"), "C s ?debug neskocilo na konec")

    # uzka obrazovka (stranka hrace): vsechny titulky v liste a kazdy
    # otevreny panel v okne
    otevri(page)
    for w in (480, 380):
        page.set_viewport_size({"width": w, "height": 700})
        mimo = page.evaluate("""() => {
          const W = document.documentElement.clientWidth, out = [];
          for (const m of document.querySelectorAll('#wbbar .wbmenu')) {
            if (m.hidden) continue;
            const t = m.querySelector('.wbtitle');
            if (t.getBoundingClientRect().right > W) out.push('titulek ' + t.textContent);
            t.click();
            const r = m.querySelector('.wbpanel').getBoundingClientRect();
            if (r.left < 0 || r.right > W) out.push('panel ' + t.textContent);
            document.body.click();
          }
          return out; }""")
        expect(not mimo, "sirka %d: mimo okno %r" % (w, mimo))
    page.set_viewport_size({"width": 1280, "height": 900})

    expect(not errs, "JS chyby: %r" % errs)
    b.close()

if chyby:
    sys.exit("WB FAIL: %d" % len(chyby))
print("WB OK: menu hrace anglicky, Debug jen s ?debug, E bez vlivu na CRT, "
      "knofliky obrazu jako CSS filtr (vychozi bez filtru), R/F/C")
