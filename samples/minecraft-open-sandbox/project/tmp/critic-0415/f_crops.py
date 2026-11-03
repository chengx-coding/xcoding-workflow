import os
import numpy as np
from PIL import Image

ROOT = r"C:\dev\xcoding-workflow-dev\wf-iterations\emberdeep-visual-0414\visual\critic-input-0415"
OUT = r"C:\dev\xcoding-workflow-dev\wf-iterations\emberdeep-visual-0414\tmp\critic-0415\crops"
os.makedirs(OUT, exist_ok=True)

def crop(rel, box, name, scale=3):
    im = Image.open(os.path.join(ROOT, rel)).convert("RGB")
    c = im.crop(box)
    c = c.resize((c.width * scale, c.height * scale), Image.NEAREST)
    c.save(os.path.join(OUT, name))
    print(name, c.size)

# hotbar + hearts at each viewport
crop("candidate/1280x800/02-day.png", (380, 680, 900, 790), "hotbar-1280.png", 3)
crop("candidate/960x600/02-day.png", (280, 490, 720, 595), "hotbar-960.png", 3)
crop("candidate/800x600/02-day.png", (280, 490, 620, 595), "hotbar-800.png", 3)

# bottom-left corner (green dot)
crop("candidate/1280x800/02-day.png", (0, 770, 40, 800), "corner-1280.png", 10)
crop("candidate/800x600/02-day.png", (0, 570, 40, 600), "corner-800.png", 10)

# ore closeups candidate underground
crop("candidate/1280x800/04-underground.png", (1180, 580, 1280, 800), "ore-1280-right.png", 5)
crop("candidate/800x600/04-underground.png", (540, 340, 700, 560), "ore-800-ember.png", 5)
crop("candidate/800x600/04-underground.png", (480, 170, 660, 300), "ore-800-coal.png", 5)
crop("candidate/1280x800/04-underground.png", (340, 280, 560, 480), "ore-1280-center.png", 4)

# title lower area at 1280 and 800
crop("candidate/1280x800/01-title.png", (0, 560, 1280, 800), "title-lower-1280.png", 1)
crop("candidate/800x600/01-title.png", (0, 430, 800, 600), "title-lower-800.png", 1)

# inventory pack 1280 and 800
crop("candidate/1280x800/05-inventory.png", (130, 140, 620, 440), "inv-pack-1280.png", 2)
crop("candidate/800x600/05-inventory.png", (35, 75, 390, 260), "inv-pack-800.png", 3)
crop("candidate/1280x800/05-inventory.png", (620, 140, 1160, 740), "inv-craft-1280.png", 1)
crop("candidate/800x600/05-inventory.png", (380, 75, 770, 590), "inv-craft-800.png", 1)
