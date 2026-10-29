const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const playerApi = require("../js/player.js");

function flatArena(seed) {
  const world = worldApi.createWorld(seed || config.seed);
  const base = worldApi.surfaceHeightAt(world, 64);
  for (let x = 56; x <= 74; x += 1) {
    for (let y = base - 8; y < base; y += 1) {
      worldApi.setBlock(world, x, y, config.blocks.air);
    }
    for (let y = base + 1; y <= base + 12; y += 1) {
      worldApi.setBlock(world, x, y, config.blocks.air);
    }
    worldApi.setBlock(world, x, base, config.blocks.stone);
  }
  return { world: world, base: base };
}

test("gravity settles the player on the surface", () => {
  const arena = flatArena();
  const player = playerApi.createPlayer(64.5, arena.base - 5);
  for (let step = 0; step < 180; step += 1) {
    playerApi.stepPlayer(player, arena.world, {}, 1 / 60);
  }
  assert.equal(player.onGround, true);
  assert.ok(Math.abs(player.y - arena.base) < 0.02, "feet should rest on the floor");
  assert.equal(player.vy, 0);
});

test("horizontal movement is stopped by a solid wall", () => {
  const arena = flatArena();
  for (let y = arena.base - 5; y < arena.base; y += 1) {
    worldApi.setBlock(arena.world, 68, y, config.blocks.stone);
  }
  const player = playerApi.createPlayer(62.5, arena.base);
  for (let step = 0; step < 240; step += 1) {
    playerApi.stepPlayer(player, arena.world, { right: true }, 1 / 60);
  }
  assert.ok(player.x + player.width / 2 <= 68.001, "the player must not pass through the wall");
  assert.ok(player.x + player.width / 2 > 67.8, "the player should reach the wall");
  assert.equal(player.onGround, true);
});

test("a rising edge on jump launches the player", () => {
  const arena = flatArena();
  const player = playerApi.createPlayer(64.5, arena.base);
  player.onGround = true;
  const events = playerApi.stepPlayer(player, arena.world, { jump: true }, 1 / 60);
  assert.equal(events.jumped, true);
  assert.ok(player.vy < 0);
});

test("holding jump clears more than one block and lands again", () => {
  const arena = flatArena();
  const player = playerApi.createPlayer(64.5, arena.base);
  player.onGround = true;
  let highest = arena.base;
  for (let step = 0; step < 90; step += 1) {
    playerApi.stepPlayer(player, arena.world, { jump: true }, 1 / 60);
    highest = Math.min(highest, player.y);
  }
  for (let step = 0; step < 120; step += 1) {
    playerApi.stepPlayer(player, arena.world, { jump: false }, 1 / 60);
    highest = Math.min(highest, player.y);
  }
  assert.ok(arena.base - highest > 1.8, "a held jump should clear at least 1.8 tiles");
  assert.equal(player.onGround, true);
});

test("a ceiling stops an upward jump", () => {
  const arena = flatArena();
  for (let x = 56; x <= 74; x += 1) {
    worldApi.setBlock(arena.world, x, arena.base - 4, config.blocks.stone);
    worldApi.setBlock(arena.world, x, arena.base - 3, config.blocks.stone);
  }
  const player = playerApi.createPlayer(64.5, arena.base);
  player.onGround = true;
  for (let step = 0; step < 120; step += 1) {
    playerApi.stepPlayer(player, arena.world, { jump: true }, 1 / 60);
    assert.ok(player.y - player.height >= arena.base - 3 - 0.01, "the head must not enter the ceiling");
  }
});

test("player serialization round-trips a position and facing", () => {
  const player = playerApi.createPlayer(91.25, 37.5);
  player.facing = -1;
  player.vx = 2.5;
  const restored = playerApi.restorePlayer(playerApi.serializePlayer(player), 0, 0);
  assert.equal(restored.x, 91.25);
  assert.equal(restored.y, 37.5);
  assert.equal(restored.facing, -1);
  assert.equal(restored.vx, 2.5);
});

test("restorePlayer falls back for invalid data", () => {
  const restored = playerApi.restorePlayer({ x: "nope", y: null }, 12, 34);
  assert.equal(restored.x, 12);
  assert.equal(restored.y, 34);
});
