const test = require("node:test");
const assert = require("node:assert/strict");
const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const playerApi = require("../js/player.js");

function fresh() {
  const world = worldApi.createWorld(config.seed);
  const player = playerApi.createPlayer(world.spawn.x, world.spawn.y);
  return { world, player };
}

test("a spawned player stands on the surface without overlapping solids", () => {
  const { world, player } = fresh();
  assert.equal(playerApi.overlapsSolid(world, player.x, player.y, player.width, player.height), false);
  for (let i = 0; i < 30; i += 1) {
    playerApi.stepPlayer(player, world, { right: false, left: false, jump: false }, 1 / 60);
  }
  assert.equal(player.onGround, true);
});

test("walking and jumping change position and return to the ground", () => {
  const { world, player } = fresh();
  const startX = player.x;
  for (let i = 0; i < 40; i += 1) {
    playerApi.stepPlayer(player, world, { right: true, jump: false }, 1 / 60);
  }
  assert.ok(player.x > startX);
  for (let i = 0; i < 10; i += 1) {
    playerApi.stepPlayer(player, world, { right: false, jump: true }, 1 / 60);
  }
  for (let i = 0; i < 140; i += 1) {
    playerApi.stepPlayer(player, world, { right: false, jump: false }, 1 / 60);
  }
  assert.equal(player.onGround, true);
  assert.equal(playerApi.overlapsSolid(world, player.x, player.y, player.width, player.height), false);
});

test("trees and stone are mined faster with the right tool", () => {
  const handStone = playerApi.miningSpeedFor(config.blocks.stone, null);
  const pickStone = playerApi.miningSpeedFor(config.blocks.stone, config.itemDefs[config.itemIds.woodenPickaxe]);
  const axeStone = playerApi.miningSpeedFor(config.blocks.stone, config.itemDefs[config.itemIds.woodenAxe]);
  assert.ok(pickStone > handStone);
  assert.equal(axeStone, handStone);
  assert.ok(playerApi.miningSpeedFor(config.blocks.water, null) === 0);
});

test("mining progresses and completes", () => {
  const { player } = fresh();
  const target = { x: 10, y: 62, block: config.blocks.stone };
  let result = { done: false };
  for (let i = 0; i < 240 && !result.done; i += 1) {
    result = playerApi.updateMining(player, target, 1 / 60, config.itemDefs[config.itemIds.woodenPickaxe]);
  }
  assert.equal(result.done, true);
});

test("placement rejects occupied cells, distance and unsupported air", () => {
  const { world, player } = fresh();
  const ground = world.surface[Math.floor(player.x)];
  const occupied = playerApi.validatePlacement(world, player, Math.floor(player.x), ground, config.blocks.dirt);
  assert.equal(occupied.ok, false);
  const far = playerApi.validatePlacement(world, player, 2, 2, config.blocks.dirt);
  assert.equal(far.ok, false);
  const unsupported = playerApi.validatePlacement(world, player, Math.floor(player.x) + 2, ground - 8, config.blocks.dirt);
  assert.equal(unsupported.ok, false);
});

test("damage and respawn restore a playable state", () => {
  const { world, player } = fresh();
  playerApi.damagePlayer(player, 5, "test");
  assert.equal(player.health, 15);
  playerApi.damagePlayer(player, 99, "test");
  assert.equal(player.health, 0);
  assert.equal(player.dead, true);
  playerApi.respawnPlayer(player, { x: world.spawn.x, y: world.spawn.y });
  assert.equal(player.health, 20);
  assert.equal(player.dead, false);
  assert.equal(player.x, world.spawn.x);
});

test("sprinting covers more ground than walking on flat terrain", () => {
  function flatWorld() {
    const data = new Uint8Array(60 * 20);
    for (let x = 0; x < 60; x += 1) {
      data[10 * 60 + x] = config.blocks.stone;
    }
    return { width: 60, height: 20, data, surface: new Int16Array(60).fill(10) };
  }
  const world = flatWorld();
  const walker = playerApi.createPlayer(5.5, 10);
  const runner = playerApi.createPlayer(5.5, 10);
  walker.onGround = true;
  runner.onGround = true;
  for (let i = 0; i < 60; i += 1) {
    playerApi.stepPlayer(walker, world, { right: true, sprint: false }, 1 / 60);
    playerApi.stepPlayer(runner, world, { right: true, sprint: true }, 1 / 60);
  }
  assert.ok(runner.x > walker.x + 1, "sprint should move farther");
});
