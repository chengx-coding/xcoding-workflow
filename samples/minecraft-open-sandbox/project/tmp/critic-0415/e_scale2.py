import os
import numpy as np
from PIL import Image

ROOT = r"C:\dev\xcoding-workflow-dev\wf-iterations\emberdeep-visual-0414\visual\critic-input-0415"

def load(p):
    return np.asarray(Image.open(os.path.join(ROOT, p)).convert("RGB")).astype(np.int16)

def trunk_runs(p, y0, y1, frac=0.5):
    a = load(p)
    h, w, _ = a.shape
    band = a[y0:y1]
    r, g, b = band[:, :, 0], band[:, :, 1], band[:, :, 2]
    brown = (r > 70) & (r < 190) & (g > 40) & (g < 140) & (b < 110) & (r > g + 15) & (g > b)
    counts = brown.sum(axis=0)
    runs = []
    x = 0
    while x < w:
        if counts[x] > (y1 - y0) * frac:
            x2 = x
            while x2 + 1 < w and counts[x2 + 1] > (y1 - y0) * frac:
                x2 += 1
            runs.append((x, x2, x2 - x + 1))
            x = x2 + 1
        else:
            x += 1
    return runs

print("== trunk runs (sky band, above ground)")
for p, y0, y1 in [
    ("candidate/1280x800/02-day.png", 300, 400),
    ("baseline/1280x800/02-day.png", 300, 400),
    ("candidate/960x600/02-day.png", 200, 290),
    ("baseline/960x600/02-day.png", 200, 290),
    ("candidate/800x600/02-day.png", 220, 300),
    ("baseline/800x600/02-day.png", 220, 300),
]:
    print(p, trunk_runs(p, y0, y1))

# vertical block period: grass surface row and dirt band thickness at several x
def surface_profile(p, xs):
    a = load(p)
    h, w, _ = a.shape
    r, g, b = a[:,:,0], a[:,:,1], a[:,:,2]
    green = (g > 60) & (g > r + 10) & (g > b + 10)
    prof = []
    for x in xs:
        col = green[:, x]
        idx = np.where(col)[0]
        prof.append(int(idx.min()) if len(idx) else -1)
    return prof

for p in ["candidate/1280x800/02-day.png", "baseline/1280x800/02-day.png",
          "candidate/960x600/02-day.png", "candidate/800x600/02-day.png"]:
    a = load(p)
    w = a.shape[1]
    xs = list(range(0, w, 8))
    prof = surface_profile(p, xs)
    # print transitions (unique runs) as step widths
    runs = []
    prev = None
    for i, v in enumerate(prof):
        if v != prev:
            runs.append((xs[i], v))
            prev = v
    print("== surface steps", p, len(runs))
    print("  ", runs[:40])
