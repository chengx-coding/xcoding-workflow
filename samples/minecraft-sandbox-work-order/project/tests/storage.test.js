const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const playerApi = require("../js/player.js");
const storage = require("../js/storage.js");

function makeStorage() {
  const data = new Map();
  return {
    getItem: function (key) {
      return data.has(key) ? data.get(key) : null;
    },
    setItem: function (key, value) {
      data.set(key, String(value));
    },
    removeItem: function (key) {
      data.delete(key);
    }
  };
}

function makeWorld() {
  const world = worldApi.createWorld(config.seed);
  worldApi.setBlock(world, 12, 10, config.blocks.planks);
  return world;
}

test("saved world, player, selected slot and statistics round-trip", () => {
  const world = makeWorld();
  const player = playerApi.createPlayer(42.5, 38);
  player.facing = -1;
  const raw = storage.serializeSave(world, player, {
    selected: 4,
    timeOfDay: 0.61,
    stats: { mined: 12, placed: 8, distance: 45.5, crystals: 2 },
    muted: true
  });
  const parsed = storage.parseSave(raw);
  assert.equal(parsed.ok, true);
  assert.equal(parsed.value.selected, 4);
  assert.equal(parsed.value.timeOfDay, 0.61);
  assert.equal(parsed.value.stats.mined, 12);
  assert.equal(parsed.value.stats.placed, 8);
  assert.equal(parsed.value.stats.crystals, 2);
  assert.equal(parsed.value.settings.muted, true);
  assert.equal(parsed.value.player.x, 42.5);
  assert.equal(parsed.value.player.facing, -1);
  assert.equal(worldApi.getBlock(parsed.value.world, 12, 10), config.blocks.planks);
});

test("invalid, stale and corrupt payloads are rejected", () => {
  assert.equal(storage.parseSave("not json").reason, "invalid-json");
  assert.equal(storage.parseSave(JSON.stringify({ version: 999 })).reason, "version");
  const valid = JSON.parse(
    storage.serializeSave(makeWorld(), playerApi.createPlayer(10.5, 10), { selected: 0 })
  );
  valid.world.data = [1, 2, 3];
  assert.equal(storage.parseSave(JSON.stringify(valid)).reason, "world");
  valid.world.data = null;
  assert.equal(storage.parseSave(JSON.stringify(valid)).reason, "world");
  const invalidPlayer = JSON.parse(
    storage.serializeSave(makeWorld(), playerApi.createPlayer(10.5, 10), { selected: 0 })
  );
  invalidPlayer.player.x = 999999;
  assert.equal(storage.parseSave(JSON.stringify(invalidPlayer)).reason, "player");
});

test("storage helpers read, write and clear with a storage-like object", () => {
  const store = makeStorage();
  const world = makeWorld();
  const player = playerApi.createPlayer(20.5, 20);
  assert.equal(storage.readSave(store, "missing").reason, "empty");
  assert.equal(
    storage.writeSave(store, "save", world, player, {
      selected: 2,
      timeOfDay: 0.5,
      stats: { mined: 1, placed: 2, distance: 3, crystals: 0 },
      muted: false
    }).ok,
    true
  );
  const loaded = storage.readSave(store, "save");
  assert.equal(loaded.ok, true);
  assert.equal(loaded.value.selected, 2);
  assert.equal(storage.clearSave(store, "save").ok, true);
  assert.equal(storage.readSave(store, "save").reason, "empty");
});

test("write failures do not throw and are reported", () => {
  const store = {
    getItem: function () { return null; },
    setItem: function () { throw new Error("quota"); },
    removeItem: function () {}
  };
  const result = storage.writeSave(store, "save", makeWorld(), playerApi.createPlayer(4.5, 4), {
    selected: 0,
    timeOfDay: 0.2,
    stats: { mined: 0, placed: 0, distance: 0, crystals: 0 },
    muted: false
  });
  assert.equal(result.ok, false);
  assert.equal(result.reason, "write-failed");
});

test("out-of-range selections are clamped and bad stats are sanitized", () => {
  const payload = JSON.parse(
    storage.serializeSave(makeWorld(), playerApi.createPlayer(10.5, 10), {
      selected: 999,
      timeOfDay: 0.3,
      stats: { mined: -4, placed: -1, distance: -20, crystals: -2 },
      muted: false
    })
  );
  payload.selected = 999;
  payload.stats = { mined: -1, placed: -2, distance: -3, crystals: -4 };
  const parsed = storage.parseSave(JSON.stringify(payload));
  assert.equal(parsed.ok, true);
  assert.equal(parsed.value.selected, config.hotbar.length - 1);
  assert.equal(parsed.value.stats.mined, 0);
  assert.equal(parsed.value.stats.placed, 0);
  assert.equal(parsed.value.stats.distance, 0);
  assert.equal(parsed.value.stats.crystals, 0);
});
