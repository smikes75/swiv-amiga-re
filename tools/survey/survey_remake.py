"""Simulace prepisu pres cely TOWN bez vstupu (neomezene zivoty), snimky v casech t (s po fire)."""
from playwright.sync_api import sync_playwright
import sys, base64, io, os, json
sys.path.insert(0, '/Users/mik/claude46/Amiga/SWIV-projekt/tools')
from compare import to_vamiga
from PIL import Image
ROOT='/Users/mik/claude46/Amiga/SWIV-projekt'
OUT=ROOT+'/build/survey'
TS=None
ticks={}
for x in sys.argv[1].split(","):
    a,b=(x.split(":")+[None])[:2]; ticks[a]=int(b) if b else 50*(int(a)-17)+83
with sync_playwright() as pw:
    b=pw.chromium.launch(); page=b.new_page()
    page.goto("file://"+ROOT+"/game.html")
    page.set_input_files("#fpick", ROOT+"/SWIVFIX.ADF")
    page.wait_for_selector("#titlewrap", state="visible")
    page.evaluate("window.requestAnimationFrame = () => 0")
    page.keyboard.press(" ")
    page.wait_for_selector("#gamewrap", state="visible")
    res = page.evaluate("""(ticks) => {
      startGame(0); const g = state.g, p = g.player;
      g.scrollMul = 1; g.vblBase = 186; g.lives = 100000;
      const fod = [{x: 257, vx: -0.8125}, {x: 195, vx: 0.7}]; let n = 0;
      window.fodderInitial = () => { const f = fod[Math.min(n++, fod.length - 1)]; return {x: f.x, vx: f.vx}; };
      const want = {}; for (const [t, T] of Object.entries(ticks)) want[T] = t;
      const out = {}; const log = [];
      const maxT = Math.max(...Object.keys(want).map(Number));
      let deaths = 0, lastAlive = true;
      for (let i = 1; i <= maxT; i++) {
        if (g.over) { log.push(['over', i, g.won]); break; }
        step(g);
        if (lastAlive && !p.alive) { deaths++; log.push(['death', i, Math.floor(g.scroll)]); }
        lastAlive = p.alive;
        if (want[i]) {
          g.hudCopperPrimed = true; const now = performance.now(); g.last = now; frame(now);
          out[want[i]] = { png: document.querySelector('#game').toDataURL('image/png'), scroll: g.scroll, score: g.score, lives: g.lives, alive: p.alive,
            spawns: g.spawns.filter(s => s.born && s.alive).map(s => [s.beh, Math.round(s.x), Math.round(s.y - g.scroll)]),
            air: g.air.filter(a => a.alive).length, hazards: g.hazards.filter(h => h.alive).length, tokens: g.tokens.filter(k => !k.dead).length };
        }
      }
      return { out, log, deaths };
    }""", ticks)
    for t, d in sorted(res['out'].items(), key=lambda kv: int(kv[0])):
        img = to_vamiga(Image.open(io.BytesIO(base64.b64decode(d['png'].split(',',1)[1]))).convert('RGB'))
        img.save(f"{OUT}/remake_t{t}.png")
        print('t', t, 'T', ticks[t], 'scroll', round(d['scroll']), 'score', d['score'], 'alive', d['alive'], 'spawns', d['spawns'], 'air', d['air'], 'haz', d['hazards'], 'tok', d['tokens'])
    print('log', res['log'][:40], 'deaths', res['deaths'])
    b.close()
