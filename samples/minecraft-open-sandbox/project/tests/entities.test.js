const test = require("node:test");
const assert = require("node:assert/strict");
const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const entities = require("../js/entities.js");

function scene() {
  const world = worldApi.createWorld(config.seed);
  const player = {
    x: world.spawn.x,
    y: world.spawn.y,
    width: 0.68,
    height: 1.8
  };
  return { world, player, manager: entities.createManager() };
}

test("spawn caps prevent runaway populations", () => {
  const { world, player, manager } = scene();
  for (let i = 0; i < entities.hostileCap; i += 1) {
    entities.spawn(manager, "zombie", player.x + 20 + i, player.y);
  }
  for (let i = 0; i < entities.passiveCap; i += 1) {
    entities.spawn(manager, "pig", player.x - 20 - i, player.y);
  }
  const before = manager.list.length;
  entities.trySpawn(manager, world, player, 0.8);
  assert.equal(manager.list.length, before);
});

test("a zombie walks toward the player at night", () => {
  const { world, player, manager } = scene();
  const zombie = entities.spawn(manager, "zombie", player.x + 4, world.surface[Math.floor(player.x) + 4]);
  const start = zombie.x;
  for (let i = 0; i < 120; i += 1) {
    entities.update(manager, { world, player, time: 0.8, dt: 1 / 60, effects: {} });
  }
  assert.ok(Math.abs(zombie.x - player.x) < Math.abs(start - player.x));
});

test("hitting a mob damages it, knocks it back, and drops loot on death", () => {
  const { world, player, manager } = scene();
  const pig = entities.spawn(manager, "pig", player.x + 2, world.surface[Math.floor(player.x) + 2]);
  const drops = [];
  const hit = entities.hit(manager, pig, 20, 1, { effects: { onDrop: (id) => drops.push(id) } });
  assert.equal(hit.killed, true);
  assert.equal(manager.list.includes(pig), false);
  assert.ok(drops.length >= 1);
  assert.equal(drops[0], config.itemIds.rawPork);
});

test("hostiles despawn in daylight and mobAt finds a body", () => {
  const { world, player, manager } = scene();
  const zombie = entities.spawn(manager, "zombie", player.x + 1, world.surface[Math.floor(player.x) + 1]);
  assert.equal(entities.mobAt(manager, zombie.x, zombie.y - 0.5), zombie);
  for (let i = 0; i < 5; i += 1) {
    entities.update(manager, { world, player, time: 0.3, dt: 1 / 60, effects: {} });
  }
  assert.equal(manager.list.includes(zombie), false);
});

test("night spawning finds a valid surface around the player", () => {
  const originalRandom = Math.random;
  Math.random = () => 0.1;
  try {
    for (let seed = 1; seed <= 5; seed += 1) {
      const world = worldApi.createWorld(seed);
      const player = { x: world.spawn.x, y: world.spawn.y, width: 0.68, height: 1.8 };
      const manager = entities.createManager();
      const spawned = entities.trySpawn(manager, world, player, 0.8);
      assert.equal(spawned, true, "seed " + seed + " should spawn a mob");
      assert.ok(manager.list.length >= 1);
      assert.equal(manager.list[0].hostile, true);
    }
  } finally {
    Math.random = originalRandom;
  }
});
