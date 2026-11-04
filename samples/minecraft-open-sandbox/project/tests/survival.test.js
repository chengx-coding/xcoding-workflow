const test = require("node:test");
const assert = require("node:assert/strict");
const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const playerApi = require("../js/player.js");
const survival = require("../js/survival.js");

function fresh() {
  const world = worldApi.createWorld(config.seed);
  const player = playerApi.createPlayer(world.spawn.x, world.spawn.y);
  return { world, player };
}

test("falling more than three blocks hurts and resets the fall", () => {
  const { world, player } = fresh();
  player.fallDistance = 7;
  player.onGround = true;
  const events = survival.update(player, world, 1 / 60, {});
  assert.equal(player.health, 16);
  assert.equal(player.fallDistance, 0);
  assert.ok(events.some((event) => event.type === "damage" && event.cause === "fall"));
});

test("movement and sprinting drain hunger through exhaustion", () => {
  const { world, player } = fresh();
  player.hunger = 20;
  player.saturation = 0;
  player.exhaustion = 0;
  player.moving = true;
  for (let i = 0; i < 60 * 40; i += 1) {
    survival.update(player, world, 1 / 60, {});
  }
  assert.ok(player.hunger < 20);
});

test("an empty stomach causes starvation damage", () => {
  const { world, player } = fresh();
  player.hunger = 0;
  for (let i = 0; i < 60 * 5; i += 1) {
    survival.update(player, world, 1 / 60, {});
  }
  assert.ok(player.health < 20);
});

test("high hunger regenerates health slowly", () => {
  const { world, player } = fresh();
  player.health = 15;
  player.hunger = 20;
  for (let i = 0; i < 60 * 5; i += 1) {
    survival.update(player, world, 1 / 60, {});
  }
  assert.ok(player.health >= 16);
});

test("air drains underwater and drowning damages the player", () => {
  const world = { width: 10, height: 10, data: new Uint8Array(100).fill(config.blocks.air), surface: new Int16Array(10) };
  world.data[3 * 10 + 5] = config.blocks.water;
  const player = playerApi.createPlayer(5.5, 5);
  let events = [];
  for (let i = 0; i < 60 * 14; i += 1) {
    events = events.concat(survival.update(player, world, 1 / 60, {}));
  }
  assert.ok(player.air < player.maxAir);
  assert.ok(events.some((event) => event.cause === "drowning"));
});

test("eating restores hunger and saturation", () => {
  const { world, player } = fresh();
  player.hunger = 10;
  player.saturation = 0;
  const ok = survival.eat(player, { food: 4 });
  assert.equal(ok, true);
  assert.equal(player.hunger, 14);
  assert.ok(player.saturation > 0);
  assert.equal(survival.eat(player, { food: 4 }), true);
});
