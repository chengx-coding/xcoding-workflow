const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const inventory = require("../js/inventory.js");
const mining = require("../js/mining.js");

const B = config.blocks;
const GROUND = Math.floor(config.worldHeight * 0.65);
const STONE_TILE = GROUND + 3;

function flatWorld() {
  return worldApi.createWorld(config.seed);
}

function emptyBag() {
  return inventory.createInventory();
}

test("stone target info depends on the held pickaxe", () => {
  const world = flatWorld();
  const bag = emptyBag();
  const bare = mining.targetInfo(world, bag, 10, STONE_TILE);
  assert.equal(bare.ok, true);
  assert.equal(bare.canHarvest, false);
  assert.equal(bare.time, 1.6);

  inventory.add(bag, 110, 1);
  const wooden = mining.targetInfo(world, bag, 10, STONE_TILE);
  assert.equal(wooden.canHarvest, true);
  assert.ok(wooden.time < 1, "a wooden pickaxe should mine stone faster than bare hands");

  inventory.add(bag, 111, 1);
  const stone = mining.targetInfo(world, bag, 10, STONE_TILE);
  assert.ok(stone.time < wooden.time, "a stone pickaxe should beat a wooden one");
  assert.equal(stone.drop, B.cobblestone);
});

test("unbreakable blocks and air cannot be mined", () => {
  const world = flatWorld();
  const bag = emptyBag();
  worldApi.setBlock(world, 10, world.height - 1, B.bedrock);
  assert.equal(mining.targetInfo(world, bag, 10, world.height - 1).reason, "unbreakable");
  assert.equal(mining.targetInfo(world, bag, 10, 0).reason, "empty");
});

test("holding a mine action fills progress over the expected time", () => {
  const world = flatWorld();
  const bag = emptyBag();
  inventory.add(bag, 110, 1);
  const state = mining.createMining();
  const info = mining.targetInfo(world, bag, 10, STONE_TILE);
  let elapsed = 0;
  let done = false;
  while (!done && elapsed < 5) {
    const step = mining.advance(state, world, bag, 10, STONE_TILE, 0.1);
    done = step.done;
    elapsed += 0.1;
  }
  assert.equal(done, true);
  assert.ok(Math.abs(elapsed - info.time) <= 0.11, "break time should match hardness / tool speed");
});

test("switching targets resets mining progress", () => {
  const world = flatWorld();
  const bag = emptyBag();
  inventory.add(bag, 110, 1);
  const state = mining.createMining();
  mining.advance(state, world, bag, 10, STONE_TILE, 0.4);
  assert.ok(state.progress > 0);
  mining.advance(state, world, bag, 11, STONE_TILE, 0.05);
  assert.ok(state.progress < 0.4);
});

test("breaking a block removes it, drops the right item and records the tool rule", () => {
  const world = flatWorld();
  const bag = emptyBag();
  const bare = mining.breakBlock(world, bag, 10, STONE_TILE);
  assert.equal(bare.ok, true);
  assert.equal(bare.drop, 0);
  assert.equal(bare.reason, "tool-too-weak");
  assert.equal(worldApi.getBlock(world, 10, STONE_TILE), B.air);

  inventory.add(bag, 110, 1);
  const withPick = mining.breakBlock(world, bag, 10, STONE_TILE + 1);
  assert.equal(withPick.drop, B.cobblestone);
  assert.equal(inventory.count(bag, B.cobblestone), 1);
});

test("reach is measured from the player centre", () => {
  const player = { x: 10.5, y: GROUND, height: 1.78 };
  assert.equal(mining.reachable(player, 12, GROUND - 1), true);
  assert.equal(mining.reachable(player, 30, GROUND - 1), false);
});
