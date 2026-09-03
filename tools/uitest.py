#!/usr/bin/env python3
"""End-to-end attract, renderer, audio a behavior regrese v realnem Chromiu.

Projde tok vlozeni ADF -> nativni attract -> fire -> TOWN, overi puvodni dispatch
tabulku, palety, formace, miny, vlak, plamenomet, animace ROTOBASE/POPUP
a cyklus CAMOGUN.
Pri chybe nebo nesplnene podmince skonci nenulovym navratovym kodem.

    python3 tools/uitest.py
"""

from playwright.sync_api import sync_playwright
import hashlib
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

            # Zastavime wall-clock RAF a attract i hru pak overujeme ciste
            # po jednotlivych 50Hz krocich.
            page.evaluate("window.requestAnimationFrame = () => 0")
            intro_core = page.evaluate("""() => {
              const fnv1a = bytes => {
                let h = 0x811C9DC5;
                for (const value of bytes)
                  h = Math.imul((h ^ value) >>> 0, 0x01000193) >>> 0;
                return h.toString(16).padStart(8, '0');
              };
              const rawNames = [
                'COVER.RAW', 'MUSHROOM.RAW', 'FACES.RAW',
                'HELIBP1.RAW', 'HELIBP2.RAW',
                'JEEPBP1.RAW', 'JEEPBP2.RAW'
              ];
              const rawHashes = Object.fromEntries(rawNames.map(name =>
                [name, fnv1a(introRaw(name).pixels)]));
              const blueprintIndex8 = Object.fromEntries(
                rawNames.slice(3).map(name => [name,
                  Array.from(introRaw(name).pixels).filter(v => v === 8).length]));

              const streamCases = [
                [0x15F4, 180, 86], [0x16A2, 180, 137],
                [0x17B4, 180, 86], [0x1856, 180, 137],
                [0x1906, 16, 196]
              ];
              const streamEnds = [], streamEndVbls = [];
              for (const [offset, x, y] of streamCases) {
                const pixels = new Uint8Array(320 * 256);
                const mask = new Uint8Array(320 * 256);
                const task = createBlueprintTextTask(
                  state.prog, offset, x, y, pixels, mask);
                let guard = 4000, vbl = 0;
                while (!task.done && guard-- > 0) {
                  resumeBlueprintTextTask(task);
                  if (!task.done) vbl++;
                }
                streamEnds.push(task.done ? task.end + 1 : -1);
                streamEndVbls.push(task.done ? vbl : -1);
              }

              const pal0 = blueprintPaletteAt(state.prog, 0);
              const pal8 = blueprintPaletteAt(state.prog, 8);
              const pal48 = blueprintPaletteAt(state.prog, 48);
              const pal78 = blueprintPaletteAt(state.prog, 78);
              const highScoreCounts = [];
              for (let i = 1; i <= 16; i++)
                highScoreCounts.push(parseHighScoreNames(
                  introFileBytes('HS' + i + '.TXT')).length);

              const live = state.attract;
              const blueprintTiming = index => {
                prepareAttractScene(live, index);
                const scene = live.scene, phases = {};
                let activation = 0, allTextDoneAt = null,
                    revealedAt = null, taskStartedAt = null,
                    firstTaskOffsets = null, guard = 1000;
                while (live.scene === scene && guard-- > 0) {
                  const phase = live.phase;
                  phases[phase] = (phases[phase] || 0) + 1;
                  stepAttract(live);
                  if (revealedAt === null && live.blueprintRevealed)
                    revealedAt = activation + 1;
                  if (taskStartedAt === null && live.blueprintTaskStarted) {
                    taskStartedAt = activation + 1;
                    firstTaskOffsets = live.blueprintTasks.map(
                      task => task.p - task.start);
                  }
                  if (allTextDoneAt === null && live.blueprintTasks &&
                      live.blueprintTasks.every(task => task.done))
                    allTextDoneAt = activation;
                  activation++;
                }
                return { phases, allTextDoneAt, next: live.scene,
                         nextPhase: live.phase, activations: activation,
                         revealedAt, taskStartedAt, firstTaskOffsets };
              };
              const blueprintTimings = [blueprintTiming(2), blueprintTiming(4)];
              const repeatedHeliTiming = blueprintTiming(2);
              prepareAttractScene(live, 0); live.vbl = 0;
              live.phase = 'hold'; live.phaseTick = 0; renderAttract(live);
              return {
                order: Array.from(ATTRACT_SCENE_ORDER),
                holds: Object.assign({}, ATTRACT_HOLD_VBLS),
                fades: Array.from(ATTRACT_FADE_LEVELS),
                colorStarts: Array.from(BLUEPRINT_COLOR_STARTS),
                rawHashes, blueprintIndex8, streamEnds, streamEndVbls,
                highScoreCounts,
                highScoreFiles: [
                  introHighScoreFile('heli', 0), introHighScoreFile('heli', 7),
                  introHighScoreFile('jeep', 0), introHighScoreFile('jeep', 7)
                ],
                hud: [0, 127, 128, 255, 256].map(attractHudTexts),
                paletteCheckpoints: {
                  zero: [pal0[1], pal0[9]],
                  eight: [pal8[2], pal8[10]],
                  fortyEight: [pal48[7], pal48[15]],
                  seventyEight: [pal78[1], pal78[8], pal78[15]]
                },
                copperCounts: {
                  cover: introCopperEvents('cover').length,
                  sales: introCopperEvents('sales').length,
                  faces: introCopperEvents('faces').length,
                  scores: introCopperEvents('heliScores').length
                },
                salesGradient: decodeIntroCopperTable(
                  state.prog, 0x2BFF, 48).map(e =>
                    [e.line, e.color, e.word]),
                sales: programCString(state.prog, 0x2400),
                faces: programCString(state.prog, 0x2232),
                blueprintTimings,
                repeatedHeliTiming,
                blueprintScoreBlack: attractPaletteAndFade({
                  scene: 'heliBlueprint', phase: 'blueprintScoreBlack',
                  phaseTick: 0, vehicle: 'heli'
                }).black,
                blueprintFadeLevels: {
                  finalWhite: [
                    blueprintFinalWhiteLevel('heli', 0),
                    blueprintFinalWhiteLevel('heli', 12),
                    blueprintFinalWhiteLevel('heli', 13),
                    blueprintFinalWhiteLevel('jeep', 0),
                    blueprintFinalWhiteLevel('jeep', 11),
                    blueprintFinalWhiteLevel('jeep', 12),
                  ],
                  scoreBlack: [
                    blueprintScoreFadeBlack('heli', 0),
                    blueprintScoreFadeBlack('heli', 1),
                    blueprintScoreFadeBlack('heli', 12),
                    blueprintScoreFadeBlack('heli', 13),
                    blueprintScoreFadeBlack('jeep', 0),
                    blueprintScoreFadeBlack('jeep', 1),
                    blueprintScoreFadeBlack('jeep', 16),
                  ],
                },
                rendered: live.lastRender,
              };
            }""")
            expect(intro_core["order"] == [
                "cover", "sales", "heliBlueprint", "heliScores",
                "jeepBlueprint", "jeepScores", "faces"],
                "attract ma spatne poradi obrazovek")
            expect(intro_core["holds"] == {
                "cover": 600, "sales": 400, "heliScores": 250,
                "jeepScores": 250, "faces": 600},
                "attract ma spatne nativni hold casy")
            expect(intro_core["fades"] == list(range(0, 257, 16)),
                "black/white fade nema 17 nativnich endpointu")
            expect(intro_core["colorStarts"] == [0, 8, 16, 24, 32, 40, 48],
                "blueprint color tasky nemaji nativni rozestupy")
            expect(intro_core["rawHashes"] == {
                "COVER.RAW": "5fde4656", "MUSHROOM.RAW": "71275df0",
                "FACES.RAW": "b030d83b", "HELIBP1.RAW": "13ca9754",
                "HELIBP2.RAW": "50b837b1", "JEEPBP1.RAW": "b7ebb0aa",
                "JEEPBP2.RAW": "adc91ca6"},
                "indexed RAW decoder zmenil nektery intro asset")
            expect(all(v == 0 for v in intro_core["blueprintIndex8"].values()),
                "blueprint RAW pouziva rezervovany textovy index 8")
            expect(intro_core["streamEnds"] == [
                0x16A2, 0x1757, 0x1856, 0x1906, 0x192B],
                "blueprint parser neskoncil na presnych hranicich streamu")
            expect(intro_core["streamEndVbls"] == [144, 176, 96, 176, 0],
                "blueprint typewriter nema nativni wait/resume casovani: %r" %
                intro_core["streamEndVbls"])
            expect(intro_core["highScoreCounts"] == [7] * 16,
                "nektery nativni high-score soubor nema sedm jmen")
            expect(intro_core["highScoreFiles"] == [
                "HS1.TXT", "HS8.TXT", "HS9.TXT", "HS16.TXT"],
                "HELI/JEEP high-score RNG saha mimo nativni skupinu")
            expect(intro_core["hud"] == [
                ["PRESS FIRE", "PRESS FIRE"],
                ["PRESS FIRE", "PRESS FIRE"],
                ["HELI 0[ 2* 0000000", "JEEP 0[ 2* 0000000"],
                ["HELI 0[ 2* 0000000", "JEEP 0[ 2* 0000000"],
                ["PRESS FIRE", "PRESS FIRE"]],
                "attract HUD se neprepina na hranici VBL bitu 7")
            expect(intro_core["paletteCheckpoints"] == {
                "zero": [0x777, 0xFFF], "eight": [0x777, 0xFFF],
                "fortyEight": [0x777, 0xFFF],
                "seventyEight": [0x051, 0xCCE, 0x0A3]},
                "blueprint palette tasky nemaji nativni prubeh: %r" %
                intro_core["paletteCheckpoints"])
            expected_blueprint_tail = {
                "blueprintColor": 79, "blueprintWhite": 2,
                "blueprintMerge": 9, "blueprintFinalFade": 17,
                "blueprintHold": 50, "blueprintFadeOut": 17,
            }
            expect(intro_core["blueprintScoreBlack"] == 256,
                   "score-loader copy tail znovu odkryl blueprint")
            expect(intro_core["blueprintFadeLevels"] == {
                     "finalWhite": [96, 96, 0, 96, 96, 0],
                     "scoreBlack": [0, 224, 224, 256, 0, 256, 256]},
                   "blueprint publish/fade paleta neni z dense native frames: %r" %
                   intro_core["blueprintFadeLevels"])
            for timing, load_vbls, score_load_vbls, black_vbls, activations, \
                    reveal, task_start, text_done, first_offsets, next_scene in zip(
                    intro_core["blueprintTimings"], [100, 96], [100, 58],
                    [8, 7], [382, 335], [51, 45], [63, 57], [238, 232],
                    [[37, 21, 7], [37, 21, 7]],
                    ["heliScores", "jeepScores"]):
                phases = dict(expected_blueprint_tail)
                phases["blueprintLoad"] = load_vbls
                phases["blueprintScoreLoad"] = score_load_vbls
                phases["blueprintScoreBlack"] = black_vbls
                expect(timing["phases"] == phases and
                       timing["allTextDoneAt"] == text_done and
                       timing["next"] == next_scene and
                       timing["nextPhase"] == "hold" and
                       timing["revealedAt"] == reveal and
                       timing["taskStartedAt"] == task_start and
                       timing["firstTaskOffsets"] == first_offsets and
                       timing["activations"] == activations == sum(phases.values()),
                       "blueprint loader/tail timing nesedi: %r" % timing)
            repeated_heli = intro_core["repeatedHeliTiming"]
            repeated_phases = dict(expected_blueprint_tail)
            repeated_phases.update({"blueprintLoad": 100,
                                    "blueprintScoreLoad": 58,
                                    "blueprintScoreBlack": 7})
            expect(repeated_heli["phases"] == repeated_phases and
                   repeated_heli["allTextDoneAt"] == 238 and
                   repeated_heli["next"] == "heliScores" and
                   repeated_heli["nextPhase"] == "hold" and
                   repeated_heli["revealedAt"] == 51 and
                   repeated_heli["taskStartedAt"] == 63 and
                   repeated_heli["firstTaskOffsets"] == [37, 21, 7] and
                   repeated_heli["activations"] == 339,
                   "opakovana HELI stranka znovu nacita oba HS seznamy: %r" %
                   repeated_heli)
            expect(intro_core["copperCounts"] == {
                "cover": 0, "sales": 45, "faces": 80, "scores": 84},
                "intro nema presny pocet scanline Copper udalosti")
            expect(intro_core["salesGradient"] == [
                [48, 15, 0xF6D], [49, 15, 0xF9E], [50, 15, 0xFCF],
                [53, 15, 0xF9E], [54, 15, 0xF6D]],
                "sales COLOR15 gradient neni precteny z AMPROG tabulky")
            expect("PUBLISHED BY THE SALES CURVE LTD" in intro_core["sales"] and
                   "PRESS FIRE TO START GAME." in intro_core["sales"],
                "chybi embedded sales text")
            expect("Ronald Pieket" in intro_core["faces"] and
                   "Ned Langman" in intro_core["faces"],
                "chybi embedded FACES credits")
            expect(intro_core["rendered"]["scene"] == "cover" and
                   intro_core["rendered"]["black"] == 0,
                "COVER se nevykreslil nativni indexed cestou")

            mod_core = page.evaluate("""() => {
              const census = name => {
                const bytes = introFileBytes(name);
                const positions = bytes.subarray(952, 1080);
                let patterns = 0;
                for (const value of positions) patterns = Math.max(patterns, value + 1);
                const counts = { e001: 0, e200: 0, e400: 0,
                                 slide2: 0, vibrato4: 0 };
                for (let o = 1084; o < 1084 + patterns * 1024; o += 4) {
                  const effect = bytes[o + 2] & 15, arg = bytes[o + 3];
                  if (effect === 0 && arg === 1) counts.e001++;
                  if (effect === 2) { counts.slide2++; if (arg === 0) counts.e200++; }
                  if (effect === 4) { counts.vibrato4++; if (arg === 0) counts.e400++; }
                }
                return counts;
              };

              const synthetic = new Uint8Array(1084 + 1024);
              synthetic[950] = 1; synthetic[952] = 0;
              const cell = (row, period, effect, arg) => {
                const o = 1084 + row * 16;
                synthetic[o] = (period >> 8) & 15;
                synthetic[o + 1] = period & 255;
                synthetic[o + 2] = effect & 15;
                synthetic[o + 3] = arg;
                return row * 16;
              };
              const vib481 = cell(0, 428, 4, 0x81);
              const vib402 = cell(1, 0, 4, 0x02);
              const vib430 = cell(2, 0, 4, 0x30);
              const slide201 = cell(3, 600, 2, 0x01);
              const slide200 = cell(4, 0, 2, 0x00);
              const regular = cell(5, 508, 0, 0);
              const player = ModPlayer(synthetic);
              const C = player.channels[0];
              player.debug.note(0, vib481);
              const memories = [[C.vibspeed, C.vibdepth]];
              player.debug.note(0, vib402);
              memories.push([C.vibspeed, C.vibdepth]);
              player.debug.note(0, vib430);
              memories.push([C.vibspeed, C.vibdepth]);
              C.vibpos = 17; player.debug.note(0, regular);
              const retriggerPhase = C.vibpos;
              player.debug.note(0, slide201); player.debug.tickFx();
              const after201 = C.period;
              player.debug.note(0, slide200); player.debug.tickFx();
              const after200 = C.period;

              C.period = 428; C.eff = 4; C.vibspeed = 6; C.vibdepth = 2;
              C.vibpos = 0; C.fxperiod = 999; player.state.tick = 1;
              player.debug.trackerTick();
              const vibratoFirst = [C.fxperiod, C.vibpos];
              player.debug.trackerTick();
              const vibratoSecond = [C.fxperiod, C.vibpos];

              let processor;
              const fakeContext = {
                sampleRate: 48000, destination: {},
                createScriptProcessor: () => processor = {
                  connect() {}, disconnect() {}, onaudioprocess: null
                },
                createGain: () => ({ gain: { value: 0 }, connect() {}, disconnect() {} })
              };
              const timing = ModPlayer(synthetic);
              timing.start(fakeContext, 1);
              const left = new Float32Array(1921), right = new Float32Array(1921);
              processor.onaudioprocess({ outputBuffer: {
                getChannelData: channel => channel ? right : left
              }});
              const trackerTicks = timing.state.tick;
              timing.stop();

              let stereoProcessor;
              const stereoContext = {
                sampleRate: 48000, destination: {},
                createScriptProcessor: () => stereoProcessor = {
                  connect() {}, disconnect() {}, onaudioprocess: null
                },
                createGain: () => ({ gain: { value: 0 }, connect() {}, disconnect() {} })
              };
              const stereo = ModPlayer(synthetic);
              stereo.start(stereoContext, 1);
              Object.assign(stereo.channels[0], {
                s: { data: new Uint8Array([64]), len: 1, ls: 0, ll: 0 },
                pos: 0, period: 428, vol: 64, playing: true
              });
              const hardLeft = new Float32Array(1), silentRight = new Float32Array(1);
              stereoProcessor.onaudioprocess({ outputBuffer: {
                getChannelData: channel => channel ? silentRight : hardLeft
              }});
              stereo.stop();

              return {
                amt: census('AMTITUNE.MOD'), amh: census('AMHITUNE.MOD'),
                arp: [proTrackerArpeggioPeriod(856, 0),
                      proTrackerArpeggioPeriod(856, 1),
                      proTrackerArpeggioPeriod(856, 12)],
                vibTable: [proTrackerVibratoPeriod(428, 0, 2),
                           proTrackerVibratoPeriod(428, 16, 2),
                           proTrackerVibratoPeriod(428, 48, 2)],
                memories, retriggerPhase, after201, after200,
                vibratoFirst, vibratoSecond, trackerTicks,
                stereo: [hardLeft[0], silentRight[0]]
              };
            }""")
            expect(mod_core["amt"] == {
                "e001": 3, "e200": 3, "e400": 1,
                "slide2": 163, "vibrato4": 46},
                "AMTITUNE effect census se zmenil")
            expect(mod_core["amh"] == {
                "e001": 0, "e200": 0, "e400": 0,
                "slide2": 4, "vibrato4": 87},
                "AMHITUNE effect census se zmenil")
            expect(mod_core["arp"] == [856, 808, 428],
                "arpeggio nepouziva finetune-0 ProTracker period table")
            expect(mod_core["vibTable"] == [428, 431, 425],
                "vibrato nema nativni 32-entry sine/sign")
            expect(mod_core["memories"] == [[8, 1], [8, 2], [3, 2]],
                "4xy si nepamatuje speed/depth po nibblech")
            expect(mod_core["retriggerPhase"] == 0,
                "nova nota neresetovala vibrato phase")
            expect(mod_core["after201"] == 601 and mod_core["after200"] == 601,
                "2xx ma chybne parameter memory; PT 200 musi byt no-op")
            expect(mod_core["vibratoFirst"] == [428, 6] and
                   mod_core["vibratoSecond"] == [430, 12],
                "vibrato posunuje fazi pred vypoctem nebo leakuje periodu")
            expect(mod_core["trackerTicks"] == 3,
                "48kHz tracker tick ma off-by-one delku")
            expect(abs(mod_core["stereo"][0] - 0.5) < 1e-7 and
                   mod_core["stereo"][1] == 0,
                "Paula LRRL mix stale pridava umele stereo preslechy")

            started = time.time()
            page.keyboard.press(" ")
            page.wait_for_selector("#gamewrap", state="visible")
            expect(page.is_visible("#gamewrap"),
                "fire z attractu nespustil primo TOWN")
            expect(not page.is_visible("#levelpick"),
                "nativni fire omylem otevrel vyvojarsky level picker")

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

              const color07Ticks = [0, 3, 4, 28, 31, 32, 35, 36,
                                    60, 63, 64]
                .map(tick => townObjectColor07Word(tick));
              const color07Direct = colorizeIndexedField(
                new Uint8Array([7]), 1, 1, 1, 0, 0,
                state.copperChecks, undefined, 0, 128,
                townObjectColor07Word(28));
              const color07BlackFade = colorizeIndexedField(
                new Uint8Array([7]), 1, 1, 1, 0, 0,
                state.copperChecks, undefined, 128, 0);

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
                  lead: parsed.lead, startScroll: state.g.scroll,
                  objectColors: Array.from(
                    state.copperChecks[0].pal.slice(0, 10)),
                  objectColors104: Array.from(
                    state.copperChecks[1].pal.slice(0, 10)),
                  color07Ticks,
                  color07Direct: Array.from(color07Direct),
                  color07BlackFade: Array.from(color07BlackFade),
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
                   renderer_core["town"]["height"] == 3441 and
                   renderer_core["town"]["lead"] == 96 and
                   renderer_core["town"]["startScroll"] == 3249,
                   "Copper fixture nenacetla skutecnou mapu TOWN")
            # Objektove barvy zapisuje PAM: hlavicka (ry 96) ma jen 5/8/9,
            # checkpoint ry=104 doplni 1-4, 6, 7. Zadny engine override;
            # drivejsi tmavsi "zmerena" sada byla gamma krivka emulatoru.
            expect(renderer_core["town"]["objectColors"] ==
                   [0x000, 0x000, 0x000, 0x000, 0x000,
                    0x888, 0x000, 0x000, 0xFE8, 0xFFF] and
                   renderer_core["town"]["objectColors104"] ==
                   [0x000, 0x555, 0x687, 0x7BA, 0x987,
                    0x888, 0xBCB, 0xB30, 0xFE8, 0xFFF],
                   "TOWN nema PAM objektovou paletu (ry 96 / ry 104): %s / %s" %
                   (renderer_core["town"]["objectColors"],
                    renderer_core["town"]["objectColors104"]))
            expect(renderer_core["town"]["color07Ticks"] ==
                   [0x800, 0x800, 0x900, 0xF00, 0xF00, 0xF00,
                    0xF00, 0xE00, 0x800, 0x800, 0x800] and
                   renderer_core["town"]["color07Direct"] ==
                   [255, 0, 0, 255] and
                   # hlavicka PAM (ry 96) COLOR07 nezapisuje (az ry 104 = b30);
                   # pri black fadu se CPU writer 0x28fe preskoci, takze
                   # fixture s hlavickovou paletou da cernou
                   renderer_core["town"]["color07BlackFade"] ==
                   [0, 0, 0, 255],
                   "TOWN COLOR07 nema nativni 8..15..8 trojuhelnik/fade: %s" %
                   renderer_core["town"])
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
            # RGB hodnoty jdou cistě z PAM checkpointu (vcetne objektovych
            # barev z ry 104); legacy varianta se lisi jen na hranici
            # checkpointu (21 pixelu na kontrolnich 21 radcich).
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

            native_hud = page.evaluate("""() => {
              const plane = buildHudPlane(
                state.prog, 'HELI 4[ 2* 0000000', 'PRESS FIRE');
              const bits = Array.from(plane.bytes)
                .reduce((n, b) => n + b.toString(2).replaceAll('0', '').length, 0);
              const first = Array.from({length: 7}, (_, row) =>
                hudHighColorWord(16, row, 0, false, true));
              const steady = Array.from({length: 7}, (_, row) =>
                hudHighColorWord(16, row, 0, false, false));
              const bankPhase15 = [19, 23, 27, 31].map(index =>
                hudHighColorWord(index, 0, 15, false, false));
              const field = new Uint8Array(320 * 16);
              for (let i = 0; i < field.length; i++) field[i] = i & 15;
              const rgba = new Uint8ClampedArray(field.length * 4);
              const hostileHigh = new Uint16Array(16); hostileHigh.fill(0xFF0);
              compositeHudPlane(field, 320, rgba, plane.bytes, 0,
                                hostileHigh, false);
              let firstPixel = null;
              const effectiveRows = Array.from({length: 7}, () => new Set());
              for (let row = 0; row < 7 && !firstPixel; row++)
                for (let x = 0; x < 320; x++)
                  if (plane.bytes[row * HUD_STRIDE + (x >> 3)] &
                      (0x80 >> (x & 7))) {
                    const o = ((HUD_SCREEN_Y + row) * 320 + x) * 4;
                    firstPixel = [row, x, ...rgba.slice(o, o + 4)]; break;
                  }
              for (let row = 0; row < 7; row++)
                for (let x = 0; x < 320; x++)
                  if (plane.bytes[row * HUD_STRIDE + (x >> 3)] &
                      (0x80 >> (x & 7))) {
                    const o = ((HUD_SCREEN_Y + row) * 320 + x) * 4;
                    effectiveRows[row].add(
                      `${rgba[o]},${rgba[o + 1]},${rgba[o + 2]}`);
                  }
              const retainedGame = { tick: 15, fadeBlack: 0,
                                     spriteColorFlash: false };
              const retained0 = Array.from(updateRetainedHighColors(retainedGame));
              retainedGame.tick = 3; retainedGame.fadeBlack = 16;
              retainedGame.spriteColorFlash = true;
              const retainedFade = Array.from(updateRetainedHighColors(retainedGame));
              retainedGame.fadeBlack = 0;
              const retainedAfter = Array.from(updateRetainedHighColors(retainedGame));
              return { bytes: Array.from(plane.bytes), bits,
                widths: [plane.leftWidth, plane.rightWidth, plane.rightX],
                first, steady, bankPhase15,
                gray: [hudHighColorWord(18, 0, 0, false, false),
                       hudHighColorWord(18, 0, 0, true, false)],
                inheritedCold: [20,24,28].map(index =>
                  hudHighColorWord(index, 0, 0, false, false)),
                firstPixel, effectiveRows: effectiveRows.map(s => [...s]),
                retained: [retained0, retainedFade, retainedAfter] };
            }""")
            expect(hashlib.sha256(bytes(native_hud["bytes"])).hexdigest() ==
                   "083735374ea183f35350e6bbd4cb97e6bb8202d81ae7f51621764093154cd894" and
                   native_hud["bits"] == 638 and
                   native_hud["widths"] == [133, 76, 236],
                   "nativni HUD font/maska/anchory nesedi: %s" % native_hud)
            expect(native_hud["first"] ==
                   [0xDDF,0xAAE,0xCCF,0xCCF,0xCCF,0xAAE,0x88D] and
                   native_hud["steady"] ==
                   [0x88D,0xAAE,0xCCF,0xCCF,0xCCF,0xAAE,0x88D] and
                   native_hud["bankPhase15"] ==
                   [0x800,0xC00,0xFF0,0xFC0] and
                   native_hud["gray"] == [0x999,0xFFF] and
                   native_hud["inheritedCold"] == [0,0,0],
                   "HUD COLOR16..31 Copper banky nesedi: %s" % native_hud)
            expected_retained0 = [
                0,0xFFF,0x999,0x800, 0,0xFFF,0x999,0xC00,
                0,0xFFF,0x999,0xFF0, 0,0xFFF,0x999,0xFC0]
            expected_retained_after = [
                0,0xFFF,0xFFF,0x800, 0,0xFFF,0xFFF,0xF80,
                0,0xFFF,0xFFF,0xF00, 0,0xFFF,0xFFF,0xC00]
            expect(native_hud["retained"] ==
                   [expected_retained0, expected_retained0,
                    expected_retained_after],
                   "COLOR17..31 se nezachovaji behem black fade: %s" %
                   native_hud["retained"])
            expect(native_hud["firstPixel"][0] == 0 and
                   native_hud["firstPixel"][2:] == [136,136,221,255],
                   "HUD maska nema steady COLOR16 na prvnim tahu: %s" %
                   native_hud["firstPixel"])
            expect(native_hud["effectiveRows"] ==
                   [["136,136,221"],["170,170,238"],
                    ["204,204,255"],["204,204,255"],["204,204,255"],
                    ["170,170,238"],["136,136,221"]],
                   "HUD nesmi zdedit lower4 ani blikajici sprite banky: %s" %
                   native_hud["effectiveRows"])

            hw_allocator = page.evaluate("""() => {
              const synthetic = Array.from({length: 66}, (_, i) => ({
                id: i, key: 1000 - i, serial: i,
                startY: 20 + i * 20, stopY: 30 + i * 20,
                dmaVisible: true
              }));
              const cap = allocateHwSpriteQueue(synthetic, 0);
              const offTop = { id: 'off', key: 2000, serial: 100,
                               startY: -1, stopY: 10, dmaVisible: true };
              const withTop = allocateHwSpriteQueue(
                [offTop, ...synthetic.slice(0, 64)], 0);
              const black = allocateHwSpriteQueue(synthetic.slice(0, 8), 1);

              const equal = [
                { id:'actor10', key:55, serial:0, startY:10, stopY:12 },
                { id:'actor20', key:55, serial:1, startY:30, stopY:32 },
                { id:'bullet0', key:55, serial:2, startY:50, stopY:52 },
                { id:'bullet1', key:55, serial:3, startY:70, stopY:72 }
              ];
              const equalAlloc = allocateHwSpriteQueue(equal, 0);

              const reuse = Array.from({length: 9}, (_, i) => ({
                id:i, key:100-i, serial:i,
                startY:i===0 ? 10 : i===8 ? 21 : 40+i*20,
                stopY:i===0 ? 21 : i===8 ? 30 : 50+i*20
              }));
              const blocked = allocateHwSpriteQueue(reuse, 0);
              const blockedVisible = blocked.channels[0].map(r=>r.dmaVisible);
              reuse[8].startY = 22;
              const safe = allocateHwSpriteQueue(reuse, 0);

              const sourceGame = { scroll:100, fadeBlack:0, tick:0,
                nextBobOrdinal:30,
                shots:[
                  {kind:'can',x:100,y:40,ang:64,phase:0,bobOrdinal:10},
                  {kind:'hom',x:100,y:40,ang:64,bobOrdinal:11},
                  {kind:'can',x:110,y:50,ang:64,phase:1,bobOrdinal:12}
                ],
                plops:[{x:120,y:60,t:1,bobOrdinal:20}],
                bullets:[{x:140,y:80,frame:14,poolSlot:0}]
              };
              const source = townHwCandidates(sourceGame).map(r =>
                [r.kind,r.frame,r.startX,r.startY,r.poolSlot ?? null]);
              const bolt7 = hwSpriteCandidate(sourceGame,
                {x:20,y:7},'player-bolt','BULLET.LIN',14);
              const bolt8 = hwSpriteCandidate(sourceGame,
                {x:20,y:8},'player-bolt','BULLET.LIN',14);
              const geometry = [14,2,28].map(frame => {
                const s=indexedFrameFor(state,'BULLET.LIN',frame);
                return [frame,s.w,s.h,s.ox,s.oy];
              });

              const paletteGame = {tick:0,fadeBlack:0,fadeWhite:0,
                                   spriteColorFlash:false};
              const banks = [0,1,2,3].map(bank =>
                hwSpritePalette(paletteGame,bank).pal.slice(1,4));
              paletteGame.fadeWhite = 256;
              const whiteBanks = [0,1,2,3].map(bank =>
                hwSpritePalette(paletteGame,bank).pal.slice(1,4));

              // Dva prekryte cannon sprity se stejnym depth: novejsi actor
              // dostane channel0 a musi prekreslit starsi channel7/bank3.
              const layerGame = {scroll:0,tick:0,fadeBlack:0,fadeWhite:0,
                spriteColorFlash:false,nextBobOrdinal:3,
                shots:[
                  {kind:'can',x:30,y:30,ang:64,phase:0,bobOrdinal:1},
                  {kind:'can',x:30,y:30,ang:64,phase:0,bobOrdinal:2}
                ],plops:[],bullets:[]};
              const cv=document.createElement('canvas');
              cv.width=64; cv.height=64;
              const cx=cv.getContext('2d');
              const layerAlloc=drawTownHardwareSprites(cx,layerGame);
              const actual=cx.getImageData(0,0,64,64).data;
              function expectedBank(bank) {
                const out=document.createElement('canvas');
                out.width=64; out.height=64;
                const ox=out.getContext('2d');
                const hp=hwSpritePalette(layerGame,bank);
                const sp=sprite('BULLET.LIN',28,hp.pal,hp.key);
                ox.drawImage(sp.cv,30+sp.ox,30+sp.oy);
                return ox.getImageData(0,0,64,64).data;
              }
              const bank0=expectedBank(0), bank3=expectedBank(3);
              let probe=-1;
              for (let i=0;i<actual.length;i+=4)
                if (bank0[i+3] && (bank0[i]!==bank3[i] ||
                    bank0[i+1]!==bank3[i+1] || bank0[i+2]!==bank3[i+2])) {
                  probe=i; break;
                }
              const sameAt=(a,b,i) => i>=0 && a[i]===b[i] &&
                a[i+1]===b[i+1] && a[i+2]===b[i+2] && a[i+3]===b[i+3];
              const layering=[probe>=0,sameAt(actual,bank0,probe),
                sameAt(actual,bank3,probe),
                layerAlloc.accepted.map(r=>[r.source.bobOrdinal,r.channel])];

              const pool = {bullets:[{poolSlot:0},{poolSlot:2}]};
              const free1 = firstFreePlayerBulletSlot(pool);
              spawnPlayerBullet(pool,{x:0,y:0});
              const got1 = pool.bullets.at(-1).poolSlot;
              pool.bullets = Array.from({length:30},(_,poolSlot)=>({poolSlot}));
              const full = spawnPlayerBullet(pool,{x:0,y:0});
              return {
                cap:{accepted:cap.accepted.length,remaining:cap.remaining,
                     channels:cap.accepted.slice(0,16).map(r=>r.channel),
                     per:cap.channels.map(c=>c.length)},
                top:{accepted:withTop.accepted.length,
                     hasOff:withTop.accepted.some(r=>r.id==='off')},
                black:black.accepted.length,
                equal:{order:equalAlloc.traversal.map(r=>r.id),
                       channels:equalAlloc.accepted.map(r=>r.channel)},
                dma:[blockedVisible,
                     safe.channels[0].map(r=>r.dmaVisible)],
                source, geometry, banks, whiteBanks, layering,
                boltTop:[bolt7.startY,bolt8.startY,
                  allocateHwSpriteQueue([bolt7],0).accepted.length,
                  allocateHwSpriteQueue([bolt8],0).accepted.length],
                pool:[free1,got1,full,pool.bullets.length]
              };
            }""")
            expect(hw_allocator["cap"] == {
                     "accepted":64,"remaining":0,
                     "channels":[0,7,6,5,4,3,2,1,0,7,6,5,4,3,2,1],
                     "per":[8,8,8,8,8,8,8,8]} and
                   hw_allocator["top"] == {"accepted":64,"hasOff":False} and
                   hw_allocator["black"] == 0,
                   "0x3d00 HW capacity/channel/off-top/fade nesedi: %s" %
                   hw_allocator)
            expect(hw_allocator["equal"] == {
                     "order":["bullet1","bullet0","actor20","actor10"],
                     "channels":[0,7,6,5]} and
                   hw_allocator["dma"] == [[True,False],[True,True]],
                   "HW equal-key traversal nebo DMA channel reuse nesedi: %s" %
                   hw_allocator)
            expect(hw_allocator["geometry"] == [
                     [14,3,14,-1,-8],[2,11,11,-5,-5],[28,5,12,-2,-6]] and
                   sorted((r[0],r[1]) for r in hw_allocator["source"]) ==
                     [("cannon",28),("cannon",44),
                      ("player-bolt",14),("plop",2)] and
                   hw_allocator["boltTop"] == [-1,0,0,1] and
                   hw_allocator["pool"] == [1,1,False,30],
                   "HW source/geometry/30-slot pool nesedi: %s" % hw_allocator)
            expected_hw_banks = [
                [[255,255,255],[153,153,153],[204,0,0]],
                [[255,255,255],[153,153,153],[255,255,0]],
                [[255,255,255],[153,153,153],[255,204,0]],
                [[255,255,255],[153,153,153],[136,0,0]]]
            expect(hw_allocator["banks"] == expected_hw_banks and
                   hw_allocator["whiteBanks"] == expected_hw_banks and
                   hw_allocator["layering"] ==
                     [True,True,False,[[2,0],[1,7]]],
                   "HW banky/white-fade/channel priority nesedi: %s" %
                   hw_allocator)
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
              const hp = hwSpritePalette({tick:0,fadeBlack:0,
                fadeWhite:0,spriteColorFlash:false}, 0);
              return {
                frame28: colors(sprite('BULLET.LIN', 28, hp.pal,
                                       hp.key + ':test28')),
                frame44: colors(sprite('BULLET.LIN', 44, hp.pal,
                                       hp.key + ':test44')),
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
              const savedRandom32 = window.random32;
              window.random32 = () => 0x40004000;
              try {
                const g = { air: [], waveSeq: 0, players: 1,
                            activeCost: 0, scroll: 149 };
                spawnFodderFormation(g, { y: 100, typ: 1 });
                const fod = g.air;
                const before = activateAirMember(g, fod[0], { x: 100, y: 200, alive: true });
                g.scroll = 148;
                const atMargin = activateAirMember(g, fod[0], { x: 100, y: 200, alive: true });
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
                const yFirst = activateAirMember(gy, yellow[0], { x: 100, y: 200, alive: true });
                const xFirst = yellow[0].x;
                gy.scroll = 141;
                const yBefore = activateAirMember(gy, yellow[1], { x: 200, y: 200, alive: true });
                gy.scroll = 140;
                const ySecond = activateAirMember(gy, yellow[1], { x: 200, y: 200, alive: true });
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
              } finally { window.random32 = savedRandom32; }
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
                   "YELLOW nema 6 samostatne aktivovanych clenu/animaci: %s" %
                   formations)
            expect(formations["budgetAccepted"] is False and
                   formations["rejectedDead"] is True and
                   formations["cappedCost"] == 160,
                   "active budget dovolil prekrocit 160")

            # TOWN boss GOOSE (0xc78a): blikajici nalet, rozvinuti tela,
            # ctverice deti vcetne eskorty, hit-spread, palba a kruh bonusu.
            boss = page.evaluate("""() => {
              const g = state.g;
              const s = g.spawns.find(o => o.beh === 'boss');
              if (!s) return { err: 'boss v TOWN neni' };
              const saved = {
                random32: window.random32, spawns: g.spawns, air: g.air,
                hazards: g.hazards, shots: g.shots, bullets: g.bullets,
                plops: g.plops, tokens: g.tokens, booms: g.booms,
                effects: g.effects, activeCost: g.activeCost,
                scrollMul: g.scrollMul
              };
              window.random32 = () => 0;
              try {
                g.spawns = [s]; g.air = []; g.hazards = []; g.shots = [];
                g.bullets = []; g.plops = []; g.tokens = []; g.booms = [];
                g.effects = []; g.activeCost = 0; g.scrollMul = 0;
                g.over = false; g.won = false;
                g.player.alive = true; g.player.x = 100; g.player.y = 220;
                g.player.inv = 30000; g.player.bubbleTimer = 0;
                s.born = false; s.armed = true; s.alive = true;
                s.budgeted = false; s.y = g.scroll; // presne margin 0
                step(g);
                const born = {
                  x: s.x, sy: Math.round(s.y - g.scroll), hp: s.hp, st: s.st,
                  parts: s.parts.length, assemblyLeft: s.assemblyLeft,
                  cost: s.cost, activeCost: g.activeCost,
                  coroutine: s.coroutine, hidden: s.bodyHidden
                };
                let guard = 0;
                while (s.st === 0 && guard++ < 2000) step(g);
                const dock = {
                  st: s.st, hp: s.hp, sy: Math.round(s.y - g.scroll),
                  assemblyLeft: s.assemblyLeft, timer: s.timer ?? null,
                  rotorActive: s.rotorActive
                };
                guard = 0;
                while (s.st !== 2 && guard++ < 6000) step(g);
                const children = s.parts.map(q => ({
                  id: q.id, kind: q.kind, target: [q.tx, q.ty],
                  linked: q.linked, entered: q.entered, z: q.z
                }));
                const assembled = {
                  guard, st: s.st, hp: s.hp, left: s.assemblyLeft,
                  timer: s.timer, fireT: s.fireT, bodyFrame: s.bodyFrame,
                  activeCost: g.activeCost,
                  bodyOffsets: s.parts.filter(q => q.kind === 'body')
                    .map(q => [q.ox, q.oy]).sort((a, b) =>
                      a[0] - b[0] || a[1] - b[1]),
                  children
                };

                // Prvni bojova salva je mireny cannon + dva homing BOBs.
                g.shots = []; s.fireT = 1;
                step(g);
                const salvo = g.shots.map(x => x.kind).sort();

                // Neletalni zasah: pouze parent je jeden frame index 9;
                // tri casti tela se rozhodi a kontrahuji, escort ne.
                g.shots = []; g.bullets = [
                  { x: s.x, y: (s.y - g.scroll) + 9 },
                  { x: s.x + 1, y: (s.y - g.scroll) + 9 }
                ];
                const hp0 = s.hp;
                step(g);                       // VBL N: pouze pending bit0
                const spreadQueued = {
                  hp: s.hp, flag: s.hitSpread,
                  bulletsLeft: g.bullets.length,
                  pending: s.collisionEventWord | 0
                };
                step(g);                       // VBL N+1: 0x64b6 callback
                const white = composeTownBobs(g, Math.floor(g.scroll)).ordered
                  .filter(r => r.kind === 'main' &&
                    (r.id === 'boss-main-main' || r.id.startsWith('boss-')) &&
                    r.op === BOB_FILL_INDEX9)
                  .map(r => r.id);
                const spread = {
                  hp: s.hp, hp0, flag: s.hitSpread,
                  bulletsLeft: g.bullets.length,
                  offsets: s.parts.filter(q => q.kind === 'body')
                    .map(q => [q.ox, q.oy]).sort((a, b) =>
                      a[0] - b[0] || a[1] - b[1]),
                  white
                };
                g.bullets = [];
                step(g);
                const returning = {
                  flag: s.hitSpread,
                  offsets: s.parts.filter(q => q.kind === 'body')
                    .map(q => [q.ox, q.oy]).sort((a, b) =>
                      a[0] - b[0] || a[1] - b[1])
                };

                // Projectile bit0 koaleskuje, player-contact bit3 je ale
                // samostatny callback a muze ve stejnem VBL ubrat dalsi HP.
                // Sweep 0xffff cte uzel z RESUME (0x6430): teleport hrace
                // ve fixture proto doplni i snapshot uzlu.
                const teleport = (x, y) => {
                  g.player.x = x; g.player.y = y; snapNode(g, g.player, x, y);
                };
                g.bullets = [{ x: s.x, y: (s.y - g.scroll) + 9 }];
                teleport(s.x, s.y - g.scroll);
                const bothHp0 = s.hp; step(g);
                teleport(100, 220); step(g);
                const bothEvents = { before: bothHp0, after: s.hp,
                                     playerAlive: g.player.alive };
                const childPart = s.parts.find(q => q.id === 'left');
                const childPos = bossPartPosition(s, childPart, g.scroll);
                g.bullets = []; teleport(childPos.x, childPos.y);
                const childHp0 = s.hp; step(g);
                teleport(100, 220); step(g);
                const childOnly = { before: childHp0, after: s.hp,
                                    playerAlive: g.player.alive };
                teleport(100, 220);

                // Izolovany home overshoot a escort offset replacement.
                const microBoss = { x: 100, y: 200, parts: [],
                                    assemblyLeft: 4, hitSpread: false };
                const oq = newBossChild(BOSS_BODY_PARTS[0], 0, false);
                Object.assign(oq, { phase: 'home', entered: true, linked: false,
                  x: 80, y: 88, vx: 1, vy: 2 });
                microBoss.parts = [oq];
                stepBossParts({ scroll: 100 }, microBoss, 0);
                const overshoot = { phase: oq.phase, linked: oq.linked,
                  pos: [oq.x, oq.y], left: microBoss.assemblyLeft };
                stepBossParts({ scroll: 100 }, microBoss, 0);
                const snapped = { phase: oq.phase, linked: oq.linked,
                  offset: [oq.ox, oq.oy], left: microBoss.assemblyLeft };
                const eq = newBossChild(BOSS_ESCORT, 0, true);
                Object.assign(eq, { linked: true, entered: true, phase: 'snake',
                  ang: 64, snakeTurn: -8, snakeSteps: 6, snakeWait: 0 });
                stepBossEscort(eq);
                const e1 = angVel(56, 18);
                const escort1 = Math.abs(eq.ox - e1.vx) < 1e-12 &&
                  Math.abs(eq.oy - (e1.vy + 12)) < 1e-12;
                stepBossEscort(eq);
                const e2 = angVel(48, 18);
                const escort2 = Math.abs(eq.ox - e2.vx) < 1e-12 &&
                  Math.abs(eq.oy - (e2.vy + 12)) < 1e-12;

                // Parentuv pohyb je 16.16, ale c818/c887/c8b2/c8ce
                // porovnavaji pouze high WORD. Zlomky .75 proto patri do
                // stejne vetve jako cela 72/64/128/192, nikoli za hranici.
                function gooseWordBoundary(st, bsy, patch = {}) {
                  const bg = Object.assign({}, g, {
                    tick: 0, scroll: 1000, scrollMul: 0,
                    over: false, won: false, keys: {},
                    player: Object.assign({}, g.player, {
                      x: patch.targetX ?? 100.25, y: 240, alive: true,
                      inv: 30000, bubbleTimer: 0, bubbleBound: null,
                      cool: 0, bobOrdinal: 0
                    }),
                    spawns: [], air: [], hazards: [], shots: [], bullets: [],
                    plops: [], tokens: [], booms: [], effects: [],
                    activeCost: 0, smartPulse: 0, smartPulseTasks: [],
                    smartPulseTaskOrdinals: [], tokenSfxTasks: [],
                    townExplosionTasks: [], nextBobOrdinal: 2,
                    sfx: createTownSfxState()
                  });
                  const bs = Object.assign({}, s, {
                    born: true, alive: true, st, hp: 25,
                    x: patch.x ?? 100.75, y: bg.scroll + bsy,
                    vx: patch.vx ?? 0, vy: patch.vy ?? 0,
                    arrived: patch.arrived ?? false,
                    timer: patch.timer ?? 100, fireT: patch.fireT ?? 100,
                    parts: [], assemblyLeft: 0, bodyHidden: false,
                    unfoldPos: -1, rotorActive: false, hitSpread: false,
                    groupReleased: false, retireAfterField: false,
                    collisionEventWord: 0, collisionPlayerCredit: false,
                    budgeted: false, cost: 0, bobOrdinal: 1,
                    scrollLocked: true
                  });
                  bg.spawns = [bs]; step(bg);
                  return { boss: bs, game: bg };
                }
                const wbIngress = gooseWordBoundary(0, 74.75, { vy: -2 });
                const wbTarget = gooseWordBoundary(2, 100);
                const wbLow = gooseWordBoundary(2, 64.75);
                const wbHigh = gooseWordBoundary(2, 192.75);
                const wbFire = gooseWordBoundary(2, 128.75, { fireT: 1 });
                const wordBoundaries = {
                  ingress: [wbIngress.boss.arrived,
                    positionWord(wbIngress.boss.y - wbIngress.game.scroll)],
                  targetVx: wbTarget.boss.vx,
                  vertical: [wbLow.boss.vy, wbHigh.boss.vy],
                  fire: wbFire.game.shots.map(q => q.kind).sort()
                };

                // Letalni GOOSE zasah musi ve fieldu N pouze zapsat bit0.
                // Death synth, BIGEXPL, unlink i dva TOKENy pro timer>500
                // vzniknou az pri resume parent tasku v N+1.
                const deathGame = Object.assign({}, g, {
                  tick: 0, scrollMul: 0, over: false, won: false,
                  keys: {}, player: Object.assign({}, g.player, {
                    x: 100, y: 220, alive: true, inv: 30000,
                    bubbleTimer: 0, bubbleBound: null, cool: 0
                  }),
                  spawns: [], air: [], hazards: [], shots: [], bullets: [],
                  plops: [], tokens: [], booms: [], effects: [],
                  activeCost: 140, smartPulse: 0, smartPulseTasks: [],
                  tokenSfxTasks: [], sfx: createTownSfxState()
                });
                const deathBoss = Object.assign({}, s, {
                  born: true, alive: true, hp: 1, timer: 503, fireT: 100,
                  st: 2, x: 160, y: deathGame.scroll + 100,
                  vx: 0, vy: 0, scrollLocked: true,
                  hitSpread: false, groupReleased: false,
                  budgeted: true, collisionEventWord: 0,
                  collisionPlayerCredit: false,
                  parts: s.parts.map(q => Object.assign({}, q, {
                    budgeted: true
                  }))
                });

                // Timeout 0xc908 propadne po nastaveni vy=-4 rovnou do
                // 0xc930/0x62d2; prvni escape field tedy musi byt o 4 px
                // vys uz v tomto resume a nove TOKENy se take jednou pohnou.
                const timeoutGame = Object.assign({}, deathGame, {
                  tick: 0, player: Object.assign({}, deathGame.player),
                  spawns: [], air: [], hazards: [], shots: [], bullets: [],
                  plops: [], tokens: [], booms: [], effects: [],
                  activeCost: 140, sfx: createTownSfxState()
                });
                const timeoutBoss = Object.assign({}, deathBoss, {
                  x: 160, y: timeoutGame.scroll + 100, st: 2,
                  hp: 25, timer: 0, fireT: 1, vx: 0, vy: 0,
                  groupReleased: false, budgeted: true,
                  parts: deathBoss.parts.map(q => Object.assign({}, q, {
                    budgeted: true
                  }))
                });
                timeoutGame.spawns = [timeoutBoss];
                step(timeoutGame);
                const timeoutToken = timeoutGame.tokens[0];
                const timeoutEscape = [timeoutBoss.st,
                  +timeoutBoss.x.toFixed(6),
                  Math.round(timeoutBoss.y - timeoutGame.scroll),
                  timeoutBoss.vy, timeoutGame.shots.length,
                  timeoutGame.tokens.length,
                  timeoutGame.tokens.map(k => k.burst),
                  [timeoutToken.ang,
                   +(timeoutToken.x - 160).toFixed(2),
                   +(timeoutToken.y - (timeoutGame.scroll + 100)).toFixed(2)],
                  timeoutBoss.timer, timeoutGame.activeCost,
                  timeoutGame.sfx.events.filter(e =>
                    e.kind === 'cannon' || e.kind === 'homing').length];

                // Po timeoutu unikajici parent skonci na -64 poslednim
                // fieldem N. N+1 orphan callback vyhodi pouze eskortu a
                // uvolni child cost40; parent cost100 drzi checksum tail
                // az do resume N+108.
                let timeoutCullGuard = 0;
                while (!timeoutBoss.retireAfterField &&
                       timeoutCullGuard++ < 100) step(timeoutGame);
                const timeoutCullN = {
                  guard: timeoutCullGuard,
                  alive: timeoutBoss.alive,
                  retire: !!timeoutBoss.retireAfterField,
                  sy: Math.floor(timeoutBoss.y - timeoutGame.scroll),
                  cost: timeoutGame.activeCost,
                  booms: timeoutGame.booms.length,
                  tokens: timeoutGame.tokens.length
                };
                step(timeoutGame);              // cull N+1: orphan + tail start
                const timeoutCullN1 = {
                  present: timeoutGame.spawns.includes(timeoutBoss),
                  alive: timeoutBoss.alive,
                  cost: timeoutGame.activeCost,
                  booms: timeoutGame.booms.map(b => [b.source, b.z]),
                  bigexpl: timeoutGame.sfx.events.filter(e =>
                    e.kind === 'bigexpl').length
                };
                for (let i = 0; i < 106; i++) step(timeoutGame);
                const timeoutCullN107 = {
                  present: timeoutGame.spawns.includes(timeoutBoss),
                  cost: timeoutGame.activeCost,
                  parentBudgeted: !!timeoutBoss.budgeted
                };
                step(timeoutGame);
                const timeoutCullN108 = {
                  present: timeoutGame.spawns.includes(timeoutBoss),
                  cost: timeoutGame.activeCost,
                  parentBudgeted: !!timeoutBoss.budgeted
                };

                deathGame.spawns = [deathBoss];
                deathGame.bullets = [{ x: deathBoss.x,
                  y: deathBoss.y - deathGame.scroll + 9 }];
                step(deathGame);                // N: field + pending bit0
                const deathBullet = deathGame.bullets[0];
                const deathQueued = {
                  alive: deathBoss.alive, hp: deathBoss.hp,
                  timer: deathBoss.timer,
                  tokens: deathGame.tokens.length,
                  booms: deathGame.booms.length,
                  bullets: deathGame.bullets.length,
                  consumed: !!deathBullet.collisionConsumed,
                  pending: deathBoss.collisionEventWord | 0,
                  credit: !!deathBoss.collisionPlayerCredit,
                  cost: deathGame.activeCost,
                  sounds: deathGame.sfx.events.map(e => e.kind),
                  bossBob: composeTownBobs(deathGame,
                    Math.floor(deathGame.scroll)).ordered
                    .some(r => r.id === 'boss-main-main'),
                  boltHw: townHwCandidates(deathGame)
                    .filter(r => r.kind === 'player-bolt').length
                };
                step(deathGame);                // N+1: 0xc974 lethal callback
                const death = {
                  alive: deathBoss.alive, hp: deathBoss.hp,
                  pending: deathBoss.collisionEventWord | 0,
                  tokens: deathGame.tokens.map(k => [
                    k.typ, k.ang, k.phase, k.interactive, k.burst,
                    +(k.x - deathBoss.x).toFixed(2),
                    +(k.y - deathBoss.y).toFixed(2)]),
                  bullets: deathGame.bullets.length,
                  sounds: deathGame.sfx.events.map(e =>
                    [e.kind, e.accepted, e.tick]),
                  booms: deathGame.booms.map(b => [b.source, b.t, b.z]),
                  activeCost: deathGame.activeCost,
                  released: deathBoss.groupReleased,
                  bossBob: composeTownBobs(deathGame,
                    Math.floor(deathGame.scroll)).ordered
                    .some(r => r.id === 'boss-main-main'),
                  boltHw: townHwCandidates(deathGame)
                    .filter(r => r.kind === 'player-bolt').length
                };
                for (let i = 0; i < 106; i++) step(deathGame);
                const deathN107 = {
                  present: deathGame.spawns.includes(deathBoss),
                  cost: deathGame.activeCost,
                  parentBudgeted: !!deathBoss.budgeted
                };
                step(deathGame);
                const deathN108 = {
                  present: deathGame.spawns.includes(deathBoss),
                  cost: deathGame.activeCost,
                  parentBudgeted: !!deathBoss.budgeted
                };

                // HP1 + oba residentni bity: chranena HELI zachova bit3.
                // 0x64b6 musi po prvni lethal bit0 smrti pokracovat bitem3:
                // prvni callback dropne kruh2, vynuluje timer a druhy proto
                // dropne kruh3. Parent vybuchne dvakrat, orphan eskorta 1x.
                const bothGame = Object.assign({}, deathGame, {
                  tick: 0, player: Object.assign({}, deathGame.player, {
                    x: 160, y: 100, alive: true, inv: 30000,
                    bubbleTimer: 0, bubbleBound: null
                  }),
                  spawns: [], air: [], hazards: [], shots: [], bullets: [],
                  plops: [], tokens: [], booms: [], effects: [],
                  activeCost: 140, score: 0, smartPulse: 0,
                  smartPulseTasks: [], tokenSfxTasks: [],
                  sfx: createTownSfxState(), nextBobOrdinal: 100
                });
                const bothBoss = Object.assign({}, deathBoss, {
                  born: true, alive: true, hp: 1, timer: 503,
                  x: 160, y: bothGame.scroll + 100,
                  groupReleased: false, budgeted: true,
                  retireAfterField: false, checksumReleaseTick: null,
                  checksumDone: false,
                  collisionEventWord: 0, collisionPlayerCredit: false,
                  parts: s.parts.map(q => Object.assign({}, q, {
                    alive: true, dead: false, entered: true, linked: true,
                    orphanPending: false, budgeted: true
                  }))
                });
                bothGame.spawns = [bothBoss];
                bothGame.bullets = [{ x: bothBoss.x,
                  y: bothBoss.y - bothGame.scroll + 9 }];
                step(bothGame);                 // N: bit0 | bit3
                const bothQueued = {
                  hp: bothBoss.hp,
                  pending: bothBoss.collisionEventWord | 0,
                  player: [bothGame.player.alive, bothGame.player.inv],
                  tokens: bothGame.tokens.length,
                  booms: bothGame.booms.length,
                  cost: bothGame.activeCost
                };
                bothGame.player.x = 100; bothGame.player.y = 220;
                step(bothGame);                 // N+1: dva death callbacky
                const bothDeath = {
                  hp: bothBoss.hp,
                  pending: bothBoss.collisionEventWord | 0,
                  tokens: bothGame.tokens.map(k => [k.typ, k.ang, k.burst]),
                  boomOrder: bothGame.booms.map(b => [b.source, b.z]),
                  synth: bothGame.sfx.events.filter(e =>
                    e.kind.startsWith('goose-death')).map(e => e.kind),
                  bigexpl: bothGame.sfx.events.filter(e =>
                    e.kind === 'bigexpl').length,
                  cost: bothGame.activeCost,
                  parentBudgeted: !!bothBoss.budgeted,
                  childBudgeted: bothBoss.parts.filter(q => q.budgeted).length
                };

                g.tokens = [];
                dropBossTokens(g, s, 2);
                const ring = g.tokens.map(k => k.ang);
                return { born, dock, assembled, salvo, spreadQueued,
                         spread, returning,
                         bothEvents, childOnly, overshoot, snapped,
                         escortReplace: escort1 && escort2,
                         wordBoundaries,
                         timeoutEscape, timeoutCullN, timeoutCullN1,
                         timeoutCullN107, timeoutCullN108,
                         deathQueued, death, deathN107, deathN108,
                         bothQueued, bothDeath, ring,
                         tokenTypes: g.tokens.map(k => k.typ) };
              } finally {
                window.random32 = saved.random32; g.spawns = saved.spawns;
                g.air = saved.air; g.hazards = saved.hazards;
                g.shots = saved.shots; g.bullets = saved.bullets;
                g.plops = saved.plops; g.tokens = saved.tokens;
                g.booms = saved.booms; g.effects = saved.effects;
                g.activeCost = saved.activeCost; g.scrollMul = saved.scrollMul;
              }
            }""")
            expect("err" not in boss, boss.get("err", ""))
            expect(boss["born"]["coroutine"] == 0xC78A,
                   "boss neni routovany na korutinu 0xc78a")
            expect(boss["born"]["x"] == 160 and boss["born"]["sy"] == 286,
                   "boss po setupu neudelal stejnotikovy prvni krok z y288: %s"
                   % boss["born"])
            expect(boss["born"]["hp"] == 0 and boss["born"]["parts"] == 4 and
                   boss["born"]["assemblyLeft"] == 4 and
                   boss["born"]["cost"] == 100 and
                   boss["born"]["activeCost"] == 110,
                   "boss parent+stejnotikovy escort nemaji cost100+10: %s"
                   % boss["born"])
            expect(boss["dock"]["st"] == 1 and boss["dock"]["hp"] == 25 and
                   boss["dock"]["sy"] <= 72 and
                   boss["dock"]["assemblyLeft"] > 0 and
                   boss["dock"]["timer"] == 0 and
                   boss["dock"]["rotorActive"] is True,
                   "boss nezastavil na y 72 a necekal na deti: %s"
                   % boss["dock"])
            expected_children = [
                {"id": "escort", "kind": "escort", "target": [0, 24],
                 "linked": True, "entered": True, "z": 33},
                {"id": "left", "kind": "body", "target": [-16, -12],
                 "linked": True, "entered": True, "z": 33},
                {"id": "right", "kind": "body", "target": [16, -12],
                 "linked": True, "entered": True, "z": 33},
                {"id": "top", "kind": "body", "target": [0, -44],
                 "linked": True, "entered": True, "z": 33},
            ]
            expect(boss["assembled"]["guard"] < 6000 and
                   boss["assembled"]["st"] == 2 and
                   boss["assembled"]["left"] == 0 and
                   boss["assembled"]["timer"] == 2000 and
                   boss["assembled"]["fireT"] == 9 and
                   boss["assembled"]["bodyFrame"] == 5 and
                   boss["assembled"]["activeCost"] == 140 and
                   boss["assembled"]["children"] == expected_children and
                   boss["assembled"]["bodyOffsets"] ==
                     [[-16, -12], [0, -44], [16, -12]],
                   "GOOSE se neslozil ze ctyr deti pred startem boje: %s"
                   % boss["assembled"])
            expect(boss["salvo"] == ["can", "hom", "hom"],
                   "salva bosse ma byt mireny granat + dve navadene: %s"
                   % boss["salvo"])
            # screen-y se pocita z celociselneho scrollu (word fp@(3542));
            expect(boss["wordBoundaries"] == {
                     "ingress": [True, 72],
                     "targetVx": 1536 / 65536,
                     "vertical": [0, 0],
                     "fire": ["can", "hom", "hom"]},
                   "GOOSE nepouziva high-WORD hranice pohybu/palby: %s" %
                   boss["wordBoundaries"])
            expect(boss["spreadQueued"] == {
                     "hp": boss["spread"]["hp0"], "flag": False,
                     "bulletsLeft": 2, "pending": 1},
                   "GOOSE callback probehl uz v producing VBL: %s" %
                   boss["spreadQueued"])
            expect(boss["spread"]["hp"] == boss["spread"]["hp0"] - 1 and
                   boss["spread"]["flag"] is True and
                   boss["spread"]["bulletsLeft"] == 0 and
                   boss["spread"]["offsets"] ==
                     [[-28, -20], [0, -84], [28, -20]] and
                   boss["spread"]["white"] == ["boss-main-main"],
                   "zasah nerozhodil dily nebo nezbelil pouze parent: %s"
                   % boss["spread"])
            expect(boss["returning"] == {
                     "flag": False,
                     "offsets": [[-24, -16], [0, -80], [24, -16]]},
                   "dily se po hit-framu nevraceji po 4 px: %s"
                   % boss["returning"])
            expect(boss["bothEvents"]["after"] ==
                     boss["bothEvents"]["before"] - 2 and
                   boss["bothEvents"]["playerAlive"] is True and
                   boss["childOnly"]["after"] == boss["childOnly"]["before"] and
                   boss["childOnly"]["playerAlive"] is True,
                   "GOOSE event bity/parent-vs-child kontakt nesedi: %s / %s"
                   % (boss["bothEvents"], boss["childOnly"]))
            expect(boss["overshoot"] == {"phase": "overshoot",
                     "linked": False, "pos": [82, 92], "left": 4} and
                   boss["snapped"] == {"phase": "linked", "linked": True,
                     "offset": [-16, -12], "left": 3} and
                   boss["escortReplace"] is True,
                   "GOOSE child overshoot/snap nebo escort replacement nesedi: %s / %s"
                   % (boss["overshoot"], boss["snapped"]))
            expect(boss["timeoutEscape"] ==
                     [3, 160, 96, -4, 0, 5, [31, 31, 31, 31, 31],
                      [0, 1.25, -1], 0, 165, 0],
                   "GOOSE timeout nepropadl do prvniho -4px escape fieldu: %s" %
                   boss["timeoutEscape"])
            expect(boss["timeoutCullN"] == {
                     "guard": 40, "alive": True, "retire": True,
                     "sy": -64, "cost": 165, "booms": 0, "tokens": 5},
                   "unikajici GOOSE nema posledni cull field N: %s" %
                   boss["timeoutCullN"])
            expect(boss["timeoutCullN1"] == {
                     "present": True, "alive": False, "cost": 125,
                     "booms": [["boss-escort", 34]], "bigexpl": 2},
                   "timeout cull nema v N+1 pouze escort orphan explozi: %s" %
                   boss["timeoutCullN1"])
            expect(boss["timeoutCullN107"] == {
                     "present": True, "cost": 125,
                     "parentBudgeted": True} and
                   boss["timeoutCullN108"] == {
                     "present": True, "cost": 25,
                     "parentBudgeted": False},
                   "timeout GOOSE neuvolnil parent cost presne v N+108: %s / %s"
                   % (boss["timeoutCullN107"], boss["timeoutCullN108"]))
            expect(boss["deathQueued"] == {
                     "alive": True, "hp": 1, "timer": 502,
                     "tokens": 0, "booms": 0, "bullets": 1,
                     "consumed": True, "pending": 1, "credit": False,
                     "cost": 140, "sounds": [],
                     "bossBob": True, "boltHw": 1},
                   "GOOSE smrt probehla uz v producing VBL: %s" %
                   boss["deathQueued"])
            expect(boss["death"] == {
                     "alive": False, "hp": 0, "pending": 0,
                     "tokens": [
                       [3, 0, "burst", False, 31, 1.25, -1],
                       [3, 128, "burst", False, 31, -1.25, -1]],
                     "bullets": 0,
                     "sounds": [
                       ["goose-death-r", True, 2],
                       ["goose-death-l", True, 2],
                       ["bigexpl", True, 2], ["bigexpl", True, 2],
                       ["bigexpl", False, 2], ["bigexpl", False, 2]],
                     "booms": [["boss-parent", 0, 33],
                               ["boss-escort", 0, 34]],
                     "activeCost": 110, "released": True,
                     "bossBob": False, "boltHw": 0},
                   "GOOSE death callback/TOKEN childy nejsou presne v N+1: %s" %
                   boss["death"])
            expect(boss["deathN107"] == {
                     "present": True, "cost": 110,
                     "parentBudgeted": True} and
                   boss["deathN108"] == {
                     "present": True, "cost": 10,
                     "parentBudgeted": False},
                   "GOOSE checksum tail neuvolnil parent cost presne v N+108: %s / %s"
                   % (boss["deathN107"], boss["deathN108"]))
            expect(boss["bothQueued"] == {
                     "hp": 1, "pending": 9, "player": [True, 29999],
                     "tokens": 0, "booms": 0, "cost": 140},
                   "GOOSE HP1 neudrzel bit0|bit3 do N+1: %s" %
                   boss["bothQueued"])
            expect(boss["bothDeath"] == {
                     "hp": -1, "pending": 0,
                     "tokens": [[3, 0, 31], [3, 128, 31],
                                [3, 0, 31], [3, 85, 31], [3, 170, 31]],
                     "boomOrder": [["boss-parent", 33],
                                   ["boss-parent", 33],
                                   ["boss-escort", 34]],
                     "synth": ["goose-death-r", "goose-death-l",
                               "goose-death-r", "goose-death-l"],
                     "bigexpl": 6, "cost": 125,
                     "parentBudgeted": True, "childBudgeted": 0},
                   "GOOSE HP1 bit0|bit3 neprovedl dva death callbacky 2+3: %s" %
                   boss["bothDeath"])
            expect(len(boss["ring"]) == 2 and
                   (boss["ring"][1] - boss["ring"][0]) % 256 == 128,
                   "kruh bonusu nema krok 256/pocet: %s" % boss["ring"])
            expect(boss["tokenTypes"] == [3, 3],
                   "GOOSE bonusy nezacinaji typem ochrany 3: %s"
                   % boss["tokenTypes"])

            # Loader kill pouze zneplatni generation word. SMART callback
            # proto nesmi potlacit pozdejsi bit0/bit3 callbacky ze stejneho
            # ulozeneho wordu; fyzicky cost/task cleanup prijde jen jednou.
            scheduler_callbacks = page.evaluate("""() => {
              const live = state.g;
              function makeGame(playerPatch = {}) {
                const player = Object.assign({
                  x: 20, y: 220, ang: 17, alive: true, inv: 100,
                  bubbleTimer: 0, bubbleBound: null, bubbleFrame: 9,
                  bubbleZ: 0, bubblePhase: 0, bank: 0, cool: 0,
                  weapon: 2, tokenCount: 0, mode: 0, reload: 11,
                  respawnT: 0, rank: 0, heliAnimPos: 0,
                  heliAnimFresh: true, weaponX: 20, weaponY: 220,
                  bobOrdinal: 0
                }, playerPatch);
                return {
                  mapH: live.mapH, mapW: 320, mapIndex: live.mapIndex,
                  tick: 0, scroll: 1000, scrollMul: 0,
                  over: false, won: false, keys: {}, player,
                  nextBobOrdinal: 20, bullets: [], shots: [], plops: [],
                  spawns: [], booms: [], effects: [], tokens: [], air: [],
                  hazards: [], activeCost: 0, score: 0,
                  nextLife: 10000, lives: 4, players: 1, difficulty: 0,
                  levelPhase: 0, rngState: 0, rngVhposWord: 0,
                  rotoDirectionWord: 0, fadeBlack: 0, fadeWhite: 0,
                  fadeDir: 0, fadeWhiteStep: 0, smartPulse: 0,
                  smartPulseTasks: [], tokenSfxTasks: [], flash: 0,
                  sfx: createTownSfxState()
                };
              }
              const eventKinds = g => g.sfx.events.map(e => e.kind);

              const hg = makeGame();
              const hom = { kind: 'hom', x: 160, y: 100, ang: 0,
                spd: 3, lead: 20, corr: 12, ct: 0,
                cost: 5, budgeted: true, dead: false, bobOrdinal: 1,
                collisionEventWord: 9, collisionPlayerCredit: true };
              hg.shots = [hom]; hg.activeCost = 5;
              hg.smartPulse = 20; hg.smartPulseTasks = [20];
              step(hg);
              const homing = {
                score: hg.score, booms: hg.booms.length,
                bigexpl: eventKinds(hg).filter(k => k === 'bigexpl').length,
                shots: hg.shots.length, dead: !!hom.dead,
                pending: hom.collisionEventWord | 0, cost: hg.activeCost
              };

              const ag = makeGame();
              const air = { kind: 'fod', x: 160, y: ag.scroll + 100,
                vx: 0, vy: 0, ax: 0, ay: 0,
                alive: true, pending: false, dead: false,
                cost: 10, budgeted: true, hp: 1, scoreValue: 12,
                shooter: false, seq: [0, 1], apos: 0, at: 0,
                animFresh: false, bobOrdinal: 1,
                collisionEventWord: 9, collisionPlayerCredit: true };
              ag.air = [air]; ag.activeCost = 10;
              ag.smartPulse = 20; ag.smartPulseTasks = [20];
              step(ag);
              const genericAir = {
                hp: air.hp, score: ag.score, booms: ag.booms.length,
                bigexpl: eventKinds(ag).filter(k => k === 'bigexpl').length,
                air: ag.air.length, dead: !!air.dead,
                pending: air.collisionEventWord | 0, cost: ag.activeCost
              };

              // TOKEN SMART ignoruje. Bit0 musi zmenit typ3 -> typ0 jeste
              // pred bit3 pickupem, takze nevznikne +500 ochrana/skore.
              const tg = makeGame();
              const token = { x: 160, y: tg.scroll + 100,
                vx: 0, vy: .5, typ: 3, cycles: 12, blink: false,
                hitCooldown: -1, phase: 'active', interactive: true,
                activeHalf: 0, dead: false, cost: 5, budgeted: true,
                bobOrdinal: 1, collisionEventWord: 9,
                collisionPlayerCredit: true };
              tg.tokens = [token]; tg.activeCost = 5;
              tg.smartPulse = 20; tg.smartPulseTasks = [20];
              step(tg);
              const tokenBoth = {
                typ: token.typ, cycles: token.cycles,
                cooldown: token.hitCooldown,
                picked: tg.tokensPickedUp || 0,
                tokenCount: tg.player.tokenCount,
                weapon: tg.player.weapon, mode: tg.player.mode,
                inv: tg.player.inv, score: tg.score,
                tokens: tg.tokens.length, dead: !!token.dead,
                pending: token.collisionEventWord | 0, cost: tg.activeCost,
                pickupSfx: eventKinds(tg)
                  .filter(k => k === 'token-pickup').length
              };

              // BIRD ma vlastni neletalni callback: -6y, RNG+cannon,
              // a teprve potom standardni a35a generic-hit vrstvu.
              const bg = makeGame();
              const bird = { kind: 'bird', x: 160, y: bg.scroll + 100,
                vx: 0, vy: 0, alive: true, pending: false, dead: false,
                cost: 10, budgeted: true, hp: 2, scoreValue: 18,
                shooter: false, seq: [0, 1, 2, 3], per: 4,
                apos: 0, at: 0, animFresh: false, bobOrdinal: 1,
                collisionEventWord: 1, collisionPlayerCredit: true };
              bg.air = [bird]; bg.activeCost = 10;
              const savedRandom32 = window.random32;
              window.random32 = () => 0;
              step(bg);
              window.random32 = savedRandom32;
              const birdHit = {
                hp: bird.hp,
                sy: Math.round(bird.y - bg.scroll),
                shots: bg.shots.map(s => [s.kind, s.ang]),
                kinds: eventKinds(bg), score: bg.score,
                alive: bird.alive, cost: bg.activeCost
              };

              // GOOSE nonlethal 0xc974 vrstva je custom stereo synth a
              // nasledny standardni generic-hit. Boss je vuci SMART immune.
              const gg = makeGame();
              const src = live.spawns.find(s => s.beh === 'boss');
              if (!src || !src.parts) return { err: 'boss template chybi' };
              const goose = Object.assign({}, src, {
                born: true, alive: true, st: 2, hp: 3, timer: 1000,
                x: 160, y: gg.scroll + 100, vx: .5, vy: 0,
                fireT: 100, scrollLocked: true, hitSpread: false,
                groupReleased: false, budgeted: true, bobOrdinal: 1,
                collisionEventWord: 1, collisionPlayerCredit: true,
                parts: src.parts.map(q => Object.assign({}, q, {
                  entered: true, linked: true, budgeted: true
                }))
              });
              gg.spawns = [goose]; gg.activeCost = 140;
              gg.smartPulse = 20; gg.smartPulseTasks = [20];
              step(gg);
              const gooseHit = {
                hp: goose.hp, alive: goose.alive,
                pending: goose.collisionEventWord | 0,
                kinds: eventKinds(gg), booms: gg.booms.length,
                cost: gg.activeCost
              };
              return { homing, genericAir, tokenBoth, birdHit, gooseHit };
            }""")
            expect("err" not in scheduler_callbacks,
                   scheduler_callbacks.get("err", ""))
            expect(scheduler_callbacks["homing"] == {
                     "score": 21, "booms": 3, "bigexpl": 6,
                     "shots": 0, "dead": True, "pending": 0, "cost": 0},
                   "SMART+bit0|bit3 potlacil HOMING callback po invalidaci: %s"
                   % scheduler_callbacks["homing"])
            expect(scheduler_callbacks["genericAir"] == {
                     "hp": -1, "score": 36, "booms": 3,
                     "bigexpl": 6, "air": 0, "dead": True,
                     "pending": 0, "cost": 0},
                   "SMART+bit0|bit3 potlacil generic air callback: %s" %
                   scheduler_callbacks["genericAir"])
            expect(scheduler_callbacks["tokenBoth"] == {
                     "typ": 0, "cycles": 11, "cooldown": 4,
                     "picked": 1, "tokenCount": 1,
                     "weapon": 3, "mode": 0, "inv": 99, "score": 0,
                     "tokens": 0, "dead": True, "pending": 0, "cost": 0,
                     "pickupSfx": 1},
                   "TOKEN bit0 nepredbehl bit3 nebo nebyl SMART immune: %s" %
                   scheduler_callbacks["tokenBoth"])
            expect(scheduler_callbacks["birdHit"] == {
                     "hp": 1, "sy": 94, "shots": [["can", 56]],
                     "kinds": ["cannon", "generic-hit"], "score": 0,
                     "alive": True, "cost": 10},
                   "BIRD nonlethal callback nema -6y/cannon/generic-hit: %s" %
                   scheduler_callbacks["birdHit"])
            expect(scheduler_callbacks["gooseHit"] == {
                     "hp": 2, "alive": True, "pending": 0,
                     "kinds": ["goose-hit-l", "goose-hit-r", "generic-hit"],
                     "booms": 0, "cost": 140},
                   "GOOSE nonlethal callback nema custom+generic hit vrstvy: %s"
                   % scheduler_callbacks["gooseHit"])

            # Priority-100 FIFO hrany: callback nesmi spustit nove a36a
            # childy inline, GOOSE orphan pouziva posledni publikovany field
            # a checksum parent uvolni cost az ve sve pozici mezi tasky.
            fifo_scheduler_edges = page.evaluate("""() => {
              const live = state.g;
              function makeGame(playerPatch = {}) {
                const maxTop = Math.max(1, live.mapH - 257);
                const scroll = Math.min(1000, maxTop);
                const player = Object.assign({
                  x: 20, y: 220, ang: 17, alive: true, inv: 100,
                  bubbleTimer: 0, bubbleBound: null, bubbleFrame: 9,
                  bubbleZ: 0, bubblePhase: 0, bank: 0, cool: 0,
                  weapon: 2, tokenCount: 0, mode: 0, reload: 11,
                  respawnT: 0, rank: 0, heliAnimPos: 0,
                  heliAnimFresh: true, weaponX: 20, weaponY: 220,
                  bobOrdinal: 0, collisionEventWord: 0,
                  collisionLethal: false
                }, playerPatch);
                return {
                  mapH: live.mapH, mapW: 320, mapIndex: live.mapIndex,
                  terrainOpen: live.terrainOpen,
                  tick: 0, scroll, scrollMul: 0,
                  over: false, won: false, keys: {}, player,
                  nextBobOrdinal: 50, bullets: [], shots: [], plops: [],
                  spawns: [], booms: [], effects: [], tokens: [], air: [],
                  hazards: [], activeCost: 0, score: 0,
                  nextLife: 10000, lives: 4, players: 1, difficulty: 0,
                  levelPhase: 0, rngState: 0x13579bdf, rngVhposWord: 0,
                  rotoDirectionWord: 0, fadeBlack: 0, fadeWhite: 0,
                  fadeDir: 0, fadeWhiteStep: 0, smartPulse: 0,
                  smartPulseTasks: [], tokenSfxTasks: [],
                  townExplosionTasks: [], tokensPickedUp: 0, flash: 0,
                  sfx: createTownSfxState()
                };
              }
              const kinds = g => g.sfx.events.map(e => e.kind);
              const round = n => +n.toFixed(6);

              // SMART a36a pouze zaradi explosion child. BIRD bit0 pak musi
              // spotrebovat svuj cannon RNG jeste pred dvema BIGEXPL RNG,
              // ktere child dostane az po navratu ze soucasneho tasku.
              const og = makeGame();
              const orderBird = {
                kind: 'bird', x: 160, y: og.scroll + 100,
                vx: 0, vy: 0, alive: true, pending: false, dead: false,
                cost: 10, budgeted: true, hp: 2, scoreValue: 18,
                shooter: false, seq: [0, 1, 2, 3], per: 4,
                apos: 0, at: 0, animFresh: false, bobOrdinal: 1,
                collisionEventWord: 1, collisionPlayerCredit: true
              };
              og.air = [orderBird]; og.activeCost = 10; og.smartPulse = 20;
              const savedRandom32 = window.random32;
              const rngTrace = [], rngValues = [5, 11, 22];
              window.random32 = () => {
                const value = rngValues[rngTrace.length] ?? 0x44;
                rngTrace.push(value); return value;
              };
              let queuedA36a;
              try {
                const task = { kind: 'air', o: orderBird, ordinal: 1 };
                resumeTownObjectHousekeeping(og, task);
                queuedA36a = {
                  birdHp: orderBird.hp,
                  cannonAngle: og.shots[0] ? og.shots[0].ang : null,
                  rng: rngTrace.slice(), kinds: kinds(og),
                  booms: og.booms.length,
                  queued: og.townExplosionTasks.length,
                  invalidated: !!orderBird.retireAfterField
                };
                retireTownTaskAfterField(og, task);
                runFreshTownExplosionTasks(og);
                queuedA36a.after = {
                  rng: rngTrace.slice(), kinds: kinds(og),
                  booms: og.booms.length,
                  queued: og.townExplosionTasks.length,
                  alive: orderBird.alive, cost: og.activeCost
                };
              } finally { window.random32 = savedRandom32; }

              // Escort +542 musi explodovat na posledni pozici, kterou jeho
              // task skutecne publikoval. Nasledna kompenzace parenta ji uz
              // nesmi posunout. Zbytek snake kodu spotrebuje 2/1/0 RNG.
              const pg = makeGame();
              const publishedEscort = newBossChild(BOSS_ESCORT, 0, true);
              Object.assign(publishedEscort, {
                phase: 'linked', entered: true, linked: true,
                ox: 7.25, oy: 18.5, frame: 8, bobOrdinal: 2,
                budgeted: true, cost: 10
              });
              const publishedBoss = {
                beh: 'boss', file: 'GOOSE.LIN', idx: 0,
                born: true, taskStarted: true, armed: true, alive: true,
                x: 123.5, y: pg.scroll + 81.25, hp: 25,
                st: 1, assemblyLeft: 1, parts: [publishedEscort],
                bodyHidden: true, bodyFrame: 0, rotorActive: false,
                hitSpread: false, groupReleased: false, bobOrdinal: 1
              };
              pg.spawns = [publishedBoss]; pg.activeCost = 10;
              stepBossParts(pg, publishedBoss, 0);
              const published = {
                x: round(publishedEscort.publishedWorldX),
                y: round(publishedEscort.publishedWorldY),
                scroll: round(pg.scroll),
                screen: [
                  round(bossPartPosition(publishedBoss, publishedEscort,
                                         pg.scroll).x),
                  round(bossPartPosition(publishedBoss, publishedEscort,
                                         pg.scroll).y)
                ],
                rendered: composeTownBobs(pg, Math.floor(pg.scroll)).ordered
                  .some(r => r.id === 'boss-escort-main')
              };
              publishedBoss.x += 41; publishedBoss.y += 19;
              const orphanStages = [];
              for (let stage = 0; stage < 10; stage++) {
                const sg = makeGame();
                const sq = Object.assign({}, publishedEscort, {
                  phase: 'snake', snakeStage: stage,
                  alive: true, dead: false, entered: true, linked: true,
                  orphanPending: true, budgeted: true, cost: 10
                });
                const sb = Object.assign({}, publishedBoss, {
                  alive: false, groupReleased: true, parts: [sq]
                });
                sg.activeCost = 10; sg.rngState = 0x2468ace0 + stage;
                let rngCalls = 0;
                window.random32 = gg => { rngCalls++; return savedRandom32(gg); };
                try { resumeBossPartOrphan(sg, sb, sq); }
                finally { window.random32 = savedRandom32; }
                const explosion = sg.townExplosionTasks[0];
                orphanStages.push({
                  stage, rngCalls,
                  pos: explosion ? [round(explosion.x), round(explosion.y)] : null,
                  queued: sg.townExplosionTasks.length,
                  alive: sq.alive, budgeted: sq.budgeted,
                  cost: sg.activeCost
                });
              }

              // Body child, ktery pri unlinku jeste spi, dokonci delay,
              // projde a2c6 a jeden creation field. +542 jej uklidi teprve
              // pri nasledujicim vlastnim resume.
              const sg = makeGame();
              const sleeper = newBossChild(BOSS_BODY_PARTS[0], 0, false);
              Object.assign(sleeper, {
                bobOrdinal: 2, orphanPending: true,
                alive: true, dead: false, entered: false,
                budgeted: false
              });
              const sleepingBoss = {
                beh: 'boss', file: 'GOOSE.LIN', idx: 0,
                born: true, taskStarted: true, armed: true, alive: false,
                x: 160, y: sg.scroll + 80, hp: 0, st: 1,
                assemblyLeft: 1, parts: [sleeper], bodyHidden: true,
                bodyFrame: 0, rotorActive: false, hitSpread: false,
                groupReleased: true, budgeted: false, bobOrdinal: 1
              };
              sg.spawns = [sleepingBoss];
              let sleeperRng = 0;
              window.random32 = gg => { sleeperRng++; return savedRandom32(gg); };
              try { stepRetiredBossParts(sg, 0); }
              finally { window.random32 = savedRandom32; }
              const creationField = {
                entered: sleeper.entered, phase: sleeper.phase,
                alive: sleeper.alive, budgeted: sleeper.budgeted,
                cost: sg.activeCost, rngCalls: sleeperRng,
                resumeTasks: townCollisionResumeTasks(sg)
                  .filter(t => t.kind === 'bossPart' && t.o === sleeper).length,
                published: Number.isFinite(sleeper.publishedWorldX) &&
                           Number.isFinite(sleeper.publishedWorldY),
                rendered: composeTownBobs(sg, Math.floor(sg.scroll)).ordered
                  .some(r => r.id === 'boss-left-main')
              };
              step(sg);
              const sleeperCleanup = {
                alive: sleeper.alive, dead: sleeper.dead,
                budgeted: sleeper.budgeted, cost: sg.activeCost,
                rendered: composeTownBobs(sg, Math.floor(sg.scroll)).ordered
                  .some(r => r.id === 'boss-left-main')
              };

              // Sweep N ulozi kontakt obema taskum. V N+1 je player task
              // prvni: nechranena HELI zemre jeste pred c974, takze living
              // player count pri dropBossTokens je nula.
              const cg = makeGame({
                x: 160, y: 100, inv: 0, bubbleTimer: 0,
                weaponX: 160, weaponY: 100
              });
              const contactBoss = {
                beh: 'boss', file: 'GOOSE.LIN', idx: 0,
                born: true, taskStarted: true, armed: true, alive: true,
                x: 160, y: cg.scroll + 100, vx: 0, vy: 0,
                hp: 1, timer: 503, fireT: 100, st: 1,
                assemblyLeft: 1, parts: [], bodyHidden: false,
                bodyFrame: 0, rotorActive: false, rotorTick: 0,
                hitSpread: false, scrollLocked: true,
                groupReleased: false, budgeted: true, cost: 100,
                bobOrdinal: 1, collisionEventWord: 0,
                collisionPlayerCredit: false
              };
              cg.spawns = [contactBoss]; cg.activeCost = 100;
              step(cg);                         // N: pouze collision word
              const contactQueued = {
                playerAlive: cg.player.alive,
                playerLethal: !!cg.player.collisionLethal,
                bossHp: contactBoss.hp,
                bossMask: contactBoss.collisionEventWord | 0,
                tokens: cg.tokens.length
              };
              step(cg);                         // N+1: player -> boss
              const contactResolved = {
                playerAlive: cg.player.alive,
                bossAlive: contactBoss.alive, bossHp: contactBoss.hp,
                tokens: cg.tokens.length,
                bossDeath: kinds(cg)
                  .filter(k => k.startsWith('goose-death')).length
              };

              // Due checksum parent lezi FIFO mezi dvema BIRD tasky. Jeho
              // cost setter zaznamena presny okamzik release bez zavislosti
              // na nazvu scheduler helperu.
              const tg = makeGame();
              const makeBird = (ordinal, x) => ({
                kind: 'bird', x, y: tg.scroll + 100,
                vx: 0, vy: 0, alive: true, pending: false, dead: false,
                cost: 10, budgeted: true, hp: 2, scoreValue: 18,
                shooter: false, seq: [0, 1, 2, 3], per: 4,
                apos: 0, at: 0, animFresh: false, bobOrdinal: ordinal,
                collisionEventWord: 1, collisionPlayerCredit: true
              });
              const earlyBird = makeBird(1, 120), lateBird = makeBird(20, 220);
              let parentBudgeted = true, releaseMoment = null;
              const tailBoss = {
                beh: 'boss', file: 'GOOSE.LIN', idx: 0,
                born: true, taskStarted: true, armed: true, alive: false,
                x: 160, y: tg.scroll + 80, hp: 0, st: 1,
                assemblyLeft: 1, parts: [], bodyHidden: true,
                bodyFrame: 0, rotorActive: false, hitSpread: false,
                groupReleased: true, checksumReleaseTick: 1,
                checksumDone: false, cost: 100, bobOrdinal: 10
              };
              Object.defineProperty(tailBoss, 'budgeted', {
                configurable: true, enumerable: true,
                get: () => parentBudgeted,
                set: value => {
                  if (parentBudgeted && !value) releaseMoment = {
                    earlyHp: earlyBird.hp, lateHp: lateBird.hp,
                    shots: tg.shots.length, kinds: kinds(tg)
                  };
                  parentBudgeted = value;
                }
              });
              tg.air = [lateBird, earlyBird];
              tg.spawns = [tailBoss]; tg.activeCost = 120;
              step(tg);
              const checksumPriority = {
                releaseMoment,
                final: {
                  earlyHp: earlyBird.hp, lateHp: lateBird.hp,
                  shots: tg.shots.length, cost: tg.activeCost,
                  parentBudgeted, checksumDone: tailBoss.checksumDone
                }
              };

              return { queuedA36a, published, orphanStages,
                       creationField, sleeperCleanup,
                       contactQueued, contactResolved, checksumPriority };
            }""")
            expect(fifo_scheduler_edges["queuedA36a"] == {
                     "birdHp": 1, "cannonAngle": 61,
                     "rng": [5], "kinds": ["cannon", "generic-hit"],
                     "booms": 0, "queued": 1, "invalidated": True,
                     "after": {
                       "rng": [5, 11, 22],
                       "kinds": ["cannon", "generic-hit",
                                 "bigexpl", "bigexpl"],
                       "booms": 1, "queued": 0,
                       "alive": False, "cost": 0}},
                   "SMART a36a se spustil inline nebo predběhl BIRD RNG: %s"
                   % fifo_scheduler_edges["queuedA36a"])
            published = fifo_scheduler_edges["published"]
            expect(published["x"] == 130.75 and
                   published["screen"] == [130.75, 99.75] and
                   abs(published["y"] -
                       (published["screen"][1] + published["scroll"])) < 1e-6 and
                   published["rendered"] is True,
                   "GOOSE escort nema skutecnou posledni publikovanou pozici: %s"
                   % published)
            expected_orphan_rng = [2, 2, 2, 2, 1, 1, 1, 1, 1, 0]
            for row, rng_count in zip(
                    fifo_scheduler_edges["orphanStages"], expected_orphan_rng):
                expect(row["rngCalls"] == rng_count and
                       row["pos"] == [published["x"], published["y"]] and
                       row["queued"] == 1 and row["alive"] is False and
                       row["budgeted"] is False and row["cost"] == 0,
                       "GOOSE escort orphan stage %d nema pozici/RNG 2-1-0: %s"
                       % (row["stage"], row))
            expect(fifo_scheduler_edges["creationField"] == {
                     "entered": True, "phase": "straight",
                     "alive": True, "budgeted": True, "cost": 10,
                     "rngCalls": 1, "resumeTasks": 1,
                     "published": True, "rendered": True},
                   "spici GOOSE body nema jeden post-death creation field: %s"
                   % fifo_scheduler_edges["creationField"])
            expect(fifo_scheduler_edges["sleeperCleanup"] == {
                     "alive": False, "dead": True,
                     "budgeted": False, "cost": 0, "rendered": False},
                   "spici GOOSE body se neuvolnil az na dalsim resume: %s"
                   % fifo_scheduler_edges["sleeperCleanup"])
            expect(fifo_scheduler_edges["contactQueued"] == {
                     "playerAlive": True, "playerLethal": True,
                     "bossHp": 1, "bossMask": 8, "tokens": 0},
                   "GOOSE contact nevydrzel jako dvojice eventu do N+1: %s"
                   % fifo_scheduler_edges["contactQueued"])
            expect(fifo_scheduler_edges["contactResolved"] == {
                     "playerAlive": False, "bossAlive": False,
                     "bossHp": 0, "tokens": 0, "bossDeath": 2},
                   "player task nepredbehl GOOSE token callback: %s"
                   % fifo_scheduler_edges["contactResolved"])
            expect(fifo_scheduler_edges["checksumPriority"] == {
                     "releaseMoment": {
                       "earlyHp": 1, "lateHp": 2, "shots": 1,
                       "kinds": ["cannon", "generic-hit"]},
                     "final": {
                       "earlyHp": 1, "lateHp": 1, "shots": 2,
                       "cost": 20, "parentBudgeted": False,
                       "checksumDone": True}},
                   "GOOSE checksum cost se neuvolnil v parent FIFO pozici: %s"
                   % fifo_scheduler_edges["checksumPriority"])

            # Bonus TOKEN (0x96d8): 32t radialni burst, pak blikani a
            # hit-cooldown. Typ 3 pridava invulnerability, neni MINE bublina.
            token = page.evaluate("""() => {
              const g = state.g, p = g.player;
              g.scrollMul = 0;
              const mk = typ => {
                const k = { x: 100, y: g.scroll + 100, ang: 64,
                            vx: 0, vy: .5, typ, cycles: 12, blink: false,
                            hitCooldown: -1, burst: 0, phase: 'active',
                            interactive: true, activeHalf: 0, dead: false };
                g.tokens = [k]; return k;
              };
              // GOOSE vzdy vypusti typ3 rychlosti 1.25 px/t, 32 tiku
              // neinteraktivni; potom vynuluje vx a pada 0.5 px/t.
              g.tokens = [];
              const savedRandom = window.random32; window.random32 = () => 0;
              dropBossTokens(g, { x: 160, y: g.scroll + 120 }, 1);
              window.random32 = savedRandom;
              const burstK = g.tokens[0];
              const burstStart = { typ: burstK.typ, phase: burstK.phase,
                interactive: burstK.interactive, burst: burstK.burst,
                vx: burstK.vx, vy: burstK.vy };
              for (let i = 0; i < 31; i++) stepTokens(g, 0);
              const burst31 = { phase: burstK.phase, interactive: burstK.interactive,
                                burst: burstK.burst };
              stepTokens(g, 0);
              const burst32 = { phase: burstK.phase, interactive: burstK.interactive,
                burst: burstK.burst, x: burstK.x, vx: burstK.vx, vy: burstK.vy };
              stepTokens(g, 0);
              const active33 = { phase: burstK.phase,
                interactive: burstK.interactive, x: burstK.x, y: burstK.y,
                vx: burstK.vx, vy: burstK.vy,
                cooldown: burstK.hitCooldown, blink: burstK.blink,
                activeHalf: burstK.activeHalf };
              const burstY = burstK.y;
              shootToken(g, burstK);
              const immediate = { typ: burstK.typ, cycles: burstK.cycles,
                cooldown: burstK.hitCooldown, dy: burstK.y - burstY };
              burstK.y = g.scroll + 400;
              const offscreenCost = g.activeCost;
              stepTokens(g, 0);
              const offscreen = { present: g.tokens.includes(burstK),
                dead: burstK.dead, retire: !!burstK.retireAfterField,
                activeCost: g.activeCost,
                beforeCost: offscreenCost };
              // 0x6480 pouze invaliduje prave publikovany field. Skutecny
              // release cost/tasku probiha az pri priority-100 resume N+1.
              step(g);
              const offscreenClean = { present: g.tokens.includes(burstK),
                dead: burstK.dead, activeCost: g.activeCost };
              // Stejna poloha je behem burstu zamerne bounds-imunni.
              g.tokens = [];
              const savedRandom2 = window.random32; window.random32 = () => 0;
              dropBossTokens(g, { x: 160, y: g.scroll + 120 }, 1);
              window.random32 = savedRandom2;
              const immuneK = g.tokens[0]; immuneK.y = g.scroll + 400;
              const immuneCost = g.activeCost; stepTokens(g, 0);
              const burstBounds = { present: g.tokens.includes(immuneK),
                dead: immuneK.dead, activeCost: g.activeCost,
                beforeCost: immuneCost };
              releaseToken(g, immuneK);

              // strela: typ obiha 0->1->2->3->0
              const k = mk(0), cycle = [];
              for (let i = 0; i < 5; i++) {
                k.hitCooldown = -1; shootToken(g, k); cycle.push(k.typ);
              }
              // Po 12 obezich je typ4 jen dele chraneny, nikoli trvale zamceny.
              const k2 = mk(0);
              for (let i = 0; i < 12 * 4; i++) {
                k2.hitCooldown = -1; shootToken(g, k2);
              }
              const locked = { typ: k2.typ, cooldown: k2.hitCooldown };
              k2.y = g.scroll + 100;
              for (let i = 0; i < 24; i++) stepTokens(g, 0);
              const y0 = k2.y; shootToken(g, k2);
              const blocked = { typ: k2.typ, dy: k2.y - y0,
                                cooldown: k2.hitCooldown };
              stepTokens(g, 0); k2.y += 8; shootToken(g, k2);
              const unlocked = k2.typ;
              const k3 = mk(3); let accepted = 0;
              while (k3.typ !== 4 && accepted < 60) {
                k3.hitCooldown = -1; shootToken(g, k3); accepted++;
              }
              const fromGuard = { accepted, typ: k3.typ };
              // ucinky
              const eff = {};
              p.alive = true; p.inv = 0; p.weapon = 0; p.tokenCount = 0; p.mode = 0;
              p.reload = null; g.score = 0; g.fadeWhite = 0;
              pickupToken(g, mk(3));
              runFreshTownPriorityTasks(g);
              eff.guard = { inv: p.inv, score: g.score };
              p.reload = null;
              pickupToken(g, mk(2));
              runFreshTownPriorityTasks(g);
              eff.rate = p.reload;
              pickupToken(g, mk(4));
              runFreshTownPriorityTasks(g);
              eff.max = { weapon: p.weapon, reload: p.reload,
                          fadeWhite: g.fadeWhite, fadeStep: g.fadeWhiteStep };
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
              // Pickup callback je vzdy harmless a jen token odstrani.
              p.inv = 0; p.alive = true; p.x = 100; p.y = 100;
              const kk = mk(1); pickupToken(g, kk);
              eff.harmless = p.alive && kk.dead;
              g.smartPulse = 0; g.fadeWhite = 0; // izolace dalsich main-state testu
              return { burstStart, burst31, burst32, active33,
                       immediate, offscreen, offscreenClean,
                       burstBounds,
                       cycle, locked, blocked, unlocked, fromGuard, eff };
            }""")
            expect(token["burstStart"] == {
                     "typ": 3, "phase": "burst", "interactive": False,
                     "burst": 32, "vx": 1.25, "vy": -1},
                   "GOOSE TOKEN nema presny pocatecni radialni burst: %s"
                   % token["burstStart"])
            expect(token["burst31"] == {
                     "phase": "burst", "interactive": False, "burst": 1} and
                   token["burst32"] == {
                     "phase": "transition", "interactive": False, "burst": 0,
                     "x": 200, "vx": 1.25, "vy": -1} and
                   token["active33"]["phase"] == "active" and
                   token["active33"]["interactive"] is True and
                   token["active33"]["x"] == 200 and
                   token["active33"]["vx"] == 0 and
                   token["active33"]["vy"] == 0.5 and
                   token["active33"]["cooldown"] == -1 and
                   token["active33"]["blink"] is False and
                   token["active33"]["activeHalf"] == 1,
                   "TOKEN nema 32 burst VBL + active resume na 33.: %s / %s / %s"
                   % (token["burst31"], token["burst32"], token["active33"]))
            expect(token["immediate"] == {
                     "typ": 0, "cycles": 11, "cooldown": 4, "dy": -8} and
                   token["offscreen"]["present"] is True and
                   token["offscreen"]["dead"] is False and
                   token["offscreen"]["retire"] is True and
                   token["offscreen"]["activeCost"] ==
                     token["offscreen"]["beforeCost"] and
                   token["offscreenClean"] == {
                     "present": False, "dead": True,
                     "activeCost": token["offscreen"]["beforeCost"] - 5} and
                   token["burstBounds"]["present"] is True and
                   token["burstBounds"]["dead"] is False and
                   token["burstBounds"]["activeCost"] ==
                     token["burstBounds"]["beforeCost"],
                   "TOKEN nema burst bounds imunitu/active N/N+1 cull: %s / %s / %s / %s"
                   % (token["immediate"], token["offscreen"],
                      token["offscreenClean"], token["burstBounds"]))
            expect(token["cycle"] == [1, 2, 3, 0, 1],
                   "strela neprepina typ bonusu po 0x9780: %s" % token["cycle"])
            expect(token["locked"] == {"typ": 4, "cooldown": 12} and
                   token["blocked"] == {"typ": 4, "dy": -8, "cooldown": 0} and
                   token["unlocked"] == 1,
                   "typ4 nema docasny 12-cyklovy cooldown/y-knockback: %s"
                   % token)
            expect(token["fromGuard"] == {"accepted": 45, "typ": 4},
                   "GOOSE typ3 TOKEN nema 45 prijatych hitu do typu4: %s"
                   % token["fromGuard"])
            expect(token["eff"]["guard"] == {"inv": 500, "score": 500},
                   "typ 3 nedal 500 tiku ochrany a 500 bodu: %s"
                   % token["eff"]["guard"])
            expect(token["eff"]["rate"] == 8,
                   "typ 2 nezkratil prodlevu palby na 8: %s"
                   % token["eff"]["rate"])
            expect(token["eff"]["max"] == {"weapon": 6, "reload": 8,
                                              "fadeWhite": 256,
                                              "fadeStep": -4},
                   "typ 4 nedal plnou silu: %s" % token["eff"]["max"])
            expect(token["eff"]["power"]["afterSame"] == 1 and
                   token["eff"]["power"]["afterSwitch"] == 1 and
                   token["eff"]["power"]["mode"] == 1,
                   "sila se ma pridat jen pri shodnem rezimu: %s"
                   % token["eff"]["power"])
            expect(token["eff"]["counter"] == {
                     "afterFive": {"count": 5, "weapon": 0,
                                   "text": "HELI 3[ 3* 0000000"},
                     "capped": 19
                   }, "HUD token counter +102 nesedi nebo neni oddelen od "
                      "sily +100: %s" % token["eff"]["counter"])
            expect(token["eff"]["harmless"] is True,
                   "bonus hrace zranil - nikdy nesmi")

            # Skutecny ochranny oblouk je shootable MINE core (0x9860),
            # nikoli TOKEN typ3. Hlida scheduler frame, z +/-2, cost a konec.
            bubble = page.evaluate("""() => {
              const live = state.g;
              const makeGame = alive => ({
                mapH: live.mapH, mapIndex: live.mapIndex,
                tick: 0, scroll: 1000, scrollMul: 0,
                over: false, won: false, keys: {},
                player: { x: 120, y: 100, ang: 192, alive, inv: 0,
                  bubbleTimer: 0, bubbleFrame: 9, bubbleZ: 0,
                  bubblePhase: 0, bubbleBound: null,
                  bank: 0, cool: 0, weapon: 0, tokenCount: 0,
                  mode: 0, reload: null, respawnT: 0,
                  heliAnimPos: 0, heliAnimFresh: true,
                  weaponX: 120, weaponY: 100, bobOrdinal: 0 },
                nextBobOrdinal: 1,
                bullets: [], shots: [], plops: [], spawns: [], booms: [],
                effects: [], tokens: [], air: [], hazards: [],
                activeCost: 0, score: 0, nextLife: 10000, lives: 4,
                players: 1, rotoDirectionWord: 0,
                fadeBlack: 0, fadeWhite: 0, fadeDir: 0, fadeWhiteStep: 0
              });
              const coreAtPlayer = g => ({
                kind: 'minecore', file: 'MINE.LIN',
                x: g.player.x, y: g.scroll + g.player.y,
                vx: 0, vy: .5, scrollLocked: true,
                alive: true, dead: false, harmless: true,
                cost: 5, budgeted: true, hp: 10, scoreValue: 30,
                seq: [9, 10], per: 1, apos: 0, at: 0, consumed: 0
              });

              const g = makeGame(true), core = coreAtPlayer(g);
              // fp@(3542) je WORD: screen-y = world-y - floor(scroll)
              const corePose = h => [h.x, h.y - Math.floor(g.scroll), h.apos];
              g.hazards = [core]; g.activeCost = 5;
              step(g);                         // VBL N: pending contact bit3
              const queuedPickup = [g.player.bubbleTimer, core.consumed,
                                    core.collisionEventWord | 0];
              step(g);                         // VBL N+1 callback: +106=-1
              // Consumed task dale dela +367 bit4 compensation. Ve world-y
              // se tedy posouva s mapou, ale publikovana screen poloha mrzne.
              const pickedPose = corePose(core);
              const pickup = { alive: g.player.alive,
                timer: g.player.bubbleTimer, consumed: core.consumed,
                child: g.player.bubbleBound, activeCost: g.activeCost,
                sfx: g.sfx.events.map(e => e.kind) };
              step(g);                         // N+2: -1->500 a child #9
              const firstOrder = composeTownBobs(g, Math.floor(g.scroll)).ordered;
              const first = { timer: g.player.bubbleTimer,
                inv: g.player.inv, frame: g.player.bubbleBound.frame,
                z: g.player.bubbleBound.z, activeCost: g.activeCost,
                bubbleAt: firstOrder.findIndex(r => r.id === 'player-bubble-main'),
                playerAt: firstOrder.findIndex(r => r.id === 'player-main'),
                coreVisible: firstOrder.some(r =>
                  r.id === 'hazard-minecore-main'),
                coreFrozen: corePose(core), pickedPose,
                bubbleKinds: firstOrder.filter(r =>
                  r.id.startsWith('player-bubble')).map(r => r.kind),
                sfx: g.sfx.events.map(e => e.kind) };
              step(g);                         // 500->499, #10 za hracem
              const secondOrder = composeTownBobs(g, Math.floor(g.scroll)).ordered;
              const second = { timer: g.player.bubbleTimer,
                inv: g.player.inv, frame: g.player.bubbleBound.frame,
                z: g.player.bubbleBound.z,
                bubbleAt: secondOrder.findIndex(r => r.id === 'player-bubble-main'),
                playerAt: secondOrder.findIndex(r => r.id === 'player-main') };

              // Druhy core aktivni ochranu neprodlouzi; pouze bily flash.
              const duplicate = coreAtPlayer(g);
              g.activeCost += 5;
              const beforeTimer = g.player.bubbleTimer;
              pickupMineCore(g, duplicate);
              runFreshTownPriorityTasks(g);
              const duplicateResult = { timer: g.player.bubbleTimer,
                beforeTimer, alive: duplicate.alive, activeCost: g.activeCost,
                fade: g.fadeWhite, step: g.fadeWhiteStep,
                sfx: g.sfx.events.map(e => e.kind) };
              for (let i = 0; i < 63; i++) stepFade(g);
              const fade63 = g.fadeWhite; stepFade(g); const fade64 = g.fadeWhite;

              // Prvni core opravdu prezije wait10 a pak uvolni vlastni cost5.
              for (let i = 0; i < 7; i++) step(g);
              const wait9 = { alive: core.alive, consumed: core.consumed,
                              activeCost: g.activeCost,
                              frozen: corePose(core) };
              step(g);
              const wait10 = { alive: core.alive,
                present: g.hazards.includes(core), activeCost: g.activeCost };

              // U konce: 2->1 jeste #10 vzadu, 1->0 uz child kill/cost release.
              g.player.bubbleTimer = 2;
              g.player.bubbleBound.phase = 0;
              g.player.bubbleBound.frame = 9; g.player.bubbleBound.z = 2;
              step(g);
              const penultimateOrder = composeTownBobs(
                g, Math.floor(g.scroll)).ordered;
              const penultimate = { timer: g.player.bubbleTimer,
                frame: g.player.bubbleBound.frame, z: g.player.bubbleBound.z,
                bubbleAt: penultimateOrder.findIndex(r =>
                  r.id === 'player-bubble-main'),
                playerAt: penultimateOrder.findIndex(r => r.id === 'player-main') };
              step(g);
              const expired = { timer: g.player.bubbleTimer,
                child: g.player.bubbleBound, activeCost: g.activeCost,
                inv: g.player.inv,
                visible: composeTownBobs(g, Math.floor(g.scroll)).ordered
                  .some(r => r.id === 'player-bubble-main') };
              step(g);
              const after = { inv: g.player.inv, activeCost: g.activeCost };

              // Shoot-to-death core: 30 bodu, white flash, zadny damage hraci.
              const gs = makeGame(false), shotCore = coreAtPlayer(gs);
              shotCore.x = 180; shotCore.hp = 1;
              gs.hazards = [shotCore]; gs.activeCost = 5;
              gs.bullets = [{
                x: shotCore.x,
                y: (shotCore.y - gs.scroll) + 9
              }];
              step(gs);
              const shotQueued = [shotCore.alive, shotCore.hp,
                                  gs.bullets.length,
                                  shotCore.collisionEventWord | 0];
              step(gs);
              const shot = { alive: shotCore.alive, score: gs.score,
                activeCost: gs.activeCost, fade: gs.fadeWhite,
                fadeStep: gs.fadeWhiteStep, booms: gs.booms.length,
                sfx: gs.sfx.events.map(e => [e.kind, e.accepted]),
                guards: gs.sfx.voices.map(v => v.guard),
                rng: gs.rngState >>> 0 };

              // Inv bit3 vyplni index9 jen player main; shadow zustava clear.
              const gw = makeGame(true); gw.player.inv = 8;
              const playerQueue = composeTownBobs(
                gw, Math.floor(gw.scroll)).ordered;
              const whiteRecords = playerQueue.filter(r =>
                  r.id.startsWith('player-')).map(r => [r.id, r.op]);
              const bodyRec = playerQueue.find(r => r.id === 'player-main');
              const gunRec = playerQueue.find(r => r.id === 'player-gun-main');
              const playerVisual = {
                body0: bodyRec.spr === indexedFrameFor(state, 'JEEPHELI.LIN', 0),
                gun: !!gunRec, bodyKey: bodyRec.key
              };
              const go = makeGame(true);
              go.activeCost = 160; go.player.bubbleTimer = -1;
              step(go);
              const overBudget = { timer: go.player.bubbleTimer,
                frame: go.player.bubbleBound.frame, z: go.player.bubbleBound.z,
                visible: go.player.bubbleBound.visible,
                activeCost: go.activeCost };
              go.player.bubbleTimer = 1; step(go);
              overBudget.released = go.activeCost;

              const gc = { activeCost: 160, hazards: [], effects: [], booms: [],
                score: 0, nextLife: 10000, lives: 4 };
              spawnMineCore(gc, { x: 10, y: 20 });
              const coreBudget = { activeCost: gc.activeCost,
                                   count: gc.hazards.length };

              // Shodne z32: pozdeji zalozeny enemy se enqueueuje pozdeji,
              // BOB inserter jej kresli driv; starsi player zustane navrchu.
              const gz = makeGame(true);
              gz.player.bobOrdinal = 0; gz.nextBobOrdinal = 2;
              gz.air = [{ kind: 'bird', x: gz.player.x,
                y: gz.scroll + gz.player.y, alive: true, bobOrdinal: 1,
                seq: [0], apos: 0, hitFlash: false }];
              const zOrder = composeTownBobs(
                gz, Math.floor(gz.scroll)).ordered;
              const equalZ = {
                airAt: zOrder.findIndex(r => r.id === 'air-bird-main'),
                playerAt: zOrder.findIndex(r => r.id === 'player-main')
              };

              // White flash soucasne drzi 50t smart pulse. Default enemy
              // tasky umrou bez score; player/TOKEN/bubble/GOOSE jsou immune.
              const gp = makeGame(true);
              const normal = { born: true, alive: true, beh: 'camogun',
                x: 30, y: gp.scroll + 40, cost: 10, budgeted: true };
              const immuneBoss = { born: true, alive: true, beh: 'boss',
                x: 50, y: gp.scroll + 50, cost: 100, budgeted: true };
              const pulseAir = { alive: true, pending: false, dead: false,
                x: 60, y: gp.scroll + 60, cost: 10, budgeted: true };
              const pulseHazard = { alive: true, dead: false, kind: 'proxfrag',
                x: 70, y: gp.scroll + 70, cost: 5, budgeted: true };
              const immuneToken = { dead: false, alive: true, cost: 5,
                                    budgeted: true };
              const immuneBubble = { started: true, visible: true, cost: 5,
                                     budgeted: true };
              gp.spawns = [normal, immuneBoss]; gp.air = [pulseAir];
              gp.hazards = [pulseHazard]; gp.tokens = [immuneToken];
              gp.player.bubbleBound = immuneBubble;
              gp.shots = [{ kind: 'can', x: 10, y: 10 },
                          { kind: 'hom', x: 20, y: 20 }];
              gp.activeCost = 135; startWhiteFlash(gp);
              runFreshTownPriorityTasks(gp); applySmartPulse(gp);
              const pulseQueued = {
                booms: gp.booms.length,
                queued: (gp.townExplosionTasks || []).length,
                bigexpl: (gp.sfx && gp.sfx.events || [])
                  .filter(e => e.kind === 'bigexpl').length,
                rng: Number.isInteger(gp.rngState) ? gp.rngState : null
              };
              runFreshTownExplosionTasks(gp);
              const pulse = { smart: gp.smartPulse, normal: normal.alive,
                boss: immuneBoss.alive, air: pulseAir.alive,
                hazard: pulseHazard.alive, token: immuneToken.dead,
                bubble: gp.player.bubbleBound === immuneBubble,
                player: gp.player.alive, shots: gp.shots.length,
                activeCost: gp.activeCost, score: gp.score,
                booms: gp.booms.length };
              const gd = makeGame(false); startWhiteFlash(gd);
              runFreshTownPriorityTasks(gd);
              for (let i = 0; i < 49; i++) step(gd);
              const pulse49 = gd.smartPulse; step(gd); const pulse50 = gd.smartPulse;
              return { queuedPickup, pickup, first, second,
                       duplicate: duplicateResult,
                       fade63, fade64, wait9, wait10, penultimate,
                       expired, after, shotQueued, shot,
                       whiteRecords, playerVisual,
                       overBudget, coreBudget, equalZ,
                       pulseQueued, pulse, pulse49, pulse50 };
            }""")
            expect(bubble["queuedPickup"] == [0, 0, 8],
                   "MINE core pickup callback probehl uz ve VBL N: %s" %
                   bubble["queuedPickup"])
            expect(bubble["pickup"] == {
                     "alive": True, "timer": -1, "consumed": 10,
                     "child": None, "activeCost": 5, "sfx": []},
                   "MINE core neni harmless pickup s wait10: %s"
                   % bubble["pickup"])
            expect(bubble["first"]["timer"] == 500 and
                   bubble["first"]["inv"] == 0 and
                   bubble["first"]["frame"] == 9 and
                   bubble["first"]["z"] == 2 and
                   bubble["first"]["activeCost"] == 10 and
                   bubble["first"]["bubbleAt"] > bubble["first"]["playerAt"] and
                   bubble["first"]["coreVisible"] is False and
                   [round(v, 3) for v in bubble["first"]["coreFrozen"]] ==
                   [round(v, 3) for v in bubble["first"]["pickedPose"]] and
                   bubble["first"]["bubbleKinds"] == ["main"] and
                   bubble["first"]["sfx"] == ["shield-bubble"],
                   "prvni bubble frame neni MINE#9 pred hracem bez stinu: %s"
                   % bubble["first"])
            expect(bubble["second"]["timer"] == 499 and
                   bubble["second"]["inv"] == 99 and
                   bubble["second"]["frame"] == 10 and
                   bubble["second"]["z"] == -2 and
                   bubble["second"]["bubbleAt"] < bubble["second"]["playerAt"],
                   "druhy bubble frame neni MINE#10 za hracem: %s"
                   % bubble["second"])
            expect(bubble["duplicate"] == {
                     "timer": 499, "beforeTimer": 499, "alive": False,
                     "activeCost": 10, "fade": 256, "step": -4,
                     "sfx": ["shield-bubble"] + ["smart-bomb"] * 4} and
                   bubble["fade63"] == 4 and bubble["fade64"] == 0,
                   "duplicitni core prodlouzil bublinu nebo nema 64t flash: %s"
                   % bubble["duplicate"])
            expect(bubble["wait9"] == {
                     "alive": True, "consumed": 1, "activeCost": 10,
                     "frozen": bubble["first"]["pickedPose"]} and
                   bubble["wait10"] == {
                     "alive": False, "present": False, "activeCost": 5},
                   "sebrany core nema presny 10tikovy cleanup: %s / %s"
                   % (bubble["wait9"], bubble["wait10"]))
            expect(bubble["penultimate"]["timer"] == 1 and
                   bubble["penultimate"]["frame"] == 10 and
                   bubble["penultimate"]["z"] == -2 and
                   bubble["penultimate"]["bubbleAt"] <
                     bubble["penultimate"]["playerAt"] and
                   bubble["expired"] == {"timer": 0, "child": None,
                     "activeCost": 0, "inv": 99, "visible": False} and
                   bubble["after"] == {"inv": 98, "activeCost": 0},
                   "bubble konec nema posledni #10 a cleanup pri 1->0: %s / %s"
                   % (bubble["penultimate"], bubble["expired"]))
            expect(bubble["shotQueued"] == [True, 1, 1, 1],
                   "MINE core damage probehl uz ve VBL N: %s" %
                   bubble["shotQueued"])
            expect(bubble["shot"] == {"alive": False, "score": 30,
                     "activeCost": 0, "fade": 256, "fadeStep": -4,
                     "booms": 1,
                     "sfx": [["smart-bomb", True]] * 4 +
                            [["bigexpl", False]] * 2,
                     "guards": [508, 508, 508, 508],
                     "rng": 0x3B0E5682},
                   "rozstreleny core nema 30 bodu/white flash/cleanup: %s"
                   % bubble["shot"])
            expect(sorted(bubble["whiteRecords"]) ==
                   [["player-main", "fill9"],
                    ["player-shadow", "clear"]],
                   "inv bit3 nezbelil presne player chain bez stinu: %s"
                   % bubble["whiteRecords"])
            expect(bubble["playerVisual"] == {
                     "body0": True, "gun": False, "bodyKey": 0x7FDF},
                   "HELI nema body#0 bez viditelneho jeep/boat gun childa: %s"
                   % bubble["playerVisual"])
            expect(bubble["overBudget"] == {
                     "timer": 500, "frame": 9, "z": 2, "visible": True,
                     "activeCost": 165, "released": 160} and
                   bubble["coreBudget"] == {"activeCost": 165, "count": 1},
                   "bubble/core chybne respektuje 160 guard nebo neuvolni cost5: %s / %s"
                   % (bubble["overBudget"], bubble["coreBudget"]))
            expect(bubble["equalZ"]["airAt"] < bubble["equalZ"]["playerAt"],
                   "equal-z BOB poradi nepouziva scheduler creation order: %s"
                   % bubble["equalZ"])
            expect(bubble["pulse"] == {
                     "smart": 50, "normal": False, "boss": True,
                     "air": False, "hazard": False, "token": False,
                     "bubble": True, "player": True, "shots": 0,
                     "activeCost": 110, "score": 0, "booms": 4} and
                   bubble["pulseQueued"] == {
                     "booms": 0, "queued": 4, "bigexpl": 0, "rng": None} and
                   bubble["pulse49"] == 1 and bubble["pulse50"] == 0,
                   "white smart-pulse nema 50t default kill/imunity kontrakt: %s"
                   % bubble["pulse"])

            # HELI 0x9410 + resident collision sweep: tyto fixture zamerne
            # pokryvaji i dve chyby v Claude P0 vetvi (body anim a MIN clamp).
            player_exact = page.evaluate("""() => {
              const live = state.g;
              function makeGame(playerPatch = {}) {
                const p = Object.assign({
                  x: 100, y: 100, ang: 17, alive: true, inv: 0,
                  bubbleTimer: 0, bubbleBound: null, bubbleFrame: 9,
                  bubbleZ: 0, bubblePhase: 0, bank: 0, cool: 0,
                  weapon: 2, tokenCount: 0, mode: 0, reload: 11,
                  respawnT: 0, heliAnimPos: 0, heliAnimFresh: true,
                  weaponX: 100, weaponY: 100, bobOrdinal: 0
                }, playerPatch);
                return {
                  mapH: live.mapH, mapIndex: live.mapIndex,
                  tick: 0, scroll: 1000, scrollMul: 0,
                  over: false, won: false, keys: {}, player: p,
                  nextBobOrdinal: 1, bullets: [], shots: [], plops: [],
                  spawns: [], booms: [], effects: [], tokens: [], air: [],
                  hazards: [], activeCost: 0, score: 0,
                  nextLife: 10000, lives: 4, players: 1,
                  continues: 2, playerPhase: 'active', playerPhaseT: 0,
                  joinClosed: false, jeepLives: 1, jeepScore: 0,
                  jeepTokenCount: 0, townColor07Enabled: true,
                  rotoDirectionWord: 0, fadeBlack: 0, fadeWhite: 0,
                  fadeDir: 0, fadeWhiteStep: 0, smartPulse: 0,
                  smartPulseEpoch: 0, flash: 0
                };
              }
              const keyFor = nib => ({
                u: !!(nib & 1), d: !!(nib & 2),
                l: !!(nib & 4), r: !!(nib & 8), f: false
              });

              const joystick = [];
              for (let nib = 0; nib < 16; nib++) {
                const g = makeGame(); g.keys = keyFor(nib);
                step(g);
                joystick.push([
                  Math.round((g.player.x - 100) * 256),
                  Math.round((g.player.y - 100) * 256), g.player.ang
                ]);
              }
              // Native 0x954c clampuje PRED pohybem. Kardinalni krok muze
              // na prave publikovanem BOBu dosahnout 1/319 a 1/255.
              const lowX = makeGame({ x: 4, y: 100 });
              lowX.keys = { l: true }; step(lowX);
              const lowY = makeGame({ x: 100, y: 4 });
              lowY.keys = { u: true }; step(lowY);
              const highX = makeGame({ x: 316, y: 100 });
              highX.keys = { r: true }; step(highX);
              const highY = makeGame({ x: 100, y: 252 });
              highY.keys = { d: true }; step(highY);

              const animGame = makeGame();
              const anim = [];
              for (let i = 0; i < 8; i++) {
                step(animGame);
                const rec = composeTownBobs(
                  animGame, Math.floor(animGame.scroll)).ordered
                  .find(r => r.id === 'player-main');
                anim.push([0, 1, 2, 3, 4].find(fi =>
                  rec.spr === indexedFrameFor(state, 'JEEPHELI.LIN', fi)));
              }

              const weaponTable = [[6, 0], [1, 0], [6, 19]].map(([w, n]) => {
                const p = { weapon: w, tokenCount: n, reload: 99 };
                applyWeaponTable(p); return [p.weapon, p.reload];
              });
              const g2 = makeGame({ x: 160, y: 192, weaponX: 160,
                                    weaponY: 192, weapon: 2 });
              g2.keys.f = true; step(g2);
              const power2 = g2.bullets.map(b =>
                [b.x, +b.y.toFixed(6), b.vx, b.vy, b.frame]);
              const g6 = makeGame({ x: 160, y: 192, weaponX: 160,
                                    weaponY: 192, weapon: 6, reload: 8 });
              g6.keys.f = true; step(g6);
              const power6 = g6.bullets.map(b =>
                [b.x, +b.y.toFixed(6), b.vx, b.vy, b.frame]);
              const lag = makeGame({ x: 160, y: 192, weaponX: 150,
                                     weaponY: 180, weapon: 2 });
              lag.keys = { r: true, f: true }; step(lag);
              const latchedOrigin = lag.bullets.map(b =>
                [b.x, +b.y.toFixed(6)]);
              // Plny .25px scroll odhali poradi 0x939c -> 0xfffe updater:
              // cerstvy bolt dostane camera delta i vlastni -9 v tomtez VBL.
              const boundary = makeGame({ x: 160, y: 192, weaponX: 160,
                                          weaponY: 192, weapon: 2 });
              boundary.scrollMul = 1; boundary.keys.f = true; step(boundary);
              const freshBolt = boundary.bullets.map(b => {
                const r = hwSpriteCandidate(boundary, b, 'player-bolt',
                                             'BULLET.LIN', 14);
                return [b.x, +b.y.toFixed(2), r.anchorY];
              });

              const gr = makeGame({ x: 40, y: 40, ang: 64, weapon: 6,
                                    tokenCount: 0, reload: 8 });
              killPlayer(gr);
              gr.shots = [{ kind: 'can', x: 50, y: 50, ang: 0, spd: 0,
                            st: 0, accel: false, phase: 0 }];
              // 0x9306 (D) -> +54 smazano D+1 -> rodic ceka od D+2 100 VBL
              for (let i = 0; i < 101; i++) step(gr);
              const wait99 = [gr.player.alive, gr.player.respawnT, gr.lives];
              step(gr);
              const respawn = [gr.player.alive, gr.player.respawnT,
                gr.lives, gr.player.x, gr.player.y, gr.player.inv,
                gr.player.weapon, gr.player.reload, gr.shots.length];

              const heli0WaitGame = makeGame();
              heli0WaitGame.lives = 2;
              killPlayer(heli0WaitGame);
              for (let i = 0; i < 101; i++) step(heli0WaitGame);
              const heli0Wait99 = [heli0WaitGame.player.alive,
                heli0WaitGame.player.respawnT, heli0WaitGame.lives,
                heli0WaitGame.playerPhase];
              step(heli0WaitGame);
              const heli0After100 = [heli0WaitGame.player.alive,
                heli0WaitGame.player.respawnT, heli0WaitGame.lives,
                heli0WaitGame.playerPhase, hudStatusText(heli0WaitGame)];

              // Interni zasoba 2 -> respawn spotrebuje jednu a posledni
              // aktivni stroj musi byt HELI 0. Teprve dalsi pokus je game over.
              const lastLife = makeGame({ alive: false });
              lastLife.lives = 2;
              respawnPlayer(lastLife);
              const activeHeli0 = [lastLife.player.alive, lastLife.lives,
                lastLife.over, hudStatusText(lastLife)];
              lastLife.player.alive = false;
              lastLife.player.weapon = 6; lastLife.player.tokenCount = 5;
              lastLife.keys.f = true;             // drzeno uz pri vstupu
              respawnPlayer(lastLife);
              const exhaustedLives = [lastLife.player.alive, lastLife.lives,
                lastLife.over, lastLife.playerPhase, lastLife.playerPhaseT,
                lastLife.continues, hudStatusText(lastLife)];
              const continuePrompts = [0, 128].map(tick => {
                lastLife.tick = tick;
                const texts = hudTextsForGame(lastLife);
                return [texts.left, texts.right];
              });
              lastLife.tick = 0; lastLife.score = 123;
              step(lastLife);
              const continuedCredit = [lastLife.player.alive,
                lastLife.lives, lastLife.continues, lastLife.playerPhase,
                lastLife.score, lastLife.player.weapon,
                lastLife.player.tokenCount, lastLife.player.reload,
                hudStatusText(lastLife)];

              const creditWait = makeGame({ alive: false });
              creditWait.scrollMul = 1;      // scroll bezi i behem continue
              creditWait.lives = 1; creditWait.continues = 2;
              creditWait.effects = [{ t: 0, life: 1000 }];
              respawnPlayer(creditWait);
              for (let i = 0; i < 299; i++) step(creditWait);
              const creditWait299 = [creditWait.tick, creditWait.playerPhase,
                creditWait.playerPhaseT, creditWait.over,
                creditWait.scroll < 1000, creditWait.effects[0].t];
              step(creditWait);
              const creditWait300 = [creditWait.tick, creditWait.playerPhase,
                creditWait.fadeBlack, creditWait.over,
                creditWait.effects[0].t];

              const noCredit = makeGame({ alive: false });
              noCredit.scrollMul = 1;        // scroll bezi i behem continue
              noCredit.lives = 1; noCredit.continues = 0;
              noCredit.effects = [{ t: 0, life: 1000 }];
              respawnPlayer(noCredit);
              const noCreditStart = [noCredit.playerPhase,
                noCredit.playerPhaseT, hudTextsForGame(noCredit).left];
              for (let i = 0; i < 99; i++) step(noCredit);
              const noCredit99 = [noCredit.tick, noCredit.playerPhase,
                noCredit.playerPhaseT, noCredit.over,
                noCredit.scroll < 1000, noCredit.effects[0].t];
              step(noCredit);
              const closingStart = [noCredit.tick, noCredit.playerPhase,
                noCredit.playerPhaseT, noCredit.fadeBlack,
                noCredit.fadeDir, noCredit.joinClosed,
                noCredit.townColor07Enabled, noCredit.continues,
                noCredit.over, noCredit.effects[0].t];
              const closingPromptLow = Object.values(
                hudTextsForGame(noCredit));
              noCredit.tick = 128;
              const closingPromptHigh = Object.values(
                hudTextsForGame(noCredit));
              noCredit.tick = 100;
              for (let i = 0; i < 15; i++) step(noCredit);
              const closing15 = [noCredit.tick, noCredit.playerPhase,
                noCredit.fadeBlack, noCredit.over, noCredit.effects[0].t];
              step(noCredit);
              const statsStart = [noCredit.tick, noCredit.playerPhase,
                noCredit.fadeBlack, noCredit.over, noCredit.effects[0].t];

              // Dva bolty stejne kategorie: oba se spotrebuji, callback jen 1x.
              const co = makeGame({ alive: false });
              const ca = { kind: 'bird', x: 140, y: co.scroll + 120,
                vx: 0, vy: 0, alive: true, pending: false, dead: false,
                cost: 10, budgeted: true, hp: 3, scoreValue: 55,
                seq: [0], per: 4, apos: 0, at: 0, animFresh: false };
              co.air = [ca]; co.activeCost = 10;
              co.bullets = [{ x: 140, y: 129 }, { x: 141, y: 129 }];
              step(co);
              const coalescedQueued = [ca.hp, !!ca.hitFlash,
                co.bullets.length, ca.collisionEventWord | 0];
              step(co);
              const coalesced = [ca.hp, ca.hitFlash, co.bullets.length,
                co.shots.length, co.shots[0].phase, co.shots[0].st];

              function groundContact() {
                const g = makeGame();
                const s = { born: true, armed: true, alive: true, beh: 'mine',
                  file: 'MINE.LIN', idx: 0, fr: 0, x: g.player.x,
                  y: g.scroll + g.player.y, at: 0, hp: 10,
                  scoreValue: 25, cost: 7, budgeted: true };
                g.spawns = [s]; g.activeCost = 7; step(g);
                return [g.player.alive, s.alive, g.score];
              }
              function airContact(inv) {
                const g = makeGame({ inv });
                const a = { kind: 'bird', x: g.player.x,
                  y: g.scroll + g.player.y, vx: 0, vy: 0,
                  alive: true, pending: false, dead: false,
                  cost: 10, budgeted: true, hp: 1, scoreValue: 55,
                  seq: [0], per: 4, apos: 0, at: 0, animFresh: false };
                g.air = [a]; g.activeCost = 10; step(g); step(g);
                return [g.player.alive, a.alive, g.score, g.activeCost];
              }
              function shotContact(kind) {
                const g = makeGame();
                g.shots = [{ kind, x: g.player.x, y: g.player.y,
                  ang: 0, spd: 0, st: 0, accel: false, phase: 0,
                  lead: 0, corr: 0, ct: 0, cost: kind === 'hom' ? 5 : 0,
                  budgeted: kind === 'hom' }];
                g.activeCost = kind === 'hom' ? 5 : 0; step(g); step(g);
                return [g.player.alive, g.shots.length, g.score,
                        g.activeCost, g.booms.length];
              }
              const fragGame = makeGame({ inv: 2 });
              const frag = { kind: 'proxfrag', file: 'PROXMINE.LIN',
                x: fragGame.player.x, y: fragGame.scroll + fragGame.player.y,
                vx: 0, vy: 0, alive: true, dead: false, cost: 5,
                budgeted: true, hp: 1, scoreValue: 5,
                seq: [6], per: 2, apos: 0, at: 0 };
              fragGame.hazards = [frag]; fragGame.activeCost = 5;
              step(fragGame); step(fragGame);
              const fragContact = [fragGame.player.alive, frag.alive,
                fragGame.score, fragGame.activeCost, fragGame.booms.length];

              const lead = makeGame({ x: 100, y: 0, alive: false });
              fireHoming(lead, 100, 100, 0);
              const homSpawn = [lead.shots[0].ang, lead.shots[0].lead,
                                lead.shots[0].corr, lead.shots[0].x];
              for (let i = 0; i < 19; i++) step(lead);
              const hom20 = [lead.shots[0].ang, lead.shots[0].lead,
                             lead.shots[0].corr, lead.shots[0].x];
              step(lead);
              const hom21 = [lead.shots[0].ang, lead.shots[0].lead,
                             lead.shots[0].corr, lead.shots[0].ct];

              const cullCan = makeGame({ alive: false });
              const cullCanRef = { kind: 'can', x: 3, y: 100, ang: 128,
                spd: 3, st: 0, accel: false, phase: 0 };
              cullCan.shots = [cullCanRef];
              step(cullCan);
              const cullCanField = [cullCan.shots.length,
                cullCanRef.x, cullCanRef.phase, cullCanRef.st,
                !!cullCanRef.retireAfterField, !!cullCanRef.dead,
                townHwCandidates(cullCan).find(r => r.kind === 'cannon').frame];
              step(cullCan);
              const cullCanClean = [cullCan.shots.length, cullCanRef.x,
                cullCanRef.phase, cullCanRef.st];
              const cullHom = makeGame({ alive: false });
              const cullHomRef = { kind: 'hom', x: 3, y: 100, ang: 128,
                spd: 3, lead: 20, corr: 12, ct: 0,
                cost: 5, budgeted: true };
              cullHom.shots = [cullHomRef];
              cullHom.activeCost = 5; step(cullHom);
              const cullHomField = [cullHom.shots.length,
                cullHomRef.x, cullHomRef.lead,
                !!cullHomRef.retireAfterField, cullHom.activeCost,
                dir16(cullHomRef.ang)];
              step(cullHom);
              const cullHomClean = [cullHom.shots.length, cullHomRef.x,
                cullHomRef.lead, cullHom.activeCost, cullHomRef.budgeted];

              // Child tasky mohou vzniknout az po centralnim projectile loopu;
              // jejich prvni same-VBL 0x62d2 presto musi cull vyhodnotit.
              const freshCullCan = makeGame({ alive: false });
              fireCannon(freshCullCan, -20, 100, 128, false, false);
              const freshCullHom = makeGame({ alive: false });
              fireHoming(freshCullHom, 0, 100, 128);
              const freshCull = [!!freshCullCan.shots[0].retireAfterField,
                !!freshCullHom.shots[0].retireAfterField];

              // Jeden negative-class bolt musi zapsat event vsem prekrytym
              // positive-class targetum, ne zmizet po prvnim poli.
              const multi = makeGame({ alive: false });
              multi.air = [0, 1].map(() => ({ kind: 'bird', x: 140,
                y: multi.scroll + 120, vx: 0, vy: 0, alive: true,
                pending: false, dead: false, cost: 10, budgeted: true,
                hp: 1, scoreValue: 12, seq: [0], per: 4,
                apos: 0, at: 0, animFresh: false }));
              multi.activeCost = 20; multi.bullets = [{ x: 140, y: 129 }];
              step(multi);
              const multiQueued = [multi.air.filter(a => a.alive).length,
                multi.score, multi.bullets.length, multi.activeCost,
                multi.air.map(a => a.collisionEventWord | 0)];
              step(multi);
              const multiTarget = [multi.air.filter(a => a.alive).length, multi.score,
                                   multi.bullets.length, multi.activeCost];

              const activeToken = makeGame({ alive: false });
              activeToken.tokens = [{ x: 140, y: activeToken.scroll + 120,
                vx: 0, vy: 0, typ: 0, cycles: 12, blink: false,
                hitCooldown: -1, phase: 'active', interactive: true,
                activeHalf: 0, dead: false, cost: 5, budgeted: true }];
              activeToken.activeCost = 5;
              activeToken.bullets = [{ x: 140, y: 129 }, { x: 141, y: 129 }];
              step(activeToken);
              const tokenQueued = [activeToken.tokens[0].typ,
                activeToken.bullets.length,
                activeToken.tokens[0].collisionEventWord | 0];
              step(activeToken);
              const tokenBlock = [activeToken.tokens[0].typ,
                                  activeToken.bullets.length];
              const burstToken = makeGame({ alive: false });
              burstToken.tokens = [{ x: 140, y: burstToken.scroll + 120,
                vx: 0, vy: 0, typ: 3, cycles: 12, blink: false,
                hitCooldown: 0, burst: 10, phase: 'burst', interactive: false,
                dead: false, cost: 5, budgeted: true }];
              burstToken.activeCost = 5;
              burstToken.bullets = [{ x: 140, y: 129 }]; step(burstToken);
              const burstQueued = [burstToken.tokens[0].typ,
                burstToken.bullets.length,
                burstToken.tokens[0].collisionEventWord | 0];
              step(burstToken);
              const burstBlock = [burstToken.tokens[0].typ,
                                  burstToken.bullets.length];

              const emitterGame = makeGame({ alive: false });
              const emitterParent = { alive: true, x: 128,
                                      y: emitterGame.scroll + 120 };
              const emitter = { kind: 'flameEmitter', file: 'FLAME.LIN',
                parent: emitterParent, x: 140, y: emitterParent.y,
                alive: true, dead: false, cost: 1, budgeted: true,
                hp: 0, scoreValue: 0, seq: [12], per: 2,
                apos: 0, at: 0, t: 100 };
              emitterGame.hazards = [emitter]; emitterGame.activeCost = 1;
              emitterGame.bullets = [{ x: 140, y: 129 }];
              step(emitterGame); step(emitterGame);
              const emitterBlock = [emitter.alive, emitterGame.bullets.length];
              const puffGame = makeGame({ alive: false });
              const puff = { kind: 'flamePuff', file: 'FLAME.LIN', x: 140,
                y: puffGame.scroll + 120, vx: 0, vy: 0, alive: true,
                dead: false, cost: 10, budgeted: true, hp: 0,
                scoreValue: 0, seq: [5], per: 5, apos: 0, at: 0, life: 35 };
              puffGame.hazards = [puff]; puffGame.activeCost = 10;
              puffGame.bullets = [{ x: 140, y: 129 }]; step(puffGame);
              const puffPass = [puff.alive, puffGame.bullets.length];

              function simultaneousHoming(inv) {
                const g = makeGame({ inv });
                g.shots = [{ kind: 'hom', x: g.player.x, y: g.player.y,
                  ang: 0, spd: 0, lead: 0, corr: 0, ct: 0,
                  cost: 5, budgeted: true }];
                g.activeCost = 5;
                g.bullets = [{ x: g.player.x, y: g.player.y + 9 }];
                step(g); step(g);
                return [g.player.alive, g.shots.length, g.bullets.length,
                        g.score, g.activeCost, g.booms.length];
              }

              const coreGame = makeGame({ alive: false });
              const core2 = { kind: 'minecore', file: 'MINE.LIN', x: 140,
                y: coreGame.scroll + 120, vx: 0, vy: 0, scrollLocked: true,
                alive: true, dead: false, cost: 5, budgeted: true,
                hp: 2, scoreValue: 30, seq: [9,10], per: 1,
                apos: 0, at: 0, consumed: 0, hitFlash: false };
              coreGame.hazards = [core2]; coreGame.activeCost = 5;
              coreGame.bullets = [{ x: 140, y: 129 }, { x: 141, y: 129 }];
              step(coreGame);
              const coreHitQueued = [core2.hp, coreGame.bullets.length,
                                     core2.collisionEventWord | 0];
              step(coreGame);
              const coreHit = [core2.alive, core2.hp, core2.hitFlash,
                coreGame.score, coreGame.bullets.length, coreGame.booms.length];
              coreGame.bullets = [{ x: core2.x,
                y: core2.y - coreGame.scroll + 9 }];
              step(coreGame); step(coreGame);
              const coreDeath = [core2.alive, coreGame.score,
                coreGame.activeCost, coreGame.fadeWhite, coreGame.booms.length];
              const consumedGame = makeGame({ alive: false });
              const staleCore = { kind: 'minecore', file: 'MINE.LIN', x: 140,
                y: consumedGame.scroll + 120, vx: 0, vy: 0,
                scrollLocked: true, alive: true, dead: false,
                cost: 5, budgeted: true, hp: 10, scoreValue: 30,
                seq: [9,10], per: 1, apos: 0, at: 0, consumed: 10 };
              consumedGame.hazards = [staleCore]; consumedGame.activeCost = 5;
              consumedGame.bullets = [{ x: 140, y: 129 }];
              step(consumedGame); step(consumedGame);
              const consumedBlock = [staleCore.consumed,
                consumedGame.bullets.length, consumedGame.activeCost];

              const overCap = makeGame({ alive: false }); overCap.activeCost = 160;
              fireHoming(overCap, 100, 100, 0);
              const cost166 = overCap.activeCost;
              step(overCap); step(overCap); const cost165 = overCap.activeCost;
              overCap.shots[0].x = 3; overCap.shots[0].ang = 128;
              overCap.shots[0].spd = 3; step(overCap);
              const costLastField = overCap.activeCost;
              step(overCap);
              const homingBudget = [cost166, cost165, costLastField,
                                    overCap.activeCost];

              const smartHit = makeGame({ alive: false });
              smartHit.air = [{ kind: 'bird', x: 140,
                y: smartHit.scroll + 120, vx: 0, vy: 0, alive: true,
                pending: false, dead: false, cost: 10, budgeted: true,
                hp: 1, scoreValue: 12, seq: [0], per: 4,
                apos: 0, at: 0, animFresh: false }];
              smartHit.activeCost = 10;
              smartHit.bullets = [{ x: 140, y: 129 }]; step(smartHit);
              const smartQueued = [smartHit.air[0].alive, smartHit.score,
                smartHit.bullets.length,
                smartHit.air[0].collisionEventWord | 0,
                !!smartHit.air[0].collisionPlayerCredit];
              smartHit.smartPulse = 1; step(smartHit);
              const smartAttributed = [smartHit.air.filter(a => a.alive).length,
                smartHit.score,
                smartHit.activeCost, smartHit.booms.length, smartHit.smartPulse];

              // Smart +534 bezi pri resume pred MEDTANK coroutine: existujici
              // prefire turret uz nesmi stihnout zalozit ani ozvucit cannon.
              const smartTank = makeGame({ alive: false });
              smartTank.smartPulse = 2;
              const tank = { born: true, alive: true, beh: 'tank',
                x: 84, y: smartTank.scroll + 100, hp: 3, scoreValue: 50,
                cost: 10, budgeted: true, tankSetup: true, tankType: 0,
                st: 0, tang: 0, turretPhase: 'prefire', turretWait: 1,
                turretTask: { alive: true, cost: 4, budgeted: true,
                              bobOrdinal: 2 }, bobOrdinal: 1 };
              smartTank.spawns = [tank]; smartTank.activeCost = 14;
              step(smartTank);
              const smartPrefire = [tank.alive, smartTank.shots.length,
                smartTank.sfx.events.filter(e => e.kind === 'cannon').length,
                smartTank.activeCost];

              // Bez SMARTu stejny prefire tank granat skutecne zalozi.
              // Kontakt s chranenou HELI jej smi odstranit az na resume
              // granatoveho tasku v N+1, takze field N musi byt viditelny.
              const cannonField = makeGame({ inv: 100 });
              cannonField.nextBobOrdinal = 3;
              const contactTank = { born: true, alive: true, beh: 'tank',
                x: 84, y: cannonField.scroll + 100, hp: 3, scoreValue: 50,
                cost: 10, budgeted: true, tankSetup: true, tankType: 0,
                st: 0, tang: 0, turretPhase: 'prefire', turretWait: 1,
                turretTask: { alive: true, cost: 4, budgeted: true,
                              bobOrdinal: 2 }, bobOrdinal: 1 };
              cannonField.spawns = [contactTank]; cannonField.activeCost = 14;
              step(cannonField);                // N: fire + visible collision
              const fieldShot = cannonField.shots[0];
              const fieldCandidate = townHwCandidates(cannonField)
                .find(r => r.kind === 'cannon');
              const fieldSound = cannonField.sfx.events
                .find(e => e.kind === 'cannon');
              const cannonQueued = {
                player: [cannonField.player.alive, cannonField.player.inv],
                tank: contactTank.alive, shots: cannonField.shots.length,
                shot: fieldShot ? [
                  +fieldShot.x.toFixed(3), +fieldShot.y.toFixed(3),
                  fieldShot.phase, fieldShot.st, !!fieldShot.dead,
                  fieldShot.collisionEventWord | 0,
                  !!fieldShot.collisionPlayerCredit] : null,
                hw: fieldCandidate ? [fieldCandidate.frame,
                  fieldCandidate.anchorX, fieldCandidate.anchorY] : null,
                sfx: fieldSound ? [fieldSound.kind, fieldSound.accepted,
                                   fieldSound.tick] : null,
                cost: cannonField.activeCost
              };
              step(cannonField);                // N+1: +514 odstrani granat
              const cannonResumed = {
                player: [cannonField.player.alive, cannonField.player.inv],
                shots: cannonField.shots.length,
                hw: townHwCandidates(cannonField)
                  .filter(r => r.kind === 'cannon').length,
                sfx: cannonField.sfx.events
                  .filter(e => e.kind === 'cannon').length,
                cost: cannonField.activeCost, booms: cannonField.booms.length
              };

              // TOKEN pickup je stejny residentni event bit3: ve fieldu N
              // zustava ikona, cost i HUD beze zmeny; az N+1 spusti notu.
              const pickupGame = makeGame({ inv: 100 });
              pickupGame.tokens = [{ x: 100, y: pickupGame.scroll + 100,
                vx: 0, vy: 0, typ: 0, cycles: 12, blink: false,
                hitCooldown: -1, phase: 'active', interactive: true,
                activeHalf: 0, dead: false, cost: 5, budgeted: true,
                bobOrdinal: 1 }];
              pickupGame.activeCost = 5;
              step(pickupGame);                 // N: pouze pending bit3
              const pickupRef = pickupGame.tokens[0];
              const pickupQueued = {
                tokens: pickupGame.tokens.length, dead: pickupRef.dead,
                pending: pickupRef.collisionEventWord | 0,
                picked: pickupGame.tokensPickedUp || 0,
                count: pickupGame.player.tokenCount,
                weapon: pickupGame.player.weapon,
                cost: pickupGame.activeCost,
                sounds: pickupGame.sfx.events.filter(e =>
                  e.kind === 'token-pickup').length,
                bob: composeTownBobs(pickupGame,
                  Math.floor(pickupGame.scroll)).ordered
                  .some(r => r.id === 'token-main')
              };
              pickupGame.player.x = 200;        // geometrie se v N+1 necte
              step(pickupGame);
              const pickupSound = pickupGame.sfx.events
                .find(e => e.kind === 'token-pickup');
              const pickupResumed = {
                tokens: pickupGame.tokens.length, dead: pickupRef.dead,
                pending: pickupRef.collisionEventWord | 0,
                picked: pickupGame.tokensPickedUp,
                count: pickupGame.player.tokenCount,
                weapon: pickupGame.player.weapon,
                cost: pickupGame.activeCost,
                sound: pickupSound ? [pickupSound.kind, pickupSound.accepted,
                                      pickupSound.tick, pickupSound.period] : null,
                task: pickupGame.tokenSfxTasks.length
                  ? [pickupGame.tokenSfxTasks[0].next,
                     pickupGame.tokenSfxTasks[0].wait,
                     pickupGame.tokenSfxTasks[0].x] : null,
                bob: composeTownBobs(pickupGame,
                  Math.floor(pickupGame.scroll)).ordered
                  .some(r => r.id === 'token-main')
              };
              const retrigger = makeGame(); retrigger.smartPulse = 20;
              retrigger.fadeWhite = 100; startWhiteFlash(retrigger);
              runFreshTownPriorityTasks(retrigger);
              const smartRetrigger = [retrigger.smartPulse, retrigger.fadeWhite];

              // Kazdy 0x885a ma vlastni wait50. Stary B task proto musi
              // vypnout pulse C, i kdyz A uz globalni flag drive shodil.
              const overlapPulse = makeGame({ alive: false });
              startWhiteFlash(overlapPulse);             // A @ 0
              runFreshTownPriorityTasks(overlapPulse);
              for (let i = 0; i < 20; i++) step(overlapPulse);
              startWhiteFlash(overlapPulse);             // B @ 20
              runFreshTownPriorityTasks(overlapPulse);
              for (let i = 0; i < 30; i++) step(overlapPulse);
              const afterA = [overlapPulse.smartPulse,
                              overlapPulse.smartPulseTasks.slice()];
              for (let i = 0; i < 5; i++) step(overlapPulse);
              startWhiteFlash(overlapPulse);             // C @ 55
              runFreshTownPriorityTasks(overlapPulse);
              const afterC = [overlapPulse.smartPulse,
                              overlapPulse.smartPulseTasks.slice()];
              for (let i = 0; i < 14; i++) step(overlapPulse);
              const beforeB = overlapPulse.smartPulse;
              step(overlapPulse);                        // B deadline @ 70
              const smartOverlap = { afterA, afterC, beforeB,
                afterB: overlapPulse.smartPulse,
                pending: overlapPulse.smartPulseTasks.slice() };

              // POPUP 0xa6ae: RNG urcuje a2c6 threshold, ne uvodni wait.
              // TOWN typ=1 se pred prvni ranou invertuje a dava x-6.
              const popupGateGame = makeGame({ alive: false });
              popupGateGame.player.rank = 2048; // stabilni native difficulty1
              popupGateGame.player.weapon = 0; popupGateGame.difficulty = 1;
              popupGateGame.activeCost = 150;
              const popupGateObject = { born: false, armed: true, alive: true,
                beh: 'popup', file: 'POPUP.LIN', idx: 0, x: 100,
                y: popupGateGame.scroll + 63, typ: 1, st: 0, t: 0,
                hp: 2, fr: -1, at: 0 };
              popupGateGame.spawns = [popupGateObject];
              const savedRandom32 = window.random32;
              window.random32 = () => 63;
              step(popupGateGame);
              const at63 = [popupGateObject.born,
                            popupGateObject.activationMargin];
              popupGateObject.y = popupGateGame.scroll + 126;
              step(popupGateGame);
              const at126 = popupGateObject.born;
              popupGateObject.y = popupGateGame.scroll + 127;
              step(popupGateGame);
              const popupActivated = {
                born: popupGateObject.born, state: popupGateObject.st,
                wait: popupGateObject.t, hp: popupGateObject.hp,
                score: popupGateObject.scoreValue, cost: popupGateObject.cost,
                activeCost: popupGateGame.activeCost,
                opening: !!popupGateObject.popupAnim
              };
              for (let i = 0; i < 49; i++) step(popupGateGame);
              const popupBeforeShot = [popupGateObject.t,
                                       popupGateGame.shots.length];
              step(popupGateGame);
              const popupShot = popupGateGame.shots[0];
              const popupFired = [popupShot && popupShot.kind,
                popupShot && popupShot.x, popupShot && popupShot.ang,
                popupGateGame.activeCost, popupGateObject.popupShotsLeft];
              window.random32 = savedRandom32;

              // 0x9046 proti skutecne TOWN terrain plane1. Hodnoty nize
              // zahrnuji i neviditelny _STOP#3/flag0x14 na scrollu1553.
              const terrainRespawns = [3345, 827, 843, 1553, 1607]
                .map(scroll => {
                  const r = findPlayerRespawn({ scroll,
                    terrainOpen: live.terrainOpen, mapW: live.mapW });
                  return [scroll, r.x, r.y, r.probes];
                });
              const heli0 = indexedFrameFor(state, 'JEEPHELI.LIN', 0);
              const heliOpaque = Array.from(heli0.pix)
                .filter(color => color !== 0xFF).length;
              const fullyOpen = new Uint8Array(live.terrainOpen.length);
              fullyOpen.fill(1);
              const openRespawn = findPlayerRespawn({ scroll: 1000,
                terrainOpen: fullyOpen, mapW: 320 });
              const fullyBlocked = new Uint8Array(live.terrainOpen.length);
              const fallbackRespawn = findPlayerRespawn({ scroll: 1000,
                terrainOpen: fullyBlocked, mapW: 320 });
              const integratedRespawn = makeGame({ alive: false,
                respawnT: 1, x: 40, y: 40 });
              integratedRespawn.scroll = 1607;
              integratedRespawn.terrainOpen = live.terrainOpen;
              integratedRespawn.mapW = live.mapW;
              respawnPlayer(integratedRespawn);
              const respawnProbe = {
                real: terrainRespawns, heli: [heli0.w, heli0.h,
                  heli0.ox, heli0.oy, heliOpaque],
                open: [openRespawn.x, openRespawn.y, openRespawn.probes],
                blocked: [fallbackRespawn.x, fallbackRespawn.y,
                          fallbackRespawn.probes],
                integrated: [integratedRespawn.player.x,
                  integratedRespawn.player.y, integratedRespawn.lives]
              };

              const angles = [[1,0], [0,-1], [63,1], [3,2], [2,3],
                              [-119,-128]].map(([x,y]) => angTo(0,0,x,y));
              return { joystick, clamp: [lowX.player.x, lowY.player.y,
                       highX.player.x, highY.player.y], anim, weaponTable,
                       power2, power6, latchedOrigin, freshBolt,
                       wait99, respawn, heli0Wait99, heli0After100,
                       activeHeli0, exhaustedLives,
                       continuePrompts, continuedCredit,
                       creditWait299, creditWait300,
                       noCreditStart, noCredit99, closingStart,
                       closingPromptLow, closingPromptHigh,
                       closing15, statsStart,
                       coalescedQueued, coalesced, ground: groundContact(),
                       air: airContact(0), protectedAir: airContact(2),
                       homContact: shotContact('hom'),
                       cannonContact: shotContact('can'), fragContact,
                       multiQueued, multiTarget, tokenQueued, tokenBlock,
                       burstQueued, burstBlock, emitterBlock,
                       puffPass, simultaneous: simultaneousHoming(0),
                       simultaneousProtected: simultaneousHoming(2),
                       coreHitQueued, coreHit, coreDeath, consumedBlock,
                       homingBudget, smartQueued, smartAttributed,
                       smartPrefire, cannonQueued, cannonResumed,
                       pickupQueued, pickupResumed,
                       smartRetrigger, smartOverlap,
                       popupGate: { at63, at126, activated: popupActivated,
                                    beforeShot: popupBeforeShot,
                                    fired: popupFired },
                       respawnProbe,
                       homSpawn, hom20, hom21,
                       cull: [cullCanField, cullCanClean,
                         cullHomField, cullHomClean, freshCull], angles,
                       cullMargins: [
                         outsideCullMargin(-63.2, 100, -64),
                         outsideCullMargin(-62.9, 100, -64),
                         outsideCullMargin(.9, 100, 0),
                         outsideCullMargin(1.1, 100, 0)],
                       projectileEdges: [
                         projectileNodeHit(100, 92, 100, 100),
                         projectileNodeHit(100, 93, 100, 100),
                         projectileNodeHit(100, 108, 100, 100),
                         projectileNodeHit(100, 109, 100, 100)] };
            }""")
            expect(player_exact["joystick"] == [
                     [0, 0, 17], [0, -768, 192], [0, 768, 64], [0, 0, 17],
                     [-768, 0, 128], [-543, -543, 160], [-543, 543, 96],
                     [0, 768, 64], [768, 0, 0], [543, -543, 224],
                     [543, 543, 32], [768, 0, 0], [0, 0, 17],
                     [0, -768, 192], [0, 768, 64], [0, 0, 17]],
                   "JOY 0x959e/rychlost 3 nesedi: %s" %
                   player_exact["joystick"])
            expect(player_exact["clamp"] == [1, 1, 319, 255] and
                   player_exact["anim"] == [0, 1, 0, 2, 0, 3, 0, 4],
                   "HELI clamp nebo 0x945a anim nesedi: %s" % player_exact)
            expect(player_exact["weaponTable"] == [[2, 11], [1, 11], [5, 8]],
                   "0x70c8 neni MIN clamp: %s" % player_exact["weaponTable"])
            expect(player_exact["power2"] ==
                   [[158, 179, 0, -9, 14], [162, 179, 0, -9, 14]],
                   "startovni power2 salvo nema stejny-VBL pohyb: %s" %
                   player_exact["power2"])
            expect(player_exact["power6"] == [
                     [160,179,0,-9,14], [151,183,-6,-6,13],
                     [169,183,6,-6,15], [147,192,-9,0,12],
                     [173,192,9,0,8], [151,201,-6,6,11],
                   [169,201,6,6,9], [160,205,0,9,10]] and
                   player_exact["latchedOrigin"] == [[148, 167], [152, 167]],
                   "power6 nebo previous-child origin nesedi: %s" % player_exact)
            # fp@(3542) je WORD: 1000.0 -> 999.75 uz znamena delta -1,
            # cerstvy bolt tedy dostane 188 - 9 + 1 = 180 v tomtez VBL.
            expect(player_exact["freshBolt"] ==
                   [[158,180,180],[162,180,180]],
                   "fresh player bolt nema stejny-VBL camera delta/anchor: %s" %
                   player_exact["freshBolt"])
            expect(player_exact["wait99"] == [False, 1, 4] and
                   player_exact["respawn"] ==
                   [True, 0, 3, 160, 192, 199, 2, 11, 1],
                   "respawn neni presne 100 VBL / maze enemy shots: %s" %
                   player_exact)
            expect(player_exact["heli0Wait99"] ==
                     [False, 1, 2, "active"] and
                   player_exact["heli0After100"] ==
                     [True, 0, 1, "active", "HELI 0[ 2* 0000000"],
                   "posledni hratelny HELI 0 nevznikl presne po 100 VBL: %s" %
                   player_exact)
            expect(player_exact["activeHeli0"] ==
                     [True, 1, False, "HELI 0[ 2* 0000000"] and
                   player_exact["exhaustedLives"] ==
                     [False, 0, False, "continue", 300, 2,
                      "HELI 0[ 3* 0000000"] and
                   player_exact["continuePrompts"] == [
                     ["PRESS FIRE", "PRESS FIRE"],
                     ["HELI 0[ 3* 0000000", "JEEP 0[ 2* 0000000"]] and
                   player_exact["continuedCredit"] ==
                     [True, 4, 1, "active", 0, 3, 5, 10,
                      "HELI 3[ 3* 0000000"],
                   "posledni HELI 0 / continue kredit nesedi: %s" %
                   player_exact)
            expect(player_exact["creditWait299"] ==
                     [299, "continue", 1, False, True, 299] and
                   player_exact["creditWait300"] ==
                     [300, "closing", 0, False, 300],
                   "continue s kreditem nema presnych 300 bezicich VBL: %s" %
                   player_exact)
            expect(player_exact["noCreditStart"] ==
                     ["continue", 100, "NO CREDITS"] and
                   player_exact["noCredit99"] ==
                     [99, "continue", 1, False, True, 99] and
                   player_exact["closingStart"] ==
                     [100, "closing", 0, 0, -1, True, False, 3,
                      False, 100] and
                   player_exact["closingPromptLow"] ==
                     ["PLEASE WAIT", "PLEASE WAIT"] and
                   player_exact["closingPromptHigh"] ==
                     ["HELI 0[ 2* 0000000", "JEEP 0[ 2* 0000000"] and
                   player_exact["closing15"] ==
                     [115, "closing", 240, False, 115] and
                   player_exact["statsStart"] ==
                     [116, "stats", 256, True, 116],
                   "terminal death nema 100 VBL wait + 16 VBL fade: %s" %
                   player_exact)
            expect(player_exact["coalescedQueued"] == [3, False, 2, 1] and
                   player_exact["coalesced"] == [2, True, 0, 1, 0, 1],
                   "collision event bit se nekoaleskuje za VBL: %s" %
                   player_exact["coalesced"])
            expect(player_exact["multiQueued"] == [2, 0, 1, 20, [1, 1]] and
                   player_exact["multiTarget"] == [0, 24, 0, 0] and
                   player_exact["tokenQueued"] == [0, 2, 1] and
                   player_exact["tokenBlock"] == [1, 0] and
                   player_exact["burstQueued"] == [3, 1, 1] and
                   player_exact["burstBlock"] == [3, 0],
                   "sweep nezasahl vsechny targety / TOKEN node: %s" %
                   player_exact)
            expect(player_exact["emitterBlock"] == [True, 0] and
                   player_exact["puffPass"] == [True, 1],
                   "HP0 FLAME class36/4 pairing nesedi: %s" % player_exact)
            expect(player_exact["ground"] == [True, True, 0] and
                   player_exact["air"] == [False, False, 55, 0] and
                   player_exact["protectedAir"] == [True, False, 55, 0] and
                   player_exact["fragContact"] == [True, False, 0, 0, 0],
                   "air/ground/contact class pairing nesedi: %s" % player_exact)
            expect(player_exact["homContact"] == [False, 0, 7, 0, 17] and
                   player_exact["cannonContact"] == [False, 0, 0, 0, 16],
                   "HOMING/cannon +514 callback nesedi: %s" % player_exact)
            expect(player_exact["simultaneous"] == [False, 0, 0, 14, 0, 18] and
                   player_exact["simultaneousProtected"] ==
                   [True, 0, 0, 14, 0, 2],
                   "pred-callback collision snapshot nezachoval player event: %s" %
                   player_exact)
            expect(player_exact["coreHitQueued"] == [2, 2, 1] and
                   player_exact["coreHit"] == [True, 1, False, 0, 0, 0] and
                   player_exact["coreDeath"] == [False, 30, 0, 256, 1] and
                   player_exact["consumedBlock"] == [8, 0, 5],
                   "MINE core custom damage/wait node nesedi: %s" % player_exact)
            expect(player_exact["homingBudget"] == [166, 165, 165, 160] and
                   player_exact["smartQueued"] == [True, 0, 1, 1, True] and
                   player_exact["smartAttributed"] == [0, 24, 0, 2, 0] and
                   player_exact["smartPrefire"] == [False, 0, 0, 0] and
                   player_exact["cannonQueued"] == {
                     "player": [True, 99], "tank": True, "shots": 1,
                     "shot": [100.5, 100, 0, 1, False, 8, True],
                     "hw": [24, 100, 100],   # celociselny scroll: kotva = y
                     "sfx": ["cannon", True, 1], "cost": 14} and
                   player_exact["cannonResumed"] == {
                     "player": [True, 98], "shots": 0, "hw": 0,
                     "sfx": 1, "cost": 14, "booms": 0} and
                   player_exact["pickupQueued"] == {
                     "tokens": 1, "dead": False, "pending": 8,
                     "picked": 0, "count": 0, "weapon": 2,
                     "cost": 5, "sounds": 0, "bob": True} and
                   player_exact["pickupResumed"] == {
                     "tokens": 0, "dead": True, "pending": 0,
                     "picked": 1, "count": 1, "weapon": 3, "cost": 0,
                     "sound": ["token-pickup", True, 2, 159],
                     "task": [1, 5, 100], "bob": False} and
                   player_exact["smartRetrigger"] == [20, 256],
                   "HOMING cost nebo smart ordering/retrigger nesedi: %s" %
                   player_exact)
            expect(player_exact["smartOverlap"] == {
                     "afterA": [0, [20]], "afterC": [15, [15, 50]],
                     "beforeB": 1, "afterB": 0, "pending": [35]},
                   "prekryvajici se 0x885a tasky nemaji vlastni deadline: %s" %
                   player_exact["smartOverlap"])
            expect(player_exact["popupGate"] == {
                     "at63": [False, 127], "at126": False,
                     "activated": {"born": True, "state": 2, "wait": 50,
                       "hp": 3, "score": 70, "cost": 14,
                       "activeCost": 164, "opening": True},
                     "beforeShot": [1, 0],
                     "fired": ["hom", 94, 64, 170, 0]},
                   "POPUP nema random a2c6 gate / okamzite opening / x-6: %s" %
                   player_exact["popupGate"])
            expect(player_exact["respawnProbe"] == {
                     "real": [[3345,160,192,1], [827,160,184,2],
                              [843,160,168,4], [1553,160,168,4],
                              [1607,160,112,11]],
                     "heli": [17,32,-8,-12,306],
                     "open": [160,192,1], "blocked": [288,192,192],
                     "integrated": [160,112,3]},
                   "0x9046 nema presnou HELI masku/poradi/fallback: %s" %
                   player_exact["respawnProbe"])
            expect(player_exact["homSpawn"] == [0, 19, 10, 103] and
                   player_exact["hom20"] == [0, 0, 10, 160] and
                   player_exact["hom21"] == [242, 0, 9, 8] and
                   player_exact["cull"] ==
                   [[1, 0, 1, 1, True, False, 48], [0, 0, 1, 1],
                    [1, 0, 19, True, 5, 8], [0, 0, 19, 0, False],
                    [True, True]],
                   "HOMING lead20/turn nebo projectile margin0 nesedi: %s" %
                   player_exact)
            expect(player_exact["angles"] == [0, 192, 0, 24, 40, 163] and
                   player_exact["cullMargins"] == [True, False, True, False] and
                   player_exact["projectileEdges"] ==
                   [True, True, True, False],
                   "resident LUT 0x6610 nebo high-word cull nesedi: %s" %
                   player_exact)

            # Generalizovany 0x6480 last-field kontrakt: cull ve fieldu N
            # nesmi odstranit BOB/node ani cost. Pending event se na resume
            # N+1 odbavi pred cleanupem a task uz nesmi udelat dalsi pohyb.
            last_field_callbacks = page.evaluate("""() => {
              const live = state.g;
              const round3 = value => Math.round(value * 1000) / 1000;
              function makeGame(playerPatch = {}) {
                const player = Object.assign({
                  x: 100, y: 100, ang: 17, alive: false, inv: 0,
                  bubbleTimer: 0, bubbleBound: null, bubbleFrame: 9,
                  bubbleZ: 0, bubblePhase: 0, bank: 0, cool: 0,
                  weapon: 2, tokenCount: 0, mode: 0, reload: 11,
                  respawnT: 0, rank: 0, heliAnimPos: 0,
                  heliAnimFresh: true, weaponX: 100, weaponY: 100,
                  bobOrdinal: 0
                }, playerPatch);
                return {
                  mapH: live.mapH, mapW: 320, mapIndex: live.mapIndex,
                  tick: 0, scroll: 1000, scrollMul: 1,
                  over: false, won: false, keys: {}, player,
                  nextBobOrdinal: 2, bullets: [], shots: [], plops: [],
                  spawns: [], booms: [], effects: [], tokens: [], air: [],
                  hazards: [], activeCost: 0, score: 0,
                  nextLife: 10000, lives: 4, players: 1, difficulty: 0,
                  levelPhase: 0, rngState: 0, rngVhposWord: 0,
                  rotoDirectionWord: 0, fadeBlack: 0, fadeWhite: 0,
                  fadeDir: 0, fadeWhiteStep: 0, smartPulse: 0,
                  smartPulseTasks: [], tokenSfxTasks: [], flash: 0
                };
              }
              const rendered = (g, id) => composeTownBobs(
                g, Math.floor(g.scroll)).ordered.some(r => r.id === id);

              function homingShotGame(contact) {
                const g = makeGame(contact
                  ? { alive: true, x: 4, y: 100, inv: 4 }
                  : { alive: false });
                const shot = { kind: 'hom', x: 3, y: 100, ang: 128,
                  spd: 3, lead: 7, corr: 12, ct: 0,
                  cost: 5, budgeted: true, dead: false, bobOrdinal: 1 };
                g.shots = [shot]; g.activeCost = 5;
                if (!contact)
                  g.bullets = [{ x: 0, y: 109, vx: 0, vy: -9, frame: 14 }];
                step(g);                       // N: x 3 -> 0, cull + sweep
                const field = {
                  x: round3(shot.x), lead: shot.lead,
                  retire: !!shot.retireAfterField, dead: !!shot.dead,
                  event: shot.collisionEventWord | 0,
                  credited: !!shot.collisionPlayerCredit,
                  shots: g.shots.length, bullets: g.bullets.length,
                  cost: g.activeCost, score: g.score,
                  bob: rendered(g, 'homing-main'),
                  player: [g.player.alive, g.player.inv]
                };
                step(g);                       // N+1: callback, pak cleanup
                const resumed = {
                  x: round3(shot.x), lead: shot.lead,
                  dead: !!shot.dead, event: shot.collisionEventWord | 0,
                  shots: g.shots.length, bullets: g.bullets.length,
                  cost: g.activeCost, score: g.score, booms: g.booms.length,
                  bob: rendered(g, 'homing-main'),
                  player: [g.player.alive, g.player.inv]
                };
                return { field, resumed };
              }

              // Synteticky stav presne na hranici dvou fieldu umozni
              // oddelit poradi +367 compensation -> bit3 callback -> kill.
              const tg = makeGame({ alive: true, inv: 0 });
              const token = { x: 100, y: 1100, vx: 0, vy: .5,
                typ: 3, cycles: 12, blink: false, hitCooldown: -1,
                phase: 'active', interactive: true, activeHalf: 0,
                dead: false, cost: 5, budgeted: true, bobOrdinal: 1,
                retireAfterField: true, collisionEventWord: 8 };
              tg.tokens = [token]; tg.activeCost = 5;
              const tokenField = {
                tokens: tg.tokens.length, dead: token.dead,
                pending: token.collisionEventWord | 0,
                retire: !!token.retireAfterField, y: token.y,
                half: token.activeHalf, blink: token.blink,
                cost: tg.activeCost, bob: rendered(tg, 'token-main')
              };
              step(tg);
              const tokenResumed = {
                tokens: tg.tokens.length, dead: token.dead,
                pending: token.collisionEventWord | 0,
                y: round3(token.y), half: token.activeHalf,
                blink: token.blink, picked: tg.tokensPickedUp || 0,
                count: tg.player.tokenCount, inv: tg.player.inv,
                score: tg.score, cost: tg.activeCost,
                audio: tg.sfx.events.filter(e => e.kind === 'token-pickup')
                  .map(e => [e.tick, e.accepted, e.period]),
                soundTasks: tg.tokenSfxTasks.length,
                bob: rendered(tg, 'token-main')
              };
              return {
                homingHit: homingShotGame(false),
                homingContact: homingShotGame(true),
                token: { field: tokenField, resumed: tokenResumed }
              };
            }""")
            expect(last_field_callbacks["homingHit"] == {
                     "field": {"x": 0, "lead": 6, "retire": True,
                       "dead": False, "event": 1, "credited": True,
                       "shots": 1, "bullets": 1, "cost": 5, "score": 0,
                       "bob": True, "player": [False, 0]},
                     "resumed": {"x": 0, "lead": 6, "dead": True,
                       "event": 0, "shots": 0, "bullets": 0, "cost": 0,
                       "score": 7, "booms": 1, "bob": False,
                       "player": [False, 0]}},
                   "HOMING last field neudrzel N sweep/BOB/cost nebo N+1 callback: %s"
                   % last_field_callbacks["homingHit"])
            expect(last_field_callbacks["homingContact"] == {
                     "field": {"x": 0, "lead": 6, "retire": True,
                       "dead": False, "event": 8, "credited": True,
                       "shots": 1, "bullets": 0, "cost": 5, "score": 0,
                       "bob": True, "player": [True, 3]},
                     "resumed": {"x": 0, "lead": 6, "dead": True,
                       "event": 0, "shots": 0, "bullets": 0, "cost": 0,
                       "score": 7, "booms": 1, "bob": False,
                       "player": [True, 2]}},
                   "chranena HELI/HOMING bit3 se neodbavil pred cull cleanupem: %s"
                   % last_field_callbacks["homingContact"])
            expect(last_field_callbacks["token"] == {
                     "field": {"tokens": 1, "dead": False, "pending": 8,
                       "retire": True, "y": 1100, "half": 0,
                       "blink": False, "cost": 5, "bob": True},
                     "resumed": {"tokens": 0, "dead": True, "pending": 0,
                       "y": 1099, "half": 0, "blink": False,   # word delta
                       "picked": 1, "count": 1, "inv": 500, "score": 500,
                       "cost": 0, "audio": [[1, True, 159]],
                       "soundTasks": 1, "bob": False}},
                   "TOKEN bit3 efekt/audio nepredbehl cleanup nebo pokracoval v animaci: %s"
                   % last_field_callbacks["token"])

            # Reprezentativni bounds matrix pro vsechny kontejnery, ktere
            # pouzivaji 0x6480. Stav N musi zustat vykreslitelny a budgeted;
            # N+1 smi jen kompenzovat bit4 a uklidit, nikoli pokracovat.
            last_field_matrix = page.evaluate("""() => {
              const live = state.g;
              const round2 = value => Math.round(value * 100) / 100;
              const makeGame = () => ({
                mapH: live.mapH, mapW: 320, mapIndex: live.mapIndex,
                tick: 0, scroll: 1000, scrollMul: 1,
                over: false, won: false, keys: {},
                player: { x: 100, y: 100, ang: 17, alive: false, inv: 0,
                  bubbleTimer: 0, bubbleBound: null, bank: 0, cool: 0,
                  weapon: 2, tokenCount: 0, mode: 0, reload: 11,
                  respawnT: 0, rank: 0, heliAnimPos: 0,
                  heliAnimFresh: true, weaponX: 100, weaponY: 100,
                  bobOrdinal: 0 },
                nextBobOrdinal: 2, bullets: [], shots: [], plops: [],
                spawns: [], booms: [], effects: [], tokens: [], air: [],
                hazards: [], activeCost: 0, score: 0,
                nextLife: 10000, lives: 4, players: 1, difficulty: 0,
                levelPhase: 0, rngState: 0, rngVhposWord: 0,
                rotoDirectionWord: 0, fadeBlack: 0, fadeWhite: 0,
                fadeDir: 0, fadeWhiteStep: 0, smartPulse: 0,
                smartPulseTasks: [], tokenSfxTasks: [], flash: 0
              });
              const hasBob = (g, id) => composeTownBobs(
                g, Math.floor(g.scroll)).ordered.some(r => r.id === id);
              function pair(g, object, present, bobId, stateOf) {
                step(g);
                const field = { present: present(), alive: !!object.alive,
                  dead: !!object.dead,
                  retire: !!object.retireAfterField, cost: g.activeCost,
                  bob: hasBob(g, bobId), state: stateOf() };
                step(g);
                const cleanup = { present: present(), alive: !!object.alive,
                  dead: !!object.dead, cost: g.activeCost,
                  bob: hasBob(g, bobId), state: stateOf() };
                return { field, cleanup };
              }

              const ag = makeGame();
              const air = { kind: 'bird', x: -63, y: 1100, vx: -1, vy: 0,
                alive: true, pending: false, dead: false,
                cost: 10, budgeted: true, hp: 2, scoreValue: 55,
                seq: [0, 1], per: 4, apos: 0, at: 0,
                animFresh: false, bobOrdinal: 1 };
              ag.air = [air]; ag.activeCost = 10;
              const airLife = pair(ag, air, () => ag.air.includes(air),
                'air-bird-main', () => [round2(air.x), round2(air.y),
                                        air.apos, air.at]);

              const pg = makeGame();
              const prox = { kind: 'proxfrag', file: 'PROXMINE.LIN',
                x: 1, y: 1100, vx: -1, vy: 0, alive: true, dead: false,
                cost: 5, budgeted: true, hp: 1, scoreValue: 5,
                seq: [6, 7], per: 2, apos: 0, at: 0, bobOrdinal: 1 };
              pg.hazards = [prox]; pg.activeCost = 5;
              const proxLife = pair(pg, prox,
                () => pg.hazards.includes(prox), 'hazard-proxfrag-main',
                () => [round2(prox.x), round2(prox.y), prox.apos, prox.at]);

              const cg = makeGame();
              const core = { kind: 'minecore', file: 'MINE.LIN',
                x: -64, y: 1100, vx: 0, vy: 0, scrollLocked: true,
                alive: true, dead: false, cost: 5, budgeted: true,
                hp: 10, scoreValue: 30, seq: [9, 10], per: 1,
                apos: 0, at: 0, consumed: 0, bobOrdinal: 1 };
              cg.hazards = [core]; cg.activeCost = 5;
              const coreLife = pair(cg, core,
                () => cg.hazards.includes(core), 'hazard-minecore-main',
                () => [round2(core.x), round2(core.y), core.apos, core.at]);

              const fg = makeGame();
              const flame = { born: true, taskStarted: true, armed: true,
                alive: true, beh: 'flame', file: 'FLAME.LIN', idx: 0,
                x: -8, y: 1100, typ: 0, fr: 0, at: 0, anim: null,
                age: 0, emitterSpawned: false, hp: 3, scoreValue: 40,
                cost: 10, budgeted: true, bobOrdinal: 1 };
              fg.spawns = [flame]; fg.activeCost = 10;
              const flameLife = pair(fg, flame,
                () => fg.spawns.includes(flame), 'spawn-main',
                () => [round2(flame.x), round2(flame.y), flame.age, flame.fr]);

              const sg = makeGame();
              const spawn = { born: true, taskStarted: true, armed: true,
                alive: true, beh: 'mine', file: 'MINE.LIN', idx: 0,
                x: -64, y: 1100, typ: 0, fr: 0, at: 0, anim: null,
                hp: 10, scoreValue: 25, cost: 7, budgeted: true,
                bobOrdinal: 1 };
              sg.spawns = [spawn]; sg.activeCost = 7;
              const spawnLife = pair(sg, spawn,
                () => sg.spawns.includes(spawn), 'spawn-main',
                () => [round2(spawn.x), round2(spawn.y), spawn.fr, spawn.at]);

              const kg = makeGame();
              const token = { x: -64, y: 1100, vx: 0, vy: .5,
                typ: 0, cycles: 12, blink: false, hitCooldown: -1,
                phase: 'active', interactive: true, activeHalf: 0,
                dead: false, cost: 5, budgeted: true, bobOrdinal: 1 };
              kg.tokens = [token]; kg.activeCost = 5;
              const tokenLife = pair(kg, token,
                () => kg.tokens.includes(token), 'token-main',
                () => [round2(token.x), round2(token.y), token.activeHalf,
                       token.blink, token.hitCooldown]);

              // ROTO/MILL/GOOSE mohou mit dalsi coroutine praci za waitem.
              // Flag z N ji musi v N+1 preskocit, vcetne salvy a -4 pohybu.
              const rg = makeGame();
              const roto = { born: true, taskStarted: true, armed: true,
                alive: true, beh: 'roto', file: 'ROTOBASE.LIN', idx: 4,
                x: -64, y: 1100, typ: 0, fr: 4, at: 0, anim: null,
                hp: 4, scoreValue: 35, cost: 10, budgeted: true,
                sd: 1, spin: 4, salvoAngle: 0, t: 50, bobOrdinal: 1 };
              rg.spawns = [roto]; rg.activeCost = 10;
              const rotoLife = pair(rg, roto,
                () => rg.spawns.includes(roto), 'spawn-main',
                () => [roto.spin, roto.fr, roto.at, roto.t,
                       rg.shots.length]);

              const mg = makeGame();
              const mill = { born: true, taskStarted: true, armed: true,
                alive: true, beh: 'mill', file: 'MILL.LIN', idx: 0,
                x: -64, y: 1100, typ: 0, fr: 0, at: 0, anim: null,
                hp: 10, scoreValue: 70, cost: 15, budgeted: true,
                vy: 0, scrollLocked: true, st: 1, t: 1,
                rotorTick: 0, rotorFresh: false, bobOrdinal: 1 };
              mg.spawns = [mill]; mg.activeCost = 15;
              const millLife = pair(mg, mill,
                () => mg.spawns.includes(mill), 'mill-main',
                () => [round2(mill.y), mill.rotorTick, mill.t,
                       mg.shots.length]);

              const gg = makeGame();
              const goose = { born: true, taskStarted: true, armed: true,
                alive: true, beh: 'boss', file: 'GOOSE.LIN', idx: 0,
                x: 160, y: 940, typ: 0, fr: 0, at: 0, anim: null,
                hp: 25, scoreValue: 0, cost: 100, budgeted: true,
                scrollLocked: true, st: 3, vx: 0, vy: -4, timer: 0,
                bodyFrame: 0, bodyHidden: false, rotorActive: false,
                rotorTick: 0, unfoldPos: -1, unfoldWait: 0,
                hitSpread: false, parts: [], assemblyLeft: 0,
                groupReleased: false, bobOrdinal: 1 };
              gg.spawns = [goose]; gg.activeCost = 100;
              const gooseLife = pair(gg, goose,
                () => gg.spawns.includes(goose), 'boss-main-main',
                () => [round2(goose.y), goose.st, goose.groupReleased,
                       gg.shots.length]);

              // PLOP publikuje prvni BULLET#2 uz ve spawn fieldu; margin0
              // jej pouze oznaci. Burst TOKEN a horizontalni TRAIN cull
              // naopak zamerne nemaji.
              const plg = makeGame(); spawnPlop(plg, 0, 100);
              const plop = plg.plops[0];
              const plopField = { present: !!plop,
                retire: !!plop.retireAfterField, dead: !!plop.dead,
                t: plop.t, cost: plg.activeCost,
                hw: townHwCandidates(plg).some(r => r.kind === 'plop') };
              step(plg);
              const plopCleanup = { present: plg.plops.includes(plop),
                dead: !!plop.dead, t: plop.t, cost: plg.activeCost,
                hw: townHwCandidates(plg).some(r => r.kind === 'plop') };

              const bg = makeGame();
              const burst = { x: -100, y: 1100, vx: -1, vy: 0,
                typ: 3, cycles: 12, blink: false, hitCooldown: 0,
                burst: 5, phase: 'burst', interactive: false,
                activeHalf: 0, dead: false, cost: 5, budgeted: true,
                bobOrdinal: 1 };
              bg.tokens = [burst]; bg.activeCost = 5;
              step(bg); const burst1 = [round2(burst.x), round2(burst.y),
                burst.burst, !!burst.retireAfterField, burst.dead,
                bg.activeCost];
              step(bg); const burst2 = [round2(burst.x), round2(burst.y),
                burst.burst, !!burst.retireAfterField, burst.dead,
                bg.activeCost];

              const trg = makeGame();
              const train = { born: true, taskStarted: true, armed: true,
                alive: true, beh: 'train', file: 'TRAIN.LIN', idx: 0,
                x: -100, y: 1100, vx: -1, vxRaw: -65536,
                typ: 0, fr: 0, at: 0, anim: null, hp: 10,
                scoreValue: 75, cost: 15, budgeted: true, bobOrdinal: 1 };
              trg.spawns = [train]; trg.activeCost = 15;
              step(trg); const train1 = [round2(train.x), train.alive,
                !!train.retireAfterField, trg.activeCost];
              step(trg); const train2 = [round2(train.x), train.alive,
                !!train.retireAfterField, trg.activeCost];

              return { lifecycle: { air: airLife, prox: proxLife,
                core: coreLife, flame: flameLife, spawn: spawnLife,
                token: tokenLife, roto: rotoLife, mill: millLife,
                goose: gooseLife },
                plop: { field: plopField, cleanup: plopCleanup },
                negative: { burst1, burst2, train1, train2 } };
            }""")
            lifecycle_costs = {"air": 10, "prox": 5, "core": 5,
                               "flame": 10, "spawn": 7, "token": 5,
                               "roto": 10, "mill": 15, "goose": 100}
            for name, cost in lifecycle_costs.items():
                life = last_field_matrix["lifecycle"][name]
                cleanup_cost = cost if name == "goose" else 0
                expect(life["field"]["present"] is True and
                       (name == "token" or life["field"]["alive"] is True) and
                       life["field"]["dead"] is False and
                       life["field"]["retire"] is True and
                       life["field"]["cost"] == cost and
                       life["field"]["bob"] is True and
                       life["cleanup"]["alive"] is False and
                       life["cleanup"]["cost"] == cleanup_cost and
                       life["cleanup"]["bob"] is False,
                       "%s nema last-field alive/render/cost -> cleanup: %s"
                       % (name, life))
            expect(last_field_matrix["lifecycle"]["goose"]["cleanup"]
                   ["present"] is True,
                   "GOOSE parent task zmizel pred checksum tail: %s" %
                   last_field_matrix["lifecycle"]["goose"])
            expected_states = {
                # scroll word: 1000 -> 999.75 je delta -1, dalsi tik 0
                "air": [[-64, 1099, 0, 1], [-64, 1099, 0, 1]],
                "prox": [[0, 1100, 0, 1], [0, 1100, 0, 1]],
                "core": [[-64, 1099, 1, 0], [-64, 1099, 1, 0]],
                "flame": [[-8, 1100, 1, 0], [-8, 1100, 1, 0]],
                "spawn": [[-64, 1100, 0, 1], [-64, 1100, 0, 1]],
                "token": [[-64, 1099.5, 1, False, -2],
                          [-64, 1099.5, 1, False, -2]],
                "roto": [[4, 4, 1, 49, 0], [4, 4, 1, 49, 0]],
                "mill": [[1099, 1, 1, 0], [1099, 1, 1, 0]],
                "goose": [[935, 3, False, 0],
                          [935, 3, True, 0]],
            }
            for name, states in expected_states.items():
                life = last_field_matrix["lifecycle"][name]
                expect([life["field"]["state"], life["cleanup"]["state"]]
                       == states,
                       "%s pokracoval po invalidaci nebo nema bit4 poradi: %s"
                       % (name, life))
            expect(last_field_matrix["plop"] == {
                     "field": {"present": True, "retire": True,
                       "dead": False, "t": 1, "cost": 1, "hw": True},
                     "cleanup": {"present": False, "dead": True,
                       "t": 1, "cost": 0, "hw": False}},
                   "PLOP margin0 nema prvni HW field a resume cleanup: %s"
                   % last_field_matrix["plop"])
            expect(last_field_matrix["negative"] == {
                     "burst1": [-101, 1099, 4, False, False, 5],
                     "burst2": [-102, 1099, 3, False, False, 5],
                     "train1": [-101, True, False, 15],
                     "train2": [-102, True, False, 15]},
                   "TOKEN burst nebo TRAIN dostal zakazany bounds cull: %s"
                   % last_field_matrix["negative"])

            # Child zalozeny az v continuation mapoveho/hazard tasku je v
            # nativnim priority-100 FIFO stale splatny jeste v temze VBL.
            # Musi proto stihnout prvni motion/anim/0x6480 i publikaci; pri
            # cullu jej az nasledujici resume uklidi bez druheho pohybu.
            fresh_hazard_fields = page.evaluate("""() => {
              const live = state.g;
              const round6 = value => Math.round(value * 1000000) / 1000000;
              const makeGame = (player = null) => ({
                mapH: live.mapH, mapW: 320, mapIndex: live.mapIndex,
                tick: 0, scroll: 1000, scrollMul: 1,
                over: false, won: false, keys: {},
                player: player || { x: 160, y: 192, ang: 17, alive: false,
                  inv: 0, bubbleTimer: 0, bubbleBound: null, bank: 0,
                  cool: 0, weapon: 2, tokenCount: 0, mode: 0, reload: 11,
                  respawnT: 0, rank: 0, heliAnimPos: 0,
                  heliAnimFresh: true, weaponX: 160, weaponY: 192,
                  bobOrdinal: 0 },
                nextBobOrdinal: 2, bullets: [], shots: [], plops: [],
                spawns: [], booms: [], effects: [], tokens: [], air: [],
                hazards: [], activeCost: 0, score: 0,
                nextLife: 10000, lives: 4, players: 1, difficulty: 1,
                levelPhase: 0, rngState: 0, rngVhposWord: 0,
                rotoDirectionWord: 0, fadeBlack: 0, fadeWhite: 0,
                fadeDir: 0, fadeWhiteStep: 0, smartPulse: 0,
                smartPulseTasks: [], tokenSfxTasks: [], flash: 0
              });
              const bobCount = (g, id) => composeTownBobs(
                g, Math.floor(g.scroll)).ordered.filter(r => r.id === id).length;

              // PROXMINE parent detonuje az ve sve mapove continuation.
              // Strepy tedy pri vstupu do step() jeste v hazards[] nejsou.
              const pg = makeGame({ x: 100, y: 100, ang: 17, alive: true,
                inv: 1000, bubbleTimer: 0, bubbleBound: null, bank: 0,
                cool: 0, weapon: 2, tokenCount: 0, mode: 0, reload: 11,
                respawnT: 0, rank: 0, heliAnimPos: 0,
                heliAnimFresh: true, weaponX: 100, weaponY: 100,
                bobOrdinal: 0 });
              const proxParent = { born: true, taskStarted: true, armed: true,
                alive: true, beh: 'proxmine', file: 'PROXMINE.LIN', idx: 0,
                x: 0, y: 1100, typ: 0, fr: 5, at: 0, anim: null,
                hp: 4, scoreValue: 30, cost: 10, budgeted: true,
                st: 2, t: 1, bobOrdinal: 1 };
              pg.spawns = [proxParent]; pg.activeCost = 10;
              step(pg);
              const fragments = pg.hazards.filter(h => h.kind === 'proxfrag');
              const culled = fragments.filter(h => h.retireAfterField);
              const frag = culled[0];
              const proxField = {
                parentAlive: proxParent.alive, count: fragments.length,
                retired: culled.length, cost: pg.activeCost,
                bob: bobCount(pg, 'hazard-proxfrag-main'),
                selected: frag && {
                  pos: [round6(frag.x), round6(frag.y)],
                  moved: [round6(frag.x - proxParent.x),
                          round6(frag.y - proxParent.y)],
                  velocity: [round6(frag.vx), round6(frag.vy)],
                  apos: frag.apos, at: frag.at, alive: frag.alive,
                  dead: frag.dead, retire: !!frag.retireAfterField,
                  present: pg.hazards.includes(frag)
                }
              };
              const proxFrozen = frag && [round6(frag.x), round6(frag.y)];
              step(pg);
              const proxCleanup = {
                alive: frag && frag.alive, dead: frag && frag.dead,
                present: frag && pg.hazards.includes(frag),
                pos: frag && [round6(frag.x), round6(frag.y)],
                frozen: proxFrozen, cost: pg.activeCost,
                remaining: pg.hazards.filter(h => h.kind === 'proxfrag').length
              };

              // FLAME parent pripoji emitter na age=24. I tento pozdne
              // zalozeny child musi v N snizit t, tiknout anim a cullnout.
              const eg = makeGame();
              const flame = { born: true, taskStarted: true, armed: true,
                alive: true, beh: 'flame', file: 'FLAME.LIN', idx: 0,
                x: -76, y: 1100, typ: 0, fr: 3, at: 0, anim: null,
                age: 23, emitterSpawned: false, hp: 3, scoreValue: 40,
                cost: 10, budgeted: true, bobOrdinal: 1 };
              eg.spawns = [flame]; eg.activeCost = 10;
              step(eg);
              const emitter = eg.hazards.find(h => h.kind === 'flameEmitter');
              const emitterField = {
                count: eg.hazards.length, parentRetire: !!flame.retireAfterField,
                x: emitter && round6(emitter.x), y: emitter && round6(emitter.y),
                t: emitter && emitter.t, apos: emitter && emitter.apos,
                at: emitter && emitter.at, alive: emitter && emitter.alive,
                dead: emitter && emitter.dead,
                retire: emitter && !!emitter.retireAfterField,
                cost: eg.activeCost,
                bob: bobCount(eg, 'hazard-flameEmitter-main')
              };
              const emitterFrozen = emitter &&
                [round6(emitter.x), round6(emitter.y), emitter.t,
                 emitter.apos, emitter.at];
              step(eg);
              const emitterCleanup = {
                alive: emitter && emitter.alive, dead: emitter && emitter.dead,
                present: emitter && eg.hazards.includes(emitter),
                state: emitter && [round6(emitter.x), round6(emitter.y),
                  emitter.t, emitter.apos, emitter.at],
                frozen: emitterFrozen, cost: eg.activeCost,
                bob: bobCount(eg, 'hazard-flameEmitter-main')
              };

              // Puff vznika uvnitr prvniho fieldu existujiciho emitteru;
              // dynamicky pripojeny task tedy potrebuje stejny FIFO dobeh.
              const fg = makeGame();
              const flameParent = { alive: true, x: -79, y: 1100 };
              spawnFlameEmitter(fg, flameParent);
              const sourceEmitter = fg.hazards[0];
              sourceEmitter.t = 1;
              step(fg);
              const puff = fg.hazards.find(h => h.kind === 'flamePuff');
              const puffField = {
                count: fg.hazards.length,
                emitterRetire: !!sourceEmitter.retireAfterField,
                x: puff && round6(puff.x), y: puff && round6(puff.y),
                life: puff && puff.life, apos: puff && puff.apos,
                at: puff && puff.at, alive: puff && puff.alive,
                dead: puff && puff.dead, retire: puff && !!puff.retireAfterField,
                cost: fg.activeCost,
                bob: bobCount(fg, 'hazard-flamePuff-main')
              };
              const puffFrozen = puff &&
                [round6(puff.x), round6(puff.y), puff.life, puff.apos, puff.at];
              step(fg);
              const puffCleanup = {
                alive: puff && puff.alive, dead: puff && puff.dead,
                present: puff && fg.hazards.includes(puff),
                state: puff && [round6(puff.x), round6(puff.y),
                  puff.life, puff.apos, puff.at],
                frozen: puffFrozen, cost: fg.activeCost,
                bob: bobCount(fg, 'hazard-flamePuff-main')
              };

              // Wait35 konci navratem po poslednim publikovanem fieldu.
              // life=1 proto jeste provede pohyb/anim N a teprve resume
              // N+1 uvolni task; nesmi vzniknout o pole kratsi plamen.
              const xg = makeGame();
              const expiringPuff = { kind: 'flamePuff', file: 'FLAME.LIN',
                x: 100, y: 1100, vx: 2.5, vy: 0,
                alive: true, dead: false, cost: 10, budgeted: true,
                hp: 0, scoreValue: 0, seq: [5, 6, 7, 8, 9, 10, 11],
                per: 5, apos: 0, at: 0, animFresh: false, life: 1,
                bobOrdinal: 1 };
              xg.hazards = [expiringPuff]; xg.activeCost = 10;
              step(xg);
              const expiryField = {
                x: round6(expiringPuff.x), life: expiringPuff.life,
                apos: expiringPuff.apos, at: expiringPuff.at,
                alive: expiringPuff.alive, dead: expiringPuff.dead,
                retire: !!expiringPuff.retireAfterField,
                present: xg.hazards.includes(expiringPuff),
                cost: xg.activeCost,
                bob: bobCount(xg, 'hazard-flamePuff-main')
              };
              const expiryFrozen = [round6(expiringPuff.x),
                expiringPuff.life, expiringPuff.apos, expiringPuff.at];
              step(xg);
              const expiryCleanup = {
                x: round6(expiringPuff.x), life: expiringPuff.life,
                apos: expiringPuff.apos, at: expiringPuff.at,
                frozen: expiryFrozen,
                alive: expiringPuff.alive, dead: expiringPuff.dead,
                present: xg.hazards.includes(expiringPuff),
                cost: xg.activeCost,
                bob: bobCount(xg, 'hazard-flamePuff-main')
              };

              // TRAIN vagony jsou take zalozeny az aktivacni continuation;
              // horizontalni cull nemaji, ale prvni +vx field musi byt N.
              const tg = makeGame();
              const train = { born: false, taskStarted: true, armed: true,
                alive: true, beh: 'train', file: 'TRAIN.LIN', idx: 0,
                x: 0, y: 1100, typ: 2, fr: -1, at: 0, anim: null };
              tg.spawns = [train];
              step(tg);
              const trainField = {
                parentX: round6(train.x),
                cars: tg.hazards.map(h => round6(h.x)),
                cost: tg.activeCost, bob: bobCount(tg, 'hazard-traincar-main')
              };
              step(tg);
              const trainNext = {
                parentX: round6(train.x),
                cars: tg.hazards.map(h => round6(h.x)),
                cost: tg.activeCost, bob: bobCount(tg, 'hazard-traincar-main')
              };

              // Dolni TRAIN exit se testuje az pri resume z predchoziho
              // 0x62d2. Field N na sy=272 tedy zustane publikovany a cost
              // se uvolni v N+1 drive, nez by vagon provedl dalsi x += vx.
              const bg = makeGame();
              const trainParent = { alive: true, vx: 1, vxRaw: 65536 };
              const boundaryCar = { kind: 'traincar', file: 'TRAIN.LIN',
                frame: 1, x: 100, y: 1271.75, vx: 1, vxRaw: 65536,
                parent: trainParent, alive: true, dead: false,
                cost: 15, budgeted: true, hp: 2, scoreValue: 50,
                seq: [1], per: 1, apos: 0, at: 0, animFresh: false,
                bobOrdinal: 1 };
              bg.hazards = [boundaryCar]; bg.activeCost = 15;
              step(bg);
              const trainBoundaryField = {
                x: round6(boundaryCar.x),
                sy: round6(boundaryCar.y - bg.scroll),
                alive: boundaryCar.alive, dead: boundaryCar.dead,
                retire: !!boundaryCar.retireAfterField,
                present: bg.hazards.includes(boundaryCar),
                cost: bg.activeCost,
                bob: bobCount(bg, 'hazard-traincar-main')
              };
              const trainBoundaryFrozenX = round6(boundaryCar.x);
              step(bg);
              const trainBoundaryCleanup = {
                x: round6(boundaryCar.x), frozenX: trainBoundaryFrozenX,
                alive: boundaryCar.alive, dead: boundaryCar.dead,
                present: bg.hazards.includes(boundaryCar),
                cost: bg.activeCost,
                bob: bobCount(bg, 'hazard-traincar-main')
              };

              return {
                prox: { field: proxField, cleanup: proxCleanup },
                emitter: { field: emitterField, cleanup: emitterCleanup },
                puff: { field: puffField, cleanup: puffCleanup },
                puffExpiry: { field: expiryField, cleanup: expiryCleanup },
                train: { field: trainField, next: trainNext },
                trainBoundary: { field: trainBoundaryField,
                                 cleanup: trainBoundaryCleanup }
              };
            }""")
            prox_fresh = fresh_hazard_fields["prox"]
            expect(prox_fresh["field"]["parentAlive"] is False and
                   prox_fresh["field"]["count"] == 6 and
                   prox_fresh["field"]["retired"] > 0 and
                   prox_fresh["field"]["cost"] == 30 and
                   prox_fresh["field"]["bob"] == 6 and
                   prox_fresh["field"]["selected"]["moved"] ==
                   prox_fresh["field"]["selected"]["velocity"] and
                   prox_fresh["field"]["selected"]["apos"] == 0 and
                   prox_fresh["field"]["selected"]["at"] == 0 and
                   prox_fresh["field"]["selected"]["alive"] is True and
                   prox_fresh["field"]["selected"]["dead"] is False and
                   prox_fresh["field"]["selected"]["retire"] is True and
                   prox_fresh["field"]["selected"]["present"] is True,
                   "fresh PROXMINE child nema prvni same-VBL field: %s" %
                   prox_fresh)
            expect(prox_fresh["cleanup"]["alive"] is False and
                   prox_fresh["cleanup"]["dead"] is True and
                   prox_fresh["cleanup"]["present"] is False and
                   prox_fresh["cleanup"]["pos"] ==
                   prox_fresh["cleanup"]["frozen"] and
                   prox_fresh["cleanup"]["remaining"] ==
                   6 - prox_fresh["field"]["retired"] and
                   prox_fresh["cleanup"]["cost"] ==
                   5 * prox_fresh["cleanup"]["remaining"],
                   "fresh PROXMINE cull nema N+1 cleanup bez pohybu: %s" %
                   prox_fresh)

            expect(fresh_hazard_fields["emitter"] == {
                     "field": {"count": 1, "parentRetire": True,
                       "x": -64, "y": 1100, "t": 99, "apos": 0,
                       "at": 0, "alive": True, "dead": False,
                       "retire": True, "cost": 11, "bob": 1},
                     "cleanup": {"alive": False, "dead": True,
                       "present": False,
                       "state": [-64, 1100, 99, 0, 0],
                       "frozen": [-64, 1100, 99, 0, 0],
                       "cost": 0, "bob": 0}},
                   "fresh FLAME emitter nema N field -> N+1 cleanup: %s" %
                   fresh_hazard_fields["emitter"])
            expect(fresh_hazard_fields["puff"] == {
                     "field": {"count": 2, "emitterRetire": True,
                       "x": -64.5, "y": 1100, "life": 34, "apos": 0,
                       "at": 0, "alive": True, "dead": False,
                       "retire": True, "cost": 11, "bob": 1},
                     "cleanup": {"alive": False, "dead": True,
                       "present": False,
                       "state": [-64.5, 1100, 34, 0, 0],
                       "frozen": [-64.5, 1100, 34, 0, 0],
                       "cost": 0, "bob": 0}},
                   "fresh FLAME puff nema N field -> N+1 cleanup: %s" %
                   fresh_hazard_fields["puff"])
            expect(fresh_hazard_fields["puffExpiry"] == {
                     "field": {"x": 102.5, "life": 0, "apos": 0,
                       "at": 1, "alive": True, "dead": False,
                       "retire": True, "present": True,
                       "cost": 10, "bob": 1},
                     "cleanup": {"x": 102.5, "life": 0, "apos": 0,
                       "at": 1, "frozen": [102.5, 0, 0, 1],
                       "alive": False, "dead": True, "present": False,
                       "cost": 0, "bob": 0}},
                   "FLAME puff life=1 nema posledni N field/N+1 cleanup: %s"
                   % fresh_hazard_fields["puffExpiry"])
            expect(fresh_hazard_fields["train"] == {
                     "field": {"parentX": -47, "cars": [-94, -141],
                       "cost": 45, "bob": 2},
                     "next": {"parentX": -46, "cars": [-93, -140],
                       "cost": 45, "bob": 2}},
                   "fresh TRAIN vagony vynechaly aktivacni same-VBL pohyb: %s"
                   % fresh_hazard_fields["train"])
            expect(fresh_hazard_fields["trainBoundary"] == {
                     "field": {"x": 101, "sy": 272, "alive": True,
                       "dead": False, "retire": True, "present": True,
                       "cost": 15, "bob": 1},
                     "cleanup": {"x": 101, "frozenX": 101,
                       "alive": False, "dead": True, "present": False,
                       "cost": 0, "bob": 0}},
                   "TRAIN sy=272 nema posledni N field a N+1 frozen cleanup: %s"
                   % fresh_hazard_fields["trainBoundary"])

            summary = page.evaluate("""() => ({
              dispatch: state.behaviorDispatch.size,
              mapObjects: state.mapMeta.objects,
              spawns: state.g.spawns.length,
              lives: state.g.lives,
              firstSpawnHud: hudStatusText({ lives: state.g.lives,
                player: { tokenCount: 0 }, score: 0 }),
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
            expect(summary["lives"] == 4 and
                   summary["firstSpawnHud"] == "HELI 3[ 2* 0000000" and
                   summary["hudTexts"] == [
                     "HELI 3[ 2* 0000000", "HELI 11[ 3* 0000090",
                     "HELI 3[ 2* 0100000", "HELI 3[ 2* 0999990"
                   ], "HUD nema prvni spawn/lives/weapon/score x10 format: %s" %
                   summary)
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
              const savedRandom32 = window.random32;
              window.random32 = () => 0;
              try {
                const game = spawns => ({
                  tick: 0, scroll: 100, scrollMul: 0,
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
                  hp: 3, cost: 14, budgeted: true,
                  popupShotWord: 0, popupShotsLeft: 1
                };
                const gp = game([popup]);
                gp.activeCost = 14;
                // t0 je tik, kdy se opening animator pripoji. Sledujeme
                // celou 1P sekvenci az po KILL zaviraciho skriptu na t162.
                const popupTimeline = [];
                for (let i = 0; i <= 162; i++) {
                  step(gp);
                  popupTimeline.push({ frame: popup.fr, wait: popup.t,
                                       state: popup.st, alive: popup.alive });
                }

                const gplop = game([]);
                fireHoming(gplop, 80, 90, 64, 1.5, -2);
                const plopState = () => {
                  const pl = gplop.plops[0];
                  if (!pl) return null;
                  const graphic = PLOP_SEQUENCE[pl.t];
                  return { t: pl.t, file: graphic && graphic[0],
                           frame: graphic && graphic[1],
                           x: pl.x, y: pl.y };
                };
                const homingFresh = [gplop.shots[0].lead,
                  gplop.shots[0].x, gplop.shots[0].y];
                const plop = [plopState()];
                step(gplop); plop.push(plopState());
                step(gplop); plop.push(plopState());

                // Lichy globalni tick by stary renderer donutil novou strelu
                // zacit druhou fazi. Original vzdy zacina vlastni fazi 0.
                const gcannon = game([]);
                gcannon.tick = 41;
                fireCannon(gcannon, 80, 80, 0, true, false);
                const cannonFresh = (() => {
                  const s=gcannon.shots[0];
                  return [s.x,s.y,s.st,s.hwDepth,cannonFrameFor(s),s.phase];
                })();
                const cannonDiagonal = [32,160].map(angle => {
                  const gd=game([]); fireCannon(gd,80,80,angle,true,false);
                  const s=gd.shots[0];
                  return [angle,+s.x.toFixed(6),+s.y.toFixed(6),s.hwDepth];
                });
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
                  popupBudgeted: popup.budgeted,
                  plop, homingFresh, cannonFresh, cannonDiagonal,
                  cannon, accel, budget
                };
              } finally { window.random32 = savedRandom32; }
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
                   popup[162]["alive"] is False and
                   exact_anim["popupBudgeted"] is False,
                   "POPUP closing 0xa72a neskoncil KILL na t162")
            expect(exact_anim["plop"] ==
                   [{"t": 1, "file": "BULLET.LIN", "frame": 2,
                     "x": 81.5, "y": 88}, None, None] and
                   exact_anim["homingFresh"] == [19,80,93],
                   "same-VBL HOMING/PLOP lifecycle nebo inherited velocity nesedi: %s"
                   % exact_anim)
            expect(exact_anim["cannonFresh"] ==
                   [96.5,80,1,90,24,0],
                   "fresh cannon nema prvni same-VBL movement/pre-depth: %s" %
                   exact_anim["cannonFresh"])
            expect(exact_anim["cannonDiagonal"] ==
                   [[32,91.353516,91.353516,95],
                    [160,67.646484,67.646484,84]],
                   "cannon initial ADD.W nebere signed high word 16.16: %s" %
                   exact_anim["cannonDiagonal"])
            expect(exact_anim["cannon"] ==
                   [[[24, 0, True]],
                    [[40, 1, True]],
                    [[40, 1, True], [24, 0, False]],
                    [[24, 0, True], [40, 1, False]],
                    [[40, 1, True], [24, 0, False]]],
                   "granaty nemaji vlastni fazi 24/40 pro accel i straight: %s"
                   % exact_anim["cannon"])
            expect(exact_anim["accel"] ==
                   [[96.5, 0.5], [97, 0.5], [97.5, 0.5], [98, 0.5],
                    [98.5, 1], [99.5, 1], [100.5, 1]],
                   "granat nepouziva novou rychlost az po patem pohybu: %s"
                   % exact_anim["accel"])
            expect(exact_anim["budget"] ==
                   {"accepted": [True] * 5, "rejected": False,
                    "shots": 5, "plops": 0},
                   "plny cannon budget nevypnul strelu i PLOP: %s"
                   % exact_anim["budget"])

            # Druha exactness vrstva nalezena proti nativnimu kodu po
            # Claude auditu: PRNG/VHPOSR, difficulty, unguarded costy,
            # MEDTANK child task, spread weapon a world-space cannon.
            native_exact = page.evaluate("""() => {
              const mkGame = (spawns = []) => ({
                tick: 0, scroll: 100, scrollMul: 1, over: false, won: false,
                player: { x: 160, y: 192, alive: false, inv: 0,
                  bubbleTimer: 0, rank: 0, weapon: 0 },
                keys: {}, bullets: [], shots: [], plops: [], spawns,
                booms: [], effects: [], air: [], hazards: [], tokens: [],
                players: 1, difficulty: 0, levelPhase: 0, activeCost: 0,
                score: 0, nextLife: 10000, lives: 3, nextBobOrdinal: 1,
                fadeBlack: 0, fadeWhite: 0, fadeDir: 0, fadeWhiteStep: 0,
                smartPulse: 0, smartPulseTasks: [], rngState: 0,
                rngVhposWord: 0, rotoDirectionWord: 0
              });

              const irq = { rngState: 0, rngVhposWord: 0x1234, tick: 0 };
              perturbRandomSoundIrq(irq, 0);
              const irqSeed = irq.rngState >>> 0;
              const rng1 = random32(irq) >>> 0;
              const rng2 = random32(irq) >>> 0;
              const wrap = { rngState: 0xabcd1234, rngVhposWord: 0x6000,
                             tick: 0 };
              perturbRandomSoundIrq(wrap, 0);
              const carry = { rngState: 0x80000000 };
              const rngCarry = random32(carry) >>> 0;

              const dg = { player: { rank: 2048, weapon: 4 },
                           player2: { rank: 0, weapon: 0 }, levelPhase: 3 };
              updateDifficulty(dg);

              const savedRandom32 = window.random32;
              let rngCalls = 0;
              window.random32 = () => { rngCalls++; return 0x003f0000; };
              const fg = { air: [], waveSeq: 0, difficulty: 2,
                activeCost: 0, scroll: 148, players: 1, nextBobOrdinal: 1 };
              spawnFodderFormation(fg, { y: 100, typ: 0 });
              const formationCalls = rngCalls;
              fg.difficulty = 5;
              activateAirMember(fg, fg.air[0], { x: 100, y: 200, alive: true });
              const fod = { count: fg.air.length, formationCalls,
                totalCalls: rngCalls, shooter: fg.air[0].shooter,
                cooldown: fg.air[0].cool, hp: fg.air[0].hp };

              window.random32 = () => 0x4000;
              const costs = { activeCost: 160, hazards: [], nextBobOrdinal: 1,
                              rngState: 0 };
              spawnProxFragment(costs, { x: 0, y: 0 }, 0);
              const proxCost = costs.activeCost;
              const flameParent = { x: 10, y: 20, alive: true };
              spawnFlameEmitter(costs, flameParent);
              const emitterCost = costs.activeCost;
              spawnFlamePuff(costs, costs.hazards[1]);
              const puffCost = costs.activeCost;
              const loco = { x: -48, y: 80, vx: 1, alive: true,
                             cost: 15, budgeted: false };
              accountCost(costs, loco); spawnTrainCars(costs, loco, 2);
              const costModel = { proxCost, emitterCost, puffCost,
                trainCost: costs.activeCost,
                trainFrames: costs.hazards.filter(h => h.kind === 'traincar')
                  .map(h => h.frame) };
              const orphanPos = { vx: 1 }, orphanNeg = { vx: -1 };
              for (let i = 0; i < 5; i++) {
                decayTrainVelocity(orphanPos); decayTrainVelocity(orphanNeg);
              }
              const trainDecay = [orphanPos.vxRaw, orphanNeg.vxRaw];

              const tg = mkGame(); tg.tick = 10; tg.difficulty = 3;
              tg.activeCost = 160;
              const tank = { x: 100, y: 100, cost: 10, budgeted: false };
              accountCost(tg, tank); setupTankMotion(tg, tank, 1);
              const tankCost = tg.activeCost;
              const turn240 = { tang: 240 };
              beginTankTurn(tg, turn240, 0, 'aim');
              const turn255 = { tang: 0 };
              beginTankTurn(tg, turn255, 255, 'aim');
              const turn8 = { tang: 0 };
              beginTankTurn(tg, turn8, 8, 'aim');
              const repeat = { x: 100, y: 100, ang: 64, tang: 64,
                turretTask: { alive: true }, turretPhase: 'postfire',
                turretWait: 1 };
              tg.tick = 77; stepTankTurret(tg, repeat);
              const tankTurn = {
                cost: tankCost,
                from240: [turn240.tang, turn240.turretPhase,
                          turn240.turretSteps, turn240.turretWait],
                to255: [turn255.tang, turn255.turretPhase, turn255.turretWait],
                to8: [turn8.tang, turn8.turretPhase,
                      turn8.turretSteps, turn8.turretWait],
                repeat: [repeat.turretPhase, repeat.turretStartTick]
              };

              const six = mkGame();
              six.shots = Array.from({length: 5}, () => ({ kind: 'can',
                x: 50, y: 50, ang: 0, spd: .5, st: 0, accel: true, phase: 0 }));
              const gunTank = { x: 100, y: 200, ang: 64, tang: 64,
                turretTask: { alive: true }, turretPhase: 'prefire',
                turretWait: 1 };
              stepTankTurret(six, gunTank);

              const type4 = { born: false, taskStarted: true, armed: true,
                alive: true, beh: 'tank', file: 'MEDTANK.LIN', idx: 0,
                x: 100, y: 84, typ: 4, st: 0, t: 0, hp: 0, fr: -1,
                at: 0, bobOrdinal: 1 };
              const t4g = mkGame([type4]); t4g.activeCost = 160;
              t4g.difficulty = 3; t4g.player.rank = 6144;
              step(t4g);
              const t4Born = [type4.born, type4.tankSetup, type4.hp,
                              t4g.activeCost];
              // sy je word: y - floor(scroll); prah 288 sondujeme celociselne
              type4.y = Math.floor(t4g.scroll) + 287.5; step(t4g);
              const t4Below = [type4.tankSetup, t4g.activeCost];
              type4.y = Math.floor(t4g.scroll) + 288; step(t4g);
              const t4At = [type4.tankSetup, type4.hullF,
                            type4.turretTask && type4.turretTask.alive,
                            t4g.activeCost, type4.y - Math.floor(t4g.scroll)];

              // Pred prvnim 0x62d2 raw-wait TYP4 zadny node nepublikuje:
              // skryty tank na sve budouci pozici nesmi pohltit HW bolt.
              const hiddenTank = { born: true, taskStarted: true, armed: true,
                alive: true, beh: 'tank', file: 'MEDTANK.LIN', idx: 0,
                x: 100, y: 200, typ: 4, tankType: 4, tankSetup: false,
                hp: 4, cost: 10, budgeted: true, fr: -1, at: 0 };
              const hidden = mkGame([hiddenTank]); hidden.activeCost = 10;
              hidden.bullets.push({ x: 100, y: 100, vx: 0, vy: 0,
                                    frame: 14, ball: 0 });
              step(hidden);
              const hiddenType4Bullet = hidden.bullets.length;

              const fan = mkGame();
              Object.assign(fan.player, { alive: true, inv: 1000,
                weapon: 5, mode: 1, reload: 11, cool: 0,
                weaponX: 160, weaponY: 192, ang: 192,
                bubbleTimer: 0, heliAnimPos: 0, heliAnimFresh: true });
              fan.keys = { f: true }; fan.scrollMul = 0;
              step(fan);
              const fanVelocity = fan.bullets.map(b => [b.vx, b.vy]);

              const world = mkGame();
              world.shots = [
                { kind: 'can', x: 100, y: 100, ang: 0, spd: 5,
                  st: 0, accel: false, phase: 0 },
                { kind: 'hom', x: 100, y: 100, ang: 0, spd: 3,
                  lead: 20, corr: 10, ct: 0, cost: 5, budgeted: true }
              ];
              step(world);
              const shotSpace = world.shots.map(s => [s.kind, s.x, s.y]);
              const depthGame = mkGame();
              depthGame.shots = [{ kind: 'can', x: 100, y: 40, ang: 64,
                spd: 5, st: 0, accel: false, phase: 0 }];
              step(depthGame);
              const depthShot = depthGame.shots[0];
              const depthRecord = townHwCandidates(depthGame)
                .find(r => r.kind === 'cannon');
              const cannonDepth = [depthShot.y, depthShot.hwDepth,
                depthRecord.frame, depthRecord.key,
                bobDepthKey(70), bobDepthKey(72)];

              const roto = { born: true, taskStarted: true, armed: true,
                alive: true, beh: 'roto', file: 'ROTOBASE.LIN', idx: 4,
                x: 100, y: 200, fr: 4, at: 0, spin: 4, sd: 1,
                t: 1, salvoAngle: 7, hp: 4, cost: 10, budgeted: true };
              const rg = mkGame([roto]); rg.activeCost = 10;
              rg.shots = Array.from({length: 5}, () => ({ kind: 'can',
                x: 160, y: 100, ang: 0, spd: .5, st: 0,
                accel: true, phase: 0 }));
              rngCalls = 0;
              window.random32 = () => { rngCalls++; return 0x12345678; };
              step(rg);
              const rotoFire = { shots: rg.shots.length, rngCalls,
                newAngles: rg.shots.slice(5).map(s => s.ang),
                next: [roto.salvoAngle, roto.t] };

              window.random32 = savedRandom32;
              return { scroll: SCROLL, irq: [irqSeed, rng1, rng2,
                       wrap.rngState >>> 0, rngCarry], difficulty: dg.difficulty,
                       fod, costModel, trainDecay, tankTurn,
                       sixth: six.shots.length,
                       type4: [t4Born, t4Below, t4At], fanVelocity,
                       hiddenType4Bullet, shotSpace, cannonDepth, rotoFire };
            }""")
            expect(native_exact["scroll"] == 12.5 and
                   native_exact["irq"] ==
                   [0x12340000, 0x00002468, 0x48D00000,
                    0x0BCD1234, 0x2B411D87],
                   "VHPOSR/0x883c PRNG nebo scroll $4000 nejsou bitove presne: %s" %
                   native_exact)
            expect(native_exact["difficulty"] == 3 and
                   native_exact["fod"] == {"count": 5, "formationCalls": 1,
                     "totalCalls": 2, "shooter": True, "cooldown": 95,
                     "hp": 1},
                   "fp182 difficulty/FOD task-start a activation RNG nesedi: %s" %
                   native_exact)
            expect(native_exact["costModel"] == {
                     "proxCost": 165, "emitterCost": 166, "puffCost": 176,
                     "trainCost": 221, "trainFrames": [1, 1]},
                   "unguarded a2c6 cost nebo TRAIN bit14 mapovani nesedi: %s" %
                   native_exact["costModel"])
            expect(native_exact["trainDecay"] == [47461, -47460],
                   "TRAIN orphan slowdown nezachovava signed 16.16 truncaci: %s" %
                   native_exact["trainDecay"])
            expect(native_exact["tankTurn"] == {
                     "cost": 174,
                     "from240": [256, "turn", 0, 6],
                     "to255": [0, "prefire", 16],
                     "to8": [16, "turn", 0, 6],
                     "repeat": ["first-gate", 77]} and
                   native_exact["sixth"] == 6,
                   "MEDTANK turret cost/int8 quantization/gate/direct cannon nesedi: %s" %
                   native_exact)
            expect(native_exact["type4"][0] == [True, False, 4, 170] and
                   native_exact["type4"][1] == [False, 170] and
                   native_exact["type4"][2][:4] == [True, 3, True, 174] and
                   abs(native_exact["type4"][2][4] - 287.5) < 1e-9,
                   "MEDTANK TYP4 nema raw sy288 wait a parent+child cost: %s" %
                   native_exact["type4"])
            expect(native_exact["hiddenType4Bullet"] == 1,
                   "MEDTANK TYP4 pred prvnim 0x62d2 publikuje collision node")
            expect(native_exact["fanVelocity"] ==
                   [[0,-9],[-1,-8],[1,-8],[-2,-7],[2,-7]],
                   "TOKEN mode1 neprepina HELI na presny spread fan: %s" %
                   native_exact["fanVelocity"])
            expect(native_exact["shotSpace"] ==
                   [["can",105,101],["hom",103,100]] and
                   native_exact["cannonDepth"] ==
                   [46,70,44,32697,32697,32695] and
                   native_exact["rotoFire"] == {"shots": 9, "rngCalls": 1,
                     "newAngles": [7,71,135,199], "next": [120,320]},
                   "cannon world-space nebo ROTO one-RNG/unguarded salvo nesedi: %s" %
                   native_exact)

            # Paula/CIAB exactness: ctyri persistentni voice struktury,
            # pair preference s fallbackem, strict priority, proceduralni
            # timelines, persistentni 0x56e6 scratch a dvouvrstvy BIGEXPL.
            audio_exact = page.evaluate("""() => {
              const savedActx = actx;
              actx = null;                     // pure logical model, bez vystupu
              try {
                const fresh = () => ({ tick: 0, rngState: 0,
                  rngVhposWord: 0, sfx: createTownSfxState(),
                  nextBobOrdinal: 1, tokenSfxTasks: [],
                  townExplosionTasks: [], smartPulse: 0,
                  smartPulseTasks: [], smartPulseTaskOrdinals: [],
                  shots: [], air: [], hazards: [], spawns: [], tokens: [],
                  plops: [], booms: [], effects: [] });
                const eventChannels = (x) => {
                  const g = fresh();
                  for (let i = 0; i < 5; i++) sfxPlayerFire(g, x);
                  return { g, channels: g.sfx.events.map(e =>
                    e.accepted ? e.channel : null) };
                };
                const left = eventChannels(40), right = eventChannels(200);
                advanceTownSfxIrq(left.g);
                sfxPlayerFire(left.g, 40);
                const preempt = {
                  channel: left.g.sfx.events.at(-1).channel,
                  guards: left.g.sfx.voices.map(v => v.guard),
                };

                const fire = sfxFireTimeline(), hit = sfxHitTimeline();
                const a500 = paulaA500FilterCoefficients(44100);
                const busProbe = (() => {
                  const saved = [paulaBusContext, paulaBusInput, paulaBusNodes];
                  const probe = withIir => {
                    const links = [], filters = [];
                    const destination = { label: 'destination' };
                    const node = label => ({ label, gain: { value: 0 },
                      connect(target) { links.push([label, target.label]); } });
                    const context = { sampleRate: 44100, destination,
                      createGain: () => node('gain') };
                    if (withIir) context.createIIRFilter = (feed, feedback) => {
                      const n = node('iir' + filters.length);
                      filters.push([feed.length, feedback.length]); return n;
                    };
                    paulaBusContext = null; paulaBusInput = null;
                    paulaBusNodes = [];
                    const input = paulaOutputBus(context);
                    return { gain: input.gain.value, links, filters,
                             nodes: paulaBusNodes.length };
                  };
                  const result = { filtered: probe(true), fallback: probe(false) };
                  [paulaBusContext, paulaBusInput, paulaBusNodes] = saved;
                  return result;
                })();
                const shield = sfxShieldBubbleTimeline();
                const tokenTone = sfxTokenPickupTimeline(159);
                const transition = sfxPlayerTransitionTimeline();
                const openA = sfxOpeningTimeline(2500, 50);
                const openB = sfxOpeningTimeline(2227, 90);
                const boss = sfxBossDeathTimeline(200);
                const ticks = states => states.reduce((n, s) => n + s.ticks, 0);
                const cannonSpec = sfxNoiseTimeline(
                  { scratch: new Uint8Array(256) }, 'cannon');
                const cannon = cannonSpec.states;
                const homingSpec = sfxNoiseTimeline(
                  { scratch: new Uint8Array(256) }, 'homing');
                const homing = homingSpec.states;
                const flameSpec = sfxNoiseTimeline(
                  { scratch: new Uint8Array(256) }, 'flame-puff');
                const flame = flameSpec.states;
                const wrapped = cannon.find(s => s.period === -29916);
                const signedPcm = sfxRenderTimeline([{
                  wave: new Int8Array([127, 0]), volume: 64,
                  period: -29916, length: 2, ticks: 1,
                }], 1000);
                const dmaMinPcm = sfxRenderTimeline([{
                  wave: new Int8Array([127, 0]), volume: 64,
                  period: 72, length: 2, ticks: 1,
                }], PAULA_CLOCK / 72).slice(0, 8);

                const scratch = new Uint8Array(256);
                const hex = a => Array.from(a).map(v =>
                  v.toString(16).padStart(2, '0')).join('');
                sfxNoiseFill(scratch, 8);
                const noise1 = hex(scratch.slice(0, 32));
                sfxNoiseFill(scratch, 8);
                const noise2 = hex(scratch.slice(0, 32));
                const zeroEdge = new Uint8Array(256);
                sfxWriteLong(zeroEdge, 0, 0xFFFFFFFF);
                sfxNoiseFill(zeroEdge, 6);
                const zeroEdgeHex = hex(zeroEdge.slice(0, 24));

                const gooseTimelineScratch = new Uint8Array(256);
                gooseTimelineScratch.fill(0xAA);
                sfxWriteLong(gooseTimelineScratch, 0, 6);
                const gooseTimeline = sfxGooseHitTimeline(gooseTimelineScratch);

                const goose = fresh();
                goose.rngVhposTrace = [1, 2];
                goose.sfx.voices[0].scratch.fill(0xAA);
                goose.sfx.voices[1].scratch.fill(0xAA);
                sfxGooseHit(goose);
                const gooseSubmit = {
                  events: goose.sfx.events.map(e =>
                    [e.kind, e.accepted, e.voice, e.channel, e.period]),
                  guards: goose.sfx.voices.map(v => v.guard),
                  rng: goose.rngState >>> 0,
                };
                advanceTownSfxIrq(goose);
                const gooseIrq1 = {
                  guards: goose.sfx.voices.map(v => v.guard),
                  rng: goose.rngState >>> 0,
                  scratch: goose.sfx.voices.slice(0, 2).map(v =>
                    hex(v.scratch.slice(0, 8))),
                };
                advanceTownSfxIrq(goose);
                const gooseIrq2 = {
                  guards: goose.sfx.voices.map(v => v.guard),
                  rng: goose.rngState >>> 0,
                  seeds: goose.sfx.voices.slice(0, 2).map(v =>
                    v.effect.dynamic.seed >>> 0),
                  scratch: goose.sfx.voices.slice(0, 2).map(v =>
                    hex(v.scratch.slice(0, 32))),
                };
                for (let i = 0; i < 63; i++) advanceTownSfxIrq(goose);
                const gooseIrq65 = {
                  guards: goose.sfx.voices.map(v => v.guard),
                  effects: goose.sfx.voices.slice(0, 2).map(v => !!v.effect),
                  states: goose.sfx.voices.slice(0, 2).map(v =>
                    v.effect.dynamic.stateCount),
                  scratch: goose.sfx.voices.slice(0, 2).map(v =>
                    hex(v.scratch.slice(0, 24))),
                };
                advanceTownSfxIrq(goose);
                const gooseIrq66 = {
                  guards: goose.sfx.voices.map(v => v.guard),
                  effects: goose.sfx.voices.slice(0, 2).map(v => !!v.effect),
                  scratch: goose.sfx.voices.slice(0, 2).map(v =>
                    hex(v.scratch.slice(0, 24))),
                };

                const gooseOrder = fresh();
                gooseOrder.sfx.voices[0].guard = 160;
                sfxGooseHit(gooseOrder);
                advanceTownSfxIrq(gooseOrder);
                advanceTownSfxIrq(gooseOrder);
                const gooseOrdered = {
                  events: gooseOrder.sfx.events.map(e =>
                    [e.voice, e.channel]),
                  rng: gooseOrder.rngState >>> 0,
                  scratch1: hex(gooseOrder.sfx.voices[1].scratch.slice(0, 24)),
                  scratch3: hex(gooseOrder.sfx.voices[3].scratch.slice(0, 24)),
                };

                const gooseRejected = fresh();
                for (const voice of gooseRejected.sfx.voices) voice.guard = 160;
                sfxGooseHit(gooseRejected);
                advanceTownSfxIrq(gooseRejected);
                advanceTownSfxIrq(gooseRejected);
                const gooseReject = {
                  accepted: gooseRejected.sfx.events.map(e => e.accepted),
                  rng: gooseRejected.rngState >>> 0,
                  scratch: gooseRejected.sfx.voices.map(v =>
                    hex(v.scratch.slice(0, 4))),
                };

                const goosePreempted = fresh();
                goosePreempted.sfx.voices[0].scratch.fill(0xAA);
                goosePreempted.sfx.voices[1].scratch.fill(0xAA);
                sfxGooseHit(goosePreempted);
                advanceTownSfxIrq(goosePreempted);
                sfxPlayerBurst(goosePreempted);
                advanceTownSfxIrq(goosePreempted);
                const goosePreempt = {
                  rng: goosePreempted.rngState >>> 0,
                  scratch: goosePreempted.sfx.voices.slice(0, 2).map(v =>
                    hex(v.scratch.slice(0, 4))),
                };

                const noiseGame = fresh();
                const noiseVoice = sfxNoise(noiseGame, 40, 50, 'cannon');
                advanceTownSfxIrq(noiseGame);
                const scratchIrq1 = hex(noiseVoice.scratch.slice(0, 12));
                advanceTownSfxIrq(noiseGame);
                const scratchIrq2 = hex(noiseVoice.scratch.slice(0, 12));

                const releaseGame = fresh();
                const releaseVoice = sfxPlayerFire(releaseGame, 40);
                for (let i = 0; i < 33; i++) advanceTownSfxIrq(releaseGame);
                const release33 = [releaseVoice.guard,
                  releaseVoice.effect !== null];
                advanceTownSfxIrq(releaseGame);
                const release34 = [releaseVoice.guard,
                  releaseVoice.effect !== null];

                const shieldState = fresh();
                const shieldVoice = sfxShieldBubble(shieldState, 40);
                advanceTownSfxIrq(shieldState);
                const shieldIrq1 = hex(shieldVoice.scratch.slice(0, 16));
                advanceTownSfxIrq(shieldState);
                const shieldIrq2 = hex(shieldVoice.scratch.slice(0, 16));
                for (let i = 0; i < 48; i++) advanceTownSfxIrq(shieldState);
                const shieldIrq50 = [shieldVoice.guard,
                  shieldVoice.effect !== null];

                const tokenState = fresh();
                const tokenVoice = sfxTokenPickupNote(tokenState, 40, 159);
                advanceTownSfxIrq(tokenState);
                const tokenIrq1 = hex(tokenVoice.scratch.slice(0, 8));
                advanceTownSfxIrq(tokenState);
                const tokenIrq2 = hex(tokenVoice.scratch.slice(0, 8));
                advanceTownSfxIrq(tokenState);
                advanceTownSfxIrq(tokenState);
                const tokenIrq4 = hex(tokenVoice.scratch.slice(0, 8));
                for (let i = 0; i < 126; i++) advanceTownSfxIrq(tokenState);
                const tokenIrq130 = [tokenVoice.guard,
                  tokenVoice.effect !== null,
                  hex(tokenVoice.scratch.slice(0, 8)),
                  tokenState.rngState >>> 0];

                const clock = fresh(), perFrame = [];
                let clockTicks = 0;
                for (let i = 0; i < 125; i++) {
                  const n = advanceTownSfxClock(clock);
                  if (i < 11) perFrame.push(n);
                  clockTicks += n;
                }

                const big = fresh();
                sfxBigExplosion(big, 40);
                const bigEvents = big.sfx.events.map(e =>
                  [e.accepted, e.channel, e.period]);
                const rejected = fresh();
                for (const voice of rejected.sfx.voices) voice.guard = 1000;
                sfxBigExplosion(rejected, 40);

                const burst = fresh();
                sfxPlayerBurst(burst);

                const smart = fresh();
                sfxSmartBomb(smart);
                const smartSubmit = {
                  events: smart.sfx.events.map(e =>
                    [e.accepted, e.voice, e.channel, e.priority, e.period]),
                  guards: smart.sfx.voices.map(v => v.guard),
                  ends: smart.sfx.voices.map(v => v.effect && v.effect.end),
                  rng: smart.rngState >>> 0,
                };
                advanceTownSfxIrq(smart);
                const smartIrq1 = smart.sfx.voices.map(v => v.guard);
                const smartRetrigger = sfxSmartBomb(smart).map(Boolean);
                const smartImmediateGame = fresh();
                Object.assign(smartImmediateGame, { fadeWhite: 0,
                  fadeWhiteStep: 0, smartPulse: 0, smartPulseTasks: [] });
                startWhiteFlash(smartImmediateGame);
                startWhiteFlash(smartImmediateGame);
                runFreshTownPriorityTasks(smartImmediateGame);
                const smartImmediate = smartImmediateGame.sfx.events
                  .slice(4).map(e => e.accepted);
                const smartBlockedGame = fresh();
                for (const voice of smartBlockedGame.sfx.voices)
                  voice.guard = 508;
                sfxSmartBomb(smartBlockedGame);
                const smartBlocked = smartBlockedGame.sfx.events
                  .map(e => e.accepted);
                const smartBoundary = fresh();
                sfxSmartBomb(smartBoundary);
                for (let i = 0; i < 507; i++) advanceTownSfxIrq(smartBoundary);
                const smartIrq507 = [
                  smartBoundary.sfx.voices.map(v => v.guard),
                  smartBoundary.sfx.voices.map(v => !!v.effect)];
                advanceTownSfxIrq(smartBoundary);
                const smartIrq508 = [
                  smartBoundary.sfx.voices.map(v => v.guard),
                  smartBoundary.sfx.voices.map(v => !!v.effect)];
                for (let i = 508; i < 65538; i++)
                  advanceTownSfxIrq(smartBoundary);
                const smartIrq65538 = smartBoundary.sfx.voices
                  .map(v => !!v.effect);
                advanceTownSfxIrq(smartBoundary);
                const smartIrq65539 = smartBoundary.sfx.voices
                  .map(v => !!v.effect);
                const smartFile = state.files.find(f => f.name === 'SMART.SND');
                const smartRaw = smartFile ? unpackFile(state.adf, smartFile)
                  : new Uint8Array();
                const smartRawLength = smartFile ? smartRaw.length : -1;
                const smartRawFirst = hex(smartRaw.slice(0, 16));

                const flashHook = fresh();
                Object.assign(flashHook, { fadeWhite: 0, fadeWhiteStep: 0,
                  smartPulse: 0, smartPulseTasks: [] });
                startWhiteFlash(flashHook);
                sfxBigExplosion(flashHook, 40);
                runFreshTownPriorityTasks(flashHook);
                const smartConflict = {
                  events: flashHook.sfx.events.map(e => [e.kind, e.accepted]),
                  rng: flashHook.rngState >>> 0,
                };

                const shieldHook = fresh();
                Object.assign(shieldHook, { activeCost: 0,
                  player: { x: 200, bubbleTimer: 500,
                    bubbleBound: { started: false, visible: false,
                      budgeted: false } } });
                stepPlayerBubbleChild(shieldHook, shieldHook.player);
                stepPlayerBubbleChild(shieldHook, shieldHook.player);

                const tokenHook = fresh();
                Object.assign(tokenHook, { activeCost: 0, score: 0,
                  nextLife: 10000, lives: 4, tokenSfxTasks: [],
                  player: { alive: true, inv: 0, weapon: 0, tokenCount: 0,
                    mode: 0, reload: 11 } });
                const tokenPickupObject = { x: 40, typ: 3, dead: false,
                  cost: 0, budgeted: false };
                pickupToken(tokenHook, tokenPickupObject);
                const tokenEnqueue = {
                  events: tokenHook.sfx.events.length,
                  task: tokenHook.tokenSfxTasks.map(t =>
                    [t.started, t.next, t.wait, t.bobOrdinal, t.x]),
                };
                tokenPickupObject.x = 220; tokenHook.player.x = 220;
                runFreshTownPriorityTasks(tokenHook);
                const tokenPending = [];
                for (let frame = 1; frame <= 20; frame++) {
                  advanceTownSfxClock(tokenHook);
                  tokenHook.tick++;
                  const ready = townCollisionResumeTasks(tokenHook)
                    .filter(task => task.kind === 'tokenSfx');
                  for (const task of ready)
                    resumeTownObjectHousekeeping(tokenHook, task);
                  compactTokenSfxTasks(tokenHook);
                  if (frame === 15 || frame === 20)
                    tokenPending.push(tokenHook.tokenSfxTasks.length);
                }
                const maxTokenHook = fresh();
                Object.assign(maxTokenHook, { activeCost: 0, score: 0,
                  nextLife: 10000, lives: 4, tokenSfxTasks: [],
                  fadeWhite: 0, fadeWhiteStep: 0, smartPulse: 0,
                  smartPulseTasks: [], player: { alive: true, inv: 0,
                    weapon: 0, tokenCount: 0, mode: 0, reload: 11 } });
                pickupToken(maxTokenHook, { x: 40, typ: 4, dead: false,
                  cost: 0, budgeted: false });
                runFreshTownPriorityTasks(maxTokenHook);

                // Fresh TOKEN sound a 0x894a exploze sdileji creation FIFO.
                // Nizsi priority BIGEXPL se smi nejdriv prijmout a teprve
                // pozdejsi priority120 nota jej preemptuje.
                const fifoLowFirst = fresh();
                queueTownExplosionTask(fifoLowFirst, 40, 80, 33, 'fifo-low');
                sfxTokenPickup(fifoLowFirst, 40);
                runFreshTownPriorityTasks(fifoLowFirst);
                const fifoTokenFirst = fresh();
                sfxTokenPickup(fifoTokenFirst, 40);
                queueTownExplosionTask(fifoTokenFirst, 40, 80, 33,
                                       'fifo-late');
                runFreshTownPriorityTasks(fifoTokenFirst);
                const tokenFifo = {
                  lowFirst: fifoLowFirst.sfx.events.map(e =>
                    [e.kind, e.accepted, e.channel, e.period]),
                  tokenFirst: fifoTokenFirst.sfx.events.map(e =>
                    [e.kind, e.accepted, e.channel, e.period]),
                };

                // TOKEN child vznikly ve starsim collision callbacku se
                // nesmi rozbehnout pred GOOSE callbackem, ktery uz na
                // zacatku priority100 sweepu cekal ve stejnem snapshotu.
                const fifoExisting = fresh();
                Object.assign(fifoExisting, { activeCost: 0, score: 0,
                  nextLife: 10000, lives: 4, nextBobOrdinal: 3,
                  player: { alive: true, inv: 0, weapon: 0, tokenCount: 0,
                    mode: 0, reload: 11 } });
                fifoExisting.tokens = [{ x: 40, y: 80, typ: 3,
                  interactive: true, dead: false, cost: 0, budgeted: false,
                  bobOrdinal: 1,
                  collisionEventWord: TOWN_EVENT_PLAYER_CONTACT }];
                fifoExisting.spawns = [{ beh: 'boss', born: true,
                  alive: true, hp: 2, vx: 3, x: 160, y: 80, parts: [],
                  bobOrdinal: 2,
                  collisionEventWord: TOWN_EVENT_PLAYER_SHOT }];
                for (const task of townCollisionResumeTasks(fifoExisting))
                  resumeTownObjectHousekeeping(fifoExisting, task);
                runFreshTownPriorityTasks(fifoExisting);
                tokenFifo.existingBeforeFresh = fifoExisting.sfx.events
                  .map(e => e.kind);

                const hooks = fresh();
                Object.assign(hooks, { activeCost: 0, shots: [], plops: [],
                  hazards: [], nextBobOrdinal: 1, scroll: 0,
                  player: { x: 160, y: 192, alive: true } });
                fireCannon(hooks, 100, 100, 0);
                fireHoming(hooks, 100, 100, 0);
                spawnFlamePuff(hooks, { x: 40, y: 50 });

                const hitGame = fresh();
                Object.assign(hitGame, { activeCost: 0, score: 0,
                  nextLife: 10000, lives: 3, booms: [], effects: [],
                  townExplosionTasks: [], nextBobOrdinal: 1 });
                const target = { alive: true, hp: 2, x: 80, y: 80,
                  cost: 0, budgeted: false, scoreValue: 10, beh: 'tank' };
                damageSpawn(hitGame, target);
                damageSpawn(hitGame, target);
                runFreshTownExplosionTasks(hitGame);
                const bossHitGame = fresh();
                const bossHit = { alive: true, hp: 2, vx: 3, parts: [] };
                damageBoss(bossHitGame, bossHit);

                const stubStops = [], stubStarts = [], stubPans = [],
                  stubRates = [], stubLengths = [], stubSampleRates = [];
                actx = {
                  state: 'running', sampleRate: 1000, currentTime: 7,
                  destination: {},
                  createBuffer: (_channels, length, rate) => {
                    const data = new Float32Array(length);
                    return { length, sampleRate: rate,
                      copyToChannel: src => data.set(src),
                      getChannelData: () => data };
                  },
                  createBufferSource: () => {
                    const src = { buffer: null, connect: () => {},
                      playbackRate: { value: 1 },
                      stop: () => stubStops.push('new'), onended: null };
                    src.start = when => {
                      stubStarts.push(when); stubRates.push(src.playbackRate.value);
                      stubLengths.push(src.buffer && src.buffer.length);
                      stubSampleRates.push(src.buffer && src.buffer.sampleRate);
                    };
                    return src;
                  },
                  createStereoPanner: () => {
                    const p = { pan: { value: 0 }, connect: () => {} };
                    stubPans.push(p); return p;
                  },
                };
                const gooseWeb = fresh();
                gooseWeb.sfx.voices[0].source = {
                  stop: () => stubStops.push('old0') };
                gooseWeb.sfx.voices[1].source = {
                  stop: () => stubStops.push('old1') };
                sfxGooseHit(gooseWeb);
                const webSubmit = [stubStops.slice(), stubStarts.slice()];
                advanceTownSfxIrq(gooseWeb);
                const webIrq1Starts = stubStarts.slice();
                advanceTownSfxIrq(gooseWeb);
                const gooseWebAudio = {
                  submit: webSubmit, irq1: webIrq1Starts,
                  starts: stubStarts.slice(),
                  pans: stubPans.map(p => p.pan.value),
                };
                const smartWeb = fresh(), smartWebStart = stubStarts.length,
                  smartWebPan = stubPans.length;
                sfxSmartBomb(smartWeb);
                const smartWebAudio = {
                  delays: stubStarts.slice(smartWebStart).map(t => t - 7),
                  rates: stubRates.slice(smartWebStart),
                  lengths: stubLengths.slice(smartWebStart),
                  sampleRates: stubSampleRates.slice(smartWebStart),
                  pans: stubPans.slice(smartWebPan).map(p => p.pan.value),
                };
                const tokenWebStart = stubStarts.length;
                sfxTokenPickupNote(fresh(), 40, 159);
                const tokenWebDelay = stubStarts[tokenWebStart] - 7;
                const bossWebStart = stubStarts.length;
                sfxBigExplosion(fresh(), 40,
                                SFX_GOOSE_EXPLOSION_CHILD_DELAY);
                const bossWebDelays = stubStarts.slice(bossWebStart)
                  .map(t => t - 7);
                actx = null;

                return {
                  allocator: { left: left.channels, right: right.channels,
                    preempt },
                  a500Filter: {
                    gain: PAULA_OUTPUT_GAIN,
                    ledEnabled: PAULA_LED_FILTER_ENABLED,
                    cutoffs: [a500.low.cutoff, a500.led.cutoff,
                              a500.high.cutoff],
                    q: a500.led.q,
                    low: [a500.low.feedforward, a500.low.feedback],
                    led: [a500.led.feedforward, a500.led.feedback],
                    high: [a500.high.feedforward, a500.high.feedback],
                    busProbe,
                  },
                  fire: [fire.length, fire[0].volume, fire[0].period,
                         fire.at(-1).volume, fire.at(-1).period,
                         sfxLogicalTimeline(fire).end],
                  hit: [hit.length, hit[0].volume, hit[0].period,
                        hit.at(-1).volume, hit.at(-1).period,
                        sfxLogicalTimeline(hit).end],
                  shieldTone: [shield.length,
                    shield.slice(0, 8).map(s => s.period),
                    shield[0].volume, shield.at(-1).volume,
                    shield.at(-1).period, sfxLogicalTimeline(shield).end],
                  tokenTone: [tokenTone.length, ticks(tokenTone),
                    tokenTone[0].volume, tokenTone[0].period,
                    hex(tokenTone[0].wave), hex(tokenTone[1].wave),
                    tokenTone.at(-1).volume, hex(tokenTone.at(-1).wave),
                    sfxLogicalTimeline(tokenTone).end],
                  tokenToneWave: tokenTone.map(s => hex(s.wave)).join(''),
                  transition: [transition[0].volume, transition[0].period,
                    transition[1].volume, transition[1].period,
                    transition.at(-1).volume, transition.at(-1).period,
                    sfxLogicalTimeline(transition).end],
                  longTicks: [ticks(openA), sfxLogicalTimeline(openA).end,
                              ticks(openB), sfxLogicalTimeline(openB).end,
                              ticks(boss), sfxLogicalTimeline(boss).end],
                  cannon: [cannon.length, cannon[0].period, cannon[0].length,
                    wrapped && (wrapped.period & 0xffff),
                    cannon.at(-1).period, cannon.at(-1).length,
                    cannonSpec.logical.end,
                    Array.from(signedPcm)],
                  homing: [homing.length, homing[0].volume,
                    homing[0].period, homing.at(-1).volume,
                    homing.at(-1).period, homingSpec.logical.end],
                  flame: [flame.length, ticks(flame), flame[0].volume,
                    flame[0].period, flame[31].volume, flame[31].period,
                    flame[32].volume, flame[32].period, flame[32].ticks,
                    flame.at(-1).volume, flame.at(-1).period,
                    flame.at(-1).ticks, flameSpec.logical.end],
                  dmaMinPcm: Array.from(dmaMinPcm),
                  noise: [noise1, noise2, scratchIrq1, scratchIrq2,
                          zeroEdgeHex],
                  gooseTimeline: [gooseTimeline.length,
                    gooseTimeline[0].volume, gooseTimeline[0].period,
                    gooseTimeline[1].volume, gooseTimeline[1].period,
                    gooseTimeline.at(-1).volume,
                    gooseTimeline.at(-1).period,
                    gooseTimeline.at(-1).length],
                  goose: { submit: gooseSubmit, irq1: gooseIrq1,
                    irq2: gooseIrq2, irq65: gooseIrq65, irq66: gooseIrq66,
                    ordered: gooseOrdered, rejected: gooseReject,
                    preempted: goosePreempt },
                  release: [release33, release34],
                  pickupIrqs: { shield: [shieldIrq1, shieldIrq2, shieldIrq50],
                    token: [tokenIrq1, tokenIrq2, tokenIrq4, tokenIrq130] },
                  clock: [clockTicks, clock.sfx.irq, clock.sfx.phase, perFrame],
                  big: [bigEvents, big.rngState >>> 0,
                    rejected.sfx.events.map(e => e.accepted),
                    rejected.rngState >>> 0],
                  burst: burst.sfx.events.map(e => [e.channel, e.period]),
                  smart: { submit: smartSubmit, irq1: smartIrq1,
                    retrigger: smartRetrigger, immediate: smartImmediate,
                    blocked: smartBlocked,
                    boundaries: [smartIrq507, smartIrq508,
                      smartIrq65538, smartIrq65539],
                    rawLength: smartRawLength, rawFirst: smartRawFirst },
                  pickupSounds: {
                    flash: [flashHook.fadeWhite, flashHook.smartPulse,
                      flashHook.sfx.events.filter(e =>
                        e.kind === 'smart-bomb').map(e => e.kind)],
                    smartConflict,
                    shield: shieldHook.sfx.events.map(e =>
                      [e.kind, e.accepted, e.voice, e.channel,
                       e.priority, e.period]),
                    token: [tokenHook.sfx.events.map(e =>
                      [e.kind, e.accepted, e.channel, e.priority,
                       e.period, e.tick]),
                      tokenEnqueue, tokenPending, tokenHook.tokensPickedUp,
                      tokenHook.player.inv, tokenHook.score],
                    maxToken: maxTokenHook.sfx.events.map(e =>
                      [e.kind, e.accepted, e.channel, e.period]),
                  },
                  tokenFifo,
                  hooks: hooks.sfx.events.map(e => e.kind),
                  damage: hitGame.sfx.events.map(e => e.kind),
                  bossHit: [bossHit.hp, bossHit.vx,
                    bossHitGame.sfx.events.map(e => e.kind)],
                  gooseWebAudio,
                  smartWebAudio,
                  childAudioDelays: { token: tokenWebDelay,
                    boss: bossWebDelays },
                };
              } finally { actx = savedActx; }
            }""")
            expect(audio_exact["allocator"] == {
                     "left": [3, 0, 2, 1, None],
                     "right": [2, 1, 3, 0, None],
                     "preempt": {"channel": 3,
                                  "guards": [80, 79, 79, 79]}},
                   "Paula allocator pair/fallback/strict priority nesedi: %s" %
                   audio_exact["allocator"])
            a500_filter = audio_exact["a500Filter"]
            expect(abs(a500_filter["gain"] - 0.2048) < 1e-12 and
                   a500_filter["ledEnabled"] is False and
                   all(abs(v - e) < 1e-9 for v, e in zip(
                       a500_filter["cutoffs"],
                       [4420.970641441538, 3090.5329041189802,
                        5.127629156243507])) and
                   abs(a500_filter["q"] - 0.6602252917735248) < 1e-12 and
                   all(abs(v - e) < 1e-12 for v, e in zip(
                       a500_filter["low"][0] + a500_filter["low"][1],
                       [0.4566588477496909, 1, -0.5433411522503091])) and
                   all(abs(v - e) < 1e-12 for v, e in zip(
                       a500_filter["led"][0] + a500_filter["led"][1],
                       [0.1146938232350718, 0.2293876464701436,
                        0.1146938232350718, 1, -0.803844081470823,
                        0.2626193744111102])) and
                   all(abs(v - e) < 1e-12 for v, e in zip(
                       a500_filter["high"][0] + a500_filter["high"][1],
                       [0.9992697034688279, -0.9992697034688279,
                        1, -0.9992697034688279])),
                   "A500 shared output gain/filter coefficients nesedi: %s" %
                   a500_filter)
            expect(a500_filter["busProbe"] == {
                     "filtered": {"gain": 0.2048,
                       "links": [["gain", "iir0"], ["iir0", "iir1"],
                                 ["iir1", "destination"]],
                       "filters": [[1, 2], [2, 2]], "nodes": 2},
                     "fallback": {"gain": 0.2048,
                       "links": [["gain", "destination"]],
                       "filters": [], "nodes": 0}},
                   "A500 bus zapojil LED filtr nebo fallback ztratil gain: %s" %
                   a500_filter["busProbe"])
            expect(audio_exact["fire"] == [32, 32, 1000, 1, 6508, 34] and
                   audio_exact["hit"] == [16, 64, 200, 4, 5652, 18] and
                   audio_exact["transition"] ==
                   [64, 1500, 63, 1434, 1, 1310, 66],
                   "proceduralni FIRE/HIT/0x4dc6 timeline nesedi: %s" %
                   audio_exact)
            expect(audio_exact["shieldTone"] ==
                   [48, [150,150,154,158,162,162,158,154],
                    48, 1, 154, 50] and
                   audio_exact["tokenTone"] ==
                   [64, 128, 64, 159, "0000000000000000",
                    "1010101090101010", 1, "0000000000000000", 130],
                   "MINE bubble/TOKEN proceduralni timeline nesedi: %s / %s" %
                   (audio_exact["shieldTone"], audio_exact["tokenTone"]))
            expect(hashlib.sha256(bytes.fromhex(
                     audio_exact["tokenToneWave"])).hexdigest() ==
                   "76abe9960cca0b06a96aed5d4a7e5d06edd1505993cc57680fe1c24561dd94dd",
                   "TOKEN 0x5672 waveform hash nesedi")
            expect(audio_exact["longTicks"] == [286, 288, 326, 328, 192, 194],
                   "opening/GOOSE timeline nema presne CIA wait soucty: %s" %
                   audio_exact["longTicks"])
            expect(audio_exact["cannon"][:7] ==
                   [48, 256, 2, 35620, 32504, 6, 50] and
                   all(abs(v - 127 / 128) < 1e-9
                       for v in audio_exact["cannon"][7]),
                   "cannon WORD period/length nebo unsigned Paula render nesedi: %s" %
                   audio_exact["cannon"])
            expect(audio_exact["homing"] == [64, 64, 320, 1, 257, 66] and
                   audio_exact["flame"] ==
                   [96, 160, 0, 500, 62, 500, 64, 1000, 2,
                    1, 1000, 2, 162],
                   "HOMING/FLAME timeline nesedi: %s / %s" %
                   (audio_exact["homing"], audio_exact["flame"]))
            expect(all(abs(v - expected) < 1e-9 for v, expected in zip(
                       audio_exact["dmaMinPcm"],
                       [127 / 128, 127 / 128, 0, 0,
                        127 / 128, 127 / 128, 0, 127 / 128])),
                   "PAL period<123 address-rate clamp nesedi: %s" %
                   audio_exact["dmaMinPcm"])
            expect(audio_exact["noise"][0] ==
                   "d4bfe278efb1b4f842b1c2e485c88563218716162c2c430e861c58589bf111bf" and
                   audio_exact["noise"][1] != audio_exact["noise"][0] and
                   audio_exact["noise"][2] == "000000000000000000000000" and
                   audio_exact["noise"][3] == "d4bfe278efb1b4f800000000" and
                   audio_exact["noise"][4] ==
                   "2b411d873b0e5682ad04761cc779478fa45f93750dab5538",
                   "0x56e6 scratch neni persistentni nebo startuje o IRQ drive: %s" %
                   audio_exact["noise"])
            expect(audio_exact["gooseTimeline"] ==
                   [64, 64, 150, 63, 154, 1, 950, 24],
                   "GOOSE hit waveform timeline nesedi: %s" %
                   audio_exact["gooseTimeline"])
            expect(audio_exact["goose"]["submit"] == {
                     "events": [
                       ["goose-hit-l", True, 0, 3, 150],
                       ["goose-hit-r", True, 1, 2, 150]],
                     "guards": [160, 160, 0, 0], "rng": 0} and
                   audio_exact["goose"]["irq1"] == {
                     "guards": [159, 159, 0, 0], "rng": 0x00010000,
                     "scratch": ["aaaaaaaaaaaaaaaa", "aaaaaaaaaaaaaaaa"]},
                   "GOOSE hit submit/initial yield nesedi: %s" %
                   audio_exact["goose"])
            expect(audio_exact["goose"]["irq2"] == {
                     "guards": [158, 158, 0, 0], "rng": 0x000C0000,
                     "seeds": [6, 0x000C0000],
                     "scratch": [
                       "d4b3e278efb1b4e04281c2e485c88503214716162c2c428eaaaaaaaaaaaaaaaa",
                       "d4bfe260ef81b4f842b1c28485088563218717962f2c430eaaaaaaaaaaaaaaaa"]},
                   "GOOSE hit deferred RNG/first wave nesedi: %s" %
                   audio_exact["goose"]["irq2"])
            goose_last = [
                "68fd5430a860d1fa88b54d46b1cd0ced329b7e1dfc3a6536",
                "4690fb24f6488d213103f116e22c6207ef4fd9df98ffc318"]
            expect(audio_exact["goose"]["irq65"] == {
                     "guards": [95, 95, 0, 0], "effects": [True, True],
                     "states": [64, 64], "scratch": goose_last} and
                   audio_exact["goose"]["irq66"] == {
                     "guards": [0, 0, 0, 0], "effects": [False, False],
                     "scratch": goose_last},
                   "GOOSE hit 64 stavu/IRQ66 cleanup nesedi: %s" %
                   audio_exact["goose"])
            expect(audio_exact["goose"]["ordered"] == {
                     "events": [[3, 0], [1, 2]], "rng": 0x3B0E5682,
                     "scratch1":
                       "efb1b4fa42b5c2e485c8856b219716162c2c432e865c5858",
                     "scratch3":
                       "79bb946428c8f377e6ee51918863d05b8bf70d4031c10a69"} and
                   audio_exact["goose"]["rejected"] == {
                     "accepted": [False, False], "rng": 0,
                     "scratch": ["00000000"] * 4} and
                   audio_exact["goose"]["preempted"] == {
                     "rng": 0,
                     "scratch": ["aaaaaaaa", "aaaaaaaa"]},
                   "GOOSE hit voice-order/reject/preempt RNG nesedi: %s" %
                   audio_exact["goose"])
            expect(audio_exact["release"] == [[47, True], [0, False]] and
                   audio_exact["clock"] ==
                   [511, 511, 167175, [4] * 10 + [5]],
                   "CIAB clock/initial yield/0x4bf2 cleanup nesedi: %s" %
                   audio_exact)
            expect(audio_exact["pickupIrqs"] == {
                     "shield": ["00000000000000000000000000000000",
                       "002040607f60402000e0c0a080a0c0e0", [0,False]],
                     "token": ["0000000000000000", "0000000000000000",
                       "1010101090101010", [0,False,"0000000000000000",0]]},
                   "bubble/TOKEN scratch nebo IRQ cleanup nesedi: %s" %
                   audio_exact["pickupIrqs"])
            expect(audio_exact["big"] == [
                     [[True, 3, 599], [True, 0, 594]], 0x3B0E5682,
                     [False, False], 0x3B0E5682] and
                   audio_exact["burst"] ==
                   [[2, 1024], [1, 1032], [3, 1152], [0, 1160]],
                   "BIGEXPL 2x RNG/layers nebo player 4-layer burst nesedi: %s" %
                   audio_exact)
            expect(audio_exact["smart"] == {
                     "submit": {
                       "events": [
                         [True,1,2,127,1040], [True,2,1,127,1025],
                         [True,0,3,127,1010], [True,3,0,127,996]],
                       "guards": [508,508,508,508],
                       "ends": [65539,65539,65539,65539], "rng": 0},
                     "irq1": [507,507,507,507],
                     "retrigger": [True,True,True,True],
                     "immediate": [False,False,False,False],
                     "blocked": [False,False,False,False],
                     "boundaries": [
                       [[1,1,1,1], [True,True,True,True]],
                       [[0,0,0,0], [True,True,True,True]],
                       [True,True,True,True], [False,False,False,False]],
                     "rawLength": 8280,
                     "rawFirst": "7f7f807f80000000fdfdfdc5c17fbdb9"},
                   "SMART.SND vrstvy/guard/tail/retrigger nesedi: %s" %
                   audio_exact["smart"])
            expect(audio_exact["pickupSounds"] == {
                     "flash": [256, 50, ["smart-bomb"] * 4],
                     "smartConflict": {"events":
                       [["bigexpl",True]] * 2 + [["smart-bomb",True]] * 4,
                       "rng": 0x3B0E5682},
                     "shield": [["shield-bubble", True, 1, 2, 60, 150]],
                    "token": [[
                       ["token-pickup",True,3,120,159,0],
                       ["token-pickup",True,0,120,212,5],
                       ["token-pickup",True,3,120,159,10],
                       ["token-pickup",True,0,120,141,15]],
                       {"events": 0,
                        "task": [[False,0,0,1,40]]},
                       [1,0], 1, 500, 500],
                     "maxToken": [
                       ["token-pickup",True,3,159],
                       ["smart-bomb",True,2,1040],
                       ["smart-bomb",True,1,1025],
                       ["smart-bomb",True,0,1010],
                       ["smart-bomb",True,3,996]]},
                   "SMART/bubble/TOKEN gameplay hooky nesedi: %s" %
                   audio_exact["pickupSounds"])
            expect(audio_exact["tokenFifo"] == {
                     "lowFirst": [
                       ["bigexpl",True,3,599],
                       ["bigexpl",True,0,594],
                       ["token-pickup",True,3,159]],
                     "tokenFirst": [
                       ["token-pickup",True,3,159],
                       ["bigexpl",True,0,599],
                       ["bigexpl",True,2,594]],
                     "existingBeforeFresh": [
                       "goose-hit-l", "goose-hit-r", "generic-hit",
                       "token-pickup"]},
                   "TOKEN child a 0x894a nesdileji creation FIFO: %s" %
                   audio_exact["tokenFifo"])
            expect(audio_exact["hooks"] ==
                   ["cannon", "homing", "flame-puff"] and
                   audio_exact["damage"] ==
                   ["generic-hit", "bigexpl", "bigexpl"] and
                   audio_exact["bossHit"] ==
                   [1, -3,
                    ["goose-hit-l", "goose-hit-r", "generic-hit"]] and
                   audio_exact["gooseWebAudio"] == {
                     "submit": [["old0", "old1"], []], "irq1": [],
                     "starts": [7, 7], "pans": [-1, 1]},
                   "TOWN SFX hooky nebo nonlethal/lethal hit semantika nesedi: %s" %
                   audio_exact)
            smart_web = audio_exact["smartWebAudio"]
            expect(smart_web["lengths"] == [8280] * 4 and
                   smart_web["sampleRates"] == [8000] * 4 and
                   smart_web["pans"] == [1, 1, -1, -1] and
                   all(abs(v - 6928 / 709379) < 1e-12
                       for v in smart_web["delays"]) and
                   all(abs(v - 3546895 / (p * 8000)) < 1e-12
                       for v, p in zip(smart_web["rates"],
                                       [1040,1025,1010,996])),
                   "SMART.SND WebAudio delka/pitch/pan/start nesedi: %s" %
                   smart_web)
            child_delays = audio_exact["childAudioDelays"]
            base_irq_delay = 6928 / 709379
            expect(abs(child_delays["token"] -
                       (base_irq_delay + 0.00946)) < 1e-12 and
                   len(child_delays["boss"]) == 2 and
                   all(abs(v - (base_irq_delay + 0.00921)) < 1e-12
                       for v in child_delays["boss"]),
                   "TOKEN/GOOSE child sub-frame audio delay nesedi: %s" %
                   child_delays)

            dynamics = page.evaluate("""() => {
              const savedRandom = window.random32;
              window.random32 = () => 0;
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
                             townExplosionTasks: [], nextBobOrdinal: 1,
                             score: 0, nextLife: 10000, lives: 3 };
                const mine = { x: 90, y: 120, alive: true, cost: 7,
                               budgeted: true };
                detonateMine(gm, mine, true);
                detonateMine(gm, mine, true); // idempotence
                runFreshTownExplosionTasks(gm);
                const core = gm.hazards[0];

                const gp = { activeCost: 10, hazards: [], effects: [], booms: [],
                             townExplosionTasks: [], nextBobOrdinal: 1,
                             score: 0, nextLife: 10000, lives: 3, scroll: 0,
                             player: { x: 100, y: 100, alive: true } };
                const prox = { x: 0, y: 0, alive: true, cost: 10,
                               budgeted: true, proxAlternate: false };
                detonateProx(gp, prox);
                runFreshTownExplosionTasks(gp);
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
                const millLockedSy = gmi.spawns[0].y - Math.floor(gmi.scroll);
                step(gmi);
                const millMovedSy = gmi.spawns[0].y - Math.floor(gmi.scroll);
                for (let i = 0; i < 98; i++) step(gmi); // druhy krok uz odecetl 1
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
                  // screen-y = world-y - floor(scroll) (fp@(3542) je word)
                  locked: { birdSy: gs.air[0].y - Math.floor(gs.scroll),
                            coreSy: gs.hazards[0].y - Math.floor(gs.scroll) },
                  mill: { locked: gmi.spawns[0].scrollLocked,
                          lockedSy: millLockedSy, movedSy: millMovedSy,
                          before: millBefore, shots: gmi.shots.length,
                          angles: gmi.shots.map(s => s.ang).sort((a,b) => a-b),
                          overCap: millOverCap, released: gmb.activeCost },
                  fallbackShots: gu.shots.length
                };
              } finally { window.random32 = savedRandom; }
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
                   [round(v, 6) for v in dynamics["prox"]["speeds"]] ==
                   [2.501849, 2.500343, 2.501907,
                    2.49834, 2.49979, 2.498168],
                   "PROXMINE nepouziva kvantovanou 0x6a82 SIN LUT: %s" %
                   dynamics["prox"])
            expect(dynamics["train"] == {"count": 4,
                                           "xs": [-96, -144, -192, -240],
                                           "frames": [2, 2, 2, 2], "cost": 75},
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
                   "MILL nema wait100 a osm smeru po 32 stupnich: %s" %
                   dynamics["mill"])
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
              g.scrollMul = 0;
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
                step(g);                       // VBL N pending bit0
                step(g);                       // VBL N+1 damage callback
                return { hp: s.hp, alive: s.alive, score: g.score };
              };
              const hit1 = spr && hit();
              const hitFlash = composeTownBobs(g, Math.floor(g.scroll)).ordered
                .find(r => r.id === 'spawn-main')?.op;
              g.bullets = []; step(g);
              const clearedFlash = composeTownBobs(g, Math.floor(g.scroll)).ordered
                .find(r => r.id === 'spawn-main')?.op;
              const hit2 = spr && hit();
              return { activated, before, first, moved, recoil, settled,
                       hit1, hitFlash, clearedFlash, hit2 };
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
            expect(cam["first"]["frame"] == 1 and abs(cam["first"]["y"] + 7) < 1e-6,
                   "CAMOGUN nema prvni frame a recoil 7 px po prvnim tiku")
            expect(abs(cam["moved"]["dx"]) < 1e-6 and
                   abs(cam["moved"]["dy"] - 5) < 1e-6,
                   "CAMOGUN granat se nepohybuje konstantne 5 px/t dolu")
            expect([round(row["y"]) for row in cam["recoil"]] ==
                   [-7, -6, -5, -4, -3, -2, -1, 0] and
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
            expect(cam["hitFlash"] == "fill9" and
                   cam["clearedFlash"] == "cookie",
                   "default damage callback nema presne jeden index9 frame")
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
