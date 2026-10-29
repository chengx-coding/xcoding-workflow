const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const playerApi = require("../js/player.js");
const saveApi = require("../js/save.js");

function samplePayload() {
  const world = worldApi.createWorld(config.seed);
  const spawn = worldApi.findSpawn(world);
  worldApi.setBlock(world, spawn.x | 0, spawn.y - 1, config.blocks.planks);
  const player = playerApi.createPlayer(spawn.x, spawn.y);
  return saveApi.createPayload(
    JSON.parse(worldApi.serializeWorld(world)),
    playerApi.serializePlayer(player),
    3,
    { 1: 12, 2: 0, 3: 4 },
    1700000000000
  );
}

test("a save payload round-trips through a working store", () => {
  const store = saveApi.createMemoryStorage();
  const payload = samplePayload();
  const saved = saveApi.saveGame(store, config.saveKey, payload);
  assert.equal(saved.ok, true);
  assert.equal(saved.persisted, true);
  const loaded = saveApi.loadGame(store, config.saveKey);
  assert.equal(loaded.ok, true);
  assert.equal(loaded.payload.hotbarIndex, 3);
  assert.equal(loaded.payload.world.width, config.worldWidth);
  assert.equal(loaded.payload.player.x, payload.player.x);
  assert.deepEqual(loaded.payload.inventory, payload.inventory);
});

test("loading a missing key reports missing instead of throwing", () => {
  const store = saveApi.createMemoryStorage();
  const loaded = saveApi.loadGame(store, "nothing-here");
  assert.equal(loaded.ok, false);
  assert.equal(loaded.reason, "missing");
});

test("corrupt JSON is rejected", () => {
  const store = saveApi.createMemoryStorage();
  store.setItem(config.saveKey, "{not valid json");
  const loaded = saveApi.loadGame(store, config.saveKey);
  assert.equal(loaded.ok, false);
  assert.equal(loaded.reason, "corrupt");
});

test("an invalid or foreign payload is rejected", () => {
  const store = saveApi.createMemoryStorage();
  const payload = samplePayload();
  payload.version = 99;
  const saved = saveApi.saveGame(store, config.saveKey, payload);
  assert.equal(saved.ok, false);
  assert.equal(saved.reason, "invalid-payload");
});

test("a throwing storage falls back to memory and stays usable", () => {
  const hostile = {
    getItem: function () {
      throw new Error("denied");
    },
    setItem: function () {
      throw new Error("denied");
    },
    removeItem: function () {
      throw new Error("denied");
    }
  };
  const resolved = saveApi.resolveStorage(hostile);
  assert.equal(resolved.persisted, false);
  assert.equal(resolved.reason, "memory-fallback");
  const payload = samplePayload();
  assert.equal(saveApi.saveGame(resolved.storage, "fallback-key", payload).ok, true);
  assert.equal(saveApi.loadGame(resolved.storage, "fallback-key").ok, true);
});

test("clearGame removes a stored payload", () => {
  const store = saveApi.createMemoryStorage();
  const payload = samplePayload();
  saveApi.saveGame(store, "clear-me", payload);
  assert.equal(saveApi.loadGame(store, "clear-me").ok, true);
  saveApi.clearGame(store, "clear-me");
  assert.equal(saveApi.loadGame(store, "clear-me").ok, false);
});

test("payload validation rejects malformed world data", () => {
  const payload = samplePayload();
  payload.world.data.pop();
  assert.equal(saveApi.isValidPayload(payload), false);
});

