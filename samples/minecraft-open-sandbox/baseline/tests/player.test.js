const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const content = require("../js/content.js");
const playerApi = require("../js/player.js");

function flatWorld() {
  const width = 24;
  const height = 18;
  const data = new Uint8Array(width * height);
  const surface = new Int16Array(width);
  for (let x = 0; x < width; x += 1) {
    surface[x] = 12;
    data[12 * width + x] = config.block.GRASS;
    data[13 * width + x] = config.block.DIRT;
    data[14 * width + x] = config.block.STONE;
    data[15 * width + x] = config.block.STONE;
    data[16 * width + x] = config.block.BEDROCK;
    data[17 * width + x] = config.block.BEDROCK;
  }
  return {
    width,
    height,
    data,
    surface,
    seed: 5,
    spawn: { x: 5.5, y: 12 }
  };
}

const idle = { left: false, right: false, jumpPressed: false, jumpHeld: false, sprint: false };
const tick = 1 / 60;

function settle(player, world, steps) {
  for (let i = 0; i < steps; i += 1) {
    playerApi.updatePlayer(player, world, idle, tick, {});
  }
}

test("the player falls to the ground and remains stable", () => {
  const world = flatWorld();
  const player = playerApi.createPlayer({ x: 5.5, y: 12 });
  settle(player, world, 30);
  assert.equal(player.onGround, true);
  assert.ok(Math.abs(player.y - 12) < 0.01);
  assert.equal(player.health, config.maxHealth);
});

test("horizontal input moves the player and respects walls", () => {
  const world = flatWorld();
  for (let y = 10; y <= 11; y += 1) {
    world.data[y * world.width + 8] = config.block.STONE;
  }
  const player = playerApi.createPlayer({ x: 5.5, y: 12 });
  settle(player, world, 4);
  const startX = player.x;
  for (let i = 0; i < 120; i += 1) {
    playerApi.updatePlayer(player, world, { ...idle, right: true }, tick, {});
  }
  assert.ok(player.x > startX + 0.5);
  assert.ok(player.x + player.width / 2 <= 8.01, "body should stop at the wall");
  assert.equal(playerApi.collidesWorld(world, player.x, player.y, player.width, player.height), false);
});

test("jumping leaves the ground and lands again", () => {
  const world = flatWorld();
  const player = playerApi.createPlayer({ x: 10.5, y: 12 });
  settle(player, world, 4);
  assert.equal(player.onGround, true);
  const groundY = player.y;
  playerApi.updatePlayer(player, world, { ...idle, jumpPressed: true, jumpHeld: true }, tick, {});
  for (let i = 0; i < 20; i += 1) {
    playerApi.updatePlayer(player, world, { ...idle, jumpHeld: true }, tick, {});
  }
  assert.ok(player.y < groundY - 1.2, "jump should reach at least a block");
  settle(player, world, 100);
  assert.equal(player.onGround, true);
  assert.ok(Math.abs(player.y - groundY) < 0.02);
});

test("a deep fall causes damage but not instant death on a normal cliff", () => {
  const world = flatWorld();
  const player = playerApi.createPlayer({ x: 10.5, y: 3 });
  const events = [];
  for (let i = 0; i < 300; i += 1) {
    playerApi.updatePlayer(player, world, idle, tick, {
      onLand: (distance) => events.push(distance)
    });
  }
  assert.equal(player.onGround, true);
  assert.ok(events.length >= 1, "landing hook should fire");
  assert.ok(events[0] > config.player.fallSafe);
  assert.ok(player.health < config.maxHealth);
  assert.ok(player.health > 0);
});

test("falling out of a high place is bounded by world borders", () => {
  const world = flatWorld();
  const player = playerApi.createPlayer({ x: -5, y: 12 });
  playerApi.updatePlayer(player, world, idle, tick, {});
  assert.ok(player.x > 0, "player should not leave the world to the left");
});

test("damage cooldown, healing, and reset behave predictably", () => {
  const world = flatWorld();
  const player = playerApi.createPlayer({ x: 10.5, y: 12 });
  settle(player, world, 4);
  let hurt = 0;
  const first = playerApi.damagePlayer(player, 3, { onHurt: () => { hurt += 1; } });
  const second = playerApi.damagePlayer(player, 3, { onHurt: () => { hurt += 1; } });
  assert.equal(first, true);
  assert.equal(second, false);
  assert.equal(hurt, 1);
  assert.equal(player.health, config.maxHealth - 3);
  playerApi.healPlayer(player, 1);
  assert.equal(player.health, config.maxHealth - 2);
  playerApi.resetPlayer(player, { x: 10.5, y: 12 });
  assert.equal(player.health, config.maxHealth);
  assert.equal(player.dead, false);
});

test("solid content drives collision, and the enemy body helper works", () => {
  const world = flatWorld();
  world.data[8 * world.width + 12] = config.block.LEAVES;
  assert.equal(playerApi.collidesWorld(world, 12.5, 9.6, 0.5, 1.5), true);
  assert.equal(content.getBlockDef(config.block.LEAVES).solid, true);
  for (let y = 10; y <= 11; y += 1) {
    world.data[y * world.width + 14] = config.block.STONE;
  }
  const enemy = { x: 12.5, y: 12, vx: 0, vy: 0, width: 0.68, height: 1.35, onGround: false };
  const moved = playerApi.moveHorizontal(enemy, world, 2);
  assert.equal(moved, false);
  assert.ok(enemy.x < 14 - 0.68 / 2);
  assert.ok(enemy.x > 12.5);
});
