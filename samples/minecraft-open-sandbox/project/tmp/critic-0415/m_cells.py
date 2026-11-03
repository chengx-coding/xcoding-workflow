import os
import numpy as np
from PIL import Image
from collections import deque

ROOT = r"C:\dev\xcoding-workflow-dev\wf-iterations\emberdeep-visual-0414\visual\critic-input-0415"
a = np.asarray(Image.open(os.path.join(ROOT, "detail/ore-sheet.png")).convert("RGB")).astype(int)
tiles = {"coal": 15, "iron": 161, "ember": 307, "stone": 453, "cobble": 599}

def components(mask, minsize=15):
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    for y in range(h):
        for x in range(w):
            if mask[y, x] and not seen[y, x]:
                q = deque([(y, x)]); seen[y, x] = True; pts = []
                while q:
                    cy, cx = q.popleft(); pts.append((cy, cx))
                    for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
                        ny, nx = cy+dy, cx+dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True; q.append((ny, nx))
                if len(pts) >= minsize:
                    ys = [p[0] for p in pts]; xs = [p[1] for p in pts]
                    out.append((len(pts), min(xs), min(ys), max(xs)-min(xs)+1, max(ys)-min(ys)+1))
    return out

for name, x0 in tiles.items():
    tex = a[28:140, x0+9:x0+121]
    mx = tex.max(axis=2); mn = tex.min(axis=2)
    lum = tex.mean(axis=2)
    # glint: very bright pixels, small clusters
    glint = lum > 185
    comps = components(glint, 20)
    # mineral fill masks
    r, g, b = tex[:,:,0], tex[:,:,1], tex[:,:,2]
    if name == "coal":
        minmask = (lum < 30)
    elif name == "iron":
        minmask = (r > 170) & (g > 110) & (g < 200) & (b < 165) & (r > b + 40)
    elif name == "ember":
        minmask = (r > 150) & (r > g + 60) & (g < 140) & (b < 110)
    else:
        minmask = np.zeros_like(glint)
    mcomps = components(minmask, 60) if name in ("coal", "iron", "ember") else []
    print(f"== {name}: glint clusters={len(comps)} sizes={[c[0] for c in comps]}")
    print(f"   mineral blobs={len(mcomps)} sizes={[c[0] for c in mcomps]} bbox={[(c[1],c[2],c[3],c[4]) for c in mcomps]}")
    if name in ("coal", "iron", "ember"):
        print(f"   cell count (mineral blobs) = {len(mcomps)}, glints = {len(comps)}")
