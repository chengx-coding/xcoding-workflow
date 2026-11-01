const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const playerApi = require("../js/player.js");

function flatWorld(width, height, floor) {
  const data = new Uint8Array(width * height);
  for (let x = 0; x < width; x += 1) {
    for (let y = floor; y < height; y += 1) {
      data[y * width + x] = config.blocks.stone;
    }
  }
  return { width: width, height: height, seed: 1, data: data };
}

function stepFor(player, world, input, seconds) {
  const dt = 1 / 60;
  const steps = Math.round(seconds / dt);
  let events = [];
  for (let i = 0; i < steps; i += 1) {
    const frameInput = Object.assign({}, input);
    if (i > 0) {
      frameInput.jumpPressed = false;
    }
    events = events.concat(playerApi.stepPlayer(player, world, frameInput, dt));
  }
  return events;
}

test("a player falls and lands on the floor", () => {
  const world = flatWorld(32, 32, 20);
  const player = playerApi.createPlayer(5.5, 10);
  stepFor(player, world, {}, 1.5);
  assert.equal(player.onGround, true);
  assert.ok(Math.abs(player.y - 20) < 0.05, "expected feet at y=20, got " + player.y);
  assert.equal(player.vy, 0);
});

test("horizontal input moves the player and walls stop them", () => {
  const world = flatWorld(40, 32, 20);
  for (let y = 10; y < 20; y += 1) {
    worldApi.setBlock(world, 24, y, config.blocks.stone);
  }
  const player = playerApi.createPlayer(5.5, 20);
  stepFor(player, world, { right: true }, 1.2);
  assert.ok(player.x > 8, "expected movement, got " + player.x);
  stepFor(player, world, { right: true }, 1.5);
  assert.ok(player.x < 23.7, "expected the wall to stop the player, got " + player.x);
  assert.equal(playerApi.overlapsSolid(world, player.x, player.y, player.width, player.height), false);
});

test("jumping leaves the ground and lands again", () => {
  const world = flatWorld(32, 32, 20);
  const player = playerApi.createPlayer(6.5, 20);
  stepFor(player, world, {}, 0.2);
  assert.equal(player.onGround, true);
  const startY = player.y;
  const events = playerApi.stepPlayer(player, world, { jump: true, jumpPressed: true }, 1 / 60);
  assert.ok(events.some((event) => event.type === "jump"), "expected a jump event");
  stepFor(player, world, { jump: true }, 0.2);
  assert.ok(player.y < startY - 0.8, "expected to rise, got " + player.y);
  stepFor(player, world, {}, 1.2);
  assert.equal(player.onGround, true);
  assert.ok(Math.abs(player.y - 20) < 0.05);
});

test("coyote time allows a jump just after leaving a ledge", () => {
  const world = flatWorld(32, 32, 20);
  for (let x = 12; x < 32; x += 1) {
    for (let y = 20; y < 32; y += 1) {
      worldApi.setBlock(world, x, y, config.blocks.air);
    }
  }
  const player = playerApi.createPlayer(10.5, 20);
  stepFor(player, world, { right: true }, 0.25);
  const before = player.y;
  playerApi.stepPlayer(player, world, { right: true, jumpPressed: true, jump: true }, 1 / 60);
  stepFor(player, world, { right: true }, 0.15);
  assert.ok(player.y < before, "expected the coyote jump to lift the player");
});

test("water reduces gravity and allows swimming upward", () => {
  const world = flatWorld(32, 32, 28);
  for (let x = 0; x < 32; x += 1) {
    for (let y = 20; y < 28; y += 1) {
      worldApi.setBlock(world, x, y, config.blocks.water);
    }
  }
  const player = playerApi.createPlayer(5.5, 26);
  stepFor(player, world, {}, 0.5);
  assert.equal(player.inWater, true);
  const startY = player.y;
  stepFor(player, world, { jump: true, jumpPressed: true }, 0.5);
  assert.ok(player.y < startY, "expected swimming upward");
  assert.ok(player.vy <= 3.3);
});

test("respawn returns the player to the world spawn", () => {
  const world = worldApi.createWorld(config.seed);
  const player = playerApi.createPlayer(4, 4);
  playerApi.respawn(world, player);
  const spawn = worldApi.getSpawn(world);
  assert.equal(player.x, spawn.x + 0.5);
  assert.equal(player.y, spawn.y);
  assert.equal(player.vx, 0);
  assert.equal(player.vy, 0);
});
