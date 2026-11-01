const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const rng = require("../js/rng.js");
const worldApi = require("../js/world.js");

function blocksOf(world) {
  const counts = {};
  for (let index = 0; index < world.data.length; index += 1) {
    const block = world.data[index];
    counts[block] = (counts[block] || 0) + 1;
  }
  return counts;
}

test("terrain is deterministic for one seed and differs across seeds", () => {
  const first = worldApi.createWorld(config.seed);
  const second = worldApi.createWorld(config.seed);
  const other = worldApi.createWorld((config.seed + 991) >>> 0);
  assert.deepEqual(Array.from(first.data), Array.from(second.data));
  assert.notDeepEqual(Array.from(first.data), Array.from(other.data));
});

test("the seed is normalized to an unsigned 32-bit integer", () => {
  const world = worldApi.createWorld("42");
  assert.equal(world.seed, 42);
  assert.equal(world.seed, worldApi.createWorld(42).seed);
});

test("the spawn plateau is exactly flat for every seed", () => {
  for (const seed of [0, 1, 1337, 987654321]) {
    for (let x = 0; x <= config.plateauEndColumn; x += 1) {
      assert.equal(worldApi.surfaceHeightAt(seed, x), config.baseSurfaceRow, "seed " + seed + " column " + x);
    }
  }
});

test("the seed contract rows are stable at column 10", () => {
  const world = worldApi.createWorld(config.seed);
  const surface = config.baseSurfaceRow;
  assert.equal(worldApi.getBlock(world, 10, surface), config.blocks.grass);
  assert.equal(worldApi.getBlock(world, 10, surface + 1), config.blocks.dirt);
  assert.equal(worldApi.getBlock(world, 10, surface + 2), config.blocks.dirt);
  assert.equal(worldApi.getBlock(world, 10, world.height - 1), config.blocks.stone);
  assert.equal(worldApi.getBlock(world, 10, 0), config.blocks.air);
});

test("surface heights are clamped to the configured range", () => {
  for (let x = 0; x < config.worldWidth; x += 1) {
    const surface = worldApi.surfaceHeightAt(config.seed, x);
    assert.ok(surface >= config.minSurfaceRow, "column " + x + " too high");
    assert.ok(surface <= config.maxSurfaceRow, "column " + x + " too low");
  }
});

test("the world contains grass, dirt, stone, sand, wood and leaves", () => {
  const counts = blocksOf(worldApi.createWorld(config.seed));
  for (const name of ["grass", "dirt", "stone", "sand", "wood", "leaves"]) {
    assert.ok((counts[config.blocks[name]] || 0) > 0, "missing " + name);
  }
});

test("trees are rooted above the surface and never overwrite the ground", () => {
  const world = worldApi.createWorld(config.seed);
  let trunks = 0;
  for (let x = 0; x < world.width; x += 1) {
    const surface = worldApi.surfaceHeightAt(world.seed, x);
    for (let y = 0; y < surface; y += 1) {
      const block = worldApi.getBlock(world, x, y);
      if (block === config.blocks.wood) {
        trunks += 1;
        assert.equal(worldApi.getBlock(world, x, surface), config.blocks.grass, "tree at " + x + " is not on grass");
      }
    }
  }
  assert.ok(trunks > 0, "no trees generated");
});

test("caves are carved below the surface but never into the bedrock rows", () => {
  const world = worldApi.createWorld(config.seed);
  let carved = 0;
  for (let x = 0; x < world.width; x += 1) {
    const surface = worldApi.surfaceHeightAt(world.seed, x);
    for (let y = surface + 5; y < world.height - config.bedrockRows; y += 1) {
      if (worldApi.getBlock(world, x, y) === config.blocks.air) {
        carved += 1;
      }
    }
    for (let y = world.height - config.bedrockRows; y < world.height; y += 1) {
      assert.notEqual(worldApi.getBlock(world, x, y), config.blocks.air, "bedrock carved at " + x + "," + y);
    }
  }
  assert.ok(carved > 0, "no caves generated");
});

test("block access is bounded and validates block ids", () => {
  const world = worldApi.createWorld(config.seed);
  assert.equal(worldApi.getBlock(world, -1, 0), null);
  assert.equal(worldApi.getBlock(world, 0, -1), null);
  assert.equal(worldApi.getBlock(world, world.width, 0), null);
  assert.equal(worldApi.setBlock(world, -1, 0, 1), false);
  assert.equal(worldApi.setBlock(world, 0, 0, 99), false);
  assert.equal(worldApi.setBlock(world, 0, 0, 1), true);
  assert.equal(worldApi.getBlock(world, 0, 0), 1);
});

test("solidity treats air as walkable and everything else as solid", () => {
  const world = worldApi.createWorld(config.seed);
  assert.equal(worldApi.isSolid(world, 0, 0), false);
  assert.equal(worldApi.isSolid(world, 10, config.baseSurfaceRow), true);
  assert.equal(worldApi.isSolid(world, -1, 0), false);
});

test("spawn point sits on top of the plateau surface", () => {
  const world = worldApi.createWorld(config.seed);
  const spawn = worldApi.spawnPoint(world);
  assert.equal(spawn.x, config.spawnColumn + 0.5);
  assert.equal(spawn.y, config.baseSurfaceRow);
});

test("run-length encoding round-trips arbitrary block data", () => {
  const data = Uint8Array.from([0, 0, 0, 1, 1, 2, 2, 2, 2, 0]);
  const runs = worldApi.encodeBlocks(data);
  assert.deepEqual(runs, [[0, 3], [1, 2], [2, 4], [0, 1]]);
  assert.deepEqual(Array.from(worldApi.decodeBlocks(runs, data.length)), Array.from(data));
});

test("world RLE serialization round-trips dimensions, seed and blocks", () => {
  const world = worldApi.createWorld(config.seed);
  worldApi.setBlock(world, 20, 20, config.blocks.brick);
  const restored = worldApi.worldFromRle(worldApi.worldToRle(world));
  assert.equal(restored.width, world.width);
  assert.equal(restored.height, world.height);
  assert.equal(restored.seed, world.seed);
  assert.equal(worldApi.getBlock(restored, 20, 20), config.blocks.brick);
});

test("invalid RLE payloads are rejected", () => {
  assert.throws(() => worldApi.decodeBlocks([[1, 2]], 3), /cover/);
  assert.throws(() => worldApi.decodeBlocks([[99, 1]], 1), /block id/);
  assert.throws(() => worldApi.worldFromRle({ width: 2, height: 2, blocks: [[1, 1]] }), /cover/);
  assert.throws(() => worldApi.worldFromRle({ width: 0, height: 2, blocks: [] }), /dimensions/);
});

test("the legacy JSON serializer still round-trips", () => {
  const world = worldApi.createWorld(5);
  worldApi.setBlock(world, 3, 3, config.blocks.glass);
  const restored = worldApi.deserializeWorld(worldApi.serializeWorld(world));
  assert.equal(worldApi.getBlock(restored, 3, 3), config.blocks.glass);
  assert.throws(() => worldApi.deserializeWorld("{"), /JSON/);
});

test("noise helpers stay in range and are deterministic", () => {
  for (let x = 0; x < 40; x += 1) {
    const value = rng.fbm1D(7, x * 0.37, 3);
    assert.ok(value >= -1 && value <= 1);
    assert.equal(value, rng.fbm1D(7, x * 0.37, 3));
  }
  assert.equal(rng.hash2(3, 4, 5), rng.hash2(3, 4, 5));
  assert.notEqual(rng.hash2(3, 4, 5), rng.hash2(3, 4, 6));
  const sequence = rng.mulberry32(99);
  const first = sequence();
  const second = sequence();
  assert.ok(first >= 0 && first < 1);
  assert.ok(second >= 0 && second < 1);
  assert.equal(rng.mulberry32(99)(), first);
});

test("loading a world re-seals the bottom floor rows", () => {
  const world = worldApi.createWorld(config.seed);
  const bottom = (world.height - 1) * world.width;
  const above = (world.height - 2) * world.width;
  world.data[bottom + 3] = config.blocks.air;
  world.data[above + 4] = config.blocks.air;

  const rleRestored = worldApi.worldFromRle(worldApi.worldToRle(world));
  assert.equal(worldApi.getBlock(rleRestored, 3, world.height - 1), config.blocks.stone);
  assert.equal(worldApi.getBlock(rleRestored, 4, world.height - 2), config.blocks.stone);

  const jsonRestored = worldApi.deserializeWorld(worldApi.serializeWorld(world));
  assert.equal(worldApi.getBlock(jsonRestored, 3, world.height - 1), config.blocks.stone);
  assert.equal(worldApi.getBlock(jsonRestored, 4, world.height - 2), config.blocks.stone);
});

test("the generated world still seals the floor after generation", () => {
  const world = worldApi.createWorld(4242);
  for (let x = 0; x < world.width; x += 1) {
    for (let y = world.height - config.bedrockRows; y < world.height; y += 1) {
      assert.equal(worldApi.getBlock(world, x, y), config.blocks.stone, "unsealed at " + x + "," + y);
    }
  }
});
