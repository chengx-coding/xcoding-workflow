(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxCamera = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  function clamp(value, min, max) {
    if (max < min) {
      return (min + max) / 2;
    }
    return Math.min(Math.max(value, min), max);
  }

  function worldPixelSize(world, tile) {
    return { width: world.width * tile, height: world.height * tile };
  }

  function maxCamera(world, view, tile) {
    const size = worldPixelSize(world, tile);
    return {
      x: Math.max(0, size.width - view.width),
      y: Math.max(0, size.height - view.height)
    };
  }

  // Ideal camera position: the player's centre in the middle of the viewport,
  // then clamped so the viewport never leaves the world.
  function targetCamera(player, world, view, tile) {
    const centreX = player.x * tile;
    const centreY = (player.y - player.height / 2) * tile;
    const bounds = maxCamera(world, view, tile);
    return {
      x: clamp(centreX - view.width / 2, 0, bounds.x),
      y: clamp(centreY - view.height / 2, 0, bounds.y)
    };
  }

  function createCamera() {
    return { x: 0, y: 0 };
  }

  function approach(current, target, factor) {
    return current + (target - current) * factor;
  }

  // Exponential smoothing keeps the follow soft without storing extra state.
  // dt is clamped so a paused tab cannot teleport the view.
  function followCamera(camera, player, world, view, tile, dt, smoothing) {
    const target = targetCamera(player, world, view, tile);
    const step = Math.max(0, Math.min(Number(dt) || 0, 0.1));
    const speed = Number(smoothing) > 0 ? Number(smoothing) : 9;
    const factor = 1 - Math.exp(-speed * step);
    camera.x = approach(camera.x, target.x, factor);
    camera.y = approach(camera.y, target.y, factor);
    const bounds = maxCamera(world, view, tile);
    camera.x = clamp(camera.x, 0, bounds.x);
    camera.y = clamp(camera.y, 0, bounds.y);
    return camera;
  }

  function visibleRange(camera, world, view, tile) {
    return {
      firstX: Math.max(0, Math.floor(camera.x / tile)),
      lastX: Math.min(world.width - 1, Math.ceil((camera.x + view.width) / tile)),
      firstY: Math.max(0, Math.floor(camera.y / tile)),
      lastY: Math.min(world.height - 1, Math.ceil((camera.y + view.height) / tile))
    };
  }

  return {
    createCamera: createCamera,
    targetCamera: targetCamera,
    followCamera: followCamera,
    visibleRange: visibleRange,
    maxCamera: maxCamera,
    clamp: clamp
  };
});
