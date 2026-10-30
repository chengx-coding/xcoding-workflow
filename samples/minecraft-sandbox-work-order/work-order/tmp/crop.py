import sys
from PIL import Image

src = sys.argv[1]
out = sys.argv[2]
box = tuple(int(value) for value in sys.argv[3:7])
zoom = int(sys.argv[7]) if len(sys.argv) > 7 else 2
image = Image.open(src).convert("RGB")
crop = image.crop(box)
crop = crop.resize((crop.width * zoom, crop.height * zoom), Image.NEAREST)
crop.save(out)
print(out, crop.size)
