const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const inventory = require("../js/inventory.js");

const WOOD = config.blocks.wood;
const STONE = config.blocks.stone;
const PICKAXE_WOOD = 110;
const PICKAXE_STONE = 111;

test("a new inventory has an empty hotbar and no items", () => {
  const bag = inventory.createInventory();
  assert.equal(inventory.totalItems(bag), 0);
  assert.equal(bag.hotbar.length, config.hotbarSize);
  assert.equal(inventory.selectedId(bag), 0);
});

test("adding and removing items tracks counts and the hotbar", () => {
  const bag = inventory.createInventory();
  inventory.add(bag, WOOD, 3);
  assert.equal(inventory.count(bag, WOOD), 3);
  assert.equal(inventory.has(bag, WOOD, 3), true);
  assert.equal(inventory.has(bag, WOOD, 4), false);
  assert.equal(bag.hotbar[0], WOOD, "the first picked-up block occupies the first slot");
  assert.equal(inventory.remove(bag, WOOD, 2), true);
  assert.equal(inventory.count(bag, WOOD), 1);
  assert.equal(inventory.remove(bag, WOOD, 5), false);
  inventory.remove(bag, WOOD, 1);
  assert.equal(bag.hotbar[0], 0, "an emptied stack frees its hotbar slot");
});

test("hotbar selection and definitions resolve the held item", () => {
  const bag = inventory.createInventory();
  inventory.add(bag, WOOD, 1);
  inventory.add(bag, STONE, 1);
  assert.equal(bag.hotbar[0], WOOD);
  assert.equal(bag.hotbar[1], STONE);
  inventory.select(bag, 1);
  assert.equal(inventory.selectedId(bag), STONE);
  assert.equal(inventory.selectedDefinition(bag).name, "Stone");
  assert.equal(inventory.select(bag, 12), false);
});

test("best tool picks the highest tier of the matching class", () => {
  const bag = inventory.createInventory();
  assert.equal(inventory.bestTool(bag, "pickaxe"), null);
  inventory.add(bag, PICKAXE_WOOD, 1);
  assert.equal(inventory.bestTool(bag, "pickaxe").id, PICKAXE_WOOD);
  inventory.add(bag, PICKAXE_STONE, 1);
  assert.equal(inventory.bestTool(bag, "pickaxe").id, PICKAXE_STONE);
  assert.equal(inventory.bestTool(bag, "axe"), null);
});

test("inventory serialization round-trips entries and selection", () => {
  const bag = inventory.createInventory();
  inventory.add(bag, WOOD, 7);
  inventory.add(bag, PICKAXE_WOOD, 1);
  inventory.select(bag, 1);
  const restored = inventory.deserialize(inventory.serialize(bag));
  assert.equal(inventory.count(restored, WOOD), 7);
  assert.equal(inventory.count(restored, PICKAXE_WOOD), 1);
  assert.equal(restored.selected, 1);
  assert.deepEqual(restored.hotbar.slice(0, 2), [WOOD, PICKAXE_WOOD]);
});

test("deserialization drops unknown items and stale hotbar slots", () => {
  const restored = inventory.deserialize({
    items: [{ id: 9999, count: 3 }, { id: WOOD, count: 1 }],
    hotbar: [9999, WOOD],
    selected: 0
  });
  assert.equal(inventory.count(restored, 9999), 0);
  assert.equal(inventory.count(restored, WOOD), 1);
  assert.equal(restored.hotbar[0], 0);
  assert.equal(restored.hotbar[1], WOOD);
});
