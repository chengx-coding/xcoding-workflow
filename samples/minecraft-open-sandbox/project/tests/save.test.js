const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const inventory = require("../js/inventory.js");
const clockApi = require("../js/time.js");
const tasks = require("../js/tasks.js");
const saveApi = require("../js/save.js");

const B = config.blocks;
const GROUND = Math.floor(config.worldHeight * 0.65);

function gameState() {
  const world = worldApi.createWorld(config.seed);
  worldApi.setBlock(world, 4, GROUND - 1, B.planks);
  const bag = inventory.createInventory();
  inventory.add(bag, B.wood, 3);
  inventory.add(bag, 110, 1);
  const progress = tasks.createProgress();
  tasks.noteCollected(progress, B.wood, 3);
  tasks.sync(progress);
  return {
    seed: config.seed,
    world: world,
    player: { x: 10.5, y: GROUND, health: 17, facing: -1 },
    inventory: bag,
    clock: clockApi.createClock({ start: 0.6, day: 3 }),
    progress: progress,
    settings: { muted: true, zoom: 1.5, backdropMode: true, volume: 0.3 }
  };
}

function fakeStorage(options) {
  const store = Object.create(null);
  return {
    getItem: function (key) {
      if (options && options.throwOnRead) {
        throw new Error("blocked");
      }
      return key in store ? store[key] : null;
    },
    setItem: function (key, value) {
      if (options && options.throwOnWrite) {
        throw new Error("quota");
      }
      store[key] = String(value);
    },
    removeItem: function (key) {
      delete store[key];
    }
  };
}

test("a full save envelope round-trips world, player, inventory, clock and progress", () => {
  const state = gameState();
  const envelope = saveApi.createEnvelope(state);
  const parsed = saveApi.parse(saveApi.serialize(envelope));
  assert.equal(parsed.seed, config.seed);
  const world = saveApi.loadWorld(parsed);
  assert.equal(worldApi.getBlock(world, 4, GROUND - 1), B.planks);
  assert.deepEqual(Array.from(world.data), Array.from(state.world.data));
  assert.equal(parsed.player.x, 10.5);
  assert.equal(parsed.player.health, 17);
  assert.equal(parsed.player.facing, -1);
  const bag = inventory.deserialize(parsed.inventory);
  assert.equal(inventory.count(bag, B.wood), 3);
  assert.equal(inventory.count(bag, 110), 1);
  assert.ok(Math.abs(parsed.clock.t - 0.6) < 1e-9);
  assert.equal(parsed.clock.day, 3);
  const progress = tasks.deserialize(parsed.progress);
  assert.equal(progress.tasks.first_wood, true);
  assert.equal(parsed.settings.muted, true);
  assert.equal(parsed.settings.zoom, 1.5);
});

test("invalid or foreign saves are rejected with a reason", () => {
  assert.throws(function () { saveApi.parse("not json"); }, /not valid JSON/);
  assert.throws(function () { saveApi.parse("{}"); }, /Unsupported save version/);
  const envelope = saveApi.createEnvelope(gameState());
  envelope.version = 99;
  assert.throws(function () { saveApi.parse(JSON.stringify(envelope)); }, /Unsupported save version/);
  const withoutWorld = saveApi.createEnvelope(gameState());
  delete withoutWorld.world;
  assert.throws(function () { saveApi.parse(JSON.stringify(withoutWorld)); }, /no world/);
});

test("local storage is used when available", () => {
  const storage = saveApi.createStorage({ localStorage: fakeStorage() });
  assert.equal(storage.kind, "local");
  assert.equal(storage.available, true);
  const envelope = saveApi.createEnvelope(gameState());
  const result = saveApi.saveGame(storage, envelope);
  assert.equal(result.ok, true);
  const loaded = saveApi.loadGame(storage);
  assert.equal(loaded.seed, config.seed);
  assert.equal(loaded.settings.zoom, 1.5);
});

test("blocked browser storage degrades to a working in-memory fallback", () => {
  const storage = saveApi.createStorage({ localStorage: fakeStorage({ throwOnWrite: true }) });
  assert.equal(storage.kind, "memory");
  assert.equal(storage.available, false);
  assert.ok(storage.error && storage.error.length > 0, "the failure is surfaced, not swallowed");
  const envelope = saveApi.createEnvelope(gameState());
  assert.equal(saveApi.saveGame(storage, envelope).ok, true);
  assert.equal(saveApi.loadGame(storage).seed, config.seed);
});

test("a corrupt stored payload is reported instead of crashing", () => {
  const storage = saveApi.createStorage({});
  storage.save("{bad json");
  const loaded = saveApi.loadGame(storage);
  assert.ok(loaded.error);
  assert.equal(saveApi.loadGame(storage).error, loaded.error);
});

test("empty storage loads nothing", () => {
  const storage = saveApi.createStorage({});
  assert.equal(saveApi.loadGame(storage), null);
});

