const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const rng = require("../js/rng.js");
const worldApi = require("../js/world.js");
const inventoryApi = require("../js/inventory.js");
const physicsApi = require("../js/physics.js");
const saveApi = require("../js/save.js");

function makeState(world, inventory) {
  return {
    player: {
      x: world.spawn.x,
      y: world.spawn.y,
      health: 10,
      facing: 1
    },
    inventory: inventory || inventoryApi.createInventory(),
    selected: 0,
    timeOfDay: 0.4,
    stats: saveApi.defaultStats(),
    tutorial: saveApi.defaultTutorial(),
    settings: saveApi.defaultSettings()
  };
}

test("world generation is deterministic for a seed", () => {
  const first = worldApi.createWorld(config.seed);
  const second = worldApi.createWorld(config.seed);
  assert.deepEqual(Buffer.from(first.data), Buffer.from(second.data));
  assert.deepEqual(first.spawn, second.spawn);
  assert.equal(first.seed, config.seed >>> 0);
});

test("terrain layers remain compatible with the seed contract", () => {
  const world = worldApi.createWorld(config.seed);
  const ground = Math.floor(world.height * config.baseGroundRatio);
  assert.equal(worldApi.getBlock(world, 10, ground), config.blocks.grass);
  assert.equal(worldApi.getBlock(world, 10, ground + 1), config.blocks.dirt);
  assert.equal(worldApi.getBlock(world, 10, world.height - 1), config.blocks.stone);
  assert.equal(worldApi.isProtected(world, 10, world.height - 2), true);
});

test("generated world contains caves, ores, trees, and ground cover", () => {
  const world = worldApi.createWorld(config.seed);
  const counts = {};
  for (let index = 0; index < world.data.length; index += 1) {
    counts[world.data[index]] = (counts[world.data[index]] || 0) + 1;
  }
  assert.ok(counts[config.blocks.air] > 0);
  assert.ok(counts[config.blocks.coalOre] > 0);
  assert.ok(counts[config.blocks.ironOre] > 0);
  assert.ok(counts[config.blocks.wood] > 0);
  assert.ok(counts[config.blocks.leaves] > 0);
  assert.ok(counts[config.blocks.flower] + counts[config.blocks.tallGrass] > 0);
});

test("spawn is above solid ground with headroom", () => {
  const world = worldApi.createWorld(config.seed);
  const x = Math.floor(world.spawn.x);
  const y = Math.floor(world.spawn.y);
  assert.equal(worldApi.isSolid(world, x, y), true);
  assert.equal(worldApi.isSolid(world, x, y - 1), false);
  assert.equal(worldApi.isSolid(world, x, y - 2), false);
  assert.equal(worldApi.isSolid(world, x, y - 3), false);
});

test("sky light reaches the surface and caves can be dark", () => {
  const world = worldApi.createWorld(config.seed);
  const surface = world.surface[Math.floor(world.width / 2)];
  assert.equal(worldApi.lightAt(world, Math.floor(world.width / 2), surface - 2, 1), 15);
  let darkCave = null;
  for (let x = 30; x < world.width - 2 && !darkCave; x += 1) {
    for (let y = world.surface[x] + 8; y < world.height - 4; y += 1) {
      if (world.data[y * world.width + x] === config.blocks.air && worldApi.lightAt(world, x, y, 1) === 0) {
        darkCave = { x: x, y: y };
        break;
      }
    }
  }
  assert.ok(darkCave, "expected at least one dark cave pocket");
});

test("a torch adds local block light with falloff", () => {
  const world = worldApi.createWorld(config.seed);
  let x = 40;
  while (worldApi.getBlock(world, x, world.surface[x] - 1) !== config.blocks.air) {
    x += 1;
  }
  const y = world.surface[x] - 1;
  worldApi.setBlock(world, x, y, config.blocks.torch);
  worldApi.updateLight(world);
  assert.equal(worldApi.lightAt(world, x, y, 0.12), 14);
  assert.equal(worldApi.lightAt(world, x + 1, y, 0.12), 13);
  assert.ok(worldApi.lightAt(world, x + 8, y, 0.12) < 7);
});

test("inventory stacks, merges, and refuses overflow", () => {
  const inventory = inventoryApi.createInventory(4);
  let result = inventoryApi.addItem(inventory, "dirt", 50);
  assert.equal(result.remaining, 0);
  result = inventoryApi.addItem(inventory, "dirt", 20);
  assert.equal(result.added, 20);
  assert.equal(inventory.slots[0].count, 64);
  assert.equal(inventory.slots[1].count, 6);
  result = inventoryApi.addItem(inventory, "dirt", 200);
  assert.ok(result.remaining > 0);
  assert.equal(inventoryApi.removeItem(inventory, "dirt", 10), true);
  assert.equal(inventoryApi.countItem(inventory, "dirt"), 246);
});

test("inventory handles single-stack tools and full inventories", () => {
  const inventory = inventoryApi.createInventory(2);
  assert.equal(inventoryApi.addItem(inventory, "wood_pickaxe", 3).added, 2);
  assert.equal(inventoryApi.countItem(inventory, "wood_pickaxe"), 2);
  inventoryApi.addItem(inventory, "stone_pickaxe", 1);
  const result = inventoryApi.addItem(inventory, "dirt", 1);
  assert.equal(result.remaining, 1);
  assert.equal(inventoryApi.firstEmptySlot(inventory), -1);
});

test("starter recipes produce planks, sticks, and a table", () => {
  const inventory = inventoryApi.createInventory();
  inventoryApi.addItem(inventory, "wood", 4);
  const planks = config.recipes.find((recipe) => recipe.id === "planks");
  const sticks = config.recipes.find((recipe) => recipe.id === "sticks");
  const table = config.recipes.find((recipe) => recipe.id === "crafting_table");
  const stations = { none: true, table: false, furnace: false };

  assert.equal(inventoryApi.craftRecipe(inventory, planks, stations).ok, true);
  assert.equal(inventoryApi.countItem(inventory, "planks"), 4);
  assert.equal(inventoryApi.craftRecipe(inventory, planks, stations).ok, true);
  assert.equal(inventoryApi.countItem(inventory, "planks"), 8);
  assert.equal(inventoryApi.craftRecipe(inventory, sticks, stations).ok, true);
  assert.equal(inventoryApi.countItem(inventory, "stick"), 4);
  assert.equal(inventoryApi.craftRecipe(inventory, table, stations).ok, true);
  assert.equal(inventoryApi.countItem(inventory, "crafting_table"), 1);
});

test("table recipes require a nearby table and tier progression works", () => {
  const inventory = inventoryApi.createInventory();
  inventoryApi.addItem(inventory, "planks", 3);
  inventoryApi.addItem(inventory, "stick", 2);
  const recipe = config.recipes.find((item) => item.id === "wood_pickaxe");
  const noStations = { none: true, table: false, furnace: false };
  const withTable = { none: true, table: true, furnace: false };
  const status = inventoryApi.recipeStatus(recipe, inventory, noStations);
  assert.equal(status.ok, false);
  assert.match(status.reason, /crafting table/i);
  assert.equal(inventoryApi.craftRecipe(inventory, recipe, noStations).ok, false);
  assert.equal(inventoryApi.countItem(inventory, "planks"), 3);
  assert.equal(inventoryApi.craftRecipe(inventory, recipe, withTable).ok, true);
  assert.equal(inventoryApi.countItem(inventory, "wood_pickaxe"), 1);
  assert.equal(config.items.wood_pickaxe.tool.tier, 1);
  assert.equal(config.items.stone_pickaxe.tool.tier, 2);
  assert.equal(config.items.iron_pickaxe.tool.tier, 3);
});

test("recipe ids, items, and ingredient ids are internally consistent", () => {
  assert.equal(config.blockDefs.length, Object.keys(config.blocks).length);
  for (const recipe of config.recipes) {
    assert.ok(config.items[recipe.output.id], recipe.id + " output");
    assert.ok(recipe.output.count > 0);
    for (const ingredient of recipe.ingredients) {
      assert.ok(config.items[ingredient.id], recipe.id + " ingredient " + ingredient.id);
      assert.ok(ingredient.count > 0);
    }
    assert.ok(config.stations[recipe.station], recipe.id + " station");
  }
});

test("physics lands a falling player and supports jumping", () => {
  const world = {
    width: 20,
    height: 20,
    data: new Uint8Array(20 * 20)
  };
  for (let x = 0; x < 20; x += 1) {
    world.data[15 * 20 + x] = config.blocks.stone;
  }
  const player = physicsApi.createPlayer(5.5, 10);
  for (let frame = 0; frame < 120; frame += 1) {
    physicsApi.stepPlayer(player, world, {}, 1 / 60);
  }
  assert.equal(player.onGround, true);
  assert.ok(Math.abs(player.y - 15) < 0.02);
  let jumped = false;
  for (let frame = 0; frame < 10; frame += 1) {
    const result = physicsApi.stepPlayer(player, world, { jump: true }, 1 / 60);
    jumped = jumped || result.jumped;
  }
  assert.equal(jumped, true);
  assert.ok(player.y < 15);
  for (let frame = 0; frame < 120; frame += 1) {
    physicsApi.stepPlayer(player, world, {}, 1 / 60);
  }
  assert.equal(player.onGround, true);
});

test("physics stops horizontal movement at solid walls", () => {
  const world = {
    width: 20,
    height: 20,
    data: new Uint8Array(20 * 20)
  };
  for (let x = 0; x < 20; x += 1) {
    world.data[15 * 20 + x] = config.blocks.stone;
  }
  for (let y = 10; y <= 14; y += 1) {
    world.data[y * 20 + 10] = config.blocks.stone;
  }
  const player = physicsApi.createPlayer(5.5, 15);
  for (let frame = 0; frame < 180; frame += 1) {
    physicsApi.stepPlayer(player, world, { right: true }, 1 / 60);
  }
  assert.ok(player.x < 10);
  assert.ok(player.x > 9.4);
});

test("fall damage follows a safe threshold", () => {
  assert.equal(physicsApi.fallDamage(2), 0);
  assert.equal(physicsApi.fallDamage(config.fallSafeDistance), 0);
  assert.equal(physicsApi.fallDamage(10), 5);
  const player = physicsApi.createPlayer(0, 0);
  assert.equal(physicsApi.damagePlayer(player, 3), 3);
  assert.equal(player.health, 7);
  assert.equal(physicsApi.healPlayer(player, 10), 3);
  assert.equal(physicsApi.respawnPlayer(player, { x: 4, y: 8 }).health, 10);
});

test("in-reach and block overlap checks are bounded", () => {
  const player = physicsApi.createPlayer(5.5, 15);
  assert.equal(physicsApi.inReach(player, 5, 13, 2), true);
  assert.equal(physicsApi.inReach(player, 15, 13, 2), false);
  assert.equal(physicsApi.overlapsTile(player, 5, 14), true);
  assert.equal(physicsApi.overlapsTile(player, 7, 14), false);
});

test("save round-trips inventory, player, and block changes", () => {
  const world = worldApi.createWorld(config.seed);
  const inventory = inventoryApi.createInventory();
  inventoryApi.addItem(inventory, "wood", 5);
  inventoryApi.addItem(inventory, "torch", 2);
  const state = makeState(world, inventory);
  state.selected = 3;
  state.player.health = 7;
  state.timeOfDay = 0.81;
  state.stats.blocksMined = 12;
  state.tutorial.completed = ["wood", "planks"];
  const x = Math.floor(world.spawn.x) + 2;
  const y = Math.floor(world.spawn.y) - 3;
  worldApi.setBlock(world, x, y, config.blocks.planks);
  const text = saveApi.encodeSave(state, world);
  const decoded = saveApi.decodeSave(text);
  assert.equal(decoded.seed, world.seed);
  assert.equal(decoded.selected, 3);
  assert.equal(decoded.player.health, 7);
  assert.equal(decoded.timeOfDay, 0.81);
  assert.equal(decoded.stats.blocksMined, 12);
  assert.deepEqual(decoded.tutorial.completed, ["wood", "planks"]);
  const restored = worldApi.createWorld(decoded.seed);
  saveApi.applySaveToWorld(restored, decoded);
  assert.equal(worldApi.getBlock(restored, x, y), config.blocks.planks);
  const restoredInventory = saveApi.inventoryFromSave(decoded);
  assert.equal(inventoryApi.countItem(restoredInventory, "wood"), 5);
  assert.equal(inventoryApi.countItem(restoredInventory, "torch"), 2);
});

test("save decoder rejects malformed and corrupt payloads", () => {
  assert.throws(() => saveApi.decodeSave(""), /No save/);
  assert.throws(() => saveApi.decodeSave("{"), /valid JSON/);
  assert.throws(() => saveApi.decodeSave('{"schema":"emberblock","version":1}'), /seed/);
  const world = worldApi.createWorld(config.seed);
  const state = makeState(world);
  const payload = JSON.parse(saveApi.encodeSave(state, world));
  payload.changes = [[-1, 4, 1]];
  assert.throws(() => saveApi.decodeSave(JSON.stringify(payload)), /outside the world/);
  payload.changes = [[4, 4, 999]];
  assert.throws(() => saveApi.decodeSave(JSON.stringify(payload)), /unknown block/);
  payload.changes = [];
  payload.inventory[0] = ["not_an_item", 1];
  assert.throws(() => saveApi.decodeSave(JSON.stringify(payload)), /unknown item/);
});

test("seeded rng and noise are repeatable", () => {
  const a = rng.mulberry32(1234);
  const b = rng.mulberry32(1234);
  assert.equal(a(), b());
  assert.equal(rng.valueNoise2D(4.2, 9.7, 7), rng.valueNoise2D(4.2, 9.7, 7));
  assert.notEqual(rng.valueNoise2D(4.2, 9.7, 7), rng.valueNoise2D(4.2, 9.7, 8));
});

test("furnace smelting and iron pickaxe use station and material rules", () => {
  const inventory = inventoryApi.createInventory();
  inventoryApi.addItem(inventory, "raw_iron", 3);
  inventoryApi.addItem(inventory, "coal", 3);
  inventoryApi.addItem(inventory, "stick", 2);
  const smelt = config.recipes.find((recipe) => recipe.id === "iron_ingot");
  const pickaxe = config.recipes.find((recipe) => recipe.id === "iron_pickaxe");
  const stations = { none: true, table: true, furnace: true };
  assert.equal(inventoryApi.canCraft(inventory, smelt, stations), true);
  for (let index = 0; index < 3; index += 1) {
    assert.equal(inventoryApi.craftRecipe(inventory, smelt, stations).ok, true);
  }
  assert.equal(inventoryApi.countItem(inventory, "iron_ingot"), 3);
  assert.equal(inventoryApi.countItem(inventory, "raw_iron"), 0);
  assert.equal(inventoryApi.craftRecipe(inventory, pickaxe, stations).ok, true);
  assert.equal(inventoryApi.countItem(inventory, "iron_pickaxe"), 1);
});
