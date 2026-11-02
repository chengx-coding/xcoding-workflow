const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const inventory = require("../js/inventory.js");
const crafting = require("../js/crafting.js");
const tasks = require("../js/tasks.js");

const B = config.blocks;

function bagWith(entries) {
  const bag = inventory.createInventory();
  Object.keys(entries).forEach(function (key) {
    inventory.add(bag, Number(key), entries[key]);
  });
  return bag;
}

function readyProgress() {
  const progress = tasks.createProgress();
  progress.collected[B.cobblestone] = 8;
  progress.collected[101] = 2;
  progress.collected[102] = 4;
  progress.collected[B.planks] = 8;
  return progress;
}

test("planks convert wood into building material", () => {
  const bag = bagWith({ [B.wood]: 2 });
  const recipe = crafting.recipeById("planks");
  const result = crafting.craft(bag, recipe, tasks.createProgress());
  assert.equal(result.ok, true);
  assert.equal(inventory.count(bag, B.wood), 1);
  assert.equal(inventory.count(bag, B.planks), 4);
});

test("crafting consumes every ingredient and refuses when short", () => {
  const bag = bagWith({ [B.planks]: 3, 100: 2 });
  const recipe = crafting.recipeById("wooden_pickaxe");
  const progress = tasks.createProgress();
  progress.collected[B.planks] = 3;
  const result = crafting.craft(bag, recipe, progress);
  assert.equal(result.ok, true);
  assert.equal(inventory.count(bag, B.planks), 0);
  assert.equal(inventory.count(bag, 100), 0);
  assert.equal(inventory.count(bag, 110), 1);

  const again = crafting.craft(bag, recipe, progress);
  assert.equal(again.ok, false);
  assert.equal(again.reason, "missing");
});

test("recipes stay locked until their material has been collected", () => {
  const bag = bagWith({ [B.cobblestone]: 5, 100: 2 });
  const progress = tasks.createProgress();
  const locked = crafting.craft(bag, crafting.recipeById("stone_pickaxe"), progress);
  assert.equal(locked.ok, false);
  assert.equal(locked.reason, "locked");

  progress.collected[B.cobblestone] = 1;
  const unlocked = crafting.craft(bag, crafting.recipeById("stone_pickaxe"), progress);
  assert.equal(unlocked.ok, true);
  assert.equal(inventory.count(bag, 111), 1);
});

test("torches need coal and sticks", () => {
  const bag = bagWith({ 100: 2, 101: 1 });
  const progress = tasks.createProgress();
  progress.collected[101] = 1;
  const result = crafting.craft(bag, crafting.recipeById("torch"), progress);
  assert.equal(result.ok, true);
  assert.equal(inventory.count(bag, B.torch), 4);
});

test("the recipe list reports unlock and affordability state", () => {
  const bag = bagWith({ [B.wood]: 1 });
  const progress = tasks.createProgress();
  const visible = crafting.visible(bag, progress);
  const planks = visible.find(function (entry) { return entry.recipe.id === "planks"; });
  const sticks = visible.find(function (entry) { return entry.recipe.id === "sticks"; });
  const iron = visible.find(function (entry) { return entry.recipe.id === "iron_pickaxe"; });
  assert.equal(planks.unlocked, true);
  assert.equal(planks.canCraft, true);
  assert.equal(sticks.unlocked, false);
  assert.equal(iron.unlocked, false);
  assert.ok(visible.length >= 10);
});

test("iron tools need collected iron", () => {
  const bag = bagWith({ 102: 4, 100: 2 });
  const progress = tasks.createProgress();
  const result = crafting.craft(bag, crafting.recipeById("iron_pickaxe"), progress);
  assert.equal(result.ok, false);
  progress.collected[102] = 1;
  const retry = crafting.craft(bag, crafting.recipeById("iron_pickaxe"), progress);
  assert.equal(retry.ok, true);
  assert.equal(inventory.count(bag, 112), 1);
});

test("crafted pickaxes satisfy the progression task", () => {
  const progress = readyProgress();
  progress.crafted.wooden_pickaxe = 1;
  const completed = tasks.sync(progress);
  const ids = completed.map(function (task) { return task.id; });
  assert.ok(ids.indexOf("make_pickaxe") >= 0);
});
