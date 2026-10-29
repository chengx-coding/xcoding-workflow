from pathlib import Path

root = Path(r"C:\dev\xcoding-workflow-dev\wf-ablation\standard-sample\workspace\project")

p = root / "js" / "main.js"
t = p.read_text(encoding="utf-8")
t = t.replace("  let booted = false;\n", "")
t = t.replace(
    '      newWorld(CONFIG.seed);\n      setSaveState(storeInfo.persisted ? "saved" : "error", storeInfo.persisted ? "Ready" : "Session only");',
    '      newWorld(CONFIG.seed);\n      saveNow();\n      setSaveState(storeInfo.persisted ? "saved" : "error", storeInfo.persisted ? "Ready" : "Session only");',
)
t = t.replace("    booted = true;\n", "")
t = t.replace(
    '    seedRandom.addEventListener("click", function () {\n      seedInput.value = String(Math.floor(Math.random() * 1000000000));\n      seedInput.focus();\n      seedInput.select();\n    });',
    '    seedRandom.addEventListener("click", function () {\n      applySeed(String(Math.floor(Math.random() * 1000000000)));\n    });',
)
p.write_text(t, encoding="utf-8", newline="\n")

p = root / "js" / "render.js"
t = p.read_text(encoding="utf-8")
t = t.replace(
    '    const world = state.world;\n    const camera = state.camera;\n    const player = state.player;\n    const time = state.time;\n\n    if (hover.reason === "reach") {',
    '    const camera = state.camera;\n    const player = state.player;\n    const time = state.time;\n\n    if (hover.reason === "reach") {',
)
t = t.replace('    // Backpack\n        ctx.fillStyle = "#5a3d28";', '    // Backpack\n    ctx.fillStyle = "#5a3d28";')
p.write_text(t, encoding="utf-8", newline="\n")

p = root / "tests" / "save.test.js"
t = p.read_text(encoding="utf-8")
t = t.replace("  const store = SAVE_fake();", "  const store = saveApi.createMemoryStorage();")
t = t.replace("\nfunction SAVE_fake() {\n  return saveApi.createMemoryStorage();\n}\n", "\n")
p.write_text(t, encoding="utf-8", newline="\n")

print("cleaned")
