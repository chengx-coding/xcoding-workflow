const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const playerApi = require("../js/player.js");

function makeFlatWorld(options) {
  const settings = options || {};
  const width = settings.width || 48;
  const height = settings.height || 24;
  const surface = settings.surface || 15;
  const data = new Uint8Array(width * height);
  const ground = new Int16Array(width);
  const biomes = new Uint8Array(width);
  for (let x = 0; x < width; x += 1) {
    ground[x] = surface;
    for (let y = surface; y < height; y += 1) {
      data[y * width + x] = y === surface ? config.blocks.grass : config.blocks.stone;
    }
  }
  if (settings.wallX != null) {
    for (let y = surface - 5; y <= surface; y += 1) {
      data[y * width + settings.wallX] = config.blocks.stone;
    }
  }
  return { width: width, height: height, seed: 1, data: data, ground: ground, biomes: biomes };
}

test("gravity settles the player on solid ground", () => {
  const world = makeFlatWorld();
  const player = playerApi.createPlayer(10.5, 6);
  for (let step = 0; step < 240; step += 1) {
    playerApi.stepPlayer(player, world, {}, 1 / 120);
  }
  assert.ok(Math.abs(player.y - 15) < 0.05);
  assert.equal(player.onGround, true);
  assert.equal(player.vy, 0);
});

test("horizontal movement changes position without crossing a wall", () => {
  const world = makeFlatWorld({ wallX: 20 });
  const player = playerApi.createPlayer(8.5, 15);
  player.onGround = true;
  for (let step = 0; step < 200; step += 1) {
    playerApi.stepPlayer(player, world, { right: true }, 1 / 120);
  }
  assert.ok(player.x > 8.5 + config.moveSpeed * 0.5);
  assert.ok(player.x + player.width / 2 <= 20.01, "player should stop at the wall");
  assert.ok(player.x < 20);
});

test("jump launches upward and the player lands again", () => {
  const world = makeFlatWorld();
  const player = playerApi.createPlayer(10.5, 15);
  player.onGround = true;
  playerApi.stepPlayer(player, world, { jumpPressed: true, jumpHeld: true }, 1 / 120);
  assert.ok(player.vy < 0);
  assert.equal(player.onGround, false);
  const startY = player.y;
  for (let step = 0; step < 12; step += 1) {
    playerApi.stepPlayer(player, world, { jumpHeld: true }, 1 / 120);
  }
  assert.ok(player.y < startY - 1, "player should rise above the starting height");
  for (let step = 0; step < 360; step += 1) {
    playerApi.stepPlayer(player, world, {}, 1 / 120);
  }
  assert.ok(player.y <= 15.05);
  assert.equal(player.onGround, true);
});

test("a fast fall cannot tunnel through the floor", () => {
  const world = makeFlatWorld();
  const player = playerApi.createPlayer(10.5, 2);
  player.vy = 80;
  for (let step = 0; step < 180; step += 1) {
    playerApi.stepPlayer(player, world, {}, 0.05);
  }
  assert.ok(player.y <= 15.05, "player must not pass through terrain");
  assert.equal(player.onGround, true);
});

test("collision detects solid cells and ignores air", () => {
  const world = makeFlatWorld();
  assert.equal(playerApi.overlapsSolid(world, 10.5, 14, 0.68, 1.8), false);
  assert.equal(playerApi.overlapsSolid(world, 10.5, 15, 0.68, 1.8), false);
  assert.equal(playerApi.overlapsSolid(world, 10.5, 16, 0.68, 1.8), true);
});

test("teleportToSpawn resets momentum and remembers the point", () => {
  const world = makeFlatWorld();
  const player = playerApi.createPlayer(2, 2);
  player.vx = 8;
  player.vy = 9;
  playerApi.teleportToSpawn(player, world, { x: 20.5, y: 15 });
  assert.equal(player.x, 20.5);
  assert.equal(player.y, 15);
  assert.equal(player.vx, 0);
  assert.equal(player.vy, 0);
  assert.equal(player.spawnX, 20.5);
  assert.equal(player.spawnY, 15);
});

test("players cannot walk through the world edge", () => {
  const world = makeFlatWorld();
  const player = playerApi.createPlayer(1.5, 15);
  player.onGround = true;
  for (let step = 0; step < 240; step += 1) {
    playerApi.stepPlayer(player, world, { left: true }, 1 / 120);
  }
  assert.ok(player.x >= 0);
});
