import os
import numpy as np
from PIL import Image

ROOT = r"C:\dev\xcoding-workflow-dev\wf-iterations\emberdeep-visual-0414\visual\critic-input-0415"

def load(p):
    return np.asarray(Image.open(os.path.join(ROOT, p)).convert("RGB")).astype(int)

def bbox_dark_rect(a, region, thr=48, rowfrac=0.4, colfrac=0.3):
    x0, y0, x1, y1 = region
    sub = a[y0:y1, x0:x1]
    lum = sub.mean(axis=2)
    dark = lum < thr
    rows = dark.sum(axis=1)
    cols = dark.sum(axis=0)
    ry = np.where(rows > (x1 - x0) * rowfrac)[0]
    cx = np.where(cols > (y1 - y0) * colfrac)[0]
    if len(ry) == 0 or len(cx) == 0:
        return None
    return (x0 + int(cx.min()), y0 + int(ry.min()), x0 + int(cx.max()), y0 + int(ry.max()))

def red_bbox(a, region):
    x0, y0, x1, y1 = region
    sub = a[y0:y1, x0:x1]
    r, g, b = sub[:,:,0], sub[:,:,1], sub[:,:,2]
    m = (r > 140) & (g < 110) & (b < 120) & (r > g + 60)
    ys, xs = np.where(m)
    if not len(ys):
        return None
    return (x0 + int(xs.min()), y0 + int(ys.min()), x0 + int(xs.max()), y0 + int(ys.max())), len(ys)

def gold_bbox(a, region):
    x0, y0, x1, y1 = region
    sub = a[y0:y1, x0:x1]
    r, g, b = sub[:,:,0], sub[:,:,1], sub[:,:,2]
    m = (r > 120) & (r < 245) & (g > 90) & (g < 210) & (b < 140) & (r > g + 25) & (g > b + 15)
    ys, xs = np.where(m)
    if not len(ys):
        return None
    return (x0 + int(xs.min()), y0 + int(ys.min()), x0 + int(xs.max()), y0 + int(ys.max())), len(ys)

for vp in ["1280x800", "960x600", "800x600"]:
    p = f"candidate/{vp}/02-day.png"
    a = load(p)
    h, w, _ = a.shape
    print("==", vp, w, h)
    jr = bbox_dark_rect(a, (0, 0, min(420, w), 200))
    print("  journey card bbox", jr, "size", (jr[2]-jr[0]+1, jr[3]-jr[1]+1) if jr else None, "margins L/T", (jr[0], jr[1]) if jr else None)
    dc = bbox_dark_rect(a, (w//2-200, 0, w//2+200, 120), thr=45)
    print("  day chip bbox", dc, "size", (dc[2]-dc[0]+1, dc[3]-dc[1]+1) if dc else None)
    mm = bbox_dark_rect(a, (w-330, 0, w, 230), thr=40)
    print("  minimap bbox", mm, "size", (mm[2]-mm[0]+1, mm[3]-mm[1]+1) if mm else None, "right margin", w-1-mm[2] if mm else None)
    hb = red_bbox(a, (0, h-160, w, h-40))
    print("  hearts bbox", hb, "size", (hb[0][2]-hb[0][0]+1, hb[0][3]-hb[0][1]+1) if hb else None)
    gb = gold_bbox(a, (w//2-320, h-120, w//2+320, h-10))
    print("  hotbar gold bbox", gb)
    # hotbar slot border color sample from selected slot area: find near-horizontal 1px lines
    print("  bottom margin of hotbar (panel bottom):", )
