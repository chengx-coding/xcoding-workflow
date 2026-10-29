(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxCamera = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function createCamera() {
    return {
      x: 0,
      y: 0,
      shakeX: 0,
      shakeY: 0,
      shakeTime: 0,
      shakeDuration: 0,
      shakeMagnitude: 0,
      shakeClock: 0
    };
  }

  function clampCamera(camera, world) {
    const maxX = Math.max(0, world.width * CONFIG.tileSize - CONFIG.viewWidth);
    const maxY = Math.max(0, world.height * CONFIG.tileSize - CONFIG.viewHeight);
    camera.x = clamp(camera.x, 0, maxX);
    camera.y = clamp(camera.y, 0, maxY);
    return camera;
  }

  function updateCamera(camera, world, player, dt, snap) {
    const targetX = player.x * CONFIG.tileSize - CONFIG.viewWidth / 2;
    const targetY = (player.y - player.height / 2) * CONFIG.tileSize - CONFIG.viewHeight / 2;
    if (snap) {
      camera.x = targetX;
      camera.y = targetY;
    } else {
      const blend = 1 - Math.exp(-8.5 * Math.max(0, dt));
      camera.x += (targetX - camera.x) * blend;
      camera.y += (targetY - camera.y) * blend;
    }
    return clampCamera(camera, world);
  }

  function addShake(camera, magnitude, duration) {
    camera.shakeMagnitude = Math.max(camera.shakeMagnitude, magnitude);
    camera.shakeDuration = Math.max(camera.shakeDuration, duration);
    camera.shakeTime = camera.shakeDuration;
  }

  function updateShake(camera, dt) {
    if (camera.shakeTime <= 0) {
      camera.shakeX = 0;
      camera.shakeY = 0;
      camera.shakeMagnitude = 0;
      return;
    }
    camera.shakeClock += dt;
    camera.shakeTime = Math.max(0, camera.shakeTime - dt);
    const strength = camera.shakeMagnitude * (camera.shakeTime / Math.max(camera.shakeDuration, 0.001));
    camera.shakeX = Math.sin(camera.shakeClock * 87) * strength;
    camera.shakeY = Math.cos(camera.shakeClock * 73) * strength * 0.7;
  }

  function screenToWorld(camera, screenX, screenY) {
    return {
      x: (screenX + camera.x + camera.shakeX) / CONFIG.tileSize,
      y: (screenY + camera.y + camera.shakeY) / CONFIG.tileSize
    };
  }

  function worldToScreen(camera, worldX, worldY) {
    return {
      x: worldX * CONFIG.tileSize - camera.x - camera.shakeX,
      y: worldY * CONFIG.tileSize - camera.y - camera.shakeY
    };
  }

  function visibleTileBounds(camera, world) {
    return {
      firstX: Math.max(0, Math.floor((camera.x + camera.shakeX) / CONFIG.tileSize) - 1),
      lastX: Math.min(
        world.width - 1,
        Math.ceil((camera.x + camera.shakeX + CONFIG.viewWidth) / CONFIG.tileSize) + 1
      ),
      firstY: Math.max(0, Math.floor((camera.y + camera.shakeY) / CONFIG.tileSize) - 1),
      lastY: Math.min(
        world.height - 1,
        Math.ceil((camera.y + camera.shakeY + CONFIG.viewHeight) / CONFIG.tileSize) + 1
      )
    };
  }

  return {
    createCamera: createCamera,
    clampCamera: clampCamera,
    updateCamera: updateCamera,
    addShake: addShake,
    updateShake: updateShake,
    screenToWorld: screenToWorld,
    worldToScreen: worldToScreen,
    visibleTileBounds: visibleTileBounds
  };
});
