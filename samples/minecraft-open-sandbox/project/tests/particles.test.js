const test = require("node:test");
const assert = require("node:assert/strict");
const particles = require("../js/particles.js");

test("block particles spawn and expire", () => {
  const system = particles.createParticleSystem();
  system.spawnBlock(10, 12, 3, 12);
  assert.equal(system.list.length, 12);
  for (let i = 0; i < 120; i += 1) {
    system.update(1 / 60);
  }
  assert.equal(system.list.length, 0);
});

test("reduced motion caps burst counts", () => {
  const system = particles.createParticleSystem({ reducedMotion: true });
  system.spawnBlock(1, 2, 1, 40);
  assert.ok(system.list.length <= 3);
  system.spawnDamage(1, 1, "#f00");
  assert.ok(system.list.length <= 5);
  system.clear();
  assert.equal(system.list.length, 0);
});
