import pathlib

for name in ["js/ui.js", "README.md", "index.html"]:
    path = pathlib.Path(name)
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8", errors="strict")
        print("=" * 20, name, "valid utf-8, bytes", len(raw), "crlf", raw.count(b"\r\n"))
    except UnicodeDecodeError as error:
        print("=" * 20, name, "INVALID UTF-8", error)
        text = raw.decode("utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), 1):
        if any(ord(ch) > 127 for ch in line):
            print(lineno, ascii(line))
