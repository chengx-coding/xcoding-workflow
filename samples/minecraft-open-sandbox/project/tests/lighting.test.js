const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const lighting = require("../js/lighting.js");

const SEED = 20261102;

function clearWorld(world, fill) {
  for (let y = 0; y < world.height; y += 1) {
    for (let x = 0; x < world.width; x += 1) {
      worldApi.setBlock(world, x, y, fill);
    }
  }
}

test("sky light reaches the surface and stops at solid ground", () => {
  const world = worldApi.generateWorld(SEED);
  const light = lighting.relight(world, lighting.createLight(world));
  const x = Math.floor(world.width / 2);
  const top = worldApi.surfaceHeightAt(world, x);
  assert.ok(light.sky[(top - 1) * world.width + x] >= 14, "open sky above the surface should be bright");
  assert.ok(light.sky[(top + 20) * world.width + x] < 8, "deep underground should be much darker than the surface");
});

test("skylight spreads sideways from an opening", () => {
  const world = worldApi.generateWorld(SEED);
  clearWorld(world, config.blocks.air);
  for (let x = 0; x < world.width; x += 1) {
    worldApi.setBlock(world, x, 20, config.blocks.stone);
  }
  worldApi.setBlock(world, 50, 20, config.blocks.air);
  const light = lighting.relight(world, lighting.createLight(world));
  const nearHole = light.sky[21 * world.width + 50];
  const beside = light.sky[21 * world.width + 49];
  const threeAway = light.sky[21 * world.width + 47];
  assert.equal(nearHole, 15, "the open column under the hole keeps direct sky");
  assert.equal(beside, 14, "one tile sideways should receive sky minus one");
  assert.equal(threeAway, 12, "light should fade one level per tile");
  assert.equal(light.sky[21 * world.width + 10], 0, "distant sealed tiles stay dark");
});

test("torches light sealed underground rooms", () => {
  const world = worldApi.generateWorld(SEED);
  const x = 20;
  const top = worldApi.surfaceHeightAt(world, x);
  const roomY = top + 6;
  for (let offsetY = -1; offsetY <= 1; offsetY += 1) {
    for (let offsetX = -1; offsetX <= 1; offsetX += 1) {
      worldApi.setBlock(world, x + offsetX, roomY + offsetY, config.blocks.stone);
    }
  }
  worldApi.setBlock(world, x, roomY, config.blocks.air);
  worldApi.setBlock(world, x + 1, roomY, config.blocks.air);
  let light = lighting.relight(world, lighting.createLight(world));
  assert.equal(light.block[roomY * world.width + x], 0, "the room starts dark");
  worldApi.setBlock(world, x, roomY, config.blocks.torch);
  light = lighting.relight(world, lighting.createLight(world));
  assert.equal(light.block[roomY * world.width + x], 14);
  assert.ok(light.block[roomY * world.width + x + 1] >= 13, "torch light should reach the neighbour");
  assert.ok(lighting.brightnessAt(light, x + 1, roomY, 0.2, world.width) > 0.7);
});

test("light is blocked by solid blocks and passes through glass", () => {
  assert.equal(lighting.opaque(config.blocks.stone), true);
  assert.equal(lighting.opaque(config.blocks.dirt), true);
  assert.equal(lighting.opaque(config.blocks.glass), false);
  assert.equal(lighting.opaque(config.blocks.air), false);

  const world = worldApi.generateWorld(SEED);
  clearWorld(world, config.blocks.stone);
  worldApi.setBlock(world, 30, 40, config.blocks.air);
  worldApi.setBlock(world, 31, 40, config.blocks.glass);
  worldApi.setBlock(world, 32, 40, config.blocks.air);
  worldApi.setBlock(world, 33, 40, config.blocks.air);
  worldApi.setBlock(world, 30, 40, config.blocks.torch);
  const light = lighting.relight(world, lighting.createLight(world));
  assert.ok(light.block[40 * world.width + 32] >= 12, "light should pass through glass");
  assert.equal(light.block[40 * world.width + 29], 0, "stone blocks light completely");
});

test("daylight factor peaks at noon and falls at night", () => {
  assert.ok(lighting.daylightAt(0.25) > lighting.daylightAt(0.04));
  assert.ok(lighting.daylightAt(0.25) > 0.9);
  assert.ok(lighting.daylightAt(0.75) < 0.25);
  assert.ok(lighting.daylightAt(0.5) < lighting.daylightAt(0.25));
  assert.equal(lighting.daylightAt(0.25), lighting.daylightAt(1.25));
});
