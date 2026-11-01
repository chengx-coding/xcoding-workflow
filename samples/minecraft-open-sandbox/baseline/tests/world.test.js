const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const content = require("../js/content.js");
const worldApi = require("../js/world.js");

const B = config.block;

test("world generation is deterministic for a seed", () => {
  const first = worldApi.createWorld(12345);
  const second = worldApi.createWorld(12345);
  assert.equal(first.seed, 12345);
  assert.equal(first.width, config.worldWidth);
  assert.equal(first.height, config.worldHeight);
  assert.deepEqual(Array.from(first.surface), Array.from(second.surface));
  assert.deepEqual(first.spawn, second.spawn);
  assert.deepEqual(Array.from(first.data), Array.from(second.data));
});

test("the generated world has a playable spawn and abundant terrain", () => {
  const world = worldApi.createWorld(12345);
  assert.ok(world.spawn.x > 1 && world.spawn.x < world.width - 1);
  assert.ok(world.spawn.y > 3 && world.spawn.y < world.height - 3);
  const spawnX = Math.floor(world.spawn.x);
  assert.equal(worldApi.getBlock(world, spawnX, world.spawn.y), B.GRASS);
  assert.equal(worldApi.getBlock(world, spawnX, world.spawn.y - 1), B.AIR);
  assert.equal(worldApi.getBlock(world, spawnX, world.spawn.y - 2), B.AIR);

  assert.ok(worldApi.countBlocks(world, B.STONE) > 1000);
  assert.ok(worldApi.countBlocks(world, B.LOG) > 20);
  assert.ok(worldApi.countBlocks(world, B.LEAVES) > 80);
  assert.ok(worldApi.countBlocks(world, B.COAL_ORE) > 40);
  assert.ok(worldApi.countBlocks(world, B.IRON_ORE) > 30);
  assert.ok(worldApi.countBlocks(world, B.BEDROCK) > 100);
});

test("the world contains caves, a spawn stair, camp light, and a cave mark", () => {
  const world = worldApi.createWorld(777);
  const center = Math.floor(world.width / 2);
  assert.ok(world.meta.stairStartX > center);
  assert.ok(world.meta.stairStartX < center + 15);

  let undergroundAir = 0;
  for (let x = world.meta.stairStartX; x < Math.min(world.width - 2, world.meta.stairStartX + 30); x += 1) {
    for (let y = world.surface[x] + 2; y < world.surface[x] + 12; y += 1) {
      if (worldApi.getBlock(world, x, y) === B.AIR) {
        undergroundAir += 1;
      }
    }
  }
  assert.ok(undergroundAir > 20);

  let campfire = 0;
  let torch = 0;
  for (let x = center - 8; x <= center + 10; x += 1) {
    for (let y = 20; y < 60; y += 1) {
      const block = worldApi.getBlock(world, x, y);
      if (block === B.CAMPFIRE) {
        campfire += 1;
      }
      if (block === B.TORCH) {
        torch += 1;
      }
    }
  }
  assert.equal(campfire, 1);
  assert.equal(torch, 1);
});

test("block access and updates are bounded", () => {
  const world = worldApi.createWorld(41);
  assert.equal(worldApi.getBlock(world, -1, 0), null);
  assert.equal(worldApi.getBlock(world, 0, world.height), null);
  assert.equal(worldApi.setBlock(world, -1, 0, B.STONE), false);
  assert.equal(worldApi.setBlock(world, 4, 4, B.PLANKS), true);
  assert.equal(worldApi.getBlock(world, 4, 4), B.PLANKS);
  assert.equal(worldApi.isSolid(world, 4, 4), true);
  assert.equal(worldApi.isSolid(world, -1, 4), true);
  assert.equal(worldApi.isSolid(world, 4, -1), false);
});

test("serialization round-trips the block data, surface, and spawn", () => {
  const world = worldApi.createWorld(2024);
  worldApi.setBlock(world, 10, 10, B.BRICK);
  worldApi.setBlock(world, 11, 10, B.LANTERN);
  const payload = worldApi.worldToSave(world);
  const restored = worldApi.worldFromSave(payload);
  assert.equal(restored.width, world.width);
  assert.equal(restored.height, world.height);
  assert.equal(restored.seed, world.seed);
  assert.deepEqual(Array.from(restored.surface), Array.from(world.surface));
  assert.deepEqual(Array.from(restored.data), Array.from(world.data));
  assert.deepEqual(restored.spawn, world.spawn);
});

test("run-length decoding rejects malformed payloads", () => {
  assert.throws(() => worldApi.decodeRuns([1, 2, 3], 4), /invalid/i);
  assert.throws(() => worldApi.decodeRuns([1, 2], 3), /too short/i);
  assert.throws(() => worldApi.decodeRuns([99, 1], 1), /invalid/i);
  assert.throws(() => worldApi.worldFromSave({}), /dimensions/i);
});

test("ores, wood, and foliage use valid content definitions", () => {
  for (const name of ["COAL_ORE", "IRON_ORE", "GEM_ORE", "LOG", "LEAVES", "BEDROCK"]) {
    const def = content.getBlockDef(B[name]);
    assert.ok(def && def.name, name);
  }
  const drops = content.rollDrops(B.COAL_ORE, () => 0.1);
  assert.ok(drops.length > 0);
  assert.equal(drops[0].item, "coal");
  assert.ok(drops[0].count >= 1);
  assert.deepEqual(content.rollDrops(B.BEDROCK, () => 0.5), []);
});
