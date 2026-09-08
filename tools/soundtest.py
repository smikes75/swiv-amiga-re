#!/usr/bin/env python3
"""Later SFX: independent period oracle, live hooks, IRQs and real stereo PCM."""
from playwright.sync_api import sync_playwright
from displaytest import load_game


def signed(v):
    v &= 65535
    return v - 65536 if v & 32768 else v


def pulse(count, base, delta):
    result = []
    for volume in range(count, 0, -1):
        result.append([64 if volume & 64 else volume & 63, signed(base + delta)])
        base = signed(base + (base >> 5))
        delta = -delta
    return result


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    load_game(page)
    result = page.evaluate("""async () => {
      const saved=actx;actx=null;
      const check=(ok,msg)=>{if(!ok)throw Error(msg);};
      const fresh=()=>({tick:0,rngState:0x12345678,rngVhposWord:0,sfx:createTownSfxState(),
        nextBobOrdinal:1,activeCost:0,scroll:1000,player:{x:160,y:160},
        shots:[],hazards:[],spawns:[],air:[],plops:[],booms:[],effects:[]});
      const pairs=a=>a.map(s=>[s.volume,s.period]);
      try {
        const bomb=sfxBombTimeline(),hatch=sfxHatchTimeline(),pod=sfxInstShotTimeline(20,200),beam=sfxInstShotTimeline(50,500),ping=sfxBoltPingTimeline();
        check(JSON.stringify(pairs(pod))===JSON.stringify(pairs(sfxEggShotTimeline())),'local EGGS sweep differs');
        const g=fresh();sfxInstShot(g,40,50,500);
        const voices=g.sfx.voices.filter(v=>v.effect);
        check(JSON.stringify(voices.map(v=>v.effect.end))==='[128,136]','laser cleanup IRQs');
        for(let i=0;i<2;i++)advanceTownSfxIrq(g);
        check(voices[0].scratch[0]===127&&voices[1].scratch[0]===0,'first laser onset');
        for(let i=2;i<10;i++)advanceTownSfxIrq(g);
        check(voices[1].scratch[0]===127,'delayed laser onset');
        for(let i=10;i<136;i++)advanceTownSfxIrq(g);
        check(voices.every(v=>!v.effect&&v.guard===0),'laser cleanup');
        const hit=fresh();sfxInstallationHit(hit);
        const hv=hit.sfx.voices.filter(v=>v.effect),seed=hit.rngState;
        advanceTownSfxIrq(hit);check(hit.rngState===seed,'installation seeded too early');
        advanceTownSfxIrq(hit);check(hv.every(v=>v.effect.dynamic.lastPeriod===400),'installation period/RNG onset');
        const blocked=fresh();for(const v of blocked.sfx.voices)v.guard=10000;
        sfxInstallationHit(blocked);advanceTownSfxIrq(blocked);advanceTownSfxIrq(blocked);
        check(blocked.rngState===seed,'rejected installation consumed RNG');
        const preempt=fresh();sfxInstallationHit(preempt);sfxInstShot(preempt,40,50,500);sfxInstShot(preempt,320,50,500);
        advanceTownSfxIrq(preempt);advanceTownSfxIrq(preempt);check(preempt.rngState===seed,'preempted hit consumed RNG');
        const hook=fresh();spawnXevBomb(hook,{x:80,y:1120});check(hook.sfx.events[0].kind==='xev-bomb','bomb hook');
        hook.sfx=createTownSfxState();
        const roof={alive:true,hp:9,x:80,boltPing:true};dispatchTownShotEvent(hook,{kind:'spawn',o:roof});
        check(roof.hp===9&&hook.sfx.events[0].kind==='bolt-ping','armour ping must not damage');
        for(const beh of ['factory','inst2','inst3','inst4core']){
          hook.sfx=createTownSfxState();damageSpawn(hook,{alive:true,hp:3,x:80,beh});
          check(hook.sfx.events.length===2&&hook.sfx.events.every(e=>e.kind.startsWith('inst-hit')),'installation hit hook '+beh);
        }
        hook.sfx=createTownSfxState();
        advanceTownHazardField(hook,{kind:'platturret',alive:true,dead:false,parent:{alive:true,x:80,y:1120},ox:11,st:1,t:1,seq:[19],apos:0,at:0,per:8});
        check(hook.sfx.events[0].kind==='plat-hatch','hatch firing hook');
        const pcm=[bomb,hatch,pod,beam,ping].map(s=>{
          const a=sfxRenderTimeline(s,48000);let peak=0;for(const n of a){check(Number.isFinite(n),'nonfinite PCM');peak=Math.max(peak,Math.abs(n));}
          check(peak>0&&peak<=1,'silent/clipped mono PCM');return {samples:a.length,peak};
        });
        const stereo=[];
        for(const x of [40,240]){
          const context=new OfflineAudioContext(2,48000,48000);actx=context;
          sfxInstShot(fresh(),x,50,500);
          const buffer=await context.startRendering();
          const stats=[0,1].map(ch=>{const a=buffer.getChannelData(ch);let energy=0,peak=0,first=-1;for(let i=0;i<a.length;i++){energy+=a[i]*a[i];peak=Math.max(peak,Math.abs(a[i]));if(first<0&&Math.abs(a[i])>1e-6)first=i;}return {energy,peak,first};});
          const main=x<160?0:1;check(stats[main].energy>0&&stats[1-main].energy<1e-12,'stereo allocation');
          check(stats[main].peak<1&&stats[main].first>=468&&stats[main].first<=470,'PCM onset or clipping');
          stereo.push(stats);
        }
        const tokenPlayback=[];
        for(const rate of [44100,48000]) {
          const context=new OfflineAudioContext(2,rate,rate);actx=context;
          const voice=sfxTokenPickupNote(fresh(),40,159);
          check(voice.source.buffer===sfxTimelineBuffer(sfxTokenPickupTimeline(159),'token-pickup-5672-159',true),'TOKEN must use bandlimited cache');
          const buffer=await context.startRendering();
          let peak=0,energy=0,other=0;
          for(let i=0;i<rate;i++){
            const x=buffer.getChannelData(0)[i],y=buffer.getChannelData(1)[i];
            check(Number.isFinite(x)&&Number.isFinite(y),'TOKEN nonfinite output');
            peak=Math.max(peak,Math.abs(x));energy+=x*x;other+=y*y;
          }
          check(energy>0&&peak<1&&other<1e-12,'TOKEN audible/stereo/no clipping');
          tokenPlayback.push({rate,peak,energy});
        }
        const alias=[];
        for(const rate of [44100,48000,96000]) {
          const wave=[{wave:new Int8Array([127,-128]),volume:64,period:141,length:2,ticks:60}];
          const old=sfxRenderTimeline(wave,rate),clean=sfxRenderBandlimitedTimeline(wave,rate);
          const amplitude=(a,f)=>{let re=0,im=0;const n=a.length-256;for(let i=128;i<a.length-128;i++){re+=a[i]*Math.cos(2*Math.PI*f*i/rate);im+=a[i]*Math.sin(2*Math.PI*f*i/rate);}return 2*Math.hypot(re,im)/n;};
          const fundamental=PAULA_CLOCK/141/2;
          const harmonic=rate===96000?5:3;
          const folded=Math.abs(rate-harmonic*fundamental);
          const before=amplitude(old,folded),after=amplitude(clean,folded);
          check(clean.length===old.length&&clean.every(Number.isFinite),'resampler duration/finite');
          check(after<before*0.2,'resampler alias rejection '+rate+' '+before+' '+after);
          const ratio=amplitude(clean,fundamental)/amplitude(old,fundamental);
          check(ratio>0.9&&ratio<1.1,'resampler changed fundamental');
          for(const period of [159,212,141]){
            const tone=sfxTokenPickupTimeline(period);
            const pcm=sfxRenderBandlimitedTimeline(tone,rate);
            check(pcm.length===sfxRenderTimeline(tone,rate).length&&pcm.every(Number.isFinite),'TOKEN resampling');
          }
          alias.push({rate,before,after,ratio});
        }
        const boss=[200,202].map(base=>sfxBossDeathTimeline(base).map(s=>[s.volume,s.period,s.ticks]));
        const token=sfxTokenPickupTimeline(159).map(s=>[s.volume,s.period,s.ticks,Array.from(s.wave)]);
        return {tokenPlayback,alias,boss,token,bomb:pairs(bomb),hatch:pairs(hatch),pod:pairs(pod),beam:pairs(beam),ping:pairs(ping),wave:Array.from(bomb[0].wave),pcm,stereo};
      } finally {actx=saved;}
    }""")
    assert result['bomb'] == [[v, 250 + (48-v)*3 + (((~v if v & 4 else v) & 3) << 5)] for v in range(48, 0, -1)]
    assert result['hatch'] == [[48, p] for p in range(800, 499, -20)]
    assert result['pod'] == pulse(48, 200, 20)
    assert result['beam'] == pulse(126, 500, 50)
    assert result['ping'] == [[64, 300], [64, 500], [64, 700]]
    assert result['wave'] == [0,32,64,96,127,96,64,32,0,-32,-64,-96,-128,-96,-64,-32]
    # 0x5580 writes AUDVOL once per pair. NEG at 0x5594 only affects
    # the period calculation; it must NOT turn the second half up to 64.
    for base, actual in zip([200, 202], result['boss']):
        expected = []
        for volume in range(32, 0, -1):
            expected.extend([[volume, base + volume*4, 3],
                             [volume, base - volume*4, 3]])
        assert actual == expected, (base, actual)
    # Independent byte arithmetic from table 0x56c6 and loop 0x5696.
    table = [8, 24, 40, 56, -56, -40, -24, -8] * 2
    assert result['token'] == [
        [volume, 159, 2, [(table[i]-table[i+((volume & 31) >> 2)]) & 255
                         for i in range(8)]]
        for volume in range(64, 0, -1)]
    assert not errors, errors
    print('TOWN OK: both boss volume/period envelopes and complete token waveform sequence match disassembly.')
    print('Resampling alias rejection:', result['alias'])
    print('TOKEN playback:', result['tokenPlayback'])
    print('Sound OK: full period/volume sequences, existing EGGS parity, IRQ delay/cleanup, deferred RNG/reject/preemption, bomb/hatch/ping/hit hooks, finite PCM and offline stereo/onset/no clipping.')
    print('PCM:', result['pcm'], 'Stereo:', result['stereo'])
    browser.close()
