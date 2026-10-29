import os
from PIL import Image

d = os.path.dirname(os.path.abspath(__file__))


def crop(src, box, scale, name):
    im = Image.open(os.path.join(d, src)).convert("RGB")
    part = im.crop(box)
    part = part.resize((part.width * scale, part.height * scale), Image.LANCZOS)
    part.save(os.path.join(d, name))
    print(name, part.size)


crop("boot-960.png", (190, 475, 770, 600), 2, "crop-hotbar-960.png")
crop("hover-mine-960.png", (350, 220, 540, 350), 3, "crop-hover-mine-960.png")
crop("hover-place-960.png", (390, 220, 560, 350), 3, "crop-hover-place-960.png")
crop("overlay-960-first.png", (90, 400, 870, 545), 2, "crop-overlay-960-lower.png")
crop("final-1440.png", (400, 740, 1040, 900), 2, "crop-hotbar-1440.png")
crop("hover-place-1440.png", (620, 380, 800, 500), 3, "crop-hover-place-1440.png")
