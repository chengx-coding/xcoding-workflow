const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const blocks = require("../js/blocks.js");

const SEED_A = 20261102;
const SEED_B = 424242;

function countOf(world, id) {
  let total = 0;
  for (let index = 0; index < world.data.length; index += 1) {
    if (world.data[index] === id) {
      total += 1;
    }
  }
  return total;
}

test("generated world has configured dimensions and spawn", () => {
  const world = worldApi.generateWorld(SEED_A);
  assert.equal(world.width, config.worldWidth);
  assert.equal(world.height, config.worldHeight);
  assert.equal(world.data.length, world.width * world.height);
  assert.equal(world.seed, SEED_A >>> 0);
  assert.ok(world.spawn.x > 0 && world.spawn.x < world.width);
  assert.ok(world.spawn.y > 0 && world.spawn.y < world.height);
  assert.equal(worldApi.isGroundTile(world, Math.floor(world.spawn.x), world.spawn.y), true);
  assert.equal(worldApi.isSolid(world, Math.floor(world.spawn.x), world.spawn.y - 1), false);
});

test("generation is deterministic for one seed and differs across seeds", () => {
  const first = worldApi.generateWorld(SEED_A);
  const second = worldApi.generateWorld(SEED_A);
  const other = worldApi.generateWorld(SEED_B);
  assert.deepEqual(Array.from(first.data), Array.from(second.data));
  assert.deepEqual(Array.from(first.data), Array.from(worldApi.generateWorld(SEED_A).data));
  let differences = 0;
  for (let index = 0; index < first.data.length; index += 1) {
    if (first.data[index] !== other.data[index]) {
      differences += 1;
    }
  }
  assert.ok(differences > 500, "different seeds should produce different worlds");
});

test("the surface varies and stays inside the configured band", () => {
  const world = worldApi.generateWorld(SEED_A);
  const heights = [];
  for (let x = 0; x < world.width; x += 1) {
    const top = worldApi.terrainHeightAt(world, x);
    assert.ok(top >= 20 && top < world.height - 3, "surface height out of band at x=" + x);
    heights.push(top);
  }
  const mean = heights.reduce(function (sum, value) { return sum + value; }, 0) / heights.length;
  const variance = heights.reduce(function (sum, value) {
    return sum + (value - mean) * (value - mean);
  }, 0) / heights.length;
  assert.ok(Math.sqrt(variance) > 1.5, "surface should roll instead of being flat");
  assert.ok(Math.max.apply(null, heights) - Math.min.apply(null, heights) > 8);
});

test("the world contains caves, ores, trees and bedrock", () => {
  const world = worldApi.generateWorld(SEED_A);
  const air = countOf(world, config.blocks.air);
  const skyArea = world.width * 40;
  assert.ok(air > skyArea + 300, "underground caves should remove a meaningful number of tiles");
  assert.ok(countOf(world, config.blocks.coalOre) > 20, "coal ore should generate");
  assert.ok(countOf(world, config.blocks.ironOre) > 8, "iron ore should generate");
  assert.ok(countOf(world, config.blocks.wood) > 20, "trees should generate");
  assert.ok(countOf(world, config.blocks.leaves) > 60, "tree canopies should generate");
  assert.ok(countOf(world, config.blocks.bedrock) >= world.width, "bedrock floor should exist");
  for (let x = 0; x < world.width; x += 7) {
    assert.equal(worldApi.getBlock(world, x, world.height - 1), config.blocks.bedrock);
  }
});

test("ores stay below the surface and biome surfaces use valid blocks", () => {
  const world = worldApi.generateWorld(SEED_A);
  for (let x = 0; x < world.width; x += 1) {
    const top = worldApi.terrainHeightAt(world, x);
    const surfaceId = worldApi.getBlock(world, x, top);
    assert.ok(
      surfaceId === config.blocks.grass || surfaceId === config.blocks.sand || surfaceId === config.blocks.stone,
      "unexpected surface block " + surfaceId + " at x=" + x
    );
    for (let y = top; y < world.height; y += 1) {
      const id = worldApi.getBlock(world, x, y);
      if (id === config.blocks.coalOre) {
        assert.ok(y > top, "coal ore must not sit on the surface");
        assert.ok(y < world.height - 2, "coal ore must not replace bedrock");
      }
      if (id === config.blocks.ironOre) {
        assert.ok(y > Math.round(world.height * 0.6), "iron should be deep");
      }
    }
  }
});

test("block definitions cover every generated block id", () => {
  const world = worldApi.generateWorld(SEED_A);
  const seen = new Set(Array.from(world.data));
  seen.forEach(function (id) {
    const definition = blocks.block(id);
    assert.ok(definition, "missing block definition for id " + id);
    assert.ok(typeof definition.name === "string" && definition.name.length > 0);
  });
});

test("run-length serialization round-trips and stays compact", () => {
  const world = worldApi.generateWorld(SEED_A);
  worldApi.setBlock(world, 12, 40, config.blocks.stone);
  worldApi.setBlock(world, 13, 40, config.blocks.planks);
  const serialized = worldApi.serializeWorld(world);
  const restored = worldApi.deserializeWorld(serialized);
  assert.equal(restored.width, world.width);
  assert.equal(restored.height, world.height);
  assert.equal(restored.seed, world.seed);
  assert.deepEqual(Array.from(restored.data), Array.from(world.data));
  assert.ok(serialized.length < world.width * world.height * 2, "RLE should beat a raw JSON array");
});

test("serialization rejects corrupt payloads", () => {
  assert.throws(function () {
    worldApi.deserializeWorld(JSON.stringify({ width: 4, height: 4, rle: [1, 3] }));
  });
  assert.throws(function () {
    worldApi.deserializeWorld(JSON.stringify({ width: 4, height: 4, data: [1, 1, 1] }));
  });
  assert.throws(function () {
    worldApi.deserializeWorld(JSON.stringify({ width: 4 }));
  });
});
