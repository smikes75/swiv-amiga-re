"""Dvojice original|prepis pro casy t, dve dvojice na obrazek (640x512)."""
import sys, os
sys.path.insert(0,'/Users/mik/claude46/Amiga/SWIV-projekt/tools')
from PIL import Image, ImageDraw
from compare import CROP, FRAME_SIZE
D='/Users/mik/claude46/Amiga/SWIV-projekt/build/survey'
TS=[int(x) for x in sys.argv[1].split(',')]
OUT=sys.argv[2] if len(sys.argv)>2 else D
def orig(t):
    raw=open(f'{D}/orig_t{t}.raw','rb').read(); x,y,w,h=CROP
    return Image.frombytes('RGB',(716,285),raw).crop((x,y,x+w,y+h)).resize(FRAME_SIZE, Image.NEAREST)
pairs=[]
for t in TS:
    if not os.path.exists(f'{D}/orig_t{t}.raw') or not os.path.exists(f'{D}/remake_t{t}.png'): continue
    o=orig(t); r=Image.open(f'{D}/remake_t{t}.png').convert('RGB')
    row=Image.new('RGB',(644,256),(40,40,40)); row.paste(o,(0,0)); row.paste(r,(324,0))
    d=ImageDraw.Draw(row); d.rectangle((0,0,60,10),fill=(0,0,0)); d.text((2,0),f't{t} orig | prepis',fill=(255,255,0))
    pairs.append((t,row))
for i in range(0,len(pairs),2):
    grp=pairs[i:i+2]; img=Image.new('RGB',(644,256*len(grp)+4*(len(grp)-1)),(40,40,40))
    for k,(t,row) in enumerate(grp): img.paste(row,(0,k*260))
    name=f'{OUT}/pair_t{grp[0][0]}.png'; img.save(name); print(name)
