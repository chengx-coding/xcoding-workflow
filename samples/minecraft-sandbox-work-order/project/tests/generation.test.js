const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");

const GROUND = Math.floor(config.worldHeight * 0.65);

test("the same seed reproduces the same terrain", () => {
  const first = worldApi.createWorld(424242);
  const second = worldApi.createWorld(424242);
  assert.equal(Array.from(first.data).join(","), Array.from(second.data).join(","));
  assert.equal(first.seed, second.seed);
});

test("different seeds produce meaningfully different worlds", () => {
  const first = worldApi.createWorld(11);
  const second = worldApi.createWorld(12);
  let differences = 0;
  for (let index = 0; index < first.data.length; index += 1) {
    if (first.data[index] !== second.data[index]) {
      differences += 1;
    }
  }
  assert.ok(differences > 20, "expected the two seeds to differ in more than 20 cells");
});

test("column 10 keeps the seed ground-line contract for several seeds", () => {
  const seeds = [0, 7, 20261029, 999999];
  for (const seed of seeds) {
    const world = worldApi.createWorld(seed);
    assert.equal(worldApi.getBlock(world, 10, GROUND), config.blocks.grass, "grass at the base row");
    assert.equal(worldApi.getBlock(world, 10, GROUND + 1), config.blocks.dirt, "dirt below the surface");
    assert.equal(worldApi.getBlock(world, 10, world.height - 1), config.blocks.stone, "stone at the bottom");
    assert.equal(worldApi.getBlock(world, 10, 0), config.blocks.air, "sky at the top");
  }
});

test("the world contains trees, leaves and varied surface heights", () => {
  const world = worldApi.createWorld(config.seed);
  let wood = 0;
  let leaves = 0;
  const heights = new Set();
  for (let index = 0; index < world.data.length; index += 1) {
    if (world.data[index] === config.blocks.wood) {
      wood += 1;
    }
    if (world.data[index] === config.blocks.leaves) {
      leaves += 1;
    }
  }
  for (let x = 0; x < world.width; x += 1) {
    heights.add(worldApi.surfaceHeightAt(world, x));
  }
  assert.ok(wood > 0, "expected at least one tree trunk");
  assert.ok(leaves > 0, "expected leaf canopy blocks");
  assert.ok(heights.size >= 3, "expected the terrain profile to vary");
});

test("the generated world keeps the bottom rows solid", () => {
  const world = worldApi.createWorld(20261029);
  for (let x = 0; x < world.width; x += 1) {
    assert.equal(worldApi.getBlock(world, x, world.height - 1), config.blocks.stone);
    assert.equal(worldApi.getBlock(world, x, world.height - 2), config.blocks.stone);
  }
});

test("surface offset is exactly zero at column 10", () => {
  for (const seed of [0, 1, 2, 12345]) {
    assert.equal(worldApi.surfaceOffset(10, seed), 0);
  }
});
