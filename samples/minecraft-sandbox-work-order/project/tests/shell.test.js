const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const css = fs.readFileSync(path.join(root, "css", "style.css"), "utf8");
const readme = fs.readFileSync(path.join(root, "README.md"), "utf8");
const config = require("../js/config.js");

function scriptSources(source) {
  const pattern = /<script\s+src="([^"]+)"/g;
  const found = [];
  let match = pattern.exec(source);
  while (match) {
    found.push(match[1]);
    match = pattern.exec(source);
  }
  return found;
}

test("the page declares the required ids for the verification contract", () => {
  ["game", "status", "hud", "hotbar"].forEach((id) => {
    assert.ok(html.includes('id="' + id + '"'), "missing id=" + id);
  });
  assert.match(html, /<canvas id="game" width="960" height="540"/);
});

test("the hotbar markup has nine slots in configured order", () => {
  const slots = html.match(/class="slot"/g) || [];
  assert.equal(slots.length, 9);
  const blocks = [];
  const pattern = /data-slot="(\d)" data-block="([a-z]+)"/g;
  let match = pattern.exec(html);
  while (match) {
    blocks.push({ slot: Number(match[1]), block: match[2] });
    match = pattern.exec(html);
  }
  assert.equal(blocks.length, 9);
  const names = config.hotbar.map((block) => config.blockNames[block].toLowerCase());
  blocks.forEach((entry, index) => {
    assert.equal(entry.slot, index);
    assert.equal(entry.block, names[index]);
  });
  assert.equal(blocks[7].block, "cobblestone");
  assert.equal(blocks[8].block, "glass");
});

test("every local asset reference exists", () => {
  const references = [];
  const pattern = /(?:src|href)="([^"]+)"/g;
  let match = pattern.exec(html);
  while (match) {
    references.push(match[1]);
    match = pattern.exec(html);
  }
  references.forEach((reference) => {
    assert.ok(!/^https?:|^\/\//.test(reference), "external reference: " + reference);
    assert.ok(fs.existsSync(path.join(root, reference)), "missing asset: " + reference);
  });
});

test("scripts load every module before the entry point", () => {
  const sources = scriptSources(html);
  assert.equal(sources[0], "js/config.js");
  assert.equal(sources[sources.length - 1], "js/main.js");
  ["js/rng.js", "js/world.js", "js/player.js", "js/camera.js", "js/interaction.js", "js/daynight.js", "js/storage.js", "js/audio.js", "js/ui.js", "js/render.js"].forEach((source) => {
    assert.ok(sources.includes(source), "missing script " + source);
  });
  assert.ok(sources.indexOf("js/render.js") < sources.indexOf("js/main.js"));
});

test("no page asset contains a network reference", () => {
  const files = ["index.html", "css/style.css"].concat(
    fs.readdirSync(path.join(root, "js")).map((name) => path.join("js", name))
  );
  files.forEach((file) => {
    const text = fs.readFileSync(path.join(root, file), "utf8");
    assert.ok(!/https?:\/\//i.test(text), "network reference in " + file);
    assert.ok(!/["'(]\/\//.test(text), "protocol-relative reference in " + file);
  });
});

test("the status marker keeps the booting, ready and error contract", () => {
  assert.ok(html.includes('id="status" data-state="booting"'));
  const main = fs.readFileSync(path.join(root, "js", "main.js"), "utf8");
  assert.ok(main.includes('setStatus("ready"'));
  assert.ok(main.includes('"error"'));
  assert.ok(css.includes('#status[data-state="ready"]'));
  assert.ok(css.includes('#status[data-state="error"]'));
});

test("the stylesheet scales the page at 1280 pixels wide", () => {
  assert.match(css, /@media\s*\(min-width:\s*1280px\)/);
  const block = css.slice(css.indexOf("@media (min-width: 1280px)"));
  assert.ok(block.includes("width: 1280px"));
  assert.ok(block.includes("#hotbar"));
});

test("the stylesheet honours reduced motion", () => {
  assert.match(css, /@media\s*\(prefers-reduced-motion:\s*reduce\)/);
  const main = fs.readFileSync(path.join(root, "js", "main.js"), "utf8");
  assert.ok(main.includes("prefers-reduced-motion"));
});

test("the page exposes help, pause, seed and toast surfaces", () => {
  assert.ok(html.includes('id="help-overlay"'));
  assert.ok(html.includes('id="pause-overlay"'));
  assert.ok(html.includes('id="seed-input"'));
  assert.ok(html.includes('id="seed-form"'));
  assert.ok(html.includes('id="toasts"'));
  assert.ok(html.includes("inputmode=\"numeric\""));
});

test("every browser module is requireable and exports its public API", () => {
  const modules = {
    "../js/config.js": ["blocks", "hotbar", "hardness", "saveKey"],
    "../js/rng.js": ["parseSeedText", "mulberry32", "hash2"],
    "../js/world.js": ["createWorld", "surfaceMap", "findSpawn"],
    "../js/player.js": ["createPlayer", "stepPlayer"],
    "../js/camera.js": ["followCamera", "visibleRange"],
    "../js/interaction.js": ["createInventory", "placeBlock", "advanceMining"],
    "../js/daynight.js": ["advanceTime", "skyColors"],
    "../js/storage.js": ["createStore"],
    "../js/audio.js": ["createAudioBoard"],
    "../js/ui.js": ["formatCoords", "keyToAction"],
    "../js/render.js": ["renderFrame", "surfaceFor"]
  };
  Object.keys(modules).forEach((relative) => {
    const loaded = require(relative);
    modules[relative].forEach((key) => {
      assert.ok(key in loaded, relative + " is missing " + key);
    });
  });
});

test("README documents the game, controls, checks and architecture", () => {
  assert.ok(!/skeleton/i.test(readme), "README still describes the seed skeleton");
  assert.match(readme, /## Controls/);
  assert.ok(readme.includes("node --test"));
  assert.ok(readme.includes("tools/page_check.py"));
  assert.match(readme, /localStorage/);
  assert.ok(readme.includes("index.html"));
});

test("the config seed is numeric and the palette is complete", () => {
  assert.equal(typeof config.seed, "number");
  assert.ok(config.seed > 0);
  assert.equal(config.hotbar.length, 9);
  assert.equal(config.hotbar[7], config.blocks.cobblestone);
  assert.equal(config.hotbar[8], config.blocks.glass);
  assert.ok(config.dayCycleSeconds > 0);
  assert.ok(config.reach > 0);
});
