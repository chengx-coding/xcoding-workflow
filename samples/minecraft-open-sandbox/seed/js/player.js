(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxPlayer = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  function createPlayer(x, y) {
    return {
      x: x,
      y: y,
      vx: 0,
      vy: 0,
      onGround: false,
      width: 0.7,
      height: 1.8
    };
  }

  // Skeleton step: gravity and horizontal intent only. Collision, jumping and
  // interaction belong to the managed work order's implementation.
  function stepPlayer(player, world, input, dt) {
    player.vx = (input.left ? -CONFIG.moveSpeed : 0) + (input.right ? CONFIG.moveSpeed : 0);
    player.vy += CONFIG.gravity;
    player.x += player.vx * dt;
    player.y += player.vy * dt;
    return player;
  }

  return {
    createPlayer: createPlayer,
    stepPlayer: stepPlayer
  };
});
