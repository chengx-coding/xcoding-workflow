import json, os
import numpy as np
from PIL import Image

ROOT = r"C:\dev\xcoding-workflow-dev\wf-iterations\emberdeep-visual-0414\visual\critic-input-0415"
man = json.load(open(os.path.join(ROOT, "manifest.json"), encoding="utf-8"))

def analyze(path):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    h, w, _ = a.shape
    black = np.all(a <= 1, axis=2)
    # bbox of non-black
    nz = np.argwhere(~black)
    bbox = None
    if len(nz):
        ys, xs = nz[:, 0], nz[:, 1]
        bbox = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    # row/col pure black fractions at edges
    def frac_black_rows():
        return [round(float(black[i].mean()), 2) for i in range(min(6, h))], [round(float(black[h-1-i].mean()), 2) for i in range(min(6, h))]
    # dominant color per edge row
    return dict(size=(w, h), nonblack_bbox=bbox, black_px=int(black.sum()),
                top_rows=frac_black_rows()[0], bottom_rows=frac_black_rows()[1])

for group in ("candidate", "baseline"):
    print("=" * 8, group)
    for e in man[group]:
        r = analyze(os.path.join(ROOT, e["path"]))
        print(f'{e["viewport"]:>9} {e["state"]:<11} {str(r["size"]):<12} bbox={r["nonblack_bbox"]} black={r["black_px"]}')
