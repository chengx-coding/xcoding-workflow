import json, os
import numpy as np
from PIL import Image

ROOT = r"C:\dev\xcoding-workflow-dev\wf-iterations\emberdeep-visual-0414\visual\critic-input-0415"

def load(p):
    return np.asarray(Image.open(os.path.join(ROOT, p)).convert("RGB")).astype(np.int16)

def col(a, x, y):
    return tuple(int(v) for v in a[y, x])

for p in ["candidate/1280x800/02-day.png", "baseline/1280x800/02-day.png",
          "candidate/800x600/02-day.png", "baseline/800x600/02-day.png"]:
    a = load(p)
    print("==", p, a.shape)
    # trunk guesses
    print("  sample colors:", [(xy, col(a, *xy)) for xy in [(640, 400), (640, 500), (100, 500), (640, 760), (5, 785)]])

# find trunk: look for columns with wood color over a vertical run in the sky region
def trunk_scan(p, y0, y1):
    a = load(p)
    h, w, _ = a.shape
    # wood trunk colors: r>80, r>g*1.2, g>b, spread; sample baseline trunk
    band = a[y0:y1]
    # dominant color in band excluding sky: compute per-column count of "brown" pixels
    r, g, b = band[:, :, 0], band[:, :, 1], band[:, :, 2]
    brown = (r > 70) & (r < 180) & (g > 40) & (g < 130) & (b < 100) & (r > g + 15) & (g > b)
    counts = brown.sum(axis=0)
    runs = []
    x = 0
    while x < w:
        if counts[x] > (y1 - y0) * 0.6:
            x2 = x
            while x2 + 1 < w and counts[x2 + 1] > (y1 - y0) * 0.6:
                x2 += 1
            runs.append((x, x2, x2 - x + 1))
            x = x2 + 1
        else:
            x += 1
    return runs, counts

for p in ["candidate/1280x800/02-day.png", "baseline/1280x800/02-day.png",
          "candidate/800x600/02-day.png", "baseline/800x600/02-day.png",
          "candidate/960x600/02-day.png"]:
    runs, counts = trunk_scan(p, 300, 380)
    print(p, "trunk runs y300-380:", runs)
