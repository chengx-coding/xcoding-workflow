const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");

const GROUND = Math.floor(config.worldHeight * 0.65);

function countBlocks(world, block, yMin, yMax) {
  let count = 0;
  for (let y = yMin; y <= yMax; y += 1) {
    for (let x = 0; x < world.width; x += 1) {
      if (world.data[y * world.width + x] === block) {
        count += 1;
      }
    }
  }
  return count;
}

test("world generation is deterministic for one seed", () => {
  const a = worldApi.createWorld(12345);
  const b = worldApi.createWorld(12345);
  assert.equal(a.data.length, b.data.length);
  assert.deepEqual(Array.from(a.data), Array.from(b.data));
  assert.equal(a.seed, 12345);
});

test("different seeds generate different terrain", () => {
  const a = worldApi.createWorld(1);
  const b = worldApi.createWorld(2);
  let differences = 0;
  for (let i = 0; i < a.data.length; i += 1) {
    if (a.data[i] !== b.data[i]) {
      differences += 1;
    }
  }
  assert.ok(differences > 500, `expected meaningful terrain differences, got ${differences}`);
});

test("spawn plateau is flat at the configured ground row", () => {
  const world = worldApi.createWorld(config.seed);
  assert.equal(worldApi.GROUND_ROW, GROUND);
  for (let x = 0; x <= worldApi.PLATEAU_END; x += 1) {
    assert.equal(worldApi.terrainHeightAt(x, world.seed), GROUND, `x=${x}`);
  }
  assert.equal(worldApi.getBlock(world, 10, GROUND), config.blocks.grass);
  assert.equal(worldApi.getBlock(world, config.spawnX, GROUND), config.blocks.grass);
});

test("hills rise away from the spawn plateau", () => {
  const world = worldApi.createWorld(config.seed);
  let varied = 0;
  for (let x = 120; x < world.width; x += 1) {
    if (worldApi.surfaceHeight(world, x) !== GROUND) {
      varied += 1;
    }
  }
  assert.ok(varied > 20, `expected hilly terrain, got ${varied} varied columns`);
});

test("the world contains a forest of trees", () => {
  const world = worldApi.createWorld(config.seed);
  assert.ok(world.meta.trees >= 10, `expected at least 10 trees, got ${world.meta.trees}`);
  assert.ok(countBlocks(world, config.blocks.wood, 0, GROUND - 1) > 30);
  assert.ok(countBlocks(world, config.blocks.leaves, 0, GROUND - 1) > 60);
});

test("caves exist below the surface", () => {
  const world = worldApi.createWorld(config.seed);
  let air = 0;
  for (let y = GROUND + 8; y < world.height - 2; y += 1) {
    for (let x = 0; x < world.width; x += 1) {
      if (worldApi.getBlock(world, x, y) === config.blocks.air) {
        air += 1;
      }
    }
  }
  assert.ok(air > 400, `expected caves below the surface, got ${air} air tiles`);
});

test("ore bands are present and depth-banded", () => {
  const world = worldApi.createWorld(config.seed);
  const coal = countBlocks(world, config.blocks.coal_ore, GROUND, GROUND + 26);
  const iron = countBlocks(world, config.blocks.iron_ore, GROUND + 15, GROUND + 38);
  const ember = countBlocks(world, config.blocks.ember_ore, world.height - 26, world.height - 4);
  assert.ok(coal > 30, `coal=${coal}`);
  assert.ok(iron > 25, `iron=${iron}`);
  assert.ok(ember > 15, `ember=${ember}`);
  assert.equal(countBlocks(world, config.blocks.ember_ore, 0, GROUND), 0, "ember must stay deep");
});

test("the bottom row stays solid stone", () => {
  const world = worldApi.createWorld(config.seed);
  for (let x = 0; x < world.width; x += 1) {
    assert.equal(worldApi.getBlock(world, x, world.height - 1), config.blocks.stone);
  }
});

test("RLE serialization round-trips the whole world", () => {
  const world = worldApi.createWorld(config.seed);
  worldApi.setBlock(world, 3, 40, config.blocks.beacon);
  const payload = worldApi.serializeWorld(world);
  assert.ok(payload.length < world.data.length, "RLE payload should be smaller than raw bytes");
  const restored = worldApi.deserializeWorld(payload);
  assert.equal(restored.width, world.width);
  assert.equal(restored.height, world.height);
  assert.equal(restored.seed, world.seed);
  assert.equal(restored.data.length, world.data.length);
  assert.equal(worldApi.getBlock(restored, 3, 40), config.blocks.beacon);
  assert.deepEqual(Array.from(restored.data), Array.from(world.data));
});

test("legacy block-array payloads still load", () => {
  const world = worldApi.createWorld(7);
  const legacy = JSON.stringify({
    width: world.width,
    height: world.height,
    seed: world.seed,
    data: Array.from(world.data)
  });
  const restored = worldApi.deserializeWorld(legacy);
  assert.equal(worldApi.getBlock(restored, 10, GROUND), config.blocks.grass);
});

test("invalid world payloads are rejected", () => {
  assert.throws(() => worldApi.deserializeWorld("{}"));
  assert.throws(() => worldApi.deserializeWorld('{"width":2,"height":2,"rle":[[1,3]]}'));
  assert.throws(() => worldApi.deserializeWorld('{"width":2,"height":2,"rle":[[1,99]]}'));
});

test("exposure is required to mine into a wall", () => {
  const world = worldApi.createWorld(config.seed);
  assert.equal(worldApi.isExposed(world, 10, GROUND), true);
  assert.equal(worldApi.isExposed(world, 10, GROUND + 3), false);
});

test("placement needs an empty tile with a solid neighbour", () => {
  const world = worldApi.createWorld(config.seed);
  assert.equal(worldApi.canPlaceAt(world, 10, GROUND - 1, config.blocks.planks), true);
  assert.equal(worldApi.canPlaceAt(world, 10, GROUND, config.blocks.planks), false);
  assert.equal(worldApi.canPlaceAt(world, 10, 2, config.blocks.planks), false);
  assert.equal(worldApi.canPlaceAt(world, 10, GROUND - 1, config.blocks.torch), true);
});

test("minimap sampling returns one column per request", () => {
  const world = worldApi.createWorld(config.seed);
  const columns = worldApi.sampleColumns(world, 0, 200, 40);
  assert.equal(columns.length, 40);
  assert.equal(columns[0].x, 0);
  assert.equal(columns[39].x, 199);
  assert.equal(columns[0].surface, GROUND);
});
