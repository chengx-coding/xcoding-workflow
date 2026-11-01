const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const inventoryApi = require("../js/inventory.js");

test("inventory add, count and atomic remove", () => {
  const inventory = inventoryApi.createInventory();
  assert.equal(inventoryApi.count(inventory, "wood"), 0);
  inventoryApi.add(inventory, "wood", 3);
  inventoryApi.add(inventory, "wood", 2);
  assert.equal(inventoryApi.count(inventory, "wood"), 5);
  assert.equal(inventoryApi.has(inventory, "wood", 5), true);
  assert.equal(inventoryApi.has(inventory, "wood", 6), false);
  assert.equal(inventoryApi.remove(inventory, "wood", 6), false);
  assert.equal(inventoryApi.count(inventory, "wood"), 5);
  assert.equal(inventoryApi.remove(inventory, "wood", 5), true);
  assert.equal(inventoryApi.count(inventory, "wood"), 0);
  assert.deepEqual(inventory.items, {});
});

test("inventory rejects invalid quantities and keeps only positive integers", () => {
  const inventory = inventoryApi.createInventory({ wood: 2, stone: 0, dirt: -1, sand: 1.5 });
  assert.deepEqual(inventory.items, { wood: 2 });
  assert.equal(inventoryApi.add(inventory, "wood", 0), false);
  assert.equal(inventoryApi.remove(inventory, "wood", 0), false);
});

test("hotbar selection is bounded and cycles", () => {
  const inventory = inventoryApi.createInventory({}, 0);
  assert.equal(inventoryApi.selectedItem(inventory), config.hotbar[0]);
  assert.equal(inventoryApi.selectSlot(inventory, config.hotbar.length), false);
  assert.equal(inventoryApi.selectSlot(inventory, -1), false);
  assert.equal(inventoryApi.selectSlot(inventory, 3), true);
  assert.equal(inventory.selected, 3);
  inventoryApi.cycleSlot(inventory, 1);
  assert.equal(inventory.selected, 4);
  inventoryApi.cycleSlot(inventory, -1);
  assert.equal(inventory.selected, 3);
  inventory.selected = 0;
  inventoryApi.cycleSlot(inventory, -1);
  assert.equal(inventory.selected, config.hotbar.length - 1);
});

test("tools and placeable selection follow the inventory contents", () => {
  const inventory = inventoryApi.createInventory();
  assert.deepEqual(inventoryApi.tools(inventory), []);
  assert.equal(inventoryApi.placeableSelected(inventory), null);
  inventoryApi.add(inventory, "wood_pickaxe", 1);
  inventoryApi.add(inventory, "stone_pickaxe", 1);
  assert.deepEqual(inventoryApi.tools(inventory).sort(), ["stone_pickaxe", "wood_pickaxe"]);
  inventory.selected = 0;
  assert.equal(inventoryApi.placeableSelected(inventory), null);
  inventoryApi.add(inventory, config.hotbar[0], 1);
  assert.equal(inventoryApi.placeableSelected(inventory), config.hotbar[0]);
});
