#!/usr/bin/env python3
"""End-to-end a behavior regrese hry v realnem Chromiu.

Projde tok vlozeni ADF -> intro -> vyber TOWN, overi puvodni dispatch
tabulku, palety, formace, miny, vlak, plamenomet a cyklus CAMOGUN.
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

            summary = page.evaluate("""() => ({
              dispatch: state.behaviorDispatch.size,
              mapObjects: state.mapMeta.objects,
              spawns: state.g.spawns.length,
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
                                                s.coroutine !== 0xac12).length
            })""")
            expect(summary["dispatch"] == 73, "dispatch nema 73 zaznamu")
            expect(summary["mapObjects"] == 155, "TOWN nema 155 mapovych objektu")
            expected_behaviors = {"wave": 60, "yellow": 12, "bird": 9,
                                  "popup": 6, "mine": 6, "proxmine": 13,
                                  "train": 3, "mill": 2, "tank": 18, "roto": 9,
                                  "flame": 6, "camogun": 10,
                                  "unimplemented": 1}
            expect(summary["spawns"] == 155 and
                   summary["behaviors"] == expected_behaviors,
                   "TOWN nema spravnych 155 routovanych runtime spawnu")
            expect(summary["missing"] == 0, "TOWN obsahuje objekt bez dispatche")
            expect(summary["camoguns"] == 10, "TOWN nema 10 CAMOGUN vezi")
            expect(summary["camType1"] == 5 and summary["camType2"] == 5,
                   "CAMOGUN nema pet dvojic TYP 1/2")
            expect(summary["wrongCam"] == 0, "CAMOGUN nema korutinu 0xac12")

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
                  plops: [], spawns: [], booms: [], effects: [],
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
                  booms: [], effects: [], activeCost: 0, score: 0,
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
