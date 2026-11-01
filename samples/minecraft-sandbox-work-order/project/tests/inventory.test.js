const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const Inventory = require("../js/inventory.js");

test("the starter inventory matches the configuration", () => {
  const inventory = Inventory.starterInventory();
  for (let blockId = 1; blockId <= 9; blockId += 1) {
    const expected = config.starterInventory[blockId] || 0;
    assert.equal(Inventory.count(inventory, blockId), expected, "block " + blockId);
  }
  assert.equal(Inventory.count(inventory, config.blocks.leaves), 0);
});

test("add increases one per-block count", () => {
  const inventory = Inventory.createInventory();
  assert.equal(Inventory.add(inventory, config.blocks.stone), true);
  assert.equal(Inventory.add(inventory, config.blocks.stone, 3), true);
  assert.equal(Inventory.count(inventory, config.blocks.stone), 4);
});

test("consume decreases a count and refuses to go negative", () => {
  const inventory = Inventory.createInventory({ 3: 2 });
  assert.equal(Inventory.consume(inventory, config.blocks.stone), true);
  assert.equal(Inventory.count(inventory, config.blocks.stone), 1);
  assert.equal(Inventory.consume(inventory, config.blocks.stone, 5), false);
  assert.equal(Inventory.count(inventory, config.blocks.stone), 1);
  assert.equal(Inventory.consume(inventory, config.blocks.stone), true);
  assert.equal(Inventory.count(inventory, config.blocks.stone), 0);
});

test("invalid block ids and amounts are refused", () => {
  const inventory = Inventory.createInventory();
  assert.equal(Inventory.add(inventory, 0), false);
  assert.equal(Inventory.add(inventory, 10), false);
  assert.equal(Inventory.add(inventory, 1, 0), false);
  assert.equal(Inventory.consume(inventory, 1, -1), false);
});

test("inventory total sums all slots", () => {
  const inventory = Inventory.createInventory({ 1: 2, 2: 3, 3: 1 });
  assert.equal(Inventory.total(inventory), 6);
});

test("serialization round-trips every slot", () => {
  const inventory = Inventory.starterInventory();
  Inventory.add(inventory, config.blocks.leaves, 4);
  const restored = Inventory.fromJSON(JSON.parse(JSON.stringify(Inventory.toJSON(inventory))));
  for (let blockId = 1; blockId <= 9; blockId += 1) {
    assert.equal(Inventory.count(restored, blockId), Inventory.count(inventory, blockId));
  }
});

test("fromJSON tolerates missing and invalid slots", () => {
  const restored = Inventory.fromJSON({ 1: 5, bad: 9, 2: -4, 3: "x" });
  assert.equal(Inventory.count(restored, 1), 5);
  assert.equal(Inventory.count(restored, 2), 0);
  assert.equal(Inventory.count(restored, 3), 0);
  assert.equal(Inventory.total(restored), 5);
});
