#!/usr/bin/env python3
"""Integration smoke checks for all seven zones and direct-start junctions.

This checks runtime consistency, not Amiga parity. Each zone is sampled at
its opening and later map windows; exact behaviour fixtures live in uitest.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent

PROBE = """lv => {
  startGame(lv);
  const g = state.g;
  const unsupported = g.spawns.filter(s => ['unimplemented','missing-dispatch'].includes(s.beh));
  if (unsupported.length) throw Error('unimplemented routes in zone '+lv);
  const firstMapHeight = g.mapH - g.rowOffset - 320;
  const samples = [];
  // Sample fresh natural ingress at opening, middle and late map positions.
  // Each window runs 1200 native ticks, and renders both presentation paths.
  for (const fraction of (lv === 6 ? [0] : [0, .45, .8])) {
    startGame(lv);
    const q = state.g;
    q.scroll -= firstMapHeight * fraction;
    if (fraction) {
      for (const s of q.spawns) s.armed = s.y - scrollTop(q) < -32;
    }
    q.lives = 10000;
    const seen = new Set();
    for (let i=0; i<1200; i++) {
      q.player.inv = 2; // keep this diagnostic's player available for aiming
      step(q);
      for (const s of q.spawns) if(s.born) seen.add(s.beh);
      const live = [...q.spawns.filter(s=>s.born&&s.alive),
                    ...q.air.filter(s=>s.alive),...q.hazards.filter(s=>s.alive),
                    ...q.shots.filter(s=>!s.dead)];
      for(const s of live) if(!Number.isFinite(s.x)||!Number.isFinite(s.y))
        throw Error('non-finite position: '+(s.beh||s.kind)+' at '+lv+'/'+fraction+'/'+i);
      if (!Number.isFinite(q.activeCost) || q.activeCost < 0)
        throw Error('invalid active cost at '+lv+'/'+i);
      if(i%200===0) {
        for(const smooth of [false,true]) {
          state.smooth=smooth; q.frac=0; q.last=1000; frame(1000);
        }
      }
    }
    samples.push({fraction, routes:[...seen], cost:q.activeCost});
  }
  if (lv === 6) {
    const q = state.g;
    const boss = q.spawns.find(s=>s.beh==='inst5'&&s.born&&s.alive);
    if (!boss || !q.effects.some(e=>e.file==='INST5.LIN') ||
        !q.hazards.some(h=>h.kind==='inst5launch'))
      throw Error('direct FINAL did not create the boss and its children');
    while(boss.hp>0) damageSpawn(q,boss);
    for(let i=0;i<150;i++) step(q);
    if(!q.gameEnded || boss.alive || q.score<20000)
      throw Error('FINAL death sequence did not finish');
  }
  // The map-boundary cursor is relative to the loaded chain; difficulty
  // remains an absolute level phase even when the player starts in SCIFI.
  startGame(lv);
  const j = state.g;
  const saved = {player:j.player, keys:j.keys, score:j.score, lives:j.lives};
  j.spawns=[]; j.air=[]; j.hazards=[]; j.shots=[]; j.bullets=[];
  j.tokens=[]; j.booms=[]; j.effects=[]; j.plops=[]; j.scrollMul=0;
  j.inst1Factories=0;
  for(let i=0;i<j.junctionRows.length;i++) {
    j.scroll=j.junctionRows[i]+1; step(j);
    if(j.levelPhase!==lv+i) throw Error('early junction '+lv+'/'+i);
    j.scroll=j.junctionRows[i]; step(j);
    if(j.junctionIndex!==i+1 || j.levelPhase!==lv+i+1)
      throw Error('missed junction '+lv+'/'+i);
    step(j);
    if(j.levelPhase!==lv+i+1) throw Error('duplicate junction '+lv+'/'+i);
  }
  if(j.player!==saved.player || j.keys!==saved.keys ||
     j.score!==saved.score || j.lives!==saved.lives)
    throw Error('junction reset player state');
  return {zone:lv+1,samples,junctions:j.junctionRows.length};
}"""


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1200, "height": 900})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto((ROOT / "game.html").as_uri())
            page.set_input_files("#fpick", str(ROOT / "SWIVFIX.ADF"))
            page.wait_for_selector("#titlewrap", state="visible")
            page.evaluate("window.requestAnimationFrame = () => 0")
            for lv in range(7):
                result = page.evaluate(PROBE, lv)
                assert not errors, errors
                print(f"Zone {lv+1} OK: {len(result['samples'])} windows × 1200 ticks, both renderers, "
                      f"{result['junctions']} junctions", flush=True)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
