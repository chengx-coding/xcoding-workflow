const test = require("node:test");
const assert = require("node:assert/strict");
const config = require("../js/config.js");
const inv = require("../js/inventory.js");

test("addItem fills stacks and reports leftover when full", () => {
  const inventory = inv.createInventory();
  assert.equal(inv.addItem(inventory, config.blocks.dirt, 70), 0);
  assert.equal(inv.countItem(inventory, config.blocks.dirt), 70);
  assert.equal(inventory.slots[0].count, 64);
  assert.equal(inventory.slots[1].count, 6);
  assert.equal(inv.addItem(inventory, config.blocks.stone, 34 * 64), 0);
  assert.equal(inv.addItem(inventory, config.blocks.stone, 5), 5);
});

test("removeItem and hasItem respect counts", () => {
  const inventory = inv.createInventory();
  inv.addItem(inventory, config.itemIds.stick, 20);
  assert.equal(inv.hasItem(inventory, config.itemIds.stick, 20), true);
  assert.equal(inv.removeItem(inventory, config.itemIds.stick, 8), 8);
  assert.equal(inv.countItem(inventory, config.itemIds.stick), 12);
  assert.equal(inv.removeItem(inventory, config.itemIds.stick, 99), 12);
});

test("hotbar selection wraps and selected stack is readable", () => {
  const inventory = inv.createInventory();
  inv.addItem(inventory, config.blocks.planks, 3);
  inv.setSelected(inventory, -1);
  assert.equal(inventory.selected, 8);
  inv.cycleSelected(inventory, 1);
  assert.equal(inventory.selected, 0);
  assert.equal(inv.selectedStack(inventory).id, config.blocks.planks);
});

test("move and split keep counts consistent", () => {
  const inventory = inv.createInventory();
  inv.addItem(inventory, config.blocks.stone, 30);
  inv.moveStack(inventory, 0, 9, 10);
  assert.equal(inv.countItem(inventory, config.blocks.stone), 30);
  assert.equal(inventory.slots[0].count, 20);
  assert.equal(inventory.slots[9].count, 10);
  const split = inv.splitSlot(inventory, 0);
  assert.ok(split >= 0);
  assert.equal(inv.countItem(inventory, config.blocks.stone), 30);
});

test("serialization round-trips stacks", () => {
  const inventory = inv.createInventory();
  inv.addItem(inventory, config.itemIds.ironIngot, 5);
  const restored = inv.deserializeInventory(inv.serializeInventory(inventory));
  assert.equal(inv.countItem(restored, config.itemIds.ironIngot), 5);
});

test("consumeSelected does not consume a different slot", () => {
  const inventory = inv.createInventory();
  inv.addItem(inventory, config.blocks.dirt, 2);
  inv.setSelected(inventory, 3);
  assert.equal(inv.consumeSelected(inventory, 1), false);
  inv.setSelected(inventory, 0);
  assert.equal(inv.consumeSelected(inventory, 1), true);
  assert.equal(inv.countItem(inventory, config.blocks.dirt), 1);
});
