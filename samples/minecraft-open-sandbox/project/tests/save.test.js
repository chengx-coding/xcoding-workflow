const test = require("node:test");
const assert = require("node:assert/strict");
const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const inv = require("../js/inventory.js");
const furnace = require("../js/furnace.js");
const save = require("../js/save.js");

function fixture() {
  const world = worldApi.createWorld(4242);
  worldApi.setBlock(world, 20, 20, config.blocks.planks);
  const inventory = inv.createInventory();
  inv.addItem(inventory, config.blocks.planks, 12);
  inv.addItem(inventory, config.itemIds.woodenPickaxe, 1);
  inv.setSelected(inventory, 4);
  const store = furnace.createStore();
  const state = furnace.get(store, 21, 20, true);
  state.input = { id: config.itemIds.rawIron, count: 2 };
  state.fuel = { id: config.itemIds.coal, count: 1 };
  return {
    world: world,
    player: {
      x: world.spawn.x,
      y: world.spawn.y,
      health: 17,
      hunger: 12,
      saturation: 2,
      facing: -1,
      spawnX: world.spawn.x,
      spawnY: world.spawn.y
    },
    inventory: inventory,
    time: 0.62,
    furnaces: store,
    settings: { audio: false, reducedMotion: true, minimap: false }
  };
}

test("world RLE encodes and decodes arbitrary data exactly", () => {
  const data = new Uint8Array(1000);
  for (let i = 0; i < data.length; i += 1) {
    data[i] = i % 7;
  }
  const encoded = save.encodeWorld(data);
  assert.ok(encoded.length > 0);
  assert.deepEqual(Array.from(save.decodeWorld(encoded, data.length)), Array.from(data));
});

test("a save payload round-trips world, player, inventory and furnace", () => {
  const state = fixture();
  const payload = save.buildPayload(state);
  const text = JSON.stringify(payload);
  const parsed = save.parsePayload(text);
  assert.equal(parsed.seed, state.world.seed);
  assert.equal(parsed.width, state.world.width);
  assert.equal(parsed.player.health, 17);
  assert.equal(parsed.player.facing, -1);
  assert.equal(parsed.time, 0.62);
  assert.equal(parsed.selected, 4);
  assert.equal(parsed.data.length, state.world.data.length);
  assert.deepEqual(Array.from(parsed.data.slice(0, 200)), Array.from(state.world.data.slice(0, 200)));
  assert.equal(inv.countItem(inv.deserializeInventory(parsed.inventory), config.blocks.planks), 12);
  const restoredFurnace = furnace.deserialize(parsed.furnaces);
  const restored = furnace.get(restoredFurnace, 21, 20, false);
  assert.equal(restored.input.count, 2);
});

test("corrupt or unsupported payloads fail closed", () => {
  assert.throws(() => save.parsePayload("{"), /JSON/i);
  assert.throws(() => save.parsePayload(JSON.stringify({ v: 99 })), /version/i);
  const state = fixture();
  const payload = save.buildPayload(state);
  const broken = Object.assign({}, payload, { blocks: "AAAA" });
  assert.throws(() => save.parsePayload(JSON.stringify(broken)), /world/i);
  const wrongLength = Object.assign({}, payload, { surface: [1, 2] });
  assert.throws(() => save.parsePayload(JSON.stringify(wrongLength)), /surface/i);
});

test("storage adapter reports success, missing saves and corruption", () => {
  const memory = {
    data: {},
    getItem(key) { return this.data[key] || null; },
    setItem(key, value) { this.data[key] = value; },
    removeItem(key) { delete this.data[key]; }
  };
  assert.equal(save.hasSave(memory), false);
  assert.equal(save.loadFromStorage(memory).ok, false);
  const payload = save.buildPayload(fixture());
  assert.equal(save.saveToStorage(payload, memory).ok, true);
  assert.equal(save.hasSave(memory), true);
  assert.equal(save.loadFromStorage(memory).ok, true);
  memory.data[config.saveKey] = "{not json";
  const corrupt = save.loadFromStorage(memory);
  assert.equal(corrupt.ok, false);
  assert.equal(corrupt.corrupt, true);
  assert.equal(save.clearSave(memory), true);
  assert.equal(save.hasSave(memory), false);
});
