const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const light = require("../js/light.js");

const GROUND = Math.floor(config.worldHeight * 0.65);

test("day factor peaks at noon and drops at night", () => {
  assert.ok(light.dayFactor(0.25) > 0.9);
  assert.ok(light.dayFactor(0.4) > 0.9);
  assert.ok(light.dayFactor(0.75) < 0.15);
  assert.ok(light.dayFactor(0.1) > 0.8);
  assert.equal(light.isNight(0.75), true);
  assert.equal(light.isNight(0.25), false);
  assert.equal(light.isDuskOrDawn(0.55), true);
});

test("sky light covers the surface and darkness fills the deep", () => {
  const world = worldApi.createWorld(config.seed);
  const bounds = { x0: 0, y0: GROUND - 6, x1: 40, y1: GROUND + 12 };
  const noon = light.computeLight(world, bounds, 0.25);
  assert.equal(light.lightAt(noon, 12, GROUND - 2), 15);
  assert.ok(light.lightAt(noon, 12, GROUND + 10) <= 2, "the deep is unlit except ambient");
  const midnight = light.computeLight(world, bounds, 0.75);
  assert.ok(light.lightAt(midnight, 12, GROUND - 2) <= 4);
  assert.equal(light.lightAt(midnight, 12, GROUND), 8);
});

test("a roof blocks skylight", () => {
  const world = worldApi.createWorld(config.seed);
  // Build a closed room on the spawn plateau: roof and two walls.
  for (let x = 4; x <= 12; x += 1) {
    worldApi.setBlock(world, x, GROUND - 4, config.blocks.planks);
  }
  for (let y = GROUND - 4; y <= GROUND - 1; y += 1) {
    worldApi.setBlock(world, 4, y, config.blocks.planks);
    worldApi.setBlock(world, 12, y, config.blocks.planks);
  }
  const bounds = { x0: 0, y0: GROUND - 8, x1: 20, y1: GROUND + 2 };
  const lit = light.computeLight(world, bounds, 0.25);
  assert.ok(light.lightAt(lit, 8, GROUND - 2) <= 4, "an enclosed room holds only ambient light");
  assert.equal(light.lightAt(lit, 16, GROUND - 2), 15);
});

test("torches light the surrounding cave", () => {
  const world = worldApi.createWorld(config.seed);
  // Carve a small chamber and light it from one torch.
  for (let x = 29; x <= 38; x += 1) {
    for (let y = GROUND + 2; y <= GROUND + 3; y += 1) {
      worldApi.setBlock(world, x, y, config.blocks.air);
    }
  }
  worldApi.setBlock(world, 30, GROUND + 2, config.blocks.torch);
  const bounds = { x0: 24, y0: GROUND - 4, x1: 44, y1: GROUND + 6 };
  const lit = light.computeLight(world, bounds, 0.75);
  assert.equal(light.lightAt(lit, 30, GROUND + 2), 14);
  assert.ok(light.lightAt(lit, 31, GROUND + 2) >= 12);
  assert.ok(light.lightAt(lit, 34, GROUND + 2) >= 8);
  assert.ok(light.darknessAt(lit, 43, GROUND + 5) > 0.5);
});

test("light grid bounds are clamped and readable", () => {
  const world = worldApi.createWorld(config.seed);
  const bounds = light.computeLight(world, { x0: -20, y0: -20, x1: 10, y1: 10 }, 0.25);
  assert.equal(bounds.x0, 0);
  assert.equal(bounds.y0, 0);
  assert.equal(bounds.width, 11);
  assert.equal(bounds.height, 11);
  assert.equal(light.lightAt(bounds, -5, 0), 0);
  assert.equal(light.lightAt(bounds, 0, 0), 15);
});
