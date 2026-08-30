#!/usr/bin/env python3
"""End-to-end a behavior regrese hry v realnem Chromiu.

Projde tok vlozeni ADF -> intro -> vyber TOWN, overi puvodni dispatch
tabulku, palety, formace, miny, vlak, plamenomet, animace ROTOBASE/POPUP
a cyklus CAMOGUN.
Pri chybe nebo nesplnene podmince skonci nenulovym navratovym kodem.

    python3 tools/uitest.py
"""

from playwright.sync_api import sync_playwright
import os
import time


def expect(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1200, "height": 900})
            page.set_default_timeout(10_000)
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(
                "console.%s: %s" % (m.type, m.text)) if m.type == "error" else None)
            page.goto("file://" + os.path.abspath("game.html"))

            page.set_input_files("#fpick", os.path.abspath("SWIVFIX.ADF"))
            page.wait_for_selector("#titlewrap", state="visible")
            expect(page.is_visible("#titlewrap"), "po vlozeni ADF chybi titulka")

            page.keyboard.press(" ")
            page.wait_for_selector("#levelpick", state="visible")
            expect(page.is_visible("#levelpick"), "po stisku fire chybi vyber urovne")

            # Pred startem zastavime RAF; logiku pak tikame rucne a deterministicky.
            page.evaluate("window.requestAnimationFrame = () => 0")
            started = time.time()
            page.click("#levelbtns a:first-child")
            page.wait_for_selector("#gamewrap", state="visible")
            expect(page.is_visible("#gamewrap"), "po vyberu TOWN chybi herni canvas")

            # Indexovy renderer je viditelnou cestou statickeho pozadi;
            # zaroven overujeme jeho ciste bloky nad skutecnymi TOWN/.LIN daty.
            renderer_core = page.evaluate("""() => {
              const { fid, dico } = levelInfo(state.prog, 0);
              const pamName = state.order[fid];
              const file = state.files.find(f => f.name === pamName);
              const parsed = parsePam(unpackFile(state.adf, file), dico);
              const margin = 160, top = parsed.height + margin - 256;
              const lines = compileCopperPaletteLines(
                parsed.checks, parsed.height, margin, top, 256, 0, 0);
              const faded = compileCopperPaletteLines(
                parsed.checks, parsed.height, margin, top, 1, 64, 128);

              const levels = [0, 16, 64, 128, 240, 256];
              const sample = 0xF84;
              const fnv1a = bytes => {
                let h = 0x811C9DC5;
                for (const value of bytes)
                  h = Math.imul((h ^ value) >>> 0, 0x01000193) >>> 0;
                return h.toString(16).padStart(8, '0');
              };

              // JEEPHELI#1 je realny dvoudilny chain. Druhy dil ma cx=-16,
              // takze fixture zaroven hlida signed anchor i spolecnou kotvu.
              const logical = frames('JEEPHELI.LIN')[1];
              const indexed = decodeIndexedFrame(logical);
              const dst = new Uint8Array(64 * 64);
              dst.fill(0xFE);
              blitIndexed(dst, 64, 64, indexed, 24, 20);

              // D1: skutecne TOWN assety pres presnou unsigned frontu
              // 0x481a. Runtime se na tuto cestu zatim neprepina.
              const fodder = indexedFrameFor(state, "FODDERA.LIN", 2);
              const mill = indexedFrameFor(state, "MILL.LIN", 0);
              const rotorMask = indexedFrameFor(state, "JEEPHELI.LIN", 5);
              const popup = indexedFrameFor(state, "POPUP.LIN", 0);
              let bobSerial = 0, bobRecords = [];
              for (const spec of [
                { id: "fod", primary: fodder, x: 40, y: 20, z: 32 },
                { id: "mill", primary: mill, secondary: rotorMask,
                  x: 100, y: 60, z: 32 },
                { id: "popup", primary: popup, x: 80, y: 50, z: 0 }
              ]) {
                const batch = standardBobRecords(spec, bobSerial);
                bobRecords.push(...batch.records);
                bobSerial = batch.nextSerial;
              }
              const bobOrdered = sortBobRecords(bobRecords);
              const bobDst = new Uint8Array(160 * 128);
              for (let y = 0; y < 128; y++)
                for (let x = 0; x < 160; x++)
                  bobDst[y * 160 + x] = (3 * x + 5 * y) & 15;
              for (const record of bobOrdered) {
                if (record.op === BOB_CLEAR_INDEX0)
                  clearIndexedMask(bobDst, 160, 128, record.spr,
                                   record.x, record.y);
                else
                  blitIndexedCookie(bobDst, 160, 128, record.spr,
                                    record.x, record.y);
              }
              const suppressedShadow = standardBobRecords({
                id: "no-shadow", primary: fodder,
                x: 100, y: 70, z: 32, objectFlags: 1
              }, 0);
              const groundShadow = standardBobRecords({
                id: "ground", primary: popup, x: 100, y: 70, z: 0
              }, 0);

              const mapIndex = state.g.mapIndex, width = 320;
              const colorRows = (top, rows) => {
                const rgba = colorizeIndexedRows(
                  mapIndex, width, state.mapMeta.height, margin,
                  top, rows, state.copperChecks);
                const rgb = new Uint8Array(width * rows * 3);
                for (let i = 0; i < width * rows; i++) {
                  rgb[i * 3] = rgba[i * 4];
                  rgb[i * 3 + 1] = rgba[i * 4 + 1];
                  rgb[i * 3 + 2] = rgba[i * 4 + 2];
                }
                return rgb;
              };
              const initialTop = state.g.mapH - margin - 256;
              const initialIndex = mapIndex.subarray(
                initialTop * width, (initialTop + 256) * width);
              const initialRgb = colorRows(initialTop, 256);

              // Toto okno skutecne protina tile pres checkpoint y=2127.
              // Stary RGBA vystup musi v kroku B zustat jiny; indexova cesta
              // uz ale musi dat spravnou scanline paletu pro dalsi krok.
              const diffTop = 1454, diffRows = 21;
              const correctRgb = colorRows(diffTop, diffRows);
              const legacyRgba = state.g.big.getContext('2d').getImageData(
                0, 0, width, state.g.mapH).data;
              const legacyRgb = new Uint8Array(width * diffRows * 3);
              let paletteMismatches = 0;
              for (let i = 0; i < width * diffRows; i++) {
                const d = i * 3, s = (diffTop * width + i) * 4;
                legacyRgb[d] = legacyRgba[s];
                legacyRgb[d + 1] = legacyRgba[s + 1];
                legacyRgb[d + 2] = legacyRgba[s + 2];
                if (legacyRgb[d] !== correctRgb[d] ||
                    legacyRgb[d + 1] !== correctRgb[d + 1] ||
                    legacyRgb[d + 2] !== correctRgb[d + 2])
                  paletteMismatches++;
              }

              const edgeFirst = colorizeIndexedRows(
                mapIndex, width, state.mapMeta.height, margin, 0, 1,
                state.copperChecks);
              const edgeLast = colorizeIndexedRows(
                mapIndex, width, state.mapMeta.height, margin,
                state.g.mapH - 1, 1, state.copperChecks);
              let rejectedEdges = 0;
              for (const [edgeTop, edgeRows] of
                   [[-1, 1], [state.g.mapH, 1], [state.g.mapH - 1, 2]]) {
                try {
                  colorizeIndexedRows(
                    mapIndex, width, state.mapMeta.height, margin,
                    edgeTop, edgeRows, state.copperChecks);
                } catch (e) {
                  if (e instanceof RangeError) rejectedEdges++;
                }
              }

              // Runtime dukaz: posuneme rozdilne mapove radky na obrazovku
              // y=50..70, kde je neprekryva HUD, a docasne skryjeme BOB vrstvy.
              const g = state.g, runtimeScreenY = 50;
              const saved = {
                scroll: g.scroll, frac: g.frac, last: g.last,
                fadeBlack: g.fadeBlack, fadeWhite: g.fadeWhite,
                fadeDir: g.fadeDir, over: g.over, won: g.won,
                spawns: g.spawns, effects: g.effects, hazards: g.hazards,
                air: g.air, booms: g.booms, plops: g.plops,
                bullets: g.bullets, shots: g.shots, tokens: g.tokens,
                playerAlive: g.player.alive
              };
              let runtimeRgb;
              try {
                g.scroll = diffTop - runtimeScreenY;
                g.frac = 0; g.fadeBlack = 0; g.fadeWhite = 0;
                g.fadeDir = 0; g.over = false; g.won = false;
                g.spawns = []; g.effects = []; g.hazards = []; g.air = [];
                g.booms = []; g.plops = []; g.bullets = []; g.shots = [];
                g.tokens = []; g.player.alive = false;
                const now = performance.now(); g.last = now; frame(now);
                const runtimeRgba = document.querySelector('#game')
                  .getContext('2d').getImageData(
                    0, runtimeScreenY, width, diffRows).data;
                runtimeRgb = new Uint8Array(width * diffRows * 3);
                for (let i = 0; i < width * diffRows; i++) {
                  runtimeRgb[i * 3] = runtimeRgba[i * 4];
                  runtimeRgb[i * 3 + 1] = runtimeRgba[i * 4 + 1];
                  runtimeRgb[i * 3 + 2] = runtimeRgba[i * 4 + 2];
                }
              } finally {
                g.scroll = saved.scroll; g.frac = saved.frac; g.last = saved.last;
                g.fadeBlack = saved.fadeBlack; g.fadeWhite = saved.fadeWhite;
                g.fadeDir = saved.fadeDir; g.over = saved.over; g.won = saved.won;
                g.spawns = saved.spawns; g.effects = saved.effects;
                g.hazards = saved.hazards; g.air = saved.air;
                g.booms = saved.booms; g.plops = saved.plops;
                g.bullets = saved.bullets; g.shots = saved.shots;
                g.tokens = saved.tokens; g.player.alive = saved.playerAlive;
              }
              let runtimeMismatches = 0;
              for (let i = 0; i < correctRgb.length; i++)
                if (runtimeRgb[i] !== correctRgb[i]) runtimeMismatches++;

              return {
                town: {
                  name: pamName, height: parsed.height,
                  checks: parsed.checks.map(c => c.y),
                  boundaries: [
                    [65, parsed.height + margin - (top + 65),
                     lines[65 * 16 + 13]],
                    [66, parsed.height + margin - (top + 66),
                     lines[66 * 16 + 13]],
                    [152, parsed.height + margin - (top + 152),
                     lines[152 * 16 + 1]],
                    [153, parsed.height + margin - (top + 153),
                     lines[153 * 16 + 1]]
                  ],
                  fadedTop13: faded[13]
                },
                fade: {
                  black: levels.map(level => fadeRgb12Black(sample, level)),
                  white: levels.map(level => fadeRgb12White(sample, level)),
                  blackThenWhite: fadeRgb12(sample, 64, 128),
                  whiteThenBlack: fadeRgb12Black(
                    fadeRgb12White(sample, 128), 64)
                },
                indexed: {
                  parts: logical.parts.length,
                  anchors: logical.parts.map(p => [p.cx, p.cy, p.flags]),
                  box: [indexed.ox, indexed.oy, indexed.w, indexed.h],
                  opaque: indexed.pix.reduce(
                    (n, color) => n + (color !== 0xFF), 0),
                  hash: fnv1a(indexed.pix),
                  changed: dst.reduce((n, color) => n + (color !== 0xFE), 0),
                  blitHash: fnv1a(dst)
                },
                bob: {
                  depthZ: [0, 1, 2, 12, 24, 32, 33].map(bobDepthKey),
                  shadow32: Object.values(bobShadowAnchor(100, 70, 32)),
                  shadow33: Object.values(bobShadowAnchor(100, 70, 33)),
                  suppressedKinds: suppressedShadow.records.map(r => r.kind),
                  groundKinds: groundShadow.records.map(r => r.kind),
                  opaque: [fodder, mill, rotorMask, popup].map(spr =>
                    spr.pix.reduce((n, color) => n + (color !== 0xFF), 0)),
                  order: bobOrdered.map(record => record.id),
                  hash: fnv1a(bobDst),
                  zeros: bobDst.reduce((n, color) => n + (color === 0), 0),
                  sum: bobDst.reduce((n, color) => n + color, 0)
                },
                mapIndex: {
                  size: [width, state.g.mapH], full: fnv1a(mapIndex),
                  initial: fnv1a(initialIndex), initialRgb: fnv1a(initialRgb),
                  legacyRgba: fnv1a(legacyRgba),
                  differing: {
                    top: diffTop, rows: diffRows,
                    correct: fnv1a(correctRgb), legacy: fnv1a(legacyRgb),
                    pixels: paletteMismatches
                  }
                },
                colorizer: {
                  edges: [edgeFirst.length, edgeLast.length],
                  alpha: [edgeFirst[3], edgeLast[3]],
                  rejected: rejectedEdges,
                  runtime: fnv1a(runtimeRgb),
                  runtimeMismatches
                }
              };
            }""")
            expect(renderer_core["town"]["name"] == "TOWN.PAM" and
                   renderer_core["town"]["height"] == 3441,
                   "Copper fixture nenacetla skutecnou mapu TOWN")
            expect(renderer_core["town"]["checks"] ==
                   [96, 104, 191, 383, 578, 734, 929, 1272, 1352,
                    1621, 2127, 2601, 2769],
                   "TOWN ma jiny seznam Copper checkpointu: %s" %
                   renderer_core["town"]["checks"])
            expect(renderer_core["town"]["boundaries"] ==
                   [[65, 191, 0xBBB], [66, 190, 0x353],
                    [152, 104, 0x555], [153, 103, 0x000]],
                   "Copper paleta se neprepina na presne scanline: %s" %
                   renderer_core["town"]["boundaries"])
            expect(renderer_core["fade"]["black"] ==
                   [0xF84, 0xE73, 0xB63, 0x742, 0, 0] and
                   renderer_core["fade"]["white"] ==
                   [0xF84, 0xF95, 0xFA7, 0xFCA, 0xFFF, 0xFFF],
                   "RGB12 fade neorezava jednotlive nibble jako 0x4a48/0x4a40")
            expect(renderer_core["fade"]["blackThenWhite"] == 0xDB9 and
                   renderer_core["fade"]["whiteThenBlack"] == 0xB97 and
                   renderer_core["town"]["fadedTop13"] == 0xCCC,
                   "fade nema poradi cerna -> bila z 0x5da8/0x5e58")
            expect(renderer_core["indexed"] == {
                     "parts": 2,
                     "anchors": [[16, 12, 1], [-16, -1, 0]],
                     "box": [-16, -12, 34, 32],
                     "opaque": 448, "hash": "e4a68453",
                     "changed": 448, "blitHash": "6cfe4537"
                   },
                   "indexovy chain JEEPHELI#1 nema presny decode/blit: %s" %
                   renderer_core["indexed"])
            expect(renderer_core["bob"] == {
                     "depthZ": [0x7FFF, 0x7FFE, 0x7FFD, 0x7FF3,
                                0x7FE7, 0x7FDF, 0x7FDE],
                     "shadow32": [116, 102], "shadow33": [116, 103],
                     "suppressedKinds": ["main"],
                     "groundKinds": ["main"],
                     "opaque": [283, 248, 196, 1024],
                     "order": ["mill-shadow", "fod-shadow", "popup-main",
                               "mill-main", "fod-main", "mill-secondary"],
                     "hash": "94e10005", "zeros": 2189, "sum": 141978
                   },
                   "BOB depth/shadow/clear fixture nesedi s 0x481a/0x6364: %s" %
                   renderer_core["bob"])
            expect(renderer_core["mapIndex"] == {
                     "size": [320, 3761],
                     "full": "3d426f35", "initial": "5870b220",
                     "initialRgb": "89a47b97",
                     "legacyRgba": "b6e13bf7",
                     "differing": {
                       "top": 1454, "rows": 21,
                       "correct": "7f08f24f", "legacy": "2813671f",
                       "pixels": 21
                     }
                   },
                   "TOWN mapIndex/Copper RGB nema presny obsah: %s" %
                   renderer_core["mapIndex"])
            colorizer = renderer_core["colorizer"]
            expect(colorizer["edges"] == [1280, 1280] and
                   colorizer["alpha"] == [255, 255] and
                   colorizer["rejected"] == 3,
                   "indexovy colorizer nema bezpecne horni/dolni hranice: %s" %
                   colorizer)
            expect(colorizer["runtime"] == "7f08f24f" and
                   colorizer["runtimeMismatches"] == 0,
                   "viditelny runtime nepouziva presnou scanline paletu: %s" %
                   colorizer)
            # Fade z cerne: 0x3092 vola 0x2868, driver 0x28b0 pak odcernuje
            # krokem 16 za snimek, tedy presne 16 tiku z 256 na 0.
            fade = page.evaluate("""() => {
              const g = state.g, seq = [g.fadeBlack];
              // HUD merime zvlast: jeho text jde pres COLOR16 (0x1A0), ktera
              // je uz mimo fadovany rozsah 0x180-0x19F, takze fade neztmavi.
              const shot = () => {
                g.last = performance.now();
                frame(performance.now());
                const cv = document.querySelector('#game');
                const c2 = cv.getContext('2d');
                const count = (y0, y1) => {
                  const px = c2.getImageData(0, y0, cv.width, y1 - y0).data;
                  let n = 0;
                  for (let i = 0; i < px.length; i += 4)
                    if (px[i] || px[i + 1] || px[i + 2]) n++;
                  return n;
                };
                return { hud: count(0, 20), field: count(24, cv.height) };
              };
              const atStart = shot();
              for (let i = 0; i < 16; i++) { step(g); seq.push(g.fadeBlack); }
              const atEnd = shot(), dirAt16 = g.fadeDir;
              step(g);   // 17. tik: teprve ted subiw podtece a priznak spadne
              return { seq, dirAt16, dir: g.fadeDir, lvl: g.fadeBlack,
                       atStart, atEnd };
            }""")
            expect(fade["seq"] == list(range(256, -1, -16)),
                   "fade z cerne nekrokuje po 16 az na nulu: %s" % fade["seq"])
            expect(fade["dirAt16"] != 0,
                   "priznak fp@(142) spadl uz po 16 ticich; subiw #16 na "
                   "0x28b8 podtece az 17. tikem, blokujici 0x2868 se vraci "
                   "o snimek pozdeji nez je obraz hotovy")
            expect(fade["dir"] == 0 and fade["lvl"] == 0,
                   "17. tik nevynuloval fp@(142) nebo uroven fadu")
            expect(fade["atStart"]["field"] == 0,
                   "hraci plocha ma byt na startu cerna, ma %d barevnych "
                   "pixelu" % fade["atStart"]["field"])
            expect(fade["atStart"]["hud"] > 0,
                   "HUD ma zustat svitit i pri plnem fadu: COLOR16 (0x1A0) "
                   "lezi mimo fadovany rozsah 0x180-0x19F")
            expect(fade["atEnd"]["field"] > 1_000,
                   "po 16 ticich se hraci plocha neodcernila")

            rendered = page.evaluate("""() => {
              frame(performance.now());
              const cv = document.querySelector('#game');
              const px = cv.getContext('2d').getImageData(
                0, 0, cv.width, cv.height).data;
              let opaque = 0, nonBlack = 0;
              for (let i = 0; i < px.length; i += 4) {
                if (px[i + 3]) opaque++;
                if (px[i] || px[i + 1] || px[i + 2]) nonBlack++;
              }
              return { width: cv.width, height: cv.height, opaque, nonBlack };
            }""")
            expect(rendered["width"] == 320 and rendered["height"] == 256 and
                   rendered["opaque"] > 50_000 and rendered["nonBlack"] > 1_000,
                   "renderer nevykreslil neprázdný herní frame")

            cannon_palette = page.evaluate("""() => {
              const colors = spr => {
                const px = spr.cv.getContext('2d').getImageData(
                  0, 0, spr.w, spr.h).data;
                const out = new Set();
                for (let i = 0; i < px.length; i += 4)
                  if (px[i + 3]) out.add(`${px[i]},${px[i + 1]},${px[i + 2]}`);
                return [...out];
              };
              return {
                frame28: colors(sprite('BULLET.LIN', 28, cannonPal(0),
                                       'test:cannon:28')),
                frame44: colors(sprite('BULLET.LIN', 44, cannonPal(0),
                                       'test:cannon:44')),
                accents: CANNON_ACCENTS
              };
            }""")
            expect(set(cannon_palette["frame28"]) ==
                   {"255,255,255", "153,153,153", "204,0,0"} and
                   set(cannon_palette["frame44"]) ==
                   {"255,255,255", "153,153,153"},
                   "kanonovy granat nema bilou/sedou HW-sprite paletu")
            expect(cannon_palette["accents"] ==
                   [0xC00, 0xFF0, 0xFC0, 0x800, 0xF80, 0xF00, 0xC00, 0xFF0,
                    0xC80, 0xFF0, 0xF80, 0x800, 0xFF0, 0x000, 0xFF0, 0x800],
                   "kanonovy granat nema 16tikovou COLOR19 tabulku")

            formations = page.evaluate("""() => {
              const savedRandom = Math.random;
              Math.random = () => 0.25;
              try {
                const g = { air: [], waveSeq: 0, players: 1,
                            activeCost: 0, scroll: 149 };
                spawnFodderFormation(g, { y: 100, typ: 1 });
                const fod = g.air;
                const before = activateAirMember(g, fod[0], { x: 100 });
                g.scroll = 148;
                const atMargin = activateAirMember(g, fod[0], { x: 100 });
                const activeCost = g.activeCost;
                releaseAirMember(g, fod[0]);

                const motion = { x: 100, y: 0, vx: 0, vy: 0,
                                 ax: 0, ay: 1 / 32 };
                for (let i = 0; i < 96; i++) stepFodderMotion(motion);
                const tick96 = { y: motion.y, vy: motion.vy, ay: motion.ay };
                stepFodderMotion(motion);
                const tick97 = { y: motion.y, vy: motion.vy, ay: motion.ay };
                const edge = { x: 31, y: 0, vx: 0, vy: 0, ax: 0, ay: 0 };
                stepFodderMotion(edge);

                const fodAnim = [];
                const fa = { ...fod[1], apos: 0, at: 0, animFresh: true };
                for (let i = 0; i < 8; i++) {
                  advanceAirAnim(fa); fodAnim.push(fa.seq[fa.apos]);
                }

                const gy = { air: [], players: 1, activeCost: 0, scroll: 149 };
                spawnYellowFormation(gy, { y: 100 });
                const yellow = gy.air;
                gy.scroll = 148;
                const yFirst = activateAirMember(gy, yellow[0], { x: 100 });
                const xFirst = yellow[0].x;
                gy.scroll = 141;
                const yBefore = activateAirMember(gy, yellow[1], { x: 200 });
                gy.scroll = 140;
                const ySecond = activateAirMember(gy, yellow[1], { x: 200 });
                const xSecond = yellow[1].x;
                const yelAnim = [];
                const ya = { ...yellow[0], apos: 0, at: 0, animFresh: true };
                for (let i = 0; i < 8; i++) {
                  advanceAirAnim(ya); yelAnim.push(ya.seq[ya.apos]);
                }

                const capped = { activeCost: 160, scroll: 0 };
                const rejected = { kind: 'fod', y: 0, pending: true,
                                   alive: false, dead: false, cost: 10 };
                const budgetAccepted = activateAirMember(capped, rejected, { x: 0 });
                return {
                  fodCount: fod.length,
                  fodY: fod.map(a => a.y),
                  sharedX: new Set(fod.map(a => a.x)).size,
                  sharedVx: new Set(fod.map(a => a.vx)).size,
                  noDelay: fod.every(a => !('delay' in a)),
                  before, atMargin, activeCost, releasedCost: g.activeCost,
                  tick96, tick97, edge: { x: edge.x, vx: edge.vx }, fodAnim,
                  yellowCount: yellow.length,
                  yellowY: yellow.map(a => a.y),
                  yFirst, xFirst, yBefore, ySecond, xSecond, yelAnim,
                  budgetAccepted, rejectedDead: rejected.dead,
                  cappedCost: capped.activeCost
                };
              } finally { Math.random = savedRandom; }
            }""")
            expect(formations["fodCount"] == 4 and
                   formations["fodY"] == [100, 96, 92, 88] and
                   formations["sharedX"] == formations["sharedVx"] == 1 and
                   formations["noDelay"],
                   "FODDERA 0x8048 nema 1P formaci 4 clenu po 4 px")
            expect(formations["before"] is False and formations["atMargin"] is True and
                   formations["activeCost"] == 10 and
                   formations["releasedCost"] == 0,
                   "FODDERA nema vlastni aktivacni prah -48/budget cleanup")
            expect(abs(formations["tick96"]["vy"] - 3) < 1e-9 and
                   abs(formations["tick96"]["y"] - 145.5) < 1e-9 and
                   abs(formations["tick97"]["vy"] - 3) < 1e-9 and
                   formations["tick97"]["ay"] == 0 and
                   abs(formations["tick97"]["y"] - 148.5) < 1e-9,
                   "FODDERA nema zrychleni 1/32 px/t2 se stropem 3 px/t")
            expect(abs(formations["edge"]["vx"] - 1 / 32) < 1e-9 and
                   abs(formations["edge"]["x"] - (31 + 1 / 32)) < 1e-9 and
                   formations["fodAnim"] == [2, 3, 2, 4, 2, 5, 2, 6],
                   "FODDERA nema pozvolnou korekci okraje/rotor period 1")
            expect(formations["yellowCount"] == 6 and
                   formations["yellowY"] == [100, 92, 84, 76, 68, 60] and
                   formations["yFirst"] is True and 256 <= formations["xFirst"] < 320 and
                   formations["yBefore"] is False and formations["ySecond"] is True and
                   0 <= formations["xSecond"] < 64 and
                   formations["yelAnim"] == [0, 1, 0, 2, 0, 3, 0, 4],
                   "YELLOW nema 6 samostatne aktivovanych clenu/animaci")
            expect(formations["budgetAccepted"] is False and
                   formations["rejectedDead"] is True and
                   formations["cappedCost"] == 160,
                   "active budget dovolil prekrocit 160")

            # TOWN boss GOOSE (0xc78a, docs/TOWN-AUDIT.md 4): nalet, HP 25 uz
            # pri zastaveni, ctyri potomci s dokovanim 0xcb78, pod 0xcaac,
            # odhozeni casti pri zasahu, palba a kruh bonusu.
            boss = page.evaluate("""() => {
              const g = state.g;
              const s = g.spawns.find(o => o.beh === 'boss');
              if (!s) return { err: 'boss v TOWN neni' };
              g.scrollMul = 0.000001;
              g.player.alive = true; g.player.x = 100; g.player.y = 200;
              g.player.inv = 0; g.player.shield = 0;
              g.shots = []; g.tokens = []; g.bullets = []; g.air = [];
              s.born = false; s.armed = true; s.alive = true;
              s.y = g.scroll;                    // margin 0
              step(g);
              const born = { x: s.x, sy: Math.round(s.y - g.scroll),
                             hp: s.hp, st: s.st, parts: s.parts.length,
                             undocked: s.undocked, coroutine: s.coroutine };
              // casti: po cekani 0..63 vstoupi shora a 75 snimku leti rovne dolu
              let guard = 0, q0 = null;
              while (!q0 && guard++ < 70) {
                step(g);
                q0 = s.parts.find(q => q.entered && q.phase === 'dive' && q.t === 75);
              }
              if (!q0) return { err: 'zadna cast nevstoupila do 70 snimku' };
              const entry = { sy: Math.round(q0.y - g.scroll), phase: q0.phase,
                              x: q0.x };
              for (let i = 0; i < 74; i++) step(g);
              const dive = { phase: q0.phase, dy: Math.round(q0.y - g.scroll) - entry.sy };
              guard = 0;
              while (s.st === 0 && guard++ < 2000) step(g);
              const stopped = { st: s.st, hp: s.hp,
                                sy: Math.round(s.y - g.scroll) };
              // zasah behem cekani na dokovani: HP klesa uz ted
              g.bullets = [{ x: s.x, y: s.y - g.scroll + 9 }];
              step(g);
              const hitWhileWaiting = { hp: s.hp, st: s.st };
              guard = 0;
              const podRight = s.parts.find(q => q.pod);
              let podAtDock = null;
              while (!s.parts.every(q => q.docked) && guard++ < 4000) {
                step(g);
                if (podRight.docked && !podAtDock)
                  podAtDock = [podRight.ox, podRight.oy];   // 0xcaac: (0, +24)
              }
              const dockedTicks = guard;
              const docked = s.parts.map(q => [q.tx, q.ty]);
              step(g);
              const fight = { st: s.st, undocked: s.undocked, vy: s.vy };
              // zasah v boji: casti se odhodi na dvojnasobek a vraceji po 4
              const top = s.parts.find(q => q.ty === -44);
              g.bullets = [{ x: s.x, y: s.y - g.scroll + 9 }];
              const before = s.hp; step(g);
              const jolt = [top.oy];
              for (let i = 0; i < 12; i++) { step(g); jolt.push(top.oy); }
              const hit = { hpDrop: before - s.hp, jolt };
              // pod se po 20 yieldech houpe na rameni 18 px
              for (let i = 0; i < 40; i++) step(g);
              const pod = { phase: podRight.phase, oy: Math.round(podRight.oy),
                            frame: podRight.animFr };
              g.shots = []; s.fireT = 1;
              guard = 0;
              while (g.shots.length === 0 && guard++ < 400) step(g);
              const salvo = g.shots.map(x => x.kind).sort();
              g.tokens = [];
              dropBossTokens(g, s, 2);
              const ring = g.tokens.map(k => k.ang);
              // smrt: 0 bodu, maly vybuch, casti zmizi, pod exploduje
              g.score = 0; g.booms = []; g.tokens = []; s.hp = 1;
              g.bullets = [{ x: s.x, y: s.y - g.scroll + 9 }];
              step(g);
              const death = { alive: s.alive, score: g.score,
                              booms: g.booms.map(b => b.kind), tokens: g.tokens.length };
              return { born, stopped, entry, dive, hitWhileWaiting, dockedTicks,
                       docked, podAtDock, fight, hit, pod, salvo, ring, death };
            }""")
            expect("err" not in boss, boss.get("err", ""))
            expect(boss["born"]["coroutine"] == 0xC78A,
                   "boss neni routovany na korutinu 0xc78a")
            expect(boss["born"]["x"] == 160 and boss["born"]["sy"] == 288,
                   "boss se po aktivaci nepresunul na stred a o 288 px dal: %s"
                   % boss["born"])
            expect(boss["born"]["hp"] == 0 and boss["born"]["parts"] == 4 and
                   boss["born"]["undocked"] == 4,
                   "boss ma byt behem naletu bez HP a mit ctyri potomky: %s"
                   % boss["born"])
            expect(boss["stopped"]["st"] == 1 and boss["stopped"]["hp"] == 25 and
                   boss["stopped"]["sy"] <= 72,
                   "boss nezastavil na y 72 s 25 HP (0xc842): %s" % boss["stopped"])
            expect(boss["entry"]["sy"] == -24 and boss["entry"]["phase"] == "dive"
                   and 32 <= boss["entry"]["x"] < 288,
                   "cast nevstoupila shora z 32+rand&255 (0xca3c): %s" % boss["entry"])
            expect(boss["dive"] == {"phase": "dive", "dy": 148},
                   "cast ma 75 snimku letet rovne dolu 2 px/t (0xcbc2): %s"
                   % boss["dive"])
            expect(boss["hitWhileWaiting"] == {"hp": 24, "st": 1},
                   "boss ma jit trefit uz pred dokovanim: %s" % boss["hitWhileWaiting"])
            expect(boss["dockedTicks"] < 4000 and
                   sorted(boss["docked"]) == [[-16, -12], [0, -44], [0, 24], [16, -12]],
                   "ctyri potomci nezadokovali na ofsety 0xc9e2/0xc9ec/0xc9f0/0xcaac: %s"
                   % boss["docked"])
            expect(boss["podAtDock"] == [0, 24] and
                   boss["fight"] == {"st": 2, "undocked": 0, "vy": 1},
                   "po dokovani ma zacit boj s vy = 1 (0xc878): %s / %s"
                   % (boss["podAtDock"], boss["fight"]))
            # 0xca5e zdvojnasobi (-88) a 0xca7a v temze tiku vrati o 4 -> -84,
            # pak po 4 px az na -44
            expect(boss["hit"]["hpDrop"] == 1 and boss["hit"]["jolt"][1] == -84 and
                   boss["hit"]["jolt"][6] == -64 and boss["hit"]["jolt"][11] == -44,
                   "zasah ma vrsek odhodit na -84 a vratit po 4 px (0xca5e/0xca7a): %s"
                   % boss["hit"])
            expect(boss["pod"]["phase"] == "swing" and 12 <= boss["pod"]["oy"] <= 31
                   and 8 <= boss["pod"]["frame"] <= 11,
                   "pod se nehoupe na rameni 18 px pod telem (0xcb14): %s" % boss["pod"])
            expect(boss["salvo"] == ["can", "hom", "hom"],
                   "salva bosse ma byt mireny granat + dve navadene: %s"
                   % boss["salvo"])
            expect(len(boss["ring"]) == 2 and
                   (boss["ring"][1] - boss["ring"][0]) % 256 == 128,
                   "kruh bonusu nema krok 256/pocet: %s" % boss["ring"])
            expect(boss["death"]["alive"] is False and boss["death"]["score"] == 0 and
                   boss["death"]["booms"] == ["small", "small"] and
                   boss["death"]["tokens"] == 2,
                   "smrt bosse: 0 bodu, maly EXPL1 + exploze podu, 2 kruhy: %s"
                   % boss["death"])

            # Bonus TOKEN (0x96d8): strela prepina typ (0x9780), dotek
            # hrace sebere (0x97c6). Typ 3 je hlasena ochranna bublina.
            token = page.evaluate("""() => {
              const g = state.g, p = g.player;
              g.scrollMul = 0.000001;
              const mk = typ => {
                const k = { x: 100, y: g.scroll + 100, ang: 64, spd: 0,
                            typ, cycles: 12, blink: false, hitLock: false,
                            dead: false };
                g.tokens = [k]; return k;
              };
              // strela: typ obiha 0->1->2->3->0
              const k = mk(0), cycle = [];
              for (let i = 0; i < 5; i++) { k.hitLock = false; shootToken(g, k);
                                            cycle.push(k.typ); }
              // po dvanacti obehnutich se zamkne na 4
              const k2 = mk(0);
              for (let i = 0; i < 12 * 4; i++) { k2.hitLock = false;
                                                 shootToken(g, k2); }
              const locked = k2.typ;
              // ucinky
              const eff = {};
              p.alive = true; p.inv = 0; p.weapon = 0; p.tokenCount = 0; p.mode = 0;
              p.reload = null; g.score = 0;
              pickupToken(g, mk(3));
              eff.guard = { inv: p.inv, score: g.score };
              p.reload = null;
              pickupToken(g, mk(2));
              eff.rate = p.reload;
              pickupToken(g, mk(4));
              eff.max = { weapon: p.weapon, reload: p.reload };
              p.weapon = 0; p.mode = 0;
              pickupToken(g, mk(0));            // stejny rezim -> +1 sila
              const afterSame = p.weapon;
              pickupToken(g, mk(1));            // jiny rezim -> jen prepnuti
              eff.power = { afterSame, afterSwitch: p.weapon, mode: p.mode };
              // +102 je samostatny HUD citac vsech pickupu, nikoli sila +100.
              const cp = { alive: true, inv: 0, weapon: 0, tokenCount: 0,
                           mode: 0, reload: null };
              const gc = { player: cp, score: 0, nextLife: 10000, lives: 4 };
              for (const typ of [2, 3, 2, 3, 2])
                pickupToken(gc, { typ, dead: false });
              const afterFive = { count: cp.tokenCount, weapon: cp.weapon,
                text: hudStatusText({ lives: 4, player: cp, score: 0 }) };
              for (let i = 0; i < 20; i++)
                pickupToken(gc, { typ: 2, dead: false });
              eff.counter = { afterFive, capped: cp.tokenCount };
              // bonus hrace nezrani: 300 tiku dotyku a hrac zije
              p.inv = 0; p.alive = true; p.x = 100; p.y = 100;
              const kk = mk(1); kk.x = 100; kk.y = g.scroll + 100;
              let hp = true;
              for (let i = 0; i < 5; i++) { step(g); if (!p.alive) hp = false; }
              eff.harmless = hp;
              return { cycle, locked, eff };
            }""")
            expect(token["cycle"] == [1, 2, 3, 0, 1],
                   "strela neprepina typ bonusu po 0x9780: %s" % token["cycle"])
            expect(token["locked"] == 4,
                   "po 12 obehnutich se bonus nezamkl na typ 4: %s"
                   % token["locked"])
            expect(token["eff"]["guard"] == {"inv": 500, "score": 500},
                   "typ 3 nedal 500 tiku ochrany a 500 bodu: %s"
                   % token["eff"]["guard"])
            expect(token["eff"]["rate"] == 8,
                   "typ 2 nezkratil prodlevu palby na 8: %s"
                   % token["eff"]["rate"])
            expect(token["eff"]["max"] == {"weapon": 6, "reload": 8},
                   "typ 4 nedal plnou silu: %s" % token["eff"]["max"])
            expect(token["eff"]["power"]["afterSame"] == 1 and
                   token["eff"]["power"]["afterSwitch"] == 1 and
                   token["eff"]["power"]["mode"] == 1,
                   "sila se ma pridat jen pri shodnem rezimu: %s"
                   % token["eff"]["power"])
            expect(token["eff"]["counter"] == {
                     "afterFive": {"count": 5, "weapon": 0,
                                   "text": "HELI 4[ 3* 0000000"},
                     "capped": 19
                   }, "HUD token counter +102 nesedi nebo neni oddelen od "
                      "sily +100: %s" % token["eff"]["counter"])
            expect(token["eff"]["harmless"] is True,
                   "bonus hrace zranil - nikdy nesmi")

            # docs/TOWN-AUDIT.md P0 1-5: kolizni tridy +504, stit z jadra
            # miny (0x98c4/0x92a0/0x98f2), smart bomba (0x885a), hrac 0x9410
            # (0x9476 rychlost, 0x954c clamp, 0x714e respawn, 0x70c8 tabulka)
            # a sestrelitelna HOMING (0x8578).
            p0 = page.evaluate("""() => {
              const g = state.g, p = g.player, out = {};
              g.scrollMul = 0.000001;
              const reset = () => {
                g.air = []; g.hazards = []; g.shots = []; g.bullets = [];
                g.tokens = []; g.booms = []; g.smartT = 0; g.fadeWhite = 0;
                g.fadeWhiteStep = 0; g.activeCost = 0; g.over = false;
                p.alive = true; p.inv = 0; p.shield = 0; p.orb = null;
                p.respawnT = 0; p.x = 100; p.y = 100; p.cool = 0; g.keys = {};
                g.spawns = g.spawns.filter(s => !s.fake);
                for (const s of g.spawns) if (s.born) s.alive = false;
              };
              const mk = (beh, extra) => {
                const s = Object.assign({ fake: true, file: 'MINE.LIN', idx: 0,
                  beh, born: true, alive: true, armed: false, st: 0, t: 0,
                  x: 100, y: g.scroll + 100, fr: 0, at: 0, hp: 10,
                  scoreValue: 25, cost: 0, budgeted: false, age: 0,
                  emitterSpawned: true }, extra);
                g.spawns.push(s); return s;
              };
              const fod = (x, y) => ({ kind: 'fod', x, y: g.scroll + y, vx: 0,
                vy: 0, ax: 0, ay: 0, alive: true, pending: false, dead: false,
                cost: 0, budgeted: false, hp: 2, scoreValue: 12,
                shooter: false, cool: -1, seq: [2, 3], per: 1, apos: 0,
                at: 0, animFresh: true });
              const core = () => {
                spawnMineCore(g, { x: 100, y: g.scroll + 100 });
                return g.hazards[g.hazards.length - 1];
              };
              // 1. pozemni objekty (trida 36) vrtulnik nezabiji
              out.ground = {};
              for (const [beh, file] of [['mine', 'MINE.LIN'],
                  ['train', 'TRAIN.LIN'], ['flame', 'FLAME.LIN'],
                  ['proxmine', 'PROXMINE.LIN']]) {
                reset(); mk(beh, { file, vx: 0 });
                for (let i = 0; i < 5; i++) step(g);
                out.ground[beh] = p.alive;
              }
              // MILL (trida 34, 10 HP) zabiji a sam dostane -1 HP
              reset();
              const mill = mk('mill', { file: 'MILL.LIN', vy: 0,
                                        scrollLocked: true, st: 1, t: 1000 });
              step(g);
              out.mill = { dead: !p.alive, hp: mill.hp, respawnT: p.respawnT };
              // FODDERA dotek: hrac umre, letec -1 HP
              reset(); g.air.push(fod(100, 100)); step(g);
              out.fod = { dead: !p.alive, hp: g.air[0].hp };
              // ochrana +108 blokuje smrt, letec presto dostane zasah
              reset(); p.inv = 50; g.air.push(fod(100, 100)); step(g);
              out.protectedAlive = p.alive && g.air[0].hp === 1;
              // 2. jadro miny = stit: +106 = -1, jadro 10 snimku stoji, orb
              reset(); g.score = 0;
              const c1 = core(); step(g);
              const afterTouch = { shield: p.shield, pickupT: c1.pickupT,
                                   alive: c1.alive };
              step(g);
              const afterOrb = { shield: p.shield, orb: !!p.orb, inv: p.inv };
              let n = 1; while (c1.alive && n++ < 30) step(g);
              const coreGone = { ticks: n, alive: c1.alive };
              while (p.shield > 1) step(g);
              const lastTick = { shield: p.shield, orb: !!p.orb, inv: p.inv };
              step(g);
              const ended = { shield: p.shield, orb: !!p.orb, inv: p.inv };
              out.shield = { afterTouch, afterOrb, coreGone, lastTick, ended,
                             score: g.score };
              // se stitem dalsi jadro = smart bomba: bila 256, krok -4,
              // 50 snimku; letci a strely zemrou, TOKEN prezije
              reset(); g.score = 0; p.shield = 300; p.orb = { t: 0 };
              g.air.push(fod(200, 50));
              g.tokens.push({ x: 150, y: g.scroll + 150, ang: 0, spd: 0,
                typ: 1, cycles: 12, blink: false, hitLock: false, dead: false });
              g.shots.push({ kind: 'hom', x: 250, y: 60, ang: 64, spd: 0,
                             corr: 0, ct: 8 });
              const c2 = core(); step(g);
              out.smart = { white: g.fadeWhite, whiteStep: g.fadeWhiteStep,
                smartT: g.smartT, core: c2.alive,
                fodAlive: g.air.filter(a => a.alive).length,
                tokens: g.tokens.length, shots: g.shots.length,
                score: g.score, shield: p.shield };
              for (let i = 0; i < 64; i++) step(g);
              out.smartFaded = g.fadeWhite;
              // sestreleni jadra = smart bomba + 30 bodu
              reset(); g.score = 0;
              const c3 = core(); c3.hp = 1;
              g.bullets.push({ x: 100, y: 109 }); step(g);
              out.shootCore = { smartT: g.smartT, score: g.score,
                                alive: c3.alive };
              // 3. hrac: 3 px/t, diagonala z tabulky 0x959e, clamp 4..316/4..248
              reset(); g.keys = { r: true }; step(g);
              const dx = p.x - 100;
              const x0 = p.x, y0 = p.y; g.keys = { r: true, d: true }; step(g);
              out.move = { dx, diag: [p.x - x0, p.y - y0] };
              g.keys = { l: true }; for (let i = 0; i < 60; i++) step(g);
              const clampL = p.x;
              g.keys = { u: true }; for (let i = 0; i < 60; i++) step(g);
              out.clamp = { l: clampL, u: p.y };
              // smrt granatem -> 100 snimku -> respawn s ochranou 200 a
              // tabulkou 0x70c0 (tokenCount 0 -> sila 2, kadence 11)
              reset(); g.lives = 4; p.weapon = 0; p.reload = 5; p.tokenCount = 0;
              g.shots.push({ kind: 'can', x: 100, y: 100, ang: 64, spd: 0,
                             phase: 0, st: 0, accel: false });
              step(g);
              const died = { alive: p.alive, respawnT: p.respawnT,
                             shots: g.shots.length };
              g.shots = [];
              for (let i = 0; i < 99; i++) step(g);
              const before = p.alive;
              step(g);
              out.respawn = { died, before, after: { alive: p.alive,
                inv: p.inv, x: p.x, y: p.y, lives: g.lives,
                reload: p.reload, weapon: p.weapon } };
              // ochrana blika bitem 3 (+108): 200..193 bile, 192..185 ne
              const blink = [];
              for (let i = 0; i < 17; i++) { blink.push(p.flash); step(g); }
              out.blink = blink;
              // start zbrane: sila 2 = dve strely
              reset(); p.weapon = 2; p.reload = 11; g.keys = { f: true };
              step(g);
              out.bolts = g.bullets.length;
              // 4. HOMING sestrelitelna (7 bodu), granat ne
              reset(); g.score = 0;
              g.shots.push({ kind: 'hom', x: 200, y: 50, ang: 64, spd: 0,
                             corr: 0, ct: 8 });
              g.shots.push({ kind: 'can', x: 250, y: 50, ang: 64, spd: 0,
                             phase: 0, st: 0, accel: false });
              g.bullets.push({ x: 200, y: 58 }, { x: 250, y: 58 });
              step(g);
              out.homing = { shots: g.shots.map(s => s.kind), score: g.score,
                             bullets: g.bullets.length };
              reset(); g.lives = 4;
              return out;
            }""")
            expect(all(p0["ground"].values()),
                   "pozemni objekt zabil vrtulnik: %s" % p0["ground"])
            expect(p0["mill"] == {"dead": True, "hp": 9, "respawnT": 100},
                   "MILL (trida 34) nezabil nebo nedostal zasah: %s" % p0["mill"])
            expect(p0["fod"] == {"dead": True, "hp": 1},
                   "FODDERA dotek: %s" % p0["fod"])
            expect(p0["protectedAlive"] is True,
                   "ochrana +108 neblokovala smrt nebo letec nedostal zasah")
            sh = p0["shield"]
            expect(sh["afterTouch"] == {"shield": -1, "pickupT": 10, "alive": True},
                   "jadro miny nenastavilo +106 = -1 a nezmrazilo se: %s"
                   % sh["afterTouch"])
            expect(sh["afterOrb"] == {"shield": 500, "orb": True, "inv": 0},
                   "orb 0x98f2 / +106 = 500 nesedi: %s" % sh["afterOrb"])
            expect(sh["coreGone"]["alive"] is False and sh["coreGone"]["ticks"] == 10,
                   "jadro ma zmizet po 10 snimcich: %s" % sh["coreGone"])
            # 0x92ac nastavi +108 = 100 jeste v tiku, kdy +106 klesne na 0,
            # a 0x92d8 hned odecte tik -> 99.
            expect(sh["lastTick"] == {"shield": 1, "orb": True, "inv": 99} and
                   sh["ended"] == {"shield": 0, "orb": False, "inv": 99},
                   "konec stitu: orb ma zmizet a +108 dobihat od 100: %s / %s"
                   % (sh["lastTick"], sh["ended"]))
            expect(sh["score"] == 0, "sebrani jadra nema davat body")
            sm = p0["smart"]
            expect(sm["white"] == 256 and sm["whiteStep"] == -4 and
                   sm["smartT"] == 49 and sm["core"] is False,
                   "smart bomba po druhem jadru: %s" % sm)
            expect(sm["fodAlive"] == 0 and sm["shots"] == 0 and
                   sm["tokens"] == 1 and sm["score"] == 12,
                   "smart bomba ma zabit letce a strely s body, TOKEN ne: %s" % sm)
            expect(p0["smartFaded"] == 0, "bila po 64 snimcich nedoznela")
            expect(p0["shootCore"] == {"smartT": 49, "score": 30, "alive": False},
                   "sestreleni jadra: %s" % p0["shootCore"])
            mv = p0["move"]
            expect(abs(mv["dx"] - 3) < 1e-6 and
                   abs(mv["diag"][0] - 2.1213) < 0.01 and
                   abs(mv["diag"][1] - 2.1213) < 0.01,
                   "hrac nejede 3 px/t podle 0x959e/0x65f2: %s" % mv)
            expect(p0["clamp"] == {"l": 4, "u": 4},
                   "clamp hrace neni 4..316 / 4..248: %s" % p0["clamp"])
            rs = p0["respawn"]
            expect(rs["died"] == {"alive": False, "respawnT": 100, "shots": 1} and
                   rs["before"] is False and
                   # 0x9424 da 200, prvni 0x92a0 tehoz tiku odecte -> 199
                   rs["after"] == {"alive": True, "inv": 199, "x": 160, "y": 192,
                                   "lives": 3, "reload": 11, "weapon": 2},
                   "respawn po 100 snimcich s ochranou 200 a tabulkou 0x70c0: %s"
                   % rs)
            # +108 = 199..192 ma bit 3 nulovy, 191..184 nastaveny
            expect(p0["blink"] == [False] * 8 + [True] * 8 + [False],
                   "blikani ochrany neni 8/8 podle bitu 3: %s" % p0["blink"])
            expect(p0["bolts"] == 2, "start ma byt 2 strely (+100 = 2): %s"
                   % p0["bolts"])
            expect(p0["homing"] == {"shots": ["can"], "score": 7, "bullets": 1},
                   "HOMING ma byt sestrelitelna za 7 bodu, granat ne: %s"
                   % p0["homing"])

            summary = page.evaluate("""() => ({
              dispatch: state.behaviorDispatch.size,
              mapObjects: state.mapMeta.objects,
              spawns: state.g.spawns.length,
              lives: state.g.lives,
              hudTexts: [
                hudStatusText({ lives: 4, player: { tokenCount: 0 }, score: 0 }),
                hudStatusText({ lives: 12, player: { tokenCount: 5 }, score: 9 }),
                hudStatusText({ lives: 4, player: { tokenCount: 0 }, score: 10000 }),
                hudStatusText({ lives: 4, player: { tokenCount: 0 }, score: 99999 })
              ],
              behaviors: state.g.spawns.reduce((counts, s) => {
                counts[s.beh] = (counts[s.beh] || 0) + 1;
                return counts;
              }, {}),
              missing: state.g.spawns.filter(s => s.coroutine === null).length,
              camoguns: state.g.spawns.filter(s => s.beh === 'camogun').length,
              camType1: state.g.spawns.filter(s => s.beh === 'camogun' &&
                                               s.typ === 1).length,
              camType2: state.g.spawns.filter(s => s.beh === 'camogun' &&
                                               s.typ === 2).length,
              wrongCam: state.g.spawns.filter(s => s.beh === 'camogun' &&
                                                s.coroutine !== 0xac12).length,
              animActual: [0xA6E8, 0xA72A, 0xC7FC, 0xC82E, 0xCAE2]
                .filter(o => state.anims.some(a => a.offset === o)).length,
              animFalse: [0xA6E6, 0xA728, 0xC7FA, 0xC82C, 0xCAE0]
                .filter(o => state.anims.some(a => a.offset === o)).length
            })""")
            expect(summary["dispatch"] == 73, "dispatch nema 73 zaznamu")
            expect(summary["mapObjects"] == 155, "TOWN nema 155 mapovych objektu")
            expect(summary["lives"] == 4 and summary["hudTexts"] == [
                     "HELI 4[ 2* 0000000", "HELI 12[ 3* 0000090",
                     "HELI 4[ 2* 0100000", "HELI 4[ 2* 0999990"
                   ], "HUD nema nativni lives/weapon/score x10 format: %s" %
                   summary["hudTexts"])
            expected_behaviors = {"wave": 60, "yellow": 12, "bird": 9,
                                  "popup": 6, "mine": 6, "proxmine": 13,
                                  "train": 3, "mill": 2, "tank": 18, "roto": 9,
                                  "flame": 6, "camogun": 10,
                                  "boss": 1}
            expect(summary["spawns"] == 155 and
                   summary["behaviors"] == expected_behaviors,
                   "TOWN nema spravnych 155 routovanych runtime spawnu")
            expect(summary["missing"] == 0, "TOWN obsahuje objekt bez dispatche")
            expect(summary["camoguns"] == 10, "TOWN nema 10 CAMOGUN vezi")
            expect(summary["camType1"] == 5 and summary["camType2"] == 5,
                   "CAMOGUN nema pet dvojic TYP 1/2")
            expect(summary["wrongCam"] == 0, "CAMOGUN nema korutinu 0xac12")
            expect(summary["animActual"] == 5 and summary["animFalse"] == 0,
                   "JS animscan zacina v BSR.W displacementu: %s" % summary)

            exact_anim = page.evaluate("""() => {
              const savedRandom = Math.random;
              Math.random = () => 0;
              try {
                const game = spawns => ({
                  tick: 0, scroll: 100, scrollMul: 1e-9,
                  over: false, won: false,
                  player: { x: 0, y: 0, alive: false }, keys: {},
                  bullets: [], shots: [], plops: [], spawns,
                  booms: [], effects: [], air: [], hazards: [], tokens: [],
                  players: 1, activeCost: 0, score: 0,
                  nextLife: 10000, lives: 3, flash: 0,
                  fadeBlack: 0, fadeWhite: 0, fadeDir: 0,
                  fadeWhiteStep: 0
                });

                // Stejna x (tedy i parita) dokazuje, ze smer neurcuje poloha.
                // Oba objekty se aktivuji ve stejnem tiku v poradi mapoveho pole.
                const rotos = [0, 1].map(() => ({
                  born: false, armed: true, alive: true, beh: 'roto',
                  file: 'ROTOBASE.LIN', idx: 4, x: 101, y: 100,
                  typ: 0, anim: null, at: 0, fr: -1
                }));
                const gr = game(rotos);
                gr.rotoDirectionWord = 0;
                const rotoFrames = [[], []];
                for (let i = 0; i < 7; i++) {
                  step(gr);
                  rotoFrames[0].push(rotos[0].fr);
                  rotoFrames[1].push(rotos[1].fr);
                }

                const popup = {
                  born: true, armed: true, alive: true, beh: 'popup',
                  file: 'POPUP.LIN', idx: 0, x: 160, y: 100,
                  typ: 0, anim: null, st: 0, t: 1, fr: 0,
                  hp: 3, alt: false
                };
                const gp = game([popup]);
                // t0 je tik, kdy se opening animator pripoji. Sledujeme
                // celou 1P sekvenci az po KILL zaviraciho skriptu na t162.
                const popupTimeline = [];
                for (let i = 0; i <= 162; i++) {
                  step(gp);
                  popupTimeline.push({ frame: popup.fr, wait: popup.t,
                                       state: popup.st, alive: popup.alive });
                }

                const gplop = game([]);
                fireHoming(gplop, 80, 90, 64);
                const plopState = () => {
                  const pl = gplop.plops[0];
                  if (!pl) return null;
                  const graphic = PLOP_SEQUENCE[pl.t];
                  return { t: pl.t, file: graphic && graphic[0],
                           frame: graphic && graphic[1] };
                };
                const plop = [plopState()];
                step(gplop); plop.push(plopState());
                step(gplop); plop.push(plopState());

                // Lichy globalni tick by stary renderer donutil novou strelu
                // zacit druhou fazi. Original vzdy zacina vlastni fazi 0.
                const gcannon = game([]);
                gcannon.tick = 41;
                fireCannon(gcannon, 80, 80, 0, true, false);
                const cannonState = () => gcannon.shots.map(s =>
                  [cannonFrameFor(s), s.phase, s.accel]);
                const cannon = [cannonState()];
                step(gcannon); cannon.push(cannonState());
                fireCannonStraight(gcannon, 80, 100, 0);
                cannon.push(cannonState());
                step(gcannon); cannon.push(cannonState());
                step(gcannon); cannon.push(cannonState());

                // Pet pohybu jeste pouzije 0.5 px/t; zvysena rychlost 1.0
                // se projevi az sestym pohybem po okamzitem 16px kroku.
                const gaccel = game([]);
                fireCannon(gaccel, 80, 80, 0, true, false);
                const accel = [[gaccel.shots[0].x, gaccel.shots[0].spd]];
                for (let i = 0; i < 6; i++) {
                  step(gaccel);
                  accel.push([gaccel.shots[0].x, gaccel.shots[0].spd]);
                }

                // fp@(206) zacina na 4 a kazdy spawn jej snizi. Hodnoty
                // 4..0 dovoli pet kusu; pri -1 0x95d2 preskoci i PLOP.
                const gbudget = game([]);
                gbudget.player = { x: 160, y: 200, alive: true };
                const accepted = [];
                for (let i = 0; i < 5; i++)
                  accepted.push(fireCannon(gbudget, 80, 80, 0));
                const rejected = fireCannon(gbudget, 80, 80, 0);
                fireCannonAimed(gbudget, 80, 80);
                const budget = { accepted, rejected,
                                 shots: gbudget.shots.length,
                                 plops: gbudget.plops.length };

                return {
                  roto: {
                    xs: rotos.map(s => s.x), dirs: rotos.map(s => s.sd),
                    frames: rotoFrames, word: gr.rotoDirectionWord
                  },
                  popup: popupTimeline,
                  plop, cannon, accel, budget
                };
              } finally { Math.random = savedRandom; }
            }""")
            expect(exact_anim["roto"]["xs"] == [101, 101] and
                   exact_anim["roto"]["dirs"] == [-1, 1] and
                   exact_anim["roto"]["word"] == 0,
                   "ROTOBASE nestrida smer globalne podle poradi aktivace: %s"
                   % exact_anim["roto"])
            expect(exact_anim["roto"]["frames"] ==
                   [[4, 11, 11, 10, 10, 9, 9],
                    [4, 4, 4, 5, 5, 6, 6]],
                   "ROTOBASE nema oba smerove skripty s periodou 2: %s"
                   % exact_anim["roto"]["frames"])

            popup = exact_anim["popup"]
            expect(popup[0] == {"frame": 0, "wait": 50,
                                "state": 2, "alive": True},
                   "POPUP t0 nepripojil opening soubezne s wait(50): %s"
                   % popup[0])
            expect([row["frame"] for row in popup[1:43]] ==
                   sum(([frame] * 6 for frame in range(1, 8)), []),
                   "POPUP otevreni 1..7 nema periodu 6")
            expect([row["frame"] for row in popup[43:50]] == [7] * 7 and
                   popup[42]["wait"] == 8 and popup[49]["wait"] == 1,
                   "POPUP nema opening soubezny s puvodnim 50tikovym waitem")
            expect([row["frame"] for row in popup[50:55]] == [8] * 5 and
                   [row["frame"] for row in popup[55:126]] == [7] * 71,
                   "POPUP nema presnou palebnou/povystrelovou casovou osu")
            expect([row["frame"] for row in popup[126:162]] ==
                   sum(([frame] * 6 for frame in range(6, 0, -1)), []),
                   "POPUP zavreni 6..1 nema periodu 6")
            expect(popup[125]["state"] == 5 and popup[125]["alive"] is True and
                   popup[161]["alive"] is True and
                   popup[162]["alive"] is False,
                   "POPUP closing 0xa72a neskoncil KILL na t162")
            expect(exact_anim["plop"] ==
                   [{"t": 0, "file": "PLOP.LIN", "frame": 0},
                    {"t": 1, "file": "BULLET.LIN", "frame": 2},
                    None],
                   "PLOP nema presnou dvoutikovou cross-file sekvenci: %s"
                   % exact_anim["plop"])
            expect(exact_anim["cannon"] ==
                   [[[24, 0, True]],
                    [[40, 1, True]],
                    [[40, 1, True], [24, 0, False]],
                    [[24, 0, True], [40, 1, False]],
                    [[40, 1, True], [24, 0, False]]],
                   "granaty nemaji vlastni fazi 24/40 pro accel i straight: %s"
                   % exact_anim["cannon"])
            expect(exact_anim["accel"] ==
                   [[96, 0.5], [96.5, 0.5], [97, 0.5], [97.5, 0.5],
                    [98, 0.5], [98.5, 1], [99.5, 1]],
                   "granat nepouziva novou rychlost az po patem pohybu: %s"
                   % exact_anim["accel"])
            expect(exact_anim["budget"] ==
                   {"accepted": [True] * 5, "rejected": False,
                    "shots": 5, "plops": 0},
                   "plny cannon budget nevypnul strelu i PLOP: %s"
                   % exact_anim["budget"])

            dynamics = page.evaluate("""() => {
              const savedRandom = Math.random;
              Math.random = () => 0;
              try {
                const gb = { air: [], players: 1, activeCost: 160, scroll: 149 };
                spawnBirdFormation(gb, { x: 20, y: 100 });
                const bird = gb.air;
                const birdBefore = activateAirMember(gb, bird[0], { x: 0 });
                gb.scroll = 148;
                const birdAt = activateAirMember(gb, bird[0], { x: 0 });
                const birdCost = gb.activeCost, birdVy = bird[0].vy;
                releaseAirMember(gb, bird[0]);
                const birdAnim = [];
                const ba = { ...bird[1], apos: 0, at: 0, animFresh: true };
                for (let i = 0; i < 24; i++) {
                  advanceAirAnim(ba); birdAnim.push(ba.seq[ba.apos]);
                }

                const gm = { activeCost: 7, hazards: [], effects: [], booms: [],
                             score: 0, nextLife: 10000, lives: 3 };
                const mine = { x: 90, y: 120, alive: true, cost: 7,
                               budgeted: true };
                detonateMine(gm, mine, true);
                detonateMine(gm, mine, true); // idempotence
                const core = gm.hazards[0];

                const gp = { activeCost: 10, hazards: [], effects: [], booms: [],
                             score: 0, nextLife: 10000, lives: 3, scroll: 0,
                             player: { x: 100, y: 100, alive: true } };
                const prox = { x: 0, y: 0, alive: true, cost: 10,
                               budgeted: true, proxAlternate: false };
                detonateProx(gp, prox);
                const base = angTo(0, 0, 100, 100);

                const gt = { activeCost: 0, hazards: [] };
                const loco = { x: -48, y: 80, vx: 1, alive: true,
                               cost: 15, budgeted: false };
                reserveCost(gt, loco); spawnTrainCars(gt, loco, 4);

                const gf = { activeCost: 0, hazards: [] };
                const flame = { x: 40, y: 50, alive: true,
                                cost: 10, budgeted: false };
                reserveCost(gf, flame); spawnFlameEmitter(gf, flame);
                const emitter = gf.hazards[0]; spawnFlamePuff(gf, emitter);
                const gx = { booms: [] };
                spawnBoom(gx, 0, 0); spawnBoom(gx, 0, 0, 'player');
                spawnBoom(gx, 0, 0, 'big');
                const gbx = { booms: [] };
                spawnPlayerBurst(gbx, 100, 200, 192);
                const burstAges = gbx.booms.map(b => b.t);
                for (const b of gbx.booms) b.t++;
                const burstAfterTick = gbx.booms.map(b => b.t);
                const gmb = { activeCost: 160 }, millBudgetObj = {};
                initMill(gmb, millBudgetObj);
                const millOverCap = gmb.activeCost;
                releaseCost(gmb, millBudgetObj);

                const gs = {
                  tick: 0, scroll: 100, scrollMul: 1, over: false, won: false,
                  player: { alive: false }, keys: {}, bullets: [], shots: [],
                  plops: [], spawns: [], booms: [], effects: [], tokens: [],
                  air: [{ kind: 'bird', x: 10, y: 100, vx: 0, vy: 1,
                          alive: true, pending: false, dead: false,
                          cost: 10, budgeted: true, hp: 2, scoreValue: 55,
                          seq: [0,1,2,3,2,1], per: 4, apos: 0, at: 0,
                          animFresh: false }],
                  hazards: [{ kind: 'minecore', file: 'MINE.LIN', x: 20, y: 100,
                              vx: 0, vy: .5, scrollLocked: true,
                              alive: true, dead: false, cost: 5, budgeted: true,
                              hp: 10, scoreValue: 30, seq: [9,10], per: 1,
                              apos: 0, at: 0 }],
                  activeCost: 15, score: 0, nextLife: 10000, lives: 3
                };
                step(gs);

                const gmi = {
                  tick: 0, scroll: 100, scrollMul: 1, over: false, won: false,
                  player: { alive: false }, keys: {}, bullets: [], shots: [],
                  plops: [], air: [], hazards: [], booms: [], effects: [],
                  tokens: [],
                  activeCost: 15, score: 0, nextLife: 10000, lives: 3,
                  spawns: [{ born: true, alive: true, beh: 'mill',
                             file: 'MILL.LIN', idx: 0, fr: 0,
                             x: 100, y: 123.5, vy: .5, scrollLocked: false,
                             st: 0, rotorTick: 0, rotorFresh: true,
                             cost: 15, budgeted: true, hp: 10,
                             scoreValue: 70 }]
                };
                step(gmi);
                const millLockedSy = gmi.spawns[0].y - gmi.scroll;
                step(gmi);
                const millMovedSy = gmi.spawns[0].y - gmi.scroll;
                for (let i = 0; i < 98; i++) step(gmi);
                const millBefore = gmi.shots.length;
                step(gmi);

                const gu = {
                  tick: 0, scroll: 1000, scrollMul: 1, over: false, won: false,
                  player: { x: 160, y: 200, alive: true, inv: 1000,
                            bank: 0, cool: 0, weapon: 0 }, keys: {},
                  bullets: [], shots: [], plops: [], air: [], hazards: [],
                  booms: [], effects: [], tokens: [], activeCost: 0, score: 0,
                  nextLife: 10000, lives: 3,
                  spawns: [{ born: true, alive: true, beh: 'unimplemented',
                             file: 'GOOSE.LIN', idx: 0, x: 100, y: 1100,
                             anim: null, at: 0 }]
                };
                for (let i = 0; i < 300; i++) step(gu);

                return {
                  birdPos: bird.map(a => [a.x, a.y]), birdBefore, birdAt,
                  birdCost, birdReleased: gb.activeCost, birdVy, birdAnim,
                  mine: { alive: mine.alive, score: gm.score,
                          booms: gm.booms.length, effects: gm.effects.length,
                          persistent: gm.effects[0] && gm.effects[0].life === Infinity,
                          cores: gm.hazards.length,
                          cost: gm.activeCost, core: core && {
                            x: core.x, y: core.y, hp: core.hp, vy: core.vy,
                            seq: core.seq, per: core.per } },
                  prox: { alive: prox.alive, score: gp.score,
                          booms: gp.booms.length, cost: gp.activeCost,
                          count: gp.hazards.length,
                          angles: gp.hazards.map(h => h.ang),
                          speeds: gp.hazards.map(h => Math.hypot(h.vx, h.vy)),
                          expected: Array.from({length: 6},
                            (_, k) => (base + 21 + 42 * k) & 255) },
                  train: { count: gt.hazards.length,
                           xs: gt.hazards.map(h => h.x),
                           frames: gt.hazards.map(h => h.frame),
                           cost: gt.activeCost },
                  flame: { emitterX: emitter.x, emitterPer: emitter.per,
                           emitterSeq: emitter.seq, puff: gf.hazards[1] && {
                             vx: gf.hazards[1].vx, life: gf.hazards[1].life,
                             seq: gf.hazards[1].seq, per: gf.hazards[1].per },
                           cost: gf.activeCost },
                  boomLives: gx.booms.map(boomLife),
                  burst: { count: gbx.booms.length, ages: burstAges,
                           afterTick: burstAfterTick,
                           first: [gbx.booms[0].x, gbx.booms[0].y],
                           last: [gbx.booms[15].x, gbx.booms[15].y] },
                  locked: { birdSy: gs.air[0].y - gs.scroll,
                            coreSy: gs.hazards[0].y - gs.scroll },
                  mill: { locked: gmi.spawns[0].scrollLocked,
                          lockedSy: millLockedSy, movedSy: millMovedSy,
                          before: millBefore, shots: gmi.shots.length,
                          angles: gmi.shots.map(s => s.ang).sort((a,b) => a-b),
                          overCap: millOverCap, released: gmb.activeCost },
                  fallbackShots: gu.shots.length
                };
              } finally { Math.random = savedRandom; }
            }""")
            expect(dynamics["birdPos"] == [[20, 100], [52, 96], [84, 92], [116, 88]] and
                   dynamics["birdBefore"] is False and dynamics["birdAt"] is True and
                   dynamics["birdCost"] == 170 and dynamics["birdReleased"] == 160 and
                   dynamics["birdVy"] == 1,
                   "BIRD nema presnou 4clennou formaci/aktivaci/budget")
            expect(dynamics["birdAnim"] ==
                   [0] * 4 + [1] * 4 + [2] * 4 + [3] * 4 + [2] * 4 + [1] * 4,
                   "BIRD nema period4 flap sekvenci")
            expect(dynamics["mine"] == {
                       "alive": False, "score": 25, "booms": 1, "effects": 1,
                       "persistent": True, "cores": 1,
                       "cost": 5, "core": {"x": 90, "y": 120, "hp": 10,
                                             "vy": 0.5, "seq": [9, 10], "per": 1}},
                   "MINE nevytvorila prave jedno pohyblive jadro")
            expect(dynamics["prox"]["alive"] is False and
                   dynamics["prox"]["score"] == 0 and
                   dynamics["prox"]["booms"] == 1 and
                   dynamics["prox"]["count"] == 6 and
                   dynamics["prox"]["cost"] == 30 and
                   dynamics["prox"]["angles"] == dynamics["prox"]["expected"] and
                   all(abs(v - 2.5) < 1e-9 for v in dynamics["prox"]["speeds"]),
                   "PROXMINE nema sest strepu po 42 stupnich rychlosti 2.5")
            expect(dynamics["train"] == {"count": 4,
                                           "xs": [-96, -144, -192, -240],
                                           "frames": [1, 1, 1, 1], "cost": 75},
                   "TRAIN TYP4 nema lokomotivu + ctyri vagony po 48 px")
            expect(dynamics["flame"]["emitterX"] == 52 and
                   dynamics["flame"]["emitterPer"] == 2 and
                   dynamics["flame"]["puff"] == {
                       "vx": 2.5, "life": 35, "seq": [5,6,7,8,9,10,11], "per": 5} and
                   dynamics["flame"]["cost"] == 21,
                   "FLAME nema linked emitter a 35tikovy puff")
            expect(dynamics["boomLives"] == [28, 28, 42],
                   "typovane exploze nemaji originalni delku")
            expect(dynamics["burst"]["count"] == 16 and
                   dynamics["burst"]["ages"] == list(range(-1, -32, -2)) and
                   dynamics["burst"]["afterTick"] == list(range(0, -31, -2)) and
                   dynamics["burst"]["first"] == [100, 200] and
                   dynamics["burst"]["last"] == [65, 171],
                   "smrt hrace nema 16 dilu EXPL1 s presnym rozptylem")
            expect(abs(dynamics["locked"]["birdSy"] - 1) < 1e-9 and
                   abs(dynamics["locked"]["coreSy"] - 0.5) < 1e-9,
                   "airborne bit4 nepricetl zpet camera-scroll deltu")
            expect(dynamics["mill"]["locked"] is True and
                   abs(dynamics["mill"]["movedSy"] -
                       dynamics["mill"]["lockedSy"] - 0.5) < 1e-9 and
                   dynamics["mill"]["before"] == 0 and
                   dynamics["mill"]["shots"] == 8 and
                   dynamics["mill"]["overCap"] == 175 and
                   dynamics["mill"]["released"] == 160 and
                   (dynamics["mill"]["angles"] == list(range(0, 256, 32)) or
                    dynamics["mill"]["angles"] == list(range(16, 256, 32))),
                   "MILL nema wait100 a osm smeru palby po 32 stupnich")
            expect(dynamics["fallbackShots"] == 0,
                   "neprelozeny fallback stale strili vymyslene granaty")

            cam = page.evaluate("""() => {
              const g = state.g;
              const s = g.spawns.find(o => o.beh === 'camogun');
              if (!s) return null;
              g.spawns = [s];
              g.shots = []; g.bullets = []; g.air = [];
              g.booms = []; g.score = 0;
              g.player.alive = false;
              g.scrollMul = 0.000001;
              s.born = false; s.armed = true; s.alive = true; s.quiet = false;
              s.y = g.scroll + 100;
              const y0 = s.y;

              // Aktivacni tik se do wait(100) nepocita.
              step(g);
              const activated = { born: s.born, wait: s.t, shots: g.shots.length,
                                  hp: s.hp, score: s.scoreValue };
              for (let i = 0; i < 99; i++) step(g);
              const before = { wait: s.t, shots: g.shots.length };
              step(g);
              const shot = g.shots[0];
              const first = { shots: g.shots.length, y: s.y - y0, frame: s.fr,
                              kind: shot && shot.kind, speed: shot && shot.spd,
                              angle: shot && shot.ang, accel: shot && shot.accel,
                              shotX: shot && shot.x, shotY: shot && shot.y };
              const recoil = [{ y: first.y, frame: first.frame }];
              step(g);
              const moved = { dx: shot.x - first.shotX, dy: shot.y - first.shotY };
              recoil.push({ y: s.y - y0, frame: s.fr });
              for (let i = 0; i < 6; i++) {
                step(g);
                recoil.push({ y: s.y - y0, frame: s.fr });
              }
              const settled = { y: s.y - y0, state: s.st, wait: s.t, frame: s.fr };

              // Dva zasahy: prvni vez prezije, druhy prida presne 40 bodu.
              g.shots = []; g.bullets = []; g.booms = [];
              s.alive = true; s.born = true; s.st = 0; s.t = 1000;
              s.y = g.scroll + 100; s.fr = 0; s.hp = 2;
              const spr = sprite(s.file, s.idx);
              const hit = () => {
                const sy = s.y - g.scroll;
                g.bullets = [{ x: s.x + spr.ox + spr.w / 2,
                               y: sy + spr.oy + spr.h / 2 + 9 }];
                step(g);
                return { hp: s.hp, alive: s.alive, score: g.score };
              };
              const hit1 = spr && hit();
              const hit2 = spr && hit();
              return { activated, before, first, moved, recoil, settled, hit1, hit2 };
            }""")
            expect(cam is not None, "CAMOGUN se nepodarilo najit")
            expect(cam["activated"] == {"born": True, "wait": 100, "shots": 0,
                                         "hp": 2, "score": 40},
                   "CAMOGUN nema spravnou aktivaci/HP/body")
            expect(cam["before"] == {"wait": 1, "shots": 0},
                   "CAMOGUN nevydrzel cely wait(100)")
            expect(cam["first"]["shots"] == 1, "CAMOGUN nevystrelil presne jednou")
            expect(cam["first"]["kind"] == "can", "CAMOGUN nevytvoril granat")
            expect(cam["first"]["speed"] == 5 and cam["first"]["accel"] is False,
                   "CAMOGUN granat nema konstantnich 5 px/t")
            expect(cam["first"]["angle"] == 64, "CAMOGUN nestrili primo dolu")
            expect(cam["first"]["frame"] == 1 and abs(cam["first"]["y"] - 7) < 1e-6,
                   "CAMOGUN nema prvni frame a recoil 7 px po prvnim tiku")
            expect(abs(cam["moved"]["dx"]) < 1e-6 and
                   abs(cam["moved"]["dy"] - 5) < 1e-6,
                   "CAMOGUN granat se nepohybuje konstantne 5 px/t dolu")
            expect([round(row["y"]) for row in cam["recoil"]] ==
                   [7, 6, 5, 4, 3, 2, 1, 0] and
                   [row["frame"] for row in cam["recoil"]] ==
                   [1, 1, 1, 0, 0, 0, 0, 0],
                   "CAMOGUN nema presnou 8tikovou recoil/anim sekvenci")
            settled = cam["settled"]
            expect(abs(settled["y"]) < 1e-6 and settled["state"] == 0 and
                   settled["wait"] == 100,
                   "CAMOGUN se po osmi recoil ticich nevratil do cekani")
            expect(settled["frame"] == 0, "CAMOGUN nevratil animaci na frame 0")
            expect(cam["hit1"] == {"hp": 1, "alive": True, "score": 0},
                   "CAMOGUN neprezil prvni zasah")
            expect(cam["hit2"] == {"hp": 0, "alive": False, "score": 40},
                   "CAMOGUN po druhem zasahu nepridal 40 bodu")

            screenshot = os.environ.get("SWIV_UI_SCREENSHOT")
            if screenshot:
                page.screenshot(path=screenshot)
            expect(not errors, "browser ohlasil chyby: " + "; ".join(errors[:6]))
            print("UI OK (%.1fs): %d dispatch zaznamu, %d CAMOGUN, bez JS chyb" %
                  (time.time() - started, summary["dispatch"], summary["camoguns"]))
        finally:
            browser.close()


if __name__ == "__main__":
    main()
