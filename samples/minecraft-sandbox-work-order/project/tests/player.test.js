const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const playerApi = require("../js/player.js");

function flatWorld() {
  const world = worldApi.createWorld(config.seed);
  world.data.fill(config.blocks.air);
  for (let x = 0; x < world.width; x += 1) {
    worldApi.setBlock(world, x, 10, config.blocks.stone);
  }
  return world;
}

test("gravity lands the player on a solid floor", () => {
  const world = flatWorld();
  const player = playerApi.createPlayer(5, 5);

  for (let frame = 0; frame < 240; frame += 1) {
    playerApi.stepPlayer(player, world, {}, 1);
  }

  assert.ok(Math.abs(player.y - 10) < 0.01, `expected feet near 10, saw ${player.y}`);
  assert.equal(player.onGround, true);
  assert.equal(player.vy, 0);
});

test("horizontal collision stops the player at a solid wall", () => {
  const world = flatWorld();
  for (let y = 5; y < 10; y += 1) {
    worldApi.setBlock(world, 8, y, config.blocks.stone);
  }
  const player = playerApi.createPlayer(5, 10);

  for (let frame = 0; frame < 600; frame += 1) {
    playerApi.stepPlayer(player, world, { right: true }, 1);
  }

  const rightEdge = player.x + player.width / 2;
  assert.ok(rightEdge <= 8 + 1e-3, `right edge ${rightEdge} crossed the wall`);
  assert.ok(player.x < 8);
});

test("jumping leaves the ground and lands again", () => {
  const world = flatWorld();
  const player = playerApi.createPlayer(5, 10);

  for (let frame = 0; frame < 5; frame += 1) {
    playerApi.stepPlayer(player, world, {}, 1);
  }
  assert.equal(player.onGround, true);

  playerApi.stepPlayer(player, world, { jump: true }, 1);
  assert.ok(player.vy < 0, "jump should produce upward velocity");

  let highest = player.y;
  for (let frame = 0; frame < 180; frame += 1) {
    playerApi.stepPlayer(player, world, {}, 1);
    highest = Math.min(highest, player.y);
  }

  assert.ok(highest < 10 - 2, `expected a visible jump, highest feet ${highest}`);
  assert.ok(Math.abs(player.y - 10) < 0.01);
  assert.equal(player.onGround, true);
});

test("a large time delta still resolves floor collision without tunnelling", () => {
  const world = flatWorld();
  const player = playerApi.createPlayer(5, -4);

  for (let frame = 0; frame < 30; frame += 1) {
    playerApi.stepPlayer(player, world, {}, 3);
  }

  assert.ok(Math.abs(player.y - 10) < 0.01, `expected landing, saw ${player.y}`);
  assert.equal(player.onGround, true);
});
