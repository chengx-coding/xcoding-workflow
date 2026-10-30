const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const interaction = require("../js/interaction.js");
const playerApi = require("../js/player.js");

function makeWorld(blocks) {
  const width = 12;
  const height = 12;
  const data = new Uint8Array(width * height);
  for (let x = 0; x < width; x += 1) {
    data[8 * width + x] = config.blocks.stone;
  }
  (blocks || []).forEach((entry) => {
    data[entry.y * width + entry.x] = entry.block;
  });
  return { width, height, seed: 1, data };
}

test("a new inventory starts from the configured starter stock", () => {
  const inventory = interaction.createInventory();
  assert.equal(interaction.countOf(inventory, config.blocks.grass), config.starterStock[config.blocks.grass]);
  assert.equal(interaction.countOf(inventory, config.blocks.glass), config.starterStock[config.blocks.glass]);
  assert.equal(inventory.selected, 0);
});

test("adding blocks respects the stack cap", () => {
  const inventory = interaction.createInventory();
  inventory.counts[config.blocks.stone] = config.maxStack - 2;
  interaction.addBlock(inventory, config.blocks.stone, 5);
  assert.equal(interaction.countOf(inventory, config.blocks.stone), config.maxStack);
});

test("spending blocks refuses an empty stack", () => {
  const inventory = interaction.createInventory();
  inventory.counts[config.blocks.stone] = 1;
  assert.equal(interaction.spendBlock(inventory, config.blocks.stone, 2), false);
  assert.equal(interaction.countOf(inventory, config.blocks.stone), 1);
  assert.equal(interaction.spendBlock(inventory, config.blocks.stone, 1), true);
  assert.equal(interaction.countOf(inventory, config.blocks.stone), 0);
});

test("slot selection wraps in both directions", () => {
  const inventory = interaction.createInventory();
  assert.equal(interaction.selectSlot(inventory, -1, 9), 8);
  assert.equal(interaction.selectSlot(inventory, 9, 9), 0);
  assert.equal(interaction.selectSlot(inventory, 4, 9), 4);
  assert.equal(interaction.cycleSlot(inventory, 1, 9), 5);
  assert.equal(interaction.cycleSlot(inventory, -2, 9), 3);
});

test("number keys map to slots and reject out-of-range digits", () => {
  const inventory = interaction.createInventory();
  assert.equal(interaction.selectByNumber(inventory, 3, 9).selected, 2);
  assert.equal(interaction.selectByNumber(inventory, 0, 9).ok, false);
  assert.equal(interaction.selectByNumber(inventory, 10, 9).ok, false);
});

test("the selected block follows the hotbar order", () => {
  const inventory = interaction.createInventory();
  interaction.selectSlot(inventory, 7, config.hotbar.length);
  assert.equal(interaction.selectedBlock(inventory), config.hotbar[7]);
  assert.equal(config.hotbar[7], config.blocks.cobblestone);
  assert.equal(config.hotbar.length, 9);
});

test("hotbarModel exposes nine slots, counts and the eighth block", () => {
  const inventory = interaction.createInventory();
  const model = interaction.hotbarModel(inventory);
  assert.equal(model.length, 9);
  assert.equal(model[0].selected, true);
  assert.equal(model[7].block, config.blocks.cobblestone);
  assert.equal(model[7].digit, 8);
  assert.equal(model[7].name, "Cobblestone");
  assert.equal(model[8].block, config.blocks.glass);
});

test("targetCell converts screen pixels to world cells", () => {
  const camera = { x: 120, y: 48 };
  const cell = interaction.targetCell(camera, 120, 96, 24);
  assert.deepEqual(cell, { x: 10, y: 6 });
});

test("reach is measured from the player centre", () => {
  const player = playerApi.createPlayer(5.5, 8);
  assert.equal(interaction.inReach(player, 6, 7, 5), true);
  assert.equal(interaction.inReach(player, 11, 7, 5), false);
});

test("mining checks bounds, emptiness and reach", () => {
  const player = playerApi.createPlayer(2.5, 8);
  const world = makeWorld();
  assert.equal(interaction.canMine(world, player, 2, 8, 5).reason, "");
  assert.equal(interaction.canMine(world, player, 2, 4, 5).reason, "empty");
  assert.equal(interaction.canMine(world, player, -1, 4, 5).reason, "bounds");
  assert.equal(interaction.canMine(world, player, 9, 8, 5).reason, "reach");
});

test("mining removes the block and adds it to the inventory", () => {
  const player = playerApi.createPlayer(2.5, 8);
  const world = makeWorld();
  const inventory = interaction.createInventory();
  const before = interaction.countOf(inventory, config.blocks.stone);
  const result = interaction.mineBlock(world, player, inventory, 2, 8, 5);
  assert.equal(result.ok, true);
  assert.equal(result.block, config.blocks.stone);
  assert.equal(world.data[8 * world.width + 2], config.blocks.air);
  assert.equal(interaction.countOf(inventory, config.blocks.stone), before + 1);
});

test("placement targets the adjacent empty cell of a hovered block", () => {
  const player = playerApi.createPlayer(2.5, 8);
  const world = makeWorld();
  const target = interaction.placementTarget(world, player, 5, 8);
  assert.deepEqual(target, { x: 5, y: 7 });
  assert.deepEqual(interaction.placementTarget(world, player, 2, 4), { x: 2, y: 4 });
  assert.equal(interaction.placementTarget(world, player, 99, 99), null);
});

test("placement is refused inside the player", () => {
  const player = playerApi.createPlayer(5.5, 8);
  const world = makeWorld();
  const inventory = interaction.createInventory();
  assert.equal(interaction.canPlace(world, player, inventory, 5, 7, 5).reason, "player");
});

test("placement is refused on occupied, floating, unreachable or empty stock cells", () => {
  const player = playerApi.createPlayer(2.5, 8);
  const farPlayer = playerApi.createPlayer(5.5, 8);
  const world = makeWorld();
  const inventory = interaction.createInventory();
  assert.equal(interaction.canPlace(world, player, inventory, 2, 8, 5).reason, "occupied");
  assert.equal(interaction.canPlace(world, player, inventory, 9, 0, 5).reason, "reach");
  assert.equal(interaction.canPlace(world, player, inventory, 3, 2, 5).reason, "floating");
  inventory.counts[config.hotbar[0]] = 0;
  assert.equal(interaction.canPlace(world, farPlayer, inventory, 2, 7, 5).reason, "stock");
});

test("a valid placement spends one block and writes the cell", () => {
  const player = playerApi.createPlayer(2.5, 8);
  const world = makeWorld();
  const inventory = interaction.createInventory();
  const block = interaction.selectedBlock(inventory);
  const before = interaction.countOf(inventory, block);
  const result = interaction.placeBlock(world, player, inventory, 3, 7, 5);
  assert.equal(result.ok, true);
  assert.equal(world.data[7 * world.width + 3], block);
  assert.equal(interaction.countOf(inventory, block), before - 1);
});

test("mining progress accumulates and resets when the target changes", () => {
  const state = interaction.createMiningState();
  const first = interaction.advanceMining(state, { x: 1, y: 1 }, config.blocks.stone, 0.4);
  assert.ok(first.progress > 0 && first.progress < 1);
  assert.equal(first.done, false);
  const second = interaction.advanceMining(state, { x: 1, y: 1 }, config.blocks.stone, 0.5);
  assert.equal(second.done, true);
  const moved = interaction.advanceMining(state, { x: 2, y: 1 }, config.blocks.stone, 0.1);
  assert.ok(moved.progress < 0.2);
});

test("miningProgress is zero for a different cell", () => {
  const state = interaction.createMiningState();
  interaction.advanceMining(state, { x: 1, y: 1 }, config.blocks.dirt, 0.2);
  assert.equal(interaction.miningProgress(state, { x: 2, y: 1 }), 0);
  assert.ok(interaction.miningProgress(state, { x: 1, y: 1 }) > 0);
});

test("harder materials take longer to break", () => {
  assert.ok(interaction.blockHardness(config.blocks.stone) > interaction.blockHardness(config.blocks.dirt));
  assert.ok(interaction.blockHardness(config.blocks.leaves) < interaction.blockHardness(config.blocks.cobblestone));
});

test("hotbar order matches the configured block palette", () => {
  assert.deepEqual(Array.from(config.hotbar), [
    config.blocks.grass,
    config.blocks.dirt,
    config.blocks.stone,
    config.blocks.sand,
    config.blocks.wood,
    config.blocks.leaves,
    config.blocks.planks,
    config.blocks.cobblestone,
    config.blocks.glass
  ]);
});

test("cloneInventory copies counts and selection without aliasing", () => {
  const inventory = interaction.createInventory();
  interaction.selectSlot(inventory, 4, 9);
  const clone = interaction.cloneInventory(inventory);
  assert.deepEqual(clone, inventory);
  clone.counts[config.blocks.stone] = 0;
  assert.notEqual(inventory.counts[config.blocks.stone], 0);
});
