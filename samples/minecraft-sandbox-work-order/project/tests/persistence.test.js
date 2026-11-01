const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const Inventory = require("../js/inventory.js");
const Persistence = require("../js/persistence.js");
const worldApi = require("../js/world.js");

function makeState() {
  const world = worldApi.createWorld(config.seed);
  worldApi.setBlock(world, 20, 20, config.blocks.brick);
  const inventory = Inventory.starterInventory();
  Inventory.add(inventory, config.blocks.leaves, 3);
  return {
    world: world,
    player: { x: 12.5, y: config.baseSurfaceRow, facing: -1 },
    inventory: inventory,
    time: 0.42,
    selected: 4
  };
}

test("state serialization round-trips world, player, inventory, time and selection", () => {
  const state = makeState();
  const restored = Persistence.deserializeState(Persistence.serializeState(state));
  assert.equal(restored.world.width, state.world.width);
  assert.equal(restored.world.seed, state.world.seed);
  assert.equal(worldApi.getBlock(restored.world, 20, 20), config.blocks.brick);
  assert.equal(restored.player.x, 12.5);
  assert.equal(restored.player.y, config.baseSurfaceRow);
  assert.equal(restored.player.facing, -1);
  assert.equal(restored.time, 0.42);
  assert.equal(restored.selected, 4);
  assert.equal(Inventory.count(restored.inventory, config.blocks.leaves), 3);
});

test("save and load through a storage adapter restores the state", () => {
  const storage = Persistence.createMemoryStorage();
  const state = makeState();
  const saved = Persistence.saveState(storage, state);
  assert.equal(saved.ok, true);
  const loaded = Persistence.loadState(storage);
  assert.equal(loaded.ok, true);
  assert.equal(loaded.state.selected, 4);
  assert.equal(loaded.state.player.x, 12.5);
});

test("a missing save reports an empty reason", () => {
  const loaded = Persistence.loadState(Persistence.createMemoryStorage());
  assert.equal(loaded.ok, false);
  assert.equal(loaded.reason, "empty");
});

test("corrupt JSON falls back with a corrupt reason", () => {
  const storage = Persistence.createMemoryStorage({ [config.saveKey]: "{oops" });
  const loaded = Persistence.loadState(storage);
  assert.equal(loaded.ok, false);
  assert.equal(loaded.reason, "corrupt");
});

test("an unsupported save version is reported separately", () => {
  const storage = Persistence.createMemoryStorage();
  const payload = JSON.parse(Persistence.serializeState(makeState()));
  payload.v = 1;
  storage.setItem(config.saveKey, JSON.stringify(payload));
  const loaded = Persistence.loadState(storage);
  assert.equal(loaded.ok, false);
  assert.equal(loaded.reason, "version");
});

test("a save with a broken world payload is corrupt", () => {
  const storage = Persistence.createMemoryStorage();
  const payload = JSON.parse(Persistence.serializeState(makeState()));
  payload.world.blocks = [[1, 1]];
  storage.setItem(config.saveKey, JSON.stringify(payload));
  assert.equal(Persistence.loadState(storage).reason, "corrupt");
});

test("an unavailable storage adapter fails safely", () => {
  const storage = {
    getItem: function () {
      throw new Error("blocked");
    },
    setItem: function () {
      throw new Error("quota");
    }
  };
  assert.equal(Persistence.loadState(storage).reason, "unavailable");
  assert.equal(Persistence.saveState(storage, makeState()).reason, "unavailable");
});

test("invalid selection and time values are rejected or normalized", () => {
  const payload = JSON.parse(Persistence.serializeState(makeState()));
  payload.selected = 99;
  assert.throws(() => Persistence.deserializeState(JSON.stringify(payload)), /hotbar/);
  payload.selected = 1;
  payload.time = 3.25;
  const restored = Persistence.deserializeState(JSON.stringify(payload));
  assert.equal(restored.time, 0.25);
});

test("clearState removes the payload", () => {
  const storage = Persistence.createMemoryStorage();
  Persistence.saveState(storage, makeState());
  assert.equal(Persistence.clearState(storage), true);
  assert.equal(Persistence.loadState(storage).reason, "empty");
});
