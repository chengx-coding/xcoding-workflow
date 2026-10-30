const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const playerApi = require("../js/player.js");

function flatWorld(options) {
  const settings = options || {};
  const width = settings.width || 40;
  const height = settings.height || 40;
  const ground = settings.ground || 20;
  const data = new Uint8Array(width * height);
  for (let x = 0; x < width; x += 1) {
    for (let y = ground; y < height; y += 1) {
      data[y * width + x] = settings.block || config.blocks.stone;
    }
  }
  (settings.blocks || []).forEach((block) => {
    data[block.y * width + block.x] = block.block || config.blocks.stone;
  });
  return { width, height, seed: 1, data };
}

function settle(player, world, frames) {
  for (let index = 0; index < (frames || 180); index += 1) {
    playerApi.stepPlayer(player, world, { left: false, right: false, jump: false }, 1 / 60);
  }
  return player;
}

test("createPlayer starts with the seed dimensions and no ground contact", () => {
  const player = playerApi.createPlayer(5, 8);
  assert.equal(player.x, 5);
  assert.equal(player.y, 8);
  assert.equal(player.onGround, false);
  assert.equal(player.width, 0.7);
  assert.equal(player.height, 1.8);
});

test("gravity accelerates a falling player", () => {
  const player = playerApi.createPlayer(5, 2);
  const world = flatWorld();
  const before = player.y;
  playerApi.stepPlayer(player, world, {}, 0.1);
  assert.ok(player.vy > 0);
  assert.ok(player.y > before);
});

test("a falling player lands on solid ground", () => {
  const player = playerApi.createPlayer(5, 8);
  const world = flatWorld({ ground: 20 });
  settle(player, world);
  assert.ok(player.onGround);
  assert.ok(Math.abs(player.y - 20) < 0.01, "settled at " + player.y);
});

test("a fast fall does not tunnel through the floor", () => {
  const player = playerApi.createPlayer(5, 2);
  const world = flatWorld({ ground: 10 });
  for (let index = 0; index < 40; index += 1) {
    playerApi.stepPlayer(player, world, {}, 0.1);
  }
  assert.ok(player.y >= 10 - 0.001);
  assert.ok(player.onGround);
});

test("horizontal input moves the player in the requested direction", () => {
  const world = flatWorld();
  const player = playerApi.createPlayer(5, 20);
  settle(player, world, 30);
  const start = player.x;
  for (let index = 0; index < 60; index += 1) {
    playerApi.stepPlayer(player, world, { right: true }, 1 / 60);
  }
  assert.ok(player.x > start);
  assert.equal(player.facing, 1);
  for (let index = 0; index < 30; index += 1) {
    playerApi.stepPlayer(player, world, { left: true }, 1 / 60);
  }
  assert.equal(player.facing, -1);
});

test("a wall stops horizontal movement", () => {
  const world = flatWorld({ blocks: [{ x: 10, y: 18 }, { x: 10, y: 19 }] });
  const player = playerApi.createPlayer(5, 20);
  settle(player, world, 30);
  for (let index = 0; index < 180; index += 1) {
    playerApi.stepPlayer(player, world, { right: true }, 1 / 60);
  }
  assert.ok(player.x <= 10 - player.width / 2, "stopped at " + player.x);
  assert.ok(player.x > 9);
});

test("jumping only lifts a grounded player", () => {
  const world = flatWorld();
  const player = playerApi.createPlayer(5, 20);
  settle(player, world, 30);
  assert.ok(player.onGround);
  playerApi.stepPlayer(player, world, { jump: true }, 1 / 60);
  assert.ok(player.vy < 0);
  assert.equal(player.onGround, false);
});

test("a player in mid-air cannot jump again", () => {
  const world = flatWorld();
  const player = playerApi.createPlayer(5, 20);
  settle(player, world, 30);
  playerApi.stepPlayer(player, world, { jump: true }, 1 / 60);
  const afterJump = player.vy;
  for (let index = 0; index < 5; index += 1) {
    playerApi.stepPlayer(player, world, {}, 1 / 60);
  }
  const beforeSecond = player.vy;
  playerApi.stepPlayer(player, world, { jump: true }, 1 / 60);
  assert.ok(player.vy > beforeSecond, "gravity should continue; no second impulse");
  assert.ok(afterJump < 0);
});

test("a ceiling stops upward movement", () => {
  const world = flatWorld({ blocks: [{ x: 5, y: 16 }] });
  const player = playerApi.createPlayer(5.5, 20);
  settle(player, world, 30);
  let highest = player.y;
  for (let index = 0; index < 120; index += 1) {
    playerApi.stepPlayer(player, world, { jump: index < 10 }, 1 / 60);
    highest = Math.min(highest, player.y);
  }
  assert.ok(highest >= 17 + player.height - 0.01, "head stayed below the ceiling at " + highest);
  assert.ok(highest < 20);
});

test("the player stays inside the world bounds", () => {
  const world = flatWorld({ width: 20, ground: 20 });
  const player = playerApi.createPlayer(1, 20);
  for (let index = 0; index < 240; index += 1) {
    playerApi.stepPlayer(player, world, { left: true }, 1 / 60);
  }
  assert.ok(player.x >= player.width / 2);
  player.x = 18;
  for (let index = 0; index < 240; index += 1) {
    playerApi.stepPlayer(player, world, { right: true }, 1 / 60);
  }
  assert.ok(player.x <= world.width - player.width / 2);
});

test("isSupported detects the ground beneath the player", () => {
  const world = flatWorld();
  const grounded = playerApi.createPlayer(5, 20);
  assert.equal(playerApi.isSupported(grounded, world), true);
  const airborne = playerApi.createPlayer(5, 5);
  assert.equal(playerApi.isSupported(airborne, world), false);
});

test("overlapsCell reports the cells covered by the player box", () => {
  const player = playerApi.createPlayer(5.5, 20);
  assert.equal(playerApi.overlapsCell(player, 5, 19), true);
  assert.equal(playerApi.overlapsCell(player, 5, 17), false);
  assert.equal(playerApi.overlapsCell(player, 7, 19), false);
});

test("a zero-length step leaves the player untouched", () => {
  const world = flatWorld();
  const player = playerApi.createPlayer(5, 20);
  const snapshot = JSON.stringify(player);
  playerApi.stepPlayer(player, world, { right: true }, 0);
  assert.equal(JSON.stringify(player), snapshot);
});
