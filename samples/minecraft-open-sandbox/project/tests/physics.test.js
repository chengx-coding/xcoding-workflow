const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const physics = require("../js/physics.js");

const GROUND = Math.floor(config.worldHeight * 0.65);

function flatWorld() {
  return worldApi.createWorld(config.seed);
}

function simulate(player, world, input, seconds, onStep) {
  const dt = 1 / 60;
  const steps = Math.round(seconds / dt);
  for (let index = 0; index < steps; index += 1) {
    physics.stepPlayer(player, world, input, dt);
    if (onStep) {
      onStep(player, index);
    }
  }
  return player;
}

test("gravity drops the player onto the ground", () => {
  const world = flatWorld();
  const player = physics.createPlayer(10.5, GROUND - 6);
  let impact = 0;
  simulate(player, world, {}, 3, function (current) {
    impact = Math.max(impact, current.lastImpact);
  });
  assert.equal(player.onGround, true);
  assert.ok(Math.abs(player.y - GROUND) < 0.001, "feet should rest on the ground row");
  assert.ok(impact > 0, "landing should report an impact speed");
});

test("jumping leaves the ground and returns to it", () => {
  const world = flatWorld();
  const player = physics.createPlayer(10.5, GROUND);
  player.onGround = true;
  let peak = player.y;
  let jumped = false;
  simulate(player, world, { jump: true }, 0.1, function (current) {
    peak = Math.min(peak, current.y);
    jumped = jumped || current.justJumped;
  });
  assert.equal(jumped, true);
  simulate(player, world, {}, 1.4, function (current) {
    peak = Math.min(peak, current.y);
  });
  assert.ok(peak < GROUND - 2, "jump should rise at least two tiles");
  assert.equal(player.onGround, true);
  assert.ok(Math.abs(player.y - GROUND) < 0.001);
});

test("the player cannot walk through a wall", () => {
  const world = flatWorld();
  for (let y = GROUND - 3; y < GROUND; y += 1) {
    worldApi.setBlock(world, 13, y, config.blocks.stone);
  }
  const player = physics.createPlayer(10.5, GROUND);
  player.onGround = true;
  simulate(player, world, { right: true }, 2);
  assert.ok(player.x < 13, "the wall must stop horizontal movement");
  assert.ok(player.x > 12, "the player should still cover the ground before the wall");
});

test("single-tile ledges are climbed without jumping", () => {
  const world = flatWorld();
  worldApi.setBlock(world, 11, GROUND - 1, config.blocks.dirt);
  worldApi.setBlock(world, 12, GROUND - 1, config.blocks.dirt);
  const player = physics.createPlayer(10.5, GROUND);
  player.onGround = true;
  let climbed = false;
  simulate(player, world, { right: true }, 1.2, function (current) {
    if (current.y <= GROUND - 1 && current.onGround) {
      climbed = true;
    }
  });
  assert.equal(climbed, true, "the player should step up onto the ledge");
  assert.ok(player.x > 11.2, "the player should be on top of the step");
});

test("the player is pushed out of solid ground instead of getting stuck", () => {
  const world = flatWorld();
  const player = physics.createPlayer(10.5, GROUND - 1);
  physics.settle(player, world);
  assert.equal(physics.collidesAt(world, player, player.x, player.y), false);
  assert.ok(player.y <= GROUND, "settling resolves upward");
});

test("fall damage grows with impact speed and ignores short falls", () => {
  assert.equal(physics.fallDamage(5), 0);
  assert.equal(physics.fallDamage(10), 0);
  assert.ok(physics.fallDamage(24) >= 1);
  assert.ok(physics.fallDamage(32) > physics.fallDamage(24));
  assert.ok(physics.fallDamage(100) <= 10);
});

test("a fall from height lands with a damaging impact", () => {
  const world = flatWorld();
  const player = physics.createPlayer(10.5, GROUND - 12);
  let impact = 0;
  simulate(player, world, {}, 4, function (current) {
    impact = Math.max(impact, current.lastImpact);
  });
  assert.ok(impact > 19, "a 12 tile fall should exceed the damage threshold");
  assert.ok(physics.fallDamage(impact) > 0);
});
