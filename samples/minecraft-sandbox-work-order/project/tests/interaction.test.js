const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const playerApi = require("../js/player.js");

function flatArena() {
  const world = worldApi.createWorld(config.seed);
  const base = worldApi.surfaceHeightAt(world, 64);
  for (let x = 56; x <= 80; x += 1) {
    for (let y = base - 10; y < base; y += 1) {
      worldApi.setBlock(world, x, y, config.blocks.air);
    }
    for (let y = base + 1; y <= base + 12; y += 1) {
      worldApi.setBlock(world, x, y, config.blocks.air);
    }
    worldApi.setBlock(world, x, base, config.blocks.stone);
  }
  const player = playerApi.createPlayer(64.5, base);
  player.onGround = true;
  return { world: world, base: base, player: player };
}

test("mining succeeds on a solid block within reach", () => {
  const arena = flatArena();
  const result = worldApi.canMineBlock(arena.world, arena.player, 66, arena.base, config.reach);
  assert.equal(result.ok, true);
  assert.equal(worldApi.getBlock(arena.world, 66, arena.base), config.blocks.stone);
});

test("mining rejects empty cells, out-of-bounds cells and distant blocks", () => {
  const arena = flatArena();
  assert.equal(worldApi.canMineBlock(arena.world, arena.player, 64, arena.base - 3, config.reach).reason, "empty");
  assert.equal(worldApi.canMineBlock(arena.world, arena.player, -1, arena.base, config.reach).reason, "bounds");
  assert.equal(worldApi.canMineBlock(arena.world, arena.player, 78, arena.base, config.reach).reason, "reach");
});

test("placing succeeds in a clear, supported, non-player cell", () => {
  const arena = flatArena();
  const result = worldApi.canPlaceBlock(arena.world, arena.player, 66, arena.base - 1, config.reach);
  assert.equal(result.ok, true);
  worldApi.setBlock(arena.world, 66, arena.base - 1, config.blocks.planks);
  assert.equal(worldApi.getBlock(arena.world, 66, arena.base - 1), config.blocks.planks);
});

test("placing is refused inside the player", () => {
  const arena = flatArena();
  const result = worldApi.canPlaceBlock(arena.world, arena.player, 64, arena.base - 1, config.reach);
  assert.equal(result.ok, false);
  assert.equal(result.reason, "player");
});

test("placing is refused on occupied, unsupported and out-of-reach cells", () => {
  const arena = flatArena();
  assert.equal(worldApi.canPlaceBlock(arena.world, arena.player, 64, arena.base, config.reach).reason, "occupied");
  assert.equal(worldApi.canPlaceBlock(arena.world, arena.player, 64, arena.base - 4, config.reach).reason, "unsupported");
  assert.equal(worldApi.canPlaceBlock(arena.world, arena.player, 78, arena.base - 1, config.reach).reason, "reach");
});

test("solid-neighbour detection works on all four sides", () => {
  const arena = flatArena();
  worldApi.setBlock(arena.world, 60, arena.base - 3, config.blocks.stone);
  assert.equal(worldApi.hasSolidNeighbour(arena.world, 60, arena.base - 2), true);
  assert.equal(worldApi.hasSolidNeighbour(arena.world, 60, arena.base - 5), false);
});

test("reach uses the distance from the player centre to the cell centre", () => {
  const arena = flatArena();
  assert.equal(worldApi.cellWithinReach(arena.world, arena.player, 64, arena.base - 1, 5), true);
  assert.equal(worldApi.cellWithinReach(arena.world, arena.player, 64, arena.base - 9, 5), false);
});
