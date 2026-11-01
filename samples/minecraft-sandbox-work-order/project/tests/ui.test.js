const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const Inventory = require("../js/inventory.js");
const Ui = require("../js/ui.js");

test("the hotbar model lists nine slots with keys, names and counts", () => {
  const inventory = Inventory.starterInventory();
  const model = Ui.hotbarModel(inventory, 0);
  assert.equal(model.length, 9);
  assert.deepEqual(model.map(function (slot) { return slot.key; }), [1, 2, 3, 4, 5, 6, 7, 8, 9]);
  assert.deepEqual(model.map(function (slot) { return slot.label; }), [
    "Grass", "Dirt", "Stone", "Wood", "Leaves", "Sand", "Planks", "Glass", "Brick"
  ]);
  assert.equal(model[0].count, 16);
  assert.equal(model[4].count, 0);
  assert.equal(model[0].selected, true);
  assert.equal(model[1].selected, false);
});

test("selection wraps in both directions", () => {
  assert.equal(Ui.clampIndex(9), 0);
  assert.equal(Ui.clampIndex(-1), 8);
  assert.equal(Ui.stepSelection(8, 1), 0);
  assert.equal(Ui.stepSelection(0, -1), 8);
  assert.equal(Ui.selectedBlockId(8), config.blocks.brick);
  assert.equal(Ui.selectedBlockLabel(6), "Planks");
});

test("coordinates round the feet row correctly", () => {
  assert.deepEqual(Ui.coordinates({ x: 12.5, y: 40.9999 }), { x: 12, y: 41, text: "12, 41" });
  assert.equal(Ui.coordinates({ x: 0.2, y: 3.2 }).text, "0, 3");
});

test("the clock model exposes the label and capitalised phase", () => {
  const clock = Ui.clockModel(0.5);
  assert.equal(clock.label, "12:00");
  assert.equal(clock.phase, "day");
  assert.equal(clock.phaseLabel, "Day");
  assert.equal(Ui.clockModel(0.0).phaseLabel, "Night");
  assert.equal(Ui.clockModel(0.78).phaseLabel, "Dusk");
});

test("target text describes sky, blocks and reach", () => {
  assert.equal(Ui.targetModel(null, config.blocks.air, true).text, "Looking at the sky");
  assert.equal(Ui.targetModel({ x: 1, y: 1 }, config.blocks.grass, true).text, "Grass · left click to mine");
  assert.equal(Ui.targetModel({ x: 1, y: 1 }, config.blocks.air, true).text, "Air · right click to build");
  const refused = Ui.targetModel({ x: 30, y: 1 }, config.blocks.stone, false);
  assert.equal(refused.text, "Stone · out of reach");
  assert.equal(refused.refused, true);
});

test("toast lifetimes are longer for refusals", () => {
  assert.ok(Ui.toastLifetime("refuse") > Ui.toastLifetime("gain"));
});
