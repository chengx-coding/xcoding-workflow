import zipfile

p = r"C:\Users\Admin\.local\share\xcoding-workflow\wheels\xcoding_workflow-0.3.6-py3-none-any.whl"
z = zipfile.ZipFile(p)
names = [n for n in z.namelist() if n.endswith(".py")]
for n in names:
    print(n)
