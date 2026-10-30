const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const cameraApi = require("../js/camera.js");
const playerApi = require("../js/player.js");

const view = { width: config.viewWidth, height: config.viewHeight };
const tile = config.tileSize;

function world() {
  return { width: config.worldWidth, height: config.worldHeight, seed: 1, data: new Uint8Array(config.worldWidth * config.worldHeight) };
}

test("targetCamera centres the player when the world is larger than the view", () => {
  const gameWorld = world();
  const player = playerApi.createPlayer(64, 32);
  const target = cameraApi.targetCamera(player, gameWorld, view, tile);
  const playerCentreX = player.x * tile;
  assert.ok(Math.abs(target.x + view.width / 2 - playerCentreX) < 0.001);
});

test("targetCamera clamps to the left and top edges", () => {
  const target = cameraApi.targetCamera(playerApi.createPlayer(1, 5), world(), view, tile);
  assert.equal(target.x, 0);
  assert.equal(target.y, 0);
});

test("targetCamera clamps to the right and bottom edges", () => {
  const gameWorld = world();
  const target = cameraApi.targetCamera(playerApi.createPlayer(gameWorld.width - 1, gameWorld.height), gameWorld, view, tile);
  assert.equal(target.x, gameWorld.width * tile - view.width);
  assert.equal(target.y, gameWorld.height * tile - view.height);
});

test("followCamera approaches its target smoothly", () => {
  const gameWorld = world();
  const player = playerApi.createPlayer(60, 30);
  const camera = cameraApi.createCamera();
  const target = cameraApi.targetCamera(player, gameWorld, view, tile);
  cameraApi.followCamera(camera, player, gameWorld, view, tile, 1 / 60, 9);
  assert.ok(camera.x > 0 && camera.x < target.x);
  for (let index = 0; index < 240; index += 1) {
    cameraApi.followCamera(camera, player, gameWorld, view, tile, 1 / 60, 9);
  }
  assert.ok(Math.abs(camera.x - target.x) < 0.5);
  assert.ok(Math.abs(camera.y - target.y) < 0.5);
});

test("followCamera never leaves the world bounds", () => {
  const gameWorld = world();
  const player = playerApi.createPlayer(0.5, 1);
  const camera = cameraApi.createCamera();
  camera.x = 5000;
  camera.y = 5000;
  cameraApi.followCamera(camera, player, gameWorld, view, tile, 0.1, 9);
  assert.ok(camera.x >= 0 && camera.x <= gameWorld.width * tile - view.width);
  assert.ok(camera.y >= 0 && camera.y <= gameWorld.height * tile - view.height);
});

test("visibleRange covers the viewport and stays inside the world", () => {
  const gameWorld = world();
  const camera = { x: 300, y: 200 };
  const range = cameraApi.visibleRange(camera, gameWorld, view, tile);
  assert.ok(range.firstX <= Math.floor(camera.x / tile));
  assert.ok(range.lastX * tile >= camera.x + view.width - tile);
  assert.ok(range.firstY <= Math.floor(camera.y / tile));
  assert.ok(range.lastY * tile >= camera.y + view.height - tile);
  assert.ok(range.lastX < gameWorld.width);
  assert.ok(range.lastY < gameWorld.height);
});

test("maxCamera returns zero for a world smaller than the view", () => {
  const tiny = { width: 10, height: 10, seed: 1, data: new Uint8Array(100) };
  const bounds = cameraApi.maxCamera(tiny, view, tile);
  assert.equal(bounds.x, 0);
  assert.equal(bounds.y, 0);
});

test("followCamera ignores a paused timestamp without moving wildly", () => {
  const gameWorld = world();
  const player = playerApi.createPlayer(64, 32);
  const camera = cameraApi.createCamera();
  cameraApi.followCamera(camera, player, gameWorld, view, tile, 0, 9);
  assert.equal(camera.x, 0);
});
