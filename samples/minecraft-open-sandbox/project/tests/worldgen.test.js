const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");

test("generation is deterministic for the same seed", () => {
  const a = worldApi.createWorld(123456);
  const b = worldApi.createWorld(123456);
  assert.equal(a.width, config.worldWidth);
  assert.equal(a.height, config.worldHeight);
  assert.deepEqual(Array.from(a.data), Array.from(b.data));
  const c = worldApi.createWorld(654321);
  assert.notDeepEqual(Array.from(a.data), Array.from(c.data));
});

test("the seed-test anchor at column 10 is preserved", () => {
  const world = worldApi.createWorld(config.seed);
  const ground = Math.floor(world.height * 0.65);
  assert.equal(worldApi.getBlock(world, 10, ground), config.blocks.grass);
  assert.equal(worldApi.getBlock(world, 10, ground + 1), config.blocks.dirt);
  assert.equal(worldApi.getBlock(world, 10, ground + 2), config.blocks.dirt);
  assert.equal(worldApi.getBlock(world, 10, world.height - 1), config.blocks.stone);
  assert.equal(worldApi.getBlock(world, 0, 0), config.blocks.air);
});

test("the world contains surface, caves, ores, trees and water", () => {
  const world = worldApi.createWorld(config.seed);
  const counts = {};
  for (let i = 0; i < world.data.length; i += 1) {
    counts[world.data[i]] = (counts[world.data[i]] || 0) + 1;
  }
  assert.ok(counts[config.blocks.grass] > 50, "expected a grass surface");
  assert.ok(counts[config.blocks.stone] > 1000, "expected a stone underground");
  assert.ok(counts[config.blocks.coal] > 5, "expected coal ore");
  assert.ok(counts[config.blocks.crystal] > 0, "expected crystal ore");
  assert.ok(counts[config.blocks.wood] > 4, "expected trees");
  assert.ok(counts[config.blocks.leaves] > 10, "expected canopies");
  assert.ok(counts[config.blocks.water] > 20, "expected static lakes");
});

test("caves carve air below the surface but not the anchor column", () => {
  const world = worldApi.createWorld(config.seed);
  let undergroundAir = 0;
  for (let x = 20; x < world.width - 20; x += 1) {
    for (let y = Math.floor(world.height * 0.75); y < world.height - 2; y += 1) {
      if (worldApi.getBlock(world, x, y) === config.blocks.air) {
        undergroundAir += 1;
      }
    }
  }
  assert.ok(undergroundAir > 60, "expected carved caves, got " + undergroundAir);
  assert.equal(worldApi.getBlock(world, 10, Math.floor(world.height * 0.65)), config.blocks.grass);
  assert.equal(worldApi.getBlock(world, 10, Math.floor(world.height * 0.65) + 1), config.blocks.dirt);
});

test("the bottom row is unbreakable stone and the spawn is safe", () => {
  const world = worldApi.createWorld(config.seed);
  for (let x = 0; x < world.width; x += 1) {
    assert.equal(worldApi.getBlock(world, x, world.height - 1), config.blocks.stone);
    assert.equal(worldApi.isUnbreakable(world, x, world.height - 1), true);
  }
  const spawn = worldApi.getSpawn(world);
  assert.equal(worldApi.getBlock(world, spawn.x, spawn.y), config.blocks.grass);
  assert.equal(worldApi.getBlock(world, spawn.x, spawn.y - 1), config.blocks.air);
  assert.equal(worldApi.getBlock(world, spawn.x, spawn.y - 2), config.blocks.air);
  assert.equal(worldApi.getBlock(world, spawn.x + 4, spawn.y - 1), config.blocks.wood);
});

test("RLE encodes and decodes the world losslessly and rejects bad runs", () => {
  const world = worldApi.createWorld(config.seed);
  const runs = worldApi.encodeRle(world.data);
  assert.ok(Array.isArray(runs));
  const restored = worldApi.decodeRle(runs, world.data.length);
  assert.deepEqual(Array.from(restored), Array.from(world.data));
  assert.throws(() => worldApi.decodeRle([[1, 5]], 100), /cover/);
  assert.throws(() => worldApi.decodeRle([[99, 100]], 100), /Unknown block/);
  assert.throws(() => worldApi.decodeRle([[1, 0]], 100), /values/);
});

test("block access and solidity remain bounded and meaningful", () => {
  const world = worldApi.createWorld(config.seed);
  assert.equal(worldApi.getBlock(world, -1, 0), null);
  assert.equal(worldApi.getBlock(world, 0, world.height), null);
  assert.equal(worldApi.setBlock(world, -1, 0, config.blocks.stone), false);
  assert.equal(worldApi.setBlock(world, 4, 4, config.blocks.wood), true);
  assert.equal(worldApi.getBlock(world, 4, 4), config.blocks.wood);
  assert.equal(worldApi.isSolid(world, 4, 4), true);
  assert.equal(worldApi.isSolid(world, 0, 0), false);
  assert.equal(worldApi.isWater(world, 10, world.height - 1), false);
});
