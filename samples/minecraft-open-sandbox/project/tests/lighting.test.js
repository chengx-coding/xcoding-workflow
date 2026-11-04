const test = require("node:test");
const assert = require("node:assert/strict");
const lighting = require("../js/lighting.js");

test("daylight is brighter than night on the surface", () => {
  const day = lighting.lightLevel(0, 1, []);
  const night = lighting.lightLevel(0, 0, []);
  assert.ok(day > night);
  assert.ok(day >= 0.9);
  assert.ok(night < 0.35);
});

test("depth darkens caves and torches light them", () => {
  const cave = lighting.lightLevel(8, 1, []);
  const torch = lighting.lightLevel(8, 1, [{ distance: 1, radius: 7.5, strength: 1.15 }]);
  assert.ok(cave < 0.2);
  assert.ok(torch > cave + 0.4);
});

test("light levels stay bounded and fall off with distance", () => {
  const near = lighting.lightLevel(4, 0, [{ distance: 0, radius: 7.5, strength: 1.15 }]);
  const far = lighting.lightLevel(4, 0, [{ distance: 6, radius: 7.5, strength: 1.15 }]);
  assert.ok(near >= far);
  assert.ok(near <= 1.15);
});
