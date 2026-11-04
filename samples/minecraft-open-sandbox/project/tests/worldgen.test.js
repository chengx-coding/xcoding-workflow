const test = require("node:test");
const assert = require("node:assert/strict");
const config = require("../js/config.js");
const worldApi = require("../js/world.js");

function count(world, id) {
  return worldApi.countBlock(world, id);
}

test("the same seed produces the same terrain, a different seed does not", () => {
  const a = worldApi.createWorld(1337);
  const b = worldApi.createWorld(1337);
  const c = worldApi.createWorld(1338);
  assert.deepEqual(Array.from(a.data), Array.from(b.data));
  assert.notDeepEqual(Array.from(a.data), Array.from(c.data));
  assert.equal(a.spawn.x, b.spawn.x);
});

test("the generated world has varied terrain, caves, ore, trees and water", () => {
  const world = worldApi.createWorld(config.seed);
  const heights = new Set();
  for (let x = config.spawnPlateau + 2; x < world.width - 2; x += 1) {
    heights.add(world.surface[x]);
  }
  assert.ok(heights.size > 3, "terrain height should vary");

  let caveAir = 0;
  for (let x = 2; x < world.width - 2; x += 1) {
    for (let y = world.surface[x] + 4; y < world.height - 3; y += 1) {
      if (worldApi.getBlock(world, x, y) === config.blocks.air) {
        caveAir += 1;
      }
    }
  }
  assert.ok(caveAir > 50, "caves should carve underground air");
  assert.ok(count(world, config.blocks.coalOre) > 20, "coal should generate");
  assert.ok(count(world, config.blocks.ironOre) > 20, "iron should generate");
  assert.ok(count(world, config.blocks.wood) > 10, "trees should generate logs");
  assert.ok(count(world, config.blocks.leaves) > 20, "trees should generate leaves");
  assert.ok(count(world, config.blocks.water) > 0, "water should generate");
});

test("spawn is on solid ground above the water line", () => {
  for (const seed of [config.seed, 42, 777, 5]) {
    const world = worldApi.createWorld(seed);
    const x = Math.floor(world.spawn.x);
    const y = world.spawn.y;
    assert.ok(worldApi.isSolid(world, x, y));
    assert.equal(worldApi.getBlock(world, x, y - 1), config.blocks.air);
    assert.ok(y < config.seaLevel + 4, "spawn should not be in deep water");
  }
});

test("the seed's plateau contract is preserved for the first columns", () => {
  const world = worldApi.createWorld(config.seed);
  const ground = Math.floor(world.height * 0.65);
  assert.equal(worldApi.getBlock(world, 0, 0), config.blocks.air);
  assert.equal(worldApi.getBlock(world, 10, ground), config.blocks.grass);
  assert.equal(worldApi.getBlock(world, 10, ground + 1), config.blocks.dirt);
  assert.equal(worldApi.getBlock(world, 10, world.height - 1), config.blocks.stone);
});

test("world edits survive a serialization round trip", () => {
  const world = worldApi.createWorld(config.seed);
  worldApi.setBlock(world, 20, 20, config.blocks.planks);
  const restored = worldApi.deserializeWorld(worldApi.serializeWorld(world));
  assert.equal(worldApi.getBlock(restored, 20, 20), config.blocks.planks);
  assert.equal(restored.width, world.width);
  assert.equal(restored.spawn.y, world.spawn.y);
});

test("block queries classify solids, liquids and replaceables", () => {
  const world = worldApi.createWorld(config.seed);
  assert.equal(worldApi.isSolid(world, 10, 62), true);
  assert.equal(worldApi.isSolid(world, 10, 61), false);
  assert.equal(worldApi.isReplaceable(world, 10, 61), true);
  worldApi.setBlock(world, 10, 61, config.blocks.water);
  assert.equal(worldApi.isLiquid(world, 10, 61), true);
  assert.equal(worldApi.isSolid(world, 10, 61), false);
});
