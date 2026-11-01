const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const Camera = require("../js/camera.js");
const worldApi = require("../js/world.js");

const view = { width: config.viewWidth, height: config.viewHeight };

test("the camera eases toward the player's centred position", () => {
  const world = worldApi.createWorld(config.seed);
  const camera = Camera.createCamera();
  const player = { x: 64, y: 40 };
  const target = Camera.targetFor(player, world, view);
  for (let index = 0; index < 240; index += 1) {
    Camera.update(camera, player, world, view, 1 / 60);
  }
  assert.ok(Math.abs(camera.x - target.x) < 1, "camera x " + camera.x + " target " + target.x);
  assert.ok(Math.abs(camera.y - target.y) < 1, "camera y " + camera.y + " target " + target.y);
});

test("the camera clamps to the left and top world edges", () => {
  const world = worldApi.createWorld(config.seed);
  const camera = Camera.createCamera();
  const player = { x: 0.5, y: 2 };
  Camera.update(camera, player, world, view, 1 / 60, { reducedMotion: true });
  assert.equal(camera.x, 0);
  assert.equal(camera.y, 0);
});

test("the camera clamps to the right and bottom world edges", () => {
  const world = worldApi.createWorld(config.seed);
  const camera = Camera.createCamera();
  const player = { x: world.width - 0.5, y: world.height - 0.1 };
  Camera.update(camera, player, world, view, 1 / 60, { reducedMotion: true });
  assert.equal(camera.x, world.width * config.tileSize - view.width);
  assert.equal(camera.y, world.height * config.tileSize - view.height);
});

test("reduced motion snaps the camera without easing", () => {
  const world = worldApi.createWorld(config.seed);
  const camera = Camera.createCamera();
  const player = { x: 64, y: 40 };
  const target = Camera.targetFor(player, world, view);
  Camera.update(camera, player, world, view, 1 / 60, { reducedMotion: true });
  assert.equal(camera.x, target.x);
  assert.equal(camera.y, target.y);
});

test("a world smaller than the view keeps the camera at the origin", () => {
  const small = { width: 4, height: 4, seed: 1, data: new Uint8Array(16) };
  const camera = Camera.createCamera();
  Camera.update(camera, { x: 2, y: 2 }, small, view, 1 / 60, { reducedMotion: true });
  assert.equal(camera.x, 0);
  assert.equal(camera.y, 0);
});

test("clampAxis never returns a negative offset", () => {
  assert.equal(Camera.clampAxis(-50, 1000, 500), 0);
  assert.equal(Camera.clampAxis(2000, 1000, 500), 500);
  assert.equal(Camera.clampAxis(200, 1000, 500), 200);
});
