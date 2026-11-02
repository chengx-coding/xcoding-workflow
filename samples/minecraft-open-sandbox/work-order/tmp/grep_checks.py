import zipfile, re

p = r"C:\Users\Admin\.local\share\xcoding-workflow\wheels\xcoding_workflow-0.3.6-py3-none-any.whl"
z = zipfile.ZipFile(p)
for name in ("xcoding/runtime/application.py", "xcoding/runtime/core.py"):
    text = z.read(name).decode("utf-8")
    lines = text.splitlines()
    print("=" * 20, name)
    for i, line in enumerate(lines, 1):
        if re.search(r"check_result|check_receipt|subject|facts", line):
            print(f"{i}: {line}")
