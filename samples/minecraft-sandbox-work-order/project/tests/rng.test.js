const test = require("node:test");
const assert = require("node:assert/strict");

const rng = require("../js/rng.js");

test("hashString is deterministic for the same label", () => {
  assert.equal(rng.hashString("blockstead"), rng.hashString("blockstead"));
  assert.notEqual(rng.hashString("blockstead"), rng.hashString("blockstead "));
});

test("hashString always returns an unsigned 32-bit integer", () => {
  ["", "a", "seed:1234", "longer label with spaces"].forEach((label) => {
    const value = rng.hashString(label);
    assert.ok(Number.isInteger(value));
    assert.ok(value >= 0);
    assert.ok(value <= 0xffffffff);
  });
});

test("normalizeSeed wraps numbers into the unsigned range", () => {
  assert.equal(rng.normalizeSeed(0), 0);
  assert.equal(rng.normalizeSeed(42), 42);
  assert.equal(rng.normalizeSeed(-1), 0xffffffff);
  assert.equal(rng.normalizeSeed(2 ** 32 + 7), 7);
});

test("normalizeSeed treats non-finite values as zero", () => {
  assert.equal(rng.normalizeSeed(undefined), 0);
  assert.equal(rng.normalizeSeed("not a number"), 0);
  assert.equal(rng.normalizeSeed(Infinity), 0);
});

test("parseSeedText accepts whole numbers with surrounding space", () => {
  assert.deepEqual(rng.parseSeedText(" 42 "), { ok: true, seed: 42 });
  assert.deepEqual(rng.parseSeedText("-7"), { ok: true, seed: 4294967289 });
  assert.deepEqual(rng.parseSeedText("+9"), { ok: true, seed: 9 });
});

test("parseSeedText rejects empty, fractional and oversized input", () => {
  assert.equal(rng.parseSeedText("").ok, false);
  assert.equal(rng.parseSeedText("   ").ok, false);
  assert.equal(rng.parseSeedText("3.5").ok, false);
  assert.equal(rng.parseSeedText("1e9").ok, false);
  assert.equal(rng.parseSeedText("99999999999999999999").ok, false);
});

test("mulberry32 repeats the same stream for the same seed", () => {
  const first = rng.mulberry32(1234);
  const second = rng.mulberry32(1234);
  for (let index = 0; index < 20; index += 1) {
    assert.equal(first(), second());
  }
});

test("mulberry32 produces different streams for different seeds", () => {
  const first = rng.mulberry32(1);
  const second = rng.mulberry32(2);
  let differences = 0;
  for (let index = 0; index < 20; index += 1) {
    if (first() !== second()) {
      differences += 1;
    }
  }
  assert.ok(differences > 15);
});

test("createRandom helpers stay inside their ranges", () => {
  const random = rng.createRandom(99);
  for (let index = 0; index < 50; index += 1) {
    const value = random.range(2, 5);
    assert.ok(value >= 2 && value <= 5);
    const integer = random.int(1, 3);
    assert.ok(Number.isInteger(integer));
    assert.ok(integer >= 1 && integer <= 3);
  }
  assert.equal(random.pick([]), null);
  assert.ok(["a", "b"].includes(random.pick(["a", "b"])));
});

test("hash2 is stable per cell and normalised", () => {
  assert.equal(rng.hash2(4, 9, 77), rng.hash2(4, 9, 77));
  assert.notEqual(rng.hash2(4, 9, 77), rng.hash2(5, 9, 77));
  const value = rng.hash2(12, 34, 56);
  assert.ok(value >= 0 && value < 1);
});
