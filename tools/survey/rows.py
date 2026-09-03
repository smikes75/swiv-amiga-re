"""Radek mapy originalnich survey snimku korelaci s renderem mapy (hrube ±240, pak jemne)."""
import sys
sys.path.insert(0,'/Users/mik/claude46/Amiga/SWIV-projekt/tools')
from PIL import Image
from compare import VAMIGA_LUT, CROP, FRAME_SIZE
D='/Users/mik/claude46/Amiga/SWIV-projekt/build/survey'
m=Image.open('/Users/mik/claude46/Amiga/SWIV-projekt/build/maps/0_town.png').convert('RGB')
L=[VAMIGA_LUT[min(15,round(c/17))] for c in range(256)]
mp=m.load(); H=m.size[1]
def orig(t):
    raw=open(f'{D}/orig_t{t}.raw','rb').read(); x,y,w,h=CROP
    return Image.frombytes('RGB',(716,285),raw).crop((x,y,x+w,y+h)).resize(FRAME_SIZE, Image.NEAREST)
def score(po,S,step):
    ok=n=0
    for y in range(20,250,step):
        for x in range(0,320,step):
            a=po[x,y]; b=mp[x,S+y]; n+=1
            if abs(a[0]-L[b[0]])<=8 and abs(a[1]-L[b[1]])<=8 and abs(a[2]-L[b[2]])<=8: ok+=1
    return ok/n
for t in [int(x) for x in sys.argv[1].split(',')]:
    po=orig(t).load(); guess=3249-(50*(t-17)+83)//4
    cands=[(score(po,S,4),S) for S in range(max(0,guess-240),min(H-256,guess+240),4)]
    cands.sort(reverse=True); best=cands[0][1]
    fine=sorted(((score(po,S,2),S) for S in range(max(0,best-6),min(H-256,best+7))), reverse=True)[0]
    print(f't{t}: nominal {guess} zmereno {fine[1]} ({fine[0]*100:.0f} %) delta {fine[1]-guess:+d}')
