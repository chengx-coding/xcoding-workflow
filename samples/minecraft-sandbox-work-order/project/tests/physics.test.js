const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const playerApi = require("../js/player.js");

function makeWorld(options) {
  const settings = options || {};
  const width = settings.width || 32;
  const height = settings.height || 64;
  const groundRow = settings.groundRow || 45;
  const data = new Uint8Array(width * height);
  for (let x = 0; x < width; x += 1) {
    for (let y = groundRow; y < height; y += 1) {
      data[y * width + x] = y === groundRow ? config.blocks.grass : config.blocks.stone;
    }
  }
  return { width: width, height: height, seed: 1, data: data };
}

function stepFor(player, world, input, frames) {
  for (let index = 0; index < frames; index += 1) {
    playerApi.stepPlayer(player, world, input || {}, 1 / 60);
  }
  return player;
}

test("gravity pulls an airborne player down to the ground", () => {
  const world = makeWorld();
  const player = playerApi.createPlayer(5.5, 10);
  stepFor(player, world, {}, 240);
  assert.ok(player.y <= 45.01, "player did not land: " + player.y);
  assert.ok(player.y >= 44.5, "player fell through the ground: " + player.y);
  assert.equal(player.onGround, true);
});

test("a grounded player stands still without sinking", () => {
  const world = makeWorld();
  const player = playerApi.createPlayer(5.5, 45);
  stepFor(player, world, {}, 60);
  assert.ok(Math.abs(player.y - 45) < 0.05);
  assert.equal(player.onGround, true);
});

test("horizontal input moves the player and records facing", () => {
  const world = makeWorld();
  const player = playerApi.createPlayer(5.5, 45);
  stepFor(player, world, { right: true }, 30);
  assert.ok(player.x > 6.5);
  assert.equal(player.facing, 1);
  stepFor(player, world, { left: true }, 30);
  assert.equal(player.facing, -1);
});

test("jumping leaves the ground and lands again", () => {
  const world = makeWorld();
  const player = playerApi.createPlayer(5.5, 45);
  stepFor(player, world, {}, 5);
  assert.equal(player.onGround, true);
  playerApi.stepPlayer(player, world, { jump: true }, 1 / 60);
  assert.ok(player.vy < 0, "jump did not lift the player");
  const peak = player.y;
  stepFor(player, world, {}, 10);
  assert.ok(player.y < peak, "player did not rise");
  stepFor(player, world, {}, 240);
  assert.equal(player.onGround, true);
  assert.ok(Math.abs(player.y - 45) < 0.05);
});

test("solid walls block horizontal movement", () => {
  const world = makeWorld();
  for (let y = 41; y <= 45; y += 1) {
    world.data[y * world.width + 8] = config.blocks.stone;
  }
  const player = playerApi.createPlayer(5.5, 45);
  stepFor(player, world, { right: true }, 240);
  assert.ok(player.x + player.width / 2 <= 8.001, "player entered the wall at " + player.x);
});

test("solid ceilings stop an upward jump", () => {
  const world = makeWorld();
  for (let x = 0; x < world.width; x += 1) {
    world.data[41 * world.width + x] = config.blocks.stone;
  }
  const player = playerApi.createPlayer(5.5, 45);
  stepFor(player, world, {}, 5);
  player.vy = -config.jumpSpeed;
  stepFor(player, world, { jump: true }, 45);
  assert.ok(player.y - player.height <= 42.001, "player passed through the ceiling: " + (player.y - player.height));
});

test("high fall speed cannot tunnel through the floor", () => {
  const world = makeWorld();
  const player = playerApi.createPlayer(5.5, 2);
  player.vy = 1000;
  stepFor(player, world, {}, 300);
  assert.ok(player.y <= 45.01, "tunneled through the floor to " + player.y);
  assert.equal(player.onGround, true);
});

test("the player is clamped inside the world bounds", () => {
  const world = makeWorld();
  const left = playerApi.createPlayer(-5, 45);
  stepFor(left, world, { left: true }, 10);
  assert.ok(left.x >= left.width / 2 - 0.001);
  const right = playerApi.createPlayer(world.width + 5, 45);
  stepFor(right, world, { right: true }, 10);
  assert.ok(right.x <= world.width - right.width / 2 + 0.001);
});

test("a large frame delta is clamped instead of launching the player", () => {
  const world = makeWorld();
  const player = playerApi.createPlayer(5.5, 20);
  playerApi.stepPlayer(player, world, {}, 5);
  assert.ok(player.y < 21 && player.y > 19, "single huge delta moved too far: " + player.y);
});

test("player boxes expose the expected dimensions", () => {
  const player = playerApi.createPlayer(4, 10);
  const box = playerApi.playerBox(player);
  assert.ok(Math.abs(box.right - box.left - player.width) < 1e-9);
  assert.ok(Math.abs(box.bottom - box.top - player.height) < 1e-9);
  assert.equal(box.bottom, 10);
});

test("a long fall lands on the sealed world floor instead of leaving the world", () => {
  const width = 16;
  const height = 64;
  const data = new Uint8Array(width * height);
  for (let y = height - config.bedrockRows; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      data[y * width + x] = config.blocks.stone;
    }
  }
  const world = { width, height, seed: 1, data };
  const player = playerApi.createPlayer(5.5, 2);
  player.vy = 1000;
  stepFor(player, world, {}, 300);
  assert.ok(player.y <= height - config.bedrockRows + 0.01, "fell through the floor to " + player.y);
  assert.ok(player.y > height - config.bedrockRows - 1, "did not stop on the floor");
  assert.equal(player.onGround, true);
});
