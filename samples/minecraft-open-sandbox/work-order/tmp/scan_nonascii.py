import pathlib

for name in ["js/ui.js", "README.md", "css/style.css", "js/render.js", "index.html", "js/buttons.js"]:
    path = pathlib.Path(name)
    if not path.exists():
        continue
    text = path.read_text(encoding="utf-8")
    bad = [(i, ch, hex(ord(ch))) for i, ch in enumerate(text) if ord(ch) > 127]
    print("=" * 20, name, "non-ascii:", len(bad))
    seen = set()
    for i, ch, code in bad[:40]:
        context = text[max(0, i - 24): i + 24].replace("\n", "\\n")
        key = (ch, context[:40])
        if key in seen:
            continue
        seen.add(key)
        print(repr(context))
