const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const inventoryApi = require("../js/inventory.js");
const crafting = require("../js/crafting.js");

test("planks, sticks and torches consume and yield the documented amounts", () => {
  const inventory = inventoryApi.createInventory({ wood: 1 });
  const planks = crafting.recipeById("planks");
  assert.equal(crafting.canCraft(inventory, planks), true);
  assert.equal(crafting.craft(inventory, planks).ok, true);
  assert.equal(inventoryApi.count(inventory, "wood"), 0);
  assert.equal(inventoryApi.count(inventory, "planks"), 4);

  const sticks = crafting.recipeById("sticks");
  assert.equal(crafting.craft(inventory, sticks).ok, true);
  assert.equal(inventoryApi.count(inventory, "planks"), 2);
  assert.equal(inventoryApi.count(inventory, "stick"), 4);

  inventoryApi.add(inventory, "coal", 1);
  const torches = crafting.recipeById("torches");
  assert.equal(crafting.craft(inventory, torches).ok, true);
  assert.equal(inventoryApi.count(inventory, "torch"), 4);
  assert.equal(inventoryApi.count(inventory, "stick"), 3);
  assert.equal(inventoryApi.count(inventory, "coal"), 0);
});

test("pickaxes are unique and cost the documented materials", () => {
  const inventory = inventoryApi.createInventory({ planks: 3, stick: 2 });
  const wooden = crafting.recipeById("wood-pickaxe");
  assert.equal(crafting.craft(inventory, wooden).ok, true);
  assert.equal(inventoryApi.count(inventory, "wood_pickaxe"), 1);
  assert.equal(inventoryApi.count(inventory, "planks"), 0);
  assert.equal(crafting.canCraft(inventory, wooden), false);

  inventoryApi.add(inventory, "stone", 3);
  inventoryApi.add(inventory, "stick", 2);
  const stone = crafting.recipeById("stone-pickaxe");
  assert.equal(crafting.craft(inventory, stone).ok, true);
  assert.equal(inventoryApi.count(inventory, "stone_pickaxe"), 1);
});

test("insufficient materials fail atomically", () => {
  const inventory = inventoryApi.createInventory({ planks: 1, stick: 1 });
  const wooden = crafting.recipeById("wood-pickaxe");
  assert.equal(crafting.canCraft(inventory, wooden), false);
  assert.equal(crafting.craft(inventory, wooden).ok, false);
  assert.equal(inventoryApi.count(inventory, "planks"), 1);
  assert.equal(inventoryApi.count(inventory, "stick"), 1);
});

test("recipe costs report have and need values", () => {
  const inventory = inventoryApi.createInventory({ stone: 1, stick: 2 });
  const costs = crafting.craftCosts(inventory, crafting.recipeById("stone-pickaxe"));
  assert.deepEqual(
    costs.sort((a, b) => a.item.localeCompare(b.item)),
    [
      { item: "stick", need: 2, have: 2 },
      { item: "stone", need: 3, have: 1 }
    ]
  );
});
