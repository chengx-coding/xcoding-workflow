const test = require("node:test");
const assert = require("node:assert/strict");
const config = require("../js/config.js");
const inv = require("../js/inventory.js");
const crafting = require("../js/crafting.js");

test("planks and sticks craft by hand with exact consumption", () => {
  const inventory = inv.createInventory();
  inv.addItem(inventory, config.blocks.wood, 2);
  const planks = crafting.getRecipe("planks");
  assert.equal(crafting.canCraft(inventory, planks, false), true);
  assert.equal(crafting.craft(inventory, planks, false).ok, true);
  assert.equal(inv.countItem(inventory, config.blocks.planks), 4);
  assert.equal(inv.countItem(inventory, config.blocks.wood), 1);
  inv.addItem(inventory, config.blocks.planks, 2);
  const stick = crafting.getRecipe("stick");
  assert.equal(crafting.craft(inventory, stick, false).ok, true);
  assert.equal(inv.countItem(inventory, config.itemIds.stick), 4);
});

test("table recipes are locked without a nearby table", () => {
  const inventory = inv.createInventory();
  inv.addItem(inventory, config.blocks.planks, 3);
  inv.addItem(inventory, config.itemIds.stick, 2);
  const pick = crafting.getRecipe("wooden_pickaxe");
  assert.equal(crafting.canCraft(inventory, pick, false), false);
  const blocked = crafting.craft(inventory, pick, false);
  assert.equal(blocked.ok, false);
  assert.match(blocked.reason, /table/i);
  assert.equal(inv.countItem(inventory, config.blocks.planks), 3);
  assert.equal(crafting.craft(inventory, pick, true).ok, true);
  assert.equal(inv.countItem(inventory, config.itemIds.woodenPickaxe), 1);
  assert.equal(inv.countItem(inventory, config.blocks.planks), 0);
  assert.equal(inv.countItem(inventory, config.itemIds.stick), 0);
});

test("missing ingredients are reported without consuming anything", () => {
  const inventory = inv.createInventory();
  inv.addItem(inventory, config.blocks.planks, 1);
  const table = crafting.getRecipe("table");
  const result = crafting.craft(inventory, table, false);
  assert.equal(result.ok, false);
  assert.equal(result.missing[0].missing, 3);
  assert.equal(inv.countItem(inventory, config.blocks.planks), 1);
});

test("every recipe has a valid output and ingredient list", () => {
  assert.ok(crafting.recipes.length >= 15);
  for (const entry of crafting.recipes) {
    assert.ok(config.itemDefs[entry.output.id], entry.id + " output");
    assert.ok(entry.ingredients.length > 0, entry.id + " ingredients");
    for (const ingredient of entry.ingredients) {
      assert.ok(config.itemDefs[ingredient.id], entry.id + " ingredient " + ingredient.id);
      assert.ok(ingredient.count > 0);
    }
  }
});

test("a full inventory blocks crafting instead of destroying ingredients", () => {
  const inventory = inv.createInventory();
  for (let i = 0; i < inv.slotCount; i += 1) {
    inventory.slots[i] = { id: config.blocks.stone, count: 64 };
  }
  inv.addItem(inventory, config.blocks.wood, 0);
  // Free exactly enough room for the wood, then attempt a recipe whose output cannot fit.
  inventory.slots[0] = { id: config.blocks.wood, count: 1 };
  const planks = crafting.getRecipe("planks");
  const result = crafting.craft(inventory, planks, false);
  assert.equal(result.ok, false);
  assert.equal(inv.countItem(inventory, config.blocks.wood), 1);
});
