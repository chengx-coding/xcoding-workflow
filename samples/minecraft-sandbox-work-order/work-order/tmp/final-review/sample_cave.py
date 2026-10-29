import os
from PIL import Image

d = os.path.dirname(os.path.abspath(__file__))
im = Image.open(os.path.join(d, "final-1440.png")).convert("RGB")
w, h = im.size
print("size", w, h)
im.crop((0, 640, 420, 900)).resize((840, 520)).save(os.path.join(d, "crop-1440-bl.png"))
im.crop((1000, 620, 1440, 900)).resize((880, 560)).save(os.path.join(d, "crop-1440-br.png"))
points = [(5, 895), (40, 860), (80, 895), (120, 880), (260, 850), (300, 895),
          (10, 820), (15, 790), (35, 745), (300, 730), (20, 700), (390, 730)]
for xy in points:
    print(xy, im.getpixel(xy))
count = 0
for y in range(650, 900):
    for x in range(0, 420):
        p = im.getpixel((x, y))
        if max(p) < 12:
            count += 1
print("near-black(<12) count in 420x250 bottom-left:", count)
