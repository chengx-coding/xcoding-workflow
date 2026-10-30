const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const render = require("../js/render.js");
const worldApi = require("../js/world.js");

test("every block type has a render colour", () => {
  [1, 2, 3, 4, 5, 6, 7, 8, 9].forEach((block) => {
    assert.match(render.BLOCK_COLORS[block], /^#[0-9a-f]{6}$/i);
  });
});

test("tile variants are stable per cell and stay in range", () => {
  const variants = new Set();
  for (let index = 0; index < 200; index += 1) {
    const variant = render.tileVariant(index, index * 7, 123);
    assert.ok(Number.isInteger(variant));
    assert.ok(variant >= 0 && variant < render.TILE_VARIANTS);
    assert.equal(variant, render.tileVariant(index, index * 7, 123));
    variants.add(variant);
  }
  assert.equal(variants.size, render.TILE_VARIANTS);
});

test("depth shading starts at zero and never exceeds its cap", () => {
  assert.equal(render.depthShade(0), 0);
  assert.equal(render.depthShade(-3), 0);
  assert.ok(render.depthShade(2) > 0);
  assert.ok(render.depthShade(20) <= 0.42);
  assert.equal(render.depthShade(4), render.depthShade(4));
});

test("crack stages progress from zero to four", () => {
  assert.equal(render.crackStages(0), 0);
  assert.equal(render.crackStages(0.1), 1);
  assert.equal(render.crackStages(0.5), 2);
  assert.equal(render.crackStages(0.75), 3);
  assert.equal(render.crackStages(1), 4);
  assert.equal(render.crackStages(2), 4);
  assert.equal(render.crackStages(-1), 0);
});

test("surfaceFor matches the world surface map", () => {
  const world = worldApi.createWorld(config.seed);
  const surface = render.surfaceFor(world);
  assert.equal(surface.length, world.width);
  assert.deepEqual(Array.from(surface), Array.from(worldApi.surfaceMap(world)));
});

test("surfaceFor memoises per world object", () => {
  const world = worldApi.createWorld(99);
  const first = render.surfaceFor(world);
  const second = render.surfaceFor(world);
  assert.equal(first, second);
});

test("renderFrame is exported for the browser loop", () => {
  assert.equal(typeof render.renderFrame, "function");
});
