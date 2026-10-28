const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const playerApi = require("../js/player.js");
const renderApi = require("../js/render.js");

test("camera follows the player at the world origin", () => {
  const world = worldApi.createWorld(config.seed);
  const player = playerApi.createPlayer(config.spawnX, 41);
  const camera = renderApi.cameraForPlayer(world, player);

  assert.equal(camera.x, 0);
  assert.ok(Math.abs(camera.y - ((41 - player.height / 2) * config.tileSize - config.viewHeight / 2)) < 1e-6);
});

test("camera centres on the player in the middle of the world", () => {
  const world = worldApi.createWorld(config.seed);
  const player = playerApi.createPlayer(64, 30);
  const camera = renderApi.cameraForPlayer(world, player);

  assert.equal(camera.x, 64 * config.tileSize - config.viewWidth / 2);
  assert.equal(
    camera.y,
    (30 - player.height / 2) * config.tileSize - config.viewHeight / 2
  );
});

test("camera stays inside the world bounds at the far edge", () => {
  const world = worldApi.createWorld(config.seed);
  const player = playerApi.createPlayer(world.width - 1, world.height - 1);
  const camera = renderApi.cameraForPlayer(world, player);

  assert.equal(camera.x, world.width * config.tileSize - config.viewWidth);
  assert.equal(camera.y, world.height * config.tileSize - config.viewHeight);
});

test("all five block colours are defined for rendering", () => {
  assert.equal(Object.keys(renderApi.BLOCK_COLORS).length, 5);
  for (const id of [1, 2, 3, 4, 5]) {
    assert.match(renderApi.BLOCK_COLORS[id], /^#[0-9a-f]{6}$/i);
  }
});
