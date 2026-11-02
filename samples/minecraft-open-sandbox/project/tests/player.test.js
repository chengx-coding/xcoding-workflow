const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const playerApi = require("../js/player.js");

const GROUND = worldApi.GROUND_ROW;
const DT = 1 / 60;

function makePlayer(x, y) {
  return playerApi.createPlayer(x === undefined ? 24.5 : x, y === undefined ? GROUND : y);
}

function settle(world, player, frames) {
  const input = { left: false, right: false, jump: false, jumpPressed: false };
  for (let i = 0; i < (frames || 90); i += 1) {
    playerApi.update(player, world, input, DT);
  }
  return player;
}

test("a fresh player has the configured size and full health", () => {
  const player = makePlayer();
  assert.equal(player.width, config.playerWidth);
  assert.equal(player.height, config.playerHeight);
  assert.equal(player.health, config.maxHealth);
  assert.equal(player.dead, false);
});

test("gravity lands the player on the spawn plateau", () => {
  const world = worldApi.createWorld(config.seed);
  const player = settle(world, makePlayer());
  assert.equal(player.onGround, true);
  assert.ok(Math.abs(player.y - GROUND) < 0.05, `y=${player.y}`);
});

test("walking right collides with a wall", () => {
  const world = worldApi.createWorld(config.seed);
  const player = settle(world, makePlayer());
  worldApi.setBlock(world, 27, GROUND - 1, config.blocks.stone);
  worldApi.setBlock(world, 27, GROUND - 2, config.blocks.stone);
  const input = { left: false, right: true, jump: false, jumpPressed: false };
  for (let i = 0; i < 120; i += 1) {
    playerApi.update(player, world, input, DT);
  }
  assert.ok(player.x < 27 - config.playerWidth / 2 + 0.05, `x=${player.x}`);
  assert.ok(player.x > 24, "the player moved before hitting the wall");
});

test("jump lifts the player and it lands again", () => {
  const world = worldApi.createWorld(config.seed);
  const player = settle(world, makePlayer());
  const startY = player.y;
  const input = { left: false, right: false, jump: true, jumpPressed: true };
  playerApi.update(player, world, input, DT);
  for (let i = 0; i < 12; i += 1) {
    playerApi.update(player, world, input, DT);
  }
  assert.ok(player.y < startY - 0.5, "the player should rise");
  input.jump = false;
  input.jumpPressed = false;
  for (let i = 0; i < 200; i += 1) {
    playerApi.update(player, world, input, DT);
  }
  assert.ok(Math.abs(player.y - startY) < 0.1, `landed at ${player.y}`);
});

test("reach is measured from the player centre", () => {
  const player = makePlayer(10.5, GROUND);
  assert.equal(playerApi.canReach(player, 14, GROUND - 1, config.reach), true);
  assert.equal(playerApi.canReach(player, 24, GROUND - 1, config.reach), false);
  assert.ok(playerApi.distanceToTile(player, 14, GROUND - 1) > 4);
});

test("overlapsTile detects the tile the player stands in", () => {
  const player = makePlayer(10.5, GROUND);
  assert.equal(playerApi.overlapsTile(player, 10, GROUND - 1), true);
  assert.equal(playerApi.overlapsTile(player, 10, GROUND - 3), false);
});

test("damage respects invulnerability and death", () => {
  const player = makePlayer();
  assert.equal(playerApi.damage(player, 3), true);
  assert.equal(player.health, config.maxHealth - 3);
  assert.equal(playerApi.damage(player, 3), false, "invulnerability window");
  player.invuln = 0;
  assert.equal(playerApi.damage(player, config.maxHealth), true);
  assert.equal(player.dead, true);
  player.dead = true;
  assert.equal(playerApi.damage(player, 1), false);
});

test("respawn restores health at the spawn point", () => {
  const player = makePlayer();
  player.health = 1;
  player.dead = true;
  playerApi.respawn(player, { x: 24.5, y: GROUND });
  assert.equal(player.dead, false);
  assert.equal(player.health, config.maxHealth);
  assert.equal(player.x, 24.5);
  assert.equal(player.y, GROUND);
});

test("saved player state restores position and health", () => {
  const player = makePlayer();
  player.x = 42.5;
  player.y = GROUND - 2;
  player.health = 7;
  const saved = playerApi.serialize(player);
  const restored = playerApi.applySaved(makePlayer(), saved);
  assert.equal(restored.x, 42.5);
  assert.equal(restored.y, GROUND - 2);
  assert.equal(restored.health, 7);
});
