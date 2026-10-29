const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const cameraApi = require("../js/camera.js");

function makeWorld() {
  return { width: 100, height: 50 };
}

function makePlayer() {
  return { x: 50, y: 25, height: 1.8 };
}

test("camera follows the player when snap is requested", () => {
  const camera = cameraApi.createCamera();
  const world = makeWorld();
  const player = makePlayer();
  cameraApi.updateCamera(camera, world, player, 0, true);
  const expectedX = player.x * config.tileSize - config.viewWidth / 2;
  const expectedY = (player.y - player.height / 2) * config.tileSize - config.viewHeight / 2;
  assert.equal(camera.x, expectedX);
  assert.equal(camera.y, expectedY);
});

test("camera clamps to the world bounds at every edge", () => {
  const camera = cameraApi.createCamera();
  const world = makeWorld();
  camera.x = -500;
  camera.y = -500;
  cameraApi.clampCamera(camera, world);
  assert.equal(camera.x, 0);
  assert.equal(camera.y, 0);

  camera.x = 999999;
  camera.y = 999999;
  cameraApi.clampCamera(camera, world);
  assert.equal(camera.x, world.width * config.tileSize - config.viewWidth);
  assert.equal(camera.y, world.height * config.tileSize - config.viewHeight);
});

test("camera smoothing approaches the player without overshoot", () => {
  const camera = cameraApi.createCamera();
  const world = makeWorld();
  const player = makePlayer();
  cameraApi.updateCamera(camera, world, player, 1 / 60, true);
  const startX = camera.x;
  player.x += 6;
  cameraApi.updateCamera(camera, world, player, 1 / 60, false);
  assert.ok(camera.x > startX);
  const targetX = player.x * config.tileSize - config.viewWidth / 2;
  assert.ok(camera.x <= targetX);
});

test("screen and world coordinates round-trip", () => {
  const camera = cameraApi.createCamera();
  camera.x = 320;
  camera.y = 160;
  const point = cameraApi.screenToWorld(camera, 640, 360);
  const back = cameraApi.worldToScreen(camera, point.x, point.y);
  assert.ok(Math.abs(back.x - 640) < 0.0001);
  assert.ok(Math.abs(back.y - 360) < 0.0001);
});

test("visible tile bounds stay inside the world", () => {
  const camera = cameraApi.createCamera();
  const world = makeWorld();
  const bounds = cameraApi.visibleTileBounds(camera, world);
  assert.ok(bounds.firstX >= 0);
  assert.ok(bounds.firstY >= 0);
  assert.ok(bounds.lastX < world.width);
  assert.ok(bounds.lastY < world.height);
});

test("shake decays back to rest", () => {
  const camera = cameraApi.createCamera();
  cameraApi.addShake(camera, 4, 0.1);
  cameraApi.updateShake(camera, 0.02);
  assert.ok(camera.shakeTime > 0);
  cameraApi.updateShake(camera, 0.2);
  assert.equal(camera.shakeTime, 0);
  assert.ok(Math.abs(camera.shakeX) < 0.000001);
  assert.ok(Math.abs(camera.shakeY) < 0.000001);
});
