(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxCamera = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  function createCamera() {
    return { x: 0, y: 0 };
  }

  function clampAxis(value, worldPixels, viewPixels) {
    const max = Math.max(0, worldPixels - viewPixels);
    return Math.min(Math.max(value, 0), max);
  }

  function targetFor(player, world, view, tileSize) {
    const tile = tileSize || CONFIG.tileSize;
    return {
      x: clampAxis(player.x * tile - view.width / 2, world.width * tile, view.width),
      y: clampAxis(player.y * tile - view.height / 2, world.height * tile, view.height)
    };
  }

  // Ease toward the player, then clamp so the view never leaves the world.
  function update(camera, player, world, view, dt, options) {
    const settings = options || {};
    const tile = settings.tileSize || CONFIG.tileSize;
    const target = targetFor(player, world, view, tile);
    const reducedMotion = settings.reducedMotion === true;
    const stiffness = typeof settings.stiffness === "number" ? settings.stiffness : CONFIG.cameraStiffness;
    const delta = Number.isFinite(dt) ? Math.max(0, Math.min(0.1, dt)) : 1 / 60;
    const factor = reducedMotion ? 1 : 1 - Math.exp(-stiffness * delta);
    camera.x += (target.x - camera.x) * factor;
    camera.y += (target.y - camera.y) * factor;
    camera.x = clampAxis(camera.x, world.width * tile, view.width);
    camera.y = clampAxis(camera.y, world.height * tile, view.height);
    return camera;
  }

  return {
    createCamera: createCamera,
    clampAxis: clampAxis,
    targetFor: targetFor,
    update: update
  };
});
