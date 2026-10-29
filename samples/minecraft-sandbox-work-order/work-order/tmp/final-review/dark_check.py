import os
from PIL import Image

d = os.path.dirname(os.path.abspath(__file__))
for name in ("final-1440.png", "final-960.png"):
    im = Image.open(os.path.join(d, name)).convert("RGB")
    w, h = im.size
    dark = []
    for y in range(h):
        for x in range(w):
            p = im.getpixel((x, y))
            if max(p) <= 8:
                dark.append((x, y, p))
    print(name, "pixels max<=8:", len(dark), dark[:10])
    # bottom-left 300x150 min/max/mean
    box = im.crop((0, h - 150, 300, h))
    px = list(box.getdata())
    print(" bottom-left min", min(px), "max", max(px), "mean", tuple(round(sum(c[i] for c in px) / len(px), 1) for i in range(3)))
