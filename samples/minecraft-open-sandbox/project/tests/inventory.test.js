const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const inventoryApi = require("../js/inventory.js");

const B = config.blocks;
const I = config.items;

test("a new inventory has empty slots and a first hotbar slot", () => {
  const inventory = inventoryApi.createInventory();
  assert.equal(inventory.slots.length, config.inventorySize);
  assert.equal(inventory.selected, 0);
  assert.equal(inventory.slots[0], null);
});

test("adding materials stacks and then fills new slots", () => {
  const inventory = inventoryApi.createInventory();
  assert.equal(inventoryApi.add(inventory, B.dirt, 10), 0);
  assert.equal(inventoryApi.countOf(inventory, B.dirt), 10);
  assert.equal(inventoryApi.add(inventory, B.dirt, config.stackLimit + 5), 0);
  assert.equal(inventoryApi.countOf(inventory, B.dirt), config.stackLimit + 15);
  assert.equal(inventory.slots.filter(Boolean).length, 2);
});

test("tools do not stack", () => {
  const inventory = inventoryApi.createInventory();
  inventoryApi.add(inventory, I.pick_wood, 2);
  assert.equal(inventoryApi.countOf(inventory, I.pick_wood), 2);
  assert.equal(inventory.slots.filter(Boolean).length, 2);
});

test("removing materials consumes across stacks", () => {
  const inventory = inventoryApi.createInventory();
  inventoryApi.add(inventory, B.planks, 120);
  assert.equal(inventoryApi.remove(inventory, B.planks, 100), 100);
  assert.equal(inventoryApi.countOf(inventory, B.planks), 20);
  assert.equal(inventoryApi.remove(inventory, B.planks, 99), 20);
  assert.equal(inventoryApi.countOf(inventory, B.planks), 0);
});

test("has reports the available amount", () => {
  const inventory = inventoryApi.createInventory();
  inventoryApi.add(inventory, B.cobble, 3);
  assert.equal(inventoryApi.has(inventory, B.cobble, 3), true);
  assert.equal(inventoryApi.has(inventory, B.cobble, 4), false);
  assert.equal(inventoryApi.has(inventory, B.stone, 0), true);
});

test("swapping slots moves stacks and merges identical ones", () => {
  const inventory = inventoryApi.createInventory();
  inventoryApi.add(inventory, B.wood, 5);
  inventoryApi.add(inventory, B.stone, 2);
  assert.equal(inventoryApi.swap(inventory, 0, 1), true);
  assert.equal(inventory.slots[0].id, B.stone);
  assert.equal(inventory.slots[1].id, B.wood);
  inventory.slots[2] = { id: B.wood, count: 10 };
  inventoryApi.swap(inventory, 1, 2);
  assert.equal(inventoryApi.countOf(inventory, B.wood), 15);
  assert.equal(inventory.slots[1], null);
});

test("hotbar selection wraps inside the hotbar", () => {
  const inventory = inventoryApi.createInventory();
  inventoryApi.select(inventory, 9);
  assert.equal(inventory.selected, 0);
  inventoryApi.select(inventory, -1);
  assert.equal(inventory.selected, config.hotbarSize - 1);
  inventoryApi.select(inventory, 4);
  assert.equal(inventory.selected, 4);
});

test("selectedStack returns the active hotbar stack", () => {
  const inventory = inventoryApi.createInventory();
  inventoryApi.add(inventory, B.torch, 4);
  assert.equal(inventoryApi.selectedStack(inventory).id, B.torch);
  inventoryApi.select(inventory, 3);
  assert.equal(inventoryApi.selectedStack(inventory), null);
});

test("a full inventory reports leftover items", () => {
  const inventory = inventoryApi.createInventory();
  for (let i = 0; i < inventory.slots.length; i += 1) {
    inventory.slots[i] = { id: B.stone, count: config.stackLimit };
  }
  const leftover = inventoryApi.add(inventory, B.dirt, 5);
  assert.equal(leftover, 5);
});

test("inventory state round-trips and rejects unknown stacks", () => {
  const inventory = inventoryApi.createInventory();
  inventoryApi.add(inventory, B.stone, 9);
  inventoryApi.add(inventory, I.pick_iron, 1);
  inventoryApi.select(inventory, 2);
  const restored = inventoryApi.deserialize(inventoryApi.serialize(inventory));
  assert.equal(restored.selected, 2);
  assert.equal(inventoryApi.countOf(restored, B.stone), 9);
  assert.equal(inventoryApi.countOf(restored, I.pick_iron), 1);
  const junk = inventoryApi.deserialize({ selected: 0, slots: [{ id: 9999, count: 4 }] });
  assert.equal(junk.slots[0], null);
});
