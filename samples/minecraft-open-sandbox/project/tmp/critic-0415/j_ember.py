import os
import numpy as np
from PIL import Image
from collections import Counter

ROOT = r"C:\dev\xcoding-workflow-dev\wf-iterations\emberdeep-visual-0414\visual\critic-input-0415"

def load(p):
    return np.asarray(Image.open(os.path.join(ROOT, p)).convert("RGB")).astype(int)

def find_orange(p, hide=None):
    a = load(p)
    r, g, b = a[:,:,0], a[:,:,1], a[:,:,2]
    m = (r > 130) & (r > g * 1.6) & (g >= b) & (g < 150)
    if hide:
        for (x0,y0,x1,y1) in hide:
            m[y0:y1, x0:x1] = False
    ys, xs = np.where(m)
    print(p, 'orange px', len(ys))
    if len(ys):
        c = Counter((int(x)//12*12, int(y)//12*12) for x, y in zip(xs, ys))
        print('  clusters:', c.most_common(12))

# hide HUD regions per viewport
find_orange("candidate/1280x800/04-underground.png", [(0,0,340,130),(560,0,800,90),(1020,0,1280,220),(380,690,880,800),(1140,760,1280,800)])
find_orange("candidate/800x600/04-underground.png", [(0,0,260,120),(320,0,520,60),(610,0,800,190),(190,470,600,600),(690,560,800,600)])
find_orange("candidate/1280x800/02-day.png", [(0,0,340,130),(560,0,800,90),(1020,0,1280,220),(380,690,880,800),(1140,760,1280,800)])
find_orange("candidate/800x600/02-day.png", [(0,0,260,120),(320,0,520,60),(610,0,800,190),(190,470,600,600),(690,560,800,600)])
find_orange("candidate/1280x800/03-night.png", [(0,0,340,130),(560,0,800,90),(1020,0,1280,220),(380,690,880,800),(1140,760,1280,800)])
find_orange("baseline/1280x800/04-underground.png", [(0,0,420,160),(560,0,840,140),(900,0,1220,280),(340,660,940,730),(1080,680,1220,730)])
