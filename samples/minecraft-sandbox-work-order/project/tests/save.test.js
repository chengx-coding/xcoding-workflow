const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const playerApi = require("../js/player.js");
const saveApi = require("../js/save.js");

function memoryStorage() {
  const entries = new Map();
  return {
    getItem(key) {
      return entries.has(key) ? entries.get(key) : null;
    },
    setItem(key, value) {
      entries.set(key, String(value));
    },
    removeItem(key) {
      entries.delete(key);
    }
  };
}

test("save and load round-trips world, player and selection", () => {
  const storage = memoryStorage();
  const world = worldApi.createWorld(777);
  worldApi.setBlock(world, 4, 4, config.blocks.wood);
  const player = playerApi.createPlayer(12.5, 39.25);
  player.vx = 0.1;
  player.vy = -0.2;

  assert.equal(
    saveApi.saveState(storage, { world: world, player: player, selected: config.blocks.stone }),
    true
  );

  const restored = saveApi.loadState(storage);
  assert.ok(restored);
  assert.equal(restored.world.width, world.width);
  assert.equal(restored.world.height, world.height);
  assert.equal(restored.world.seed, world.seed);
  assert.deepEqual(Array.from(restored.world.data), Array.from(world.data));
  assert.equal(restored.player.x, 12.5);
  assert.equal(restored.player.y, 39.25);
  assert.equal(restored.player.vx, 0.1);
  assert.equal(restored.player.vy, -0.2);
  assert.equal(restored.selected, config.blocks.stone);
});

test("missing, corrupt and unsupported saves are ignored", () => {
  const storage = memoryStorage();
  assert.equal(saveApi.loadState(storage), null);

  storage.setItem(config.saveKey, "{not json");
  assert.equal(saveApi.loadState(storage), null);

  const world = worldApi.createWorld(1);
  const player = playerApi.createPlayer(2, 3);
  saveApi.saveState(storage, { world: world, player: player, selected: config.blocks.dirt });
  const payload = JSON.parse(storage.getItem(config.saveKey));
  payload.version = 99;
  storage.setItem(config.saveKey, JSON.stringify(payload));
  assert.equal(saveApi.loadState(storage), null);
});

test("an unknown selected block falls back to grass", () => {
  const storage = memoryStorage();
  const world = worldApi.createWorld(2);
  const player = playerApi.createPlayer(3, 4);

  saveApi.saveState(storage, { world: world, player: player, selected: 999 });
  const restored = saveApi.loadState(storage);

  assert.ok(restored);
  assert.equal(restored.selected, config.blocks.grass);
});

test("clearState removes the saved payload", () => {
  const storage = memoryStorage();
  const world = worldApi.createWorld(3);
  const player = playerApi.createPlayer(4, 5);

  saveApi.saveState(storage, { world: world, player: player, selected: config.blocks.wood });
  assert.ok(saveApi.loadState(storage));
  assert.equal(saveApi.clearState(storage), true);
  assert.equal(saveApi.loadState(storage), null);
});
