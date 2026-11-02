"""Repair the mojibake introduced by a Windows PowerShell round-trip."""

import pathlib

UI = pathlib.Path("js/ui.js")
README = pathlib.Path("README.md")

ui = UI.read_text(encoding="utf-8")
replacements = [
    ('["A / D  or  \u922b?/ \u922b?,', '["A / D  or  \u2190 / \u2192",'),
    ('["1 \u9225?9  or  mouse wheel"', '["1 \u2013 9  or  mouse wheel"'),
    ('No saved meadow yet \u9225?this', 'No saved meadow yet \u2014 this'),
    ('build \u9225?and light the deep.', 'build \u2014 and light the deep.'),
    ('. 1\u9225? selects a hotbar slot.', '. 1\u20139 selects a hotbar slot.'),
    ('No station nearby \u9225?place', 'No station nearby \u2014 place'),
    ('New world\u9225?/button>', 'New world\u2026</button>'),
    ('"X 24 \u8def Y 91"', '"X 24 \u00b7 Y 91"'),
    ('class="heart">\u923e?/span>', 'class="heart">\u2665</span>'),
    ('"\u8133 "', '"\u00d7 "'),
]
for old, new in replacements:
    if old not in ui:
        print("UI MISS:", ascii(old))
    ui = ui.replace(old, new)
ui = ui.replace("\u8def", "\u00b7")
UI.write_text(ui, encoding="utf-8", newline="\n")

readme = README.read_text(encoding="utf-8")
readme = readme.replace("\u922b\u6045", "\u2190").replace("\u922b\u6288", "\u2192")
readme = readme.replace("\u922b?", "\u2192")
readme = readme.replace("# Emberdeep \u9225?a small 2D sandbox", "# Emberdeep \u2014 a small 2D sandbox")
readme = readme.replace("`1` \u9225?`9`", "`1` \u2013 `9`")
README.write_text(readme, encoding="utf-8", newline="\n")

for label, path in (("ui", UI), ("readme", README)):
    text = path.read_text(encoding="utf-8")
    leftovers = [ascii(ch) for ch in text if ch in "\u922b\u9225\u8def\u923e\u8133\u6045\u6288"]
    print(label, "leftover mojibake chars:", leftovers, "non-ascii:", sum(1 for ch in text if ord(ch) > 127))
