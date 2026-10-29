const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const playerApi = require("../js/player.js");
const interaction = require("../js/interaction.js");

function makeWorld() {
  const width = 40;
  const height = 24;
  const surface = 16;
  const data = new Uint8Array(width * height);
  const ground = new Int16Array(width);
  const biomes = new Uint8Array(width);
  for (let x = 0; x < width; x += 1) {
    ground[x] = surface;
    for (let y = surface; y < height; y += 1) {
      data[y * width + x] = y === surface ? config.blocks.grass : config.blocks.stone;
    }
  }
  data[13 * width + 14] = config.blocks.wood;
  data[12 * width + 14] = config.blocks.leaves;
  return { width: width, height: height, seed: 7, data: data, ground: ground, biomes: biomes };
}

test("inspectTarget identifies mineable blocks within reach", () => {
  const world = makeWorld();
  const player = playerApi.createPlayer(10.5, 16);
  const hover = interaction.inspectTarget(world, player, 11.2, 15.2, config.blocks.stone, config.reach);
  assert.equal(hover.x, 11);
  assert.equal(hover.y, 15);
  assert.equal(hover.block, config.blocks.air);
  assert.equal(hover.empty, true);
});

test("mining removes one block and rejects empty, bedrock and distant cells", () => {
  const world = makeWorld();
  const player = playerApi.createPlayer(10.5, 16);
  const result = interaction.mineBlock(world, player, 14, 13, config.reach);
  assert.equal(result.ok, true);
  assert.equal(worldApi.getBlock(world, 14, 13), config.blocks.air);
  assert.equal(interaction.mineBlock(world, player, 14, 13, config.reach).reason, "empty");

  worldApi.setBlock(world, 12, 13, config.blocks.bedrock);
  assert.equal(interaction.mineBlock(world, player, 12, 13, config.reach).reason, "bedrock");

  worldApi.setBlock(world, 35, 5, config.blocks.stone);
  assert.equal(interaction.mineBlock(world, player, 35, 5, config.reach).reason, "reach");
});

test("placement is limited to supported, empty, reachable cells outside the player", () => {
  const world = makeWorld();
  const player = playerApi.createPlayer(10.5, 16);
  assert.equal(interaction.canPlaceBlock(world, player, 11, 15, config.reach).ok, true);
  assert.equal(interaction.canPlaceBlock(world, player, 10, 15, config.reach).reason, "player");
  assert.equal(interaction.canPlaceBlock(world, player, 10, 16, config.reach).reason, "occupied");
  assert.equal(interaction.canPlaceBlock(world, player, 11, 12, config.reach).reason, "unsupported");
  assert.equal(interaction.canPlaceBlock(world, player, 35, 5, config.reach).ok, false);
});

test("placing a block changes the world and is rejected inside the player", () => {
  const world = makeWorld();
  const player = playerApi.createPlayer(10.5, 16);
  const placed = interaction.placeBlock(world, player, 11, 15, config.blocks.planks, config.reach);
  assert.equal(placed.ok, true);
  assert.equal(worldApi.getBlock(world, 11, 15), config.blocks.planks);
  const blocked = interaction.placeBlock(world, player, 10, 15, config.blocks.stone, config.reach);
  assert.equal(blocked.ok, false);
  assert.equal(blocked.reason, "player");
  assert.equal(worldApi.getBlock(world, 10, 15), config.blocks.air);
});

test("clicking a solid face selects an adjacent empty cell", () => {
  const world = makeWorld();
  const player = playerApi.createPlayer(10.5, 16);
  const placement = interaction.findPlacementCell(world, player, 12, 16, 0.5, 0.95, config.reach);
  assert.equal(placement.ok, true);
  assert.equal(placement.y, 15);
});

test("distance and player intersection helpers behave at cell boundaries", () => {
  const player = playerApi.createPlayer(10.5, 16);
  assert.equal(interaction.distanceFromPlayer(player, 10, 15) > 0, true);
  assert.equal(interaction.intersectsPlayer(player, 10, 15), true);
  assert.equal(interaction.intersectsPlayer(player, 11, 15), false);
});
