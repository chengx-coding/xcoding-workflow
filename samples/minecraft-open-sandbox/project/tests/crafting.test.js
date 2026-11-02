const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const playerApi = require("../js/player.js");
const inventoryApi = require("../js/inventory.js");
const crafting = require("../js/crafting.js");

const B = config.blocks;
const I = config.items;
const GROUND = worldApi.GROUND_ROW;

function setup() {
  const world = worldApi.createWorld(config.seed);
  const player = playerApi.createPlayer(24.5, GROUND);
  const inventory = inventoryApi.createInventory();
  return { world, player, inventory };
}

test("the recipe table covers the full material chain", () => {
  assert.ok(crafting.list().length >= 15);
  for (const id of [
    "planks",
    "sticks",
    "workbench",
    "torches",
    "wooden_pickaxe",
    "stone_pickaxe",
    "iron_pickaxe",
    "furnace",
    "iron_ingot",
    "ember_shard",
    "ember_beacon"
  ]) {
    assert.ok(crafting.byId(id), `missing recipe ${id}`);
  }
  assert.equal(crafting.byId("nope"), null);
});

test("hand recipes do not need a station", () => {
  const { inventory } = setup();
  inventoryApi.add(inventory, B.wood, 1);
  const result = crafting.craft(crafting.byId("planks"), inventory, new Set());
  assert.equal(result.ok, true);
  assert.equal(inventoryApi.countOf(inventory, B.planks), 4);
  assert.equal(inventoryApi.countOf(inventory, B.wood), 0);
});

test("workbench recipes require a nearby workbench", () => {
  const { world, player, inventory } = setup();
  inventoryApi.add(inventory, B.planks, 10);
  inventoryApi.add(inventory, I.stick, 5);
  const recipe = crafting.byId("wooden_pickaxe");
  const without = crafting.availability(recipe, inventory, crafting.stationsNear(world, player));
  assert.equal(without.ok, false);
  assert.equal(without.reason, "station");
  worldApi.setBlock(world, 26, GROUND - 1, B.workbench);
  const withBench = crafting.availability(recipe, inventory, crafting.stationsNear(world, player));
  assert.equal(withBench.ok, true);
  const crafted = crafting.craft(recipe, inventory, crafting.stationsNear(world, player));
  assert.equal(crafted.ok, true);
  assert.equal(inventoryApi.countOf(inventory, I.pick_wood), 1);
});

test("missing materials are reported item by item", () => {
  const { inventory } = setup();
  inventoryApi.add(inventory, B.planks, 1);
  const state = crafting.availability(crafting.byId("sticks"), inventory, new Set());
  assert.equal(state.ok, false);
  assert.equal(state.reason, "materials");
  assert.equal(state.missing.length, 1);
  assert.equal(state.missing[0].id, B.planks);
  assert.equal(state.missing[0].need, 2);
});

test("a furnace smelts iron and ember from ore and coal", () => {
  const { world, player, inventory } = setup();
  worldApi.setBlock(world, 26, GROUND - 1, B.furnace);
  const stations = crafting.stationsNear(world, player);
  assert.equal(stations.has("furnace"), true);
  inventoryApi.add(inventory, B.iron_ore, 2);
  inventoryApi.add(inventory, B.ember_ore, 1);
  inventoryApi.add(inventory, I.coal, 3);
  assert.equal(crafting.craft(crafting.byId("iron_ingot"), inventory, stations).ok, true);
  assert.equal(crafting.craft(crafting.byId("ember_shard"), inventory, stations).ok, true);
  assert.equal(inventoryApi.countOf(inventory, I.iron_ingot), 1);
  assert.equal(inventoryApi.countOf(inventory, I.ember_shard), 1);
  assert.equal(inventoryApi.countOf(inventory, I.coal), 1);
});

test("stations only count near the player", () => {
  const { world, player } = setup();
  worldApi.setBlock(world, 24, GROUND - 1, B.workbench);
  worldApi.setBlock(world, 24 + 9, GROUND - 1, B.furnace);
  const stations = crafting.stationsNear(world, player, 4);
  assert.equal(stations.has("workbench"), true);
  assert.equal(stations.has("furnace"), false);
});

test("crafting a beacon consumes all three refined materials", () => {
  const { world, player, inventory } = setup();
  worldApi.setBlock(world, 26, GROUND - 1, B.workbench);
  const stations = crafting.stationsNear(world, player);
  inventoryApi.add(inventory, I.ember_shard, 3);
  inventoryApi.add(inventory, I.iron_ingot, 2);
  inventoryApi.add(inventory, B.stone_bricks, 4);
  const result = crafting.craft(crafting.byId("ember_beacon"), inventory, stations);
  assert.equal(result.ok, true);
  assert.equal(inventoryApi.countOf(inventory, B.beacon), 1);
  assert.equal(inventoryApi.countOf(inventory, I.ember_shard), 0);
});

test("a failed craft does not consume anything", () => {
  const { inventory } = setup();
  inventoryApi.add(inventory, B.wood, 2);
  const state = crafting.availability(crafting.byId("planks"), inventory, new Set());
  assert.equal(state.ok, true);
  const bad = crafting.craft(crafting.byId("workbench"), inventory, new Set());
  assert.equal(bad.ok, false);
  assert.equal(bad.reason, "materials");
  assert.equal(inventoryApi.countOf(inventory, B.wood), 2);
});
