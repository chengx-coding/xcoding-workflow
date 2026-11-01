const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const save = require("../js/save.js");

function makeState() {
  const world = worldApi.createWorld(config.seed);
  const spawn = worldApi.getSpawn(world);
  worldApi.setBlock(world, spawn.x + 2, spawn.y - 1, config.blocks.planks);
  return {
    world: world,
    player: { x: spawn.x + 0.5, y: spawn.y, vx: 0, vy: 0, facing: 1 },
    inventory: { items: { wood: 3, torch: 2 }, selected: 2 },
    time: { tick: 42.5, day: 3 }
  };
}

test("snapshot round-trips the world, player, inventory and time", () => {
  const state = makeState();
  const snapshot = save.createSnapshot(state);
  const text = save.encodeSnapshot(snapshot);
  const decoded = save.decodeSnapshot(text);
  assert.equal(decoded.width, config.worldWidth);
  assert.equal(decoded.height, config.worldHeight);
  assert.equal(decoded.seed, config.seed);
  assert.deepEqual(decoded.inventory.items, { wood: 3, torch: 2 });
  assert.equal(decoded.inventory.selected, 2);
  assert.equal(decoded.time.tick, 42.5);
  assert.equal(decoded.time.day, 3);
  const restored = save.worldFromSnapshot(decoded);
  assert.deepEqual(Array.from(restored.data), Array.from(state.world.data));
});

test("corrupt or foreign save data is rejected with a clear error", () => {
  assert.throws(() => save.decodeSnapshot("{not json"), /not valid JSON/);
  const state = makeState();
  const snapshot = save.createSnapshot(state);
  snapshot.version = 99;
  assert.throws(() => save.decodeSnapshot(JSON.stringify(snapshot)), /Unsupported save version/);
  const badDimensions = JSON.parse(JSON.stringify(save.createSnapshot(state)));
  badDimensions.width = 2;
  assert.throws(() => save.decodeSnapshot(JSON.stringify(badDimensions)), /out of range|cover/);
  const badRuns = JSON.parse(JSON.stringify(save.createSnapshot(state)));
  badRuns.blocks = [[0, 1]];
  assert.throws(() => save.decodeSnapshot(JSON.stringify(badRuns)), /cover/);
  const badInventory = JSON.parse(JSON.stringify(save.createSnapshot(state)));
  badInventory.inventory.items.wood = -1;
  assert.throws(() => save.decodeSnapshot(JSON.stringify(badInventory)), /inventory count/);
});

test("memory storage saves, loads and reports missing data", () => {
  const storage = save.createMemoryStorage();
  const state = makeState();
  const first = save.loadGame(storage);
  assert.equal(first.ok, false);
  assert.equal(first.missing, true);
  const saved = save.saveGame(storage, state);
  assert.equal(saved.ok, true);
  assert.ok(saved.bytes > 1000);
  const loaded = save.loadGame(storage);
  assert.equal(loaded.ok, true);
  assert.equal(loaded.snapshot.seed, config.seed);
  assert.equal(save.clearGame(storage), true);
  assert.equal(save.loadGame(storage).missing, true);
});

test("storage failures are reported instead of thrown", () => {
  const broken = {
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
  const state = makeState();
  const result = save.saveGame(broken, state);
  assert.equal(result.ok, false);
  assert.match(result.error, /denied/);
  const load = save.loadGame(broken);
  assert.equal(load.ok, false);
  assert.match(load.error, /denied/);
  assert.equal(save.clearGame(broken), false);
});

test("snapshot validation rejects out-of-world player positions and bad time", () => {
  const state = makeState();
  const snapshot = save.createSnapshot(state);
  const offWorld = JSON.parse(JSON.stringify(snapshot));
  offWorld.player.x = 10000;
  assert.throws(() => save.validateSnapshot(offWorld), /outside the world/);
  const badTime = JSON.parse(JSON.stringify(snapshot));
  badTime.time.tick = config.dayLengthSeconds + 1;
  assert.throws(() => save.validateSnapshot(badTime), /out of range/);
});
