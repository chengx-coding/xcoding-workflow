from PIL import Image

src = r".xcoding\work-orders\20261102-1550-open-sandbox-xc-047\artifacts\screens\05-restored.png"
out = r".xcoding\work-orders\20261102-1550-open-sandbox-xc-047\tmp\crop-holes.png"
image = Image.open(src)
image.crop((500, 330, 820, 430)).resize((960, 300)).save(out)
print(out)
