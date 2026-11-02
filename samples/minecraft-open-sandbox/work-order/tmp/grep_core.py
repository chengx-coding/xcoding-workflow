import zipfile, re

p = r"C:\Users\Admin\.local\share\xcoding-workflow\wheels\xcoding_workflow-0.3.6-py3-none-any.whl"
z = zipfile.ZipFile(p)
text = z.read("xcoding/runtime/core.py").decode("utf-8")
lines = text.splitlines()
for i, line in enumerate(lines, 1):
    if re.search(r"check|subject|facts|receipt", line, re.I):
        print(f"{i}: {line}")
