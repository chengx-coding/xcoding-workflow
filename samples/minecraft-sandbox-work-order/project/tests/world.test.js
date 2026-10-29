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

test("config exposes the seed contract", () => {
  assert.equal(typeof config.tileSize, "number");
  assert.ok(config.tileSize > 0);
  assert.ok(config.worldWidth > 0);
  assert.ok(config.worldHeight > 0);
  assert.ok(config.gravity > 0);
  assert.equal(config.blocks.air, 0);
  assert.ok(config.blocks.grass > 0);
  assert.ok(Array.isArray(config.hotbar));
  assert.ok(config.hotbar.length >= 4);
});

test("createWorld has the configured dimensions and seed", () => {
  const world = worldApi.createWorld(config.seed);
  assert.equal(world.width, config.worldWidth);
  assert.equal(world.height, config.worldHeight);
  assert.equal(world.seed, config.seed >>> 0);
  assert.equal(world.data.length, world.width * world.height);
  assert.equal(world.ground.length, world.width);
  assert.equal(world.biomes.length, world.width);
});

test("the generated world has sky, a surface layer and depth", () => {
  const world = worldApi.createWorld(config.seed);
  for (const x of [0, 10, 42, Math.floor(world.width / 2), world.width - 1]) {
    const surface = world.ground[x];
    assert.ok(surface > 5 && surface < world.height - 5);
    assert.equal(worldApi.getBlock(world, x, 0), config.blocks.air);
    assert.ok(
      worldApi.getBlock(world, x, surface) === config.blocks.grass ||
        worldApi.getBlock(world, x, surface) === config.blocks.sand
    );
    assert.ok(
      worldApi.getBlock(world, x, surface + 1) === config.blocks.dirt ||
        worldApi.getBlock(world, x, surface + 1) === config.blocks.sand ||
        worldApi.getBlock(world, x, surface + 1) === config.blocks.stone
    );
    assert.ok(
      worldApi.getBlock(world, x, world.height - 1) === config.blocks.stone ||
        worldApi.getBlock(world, x, world.height - 1) === config.blocks.bedrock
    );
  }
});

test("the same seed is deterministic and another seed changes the terrain", () => {
  const first = worldApi.createWorld(123456);
  const second = worldApi.createWorld(123456);
  const third = worldApi.createWorld(654321);
  assert.deepEqual(Array.from(first.data), Array.from(second.data));
  assert.deepEqual(Array.from(first.ground), Array.from(second.ground));
  let differences = 0;
  for (let index = 0; index < first.data.length; index += 1) {
    if (first.data[index] !== third.data[index]) {
      differences += 1;
    }
  }
  assert.ok(differences > 100, "different seeds should produce meaningfully different terrain");
});

test("required natural blocks, caves and seams are present", () => {
  const world = worldApi.createWorld(config.seed);
  const counts = countBlocks(world);
  assert.ok((counts[config.blocks.grass] || 0) > 50);
  assert.ok((counts[config.blocks.dirt] || 0) > 100);
  assert.ok((counts[config.blocks.stone] || 0) > 500);
  assert.ok((counts[config.blocks.wood] || 0) > 10);
  assert.ok((counts[config.blocks.leaves] || 0) > 20);
  assert.ok((counts[config.blocks.coal] || 0) > 5);
  assert.ok((counts[config.blocks.crystal] || 0) > 2);
  let caveAir = 0;
  for (let x = 0; x < world.width; x += 1) {
    for (let y = world.ground[x] + 4; y < world.height - 2; y += 1) {
      if (worldApi.getBlock(world, x, y) === config.blocks.air) {
        caveAir += 1;
      }
    }
  }
  assert.ok(caveAir > 100, "underground caves should open the stone");
});

test("block access is bounded", () => {
  const world = worldApi.createWorld(config.seed);
  assert.equal(worldApi.getBlock(world, -1, 0), null);
  assert.equal(worldApi.getBlock(world, 0, world.height), null);
  assert.equal(worldApi.setBlock(world, -1, 0, config.blocks.stone), false);
  assert.equal(worldApi.setBlock(world, 4, 4, config.blocks.wood), true);
  assert.equal(worldApi.getBlock(world, 4, 4), config.blocks.wood);
  assert.equal(worldApi.setBlock(world, 4, 4, 255), false);
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

test("deserialize rejects malformed payloads", () => {
  assert.throws(() => worldApi.deserializeWorld(JSON.stringify({ width: 1, height: 1, data: [] })));
  assert.throws(() =>
    worldApi.deserializeWorld(
      JSON.stringify({
        width: config.worldWidth,
        height: config.worldHeight,
        seed: config.seed,
        data: [999]
      })
    )
  );
});

test("solidity treats air as walkable", () => {
  const world = worldApi.createWorld(config.seed);
  assert.equal(worldApi.isSolid(world, 0, 0), false);
  assert.equal(worldApi.isSolid(world, 0, world.height - 1), true);
});

test("findSpawn returns a safe standing position near the anchor", () => {
  const world = worldApi.createWorld(config.seed);
  const spawn = worldApi.findSpawn(world, world.width / 2);
  assert.ok(Number.isFinite(spawn.x));
  assert.ok(Number.isFinite(spawn.y));
  assert.equal(worldApi.isSolid(world, Math.floor(spawn.x), spawn.y), true);
  assert.equal(worldApi.isSolid(world, Math.floor(spawn.x), spawn.y - 1), false);
  assert.equal(worldApi.isSolid(world, Math.floor(spawn.x), spawn.y - 2), false);
});
