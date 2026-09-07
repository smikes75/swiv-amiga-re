import sys
sys.path.insert(0,'/Users/mik/claude46/Amiga/SWIV-projekt/tools')
from PIL import Image
from compare import VAMIGA_LUT
SC='/Users/mik/claude46/Amiga/SWIV-projekt/build/survey'
t=int(sys.argv[1]); S=int(sys.argv[2])
m=Image.open('/Users/mik/claude46/Amiga/SWIV-projekt/build/maps/0_town.png').convert('RGB').crop((0,S,320,S+256))
o=Image.open(f'{SC}/base/orig_t{t}_crop.png').convert('RGB')
pm=m.load(); po=o.load()
L=lambda c: VAMIGA_LUT[min(15,round(c/17))]
mask=[[0]*320 for _ in range(256)]
for y in range(18,256):
    for x in range(320):
        a=po[x,y]; b=tuple(L(c) for c in pm[x,y])
        if max(abs(a[i]-b[i]) for i in range(3))>8: mask[y][x]=1
seen=[[0]*320 for _ in range(256)]; blobs=[]
for y in range(256):
    for x in range(320):
        if mask[y][x] and not seen[y][x]:
            st=[(x,y)]; seen[y][x]=1; pts=[]
            while st:
                cx,cy=st.pop(); pts.append((cx,cy))
                for dy in range(-2,3):
                    for dx in range(-2,3):
                        nx,ny=cx+dx,cy+dy
                        if 0<=nx<320 and 0<=ny<256 and mask[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx]=1; st.append((nx,ny))
            if len(pts)>=25:
                xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
                blobs.append((min(xs),min(ys),max(xs),max(ys),len(pts)))
for b in sorted(blobs,key=lambda b:(b[1],b[0])): print('blob x%d-%d y%d-%d n=%d'%b)
