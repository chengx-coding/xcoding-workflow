const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const playerApi = require("../js/player.js");
const inventoryApi = require("../js/inventory.js");
const progression = require("../js/progression.js");
const saveApi = require("../js/save.js");

const GROUND = worldApi.GROUND_ROW;

function memoryStorage(initial) {
  const map = new Map(Object.entries(initial || {}));
  return {
    getItem: function getItem(key) {
      return map.has(key) ? map.get(key) : null;
    },
    setItem: function setItem(key, value) {
      map.set(key, String(value));
    },
    removeItem: function removeItem(key) {
      map.delete(key);
    }
  };
}

function gameState() {
  const world = worldApi.createWorld(config.seed);
  const player = playerApi.createPlayer(24.5, GROUND);
  const inventory = inventoryApi.createInventory();
  const progress = progression.createProgress();
  const clock = { day: 2, time: 0.35 };
  return { world, player, inventory, progress, clock };
}

test("a captured save has the versioned envelope", () => {
  const state = gameState();
  const payload = saveApi.capture(state);
  assert.equal(payload.schema, 1);
  assert.equal(payload.version, config.version);
  assert.equal(payload.seed, state.world.seed);
  assert.equal(typeof payload.savedAt, "number");
  assert.equal(payload.clock.day, 2);
  assert.ok(Array.isArray(payload.world.rle));
  assert.equal(saveApi.validate(payload), "");
});

test("save and load round-trip world, inventory, progress and clock", () => {
  const state = gameState();
  worldApi.setBlock(state.world, 12, GROUND, config.blocks.air);
  worldApi.setBlock(state.world, 13, GROUND - 1, config.blocks.planks);
  inventoryApi.add(state.inventory, config.blocks.planks, 12);
  inventoryApi.add(state.inventory, config.items.pick_stone, 1);
  inventoryApi.select(state.inventory, 2);
  state.progress.stage = 4;
  state.progress.stats.blocksMined = 31;
  state.progress.stats.playtime = 95;

  const storage = memoryStorage();
  const saved = saveApi.save(storage, state);
  assert.equal(saved.ok, true);
  assert.ok(saved.bytes > 100);
  assert.ok(saved.bytes < 120000, `save should stay small, got ${saved.bytes}`);

  const loaded = saveApi.load(storage);
  assert.equal(loaded.ok, true);
  assert.equal(worldApi.getBlock(loaded.state.world, 12, GROUND), config.blocks.air);
  assert.equal(worldApi.getBlock(loaded.state.world, 13, GROUND - 1), config.blocks.planks);
  assert.equal(inventoryApi.countOf(loaded.state.inventory, config.blocks.planks), 12);
  assert.equal(inventoryApi.countOf(loaded.state.inventory, config.items.pick_stone), 1);
  assert.equal(loaded.state.inventory.selected, 2);
  assert.equal(loaded.state.progress.stage, 4);
  assert.equal(loaded.state.progress.stats.blocksMined, 31);
  assert.equal(loaded.state.clock.day, 2);
  assert.ok(Math.abs(loaded.state.clock.time - 0.35) < 1e-9);
});

test("summaries expose the saved state for the title screen", () => {
  const storage = memoryStorage();
  const state = gameState();
  state.progress.stats.blocksMined = 42;
  state.progress.stats.playtime = 305;
  saveApi.save(storage, state);
  const result = saveApi.read(storage);
  const summary = saveApi.summarize(result.data);
  assert.equal(summary.day, 2);
  assert.equal(summary.blocksMined, 42);
  assert.equal(summary.playtime, 305);
  assert.ok(summary.savedAt > 0);
  assert.equal(saveApi.formatDuration(305), "5m 05s");
  assert.equal(saveApi.formatDuration(3661), "1h 1m");
});

test("clearing the save removes the continue offer", () => {
  const storage = memoryStorage();
  const state = gameState();
  saveApi.save(storage, state);
  assert.equal(saveApi.hasSave(storage), true);
  assert.equal(saveApi.clear(storage), true);
  assert.equal(saveApi.hasSave(storage), false);
  assert.equal(saveApi.load(storage).error, "empty");
});

test("corrupt saves are rejected rather than crashing", () => {
  const storage = memoryStorage({ [config.saveKey]: "{not json" });
  assert.equal(saveApi.read(storage).error, "corrupt");
  const noSchema = memoryStorage({ [config.saveKey]: JSON.stringify({ world: {} }) });
  assert.equal(saveApi.read(noSchema).error, "corrupt");
  const badPlayer = memoryStorage({
    [config.saveKey]: JSON.stringify({
      schema: 1,
      world: JSON.parse(worldApi.serializeWorld(worldApi.createWorld(1))),
      player: { x: "nope" }
    })
  });
  const result = saveApi.load(badPlayer);
  assert.equal(result.ok, false);
  assert.equal(result.error, "corrupt");
});

test("storage failures are surfaced, not thrown", () => {
  const storage = {
    getItem: function getItem() {
      return null;
    },
    setItem: function setItem() {
      const error = new Error("no space");
      error.name = "QuotaExceededError";
      throw error;
    },
    removeItem: function removeItem() {}
  };
  const result = saveApi.save(storage, gameState());
  assert.equal(result.ok, false);
  assert.equal(result.error, "quota-exceeded");
  assert.equal(saveApi.load({}).ok, false);
  assert.equal(saveApi.save(null, gameState()).error, "storage-unavailable");
});
