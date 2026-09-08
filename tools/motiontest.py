#!/usr/bin/env python3
"""Strict fractional-motion checks complement the structural pixel oracle."""
from playwright.sync_api import sync_playwright
from displaytest import load_game

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    load_game(page)
    result = page.evaluate("""() => {
      const check=(ok,msg)=>{if(!ok)throw Error(msg);};
      const g=state.g,cv=document.querySelector('#game'),ctx=cv.getContext('2d');
      const template=composeTownBobs(g,scrollTop(g)).ordered.find(r=>r.spr);
      check(template,'BOB fixture');
      cv.width=1280;cv.height=1024;g.fadeBlack=g.fadeWhite=0;
      g.scroll=100.25;g.scrollPrev=100;
      g.bobPrev={top:100,byKey:new Map()};g.bobCur={top:100,byKey:new Map()};
      state.blendBg=true;
      const hashes=new Set();
      for(let i=0;i<12;i++){
        g.frac=TICK*i/12;renderSmoothField(ctx,g,4,{ordered:[]},null);
        check(Math.abs(g.smoothScrollF-(100+.25*i/12))<1e-9,'fractional terrain step');
        const pixels=ctx.getImageData(0,0,1280,1024).data;
        let h=2166136261;for(const p of pixels)h=Math.imul(h^p,16777619);hashes.add(h);
      }
      check(hashes.size===12,'blended background held identical display frames: '+hashes.size);
      state.blendBg=false;g.scroll=g.scrollPrev=100;
      const calls=[],draw=ctx.drawImage.bind(ctx);
      ctx.drawImage=(...args)=>{calls.push(args);draw(...args);};
      const r={...template,id:'motion-fixture',ordinal:999999,x:100.2,y:80.2};
      g.bobPrev.byKey.set(smoothBobKey(r),{x:100,y:80});
      g.frac=TICK*.75;renderSmoothField(ctx,g,4,{ordered:[r]},null);
      const last=calls.at(-1);
      check(last[1]===Math.round((100.15+r.spr.ox)*4)/4,'BOB endpoint was floored');
      check(last[2]===Math.round((180.15+r.spr.oy)*4)/4-100,'BOB Y endpoint was floored');
      const plane=new Uint8Array(HUD_STRIDE*HUD_ROWS);plane[0]=128;
      const overlay=hudOverlayCanvas(g,plane,g.tick,false);
      const alpha=overlay.getContext('2d').getImageData(0,0,320,HUD_ROWS).data;
      check(alpha[3]===255&&alpha[7]===0,'HUD must leave terrain transparent');
      g.scroll=900;g.shots=[];g.plops=[];
      const b={x:100.5,y:1000,worldSpace:true,poolSlot:0,frame:14};g.bullets=[b];
      g.hwTick=undefined;g.tick=40;captureSmoothHardware(g);
      g.tick++;b.y=1002;
      const view={lerpOK:true,alpha:.5,scrollF:900,q:v=>v};
      calls.length=0;drawTownHardwareSprites(ctx,g,view);
      const spr=indexedFrameFor(state,'BULLET.LIN',14);
      check(calls.length===1,'HW bolt not visible');
      check(calls[0][1]===100.5+spr.ox&&calls[0][2]===101+spr.oy,'world-space HW interpolation');
      g.bullets=[{...b,y:1020}];calls.length=0;drawTownHardwareSprites(ctx,g,view);
      check(calls[0][2]===120+spr.oy,'recycled slot interpolated unrelated bolt');
      g.tick++;g.bullets[0].worldSpace=false;g.bullets[0].y=120;
      calls.length=0;drawTownHardwareSprites(ctx,g,{...view,lerpOK:false});
      check(calls[0][2]===120+spr.oy,'screen-space or teleport offset');
      ctx.drawImage=draw;
      startGame(0);state.smooth=true;state.g.last=0;state.g.frac=3.1*TICK;frame(0);
      check(state.g.bobPrev.tick===state.g.tick-1,'catch-up lost adjacent BOB tick');
      check(state.g.hwPrev instanceof Map,'catch-up lost HW history');
      document.querySelector('#smoothchk').checked=false;
      document.querySelector('#smoothchk').dispatchEvent(new Event('change'));
      check(!state.g.bobPrev&&!state.g.hwPrev,'mode toggle retained stale history');
      return {blendedFrames:hashes.size,bobFractional:true,hwWorldSpace:true,slotReuse:true,hudTransparent:true,catchUp:true};
    }""")
    assert not errors, errors
    print('Motion OK:', result)
    page.evaluate("""() => {
      startGame(0);state.smooth=true;state.blendBg=true;
      document.querySelector('#smoothchk').checked=true;
      document.querySelector('#blendchk').checked=true;
      for(let i=0;i<180;i++)step(state.g);
      state.g.last=0;state.g.frac=TICK;frame(0);
      state.g.last=0;state.g.frac=TICK*1.5;frame(0);
    }""")
    page.screenshot(path='/tmp/swiv-motion.png')
    assert not errors, errors
    browser.close()
