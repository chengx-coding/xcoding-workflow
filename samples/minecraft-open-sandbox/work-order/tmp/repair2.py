import pathlib

ui_path = pathlib.Path("js/ui.js")
ui = ui_path.read_text(encoding="utf-8")
ui = ui.replace("\u923e?/span>", "\u2665</span>")
ui = ui.replace('" \u8133 " + recipe.output.count', '" \u00d7 " + recipe.output.count')
ui_path.write_text(ui, encoding="utf-8", newline="\n")

readme_path = pathlib.Path("README.md")
readme = readme_path.read_text(encoding="utf-8")
for word in ("build", "craft", "reach", "light", "forge", "mine", "raise"):
    readme = readme.replace("\u2192" + word, "\u2192 " + word)
readme = readme.replace(
    "| `A` / `D` or `\u2190 / `\u2192 | Walk left and right |",
    "| `A` / `D` or `\u2190` / `\u2192` | Walk left and right |",
)
readme_path.write_text(readme, encoding="utf-8", newline="\n")

for label, path in (("ui", ui_path), ("readme", readme_path)):
    text = path.read_text(encoding="utf-8")
    bad = [ascii(ch) for ch in text if ch in "\u922b\u9225\u8def\u923e\u8133\u6045\u6288"]
    print(label, "leftover:", bad, "non-ascii:", sum(1 for ch in text if ord(ch) > 127))
