"""Dvojice original|prepis pro snimky uz v DESERTu: radek korelaci s
1_desert.png, prevod na tik retezene mapy, simulace prepisu, montaz."""
import sys, subprocess
sys.path.insert(0, '/Users/mik/claude46/Amiga/SWIV-projekt/tools')
from PIL import Image
from compare import VAMIGA_LUT, CROP, FRAME_SIZE
D = '/Users/mik/claude46/Amiga/SWIV-projekt/build/survey'
L = [VAMIGA_LUT[min(15, round(c / 17))] for c in range(256)]
md = Image.open('/Users/mik/claude46/Amiga/SWIV-projekt/build/maps/1_desert.png').convert('RGB')
mp = md.load(); Hd = md.size[1]
H = 26854; M = 160; START = H + M - 256 - 96; BASE_DESERT = 3216
def orig(t):
    raw = open(f'{D}/orig_t{t}.raw', 'rb').read(); x, y, w, h = CROP
    return Image.frombytes('RGB', (716, 285), raw).crop((x, y, x + w, y + h)).resize(FRAME_SIZE, Image.NEAREST)
def score(po, S, st):
    ok = n = 0
    for y in range(20, 250, st):
        for x in range(0, 320, st):
            a = po[x, y]; b = mp[x, S + y]; n += 1
            if abs(a[0] - L[b[0]]) <= 8 and abs(a[1] - L[b[1]]) <= 8 and abs(a[2] - L[b[2]]) <= 8: ok += 1
    return ok / n
def best(po, lo, hi):
    c = sorted(((score(po, S, 8), S) for S in range(lo, hi, 8)), reverse=True)[0]
    return sorted(((score(po, S, 2), S) for S in range(max(lo, c[1] - 10), min(hi, c[1] + 11))), reverse=True)[0]
ts = [int(x) for x in sys.argv[1].split(',')]
hint = int(sys.argv[2]) if len(sys.argv) > 2 else None   # ocekavany DESERT radek prvniho t (zuzi hledani)
pairs = []
for t in ts:
    po = orig(t).load()
    lo, hi = (max(0, hint - 400), min(Hd - 256, hint + 400)) if hint else (0, Hd - 256)
    s, row = best(po, lo, hi)
    yd = Hd - 256 - row + 256 - 160          # y v DESERT souradnicich zaznamu: img = 5872+160-y
    y = 5872 + 160 - row
    img = H + M - (BASE_DESERT + y)
    T = 4 * (START - img)
    print(f't{t}: DESERT radek {row} ({s*100:.0f} %) -> T {T}')
    pairs.append(f'{t}:{T}')
    if hint: hint = row - 100   # dalsi snimek je ~100 px dal (8 s)
spec = ','.join(pairs)
subprocess.run([sys.executable, D.replace('build/survey', 'tools/survey') + '/survey_remake.py', spec], capture_output=True)
subprocess.run([sys.executable, D.replace('build/survey', 'tools/survey') + '/montage.py', ','.join(p.split(':')[0] for p in pairs), D], capture_output=True)
print('done')
