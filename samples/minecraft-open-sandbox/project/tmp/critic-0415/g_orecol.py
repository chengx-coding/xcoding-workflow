import os
import numpy as np
from PIL import Image

ROOT = r"C:\dev\xcoding-workflow-dev\wf-iterations\emberdeep-visual-0414\visual\critic-input-0415"

def load(p):
    return np.asarray(Image.open(os.path.join(ROOT, p)).convert("RGB")).astype(np.int16)

def stats(p, box):
    a = load(p)
    x0, y0, x1, y1 = box
    sub = a[y0:y1, x0:x1].reshape(-1, 3)
    print("  mean", sub.mean(axis=0).round(1), "max", sub.max(axis=0), "p99", np.percentile(sub, 99, axis=0).round(1))

for p in ["candidate/800x600/04-underground.png", "baseline/800x600/04-underground.png"]:
    print("==", p)
    for name, box in [("stone-mid", (300, 380, 380, 440)),
                      ("stone-deep-left", (40, 200, 120, 260)),
                      ("cave-black", (250, 480, 350, 540)),
                      ("ore-right", (560, 340, 640, 400)),
                      ("ore-ember?", (560, 430, 640, 480)),
                      ("near-torch", (420, 280, 470, 320))]:
        print(" ", name, box)
        stats(p, box)

# hue-based ore search: saturated warm pixels
def warm_pixels(p, region):
    a = load(p)
    r, g, b = a[:, :, 0].astype(float), a[:, :, 1].astype(float), a[:, :, 2].astype(float)
    mx = np.maximum(np.maximum(r, g), b); mn = np.minimum(np.minimum(r, g), b)
    sat = (mx - mn) / np.maximum(mx, 1)
    hue = np.zeros_like(r)
    warm = (r >= g) & (g >= b) & (sat > 0.45) & (mx > 110)
    warm[:region[0], :] = False
    warm[region[1]:, :] = False
    ys, xs = np.where(warm)
    print(p, "warm sat pixels:", len(ys))
    if len(ys):
        # cluster coarsely into 16px cells and report top areas
        from collections import Counter
        c = Counter((int(x) // 16 * 16, int(y) // 16 * 16) for x, y in zip(xs, ys))
        print("  top cells:", c.most_common(14))
    return a, warm

a, warm = warm_pixels("candidate/800x600/04-underground.png", (140, 130))
a2, warm2 = warm_pixels("baseline/800x600/04-underground.png", (90, 130))
