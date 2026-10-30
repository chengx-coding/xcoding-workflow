const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const storage = require("../js/storage.js");
const worldApi = require("../js/world.js");

function memoryBackend() {
  const map = new Map();
  return {
    map,
    getItem(key) {
      return map.has(key) ? map.get(key) : null;
    },
    setItem(key, value) {
      map.set(key, String(value));
    },
    removeItem(key) {
      map.delete(key);
    }
  };
}

function sampleState() {
  const world = worldApi.createWorld(7);
  return {
    seed: world.seed,
    worldText: worldApi.serializeWorld(world),
    player: { x: 12.5, y: 30 },
    inventory: { counts: { 1: 4, 2: 6 }, selected: 2 },
    timeOfDay: 0.42
  };
}

test("a saved game round-trips through the store", () => {
  const backend = memoryBackend();
  const store = storage.createStore({ storage: backend });
  assert.deepEqual(store.saveGame(sampleState()), { ok: true });
  const loaded = store.loadGame();
  assert.equal(loaded.ok, true);
  assert.equal(loaded.state.seed, 7);
  assert.equal(loaded.state.player.x, 12.5);
  assert.equal(loaded.state.inventory.selected, 2);
  assert.equal(loaded.state.timeOfDay, 0.42);
  assert.ok(loaded.state.worldText.length > 1000);
});

test("an empty store reports an empty result", () => {
  const store = storage.createStore({ storage: memoryBackend() });
  assert.deepEqual(store.loadGame(), { ok: false, reason: "empty" });
});

test("corrupt JSON is rejected instead of throwing", () => {
  const backend = memoryBackend();
  backend.setItem(config.saveKey, "{ not json");
  const store = storage.createStore({ storage: backend });
  assert.deepEqual(store.loadGame(), { ok: false, reason: "corrupt" });
});

test("payloads from another schema version are rejected", () => {
  const backend = memoryBackend();
  const payload = JSON.parse(JSON.stringify({ ...sampleState(), schemaVersion: 1, world: "x" }));
  backend.setItem(config.saveKey, JSON.stringify(payload));
  const store = storage.createStore({ storage: backend });
  assert.equal(store.loadGame().reason, "corrupt");
});

test("payloads missing required fields are rejected", () => {
  const backend = memoryBackend();
  backend.setItem(
    config.saveKey,
    JSON.stringify({ schemaVersion: config.saveVersion, seed: 1, player: { x: 1, y: 2 }, inventory: { counts: {}, selected: 0 }, timeOfDay: 0.2 })
  );
  const store = storage.createStore({ storage: backend });
  assert.equal(store.loadGame().reason, "corrupt");
});

test("a storage backend that throws is reported as unavailable", () => {
  const backend = {
    getItem() {
      throw new Error("blocked");
    },
    setItem() {
      throw new Error("blocked");
    },
    removeItem() {
      throw new Error("blocked");
    }
  };
  const store = storage.createStore({ storage: backend });
  assert.equal(store.saveGame(sampleState()).reason, "unavailable");
  assert.equal(store.loadGame().reason, "unavailable");
  assert.equal(store.clearGame().reason, "unavailable");
});

test("a missing backend degrades to unavailable", () => {
  const store = storage.createStore({ storage: null });
  assert.equal(store.available(), false);
  assert.equal(store.loadGame().reason, "unavailable");
});

test("clearGame removes the saved payload", () => {
  const backend = memoryBackend();
  const store = storage.createStore({ storage: backend });
  store.saveGame(sampleState());
  assert.equal(store.clearGame().ok, true);
  assert.equal(store.loadGame().reason, "empty");
});

test("settings persist independently from the world", () => {
  const backend = memoryBackend();
  const store = storage.createStore({ storage: backend });
  assert.equal(store.saveSettings({ muted: true }).ok, true);
  assert.equal(store.loadSettings().muted, true);
  backend.setItem(config.settingsKey, "broken");
  assert.equal(store.loadSettings().muted, false);
});

test("validateState rejects non-object payloads", () => {
  assert.equal(storage.validateState(null).ok, false);
  assert.equal(storage.validateState([]).ok, false);
  assert.equal(storage.validateState("text").ok, false);
});

test("saving an invalid state is refused rather than throwing", () => {
  const store = storage.createStore({ storage: memoryBackend() });
  assert.deepEqual(store.saveGame(null), { ok: false, reason: "invalid" });
  assert.deepEqual(store.saveGame({ seed: 1 }), { ok: false, reason: "invalid" });
});
