import os
import numpy as np
from PIL import Image

ROOT = r"C:\dev\xcoding-workflow-dev\wf-iterations\emberdeep-visual-0414\visual\critic-input-0415"

def load(p):
    return np.asarray(Image.open(os.path.join(ROOT, p)).convert("RGB")).astype(np.int16)

pts = {
    "candidate/1280x800/02-day.png": [(200,100),(400,100),(640,45),(1100,60),(610,760),(520,701),(1240,30),(5,793),(12,12),(320,125)],
    "baseline/1280x800/02-day.png": [(200,100),(400,100),(640,45),(1100,60),(610,760),(520,701),(1240,30),(5,793),(12,12),(320,125)],
}
for p, ps in pts.items():
    a = load(p)
    print("==", p)
    for (x,y) in ps:
        print(f"  ({x},{y}) = {tuple(int(v) for v in a[y,x])}")

# green dot search: find bright green pixels anywhere
for p in ["candidate/1280x800/02-day.png","baseline/1280x800/02-day.png","candidate/800x600/02-day.png"]:
    a = load(p)
    r,g,b = a[:,:,0],a[:,:,1],a[:,:,2]
    m = (g>120)&(r<120)&(b<120)&(g>r+60)&(g>b+40)
    ys,xs = np.where(m)
    print(p, "green pixels:", len(ys), (xs.min(),ys.min(),xs.max(),ys.max()) if len(ys) else None)
