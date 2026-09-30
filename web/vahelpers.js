/* Pomocne funkce nad jadrem vAmiga spolecne pro web/vacmp.html (harness)
   a web/hrat.html (hrani a ukladani stavu). Zavesi se na existujici objekt
   VA (potrebuje VA.M = modul wasm a VA.fn s chipPtr/chipSize/slowPtr/
   slowSize/snapshot funkcemi); vse se cte az pri volani. */
window.installVaHelpers = function (VA) {
/* Pamet Amigy jako jeden adresni prostor: chip RAM (0..chipSize) a slow
     RAM (0xC00000..) lezi v halde wasm kazda jinde. `at(a)` prevede amigovskou
     adresu na index do HEAPU8; U/W/L ctou big-endian slovo (bez/se znamenkem)
     a long, `w16` zapisuje slovo. Hra (zavadec, AMPROG, ulohy) lezi ve slow
     RAM, kdyz ji fix wrapperu najde (VA.patchFixScan), jinak v chip RAM. */
    VA.mem = function () {
    const H = VA.M.HEAPU8, p = VA.fn.chipPtr(), cs = VA.fn.chipSize();
    const q = VA.fn.slowPtr() - 0xc00000, ss = VA.fn.slowSize();
    const at = a => a < cs ? p + a : (a >= 0xc00000 && a < 0xc00000 + ss ? q + a : -1);
    const rd = a => { const i = at(a); return i < 0 ? 0 : H[i]; };
    const U = a => (rd(a) << 8) | rd(a + 1);
    return { H, p, cs, at, rd, U,
      W: a => { const v = U(a); return v > 0x7fff ? v - 0x10000 : v; },
      L: a => ((rd(a) << 24) | (rd(a + 1) << 16) | (rd(a + 2) << 8) | rd(a + 3)) >>> 0,
      w8: (a, v) => { const i = at(a); if (i >= 0) H[i] = v & 255; },
      w16: (a, v) => { const i = at(a); if (i >= 0) { H[i] = (v >> 8) & 255; H[i + 1] = v & 255; } },
      platna: a => at(a) >= 0 };
  };
  
  /* Kde lezi zavadec hry a AMPROG.OBJ. Zavadeci blok (7 424 B) poznam podle
     `lea 0x17dc-ish(pc),a6` na jeho offsetu 0xe6; A6 = blok + 0x16dc, AMPROG
     je ve fp@(-1402). V chip rozvrzeni (fix nenasel slow RAM) je blok na
     0x100 -> A6 0x17dc, AMPROG 0xefc0; ve slow rozvrzeni blok na 0xc00000 ->
     A6 0xc016dc, AMPROG 0xc0a4c0. */
    VA.layout = function () {
    const m = VA.mem();
    const sig = [0x4d, 0xfa, 0x15, 0xf4, 0x2d, 0x48, 0xfa, 0x86];
    const hledej = (od, do_) => {
      for (let a = od; a < do_ - 8; a += 2) {
        let ok = true;
        for (let i = 0; i < 8; i++) if (m.rd(a + i) !== sig[i]) { ok = false; break; }
        if (ok) return a - 0xe6;
      }
      return -1;
    };
    let blok = hledej(0, Math.min(m.cs, 0x20000));
    if (blok < 0 && VA.fn.slowSize()) blok = hledej(0xc00000, 0xc00000 + 0x4000);
    if (blok < 0) blok = hledej(0, m.cs);
    if (blok < 0) return null;
    const a6 = blok + 0x16dc;
    return { blok, a6, prog: m.L(a6 - 1402), slow: blok >= 0xc00000 };
  };
  
  /* Fix wrapper (N.O.M.A.D, blok 0x50000 z bootbloku) sonduje pamet po 512 kB
     pres TypeOfMem, ale smycka na 0x5019a konci uz na 0x80000, takze najde jen
     chip RAM; zavadec pak nikdy nedostane slow RAM, prestoze s ni pocita
     (typ 5 prednostne, trainer patchuje 0xC11500 = AMPROG 0xC0A4C0 + 0x7040).
     Zaplata posune mez na 16 MB. Vola se po nacteni bootbloku (~10 s), pred
     startem wrapperu (po cracktru). Vraci true, kdyz nasla puvodni bajty. */
    VA.patchFixScan = function () {
    const H = VA.M.HEAPU8, p = VA.fn.chipPtr(), a = p + 0x5019a;
    const puvodni = H[a] === 0x00 && H[a + 1] === 0x08 && H[a + 2] === 0 && H[a + 3] === 0 &&
                    H[a - 2] === 0xb9 && H[a - 1] === 0xfc;
    if (puvodni) { H[a] = 0x01; H[a + 1] = 0x00; }
    return puvodni;
  };

  /* Nahraje pole bajtu do haldy modulu a vrati ukazatel (volajici uvolni). */
  VA.toHeap = function (b64) {
    const bin = atob(b64), n = bin.length;
    const p = VA.M._malloc(n);
    const H = VA.M.HEAPU8;
    for (let i = 0; i < n; i++) H[p + i] = bin.charCodeAt(i);
    return [p, n];
  };

  /* Obnovi stav ze snapshotu jadra (web/hrat.html, tools/hrat.py). Jadro uz
     musi byt zapnute. */
  VA.loadSnapshot = function (b64) {
    const [p, n] = VA.toHeap(b64);
    const r = VA.fn.snapLoad(p, n);
    VA.M._free(p);
    return r === 0 ? '' : 'snapshot: ' + VA.fn.err();
  };
};
