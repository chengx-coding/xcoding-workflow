const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");

test("config exposes the seed contract", () => {
  assert.equal(typeof config.tileSize, "number");
  assert.ok(config.tileSize > 0);
  assert.ok(config.worldWidth > 0);
  assert.ok(config.worldHeight > 0);
  assert.ok(config.gravity > 0);
  assert.equal(config.blocks.air, 0);
  assert.ok(config.blocks.grass > 0);
});

test("createWorld has the configured dimensions and seed", () => {
  const world = worldApi.createWorld(config.seed);
  assert.equal(world.width, config.worldWidth);
  assert.equal(world.height, config.worldHeight);
  assert.equal(world.seed, config.seed >>> 0);
  assert.equal(world.data.length, world.width * world.height);
});

test("the generated world has a ground line and sky", () => {
  const world = worldApi.createWorld(config.seed);
  const ground = Math.floor(world.height * 0.65);
  assert.equal(worldApi.getBlock(world, 0, 0), config.blocks.air);
  assert.equal(worldApi.getBlock(world, 10, ground), config.blocks.grass);
  assert.equal(worldApi.getBlock(world, 10, ground + 1), config.blocks.dirt);
  assert.equal(worldApi.getBlock(world, 10, world.height - 1), config.blocks.stone);
});

test("block access is bounded", () => {
  const world = worldApi.createWorld(config.seed);
  assert.equal(worldApi.getBlock(world, -1, 0), null);
  assert.equal(worldApi.getBlock(world, 0, world.height), null);
  assert.equal(worldApi.setBlock(world, -1, 0, config.blocks.stone), false);
  assert.equal(worldApi.setBlock(world, 4, 4, config.blocks.wood), true);
  assert.equal(worldApi.getBlock(world, 4, 4), config.blocks.wood);
});

test("serialization round-trips blocks and seed", () => {
  const world = worldApi.createWorld(config.seed);
  worldApi.setBlock(world, 12, 12, config.blocks.stone);
  const restored = worldApi.deserializeWorld(worldApi.serializeWorld(world));
  assert.equal(restored.width, world.width);
  assert.equal(restored.height, world.height);
  assert.equal(restored.seed, world.seed);
  assert.equal(worldApi.getBlock(restored, 12, 12), config.blocks.stone);
});

test("solidity treats air as walkable", () => {
  const world = worldApi.createWorld(config.seed);
  assert.equal(worldApi.isSolid(world, 0, 0), false);
  assert.equal(worldApi.isSolid(world, 0, world.height - 1), true);
});
