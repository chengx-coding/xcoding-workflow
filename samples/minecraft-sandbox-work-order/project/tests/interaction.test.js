const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const playerApi = require("../js/player.js");
const interaction = require("../js/interaction.js");

function flatWorld() {
  const world = worldApi.createWorld(config.seed);
  world.data.fill(config.blocks.air);
  for (let x = 0; x < world.width; x += 1) {
    worldApi.setBlock(world, x, 10, config.blocks.stone);
  }
  return world;
}

test("screen coordinates map to world cells through the camera", () => {
  assert.deepEqual(interaction.cellFromScreen({ x: 0, y: 0 }, 24, 48, 24), { x: 1, y: 2 });
  assert.deepEqual(interaction.cellFromScreen({ x: 24, y: 24 }, 0, 0, 24), { x: 1, y: 1 });
});

test("mining is limited to solid blocks within reach", () => {
  const world = flatWorld();
  const player = playerApi.createPlayer(5, 10);

  assert.equal(interaction.canMine(world, player, 5, 10), true);
  assert.equal(interaction.canMine(world, player, 20, 10), false);
  assert.equal(interaction.canMine(world, player, 5, 5), false);

  assert.equal(interaction.mineBlock(world, player, 5, 10), true);
  assert.equal(worldApi.getBlock(world, 5, 10), config.blocks.air);
  assert.equal(interaction.mineBlock(world, player, 5, 10), false);
});

test("placement requires an empty, reachable, supported cell", () => {
  const world = flatWorld();
  const player = playerApi.createPlayer(5, 10);

  assert.equal(interaction.canPlace(world, player, 6, 9, config.blocks.stone), true);
  assert.equal(interaction.placeBlock(world, player, 6, 9, config.blocks.stone), true);
  assert.equal(worldApi.getBlock(world, 6, 9), config.blocks.stone);

  assert.equal(interaction.canPlace(world, player, 6, 10, config.blocks.stone), false);
  assert.equal(interaction.canPlace(world, player, 5, 7, config.blocks.stone), false);
  assert.equal(interaction.canPlace(world, player, 20, 9, config.blocks.stone), false);
  assert.equal(interaction.canPlace(world, player, -1, 9, config.blocks.stone), false);
  assert.equal(interaction.canPlace(world, player, 6, 9, config.blocks.air), false);
});

test("placement never overwrites the player", () => {
  const world = flatWorld();
  const player = playerApi.createPlayer(5, 10);

  assert.equal(interaction.overlapsPlayer(player, 5, 9), true);
  assert.equal(interaction.canPlace(world, player, 5, 9, config.blocks.wood), false);
  assert.equal(interaction.placeBlock(world, player, 5, 9, config.blocks.wood), false);
  assert.equal(worldApi.getBlock(world, 5, 9), config.blocks.air);
});

test("right-clicking a solid block resolves to an empty adjacent cell", () => {
  const world = flatWorld();
  const player = playerApi.createPlayer(5, 10);

  assert.deepEqual(interaction.adjacentPlacementCell(world, player, 6, 10), { x: 6, y: 9 });
  assert.deepEqual(interaction.adjacentPlacementCell(world, player, 6, 9), { x: 6, y: 9 });
  assert.equal(interaction.adjacentPlacementCell(world, player, 20, 10), null);
});
