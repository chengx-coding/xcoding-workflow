import zipfile, re

p = r"C:\Users\Admin\.local\share\xcoding-workflow\wheels\xcoding_workflow-0.3.6-py3-none-any.whl"
z = zipfile.ZipFile(p)
text = z.read("xcoding/runtime/core.py").decode("utf-8")
lines = text.splitlines()
start = None
for i, line in enumerate(lines, 1):
    if "def _resolve_value_selector" in line:
        start = i
        break
print("start", start)
for i in range(start - 1, min(start + 70, len(lines))):
    print(f"{i+1}: {lines[i]}")
