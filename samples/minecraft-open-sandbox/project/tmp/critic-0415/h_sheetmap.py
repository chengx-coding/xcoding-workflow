import os
import numpy as np
from PIL import Image

ROOT = r"C:\dev\xcoding-workflow-dev\wf-iterations\emberdeep-visual-0414\visual\critic-input-0415"
p = os.path.join(ROOT, "detail/ore-sheet.png")
a = np.asarray(Image.open(p).convert("RGB")).astype(np.int16)
h, w, _ = a.shape
print("sheet", w, h)
# find dark panel borders: rows/cols with many pixels brighter than bg but grayish
lum = a.mean(axis=2)
# print a coarse ascii map of luminance to locate tiles
step = 8
chars = " .:-=+*#%@"
for y in range(0, h, 12):
    line = ""
    for x in range(0, w, 8):
        v = lum[y:y+12, x:x+8].mean()
        line += chars[min(9, int(v / 26))]
    print(f"{y:3d} {line}")
