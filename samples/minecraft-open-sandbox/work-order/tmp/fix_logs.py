import pathlib

path = pathlib.Path("tools/browser_check.js")
text = path.read_text(encoding="utf-8")
fixed = text.replace("`n", "\n")
path.write_text(fixed, encoding="utf-8", newline="\n")
print("backtick-n count before:", text.count("`n"), "after:", fixed.count("`n"))
for i, line in enumerate(fixed.splitlines(), 1):
    if "[browser]" in line:
        print(i, line.strip())
