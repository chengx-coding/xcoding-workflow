const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");

function countBlocks(world) {
  const counts = {};
  for (let index = 0; index < world.data.length; index += 1) {
    const block = world.data[index];
    counts[block] = (counts[block] || 0) + 1;
  }
  return counts;
}

function airBelowSurface(world) {
  const surface = worldApi.surfaceMap(world);
  let air = 0;
  for (let x = 0; x < world.width; x += 1) {
    for (let y = surface[x] + 6; y < world.height; y += 1) {
      if (world.data[y * world.width + x] === config.blocks.air) {
        air += 1;
      }
    }
  }
  return air;
}

test("the same seed rebuilds an identical world", () => {
  const first = worldApi.createWorld(4242);
  const second = worldApi.createWorld(4242);
  assert.equal(first.seed, second.seed);
  assert.deepEqual(Array.from(first.data), Array.from(second.data));
});

test("different seeds generate different terrain", () => {
  const first = worldApi.createWorld(1);
  const second = worldApi.createWorld(2);
  let differences = 0;
  for (let index = 0; index < first.data.length; index += 1) {
    if (first.data[index] !== second.data[index]) {
      differences += 1;
    }
  }
  assert.ok(differences > 500, "expected hundreds of differing cells, saw " + differences);
});

test("generated worlds contain grass, dirt, stone, sand and wood", () => {
  const counts = countBlocks(worldApi.createWorld(config.seed));
  assert.ok(counts[config.blocks.grass] > 50);
  assert.ok(counts[config.blocks.dirt] > 50);
  assert.ok(counts[config.blocks.stone] > 500);
  assert.ok(counts[config.blocks.sand] > 0);
  assert.ok(counts[config.blocks.wood] > 0);
  assert.ok(counts[config.blocks.leaves] > 0);
});

test("the spawn plateau stays flat and clear of trees", () => {
  const world = worldApi.createWorld(config.seed);
  const base = Math.floor(world.height * 0.65);
  for (let x = 0; x < 20; x += 1) {
    assert.equal(worldApi.getBlock(world, x, base), config.blocks.grass);
    assert.equal(worldApi.getBlock(world, x, base - 1), config.blocks.air);
  }
});

test("caves open air pockets below the surface", () => {
  const world = worldApi.createWorld(config.seed);
  assert.ok(airBelowSurface(world) > 100, "expected cave pockets below the surface");
});

test("the bedrock floor is solid", () => {
  const world = worldApi.createWorld(config.seed);
  for (let x = 0; x < world.width; x += 1) {
    assert.ok(worldApi.isSolid(world, x, world.height - 1));
    assert.ok(worldApi.isSolid(world, x, world.height - 2));
  }
});

test("surfaceMap reports the top terrain block per column", () => {
  const world = worldApi.createWorld(config.seed);
  const surface = worldApi.surfaceMap(world);
  assert.equal(surface.length, world.width);
  for (let x = 0; x < world.width; x += 1) {
    assert.ok(worldApi.isTerrainBlock(worldApi.getBlock(world, x, surface[x])));
    for (let y = 0; y < surface[x]; y += 1) {
      assert.ok(
        !worldApi.isTerrainBlock(worldApi.getBlock(world, x, y)),
        "no terrain above the reported surface in column " + x
      );
    }
  }
});

test("findSpawn returns a clear spot above solid terrain", () => {
  const world = worldApi.createWorld(config.seed);
  const spawn = worldApi.findSpawn(world);
  assert.ok(spawn.x > 0 && spawn.x < world.width);
  assert.ok(spawn.y > 0 && spawn.y < world.height);
  assert.ok(worldApi.isSolid(world, Math.floor(spawn.x), spawn.y));
  assert.equal(worldApi.getBlock(world, Math.floor(spawn.x), spawn.y - 1), config.blocks.air);
  assert.equal(worldApi.getBlock(world, Math.floor(spawn.x), spawn.y - 2), config.blocks.air);
});

test("terrainHeight is deterministic and stays in the world", () => {
  const first = worldApi.terrainHeight(31415, 60);
  assert.equal(first, worldApi.terrainHeight(31415, 60));
  for (let x = 0; x < config.worldWidth; x += 1) {
    const height = worldApi.terrainHeight(31415, x);
    assert.ok(height >= 18 && height <= config.worldHeight - 12);
  }
});

test("worlds carry their normalised seed", () => {
  assert.equal(worldApi.createWorld(-1).seed, 0xffffffff);
  assert.equal(worldApi.createWorld("42").seed, 42);
});
