const test = require("node:test");
const assert = require("node:assert/strict");
const config = require("../js/config.js");
const furnace = require("../js/furnace.js");

test("fuel values and smelting recipes are defined", () => {
  assert.ok(furnace.fuelFor(config.itemIds.coal) > furnace.fuelFor(config.itemIds.stick));
  assert.equal(furnace.fuelFor(9999), 0);
  assert.equal(furnace.smeltFor(config.itemIds.rawIron).id, config.itemIds.ironIngot);
  assert.equal(furnace.smeltFor(config.blocks.sand).id, config.blocks.glass);
  assert.equal(furnace.smeltFor(config.itemIds.rawPork).id, config.itemIds.cookedPork);
});

test("a fuelled furnace smelts after the cook time and consumes one input", () => {
  const state = furnace.createState();
  state.input = { id: config.itemIds.rawIron, count: 2 };
  state.fuel = { id: config.itemIds.coal, count: 1 };
  let produced = null;
  for (let i = 0; i < 60 * 7 && !produced; i += 1) {
    const result = furnace.tick(state, 1 / 60);
    if (result.produced) produced = result.produced;
  }
  assert.ok(produced);
  assert.equal(state.output.id, config.itemIds.ironIngot);
  assert.equal(state.output.count, 1);
  assert.equal(state.input.count, 1);
  assert.ok(state.burnTime > 0);
});

test("an empty or invalid furnace does not burn fuel", () => {
  const state = furnace.createState();
  state.fuel = { id: config.itemIds.coal, count: 1 };
  for (let i = 0; i < 60; i += 1) {
    furnace.tick(state, 1 / 60);
  }
  assert.equal(state.fuel.count, 1);
  state.input = { id: config.blocks.dirt, count: 1 };
  for (let i = 0; i < 60; i += 1) {
    furnace.tick(state, 1 / 60);
  }
  assert.equal(state.fuel.count, 1);
});

test("output stacking respects the max stack and blocks progress when full", () => {
  const state = furnace.createState();
  state.input = { id: config.blocks.sand, count: 2 };
  state.fuel = { id: config.itemIds.coal, count: 1 };
  state.output = { id: config.blocks.glass, count: 64 };
  for (let i = 0; i < 60 * 7; i += 1) {
    furnace.tick(state, 1 / 60);
  }
  assert.equal(state.output.count, 64);
  assert.equal(state.input.count, 2);
});

test("furnace stores serialize and deserialize", () => {
  const store = furnace.createStore();
  const state = furnace.get(store, 4, 7, true);
  state.input = { id: config.itemIds.rawIron, count: 3 };
  state.fuel = { id: config.itemIds.coal, count: 2 };
  state.burnTime = 12;
  state.burnMax = 40;
  state.cookTime = 2;
  const restored = furnace.deserialize(furnace.serialize(store));
  const again = furnace.get(restored, 4, 7, false);
  assert.ok(again);
  assert.equal(again.input.count, 3);
  assert.equal(again.fuel.id, config.itemIds.coal);
  assert.equal(again.burnMax, 40);
  assert.equal(again.cookTime, 2);
});
