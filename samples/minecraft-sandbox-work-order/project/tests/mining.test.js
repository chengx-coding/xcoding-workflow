const test = require("node:test");
const assert = require("node:assert/strict");

const Mining = require("../js/mining.js");

test("a new mining state is inactive at zero progress", () => {
  const mining = Mining.createMining();
  assert.equal(mining.active, false);
  assert.equal(Mining.progressOf(mining), 0);
  assert.equal(Mining.isActive(mining), false);
});

test("starting a break records the tile and resets progress", () => {
  const mining = Mining.createMining(0.2);
  assert.equal(Mining.start(mining, 5, 6), true);
  assert.equal(mining.active, true);
  assert.deepEqual(mining.tile, { x: 5, y: 6 });
  assert.equal(Mining.progressOf(mining), 0);
});

test("progress advances with delta and completes at one", () => {
  const mining = Mining.createMining(0.2);
  Mining.start(mining, 1, 2);
  assert.equal(Mining.advance(mining, 0.1), false);
  assert.ok(Math.abs(Mining.progressOf(mining) - 0.5) < 1e-9);
  assert.equal(Mining.advance(mining, 0.1), true);
  assert.equal(Mining.progressOf(mining), 1);
});

test("progress never exceeds one and ignores invalid deltas", () => {
  const mining = Mining.createMining(0.1);
  Mining.start(mining, 0, 0);
  Mining.advance(mining, Number.NaN);
  assert.equal(Mining.progressOf(mining), 0);
  Mining.advance(mining, 5);
  assert.equal(Mining.progressOf(mining), 1);
});

test("advancing an inactive state does nothing", () => {
  const mining = Mining.createMining();
  assert.equal(Mining.advance(mining, 0.1), false);
  assert.equal(mining.progress, 0);
});

test("cancel clears the active break", () => {
  const mining = Mining.createMining();
  Mining.start(mining, 3, 4);
  Mining.advance(mining, 0.1);
  Mining.cancel(mining);
  assert.equal(Mining.isActive(mining), false);
  assert.equal(Mining.progressOf(mining), 0);
  assert.equal(mining.tile, null);
});

test("describe returns a plain probe-safe snapshot", () => {
  const mining = Mining.createMining();
  Mining.start(mining, 7, 8);
  Mining.advance(mining, 0.11);
  const described = Mining.describe(mining);
  assert.equal(described.active, true);
  assert.deepEqual(described.tile, { x: 7, y: 8 });
  assert.ok(described.progress > 0 && described.progress < 1);
  assert.equal(JSON.parse(JSON.stringify(described)).tile.x, 7);
});

test("invalid tiles are refused", () => {
  const mining = Mining.createMining();
  assert.equal(Mining.start(mining, 1.5, 2), false);
  assert.equal(mining.active, false);
});
