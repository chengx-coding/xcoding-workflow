import json, os
import numpy as np
from PIL import Image

ROOT = r"C:\dev\xcoding-workflow-dev\wf-iterations\emberdeep-visual-0414\visual\critic-input-0415"
man = json.load(open(os.path.join(ROOT, "manifest.json"), encoding="utf-8"))

def bars(path):
    a = np.asarray(Image.open(os.path.join(ROOT, path)).convert("RGB")).astype(int)
    h, w, _ = a.shape
    lum = a.mean(axis=2)
    darkrow = (lum < 22).mean(axis=1)
    darkcol = (lum < 22).mean(axis=0)
    top = 0
    while top < h and darkrow[top] > 0.98:
        top += 1
    bot = 0
    while bot < h and darkrow[h-1-bot] > 0.98:
        bot += 1
    left = 0
    while left < w and darkcol[left] > 0.98:
        left += 1
    right = 0
    while right < w and darkcol[w-1-right] > 0.98:
        right += 1
    return top, bot, left, right

print("state            viewport     group      T   B   L   R  (dark band px)")
for group in ("baseline", "candidate"):
    for e in man[group]:
        t, b, l, r = bars(e["path"])
        print(f'{e["state"]:<12} {e["viewport"]:<11} {group:<9} {t:4d}{b:4d}{l:4d}{r:4d}')
