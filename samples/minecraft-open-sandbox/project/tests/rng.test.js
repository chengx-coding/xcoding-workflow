const test = require("node:test");
const assert = require("node:assert/strict");
const rng = require("../js/rng.js");

test("mulberry32 is deterministic and stays in range", () => {
  const a = rng.mulberry32(12345);
  const b = rng.mulberry32(12345);
  for (let i = 0; i < 20; i += 1) {
    const value = a();
    assert.equal(value, b());
    assert.ok(value >= 0 && value < 1);
  }
});

test("hash2 is stable and differs by coordinate", () => {
  assert.equal(rng.hash2(4, 7, 99), rng.hash2(4, 7, 99));
  assert.notEqual(rng.hash2(4, 7, 99), rng.hash2(5, 7, 99));
  assert.notEqual(rng.hash2(4, 7, 99), rng.hash2(4, 7, 100));
});

test("noise is bounded and fbm normalizes octaves", () => {
  for (let i = 0; i < 50; i += 1) {
    const value = rng.fbm1(i * 0.37, 5, 4);
    assert.ok(value >= -1 && value <= 1);
  }
  assert.ok(rng.clamp(12, 0, 10) === 10);
});
