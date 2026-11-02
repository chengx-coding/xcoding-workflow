const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const playerApi = require("../js/player.js");
const mobsApi = require("../js/mobs.js");

const GROUND = worldApi.GROUND_ROW;
const DT = 1 / 60;

function setup() {
  const world = worldApi.createWorld(config.seed);
  const player = playerApi.createPlayer(24.5, GROUND);
  const mobs = mobsApi.createMobs();
  return { world, player, mobs };
}

test("night spawns hollows on dark ground", () => {
  const { world, player, mobs } = setup();
  mobs.spawnTimer = 0;
  const events = mobsApi.update(mobs, world, player, DT, {
    isNight: true,
    lightAt: function lightAt() {
      return 0;
    }
  });
  assert.equal(events.spawned, 1);
  assert.equal(mobs.list.length, 1);
  const mob = mobs.list[0];
  assert.ok(mob.y >= GROUND - 2 && mob.y <= GROUND + 2, `spawn y=${mob.y}`);
  assert.ok(Math.abs(mob.x - player.x) >= 8);
});

test("daylight removes hollows", () => {
  const { world, player, mobs } = setup();
  mobsApi.addMob(mobs, { x: 30.5, y: GROUND, health: 6 });
  const events = mobsApi.update(mobs, world, player, DT, { isNight: false });
  assert.equal(events.despawned, 1);
  assert.equal(mobs.list.length, 0);
});

test("bright light prevents spawning", () => {
  const { world, player, mobs } = setup();
  mobs.spawnTimer = 0;
  for (let i = 0; i < 30; i += 1) {
    mobsApi.update(mobs, world, player, DT, {
      isNight: true,
      lightAt: function lightAt() {
        return 15;
      }
    });
  }
  assert.equal(mobs.list.length, 0);
});

test("contact damages the player once per cooldown", () => {
  const { world, player, mobs } = setup();
  const mob = mobsApi.addMob(mobs, { x: player.x, y: player.y, health: 6 });
  const context = {
    isNight: true,
    lightAt: function lightAt() {
      return 0;
    }
  };
  let events = mobsApi.update(mobs, world, player, DT, context);
  assert.equal(events.damage, 2);
  assert.equal(events.hits, 1);
  events = mobsApi.update(mobs, world, player, DT, context);
  assert.equal(events.damage, 0, "attack cooldown should gate the second hit");
  assert.ok(mob.attackCooldown > 0);
});

test("attacking a hollow kills it and removes it", () => {
  const { world, player, mobs } = setup();
  const mob = mobsApi.addMob(mobs, { x: player.x + 1.5, y: player.y, health: 6 });
  const found = mobsApi.attackAt(mobs, mob.x, mob.y - 0.7, 0.35);
  assert.equal(found.hit, true);
  assert.equal(found.mob, mob);
  assert.equal(mobsApi.damage(mob, 2), false);
  assert.equal(mobsApi.damage(mob, 4), true);
  mobsApi.remove(mobs, mob);
  assert.equal(mobs.list.length, 0);
});

test("the hollow count stays within the limit", () => {
  const { world, player, mobs } = setup();
  const context = {
    isNight: true,
    lightAt: function lightAt() {
      return 0;
    }
  };
  for (let i = 0; i < 600; i += 1) {
    mobs.spawnTimer = 0;
    mobsApi.update(mobs, world, player, DT, context);
  }
  assert.ok(mobs.list.length <= config.mobLimit);
});

test("groundY skips tree canopy", () => {
  const { world } = setup();
  assert.equal(mobsApi.groundY(world, 34) > worldApi.surfaceHeight(world, 34) - 10, true);
  assert.equal(mobsApi.groundY(world, 34), GROUND);
  assert.equal(mobsApi.groundY(world, 60), worldApi.surfaceHeight(world, 60));
});
