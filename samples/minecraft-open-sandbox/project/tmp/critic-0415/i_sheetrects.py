import os
import numpy as np
from PIL import Image

ROOT = r"C:\dev\xcoding-workflow-dev\wf-iterations\emberdeep-visual-0414\visual\critic-input-0415"
p = os.path.join(ROOT, "detail/ore-sheet.png")
a = np.asarray(Image.open(p).convert("RGB")).astype(np.int16)
h, w, _ = a.shape
lum = a.mean(axis=2)
mask = lum > 25
cols = mask[:150].mean(axis=0)
rows = mask[:150].mean(axis=1)
def runs(v, thr=0.5):
    out = []
    i = 0
    while i < len(v):
        if v[i] > thr:
            j = i
            while j + 1 < len(v) and v[j + 1] > thr:
                j += 1
            out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out
print("col runs", runs(cols))
print("row runs", runs(rows))
for (x0, x1) in runs(cols):
    sub = a[:, x0:x1+1]
    print("tile col", x0, x1, "w", x1-x0+1)
