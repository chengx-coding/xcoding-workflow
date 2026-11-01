const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const mining = require("../js/mining.js");

function testWorld() {
  const world = worldApi.createWorld(config.seed);
  const spawn = worldApi.getSpawn(world);
  const player = {
    x: spawn.x + 0.5,
    y: spawn.y,
    width: 0.7,
    height: 1.8
  };
  return { world: world, spawn: spawn, player: player };
}

function findStone(world, x, fromY) {
  for (let y = fromY; y < world.height - 1; y += 1) {
    if (worldApi.getBlock(world, x, y) === config.blocks.stone) {
      return y;
    }
  }
  return -1;
}

test("hand rules allow soft blocks and refuse stone", () => {
  const { world, spawn } = testWorld();
  const grass = mining.blockRule(world, spawn.x, spawn.y, []);
  assert.equal(grass.allowed, true);
  assert.ok(grass.seconds > 0.1 && grass.seconds < 0.4);
  const stoneX = spawn.x + 10;
  const stoneY = findStone(world, stoneX, spawn.y + 4);
  assert.ok(stoneY > 0, "expected stone below the surface");
  const stone = mining.blockRule(world, stoneX, stoneY, []);
  assert.equal(stone.allowed, false);
  assert.equal(stone.reason, "tool");
});

test("pickaxe tiers gate stone and crystal with different speeds", () => {
  const { world, spawn } = testWorld();
  const stoneX = spawn.x + 10;
  const stoneY = findStone(world, stoneX, spawn.y + 4);
  assert.ok(stoneY > 0, "expected stone below the surface");
  const wooden = mining.blockRule(world, stoneX, stoneY, ["wood_pickaxe"]);
  assert.equal(wooden.allowed, true);
  const stoneTool = mining.blockRule(world, stoneX, stoneY, ["stone_pickaxe"]);
  assert.equal(stoneTool.allowed, true);
  assert.ok(stoneTool.seconds < wooden.seconds);

  worldApi.setBlock(world, stoneX, stoneY, config.blocks.crystal);
  assert.equal(mining.blockRule(world, stoneX, stoneY, ["wood_pickaxe"]).allowed, false);
  assert.equal(mining.blockRule(world, stoneX, stoneY, ["stone_pickaxe"]).allowed, true);
});

test("reach is limited to the configured distance", () => {
  const { player } = testWorld();
  assert.equal(mining.canReach(player, Math.floor(player.x) + 5, Math.floor(player.y) - 1), true);
  assert.equal(mining.canReach(player, Math.floor(player.x) + 7, Math.floor(player.y) - 1), false);
});

test("mining progresses, resets on a new target and completes with a drop", () => {
  const { world, spawn, player } = testWorld();
  const state = mining.createMining();
  const result = mining.updateMining(state, world, player, spawn.x, spawn.y, [], 0.1, true);
  assert.equal(result.active, true);
  assert.ok(result.progress > 0 && result.progress < 1);
  assert.equal(result.rule.drop, config.items.dirt);

  const reset = mining.updateMining(state, world, player, spawn.x - 1, spawn.y - 1, [], 0.1, true);
  assert.notEqual(state.progress, result.progress);

  let completed = false;
  for (let i = 0; i < 100 && !completed; i += 1) {
    const frame = mining.updateMining(state, world, player, spawn.x, spawn.y, [], 1 / 30, true);
    completed = frame.complete;
  }
  assert.equal(completed, true);
  assert.equal(mining.blockRule(world, spawn.x, spawn.y, []).allowed, true);
});

test("unbreakable and empty targets are refused", () => {
  const { world, spawn } = testWorld();
  const bottom = mining.blockRule(world, 0, world.height - 1, ["stone_pickaxe"]);
  assert.equal(bottom.allowed, false);
  assert.equal(bottom.reason, "unbreakable");
  const sky = mining.blockRule(world, 0, 0, ["stone_pickaxe"]);
  assert.equal(sky.allowed, false);
  assert.equal(sky.reason, "empty");
});
