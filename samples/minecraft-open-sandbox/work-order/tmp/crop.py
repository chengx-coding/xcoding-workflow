from PIL import Image

src = r".xcoding\work-orders\20261102-1550-open-sandbox-xc-047\artifacts\screens\02-day-surface.png"
out = r".xcoding\work-orders\20261102-1550-open-sandbox-xc-047\tmp\crop-trees.png"
image = Image.open(src)
image.crop((780, 170, 1080, 700)).resize((600, 1060)).save(out)
print(out)
