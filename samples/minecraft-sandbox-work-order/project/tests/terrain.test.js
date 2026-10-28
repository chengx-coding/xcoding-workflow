const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");

test("terrain generation is deterministic for the same seed", () => {
  const first = worldApi.createWorld(123456);
  const second = worldApi.createWorld(123456);

  assert.equal(first.seed, 123456);
  assert.equal(first.width, config.worldWidth);
  assert.equal(first.height, config.worldHeight);
  assert.equal(first.data.length, first.width * first.height);
  assert.deepEqual(Array.from(first.data), Array.from(second.data));
});

test("different seeds generate different terrain", () => {
  const firstSeed = 11;
  const secondSeed = 12;
  let differences = 0;

  for (let x = 30; x < config.worldWidth - 8; x += 1) {
    if (worldApi.surfaceHeightAt(firstSeed, x) !== worldApi.surfaceHeightAt(secondSeed, x)) {
      differences += 1;
    }
  }

  assert.ok(differences >= 8, `expected hill differences, saw ${differences}`);
  assert.notDeepEqual(
    Array.from(worldApi.createWorld(firstSeed).data),
    Array.from(worldApi.createWorld(secondSeed).data)
  );
});

test("the spawn plateau keeps the seed ground line and layers", () => {
  const world = worldApi.createWorld(config.seed);
  const ground = Math.floor(world.height * 0.65);

  for (const x of [0, 10, 12, 20, 24]) {
    assert.equal(worldApi.surfaceHeightAt(world, x), ground);
    assert.equal(worldApi.getBlock(world, x, ground - 1), config.blocks.air);
    assert.equal(worldApi.getBlock(world, x, ground), config.blocks.grass);
    assert.equal(worldApi.getBlock(world, x, ground + 1), config.blocks.dirt);
    assert.equal(worldApi.getBlock(world, x, world.height - 1), config.blocks.stone);
  }
});

test("hills keep grass on top and dirt above stone", () => {
  const world = worldApi.createWorld(config.seed);
  let checked = 0;

  for (let x = 30; x < config.worldWidth - 8 && checked < 6; x += 1) {
    const surface = worldApi.surfaceHeightAt(world, x);
    if (worldApi.getBlock(world, x, surface - 1) !== config.blocks.air) {
      continue;
    }
    assert.equal(worldApi.getBlock(world, x, surface), config.blocks.grass);
    assert.equal(worldApi.getBlock(world, x, surface + 1), config.blocks.dirt);
    assert.equal(worldApi.getBlock(world, x, surface + 4), config.blocks.stone);
    checked += 1;
  }

  assert.ok(checked >= 3, `expected to inspect hills, inspected ${checked}`);
});

test("terrain contains reachable wood from a tree", () => {
  const world = worldApi.createWorld(config.seed);
  const ground = Math.floor(world.height * 0.65);

  assert.equal(worldApi.getBlock(world, 18, ground - 1), config.blocks.wood);
  assert.equal(worldApi.getBlock(world, 18, ground - 2), config.blocks.wood);
});
