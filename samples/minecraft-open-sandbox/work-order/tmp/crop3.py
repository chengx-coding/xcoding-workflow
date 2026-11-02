from PIL import Image

src = r".xcoding\work-orders\20261102-1550-open-sandbox-xc-047\artifacts\screens\05-restored.png"
out = r".xcoding\work-orders\20261102-1550-open-sandbox-xc-047\tmp\crop-tree2.png"
image = Image.open(src)
image.crop((760, 170, 1080, 460)).resize((960, 870)).save(out)
print(out)
