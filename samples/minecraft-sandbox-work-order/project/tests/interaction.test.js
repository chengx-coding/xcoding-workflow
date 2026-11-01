const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const Inventory = require("../js/inventory.js");
const Interaction = require("../js/interaction.js");

function makeWorld() {
  const width = 24;
  const height = 64;
  const groundRow = 45;
  const data = new Uint8Array(width * height);
  for (let x = 0; x < width; x += 1) {
    for (let y = groundRow; y < height; y += 1) {
      data[y * width + x] = y === groundRow ? config.blocks.grass : config.blocks.stone;
    }
  }
  return { width: width, height: height, seed: 1, data: data };
}

function makePlayer(x, y) {
  return { x: x === undefined ? 5.5 : x, y: y === undefined ? 45 : y, vx: 0, vy: 0, onGround: true, facing: 1, width: 0.7, height: 1.8 };
}

test("mining a solid block clears it and adds it to the inventory", () => {
  const world = makeWorld();
  const player = makePlayer();
  const inventory = Inventory.createInventory();
  const result = Interaction.mineBlock(world, player, 5, 45, inventory);
  assert.equal(result.ok, true);
  assert.equal(result.block, config.blocks.grass);
  assert.equal(Interaction.blockAt(world, 5, 45), config.blocks.air);
  assert.equal(Inventory.count(inventory, config.blocks.grass), 1);
});

test("mining air is refused with a reason", () => {
  const world = makeWorld();
  const result = Interaction.mineBlock(world, makePlayer(), 5, 44, Inventory.createInventory());
  assert.equal(result.ok, false);
  assert.match(result.reason, /nothing to mine/i);
});

test("mining outside the world is refused", () => {
  const world = makeWorld();
  const result = Interaction.mineBlock(world, makePlayer(), -1, 45, Inventory.createInventory());
  assert.equal(result.ok, false);
  assert.match(result.reason, /Outside the world/);
});

test("mining beyond reach is refused and changes nothing", () => {
  const world = makeWorld();
  const before = Interaction.blockAt(world, 20, 45);
  const result = Interaction.mineBlock(world, makePlayer(), 20, 45, Inventory.createInventory());
  assert.equal(result.ok, false);
  assert.match(result.reason, /Out of reach/);
  assert.equal(Interaction.blockAt(world, 20, 45), before);
});

test("placing a block fills an empty supported cell and consumes inventory", () => {
  const world = makeWorld();
  const player = makePlayer();
  const inventory = Inventory.createInventory({ 1: 2 });
  const result = Interaction.placeBlock(world, player, 6, 44, config.blocks.grass, inventory);
  assert.equal(result.ok, true);
  assert.equal(Interaction.blockAt(world, 6, 44), config.blocks.grass);
  assert.equal(Inventory.count(inventory, config.blocks.grass), 1);
});

test("placing over an occupied cell is refused", () => {
  const world = makeWorld();
  const result = Interaction.placeBlock(world, makePlayer(), 6, 45, config.blocks.grass, Inventory.createInventory({ 1: 1 }));
  assert.equal(result.ok, false);
  assert.match(result.reason, /not empty/);
  assert.equal(Interaction.blockAt(world, 6, 45), config.blocks.grass);
});

test("placing over the player body is refused", () => {
  const world = makeWorld();
  const result = Interaction.placeBlock(world, makePlayer(), 5, 44, config.blocks.grass, Inventory.createInventory({ 1: 1 }));
  assert.equal(result.ok, false);
  assert.match(result.reason, /standing there/);
  assert.equal(Interaction.blockAt(world, 5, 44), config.blocks.air);
});

test("placing without support is refused", () => {
  const world = makeWorld();
  const result = Interaction.placeBlock(world, makePlayer(), 6, 40, config.blocks.grass, Inventory.createInventory({ 1: 1 }));
  assert.equal(result.ok, false);
  assert.match(result.reason, /next to a block/);
  assert.equal(Interaction.blockAt(world, 6, 40), config.blocks.air);
});

test("placing beyond reach is refused", () => {
  const world = makeWorld();
  const result = Interaction.placeBlock(world, makePlayer(), 20, 44, config.blocks.grass, Inventory.createInventory({ 1: 1 }));
  assert.equal(result.ok, false);
  assert.match(result.reason, /Out of reach/);
});

test("placing with an empty palette slot is refused with the block name", () => {
  const world = makeWorld();
  const inventory = Inventory.createInventory({ 5: 0 });
  const result = Interaction.placeBlock(world, makePlayer(), 6, 44, config.blocks.leaves, inventory);
  assert.equal(result.ok, false);
  assert.match(result.reason, /No leaves left/);
  assert.equal(Interaction.blockAt(world, 6, 44), config.blocks.air);
});

test("placing an unknown block id is refused", () => {
  const world = makeWorld();
  const result = Interaction.placeBlock(world, makePlayer(), 6, 44, 0, Inventory.createInventory({ 1: 1 }));
  assert.equal(result.ok, false);
  assert.match(result.reason, /No block selected/);
});

test("reach is measured from the player body centre", () => {
  const player = makePlayer(5.5);
  assert.equal(Interaction.withinReach(player, 5, 45), true);
  assert.equal(Interaction.withinReach(player, 9, 45), true);
  assert.equal(Interaction.withinReach(player, 12, 45), false);
  assert.ok(Interaction.distanceToTile(player, 5, 45) > 0);
});

test("player overlap detection matches a strict AABB test", () => {
  const player = makePlayer(5.5);
  assert.equal(Interaction.playerOverlapsTile(player, 5, 44), true);
  assert.equal(Interaction.playerOverlapsTile(player, 6, 44), false);
  assert.equal(Interaction.playerOverlapsTile(player, 5, 43), true);
});

test("support detection requires a solid neighbour", () => {
  const world = makeWorld();
  assert.equal(Interaction.hasSupport(world, 6, 44), true);
  assert.equal(Interaction.hasSupport(world, 6, 40), false);
});

test("mining and placing round-trip a block through the palette", () => {
  const world = makeWorld();
  const player = makePlayer();
  const inventory = Inventory.createInventory();
  Interaction.mineBlock(world, player, 4, 45, inventory);
  assert.equal(Interaction.blockAt(world, 4, 45), config.blocks.air);
  const result = Interaction.placeBlock(world, player, 4, 45, config.blocks.grass, inventory);
  assert.equal(result.ok, true);
  assert.equal(Interaction.blockAt(world, 4, 45), config.blocks.grass);
  assert.equal(Inventory.count(inventory, config.blocks.grass), 0);
});

test("the sealed world floor cannot be mined", () => {
  const world = makeWorld();
  const player = makePlayer(5.5, 62);
  const result = Interaction.mineBlock(world, player, 5, world.height - 1, Inventory.createInventory());
  assert.equal(result.ok, false);
  assert.match(result.reason, /floor/i);
  assert.equal(Interaction.blockAt(world, 5, world.height - 1), config.blocks.stone);
  const above = Interaction.mineBlock(world, player, 5, world.height - 3, Inventory.createInventory());
  assert.equal(above.ok, true);
});

test("validateMine mirrors the mine rules without changing the world", () => {
  const world = makeWorld();
  const player = makePlayer(5.5, 45);
  const worldBefore = Array.from(world.data.slice(0, 64));
  const valid = Interaction.validateMine(world, player, 5, 45);
  assert.equal(valid.ok, true);
  assert.equal(valid.block, config.blocks.grass);
  assert.deepEqual(Array.from(world.data.slice(0, 64)), worldBefore, "validateMine changed the world");

  const air = Interaction.validateMine(world, player, 5, 44);
  assert.equal(air.ok, false);
  assert.match(air.reason, /nothing to mine/i);
  const far = Interaction.validateMine(world, player, 20, 45);
  assert.equal(far.ok, false);
  assert.match(far.reason, /Out of reach/);
  const floor = Interaction.validateMine(world, player, 5, world.height - 1);
  assert.equal(floor.ok, false);
  assert.match(floor.reason, /floor/i);
});
