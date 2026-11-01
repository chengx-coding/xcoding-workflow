const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const lighting = require("../js/lighting.js");

test("sky light reaches the surface and stops at solid ground", () => {
  const world = worldApi.createWorld(config.seed);
  const spawn = worldApi.getSpawn(world);
  const light = lighting.computeLight(world, config.skyDay);
  assert.equal(lighting.lightAt(light, world, 0, 0), config.skyDay);
  assert.equal(lighting.lightAt(light, world, spawn.x, spawn.y - 1), config.skyDay);
  assert.equal(lighting.lightAt(light, world, spawn.x, spawn.y + 30), 0);
});

test("night lowers the sky light and phases are stable", () => {
  assert.equal(lighting.skyLevelForTime(0.25), config.skyDay);
  assert.equal(lighting.skyLevelForTime(0.75), config.skyNight);
  assert.equal(lighting.phaseForTime(0.25), "day");
  assert.equal(lighting.phaseForTime(0.75), "night");
  assert.equal(lighting.phaseForTime(0.02), "dawn");
  assert.equal(lighting.phaseForTime(0.5), "dusk");
});

test("a torch lights nearby air and darkness is bounded", () => {
  const world = worldApi.createWorld(config.seed);
  const spawn = worldApi.getSpawn(world);
  const dark = lighting.computeLight(world, config.skyNight);
  const before = lighting.lightAt(dark, world, spawn.x + 3, spawn.y - 3);
  worldApi.setBlock(world, spawn.x + 3, spawn.y - 3, config.blocks.torch);
  const lit = lighting.computeLight(world, config.skyNight);
  const after = lighting.lightAt(lit, world, spawn.x + 3, spawn.y - 3);
  assert.ok(after > before, "expected torch light to raise the tile");
  assert.ok(after >= 14);
  const nearby = lighting.lightAt(lit, world, spawn.x + 1, spawn.y - 3);
  assert.ok(nearby >= 12, "expected light to spread, got " + nearby);
  assert.equal(lighting.darknessForLevel(config.lightMax), 0);
  assert.ok(lighting.darknessForLevel(0) > 0.9);
});

test("crystal ore emits light and water attenuates it", () => {
  const width = 24;
  const height = 24;
  const data = new Uint8Array(width * height);
  const world = { width: width, height: height, seed: 1, data: data };
  for (let x = 0; x < width; x += 1) {
    for (let y = 12; y < height; y += 1) {
      data[y * width + x] = config.blocks.stone;
    }
  }
  for (let x = 0; x < 12; x += 1) {
    data[8 * width + x] = config.blocks.air;
    data[9 * width + x] = config.blocks.air;
  }
  data[8 * width + 2] = config.blocks.crystal;
  data[8 * width + 6] = config.blocks.water;
  const light = lighting.computeLight(world, config.skyNight);
  const crystal = lighting.lightAt(light, world, 2, 8);
  assert.ok(crystal >= 12);
  const throughAir = lighting.lightAt(light, world, 5, 8);
  const throughWater = lighting.lightAt(light, world, 7, 8);
  assert.ok(throughAir > throughWater, "water should attenuate more than air");
});
